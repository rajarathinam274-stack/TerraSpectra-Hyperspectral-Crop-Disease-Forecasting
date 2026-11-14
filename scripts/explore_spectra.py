"""Leakage-aware exploratory analysis for per-leaf hyperspectral spectra.

This is descriptive EDA, not model evaluation. It aggregates ROIs to pot-date
units before class summaries and PCA, retains outlier flags without deleting
samples, and requires identical wavelength axes across images for comparison.
"""
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Sequence

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from sklearn.decomposition import PCA
from sklearn.impute import SimpleImputer

BAND_PATTERN = re.compile(r"^band_(\\d+)$")
DEFAULT_GROUP = "pot_id_candidate"
DEFAULT_DATE = "date_folder_yyyymmdd_candidate"
DEFAULT_IMAGE = "image_relative_path"


class EDAValidationError(ValueError):
    """Raised when spectra cannot be compared without unsupported assumptions."""


def band_columns(columns: Sequence[str]) -> list[str]:
    found = []
    for column in columns:
        match = BAND_PATTERN.fullmatch(str(column))
        if match:
            found.append((int(match.group(1)), str(column)))
    return [name for _, name in sorted(found)]


def parse_csv_columns(value: str | None) -> list[str] | None:
    if not value:
        return None
    return [part.strip() for part in value.split(",") if part.strip()]


def resolve_wavelength_axis(audit_path, frame: pd.DataFrame, bands: list[str]):
    """Resolve a common nm axis from the Day 4 audit, else use band indices."""
    if not audit_path:
        return np.arange(len(bands), dtype=float), "band_index", "No Day 4 audit supplied."
    audit = json.loads(Path(audit_path).read_text(encoding="utf-8"))
    axis_map = audit.get("spectral_axes_by_image", {})
    if not axis_map or DEFAULT_IMAGE not in frame.columns:
        return np.arange(len(bands), dtype=float), "band_index", "No per-image wavelength mapping available."
    axes, missing = [], []
    for image_path in frame[DEFAULT_IMAGE].dropna().astype(str).unique():
        entry = axis_map.get(image_path)
        if not entry or entry.get("wavelengths_nm") is None:
            missing.append(image_path)
            continue
        axis = np.asarray(entry["wavelengths_nm"], dtype=float)
        if len(axis) != len(bands):
            raise EDAValidationError(
                f"Wavelength count for {image_path} ({len(axis)}) does not match spectra bands ({len(bands)})."
            )
        axes.append((image_path, axis))
    if missing:
        raise EDAValidationError(
            "Missing recognized wavelength axes for image(s): " + ", ".join(missing[:5])
            + ". Do not combine rows until wavelength metadata is resolved."
        )
    if not axes:
        return np.arange(len(bands), dtype=float), "band_index", "No usable wavelength axis found."
    reference_path, reference = axes[0]
    for image_path, axis in axes[1:]:
        if not np.allclose(reference, axis, rtol=0, atol=0.1):
            raise EDAValidationError(
                f"Wavelength axis differs between {reference_path} and {image_path}. "
                "Resample to a documented common grid before cross-image comparison."
            )
    if not np.all(np.isfinite(reference)) or np.any(np.diff(reference) <= 0):
        raise EDAValidationError("Wavelength axis must be finite and strictly increasing.")
    return reference, "nm", f"Common wavelength axis verified across {len(axes)} images."


def attach_annotations(spectra: pd.DataFrame, labels_path, spectrum_keys, label_keys,
                       class_column, genotype_column) -> pd.DataFrame:
    if not labels_path:
        if class_column or genotype_column:
            raise EDAValidationError("Class/genotype columns require --labels-csv and explicit join keys.")
        return spectra.copy()
    if not spectrum_keys or not label_keys or len(spectrum_keys) != len(label_keys):
        raise EDAValidationError("Annotation join requires equal-length --spectrum-keys and --label-keys.")
    labels = pd.read_csv(labels_path, encoding="utf-8-sig", low_memory=False)
    missing_s = [key for key in spectrum_keys if key not in spectra.columns]
    missing_l = [key for key in label_keys if key not in labels.columns]
    if missing_s or missing_l:
        raise EDAValidationError(f"Join key(s) missing; spectra={missing_s}, labels={missing_l}.")
    if labels[label_keys].isna().any().any():
        raise EDAValidationError("Annotation join keys contain missing values.")
    if labels.duplicated(label_keys).any():
        raise EDAValidationError("Annotation join keys are not unique; resolve duplicate label rows first.")
    labels = labels.rename(columns={lk: sk for sk, lk in zip(spectrum_keys, label_keys) if lk != sk})
    for column in (class_column, genotype_column):
        if column and column not in labels.columns:
            raise EDAValidationError(f"Requested annotation column {column!r} is missing.")
    result = spectra.merge(labels, on=spectrum_keys, how="left", validate="many_to_one", indicator=True)
    unmatched = int((result["_merge"] != "both").sum())
    result = result.drop(columns=["_merge"])
    if unmatched:
        raise EDAValidationError(f"{unmatched} spectra rows did not match annotation keys; do not infer labels.")
    for column in (class_column, genotype_column):
        if column and result[column].isna().any():
            raise EDAValidationError(f"Annotation column {column!r} contains missing values after join.")
    return result


def aggregate_pot_date(frame, bands, group_column, date_column, class_column, genotype_column):
    if group_column not in frame.columns:
        raise EDAValidationError(f"Biological grouping column {group_column!r} is missing.")
    if date_column not in frame.columns:
        raise EDAValidationError(f"Date column {date_column!r} is missing.")
    for column in (group_column, date_column):
        if frame[column].isna().any() or frame[column].astype(str).str.strip().eq("").any():
            raise EDAValidationError(f"{column!r} contains missing or blank values.")
    keys = [group_column, date_column]
    for optional in (class_column, genotype_column):
        if optional:
            if optional not in frame.columns:
                raise EDAValidationError(f"Requested label column {optional!r} is missing.")
            n_unique = frame.groupby(keys, dropna=False)[optional].nunique(dropna=False)
            if (n_unique > 1).any():
                raise EDAValidationError(f"{optional!r} varies within a pot-date group; inspect annotation joins.")
            keys.append(optional)
    numeric = frame[bands].apply(pd.to_numeric, errors="coerce")
    working = pd.concat([frame[keys].reset_index(drop=True), numeric.reset_index(drop=True)], axis=1)
    return working.groupby(keys, dropna=False, as_index=False)[bands].mean(), keys


def compute_quality_report(frame, grouped, bands, group_column, date_column):
    matrix = frame[bands].apply(pd.to_numeric, errors="coerce").to_numpy(dtype=float)
    finite_fraction = np.isfinite(matrix).mean(axis=1)
    row_quality = frame[[c for c in [group_column, date_column, DEFAULT_IMAGE, "leaf_id_within_image"] if c in frame]].copy()
    row_quality["finite_band_fraction"] = finite_fraction
    grouped_matrix = grouped[bands].to_numpy(dtype=float)
    q1, q3 = np.nanpercentile(grouped_matrix, [25, 75], axis=0)
    iqr = q3 - q1
    outlier_mask = (grouped_matrix < (q1 - 1.5 * iqr)) | (grouped_matrix > (q3 + 1.5 * iqr))
    outlier_fraction = np.nanmean(outlier_mask, axis=1)
    report = {
        "roi_rows": int(len(frame)),
        "pot_date_units": int(len(grouped)),
        "unique_groups": int(frame[group_column].nunique()),
        "unique_dates": sorted(frame[date_column].astype(str).unique().tolist()),
        "band_count": int(len(bands)),
        "missing_spectral_values": int(np.isnan(matrix).sum()),
        "nonfinite_spectral_values": int((~np.isfinite(matrix)).sum()),
        "mean_finite_fraction_per_roi": float(np.mean(finite_fraction)),
        "rois_below_95pct_finite_bands": int((finite_fraction < 0.95).sum()),
        "pot_date_units_with_any_band_iqr_outlier": int((outlier_fraction > 0).sum()),
        "pot_date_outlier_fraction_median": float(np.nanmedian(outlier_fraction)),
        "outlier_policy": "Flag only; no observation is automatically removed.",
        "replicate_unit_for_class_date_summaries": group_column,
        "warning": "Pot-date summaries are the analysis rows; ROI rows and pixels are not independent replicates.",
    }
    return report, row_quality


def summarize_class_date(grouped, bands, date_column, class_column, group_column):
    if not class_column:
        return pd.DataFrame()
    rows = []
    for (date, label), subset in grouped.groupby([date_column, class_column], dropna=False):
        values = subset[bands].to_numpy(dtype=float)
        row = {date_column: date, class_column: label, "n_pots": int(subset[group_column].nunique())}
        for index, band in enumerate(bands):
            finite = values[:, index][np.isfinite(values[:, index])]
            row[f"{band}_mean"] = float(np.mean(finite)) if len(finite) else np.nan
            row[f"{band}_sd_between_pots"] = float(np.std(finite, ddof=1)) if len(finite) > 1 else np.nan
        rows.append(row)
    return pd.DataFrame(rows)


def plot_spectral_profiles(grouped, bands, axis, axis_label, date_column, class_column, group_column, output_dir):
    plot_dir = output_dir / "spectral_profiles_by_date"
    plot_dir.mkdir(parents=True, exist_ok=True)
    written = []
    labels = sorted(grouped[class_column].dropna().astype(str).unique()) if class_column else ["all_pots"]
    for date in sorted(grouped[date_column].astype(str).unique()):
        fig, ax = plt.subplots(figsize=(10, 5))
        day = grouped[grouped[date_column].astype(str) == date]
        for label in labels:
            subset = day if not class_column else day[day[class_column].astype(str) == label]
            if subset.empty:
                continue
            values = subset[bands].to_numpy(dtype=float)
            mean = np.nanmean(values, axis=0)
            sd = np.nanstd(values, axis=0, ddof=1) if len(values) > 1 else np.zeros(len(bands))
            ax.plot(axis, mean, label=f"{label} (n pots={subset[group_column].nunique()})")
            ax.fill_between(axis, mean - sd, mean + sd, alpha=0.15)
        ax.set_title(f"Pot-level mean spectra — {date}")
        ax.set_xlabel(f"Wavelength ({axis_label})" if axis_label == "nm" else "Band index (wavelength unavailable)")
        ax.set_ylabel("Mean dark-current-corrected intensity (not reflectance)")
        ax.legend(loc="best", fontsize="small")
        ax.grid(True, alpha=0.2)
        fig.tight_layout()
        name = f"spectra_{date}.png"
        fig.savefig(plot_dir / name, dpi=150)
        plt.close(fig)
        written.append(str((plot_dir / name).relative_to(output_dir)))
    return written


def run_eda(spectra_csv, output_dir, *, audit_json=None, labels_csv=None,
            spectrum_keys=None, label_keys=None, class_column=None, genotype_column=None,
            group_column=DEFAULT_GROUP, date_column=DEFAULT_DATE):
    spectra_path, output_dir = Path(spectra_csv), Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    frame = pd.read_csv(spectra_path, encoding="utf-8-sig", low_memory=False)
    bands = band_columns(frame.columns)
    if len(bands) < 2:
        raise EDAValidationError("Expected at least two band_NNN spectral columns.")
    frame = attach_annotations(frame, labels_csv, spectrum_keys, label_keys, class_column, genotype_column)
    axis, axis_unit, axis_note = resolve_wavelength_axis(audit_json, frame, bands)
    grouped, group_keys = aggregate_pot_date(frame, bands, group_column, date_column, class_column, genotype_column)
    quality, row_quality = compute_quality_report(frame, grouped, bands, group_column, date_column)
    quality.update({
        "spectra_csv": str(spectra_path),
        "wavelength_axis_unit": axis_unit,
        "wavelength_axis_note": axis_note,
        "spectrum_domain": sorted(frame["spectrum_domain"].dropna().astype(str).unique().tolist())
            if "spectrum_domain" in frame.columns else ["unspecified"],
        "class_column": class_column,
        "genotype_column": genotype_column,
        "group_keys": group_keys,
        "annotation_join": "not supplied" if not labels_csv else "explicit many-to-one join; unmatched rows rejected",
        "pca_interpretation": "Exploratory visualization only; not a trained predictive transform and not model validation.",
    })
    grouped.to_csv(output_dir / "pot_date_spectra.csv", index=False)
    row_quality.to_csv(output_dir / "roi_quality.csv", index=False)
    summary = summarize_class_date(grouped, bands, date_column, class_column, group_column)
    if not summary.empty:
        summary.to_csv(output_dir / "spectral_summary_by_class_date.csv", index=False)
    plots = plot_spectral_profiles(grouped, bands, axis, axis_unit, date_column, class_column, group_column, output_dir)

    pca_info = {"status": "skipped", "reason": "Need at least three pot-date rows and two usable bands."}
    if len(grouped) >= 3:
        x = grouped[bands].to_numpy(dtype=float)
        x_imp = SimpleImputer(strategy="median").fit_transform(x)
        if x_imp.shape[1] >= 2 and np.isfinite(x_imp).all():
            pca = PCA(n_components=2, svd_solver="full")
            scores = pca.fit_transform(x_imp)
            score_frame = grouped[group_keys].copy()
            score_frame["PC1"], score_frame["PC2"] = scores[:, 0], scores[:, 1]
            score_frame.to_csv(output_dir / "pca_pot_date_scores.csv", index=False)
            fig, ax = plt.subplots(figsize=(8, 6))
            if class_column:
                for label, subset in score_frame.groupby(class_column):
                    ax.scatter(subset["PC1"], subset["PC2"], label=str(label), alpha=0.8)
                ax.legend(title=class_column)
            else:
                ax.scatter(score_frame["PC1"], score_frame["PC2"], alpha=0.8)
            ax.set_xlabel(f"PC1 ({pca.explained_variance_ratio_[0]:.1%} variance)")
            ax.set_ylabel(f"PC2 ({pca.explained_variance_ratio_[1]:.1%} variance)")
            ax.set_title("Exploratory PCA — pot-date mean spectra")
            ax.grid(True, alpha=0.2)
            fig.tight_layout()
            fig.savefig(output_dir / "pca_pot_date.png", dpi=150)
            plt.close(fig)
            pca_info = {
                "status": "completed_descriptive_only",
                "rows": int(len(score_frame)),
                "explained_variance_ratio": pca.explained_variance_ratio_.tolist(),
                "imputation": "Band-wise median fitted on this EDA table; refit inside training folds for predictive work.",
            }
    quality["pca"] = pca_info
    quality["plots"] = plots + (["pca_pot_date.png"] if pca_info["status"].startswith("completed") else [])
    (output_dir / "eda_report.json").write_text(json.dumps(quality, indent=2), encoding="utf-8")
    return quality


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--spectra-csv", type=Path, required=True)
    parser.add_argument("--audit-json", type=Path, default=None)
    parser.add_argument("--labels-csv", type=Path, default=None)
    parser.add_argument("--spectrum-keys", default=None, help="Comma-separated spectrum CSV join key(s).")
    parser.add_argument("--label-keys", default=None, help="Comma-separated annotation CSV join key(s), same count/order.")
    parser.add_argument("--class-column", default=None)
    parser.add_argument("--genotype-column", default=None)
    parser.add_argument("--group-column", default=DEFAULT_GROUP)
    parser.add_argument("--date-column", default=DEFAULT_DATE)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    report = run_eda(
        args.spectra_csv, args.output_dir, audit_json=args.audit_json,
        labels_csv=args.labels_csv, spectrum_keys=parse_csv_columns(args.spectrum_keys),
        label_keys=parse_csv_columns(args.label_keys), class_column=args.class_column,
        genotype_column=args.genotype_column, group_column=args.group_column,
        date_column=args.date_column,
    )
    print(json.dumps({
        "roi_rows": report["roi_rows"], "pot_date_units": report["pot_date_units"],
        "unique_groups": report["unique_groups"], "unique_dates": report["unique_dates"],
        "pca_status": report["pca"]["status"], "output_dir": str(args.output_dir),
    }, indent=2))


if __name__ == "__main__":
    main()

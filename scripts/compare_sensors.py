"""Fair, pot-grouped comparison of VNIR, SWIR and non-overlapping fusion."""
from __future__ import annotations
import argparse, json, re
from pathlib import Path
import numpy as np
import pandas as pd
from sklearn.base import clone
from sklearn.compose import ColumnTransformer
from sklearn.impute import SimpleImputer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import (accuracy_score, balanced_accuracy_score,
    classification_report, confusion_matrix, f1_score, precision_score,
    recall_score, roc_auc_score)
from sklearn.model_selection import StratifiedGroupKFold
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler

BAND_RE = re.compile(r"^band_(\d+)$")
DEFAULT_GROUP = "pot_id_candidate"
DEFAULT_DATE = "date_folder_yyyymmdd_candidate"
TARGETS = {"treatment_assignment", "observed_infection_status", "symptom_severity"}

class SensorComparisonError(ValueError):
    pass

def ordered_bands(columns):
    pairs = [(int(m.group(1)), str(c)) for c in columns
             if (m := BAND_RE.fullmatch(str(c)))]
    pairs.sort()
    if len(pairs) < 2 or len({i for i, _ in pairs}) != len(pairs):
        raise SensorComparisonError("Need at least two uniquely indexed band_NNN columns.")
    return [name for _, name in pairs]

def read_table(path, modality, target, semantics, date_col, group_col, genotype_col):
    path = Path(path)
    if not path.is_file():
        raise FileNotFoundError(path)
    header = pd.read_csv(path, nrows=0).columns.tolist()
    required = [target, date_col, group_col] + ([genotype_col] if genotype_col else [])
    missing = [c for c in required if c not in header]
    if missing:
        raise SensorComparisonError(f"{modality}: missing columns {missing}.")
    frame = pd.read_csv(path, encoding="utf-8-sig", low_memory=False,
                        dtype={c: "string" for c in required})
    for c in required:
        if frame[c].isna().any() or frame[c].str.strip().eq("").any():
            raise SensorComparisonError(f"{modality}: {c!r} contains missing/blank values.")
    bands = ordered_bands(frame.columns)
    X = frame[bands].apply(pd.to_numeric, errors="coerce").replace([np.inf, -np.inf], np.nan)
    if X.isna().all().any():
        raise SensorComparisonError(f"{modality}: at least one band is entirely missing.")
    if semantics == "treatment_assignment":
        if (frame.groupby(group_col)[target].nunique(dropna=False) > 1).any():
            raise SensorComparisonError(f"{modality}: treatment-assignment label changes within a pot.")
    if genotype_col and (frame.groupby(group_col)[genotype_col].nunique(dropna=False) > 1).any():
        raise SensorComparisonError(f"{modality}: genotype annotation changes within a pot.")
    frame[bands] = X
    return frame, bands

def load_matched(vnir_csv, swir_csv, *, target, semantics, date_value,
                 date_col=DEFAULT_DATE, group_col=DEFAULT_GROUP, genotype_col=None):
    if semantics not in TARGETS:
        raise SensorComparisonError(f"target semantics must be one of {sorted(TARGETS)}")
    v, vb = read_table(vnir_csv, "VNIR", target, semantics, date_col, group_col, genotype_col)
    s, sb = read_table(swir_csv, "SWIR", target, semantics, date_col, group_col, genotype_col)
    keys = [group_col, date_col]
    v, s = (f.loc[f[date_col].astype(str) == str(date_value)].copy() for f in (v, s))
    if v.empty or s.empty:
        raise SensorComparisonError(f"No rows for selected date {date_value!r}.")
    for name, f in (("VNIR", v), ("SWIR", s)):
        if f.duplicated(keys).any() or f[group_col].duplicated().any():
            raise SensorComparisonError(f"{name}: expected exactly one pot-date row per pot.")
    vk = set(map(tuple, v[keys].astype(str).to_numpy()))
    sk = set(map(tuple, s[keys].astype(str).to_numpy()))
    if vk != sk:
        raise SensorComparisonError(
            f"VNIR/SWIR keys differ; only VNIR={sorted(vk-sk)[:5]}, only SWIR={sorted(sk-vk)[:5]}"
        )
    v, s = (f.sort_values(keys).reset_index(drop=True) for f in (v, s))
    if not v[keys].astype(str).equals(s[keys].astype(str)):
        raise SensorComparisonError("Internal pot/date ordering mismatch.")
    for col in [target] + ([genotype_col] if genotype_col else []):
        if not v[col].astype(str).equals(s[col].astype(str)):
            raise SensorComparisonError(f"VNIR/SWIR {col} annotations disagree.")
    y = v[target].astype(str)
    groups = v[group_col].astype(str)
    if y.nunique() < 2:
        raise SensorComparisonError("Selected date must contain at least two classes.")
    meta_cols = keys + [target] + ([genotype_col] if genotype_col else [])
    return {
        "metadata": v[meta_cols].copy(), "X_vnir": v[vb].copy(), "X_swir": s[sb].copy(),
        "vnir_bands": vb, "swir_bands": sb, "y": y, "groups": groups,
        "labels": sorted(y.unique()), "class_counts": y.value_counts().sort_index().to_dict(),
        "matched_pots": int(groups.nunique()), "selected_date": str(date_value),
    }

def load_axis(path, modality, n_bands):
    audit = json.loads(Path(path).read_text(encoding="utf-8"))
    if audit.get("modality", "").upper() not in {"", modality}:
        raise SensorComparisonError(f"{modality} audit declares a different modality.")
    entries = audit.get("spectral_axes_by_image", {})
    if not entries:
        raise SensorComparisonError(f"{modality} audit has no spectral_axes_by_image.")
    axes = []
    for image, entry in entries.items():
        vals = entry.get("wavelengths_nm") if isinstance(entry, dict) else None
        if vals is None:
            raise SensorComparisonError(f"{modality} audit lacks nm wavelengths for {image}.")
        axis = np.asarray(vals, dtype=float)
        if len(axis) != n_bands or not np.isfinite(axis).all() or np.any(np.diff(axis) <= 0):
            raise SensorComparisonError(f"{modality} has invalid wavelength axis for {image}.")
        axes.append((image, axis))
    ref_name, ref = axes[0]
    for name, axis in axes[1:]:
        if not np.allclose(ref, axis, rtol=0, atol=0.1):
            raise SensorComparisonError(f"{modality} axes differ between {ref_name} and {name}.")
    return ref, {"image_count": len(axes), "bands": len(ref),
                 "min_nm": float(ref.min()), "max_nm": float(ref.max())}

def make_features(data, va, sa, tolerance):
    if tolerance < 0 or not np.isfinite(tolerance):
        raise SensorComparisonError("Overlap tolerance must be finite and non-negative.")
    keep = sa > va.max() + tolerance
    kept = [b for b, ok in zip(data["swir_bands"], keep) if ok]
    dropped = [b for b, ok in zip(data["swir_bands"], keep) if not ok]
    if len(kept) < 2:
        raise SensorComparisonError("Fewer than two non-overlapping SWIR bands remain.")
    vn = [f"VNIR__{b}" for b in data["vnir_bands"]]
    sn = [f"SWIR__{b}" for b in kept]
    fusion = pd.concat([
        data["X_vnir"].rename(columns=dict(zip(data["vnir_bands"], vn))),
        data["X_swir"][kept].rename(columns=dict(zip(kept, sn)))
    ], axis=1)
    return {"VNIR": data["X_vnir"], "SWIR": data["X_swir"],
            "FUSION_NONOVERLAP": fusion}, {
        "vnir_range_nm": [float(va.min()), float(va.max())],
        "swir_range_nm": [float(sa.min()), float(sa.max())],
        "swir_bands_retained": kept, "swir_bands_excluded": dropped,
        "fusion_rule": "all VNIR bands + SWIR bands > max(VNIR)+tolerance; no interpolation",
        "fusion_feature_columns": vn + sn, "vnir_feature_columns": vn,
        "swir_feature_columns": sn, "overlap_tolerance_nm": float(tolerance),
    }

def lr_pipeline():
    return Pipeline([
        ("imputer", SimpleImputer(strategy="median", keep_empty_features=True)),
        ("scaler", StandardScaler()),
        ("classifier", LogisticRegression(C=1.0, class_weight="balanced",
                                          max_iter=5000, solver="lbfgs", random_state=42))
    ])

def fusion_pipeline(vcols, scols):
    branch = lambda: Pipeline([
        ("imputer", SimpleImputer(strategy="median", keep_empty_features=True)),
        ("scaler", StandardScaler())
    ])
    prep = ColumnTransformer([
        ("vnir", branch(), vcols), ("swir", branch(), scols)
    ], transformer_weights={"vnir": 1/np.sqrt(len(vcols)),
                             "swir": 1/np.sqrt(len(scols))},
       remainder="drop", verbose_feature_names_out=False)
    return Pipeline([("features", prep),
        ("classifier", LogisticRegression(C=1.0, class_weight="balanced",
                                          max_iter=5000, solver="lbfgs", random_state=42))])

def metrics(y, pred, labels, probs):
    rep = classification_report(y, pred, labels=labels, output_dict=True, zero_division=0)
    out = {
        "accuracy": float(accuracy_score(y, pred)),
        "balanced_accuracy": float(balanced_accuracy_score(y, pred)),
        "macro_f1": float(f1_score(y, pred, labels=labels, average="macro", zero_division=0)),
        "macro_precision": float(precision_score(y, pred, labels=labels, average="macro", zero_division=0)),
        "macro_recall": float(recall_score(y, pred, labels=labels, average="macro", zero_division=0)),
        "per_class": {str(c): {k: float(rep[str(c)][k]) for k in ["precision","recall","f1-score"]}
                      | {"support": int(rep[str(c)]["support"])} for c in labels},
        "confusion_matrix": confusion_matrix(y, pred, labels=labels).tolist()
    }
    if len(labels) == 2:
        out["roc_auc"] = float(roc_auc_score((np.asarray(y) == labels[1]).astype(int), probs[:, 1]))
        out["roc_auc_positive_class"] = labels[1]
    else:
        out["roc_auc_ovr_macro"] = float(roc_auc_score(
            y, probs, labels=labels, multi_class="ovr", average="macro"
        ))
    return out

def run(vnir_csv, swir_csv, vnir_audit, swir_audit, output_dir, *,
        target, semantics, date_value, date_col=DEFAULT_DATE, group_col=DEFAULT_GROUP,
        genotype_col=None, n_splits=5, random_state=42, overlap_tolerance_nm=0.5,
        spectrum_domain="dark_current_corrected_intensity_not_reflectance"):
    if n_splits < 2 or random_state < 0:
        raise SensorComparisonError("n_splits must be >=2 and random_state non-negative.")
    d = load_matched(vnir_csv, swir_csv, target=target, semantics=semantics,
                     date_value=date_value, date_col=date_col, group_col=group_col,
                     genotype_col=genotype_col)
    va, vi = load_axis(vnir_audit, "VNIR", len(d["vnir_bands"]))
    sa, si = load_axis(swir_audit, "SWIR", len(d["swir_bands"]))
    sets, fusion = make_features(d, va, sa, overlap_tolerance_nm)
    counts = pd.DataFrame({"y": d["y"], "group": d["groups"]}).drop_duplicates().groupby("y").group.nunique()
    if int(counts.min()) < n_splits:
        raise SensorComparisonError(f"Each class needs >= {n_splits} independent pots; counts={counts.to_dict()}.")
    splits = list(StratifiedGroupKFold(n_splits=n_splits, shuffle=True,
                  random_state=random_state).split(sets["VNIR"], d["y"], d["groups"]))
    fold_ids = np.full(len(d["y"]), -1, dtype=int)
    fold_info = []
    for i, (tr, te) in enumerate(splits, 1):
        tg, vg = set(d["groups"].iloc[tr]), set(d["groups"].iloc[te])
        if tg & vg or set(d["y"].iloc[tr]) != set(d["labels"]) or set(d["y"].iloc[te]) != set(d["labels"]):
            raise SensorComparisonError(f"Fold {i} has group overlap or lacks a class.")
        if np.any(fold_ids[te] != -1):
            raise SensorComparisonError("A pot appears in multiple test folds.")
        fold_ids[te] = i
        fold_info.append({"fold": i, "train_pots": len(tg), "test_pots": len(vg),
                          "train_group_ids": sorted(tg), "test_group_ids": sorted(vg)})
    if np.any(fold_ids < 1):
        raise SensorComparisonError("Incomplete out-of-fold fold assignments.")

    outdir = Path(output_dir); outdir.mkdir(parents=True, exist_ok=True)
    d["metadata"].assign(fold=fold_ids).to_csv(outdir/"shared_split_assignments.csv", index=False)
    d["metadata"].to_csv(outdir/"matched_pot_date_samples.csv", index=False)
    all_metrics, fold_metrics, results = [], [], {}
    for name, X in sets.items():
        if name == "FUSION_NONOVERLAP":
            model = fusion_pipeline(fusion["vnir_feature_columns"], fusion["swir_feature_columns"])
        else:
            model = lr_pipeline()
        pred = np.empty(len(d["y"]), dtype=object)
        probs = np.full((len(d["y"]), len(d["labels"])), np.nan)
        for i, (tr, te) in enumerate(splits, 1):
            fitted = clone(model).fit(X.iloc[tr], d["y"].iloc[tr])
            pred[te] = fitted.predict(X.iloc[te]).astype(str)
            p = fitted.predict_proba(X.iloc[te])
            classes = list(map(str, fitted.named_steps["classifier"].classes_))
            for j, label in enumerate(d["labels"]):
                probs[te, j] = p[:, classes.index(label)]
            fm = metrics(d["y"].iloc[te].to_numpy(), pred[te].astype(str), d["labels"], probs[te])
            fm.update({"feature_set": name, "fold": i,
                       "train_pots": fold_info[i-1]["train_pots"],
                       "test_pots": fold_info[i-1]["test_pots"]})
            fold_metrics.append(fm)
        if pd.isna(pred).any() or not np.isfinite(probs).all():
            raise SensorComparisonError(f"{name}: incomplete OOF outputs.")
        pooled = metrics(d["y"], pred.astype(str), d["labels"], probs)
        pooled.update({"feature_count": int(X.shape[1]), "matched_pots": d["matched_pots"]})
        results[name] = pooled
        metric_keys = ["accuracy","balanced_accuracy","macro_f1","macro_precision","macro_recall"]
        metric_keys += ["roc_auc"] if "roc_auc" in pooled else ["roc_auc_ovr_macro"]
        all_metrics.append({"feature_set": name, "feature_count": X.shape[1],
            "matched_pots": d["matched_pots"], **{k: pooled[k] for k in metric_keys}})
        table = d["metadata"].copy()
        table["fold"] = fold_ids; table["predicted_label"] = pred.astype(str)
        for j, label in enumerate(d["labels"]):
            safe = re.sub(r"[^A-Za-z0-9]+", "_", label).strip("_") or f"class_{j}"
            table[f"probability_{safe}"] = probs[:, j]
        table.to_csv(outdir/f"oof_predictions_{name.lower()}.csv", index=False)
        pd.DataFrame(confusion_matrix(d["y"], pred.astype(str), labels=d["labels"]),
            index=[f"true_{c}" for c in d["labels"]],
            columns=[f"pred_{c}" for c in d["labels"]]).to_csv(outdir/f"confusion_matrix_{name.lower()}.csv")

    pd.DataFrame(all_metrics).sort_values("feature_set").to_csv(outdir/"sensor_comparison_metrics.csv", index=False)
    pd.DataFrame(fold_metrics).to_csv(outdir/"sensor_comparison_fold_metrics.csv", index=False)
    report = {
        "experiment": "Day 9 matched pot-date VNIR/SWIR/fusion comparison",
        "date": d["selected_date"], "target": target, "target_semantics": semantics,
        "matched_pots": d["matched_pots"], "class_pot_counts": d["class_counts"],
        "spectrum_domain": spectrum_domain, "group_column": group_col,
        "n_splits": n_splits, "random_state": random_state, "folds": fold_info,
        "classifier": "fixed LogisticRegression(C=1.0, class_weight=balanced)",
        "preprocessing": "Fold-fitted median imputation and standardization.",
        "wavelength_axes": {"VNIR": vi, "SWIR": si}, "fusion": fusion, "metrics": results,
        "selection_note": "Choosing the highest of three OOF scores adds selection optimism; confirm on a separately predeclared untouched evaluation.",
        "limitations": [
            "Exact pot/date keys and target labels must match between modalities.",
            "Pot is the independent split unit; pixels/ROIs are not independent replicates.",
            "Pot-date matching does not establish that both cameras imaged the same individual leaf.",
            "Fusion uses VNIR plus SWIR wavelengths above the VNIR maximum; no interpolation or overlap double-counting.",
            "Sensor blocks are independently imputed/scaled in each training fold and weighted by inverse square-root feature count.",
            "Same-date classification is not future disease forecasting.",
            "Controlled growth-chamber results are not field validation."
        ],
        "outputs": ["matched_pot_date_samples.csv","shared_split_assignments.csv",
            "sensor_comparison_metrics.csv","sensor_comparison_fold_metrics.csv",
            "oof_predictions_vnir.csv","oof_predictions_swir.csv",
            "oof_predictions_fusion_nonoverlap.csv","confusion_matrix_vnir.csv",
            "confusion_matrix_swir.csv","confusion_matrix_fusion_nonoverlap.csv"]
    }
    report["interpretation"] = {
        "treatment_assignment": "Experimental treatment discrimination only; not symptom detection or forecasting.",
        "observed_infection_status": "Same-date infection classification only; not future forecasting.",
        "symptom_severity": "Same-date severity classification only; not future forecasting."
    }[semantics]
    (outdir/"sensor_comparison_report.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    return report

def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--vnir-csv", type=Path, required=True); p.add_argument("--swir-csv", type=Path, required=True)
    p.add_argument("--vnir-audit", type=Path, required=True); p.add_argument("--swir-audit", type=Path, required=True)
    p.add_argument("--output-dir", type=Path, required=True); p.add_argument("--target-column", required=True)
    p.add_argument("--target-semantics", choices=sorted(TARGETS), required=True)
    p.add_argument("--date-value", required=True); p.add_argument("--date-column", default=DEFAULT_DATE)
    p.add_argument("--group-column", default=DEFAULT_GROUP); p.add_argument("--genotype-column", default=None)
    p.add_argument("--n-splits", type=int, default=5); p.add_argument("--random-state", type=int, default=42)
    p.add_argument("--overlap-tolerance-nm", type=float, default=0.5)
    p.add_argument("--spectrum-domain", choices=["dark_current_corrected_intensity_not_reflectance","validated_reflectance"],
                   default="dark_current_corrected_intensity_not_reflectance")
    a = p.parse_args()
    r = run(a.vnir_csv, a.swir_csv, a.vnir_audit, a.swir_audit, a.output_dir,
        target=a.target_column, semantics=a.target_semantics, date_value=a.date_value,
        date_col=a.date_column, group_col=a.group_column, genotype_col=a.genotype_column,
        n_splits=a.n_splits, random_state=a.random_state,
        overlap_tolerance_nm=a.overlap_tolerance_nm, spectrum_domain=a.spectrum_domain)
    print(json.dumps({"date": r["date"], "matched_pots": r["matched_pots"],
        "class_pot_counts": r["class_pot_counts"],
        "metrics": {k: {m: v[m] for m in ["macro_f1","balanced_accuracy","roc_auc","roc_auc_ovr_macro","feature_count"] if m in v}
                    for k,v in r["metrics"].items()}}, indent=2))

if __name__ == "__main__":
    main()

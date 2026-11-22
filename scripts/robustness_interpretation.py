"""Pot-grouped held-out error, band-importance and robustness analysis.

This evaluates one predeclared model at one acquisition date. Preprocessing is
fit within training folds. It is same-date classification, never forecasting.
"""
from __future__ import annotations
import argparse
import json
import re
from pathlib import Path
import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestClassifier
from sklearn.impute import SimpleImputer
from sklearn.inspection import permutation_importance
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import (accuracy_score, balanced_accuracy_score,
    classification_report, confusion_matrix, f1_score)
from sklearn.model_selection import StratifiedGroupKFold
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler
from sklearn.svm import SVC

DATE = "date_folder_yyyymmdd_candidate"
GROUP = "pot_id_candidate"
BAND_RE = re.compile(r"^band_(\d+)$")
SEMANTICS = {"treatment_assignment", "observed_infection_status", "symptom_severity"}

class RobustnessError(ValueError):
    """Invalid or scientifically unsupported robustness input."""


def bands_from(columns):
    found = [(int(m.group(1)), str(c)) for c in columns
             if (m := BAND_RE.fullmatch(str(c)))]
    result = [name for _, name in sorted(found)]
    if len(result) < 2:
        raise RobustnessError("Expected at least two band_NNN spectral columns.")
    return result


def prepare(frame, target, date_value, date_col, group_col, semantics):
    if semantics not in SEMANTICS:
        raise RobustnessError(f"target semantics must be one of {sorted(SEMANTICS)}")
    required = [target, date_col, group_col]
    missing = [c for c in required if c not in frame]
    if missing:
        raise RobustnessError(f"Required columns missing: {missing}")
    for c in required:
        if frame[c].isna().any() or frame[c].astype(str).str.strip().eq("").any():
            raise RobustnessError(f"Required column {c!r} contains missing/blank values")
    if semantics == "treatment_assignment":
        if (frame.groupby(group_col)[target].nunique(dropna=False) > 1).any():
            raise RobustnessError("Treatment-assignment label changes within a pot across dates")
    selected = frame.loc[frame[date_col].astype(str) == str(date_value)].copy()
    if selected.empty:
        raise RobustnessError(f"No rows found for selected date {date_value!r}")
    if selected[group_col].duplicated().any():
        raise RobustnessError("Expected exactly one aggregated pot-date row per pot")
    bands = bands_from(frame.columns)
    X = selected[bands].apply(pd.to_numeric, errors="coerce").replace([np.inf, -np.inf], np.nan)
    empty = X.columns[X.isna().all()].tolist()
    if empty:
        raise RobustnessError(f"All values missing in bands: {empty}")
    y = selected[target].astype(str)
    groups = selected[group_col].astype(str)
    counts = y.value_counts()
    if len(counts) < 2:
        raise RobustnessError("Target must contain at least two classes")
    return selected.reset_index(drop=True), X.reset_index(drop=True), y.reset_index(drop=True), groups.reset_index(drop=True), bands, counts


def make_pipeline(model_name, seed):
    if model_name == "logistic_regression":
        model, scaler = LogisticRegression(C=1.0, class_weight="balanced", max_iter=5000,
                                            solver="lbfgs", random_state=seed), StandardScaler()
    elif model_name == "rbf_svm":
        model, scaler = SVC(C=1.0, kernel="rbf", gamma="scale", class_weight="balanced",
                            random_state=seed), StandardScaler()
    elif model_name == "random_forest":
        model, scaler = RandomForestClassifier(n_estimators=300, max_features="sqrt",
            class_weight="balanced_subsample", n_jobs=1, random_state=seed), "passthrough"
    else:
        raise RobustnessError(f"Unsupported model: {model_name}")
    return Pipeline([("imputer", SimpleImputer(strategy="median", keep_empty_features=True)),
                     ("scaler", scaler), ("classifier", model)])


def score(y, pred, labels):
    return {"accuracy": float(accuracy_score(y, pred)),
            "balanced_accuracy": float(balanced_accuracy_score(y, pred)),
            "macro_f1": float(f1_score(y, pred, labels=labels, average="macro", zero_division=0)),
            "per_class": classification_report(y, pred, labels=labels, output_dict=True, zero_division=0),
            "confusion_matrix": confusion_matrix(y, pred, labels=labels).tolist()}


def run(input_csv, output_dir, *, target_column, target_semantics, date_value,
        date_column=DATE, group_column=GROUP, model_name="logistic_regression",
        n_splits=5, permutation_repeats=10, noise_repeats=10,
        noise_sd_fraction=0.05, random_state=42):
    if n_splits < 2 or permutation_repeats < 1 or noise_repeats < 1:
        raise RobustnessError("n_splits >= 2 and both repeat counts >= 1 are required")
    if not np.isfinite(noise_sd_fraction) or noise_sd_fraction < 0:
        raise RobustnessError("noise_sd_fraction must be finite and non-negative")
    frame = pd.read_csv(input_csv, encoding="utf-8-sig", low_memory=False,
                        dtype={group_column: "string", date_column: "string", target_column: "string"})
    selected, X, y, groups, bands, counts = prepare(
        frame, target_column, date_value, date_column, group_column, target_semantics)
    if int(counts.min()) < n_splits:
        raise RobustnessError(f"Each class needs at least {n_splits} independent pots; counts={counts.to_dict()}")
    labels = sorted(y.unique())
    splitter = StratifiedGroupKFold(n_splits=n_splits, shuffle=True, random_state=random_state)
    splits = list(splitter.split(X, y, groups))
    oof = pd.DataFrame({group_column: groups, date_column: selected[date_column].astype(str),
                        "y_true": y, "fold": -1, "y_pred": ""})
    fold_rows, importance_rows, ablation_rows, noise_rows = [], [], [], []
    fold_audit = []
    for fold, (tr, te) in enumerate(splits, 1):
        train_groups, test_groups = set(groups.iloc[tr]), set(groups.iloc[te])
        if train_groups & test_groups:
            raise RobustnessError(f"Pot leakage in fold {fold}")
        if set(y.iloc[tr]) != set(labels) or set(y.iloc[te]) != set(labels):
            raise RobustnessError(f"Fold {fold} does not contain every class in train and test")
        Xt, Xv, yt, yv = X.iloc[tr].copy(), X.iloc[te].copy(), y.iloc[tr], y.iloc[te]
        empty = Xt.columns[Xt.isna().all()].tolist()
        if empty:
            raise RobustnessError(f"Fold {fold} has all-missing training bands: {empty}")
        fitted = make_pipeline(model_name, random_state + fold).fit(Xt, yt)
        pred = fitted.predict(Xv)
        base = score(yv, pred, labels)
        oof.loc[te, "fold"], oof.loc[te, "y_pred"] = fold, pred
        fold_rows.append({"fold": fold, "train_pots": len(train_groups), "test_pots": len(test_groups),
                          "macro_f1": base["macro_f1"], "balanced_accuracy": base["balanced_accuracy"],
                          "accuracy": base["accuracy"]})
        fold_audit.append({"fold": fold, "train_pots": len(train_groups), "test_pots": len(test_groups),
                           "group_overlap": False})
        pi = permutation_importance(fitted, Xv, yv, scoring="f1_macro",
                                    n_repeats=permutation_repeats,
                                    random_state=random_state + fold, n_jobs=1)
        for i, band in enumerate(bands):
            importance_rows.append({"fold": fold, "band": band,
                                    "mean_f1_decrease": float(pi.importances_mean[i]),
                                    "sd_f1_decrease": float(pi.importances_std[i])})
            # Remove one band using a training-only median replacement.
            ablated = Xv.copy()
            ablated[band] = float(Xt[band].median())
            ablated_score = score(yv, fitted.predict(ablated), labels)
            ablation_rows.append({"fold": fold, "band": band,
                                  "macro_f1_drop": base["macro_f1"] - ablated_score["macro_f1"]})
        train_sd = Xt.std(axis=0, ddof=0).fillna(0.0)
        for repeat in range(noise_repeats):
            rng = np.random.default_rng(random_state + fold * 10000 + repeat)
            noisy = Xv.copy()
            for band in bands:
                values = noisy[band].to_numpy(dtype=float, copy=True)
                valid = np.isfinite(values)
                sigma = float(train_sd[band]) * noise_sd_fraction
                if sigma and valid.any():
                    values[valid] += rng.normal(0.0, sigma, size=int(valid.sum()))
                noisy[band] = values
            noisy_score = score(yv, fitted.predict(noisy), labels)
            noise_rows.append({"fold": fold, "repeat": repeat + 1, "noise_sd_fraction": noise_sd_fraction,
                               "macro_f1": noisy_score["macro_f1"],
                               "balanced_accuracy": noisy_score["balanced_accuracy"],
                               "macro_f1_drop": base["macro_f1"] - noisy_score["macro_f1"]})
    if (oof["fold"] < 1).any() or oof["y_pred"].eq("").any():
        raise RobustnessError("Out-of-fold predictions are incomplete")
    pooled = score(oof.y_true, oof.y_pred, labels)
    fold_df, pi_df = pd.DataFrame(fold_rows), pd.DataFrame(importance_rows)
    pi_summary = (pi_df.groupby("band").agg(mean_f1_decrease=("mean_f1_decrease", "mean"),
        sd_f1_decrease=("mean_f1_decrease", "std")).fillna(0).reset_index()
        .sort_values("mean_f1_decrease", ascending=False))
    ablation = (pd.DataFrame(ablation_rows).groupby("band").macro_f1_drop
                .agg(mean_macro_f1_drop="mean", sd_macro_f1_drop="std").fillna(0)
                .reset_index().sort_values("mean_macro_f1_drop", ascending=False))
    noise = pd.DataFrame(noise_rows)
    out = Path(output_dir); out.mkdir(parents=True, exist_ok=True)
    oof.to_csv(out / "oof_predictions.csv", index=False)
    fold_df.to_csv(out / "fold_metrics.csv", index=False)
    pi_summary.to_csv(out / "permutation_importance.csv", index=False)
    ablation.to_csv(out / "band_ablation.csv", index=False)
    noise.to_csv(out / "noise_sensitivity.csv", index=False)
    meaning = {"treatment_assignment": "Experimental inoculation-assignment classification only; not symptom detection or forecasting.",
               "observed_infection_status": "Same-date classification of independently assessed infection status; not forecasting.",
               "symptom_severity": "Same-date classification of symptom severity; not future-severity forecasting."}[target_semantics]
    report = {"task": "same_date_classification", "model": model_name, "target_column": target_column,
        "target_semantics": target_semantics, "target_interpretation": meaning, "selected_date": str(date_value),
        "group_column": group_column, "n_independent_pots": int(groups.nunique()),
        "class_counts": {str(k): int(v) for k, v in counts.items()}, "n_splits": n_splits,
        "folds": fold_audit, "group_overlap": False, "pooled_oof_metrics": pooled,
        "fold_macro_f1_mean": float(fold_df.macro_f1.mean()),
        "fold_macro_f1_sd": float(fold_df.macro_f1.std(ddof=1)),
        "noise_stress": {"sd_fraction_of_training_fold_sd": noise_sd_fraction,
            "repeats_per_fold": noise_repeats, "mean_macro_f1": float(noise.macro_f1.mean()),
            "mean_macro_f1_drop": float(noise.macro_f1_drop.mean())},
        "permutation_importance": {"method": "held-out-pot permutation; macro-F1 decrease",
            "repeats_per_band_per_fold": permutation_repeats,
            "top_bands": pi_summary.head(10).to_dict(orient="records")},
        "band_ablation": {"method": "replace held-out band with training-fold median",
            "top_sensitive_bands": ablation.head(10).to_dict(orient="records")},
        "limitations": ["Synthetic tests validate software only; no biological performance is implied.",
            "Importance is conditional on model, date, cohort and grouped split; correlated bands can mask each other.",
            "Band ablation and Gaussian noise are stress tests, not sensor calibration validation.",
            "Treatment assignment is not observed symptom detection or future disease forecasting.",
            "Controlled-environment data do not establish field validation."]}
    (out / "robustness_report.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    return report


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--input-csv", required=True); p.add_argument("--output-dir", required=True)
    p.add_argument("--target-column", required=True); p.add_argument("--target-semantics", required=True, choices=sorted(SEMANTICS))
    p.add_argument("--date-value", required=True); p.add_argument("--date-column", default=DATE)
    p.add_argument("--group-column", default=GROUP)
    p.add_argument("--model", default="logistic_regression", choices=["logistic_regression", "rbf_svm", "random_forest"])
    p.add_argument("--n-splits", type=int, default=5); p.add_argument("--permutation-repeats", type=int, default=10)
    p.add_argument("--noise-repeats", type=int, default=10); p.add_argument("--noise-sd-fraction", type=float, default=0.05)
    p.add_argument("--random-state", type=int, default=42); a = p.parse_args()
    r = run(a.input_csv, a.output_dir, target_column=a.target_column, target_semantics=a.target_semantics,
        date_value=a.date_value, date_column=a.date_column, group_column=a.group_column, model_name=a.model,
        n_splits=a.n_splits, permutation_repeats=a.permutation_repeats, noise_repeats=a.noise_repeats,
        noise_sd_fraction=a.noise_sd_fraction, random_state=a.random_state)
    print(json.dumps({"task": r["task"], "model": r["model"], "n_independent_pots": r["n_independent_pots"],
        "pooled_oof_macro_f1": r["pooled_oof_metrics"]["macro_f1"],
        "pooled_oof_balanced_accuracy": r["pooled_oof_metrics"]["balanced_accuracy"], "output_dir": a.output_dir}, indent=2))

if __name__ == "__main__":
    main()

"""Leakage-aware logistic-regression baseline on one acquisition date.

Input is Day 5's pot-date aggregated spectra table. Evaluation uses
StratifiedGroupKFold; imputation and scaling are fitted inside each training
fold. This is same-date classification, never future disease forecasting.
"""
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
from sklearn.impute import SimpleImputer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import (
    accuracy_score, balanced_accuracy_score, classification_report,
    confusion_matrix, f1_score, precision_score, recall_score, roc_auc_score,
)
from sklearn.model_selection import StratifiedGroupKFold
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler

BAND_PATTERN = re.compile(r"^band_(\d+)$")
DEFAULT_GROUP = "pot_id_candidate"
DEFAULT_DATE = "date_folder_yyyymmdd_candidate"
ALLOWED_TARGET_SEMANTICS = {
    "treatment_assignment", "observed_infection_status", "symptom_severity"
}


class BaselineValidationError(ValueError):
    """Raised when the input cannot support a valid baseline evaluation."""


def ordered_band_columns(columns) -> list[str]:
    matches = []
    for column in columns:
        match = BAND_PATTERN.fullmatch(str(column))
        if match:
            matches.append((int(match.group(1)), str(column)))
    result = [name for _, name in sorted(matches)]
    if len(result) < 2:
        raise BaselineValidationError("Expected at least two band_NNN columns.")
    return result


def build_pipeline(c_value: float = 1.0) -> Pipeline:
    if c_value <= 0:
        raise BaselineValidationError("C must be greater than zero.")
    return Pipeline([
        ("imputer", SimpleImputer(strategy="median")),
        ("scaler", StandardScaler()),
        ("classifier", LogisticRegression(
            C=c_value, class_weight="balanced", max_iter=5000,
            solver="lbfgs", random_state=42,
        )),
    ])


def _safe_name(value: object) -> str:
    return re.sub(r"[^A-Za-z0-9]+", "_", str(value)).strip("_") or "class"


def prepare_one_date(frame: pd.DataFrame, *, target_column: str, date_value: str,
                     date_column: str, group_column: str, target_semantics: str):
    if target_semantics not in ALLOWED_TARGET_SEMANTICS:
        raise BaselineValidationError(
            f"target_semantics must be one of {sorted(ALLOWED_TARGET_SEMANTICS)}."
        )
    required = [target_column, date_column, group_column]
    missing = [c for c in required if c not in frame.columns]
    if missing:
        raise BaselineValidationError(f"Required column(s) missing: {missing}")
    bands = ordered_band_columns(frame.columns)
    for column in required:
        if frame[column].isna().any() or frame[column].astype(str).str.strip().eq("").any():
            raise BaselineValidationError(f"Required column {column!r} contains missing/blank values.")

    if target_semantics == "treatment_assignment":
        varying = frame.groupby(group_column)[target_column].nunique(dropna=False)
        if (varying > 1).any():
            raise BaselineValidationError(
                "Treatment-assignment label changes within a pot across dates. "
                "Inspect the annotation join before modelling."
            )

    selected = frame.loc[frame[date_column].astype(str) == str(date_value)].copy()
    if selected.empty:
        available = sorted(frame[date_column].astype(str).unique().tolist())
        raise BaselineValidationError(
            f"No rows for date {date_value!r}; available dates include {available[:10]}."
        )
    if selected[group_column].duplicated().any():
        duplicate_groups = selected.loc[
            selected[group_column].duplicated(keep=False), group_column
        ].astype(str).unique().tolist()[:10]
        raise BaselineValidationError(
            "Expected exactly one pot-date row per pot; duplicate groups: "
            f"{duplicate_groups}. Resolve aggregation/annotation joins first."
        )

    X = selected[bands].apply(pd.to_numeric, errors="coerce")
    X = X.replace([np.inf, -np.inf], np.nan)
    all_missing = X.columns[X.isna().all()].tolist()
    if all_missing:
        raise BaselineValidationError(f"All values missing in spectral bands: {all_missing}")
    y = selected[target_column].astype(str)
    groups = selected[group_column].astype(str)
    counts = y.value_counts().sort_index()
    if len(counts) < 2:
        raise BaselineValidationError("Target must contain at least two classes.")
    return selected, X, y, groups, bands, counts


def _metrics(y_true, y_pred, labels):
    return {
        "accuracy": float(accuracy_score(y_true, y_pred)),
        "balanced_accuracy": float(balanced_accuracy_score(y_true, y_pred)),
        "macro_f1": float(f1_score(y_true, y_pred, average="macro", zero_division=0)),
        "macro_precision": float(precision_score(y_true, y_pred, average="macro", zero_division=0)),
        "macro_recall": float(recall_score(y_true, y_pred, average="macro", zero_division=0)),
        "confusion_matrix": confusion_matrix(y_true, y_pred, labels=labels).tolist(),
    }


def run_baseline(input_csv, output_dir, *, target_column: str, date_value: str,
                 target_semantics: str, date_column: str = DEFAULT_DATE,
                 group_column: str = DEFAULT_GROUP, n_splits: int = 5,
                 random_state: int = 42, c_value: float = 1.0):
    if n_splits < 2:
        raise BaselineValidationError("n_splits must be at least 2.")
    frame = pd.read_csv(
        input_csv, encoding="utf-8-sig", low_memory=False,
        dtype={group_column: "string", date_column: "string", target_column: "string"},
    )
    selected, X, y, groups, bands, counts = prepare_one_date(
        frame, target_column=target_column, date_value=date_value,
        date_column=date_column, group_column=group_column,
        target_semantics=target_semantics,
    )
    if int(counts.min()) < n_splits:
        raise BaselineValidationError(
            f"Each class needs at least {n_splits} independent pot groups for "
            f"{n_splits}-fold CV; counts={counts.to_dict()}."
        )
    labels = sorted(y.unique().tolist())
    splitter = StratifiedGroupKFold(
        n_splits=n_splits, shuffle=True, random_state=random_state
    )
    oof_pred = pd.Series(index=selected.index, dtype="object")
    probability_columns = [f"probability_{_safe_name(label)}" for label in labels]
    oof_proba = pd.DataFrame(index=selected.index, columns=probability_columns, dtype=float)
    fold_ids = pd.Series(index=selected.index, dtype="int64")
    fold_metrics = []

    for fold, (train_idx, test_idx) in enumerate(splitter.split(X, y, groups), start=1):
        y_train, y_test = y.iloc[train_idx], y.iloc[test_idx]
        if set(y_train.unique()) != set(labels) or set(y_test.unique()) != set(labels):
            raise BaselineValidationError(
                f"Fold {fold} lacks a target class in train or test; reduce folds or add independent pots."
            )
        model = build_pipeline(c_value)
        model.fit(X.iloc[train_idx], y_train)
        prediction = model.predict(X.iloc[test_idx])
        probabilities = model.predict_proba(X.iloc[test_idx])
        model_classes = model.named_steps["classifier"].classes_
        oof_pred.iloc[test_idx] = prediction
        fold_ids.iloc[test_idx] = fold
        for index, label in enumerate(model_classes):
            column = f"probability_{_safe_name(label)}"
            oof_proba.iloc[test_idx, oof_proba.columns.get_loc(column)] = probabilities[:, index]
        item = _metrics(y_test, prediction, labels)
        item.update({
            "fold": fold,
            "train_pots": int(groups.iloc[train_idx].nunique()),
            "test_pots": int(groups.iloc[test_idx].nunique()),
        })
        fold_metrics.append(item)

    if oof_pred.isna().any() or oof_proba.isna().any().any() or fold_ids.isna().any():
        raise BaselineValidationError("Out-of-fold predictions are incomplete.")
    oof_pred = oof_pred.astype(str)
    overall = _metrics(y, oof_pred, labels)
    if len(labels) == 2:
        positive = labels[1]
        overall["roc_auc"] = float(roc_auc_score(
            (y == positive).astype(int), oof_proba[f"probability_{_safe_name(positive)}"]
        ))
        overall["roc_auc_positive_class"] = positive

    report = classification_report(
        y, oof_pred, labels=labels, output_dict=True, zero_division=0
    )
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    predictions = selected[[group_column, date_column, target_column]].copy()
    predictions["fold"] = fold_ids.astype(int)
    predictions["predicted_label"] = oof_pred
    predictions = predictions.join(oof_proba)
    predictions.to_csv(output_dir / "oof_predictions.csv", index=False)
    split_table = selected[[group_column, date_column, target_column]].copy()
    split_table["fold"] = fold_ids.astype(int)
    split_table.to_csv(output_dir / "split_assignments.csv", index=False)
    pd.DataFrame(
        confusion_matrix(y, oof_pred, labels=labels),
        index=[f"true_{label}" for label in labels],
        columns=[f"pred_{label}" for label in labels],
    ).to_csv(output_dir / "confusion_matrix.csv")

    interpretation = {
        "treatment_assignment": (
            "Experimental inoculation assignment classification only; not observed symptom "
            "detection and not future disease forecasting."
        ),
        "observed_infection_status": (
            "Same-date infection-status classification only; not future disease forecasting."
        ),
        "symptom_severity": (
            "Same-date symptom-severity classification only; not future disease forecasting."
        ),
    }[target_semantics]
    metrics = {
        "model": "median imputation + standard scaling + logistic regression",
        "input_csv": str(input_csv), "selected_date": str(date_value),
        "target_column": target_column, "target_semantics": target_semantics,
        "target_interpretation": interpretation, "group_column": group_column,
        "independent_groups": int(groups.nunique()), "samples": int(len(selected)),
        "features": bands,
        "class_counts_by_pot": {str(k): int(v) for k, v in counts.items()},
        "validation": {
            "method": "StratifiedGroupKFold", "n_splits": n_splits,
            "shuffle": True, "random_state": random_state,
            "group_overlap": False, "one_row_per_group_at_selected_date": True,
        },
        "preprocessing": (
            "Median imputation and standard scaling are inside a Pipeline fitted "
            "on training folds only."
        ),
        "out_of_fold_metrics": overall, "classification_report": report,
        "fold_metrics": fold_metrics,
        "limitations": [
            "One selected acquisition date only.",
            "Treatment-assignment classification is not biological symptom detection.",
            "Same-date classification is not future-state forecasting.",
            "Controlled-environment data are not field validation.",
            "C is a predeclared baseline value; no hyperparameter tuning was performed.",
        ],
    }
    (output_dir / "baseline_metrics.json").write_text(
        json.dumps(metrics, indent=2), encoding="utf-8"
    )
    # Separate final fit for downstream demo; OOF metrics remain out-of-fold.
    final_model = build_pipeline(c_value).fit(X, y)
    joblib.dump({
        "pipeline": final_model, "feature_columns": bands,
        "target_column": target_column, "target_semantics": target_semantics,
        "selected_date": str(date_value), "group_column": group_column,
    }, output_dir / "baseline_logistic_regression.joblib")
    return metrics


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input-csv", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--target-column", required=True)
    parser.add_argument("--target-semantics", choices=sorted(ALLOWED_TARGET_SEMANTICS), required=True)
    parser.add_argument("--date-value", required=True, help="One fixed date, e.g. 20210311.")
    parser.add_argument("--date-column", default=DEFAULT_DATE)
    parser.add_argument("--group-column", default=DEFAULT_GROUP)
    parser.add_argument("--n-splits", type=int, default=5)
    parser.add_argument("--random-state", type=int, default=42)
    parser.add_argument("--C", type=float, default=1.0)
    args = parser.parse_args()
    result = run_baseline(
        args.input_csv, args.output_dir, target_column=args.target_column,
        target_semantics=args.target_semantics, date_value=args.date_value,
        date_column=args.date_column, group_column=args.group_column,
        n_splits=args.n_splits, random_state=args.random_state, c_value=args.C,
    )
    print(json.dumps({
        "selected_date": result["selected_date"],
        "target_semantics": result["target_semantics"],
        "independent_groups": result["independent_groups"],
        "out_of_fold_metrics": result["out_of_fold_metrics"],
        "output_dir": str(args.output_dir),
    }, indent=2))


if __name__ == "__main__":
    main()

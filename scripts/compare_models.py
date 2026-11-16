"""Compare fixed Logistic Regression, RBF-SVM and Random Forest models.

All models use the same predeclared StratifiedGroupKFold pot-level folds.
Imputation/scaling (where applicable) are inside each fold's Pipeline.
This is same-date classification, not temporal forecasting.
"""
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestClassifier
from sklearn.impute import SimpleImputer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import (
    accuracy_score, balanced_accuracy_score, classification_report,
    confusion_matrix, f1_score, precision_score, recall_score, roc_auc_score,
)
from sklearn.model_selection import StratifiedGroupKFold
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler
from sklearn.svm import SVC

DEFAULT_GROUP = "pot_id_candidate"
DEFAULT_DATE = "date_folder_yyyymmdd_candidate"
ALLOWED_TARGET_SEMANTICS = {
    "treatment_assignment", "observed_infection_status", "symptom_severity"
}
BAND_PATTERN = re.compile(r"^band_(\d+)$")


class BaselineValidationError(ValueError):
    """Raised when the input cannot support valid grouped model comparison."""


def _safe_name(value: object) -> str:
    return re.sub(r"[^A-Za-z0-9]+", "_", str(value)).strip("_") or "class"


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


def prepare_one_date(frame: pd.DataFrame, *, target_column: str, date_value: str,
                     date_column: str, group_column: str, target_semantics: str):
    if target_semantics not in ALLOWED_TARGET_SEMANTICS:
        raise BaselineValidationError(
            f"target_semantics must be one of {sorted(ALLOWED_TARGET_SEMANTICS)}."
        )
    required = [target_column, date_column, group_column]
    missing = [column for column in required if column not in frame.columns]
    if missing:
        raise BaselineValidationError(f"Required column(s) missing: {missing}")
    bands = ordered_band_columns(frame.columns)
    for column in required:
        if frame[column].isna().any() or frame[column].astype(str).str.strip().eq("").any():
            raise BaselineValidationError(
                f"Required column {column!r} contains missing/blank values."
            )
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
        raise BaselineValidationError(
            "Expected exactly one pot-date row per pot; duplicate groups found."
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


def build_models(random_state: int = 42) -> dict[str, Pipeline]:
    """Return fixed, untuned model specifications for a fair Day 7 comparison."""
    if random_state < 0:
        raise BaselineValidationError("random_state must be non-negative.")

    logistic = Pipeline([
        ("imputer", SimpleImputer(strategy="median")),
        ("scaler", StandardScaler()),
        ("classifier", LogisticRegression(
            C=1.0, class_weight="balanced", max_iter=5000,
            solver="lbfgs", random_state=random_state,
        )),
    ])
    svm = Pipeline([
        ("imputer", SimpleImputer(strategy="median")),
        ("scaler", StandardScaler()),
        ("classifier", SVC(
            C=1.0, kernel="rbf", gamma="scale", class_weight="balanced",
            probability=False, decision_function_shape="ovr",
            random_state=random_state,
        )),
    ])
    forest = Pipeline([
        ("imputer", SimpleImputer(strategy="median")),
        ("classifier", RandomForestClassifier(
            n_estimators=500, criterion="gini", max_features="sqrt",
            min_samples_leaf=1, class_weight="balanced_subsample",
            n_jobs=-1, random_state=random_state,
        )),
    ])
    return {
        "logistic_regression": logistic,
        "rbf_svm": svm,
        "random_forest": forest,
    }


def _metric_bundle(y_true, y_pred, labels) -> dict:
    report = classification_report(
        y_true, y_pred, labels=labels, output_dict=True, zero_division=0
    )
    return {
        "accuracy": float(accuracy_score(y_true, y_pred)),
        "balanced_accuracy": float(balanced_accuracy_score(y_true, y_pred)),
        "macro_f1": float(f1_score(y_true, y_pred, labels=labels, average="macro", zero_division=0)),
        "macro_precision": float(precision_score(y_true, y_pred, labels=labels, average="macro", zero_division=0)),
        "macro_recall": float(recall_score(y_true, y_pred, labels=labels, average="macro", zero_division=0)),
        "per_class": {
            str(label): {
                "precision": float(report[str(label)]["precision"]),
                "recall": float(report[str(label)]["recall"]),
                "f1": float(report[str(label)]["f1-score"]),
                "support": int(report[str(label)]["support"]),
            }
            for label in labels
        },
        "confusion_matrix": confusion_matrix(y_true, y_pred, labels=labels).tolist(),
    }


def _extract_scores(model: Pipeline, X_test: pd.DataFrame):
    classifier = model.named_steps["classifier"]
    classes = [str(value) for value in classifier.classes_]
    scores = {}
    if hasattr(classifier, "predict_proba"):
        values = model.predict_proba(X_test)
        kind = "probability"
        for index, label in enumerate(classes):
            scores[f"probability_{_safe_name(label)}"] = values[:, index]
    elif hasattr(classifier, "decision_function"):
        values = np.asarray(model.decision_function(X_test))
        kind = "decision_score"
        if values.ndim == 1:
            # Binary SVC decision_function is positive for classes_[1].
            scores[f"decision_score_positive_{_safe_name(classes[1])}"] = values
        else:
            for index, label in enumerate(classes):
                scores[f"decision_score_{_safe_name(label)}"] = values[:, index]
    else:
        kind = "none"
    return scores, kind


def _pooled_auc(y_true, score_frame, score_kind, labels):
    if len(labels) != 2 or score_kind == "none":
        return None, None
    positive = labels[1]
    column = (
        f"probability_{_safe_name(positive)}"
        if score_kind == "probability"
        else f"decision_score_positive_{_safe_name(positive)}"
    )
    if column not in score_frame:
        return None, None
    value = roc_auc_score(
        (np.asarray(y_true) == positive).astype(int), score_frame[column]
    )
    return float(value), positive


def run_comparison(
    input_csv, output_dir, *, target_column: str, target_semantics: str,
    date_value: str, date_column: str = DEFAULT_DATE,
    group_column: str = DEFAULT_GROUP, n_splits: int = 5,
    random_state: int = 42,
):
    if target_semantics not in ALLOWED_TARGET_SEMANTICS:
        raise BaselineValidationError(
            f"target_semantics must be one of {sorted(ALLOWED_TARGET_SEMANTICS)}."
        )
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
    # Materialize once: every model receives exactly the same fold membership.
    splits = list(splitter.split(X, y, groups))
    fold_ids = np.full(len(selected), -1, dtype=int)
    for fold, (train_idx, test_idx) in enumerate(splits, start=1):
        train_groups = set(groups.iloc[train_idx])
        test_groups = set(groups.iloc[test_idx])
        if train_groups & test_groups:
            raise BaselineValidationError(f"Pot leakage detected in fold {fold}.")
        if set(y.iloc[train_idx]) != set(labels) or set(y.iloc[test_idx]) != set(labels):
            raise BaselineValidationError(
                f"Fold {fold} lacks a class in train or test; reduce folds or add independent pots."
            )
        if np.any(fold_ids[test_idx] != -1):
            raise BaselineValidationError("A row appears in more than one test fold.")
        fold_ids[test_idx] = fold
    if np.any(fold_ids < 1):
        raise BaselineValidationError("Some rows did not receive an out-of-fold assignment.")

    from sklearn.base import clone
    models = build_models(random_state)
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    all_metrics = {}
    all_fold_rows = []

    base_columns = selected[[group_column, date_column, target_column]].copy().reset_index(drop=True)
    split_table = base_columns.copy()
    split_table["fold"] = fold_ids
    split_table.to_csv(output_dir / "shared_split_assignments.csv", index=False)

    comparison_rows = []
    for model_name, estimator_template in models.items():
        predictions = np.empty(len(selected), dtype=object)
        score_values: dict[str, np.ndarray] = {}
        score_kind = "none"
        fold_rows = []

        for fold, (train_idx, test_idx) in enumerate(splits, start=1):
            model = clone(estimator_template)
            model.fit(X.iloc[train_idx], y.iloc[train_idx])
            pred = model.predict(X.iloc[test_idx]).astype(str)
            predictions[test_idx] = pred

            scores, fold_score_kind = _extract_scores(model, X.iloc[test_idx])
            if score_kind == "none":
                score_kind = fold_score_kind
            elif score_kind != fold_score_kind:
                raise BaselineValidationError("Inconsistent score type across folds.")
            for column, values in scores.items():
                if column not in score_values:
                    score_values[column] = np.full(len(selected), np.nan, dtype=float)
                score_values[column][test_idx] = values

            fold_metric = _metric_bundle(y.iloc[test_idx], pred, labels)
            fold_metric.update({
                "model": model_name, "fold": fold,
                "train_pots": int(groups.iloc[train_idx].nunique()),
                "test_pots": int(groups.iloc[test_idx].nunique()),
            })
            fold_rows.append(fold_metric)
            all_fold_rows.append(fold_metric)

        if pd.isna(predictions).any():
            raise BaselineValidationError(f"{model_name} has incomplete OOF predictions.")
        oof_scores = pd.DataFrame(score_values)
        if len(oof_scores.columns) and oof_scores.isna().any().any():
            raise BaselineValidationError(f"{model_name} has incomplete OOF scores.")

        pooled = _metric_bundle(y, predictions.astype(str), labels)
        auc, auc_positive = _pooled_auc(y, oof_scores, score_kind, labels)
        if auc is not None:
            pooled["roc_auc"] = auc
            pooled["roc_auc_positive_class"] = auc_positive

        fold_f1 = np.asarray([row["macro_f1"] for row in fold_rows], dtype=float)
        summary = {
            "model": model_name,
            "out_of_fold_metrics": pooled,
            "fold_macro_f1_mean": float(fold_f1.mean()),
            "fold_macro_f1_std": float(fold_f1.std(ddof=1)) if len(fold_f1) > 1 else 0.0,
            "fold_metrics": fold_rows,
            "score_type": score_kind,
            "class_counts_by_pot": {str(k): int(v) for k, v in counts.items()},
        }
        all_metrics[model_name] = summary

        prediction_table = base_columns.copy()
        prediction_table["fold"] = fold_ids
        prediction_table["predicted_label"] = predictions.astype(str)
        for column, values in score_values.items():
            prediction_table[column] = values
        prediction_table.to_csv(output_dir / f"{model_name}_oof_predictions.csv", index=False)

        confusion = pd.DataFrame(
            confusion_matrix(y, predictions.astype(str), labels=labels),
            index=[f"true_{label}" for label in labels],
            columns=[f"pred_{label}" for label in labels],
        )
        confusion.to_csv(output_dir / f"{model_name}_confusion_matrix.csv")

        # Full-data fit is for downstream inference only; metrics above are OOF.
        final_model = clone(estimator_template).fit(X, y)
        joblib.dump({
            "pipeline": final_model, "model_name": model_name,
            "feature_columns": bands, "target_column": target_column,
            "target_semantics": target_semantics, "selected_date": str(date_value),
            "group_column": group_column,
            "fixed_hyperparameters": "Day 7 predeclared defaults; no tuning",
        }, output_dir / f"{model_name}.joblib")

        comparison_rows.append({
            "model": model_name,
            "macro_f1_oof": pooled["macro_f1"],
            "balanced_accuracy_oof": pooled["balanced_accuracy"],
            "macro_precision_oof": pooled["macro_precision"],
            "macro_recall_oof": pooled["macro_recall"],
            "fold_macro_f1_mean": summary["fold_macro_f1_mean"],
            "fold_macro_f1_std": summary["fold_macro_f1_std"],
            "roc_auc_oof": pooled.get("roc_auc"),
            "score_type": score_kind,
        })

    comparison = pd.DataFrame(comparison_rows).sort_values(
        ["macro_f1_oof", "balanced_accuracy_oof"],
        ascending=False, na_position="last",
    )
    comparison.to_csv(output_dir / "model_comparison.csv", index=False)
    pd.DataFrame(all_fold_rows).to_csv(output_dir / "fold_metrics.csv", index=False)

    target_interpretation = {
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

    report = {
        "experiment": "Day 7 fixed-model comparison",
        "input_csv": str(input_csv), "selected_date": str(date_value),
        "target_column": target_column, "target_semantics": target_semantics,
        "target_interpretation": target_interpretation,
        "group_column": group_column, "independent_pots": int(groups.nunique()),
        "rows": int(len(selected)), "feature_columns": bands,
        "class_counts_by_pot": {str(k): int(v) for k, v in counts.items()},
        "validation": {
            "method": "StratifiedGroupKFold", "n_splits": n_splits,
            "shuffle": True, "random_state": random_state,
            "shared_identical_folds_for_all_models": True,
            "group_overlap": False, "one_row_per_pot_at_selected_date": True,
        },
        "preprocessing": {
            "all_models": "Median imputation fitted inside each training fold.",
            "logistic_regression": "StandardScaler fitted inside each training fold.",
            "rbf_svm": "StandardScaler fitted inside each training fold.",
            "random_forest": "No scaling; tree split thresholds are scale-insensitive.",
        },
        "fixed_model_specifications": {
            "logistic_regression": "C=1.0, class_weight=balanced, max_iter=5000",
            "rbf_svm": "RBF kernel, C=1.0, gamma=scale, class_weight=balanced, probability=False",
            "random_forest": "500 trees, max_features=sqrt, min_samples_leaf=1, class_weight=balanced_subsample",
        },
        "models": all_metrics,
        "comparison_table": comparison.to_dict(orient="records"),
        "selection_warning": (
            "This is a fixed-specification exploratory comparison. Choosing the best model "
            "from these same OOF results creates selection optimism; Day 8 must use nested "
            "group-aware validation for tuning/model selection."
        ),
        "limitations": [
            "One selected acquisition date only.",
            "No hyperparameter tuning in Day 7.",
            "Treatment assignment is not symptom detection.",
            "Same-date classification is not future-state forecasting.",
            "Controlled-environment data are not field validation.",
            "No external test set is used.",
        ],
    }
    (output_dir / "model_comparison_metrics.json").write_text(
        json.dumps(report, indent=2), encoding="utf-8"
    )
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input-csv", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--target-column", required=True)
    parser.add_argument("--target-semantics", choices=sorted(ALLOWED_TARGET_SEMANTICS), required=True)
    parser.add_argument("--date-value", required=True)
    parser.add_argument("--date-column", default=DEFAULT_DATE)
    parser.add_argument("--group-column", default=DEFAULT_GROUP)
    parser.add_argument("--n-splits", type=int, default=5)
    parser.add_argument("--random-state", type=int, default=42)
    args = parser.parse_args()

    result = run_comparison(
        args.input_csv, args.output_dir, target_column=args.target_column,
        target_semantics=args.target_semantics, date_value=args.date_value,
        date_column=args.date_column, group_column=args.group_column,
        n_splits=args.n_splits, random_state=args.random_state,
    )
    print(json.dumps({
        "selected_date": result["selected_date"],
        "target_semantics": result["target_semantics"],
        "independent_pots": result["independent_pots"],
        "comparison_table": result["comparison_table"],
        "output_dir": str(args.output_dir),
    }, indent=2))


if __name__ == "__main__":
    main()

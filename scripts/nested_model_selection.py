"""Nested, pot-grouped model tuning and feature-selection comparison.

Inner grouped CV tunes each predeclared pipeline. Outer grouped CV evaluates it.
Imputation, scaling and ANOVA selection are inside Pipelines. This is same-date
classification, not temporal forecasting.
"""
from __future__ import annotations

import argparse
import json
import re
import warnings
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestClassifier
from sklearn.feature_selection import SelectKBest, f_classif
from sklearn.impute import SimpleImputer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import (
    accuracy_score, balanced_accuracy_score, classification_report,
    confusion_matrix, f1_score, precision_score, recall_score,
)
from sklearn.model_selection import GridSearchCV, StratifiedGroupKFold
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler
from sklearn.svm import SVC

DEFAULT_DATE = "date_folder_yyyymmdd_candidate"
DEFAULT_GROUP = "pot_id_candidate"
ALLOWED_TARGET_SEMANTICS = {
    "treatment_assignment", "observed_infection_status", "symptom_severity"
}
BAND_PATTERN = re.compile(r"^band_(\d+)$")


class NestedSelectionError(ValueError):
    """Raised when data cannot support the requested nested grouped CV."""


def prepare_one_date(frame, *, target_column, date_value, date_column, group_column, target_semantics):
    if target_semantics not in ALLOWED_TARGET_SEMANTICS:
        raise NestedSelectionError(f"target_semantics must be one of {sorted(ALLOWED_TARGET_SEMANTICS)}.")
    required = [target_column, date_column, group_column]
    missing = [column for column in required if column not in frame.columns]
    if missing:
        raise NestedSelectionError(f"Required column(s) missing: {missing}")
    matches = []
    for column in frame.columns:
        match = BAND_PATTERN.fullmatch(str(column))
        if match:
            matches.append((int(match.group(1)), str(column)))
    bands = [name for _, name in sorted(matches)]
    if len(bands) < 2:
        raise NestedSelectionError("Expected at least two band_NNN spectral columns.")
    for column in required:
        if frame[column].isna().any() or frame[column].astype(str).str.strip().eq("").any():
            raise NestedSelectionError(f"Required column {column!r} contains missing/blank values.")
    if target_semantics == "treatment_assignment":
        varying = frame.groupby(group_column)[target_column].nunique(dropna=False)
        if (varying > 1).any():
            raise NestedSelectionError("Treatment-assignment label changes within a pot across dates.")
    selected = frame.loc[frame[date_column].astype(str) == str(date_value)].copy()
    if selected.empty:
        raise NestedSelectionError(f"No rows found for selected date {date_value!r}.")
    if selected[group_column].duplicated().any():
        raise NestedSelectionError("Expected exactly one pot-date row per pot; duplicate groups found.")
    X = selected[bands].apply(pd.to_numeric, errors="coerce").replace([np.inf, -np.inf], np.nan)
    all_missing = X.columns[X.isna().all()].tolist()
    if all_missing:
        raise NestedSelectionError(f"All values missing in spectral bands: {all_missing}")
    y = selected[target_column].astype(str)
    groups = selected[group_column].astype(str)
    counts = y.value_counts().sort_index()
    if len(counts) < 2:
        raise NestedSelectionError("Target must contain at least two classes.")
    return selected, X, y, groups, bands, counts


def validate_splits(splits, y, groups, labels, stage):
    assignments = np.full(len(y), -1, dtype=int)
    records = []
    for fold, (train_idx, test_idx) in enumerate(splits, start=1):
        train_groups = set(groups.iloc[train_idx].astype(str))
        test_groups = set(groups.iloc[test_idx].astype(str))
        if train_groups & test_groups:
            raise NestedSelectionError(f"{stage} fold {fold}: group overlap detected.")
        if set(y.iloc[train_idx].astype(str)) != set(labels):
            raise NestedSelectionError(f"{stage} fold {fold}: training partition lacks a class.")
        if set(y.iloc[test_idx].astype(str)) != set(labels):
            raise NestedSelectionError(f"{stage} fold {fold}: test partition lacks a class.")
        if np.any(assignments[test_idx] != -1):
            raise NestedSelectionError(f"{stage}: row occurs in multiple test folds.")
        assignments[test_idx] = fold
        records.append({
            "fold": fold, "train_groups": sorted(train_groups),
            "test_groups": sorted(test_groups),
            "train_rows": int(len(train_idx)), "test_rows": int(len(test_idx)),
        })
    if np.any(assignments < 1):
        raise NestedSelectionError(f"{stage}: incomplete test-fold assignments.")
    return assignments, records


def feature_k_values(n_features):
    return sorted({min(k, n_features - 1) for k in (10, 25, 50) if n_features > 1})


def build_candidate(model_name, feature_selection, n_features, random_state):
    if feature_selection not in {"none", "anova_kbest"}:
        raise NestedSelectionError(f"Unknown feature-selection strategy: {feature_selection}")
    selector = "passthrough" if feature_selection == "none" else SelectKBest(score_func=f_classif)

    if model_name == "logistic_regression":
        scaler = StandardScaler()
        classifier = LogisticRegression(
            class_weight="balanced", max_iter=5000, solver="lbfgs", random_state=random_state
        )
        grid = {"classifier__C": [0.1, 1.0, 10.0]}
    elif model_name == "rbf_svm":
        scaler = StandardScaler()
        classifier = SVC(kernel="rbf", class_weight="balanced", probability=False)
        grid = {"classifier__C": [0.1, 1.0, 10.0], "classifier__gamma": ["scale", "auto"]}
    elif model_name == "random_forest":
        scaler = "passthrough"
        classifier = RandomForestClassifier(
            n_estimators=200, class_weight="balanced_subsample",
            random_state=random_state, n_jobs=1,
        )
        grid = {"classifier__max_features": ["sqrt", 0.5],
                "classifier__min_samples_leaf": [1, 2]}
    else:
        raise NestedSelectionError(f"Unknown model family: {model_name}")

    if feature_selection == "anova_kbest":
        grid["selector__k"] = feature_k_values(n_features)
        if not grid["selector__k"]:
            raise NestedSelectionError("ANOVA selection requires at least two spectral bands.")
    pipeline = Pipeline([
        ("imputer", SimpleImputer(strategy="median", keep_empty_features=True)),
        ("scaler", scaler),
        ("selector", selector),
        ("classifier", classifier),
    ])
    return pipeline, grid


def metric_bundle(y_true, y_pred, labels):
    return {
        "accuracy": float(accuracy_score(y_true, y_pred)),
        "balanced_accuracy": float(balanced_accuracy_score(y_true, y_pred)),
        "macro_f1": float(f1_score(y_true, y_pred, labels=labels, average="macro", zero_division=0)),
        "macro_precision": float(precision_score(y_true, y_pred, labels=labels, average="macro", zero_division=0)),
        "macro_recall": float(recall_score(y_true, y_pred, labels=labels, average="macro", zero_division=0)),
        "per_class": classification_report(y_true, y_pred, labels=labels, output_dict=True, zero_division=0),
        "confusion_matrix": confusion_matrix(y_true, y_pred, labels=labels).tolist(),
    }


def run_nested_selection(
    input_csv, output_dir, *, target_column, target_semantics, date_value,
    date_column=DEFAULT_DATE, group_column=DEFAULT_GROUP,
    outer_splits=5, inner_splits=4, random_state=42, n_jobs=1,
):
    if target_semantics not in ALLOWED_TARGET_SEMANTICS:
        raise NestedSelectionError(f"target_semantics must be one of {sorted(ALLOWED_TARGET_SEMANTICS)}.")
    if outer_splits < 2 or inner_splits < 2:
        raise NestedSelectionError("Both outer_splits and inner_splits must be at least 2.")
    if n_jobs == 0:
        raise NestedSelectionError("n_jobs cannot be zero.")

    frame = pd.read_csv(
        input_csv, encoding="utf-8-sig", low_memory=False,
        dtype={group_column: "string", date_column: "string", target_column: "string"},
    )
    selected, X, y, groups, bands, counts = prepare_one_date(
        frame, target_column=target_column, date_value=date_value,
        date_column=date_column, group_column=group_column,
        target_semantics=target_semantics,
    )
    selected = selected.reset_index(drop=True)
    X, y, groups = X.reset_index(drop=True), y.reset_index(drop=True).astype(str), groups.reset_index(drop=True).astype(str)
    labels = sorted(y.unique().tolist())
    if int(counts.min()) < outer_splits:
        raise NestedSelectionError(
            f"Each class needs at least {outer_splits} independent pot groups for outer CV; "
            f"class counts={counts.to_dict()}."
        )

    outer = list(StratifiedGroupKFold(
        n_splits=outer_splits, shuffle=True, random_state=random_state
    ).split(X, y, groups))
    outer_ids, outer_records = validate_splits(outer, y, groups, labels, "outer")
    model_names = ["logistic_regression", "rbf_svm", "random_forest"]
    feature_strategies = ["none", "anova_kbest"]
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    split_table = selected[[group_column, date_column, target_column]].copy()
    split_table["outer_fold"] = outer_ids
    split_table.to_csv(output_dir / "outer_split_assignments.csv", index=False)

    summaries, all_fold_rows, all_search_records = {}, [], []
    inner_split_records = {}
    for model_name in model_names:
        for feature_strategy in feature_strategies:
            strategy_name = f"{model_name}__{feature_strategy}"
            oof = np.full(len(selected), None, dtype=object)
            fold_rows, selected_params = [], []

            for outer_fold, (train_idx, test_idx) in enumerate(outer, start=1):
                X_train, y_train = X.iloc[train_idx].reset_index(drop=True), y.iloc[train_idx].reset_index(drop=True)
                groups_train = groups.iloc[train_idx].reset_index(drop=True)
                X_test, y_test = X.iloc[test_idx], y.iloc[test_idx]
                inner_counts = pd.DataFrame({"y": y_train, "group": groups_train}).drop_duplicates().groupby("y")["group"].nunique()
                if int(inner_counts.min()) < inner_splits:
                    raise NestedSelectionError(
                        f"Outer fold {outer_fold}: each class needs at least {inner_splits} "
                        f"training pots for inner CV; counts={inner_counts.to_dict()}."
                    )
                inner = list(StratifiedGroupKFold(
                    n_splits=inner_splits, shuffle=True,
                    random_state=random_state + 1000 + outer_fold,
                ).split(X_train, y_train, groups_train))
                _, inner_records = validate_splits(
                    inner, y_train, groups_train, labels, f"inner_outer_{outer_fold}"
                )
                inner_split_records[str(outer_fold)] = inner_records

                estimator, param_grid = build_candidate(
                    model_name, feature_strategy, len(bands), random_state + outer_fold
                )
                search = GridSearchCV(
                    estimator, param_grid, scoring="f1_macro", cv=inner,
                    refit=True, n_jobs=n_jobs, error_score="raise",
                    return_train_score=False,
                )
                with warnings.catch_warnings(record=True) as caught:
                    warnings.simplefilter("always")
                    search.fit(X_train, y_train)
                prediction = search.best_estimator_.predict(X_test).astype(str)
                oof[test_idx] = prediction

                fold_metric = metric_bundle(y_test, prediction, labels)
                fold_metric.update({
                    "model": model_name, "feature_selection": feature_strategy,
                    "outer_fold": outer_fold,
                    "train_pots": int(groups.iloc[train_idx].nunique()),
                    "test_pots": int(groups.iloc[test_idx].nunique()),
                    "best_inner_macro_f1": float(search.best_score_),
                })
                fold_rows.append(fold_metric)
                all_fold_rows.append(fold_metric)
                best_params = dict(search.best_params_)
                selected_k = best_params.get("selector__k")
                selected_params.append({
                    "outer_fold": outer_fold,
                    "best_inner_macro_f1": float(search.best_score_),
                    "best_params": best_params,
                    "selected_k": int(selected_k) if selected_k is not None else None,
                    "warnings": [str(item.message) for item in caught],
                })
                all_search_records.append({
                    "strategy": strategy_name, "outer_fold": outer_fold,
                    "best_inner_macro_f1": float(search.best_score_),
                    "best_params": best_params,
                    "selected_k": int(selected_k) if selected_k is not None else None,
                })

            if any(value is None for value in oof):
                raise NestedSelectionError(f"{strategy_name}: incomplete outer OOF predictions.")
            predictions = np.asarray(oof, dtype=str)
            pooled = metric_bundle(y, predictions, labels)
            fold_f1 = np.asarray([row["macro_f1"] for row in fold_rows], dtype=float)
            selected_k_values = [p["selected_k"] for p in selected_params if p["selected_k"] is not None]
            summaries[strategy_name] = {
                "model": model_name, "feature_selection": feature_strategy,
                "outer_oof_metrics": pooled,
                "outer_fold_macro_f1_mean": float(fold_f1.mean()),
                "outer_fold_macro_f1_std": float(fold_f1.std(ddof=1)) if len(fold_f1) > 1 else 0.0,
                "fold_metrics": fold_rows,
                "inner_best_scores_are_tuning_scores_not_generalization_estimates": True,
                "selected_k_by_outer_fold": selected_k_values,
                "outer_fold_best_params": selected_params,
            }
            prediction_table = selected[[group_column, date_column, target_column]].copy()
            prediction_table["outer_fold"] = outer_ids
            prediction_table["predicted_label"] = predictions
            prediction_table.to_csv(output_dir / f"outer_oof_{model_name}_{feature_strategy}.csv", index=False)
            pd.DataFrame(
                confusion_matrix(y, predictions, labels=labels),
                index=[f"true_{label}" for label in labels],
                columns=[f"pred_{label}" for label in labels],
            ).to_csv(output_dir / f"confusion_matrix_{model_name}_{feature_strategy}.csv")

    comparison_rows = []
    for name, summary in summaries.items():
        m = summary["outer_oof_metrics"]
        comparison_rows.append({
            "strategy": name, "model": summary["model"],
            "feature_selection": summary["feature_selection"],
            "outer_oof_macro_f1": m["macro_f1"],
            "outer_oof_balanced_accuracy": m["balanced_accuracy"],
            "outer_oof_macro_precision": m["macro_precision"],
            "outer_oof_macro_recall": m["macro_recall"],
            "outer_fold_macro_f1_mean": summary["outer_fold_macro_f1_mean"],
            "outer_fold_macro_f1_std": summary["outer_fold_macro_f1_std"],
            "selected_k_by_outer_fold": json.dumps(summary["selected_k_by_outer_fold"]),
        })
    comparison = pd.DataFrame(comparison_rows).sort_values("outer_oof_macro_f1", ascending=False)
    comparison.to_csv(output_dir / "feature_selection_comparison.csv", index=False)
    pd.DataFrame(all_fold_rows).to_csv(output_dir / "outer_fold_metrics.csv", index=False)
    (output_dir / "outer_fold_search_results.json").write_text(
        json.dumps(all_search_records, indent=2), encoding="utf-8"
    )

    interpretations = {
        "treatment_assignment": "Experimental inoculation assignment classification only; not observed symptom detection and not future disease forecasting.",
        "observed_infection_status": "Same-date infection-status classification only; not future disease forecasting.",
        "symptom_severity": "Same-date symptom-severity classification only; not future disease forecasting.",
    }
    report = {
        "experiment": "Day 8 nested pot-grouped model tuning and feature-selection comparison",
        "input_csv": str(input_csv), "selected_date": str(date_value),
        "target_column": target_column, "target_semantics": target_semantics,
        "target_interpretation": interpretations[target_semantics],
        "group_column": group_column, "independent_pots": int(groups.nunique()),
        "rows": int(len(selected)), "feature_count": int(len(bands)),
        "class_counts_by_pot": {str(k): int(v) for k, v in counts.items()},
        "validation": {
            "outer_method": "StratifiedGroupKFold", "outer_splits": outer_splits,
            "inner_method": "StratifiedGroupKFold", "inner_splits": inner_splits,
            "random_state": random_state, "outer_group_overlap": False,
            "inner_group_overlap": False, "outer_splits_shared_across_all_strategies": True,
            "inner_splits_shared_within_outer_fold": True,
            "outer_fold_assignments": outer_records,
            "inner_fold_assignments_by_outer_fold": inner_split_records,
        },
        "preprocessing_and_selection": {
            "imputation": "Median imputation inside each Pipeline, fitted on training partitions only.",
            "scaling": "StandardScaler inside LR/SVM pipelines; Random Forest is not scaled.",
            "feature_selection": "ANOVA SelectKBest is inside each Pipeline and fitted within inner training folds only.",
        },
        "search": {
            "scoring": "macro_f1", "refit": True, "n_jobs": n_jobs,
            "model_families": model_names, "feature_selection_strategies": feature_strategies,
            "grid_details": {
                "logistic_regression": {"C": [0.1, 1.0, 10.0]},
                "rbf_svm": {"C": [0.1, 1.0, 10.0], "gamma": ["scale", "auto"]},
                "random_forest": {"n_estimators": 200, "max_features": ["sqrt", 0.5], "min_samples_leaf": [1, 2]},
                "anova_kbest_k": feature_k_values(len(bands)),
            },
        },
        "strategies": summaries,
        "comparison_table": comparison.to_dict(orient="records"),
        "selection_warning": (
            "Each row estimates one predeclared tuned procedure. Selecting the best of six outer scores "
            "adds another selection step and can be optimistic; confirm a final choice on an untouched "
            "external test set or a separately predeclared final evaluation."
        ),
        "limitations": [
            "One preselected acquisition date only; same-date classification.",
            "Treatment assignment is not independently observed infection or symptom severity.",
            "No future-state target or time-forward forecast is evaluated.",
            "Pot-level groups are the independent validation units; no field validation is implied.",
            "Outer CV is not an independent external test.",
        ],
    }
    (output_dir / "nested_cv_metrics.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
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
    parser.add_argument("--outer-splits", type=int, default=5)
    parser.add_argument("--inner-splits", type=int, default=4)
    parser.add_argument("--random-state", type=int, default=42)
    parser.add_argument("--n-jobs", type=int, default=1)
    args = parser.parse_args()
    report = run_nested_selection(
        args.input_csv, args.output_dir,
        target_column=args.target_column, target_semantics=args.target_semantics,
        date_value=args.date_value, date_column=args.date_column,
        group_column=args.group_column, outer_splits=args.outer_splits,
        inner_splits=args.inner_splits, random_state=args.random_state, n_jobs=args.n_jobs,
    )
    print(json.dumps({
        "selected_date": report["selected_date"],
        "target_semantics": report["target_semantics"],
        "independent_pots": report["independent_pots"],
        "comparison_table": report["comparison_table"],
        "output_dir": str(args.output_dir),
    }, indent=2))


if __name__ == "__main__":
    main()

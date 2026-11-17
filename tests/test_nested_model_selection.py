import json

import numpy as np
import pandas as pd
import pytest

from scripts.nested_model_selection import (
    NestedSelectionError, build_candidate, run_nested_selection,
)


def make_table(tmp_path, n_per_class=10, n_bands=6):
    rng = np.random.default_rng(20261117)
    rows = []
    for class_index, label in enumerate(["Control", "Inoculated"]):
        for pot_index in range(n_per_class):
            pot = f"P{class_index * n_per_class + pot_index + 1:02d}"
            pot_effect = rng.normal(0, 0.12)
            for date, shift in [("20210311", 0.0), ("20210320", 0.05)]:
                row = {
                    "pot_id_candidate": pot,
                    "date_folder_yyyymmdd_candidate": date,
                    "treatment": label,
                }
                for band in range(1, n_bands + 1):
                    signal = (0.7 if class_index else 0.3) + shift + pot_effect
                    row[f"band_{band:03d}"] = signal + rng.normal(0, 0.08)
                rows.append(row)
    path = tmp_path / "pot_date_spectra.csv"
    pd.DataFrame(rows).to_csv(path, index=False)
    return path


def test_candidate_pipelines_keep_feature_selection_inside_pipeline():
    pipeline, grid = build_candidate("logistic_regression", "anova_kbest", 6, 42)
    assert pipeline.named_steps["selector"].__class__.__name__ == "SelectKBest"
    assert grid["selector__k"] == [5]
    assert "classifier__C" in grid
    rf, rf_grid = build_candidate("random_forest", "none", 6, 42)
    assert rf.named_steps["scaler"] == "passthrough"
    assert rf.named_steps["selector"] == "passthrough"
    assert rf_grid["classifier__min_samples_leaf"] == [1, 2]


def test_nested_cv_writes_group_safe_outputs_for_all_six_strategies(tmp_path):
    source = make_table(tmp_path)
    out = tmp_path / "nested"
    report = run_nested_selection(
        source, out, target_column="treatment",
        target_semantics="treatment_assignment", date_value="20210311",
        outer_splits=3, inner_splits=2, random_state=42, n_jobs=1,
    )
    assert report["independent_pots"] == 20
    assert report["validation"]["outer_group_overlap"] is False
    assert report["validation"]["inner_group_overlap"] is False
    assert report["validation"]["outer_splits_shared_across_all_strategies"] is True
    assert len(report["strategies"]) == 6
    assert (out / "outer_split_assignments.csv").exists()
    assert (out / "feature_selection_comparison.csv").exists()
    assert (out / "nested_cv_metrics.json").exists()
    split = pd.read_csv(out / "outer_split_assignments.csv")
    assert split.groupby("pot_id_candidate")["outer_fold"].nunique().max() == 1
    for model in ["logistic_regression", "rbf_svm", "random_forest"]:
        for selector in ["none", "anova_kbest"]:
            pred_path = out / f"outer_oof_{model}_{selector}.csv"
            cm_path = out / f"confusion_matrix_{model}_{selector}.csv"
            assert pred_path.exists() and cm_path.exists()
            pred = pd.read_csv(pred_path)
            assert len(pred) == 20
            assert pred["pot_id_candidate"].nunique() == 20
            assert pred.groupby("pot_id_candidate")["outer_fold"].nunique().max() == 1
    saved = json.loads((out / "nested_cv_metrics.json").read_text())
    assert "not future disease forecasting" in saved["target_interpretation"]
    assert "untouched external test" in saved["selection_warning"]


def test_insufficient_outer_groups_rejected(tmp_path):
    source = make_table(tmp_path, n_per_class=4)
    with pytest.raises(NestedSelectionError, match="at least 5 independent pot groups"):
        run_nested_selection(
            source, tmp_path / "out", target_column="treatment",
            target_semantics="treatment_assignment", date_value="20210311",
            outer_splits=5, inner_splits=3,
        )


def test_inconsistent_treatment_assignment_across_dates_rejected(tmp_path):
    source = make_table(tmp_path)
    frame = pd.read_csv(source)
    frame.loc[frame["pot_id_candidate"] == "P01", "treatment"] = ["Control", "Inoculated"]
    frame.to_csv(source, index=False)
    with pytest.raises(NestedSelectionError, match="Treatment-assignment label changes within a pot"):
        run_nested_selection(
            source, tmp_path / "out", target_column="treatment",
            target_semantics="treatment_assignment", date_value="20210311",
            outer_splits=5, inner_splits=3,
        )


def test_missing_target_column_rejected(tmp_path):
    source = make_table(tmp_path)
    with pytest.raises(NestedSelectionError, match=r"Required column\(s\) missing"):
        run_nested_selection(
            source, tmp_path / "out", target_column="unknown_label",
            target_semantics="treatment_assignment", date_value="20210311",
            outer_splits=5, inner_splits=3,
        )

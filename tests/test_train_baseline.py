import json

import pandas as pd
import pytest

from scripts.train_baseline import (
    BaselineValidationError, ordered_band_columns, prepare_one_date, run_baseline,
)


def make_table(tmp_path, n_per_class=10):
    rows = []
    for label_index, label in enumerate(["Control", "Infected"]):
        for pot_index in range(n_per_class):
            pot = f"{label_index * n_per_class + pot_index + 1:02d}"
            base = 0.3 if label == "Control" else 0.8
            for date, delta in [("20210311", 0.0), ("20210320", 0.1)]:
                rows.append({
                    "pot_id_candidate": pot,
                    "date_folder_yyyymmdd_candidate": date,
                    "treatment": label,
                    "band_010": base + delta + pot_index * 0.001,
                    "band_002": base + delta + pot_index * 0.002,
                    "band_001": base + delta + pot_index * 0.003,
                })
    path = tmp_path / "pot_date_spectra.csv"
    pd.DataFrame(rows).to_csv(path, index=False)
    return path


def test_band_columns_are_ordered_numerically():
    assert ordered_band_columns(["band_010", "band_002", "band_001", "x"]) == [
        "band_001", "band_002", "band_010"
    ]


def test_prepare_one_date_rejects_duplicate_pot_rows(tmp_path):
    frame = pd.read_csv(make_table(tmp_path), dtype={
        "pot_id_candidate": str, "date_folder_yyyymmdd_candidate": str
    })
    frame = pd.concat([frame, frame.iloc[[0]]], ignore_index=True)
    with pytest.raises(BaselineValidationError, match="exactly one pot-date row"):
        prepare_one_date(
            frame, target_column="treatment", date_value="20210311",
            date_column="date_folder_yyyymmdd_candidate",
            group_column="pot_id_candidate", target_semantics="treatment_assignment",
        )


def test_treatment_assignment_must_be_constant_within_pot(tmp_path):
    frame = pd.read_csv(make_table(tmp_path), dtype={
        "pot_id_candidate": str, "date_folder_yyyymmdd_candidate": str
    })
    mask = ((frame.pot_id_candidate == "01") &
            (frame.date_folder_yyyymmdd_candidate == "20210320"))
    frame.loc[mask, "treatment"] = "Infected"
    with pytest.raises(BaselineValidationError, match="changes within a pot"):
        prepare_one_date(
            frame, target_column="treatment", date_value="20210311",
            date_column="date_folder_yyyymmdd_candidate",
            group_column="pot_id_candidate", target_semantics="treatment_assignment",
        )


def test_baseline_runs_grouped_oof_and_writes_artifacts(tmp_path):
    input_path = make_table(tmp_path)
    out = tmp_path / "baseline"
    metrics = run_baseline(
        input_path, out, target_column="treatment",
        target_semantics="treatment_assignment", date_value="20210311",
        n_splits=5, random_state=42,
    )
    assert metrics["independent_groups"] == 20
    assert metrics["validation"]["group_overlap"] is False
    assert metrics["target_interpretation"].startswith("Experimental inoculation")
    for name in [
        "baseline_metrics.json", "oof_predictions.csv", "split_assignments.csv",
        "confusion_matrix.csv", "baseline_logistic_regression.joblib",
    ]:
        assert (out / name).exists()
    splits = pd.read_csv(out / "split_assignments.csv")
    assert splits.groupby("pot_id_candidate")["fold"].nunique().max() == 1
    assert splits.pot_id_candidate.nunique() == 20
    report = json.loads((out / "baseline_metrics.json").read_text())
    assert report["validation"]["method"] == "StratifiedGroupKFold"
    assert "not future disease forecasting" in report["target_interpretation"]


def test_five_fold_cv_requires_five_independent_pots_per_class(tmp_path):
    path = make_table(tmp_path, n_per_class=4)
    with pytest.raises(BaselineValidationError, match="at least 5 independent pot groups"):
        run_baseline(
            path, tmp_path / "out", target_column="treatment",
            target_semantics="treatment_assignment", date_value="20210311",
            n_splits=5,
        )


def test_missing_target_column_is_rejected(tmp_path):
    frame = pd.read_csv(make_table(tmp_path)).drop(columns=["treatment"])
    with pytest.raises(BaselineValidationError, match="Required column"):
        prepare_one_date(
            frame, target_column="treatment", date_value="20210311",
            date_column="date_folder_yyyymmdd_candidate",
            group_column="pot_id_candidate", target_semantics="treatment_assignment",
        )

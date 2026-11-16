import json

import numpy as np
import pandas as pd
import pytest

from scripts.compare_models import BaselineValidationError, build_models, run_comparison


def make_table(tmp_path, n_per_class=10):
    rows = []
    rng = np.random.default_rng(17)
    for label_index, label in enumerate(["Control", "Infected"]):
        for pot_index in range(n_per_class):
            pot = f"{label_index * n_per_class + pot_index + 1:02d}"
            base = 0.25 if label == "Control" else 0.75
            pot_shift = rng.normal(0, 0.025)
            for date, delta in [("20210311", 0.0), ("20210320", 0.08)]:
                rows.append({
                    "pot_id_candidate": pot,
                    "date_folder_yyyymmdd_candidate": date,
                    "treatment": label,
                    "band_001": base + delta + pot_shift + rng.normal(0, 0.02),
                    "band_002": base + delta + pot_shift * 0.5 + rng.normal(0, 0.02),
                    "band_010": base + delta + rng.normal(0, 0.02),
                })
    path = tmp_path / "pot_date_spectra.csv"
    pd.DataFrame(rows).to_csv(path, index=False)
    return path


def test_model_factories_include_fixed_three_models():
    models = build_models(42)
    assert set(models) == {"logistic_regression", "rbf_svm", "random_forest"}
    assert models["rbf_svm"].named_steps["classifier"].probability is False
    assert models["random_forest"].named_steps["classifier"].n_estimators == 500


def test_comparison_uses_shared_grouped_folds_and_writes_artifacts(tmp_path):
    input_path = make_table(tmp_path)
    out = tmp_path / "comparison"
    report = run_comparison(
        input_path, out, target_column="treatment",
        target_semantics="treatment_assignment", date_value="20210311",
        n_splits=5, random_state=42,
    )
    assert report["validation"]["shared_identical_folds_for_all_models"] is True
    assert report["validation"]["group_overlap"] is False
    assert report["independent_pots"] == 20
    assert set(report["models"]) == {"logistic_regression", "rbf_svm", "random_forest"}
    for name in report["models"]:
        assert (out / f"{name}_oof_predictions.csv").exists()
        assert (out / f"{name}_confusion_matrix.csv").exists()
        assert (out / f"{name}.joblib").exists()
        preds = pd.read_csv(out / f"{name}_oof_predictions.csv")
        assert preds.groupby("pot_id_candidate")["fold"].nunique().max() == 1
    split = pd.read_csv(out / "shared_split_assignments.csv")
    assert split.groupby("pot_id_candidate")["fold"].nunique().max() == 1
    summary = pd.read_csv(out / "model_comparison.csv")
    assert set(summary.model) == {"logistic_regression", "rbf_svm", "random_forest"}
    assert report["target_interpretation"].startswith("Experimental inoculation")
    assert "selection optimism" in report["selection_warning"]
    saved = json.loads((out / "model_comparison_metrics.json").read_text())
    assert saved["validation"]["shared_identical_folds_for_all_models"] is True


def test_insufficient_groups_rejected(tmp_path):
    path = make_table(tmp_path, n_per_class=4)
    with pytest.raises(BaselineValidationError, match="at least 5 independent pot groups"):
        run_comparison(
            path, tmp_path / "out", target_column="treatment",
            target_semantics="treatment_assignment", date_value="20210311",
            n_splits=5,
        )


def test_invalid_target_semantics_rejected(tmp_path):
    path = make_table(tmp_path)
    with pytest.raises(BaselineValidationError, match="target_semantics"):
        run_comparison(
            path, tmp_path / "out", target_column="treatment",
            target_semantics="forecast", date_value="20210311",
        )

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

import joblib
import numpy as np
import pandas as pd
import pytest
from sklearn.impute import SimpleImputer
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler

from predict import PredictionValidationError, run_inference

DATE_COLUMN = "date_folder_yyyymmdd_candidate"


def make_bundle(path, semantics="treatment_assignment"):
    X = pd.DataFrame(
        [[0.1, 0.2], [0.2, 0.1], [0.8, 0.9], [0.9, 0.8]],
        columns=["band_001", "band_002"],
    )
    y = np.array(["Control", "Control", "Inoculated", "Inoculated"])
    pipeline = Pipeline([
        ("imputer", SimpleImputer(strategy="median")),
        ("scaler", StandardScaler()),
        ("classifier", LogisticRegression(random_state=42)),
    ]).fit(X, y)
    joblib.dump({
        "pipeline": pipeline,
        "feature_columns": ["band_001", "band_002"],
        "target_column": "treatment",
        "target_semantics": semantics,
        "selected_date": "20210311",
        "group_column": "pot_id_candidate",
    }, path)
    return path


def make_input(path, dates=None, values=None):
    dates = dates or ["20210311", "20210311"]
    values = values or [[0.15, 0.15], [0.85, 0.85]]
    pd.DataFrame({
        "pot_id_candidate": ["01", "02"][:len(dates)],
        DATE_COLUMN: dates,
        "band_001": [row[0] for row in values],
        "band_002": [row[1] for row in values],
    }).to_csv(path, index=False)
    return path


def test_inference_writes_predictions_and_probabilities(tmp_path):
    model = make_bundle(tmp_path / "model.joblib")
    source = make_input(tmp_path / "input.csv")
    output = tmp_path / "predictions.csv"
    summary = run_inference(source, model, output)
    result = pd.read_csv(output, dtype={"pot_id_candidate": str})
    assert summary["rows_predicted"] == 2
    assert summary["feature_count"] == 2
    assert summary["target_semantics"] == "treatment_assignment"
    assert summary["probabilities_written"] is True
    assert result["predicted_label"].tolist() == ["Control", "Inoculated"]
    assert "probability_Control" in result.columns
    assert "not observed symptom detection" in result.loc[0, "prediction_interpretation"]
    assert result["prediction_scope"].str.contains("not future disease forecasting").all()


def test_inference_rejects_mixed_or_wrong_acquisition_dates(tmp_path):
    model = make_bundle(tmp_path / "model.joblib")
    source = make_input(tmp_path / "input.csv", dates=["20210311", "20210320"])
    with pytest.raises(PredictionValidationError, match="Model was fitted for date"):
        run_inference(source, model, tmp_path / "out.csv")


def test_inference_rejects_missing_spectral_feature(tmp_path):
    model = make_bundle(tmp_path / "model.joblib")
    source = make_input(tmp_path / "input.csv")
    pd.read_csv(source).drop(columns=["band_002"]).to_csv(source, index=False)
    with pytest.raises(PredictionValidationError, match="missing required spectral features"):
        run_inference(source, model, tmp_path / "out.csv")


def test_inference_rejects_rows_with_no_usable_spectrum(tmp_path):
    model = make_bundle(tmp_path / "model.joblib")
    source = make_input(tmp_path / "input.csv", values=[[np.nan, np.nan], [0.8, 0.9]])
    with pytest.raises(PredictionValidationError, match="no usable spectral values"):
        run_inference(source, model, tmp_path / "out.csv")


def test_inference_requires_date_column(tmp_path):
    model = make_bundle(tmp_path / "model.joblib")
    source = make_input(tmp_path / "input.csv")
    pd.read_csv(source).drop(columns=[DATE_COLUMN]).to_csv(source, index=False)
    with pytest.raises(PredictionValidationError, match="acquisition-date column"):
        run_inference(source, model, tmp_path / "out.csv")


def test_semantics_are_not_relabelled_as_forecasting(tmp_path):
    model = make_bundle(tmp_path / "model.joblib", semantics="observed_infection_status")
    source = make_input(tmp_path / "input.csv")
    output = tmp_path / "predictions.csv"
    run_inference(source, model, output)
    result = pd.read_csv(output)
    assert result["prediction_target_semantics"].eq("observed_infection_status").all()
    assert result["prediction_interpretation"].str.contains("Same-date").all()
    assert result["prediction_scope"].str.contains("not future disease forecasting").all()


def test_inference_rejects_duplicate_pot_rows(tmp_path):
    model = make_bundle(tmp_path / "model.joblib")
    source = make_input(tmp_path / "input.csv")
    frame = pd.read_csv(source)
    frame.loc[1, "pot_id_candidate"] = frame.loc[0, "pot_id_candidate"]
    frame.to_csv(source, index=False)
    with pytest.raises(PredictionValidationError, match="one row per independent pot"):
        run_inference(source, model, tmp_path / "out.csv")

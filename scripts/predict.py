"""Run guarded, same-date inference with a TerraSpectra baseline artifact.

This utility does not train a model and does not perform temporal forecasting.
The input must contain one acquisition date matching the date used to train the
serialized baseline pipeline.
"""
from __future__ import annotations
import argparse
import json
import re
from pathlib import Path
import joblib
import numpy as np
import pandas as pd

DEFAULT_DATE_COLUMN = "date_folder_yyyymmdd_candidate"
ALLOWED_TARGET_SEMANTICS = {
    "treatment_assignment", "observed_infection_status", "symptom_severity"
}
RESERVED_OUTPUT_COLUMNS = {
    "predicted_label", "prediction_target_semantics", "prediction_interpretation",
    "model_target_column", "model_selected_date", "prediction_scope",
}


class PredictionValidationError(ValueError):
    """Raised when a model bundle or inference table is unsafe to use."""


def _safe_name(value: object) -> str:
    return re.sub(r"[^A-Za-z0-9]+", "_", str(value)).strip("_") or "class"


def target_interpretation(semantics: str) -> str:
    messages = {
        "treatment_assignment": (
            "Experimental inoculation-assignment classification only; not observed "
            "symptom detection and not future disease forecasting."
        ),
        "observed_infection_status": (
            "Same-date observed-infection-status classification only; not future "
            "disease forecasting."
        ),
        "symptom_severity": (
            "Same-date symptom-severity classification only; not future disease forecasting."
        ),
    }
    if semantics not in messages:
        raise PredictionValidationError(
            f"Unsupported target semantics {semantics!r}; expected one of "
            f"{sorted(ALLOWED_TARGET_SEMANTICS)}."
        )
    return messages[semantics]


def load_model_bundle(model_path: str | Path) -> dict:
    """Load and validate a trusted joblib bundle created by train_baseline.py."""
    try:
        bundle = joblib.load(model_path)
    except Exception as exc:
        raise PredictionValidationError(
            f"Could not load model artifact {model_path!s}: {exc}"
        ) from exc
    if not isinstance(bundle, dict):
        raise PredictionValidationError("Model artifact must be a dictionary bundle.")
    required = {
        "pipeline", "feature_columns", "target_column",
        "target_semantics", "selected_date"
    }
    missing = sorted(required - set(bundle))
    if missing:
        raise PredictionValidationError(f"Model bundle is missing required keys: {missing}")
    if not callable(getattr(bundle["pipeline"], "predict", None)):
        raise PredictionValidationError("Model bundle pipeline does not expose predict().")
    columns = bundle["feature_columns"]
    if not isinstance(columns, (list, tuple)) or not columns:
        raise PredictionValidationError("feature_columns must be a non-empty list or tuple.")
    features = [str(column) for column in columns]
    if len(features) != len(set(features)):
        raise PredictionValidationError("feature_columns contains duplicate names.")
    group_column = str(bundle.get("group_column", "pot_id_candidate"))
    metadata = {str(bundle["target_column"]), group_column, DEFAULT_DATE_COLUMN}
    overlap = sorted(set(features).intersection(metadata))
    if overlap:
        raise PredictionValidationError(
            f"Model feature_columns contains target/group/date metadata: {overlap}"
        )
    if not str(bundle["selected_date"]).strip():
        raise PredictionValidationError("selected_date is missing or blank in the model bundle.")
    target_interpretation(str(bundle["target_semantics"]))
    return bundle


def run_inference(
    input_csv: str | Path,
    model_path: str | Path,
    output_csv: str | Path,
    *,
    date_column: str = DEFAULT_DATE_COLUMN,
) -> dict:
    bundle = load_model_bundle(model_path)
    group_column = str(bundle.get("group_column", "pot_id_candidate"))
    feature_columns = [str(column) for column in bundle["feature_columns"]]
    if date_column in feature_columns or group_column in feature_columns:
        raise PredictionValidationError("Date/group metadata cannot be model features.")
    dtype = {date_column: "string", group_column: "string"}
    try:
        frame = pd.read_csv(input_csv, encoding="utf-8-sig", low_memory=False, dtype=dtype)
    except Exception as exc:
        raise PredictionValidationError(f"Could not read input CSV {input_csv!s}: {exc}") from exc
    if frame.empty:
        raise PredictionValidationError("Input CSV contains no rows.")
    if group_column not in frame.columns:
        raise PredictionValidationError(
            f"Required biological grouping column {group_column!r} is missing."
        )
    if frame[group_column].isna().any() or frame[group_column].astype(str).str.strip().eq("").any():
        raise PredictionValidationError("Biological grouping column contains missing/blank values.")
    if frame[group_column].duplicated().any():
        duplicated = frame.loc[
            frame[group_column].duplicated(keep=False), group_column
        ].astype(str).unique().tolist()[:10]
        raise PredictionValidationError(
            "Expected one row per independent pot/inference unit; duplicate group IDs: "
            f"{duplicated}. Aggregate ROIs/sides before inference."
        )
    if date_column not in frame.columns:
        raise PredictionValidationError(
            f"Required acquisition-date column {date_column!r} is missing. "
            "The model is date-specific, so its training date must be checked."
        )
    selected_date = str(bundle["selected_date"])
    dates = frame[date_column]
    if dates.isna().any() or dates.astype(str).str.strip().eq("").any():
        raise PredictionValidationError("Acquisition-date column contains missing/blank values.")
    observed_dates = sorted(dates.astype(str).unique().tolist())
    if observed_dates != [selected_date]:
        raise PredictionValidationError(
            f"Model was fitted for date {selected_date!r}, but input contains "
            f"{observed_dates}. Use a matching date-specific model; do not mix dates."
        )

    missing_features = [column for column in feature_columns if column not in frame.columns]
    if missing_features:
        raise PredictionValidationError(
            f"Input is missing required spectral features: {missing_features}"
        )
    collisions = sorted(RESERVED_OUTPUT_COLUMNS.intersection(frame.columns))
    collisions.extend(
        sorted(column for column in frame.columns if str(column).startswith("probability_"))
    )
    target_column = str(bundle["target_column"])
    if target_column in frame.columns:
        collisions.append(target_column)
    collisions = sorted(set(collisions))
    if collisions:
        raise PredictionValidationError(
            f"Input already contains reserved prediction output columns: {collisions}"
        )

    X = frame.loc[:, feature_columns].apply(pd.to_numeric, errors="coerce")
    X = X.replace([np.inf, -np.inf], np.nan)
    all_missing = X.isna().all(axis=1)
    if all_missing.any():
        lines = (np.flatnonzero(all_missing.to_numpy()) + 2).tolist()[:10]
        raise PredictionValidationError(
            "At least one row has no usable spectral values; CSV line(s): "
            f"{lines}. Partial missing bands may be imputed by the fitted pipeline."
        )

    pipeline = bundle["pipeline"]
    try:
        predictions = np.asarray(pipeline.predict(X))
    except Exception as exc:
        raise PredictionValidationError(f"Model prediction failed: {exc}") from exc
    if predictions.ndim != 1 or len(predictions) != len(frame):
        raise PredictionValidationError("Model returned an invalid prediction shape.")

    semantics = str(bundle["target_semantics"])
    interpretation = target_interpretation(semantics)
    result = frame.copy()
    result["predicted_label"] = predictions.astype(str)
    result["prediction_target_semantics"] = semantics
    result["prediction_interpretation"] = interpretation
    result["model_target_column"] = str(bundle["target_column"])
    result["model_selected_date"] = selected_date
    result["prediction_scope"] = "same-date classification; not future disease forecasting"

    predict_proba = getattr(pipeline, "predict_proba", None)
    if callable(predict_proba):
        probabilities = np.asarray(predict_proba(X), dtype=float)
        classes = getattr(pipeline, "classes_", None)
        if classes is None and hasattr(pipeline, "named_steps"):
            classes = getattr(pipeline.named_steps.get("classifier"), "classes_", None)
        if classes is None or probabilities.shape != (len(frame), len(classes)):
            raise PredictionValidationError(
                "Model exposes predict_proba(), but class labels/probability shape are inconsistent."
            )
        if (
            not np.isfinite(probabilities).all()
            or (probabilities < 0).any()
            or (probabilities > 1).any()
        ):
            raise PredictionValidationError("Model returned probabilities outside [0, 1].")
        probability_columns = [f"probability_{_safe_name(label)}" for label in classes]
        if len(probability_columns) != len(set(probability_columns)):
            raise PredictionValidationError(
                "Class labels collide after probability-column name normalization."
            )
        for index, column in enumerate(probability_columns):
            result[column] = probabilities[:, index]

    output_path = Path(output_csv)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    result.to_csv(output_path, index=False)
    return {
        "rows_predicted": int(len(result)),
        "feature_count": int(len(feature_columns)),
        "independent_groups": int(frame[group_column].nunique()),
        "selected_date": selected_date,
        "target_semantics": semantics,
        "interpretation": interpretation,
        "output_csv": str(output_path),
        "probabilities_written": bool(callable(predict_proba)),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input-csv", type=Path, required=True)
    parser.add_argument("--model", type=Path, required=True,
                        help="Trusted joblib bundle created by scripts/train_baseline.py.")
    parser.add_argument("--output-csv", type=Path, required=True)
    parser.add_argument("--date-column", default=DEFAULT_DATE_COLUMN)
    args = parser.parse_args()
    summary = run_inference(
        args.input_csv, args.model, args.output_csv, date_column=args.date_column
    )
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()

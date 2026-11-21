# Day 12 — Guarded inference and demonstration pipeline

## Purpose

\`scripts/predict.py\` loads a trusted serialized pipeline created by \`scripts/train_baseline.py\`, validates a new pot-date spectral CSV, and writes same-date class predictions plus probabilities when supported. It is an inference utility, not a disease-forecasting model or a user-facing agronomic recommendation system.

## Required model artifact

The model file must be a trusted joblib bundle containing:

- \`pipeline\`: fitted scikit-learn pipeline exposing \`predict()\`;
- \`feature_columns\`: exact ordered list of spectral band columns used in training;
- \`target_column\`: original target field name;
- \`target_semantics\`: \`treatment_assignment\`, \`observed_infection_status\`, or \`symptom_severity\`;
- \`selected_date\`: the single acquisition date used for training;
- \`group_column\`: pot grouping field, defaulting to \`pot_id_candidate\`.

Only load artifacts produced by this repository or another trusted source. Joblib/pickle deserialization can execute code; do not load untrusted model files.

## Input contract

The input CSV must contain:

- the same acquisition date as the fitted model (default \`date_folder_yyyymmdd_candidate\`);
- every spectral feature named in the model bundle's \`feature_columns\`;
- one row per independent pot/inference unit (duplicate pot IDs are rejected);
- pot identifiers retained as metadata, never passed as model features.

The script selects only the exact training feature columns and rejects mixed/wrong dates, missing feature columns, missing/duplicate pot IDs, empty input, and rows with no usable spectral values. Partial missing bands are passed to the fitted imputer. Preprocessing is not refitted at inference time.

## Run

\`\`\`bash
python scripts/predict.py \\
  --input-csv reports/eda/vnir/new_pot_date_spectra.csv \\
  --model models/day6_vnir/baseline_logistic_regression.joblib \\
  --output-csv reports/generated/day12_predictions.csv
\`\`\`

If the date column uses a verified alternative name, pass \`--date-column ACTUAL_DATE_COLUMN\`.

## Output

The output CSV retains input metadata and adds:

- \`predicted_label\`;
- \`prediction_target_semantics\` and \`prediction_interpretation\`;
- \`model_target_column\` and \`model_selected_date\`;
- \`prediction_scope\`;
- \`probability_<class>\` columns when \`predict_proba()\` is available.

## Scientific boundaries

- \`treatment_assignment\` means inoculation/control assignment discrimination only. It is not observed symptom detection.
- \`observed_infection_status\` and \`symptom_severity\` are valid only if independently measured and verified in the source annotations.
- Every output is same-date classification. This script does not forecast a later disease state.
- A date-specific model rejects input from another date. Do not remove this guard to combine time points.
- Pot-level aggregation and group-aware evaluation must happen before the model artifact is created. Pixels, leaves and repeated pot observations must not be treated as independent samples.
- Controlled-environment results are not field validation.

## Current execution status

This is a tested inference scaffold for a future trusted model artifact. The repository does not contain a real-data model artifact because the annotation CSVs and validated real spectra have not yet been acquired and processed. Synthetic tests validate input guards, date checks, output structure and semantic warnings only. No real predictions, disease-detection performance or forecast metrics are claimed.

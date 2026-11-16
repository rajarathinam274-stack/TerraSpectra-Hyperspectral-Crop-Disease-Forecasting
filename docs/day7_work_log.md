# Day 7 work log — 2026-11-16

## Objective

Implement a reproducible fixed-specification comparison of Logistic Regression, RBF-SVM and Random Forest using identical pot-grouped folds.

## Repository review

- Authenticated GitHub account: rajarathinam274-stack.
- Repository: rajarathinam274-stack/TerraSpectra-Hyperspectral-Crop-Disease-Forecasting.
- Default branch: main; public; authenticated account has admin and push permissions.
- Reviewed the 15-day roadmap, README, Day 6 method/work log, baseline implementation, Day 5 EDA implementation and dataset configuration.
- Dataset acquisition and real ROI extraction remain incomplete; no real feature table is available in this execution environment.

## Implementation

Added scripts/compare_models.py and tests/test_compare_models.py.

- Compares the Day 6 Logistic Regression baseline with RBF-SVM and Random Forest.
- Materializes one StratifiedGroupKFold split list and reuses it for all models.
- Groups by pot and explicitly rejects any train/test pot overlap.
- Requires exactly one row per pot at one preselected acquisition date.
- Fits median imputation within each training fold; fits standardization inside the LR/SVM pipelines only.
- Uses fixed, untuned hyperparameters to keep Day 7 distinct from Day 8 tuning.
- Writes shared split assignments, per-model OOF predictions, per-model confusion matrices, fold metrics, pooled comparison metrics and final inference-only model artifacts.
- Uses SVM decision scores (no internal probability calibration) for binary ROC-AUC.

## Local verification

- Focused synthetic-fixture tests: 4 passed.
- Test fixture: 20 independent synthetic pots, two classes, two dates; five grouped folds.
- Python compileall: passed.
- CLI help invocation: passed.
- Real dataset training: not run.
- Full repository test suite: not run.

## Scientific interpretation

The selected date and target must be verified from actual annotations. A treatment-assignment label only evaluates discrimination of experimental inoculation assignment; it is not a symptom label. Same-date observed infection or severity classification is still not forecasting.

The model comparison is exploratory. Choosing the best model from these same OOF scores creates selection optimism; Day 8 must use nested group-aware model selection. No real metrics, winning model or forecast result is claimed.

## Blocker and next action

The actual annotation CSVs, validated image-coordinate registration and Day 4 real spectra remain unavailable in the execution environment. Obtain and audit these data in Colab/local compute before running the comparison. If no independently measured symptom labels exist, retain the explicit treatment-discrimination interpretation and do not claim disease forecasting.

# Day 7 — Fixed nonlinear model comparison

## Objective

Compare the Day 6 logistic-regression baseline with a radial-basis-function support vector classifier and a random forest on one preselected acquisition date. This is a fixed-specification comparison, not hyperparameter tuning.

## Input and target contract

Use the Day 5 pot-date spectral table with a verified annotation join. The table must contain one row per pot for the selected date, at least two numeric band_NNN columns, a verified date column, a pot grouping key and a target whose semantics are documented.

The CLI requires an explicit target semantic:

- treatment_assignment: experimental inoculation assignment, not symptom status.
- observed_infection_status: independently observed same-date infection status.
- symptom_severity: independently measured same-date severity category.

A treatment assignment label must be constant within a pot across all dates. Never relabel treatment assignment as observed infection or symptom status.

## Models and predeclared settings

| Model | Pipeline | Fixed specification |
|---|---|---|
| Logistic Regression | Median imputation → StandardScaler → LogisticRegression | C=1.0, class_weight=balanced, max_iter=5000 |
| RBF-SVM | Median imputation → StandardScaler → SVC | RBF, C=1.0, gamma=scale, class_weight=balanced, probability=False |
| Random Forest | Median imputation → RandomForestClassifier | 500 trees, max_features=sqrt, min_samples_leaf=1, class_weight=balanced_subsample |

Scaling is fitted only for Logistic Regression and SVM, inside each training-fold pipeline. Random forests do not require standardization because their split rules are based on feature thresholds. The SVM uses decision scores rather than probability calibration; binary ROC-AUC is computed from the positive-class decision score. The Random Forest and Logistic Regression use class probabilities for ROC-AUC.

The RBF-SVM implementation is based on LIBSVM and its fit cost can grow at least quadratically with sample count. This dataset's pot-level sample size is small, but runtime should be monitored if the pipeline is later expanded to pixel-level observations (which are not valid independent samples). See the official SVC documentation: https://scikit-learn.org/stable/modules/generated/sklearn.svm.SVC.html

Random Forest uses balanced_subsample, which recalculates class weights within each bootstrap sample. See the official RandomForestClassifier documentation: https://scikit-learn.org/stable/modules/generated/sklearn.ensemble.RandomForestClassifier.html

## Validation protocol

- One acquisition date is fixed before evaluation.
- Exactly one pot-date row per pot is required.
- All models receive the same materialized 5-fold StratifiedGroupKFold split assignments.
- Pot IDs are the groups; train/test pot overlap is explicitly rejected.
- Each training fold independently fits its imputer and (where required) scaler.
- Each test pot receives exactly one out-of-fold prediction per model.
- Each class must have at least as many independent pots as folds, and every fold must contain every class in train and test.
- The random seed is recorded and split assignments are written to disk.

StratifiedGroupKFold attempts to preserve class proportions while keeping groups non-overlapping. See the official documentation: https://scikit-learn.org/stable/modules/generated/sklearn.model_selection.StratifiedGroupKFold.html

## Metrics

The comparison reports pooled out-of-fold:

- Accuracy and balanced accuracy.
- Macro-F1, macro-precision and macro-recall.
- Per-class precision, recall, F1 and support.
- Confusion matrix.
- Binary ROC-AUC where a valid continuous score is available.
- Fold-wise macro-F1 mean and sample standard deviation.

Do not select a model based only on accuracy. With few independent pots, fold-level variability and per-class recall are important.

## Outputs

The output directory contains:

- shared_split_assignments.csv
- logistic_regression_oof_predictions.csv
- rbf_svm_oof_predictions.csv
- random_forest_oof_predictions.csv
- One confusion matrix per model.
- fold_metrics.csv
- model_comparison.csv
- model_comparison_metrics.json
- Three final all-data-fitted .joblib pipelines for downstream inference only.

The all-data fitted models are not used to calculate reported scores. Raw data and model binaries remain excluded from Git.

## Run

    python scripts/compare_models.py \
      --input-csv reports/eda/vnir/pot_date_spectra.csv \
      --output-dir models/day7_vnir \
      --target-column ACTUAL_VERIFIED_LABEL_COLUMN \
      --target-semantics treatment_assignment \
      --date-value VERIFIED_DATE_YYYYMMDD \
      --n-splits 5 \
      --random-state 42

Replace every placeholder with a field/value verified from the actual annotation and acquisition files.

## Interpretation and limitations

This is a fixed-hyperparameter model comparison. Selecting the best model from these same out-of-fold scores introduces selection optimism. Day 8 must use group-aware nested cross-validation for tuning and model selection, with all preprocessing and feature selection contained inside the inner training folds.

The experiment uses one observed date. It is same-date classification, not future-state prediction. Treatment assignment classification is not proof of symptom detection. The controlled growth-chamber dataset is not field validation.

## Verification status

Four focused synthetic-fixture tests passed locally. The tests validate shared pot-level folds, output generation, model factory settings and input guards. The real annotation CSVs and Day 4 spectral table have not been processed in this environment, so no real model metrics or winning model are reported.

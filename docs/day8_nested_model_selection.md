# Day 8 — Nested pot-grouped model selection

## Objective

Tune Logistic Regression, RBF-SVM and Random Forest while comparing no feature selection with ANOVA SelectKBest. Estimate each predeclared model/selection procedure using nested group-aware cross-validation on one acquisition date.

## Why nested CV

The inner loop selects hyperparameters; the outer loop evaluates the complete tuning procedure on pot groups not used by the inner search. Reusing the same folds for tuning and evaluation produces optimistic estimates. See the scikit-learn nested-CV example: https://scikit-learn.org/stable/auto_examples/model_selection/plot_nested_cross_validation_iris.html

## Experimental unit and target

- Input: Day 5 pot-date aggregated spectra after a verified annotation join.
- Exactly one row per pot at one preselected acquisition date.
- Group: pot ID, because treatment was assigned at pot level.
- Target semantics must be explicit: treatment_assignment, observed_infection_status or symptom_severity.
- Treatment assignment must be constant within a pot across dates. It is inoculation assignment, not observed symptom status.

## Nested validation

Defaults: five outer StratifiedGroupKFold folds and three inner StratifiedGroupKFold folds. The outer split list is materialized once and shared by all six predeclared strategies. Within each outer training partition, one inner split list is materialized and shared by the six searches for that outer fold. Every split is checked for pot overlap and class presence.

The six strategies are three model families crossed with two feature-selection procedures:

1. none: all spectral bands after training-fold imputation.
2. anova_kbest: univariate ANOVA F-test selection with k tuned among reduced-band candidates (up to 10, 25 or 50 bands).

| Family | Inner-tuned parameters | Fixed settings |
|---|---|---|
| Logistic Regression | C = 0.1, 1, 10 | balanced weights, lbfgs, max_iter=5000 |
| RBF-SVM | C = 0.1, 1, 10; gamma = scale/auto | RBF, balanced weights, no probability calibration |
| Random Forest | max_features = sqrt/0.5; min_samples_leaf = 1/2 | 200 trees, balanced_subsample, fixed seed |

Inner selection metric is macro-F1. GridSearchCV refits the best pipeline on the full outer training partition; each untouched outer pot group is predicted once. Imputation, standardization (LR/SVM) and ANOVA selection are inside the Pipeline. Feature selection is therefore refitted in every inner training fold and never sees inner-validation or outer-test labels.

## Outputs

- outer_split_assignments.csv
- outer_oof_{model}_{feature_selection}.csv for six strategies
- confusion_matrix_{model}_{feature_selection}.csv for six strategies
- outer_fold_metrics.csv
- feature_selection_comparison.csv
- outer_fold_search_results.json
- nested_cv_metrics.json, including fold membership, selected parameters and metrics

No all-data model is saved on Day 8. This deliverable is an evaluation record, not a production model before scientific data validation.

## Run

    python scripts/nested_model_selection.py \
      --input-csv reports/eda/vnir/pot_date_spectra.csv \
      --output-dir models/day8_vnir \
      --target-column ACTUAL_VERIFIED_LABEL_COLUMN \
      --target-semantics treatment_assignment \
      --date-value VERIFIED_DATE_YYYYMMDD \
      --outer-splits 5 --inner-splits 3 \
      --random-state 42 --n-jobs 1

Replace the target column and date only after verifying the actual annotation schema and target semantics. The table must contain the pot/date columns or explicitly supplied alternatives.

## Interpretation and limitations

Each outer result estimates one predeclared tuned procedure. Sorting six outer scores and selecting the largest adds another selection step and can be optimistic; confirm a final choice using an untouched external test set or a separately predeclared final evaluation. With few independent pots, report outer-fold variability and per-class recall, not only pooled macro-F1.

This is one-date classification. Treatment assignment is not symptom detection. Same-date infection/severity classification is not prediction of a future disease state. No forecasting claim is supported without stable repeated biological identities and future symptom/severity labels. Controlled growth-chamber results are not field validation.

## Verification status

Five focused synthetic tests passed locally. They validate nested group splits, Pipeline-contained feature selection, output generation and input guards. No actual annotation CSV or Day 4 spectral table was available during implementation; no real model score is claimed.


### Feature-selection stability record

For every outer fold, the report stores selected band column names and their frequency across outer folds. This is descriptive stability information, not a significance test; feature selection is still learned exclusively inside inner training folds.

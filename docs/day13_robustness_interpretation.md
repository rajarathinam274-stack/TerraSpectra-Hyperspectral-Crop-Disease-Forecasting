# Day 13 — Robustness and interpretation

## Objective

Evaluate one predeclared same-date classifier with pot-grouped out-of-fold predictions, then inspect held-out errors, wavelength-band contribution and sensitivity to controlled perturbations. The implementation fails closed when the sample table cannot support independent pot-level validation.

## Scientific scope

The unit of evaluation is one pot at one selected acquisition date. The input must contain exactly one aggregated row per pot/date. All leaves, sides, ROIs and pixels from a pot must be aggregated before this analysis; they must not be treated as independent replicates.

The script evaluates one model specified before examining the output: logistic_regression, rbf_svm or random_forest. It uses StratifiedGroupKFold with pot ID as the group. Imputation and scaling are inside a scikit-learn Pipeline and are fitted only on each training fold. Each pot receives one held-out prediction.

Target semantics remain explicit:

- treatment_assignment: discrimination of experimental inoculation assignment only.
- observed_infection_status: same-date classification of an independently assessed infection-status label.
- symptom_severity: same-date classification of an independently assessed severity category.

None of these is future-state forecasting. Treatment assignment is fixed at inoculation and must never be presented as a symptom label.

## Interpretation and stress tests

1. Out-of-fold error analysis: oof_predictions.csv records the held-out pot, true label, predicted label and fold. fold_metrics.csv records per-fold macro-F1, balanced accuracy and accuracy. robustness_report.json contains pooled OOF metrics, class-wise precision/recall/F1 and the confusion matrix.
2. Permutation importance: each spectral band is independently permuted among held-out pots. Importance is the decrease in held-out macro-F1 relative to unpermuted predictions. Correlated bands can share or mask importance; a low value is not proof that a wavelength is biologically irrelevant.
3. Band ablation: one held-out band at a time is replaced with that fold's training median. This is a controlled missing-information stress test, not a physical simulation of sensor failure.
4. Gaussian-noise sensitivity: independent noise is added to finite held-out values, with per-band standard deviation equal to noise_sd_fraction times the training-fold standard deviation. The default fraction is 0.05. This is a relative stress-test setting, not an empirically measured instrument-noise level.

All importance and stress-test results are conditional on the chosen model, acquisition date, sample cohort and split seed. They are not causal wavelength effects.

## Run

First create a verified pot-date spectral table using the Day 2–5 workflow. Confirm the actual label column and date-to-DPI mapping from the downloaded annotation files; do not copy placeholders or infer labels from folder names.

~~~bash
python scripts/robustness_interpretation.py \
  --input-csv reports/eda/vnir/pot_date_spectra.csv \
  --output-dir reports/day13/vnir \
  --target-column VERIFIED_LABEL_COLUMN \
  --target-semantics treatment_assignment \
  --date-value VERIFIED_DATE_YYYYMMDD \
  --group-column pot_id_candidate \
  --date-column date_folder_yyyymmdd_candidate \
  --model logistic_regression \
  --n-splits 5 \
  --permutation-repeats 10 \
  --noise-repeats 10 \
  --noise-sd-fraction 0.05 \
  --random-state 42
~~~

VERIFIED_LABEL_COLUMN and VERIFIED_DATE_YYYYMMDD are placeholders. Use treatment_assignment only for a verified inoculation/control field. Use observed symptom semantics only if the label is independently assessed and documented.

## Outputs

- oof_predictions.csv — one held-out prediction per pot.
- fold_metrics.csv — fold-level evaluation.
- permutation_importance.csv — per-band mean and standard deviation of macro-F1 decrease.
- band_ablation.csv — per-band ablation sensitivity.
- noise_sensitivity.csv — repeat-level perturbation metrics.
- robustness_report.json — pooled OOF metrics, split audit, interpretation and limitations.

## Verification status and limitations

The implementation is covered by synthetic fixtures only. Synthetic tests validate grouped-fold bookkeeping, outputs and input guards; they do not validate biological performance. At this checkpoint, the repository does not contain the real annotation CSVs or verified real pot-date spectra, so no real-data importance ranking, error analysis or robustness score is reported.

The public wheat experiment was conducted under controlled conditions. Any eventual result must be described as controlled-environment performance, not field validation. Genuine future disease forecasting remains a separate no-go until independently assessed future symptom/severity labels with timestamps and stable pot identity are available.

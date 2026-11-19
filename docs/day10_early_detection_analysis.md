# Day 10 — Date-wise early-detection analysis

## Research interpretation

The experiment paper reports visual inspection throughout the wheat–*Zymoseptoria tritici* experiment, progressive necrosis beginning at 7 DPI, and pycnidia at later stages. It also notes that natural senescence can resemble disease symptoms and that a disease-confidence level was recorded. Figure 4 illustrates one infected leaf at 12–14 DPI. These are study-level observations, not a complete per-pot/date symptom-label table.

The published data description identifies general, VNIR and SWIR annotation CSVs describing samples and leaf counts per image/day. Actual per-pot/date symptom-status columns have not been verified from the downloaded CSVs.

## Implementation

`scripts/analyze_early_detection.py` fits one separate Logistic Regression classifier per acquisition date. It uses a single `StratifiedGroupKFold` assignment at pot level, reused across all dates. All sides and dates belonging to one pot stay in the same fold. Median imputation and standardization are fitted inside each training fold.

Outputs include date-level and fold-level metrics, out-of-fold predictions, pot-fold assignments, a macro-F1 trend plot and a JSON audit report. The script reports coverage and refuses duplicate pot-date rows, treatment-label drift, invalid DPI mappings, missing classes and incomplete fold predictions. It calculates a class-stratified pot-bootstrap 95% interval for macro-F1.

## Scientific boundary

The current target is inoculation treatment assignment. Results therefore describe **same-date spectral discrimination of inoculated versus control pots**, not symptom detection and not forecasting. Treatment assignment is known at inoculation. The script deliberately marks symptom status as `not_assessed` and never declares an earliest pre-symptomatic date.

A genuine pre-symptomatic claim requires independently verified symptom-status annotations with complete cohort coverage. A genuine forecast requires a future symptom/severity outcome, stable biological identity across time, and chronological evaluation.

## Run

Verify the actual date-to-DPI mapping in the annotation metadata before running:

```bash
python scripts/analyze_early_detection.py \
  --input-csv reports/eda/vnir/pot_date_spectra.csv \
  --output-dir models/day10_vnir \
  --target-column VERIFIED_TREATMENT_COLUMN \
  --dpi-column VERIFIED_DPI_COLUMN \
  --n-splits 5 --random-state 42 --bootstrap-reps 1000
```

The uppercase column names are placeholders. Do not infer DPI from folder names alone or use the provisional mapping from earlier notes without confirming it against the experiment timetable.

## Outputs

- `date_metrics.csv`
- `date_fold_metrics.csv`
- `oof_predictions_by_date.csv`
- `shared_pot_fold_assignments.csv`
- `date_performance.png`
- `early_detection_report.json`

## Sources

- Latchoumane et al. (2025), *Data in Brief* 59, 111404, https://doi.org/10.1016/j.dib.2025.111404
- Dataset record: https://doi.org/10.57745/WVP0FJ

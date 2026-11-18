# Day 9 — Matched VNIR vs SWIR vs spectral fusion

## Objective

Compare VNIR-only, SWIR-only and non-overlapping fused features using the same pot-date samples, labels, fixed Logistic Regression classifier and pot-grouped folds. The fixed classifier isolates the sensor-feature comparison; Day 8 nested model selection remains separate.

## Dataset facts

The wheat Septoria dataset (DOI: https://doi.org/10.57745/WVP0FJ) describes HySpex VNIR-1800 (216 bands, nominally 411–993 nm) and HySpex SWIR-384 (256 bands, nominally 964–2494 nm). It includes 18 acquisition dates, 1,175 images per modality and 3,326 leaves. The reported wavelength ranges overlap from approximately 964–993 nm. These are paper specifications, not substitutes for validating actual Day 4 wavelength audits. Article: https://pmc.ncbi.nlm.nih.gov/articles/PMC11919375/.

## Matching and experimental unit

Inputs are separate Day 5 `pot_date_spectra.csv` files after verified annotation joins. The default matching keys are `pot_id_candidate` and `date_folder_yyyymmdd_candidate`. The selected-date key sets must be exactly identical; unmatched samples are not silently intersected. Target labels and optional genotype labels must agree. Treatment assignment must remain constant within pot across dates. Each input must contain one row per pot/date.

The comparison is at the **pot-date aggregate level**. It does not prove that both cameras measured the same individual leaf. Pot is the validation group because treatment was assigned at pot level.

## Wavelength handling and fusion

Both Day 4 audit JSON files are required. Every image must have a finite, strictly increasing nm axis with the expected band count; axes within each modality must agree within 0.1 nm. Fusion keeps all VNIR bands and only SWIR bands strictly above the maximum VNIR wavelength plus 0.5 nm (configurable). No interpolation is performed and the overlap is not counted twice. This assigns the overlap to VNIR; it is a transparent baseline, not proof that VNIR is better there.

## Validation

Five-fold `StratifiedGroupKFold` by pot is materialized once and reused across all three feature sets. Each uses the same fixed Logistic Regression (`C=1`, balanced weights). Median imputation and standardization are fitted inside each training fold. Fusion has separate fold-fitted imputation/scaling per sensor block and weights each block by `1/sqrt(feature_count)` to avoid giving the larger feature block automatically greater total norm. No all-data model is saved.

Metrics include accuracy, balanced accuracy, macro-F1, macro precision/recall, class-wise precision/recall/F1, confusion matrices and binary ROC-AUC (or macro one-vs-rest ROC-AUC for multiclass). Fold-level metrics are retained.

## Run

Create the Day 5 tables separately after confirming actual annotation columns and join keys:

```bash
python scripts/explore_spectra.py --spectra-csv data/processed/vnir_leaf_spectra.csv --audit-json data/processed/vnir_roi_audit.json --labels-csv data/metadata/VNIR_data.csv --spectrum-keys VERIFIED_SPECTRUM_KEYS --label-keys VERIFIED_ANNOTATION_KEYS --class-column VERIFIED_TARGET_COLUMN --genotype-column VERIFIED_GENOTYPE_COLUMN --output-dir reports/eda/vnir
python scripts/explore_spectra.py --spectra-csv data/processed/swir_leaf_spectra.csv --audit-json data/processed/swir_roi_audit.json --labels-csv data/metadata/SWIR_data.csv --spectrum-keys VERIFIED_SPECTRUM_KEYS --label-keys VERIFIED_ANNOTATION_KEYS --class-column VERIFIED_TARGET_COLUMN --genotype-column VERIFIED_GENOTYPE_COLUMN --output-dir reports/eda/swir
```

Then run:

```bash
python scripts/compare_sensors.py \
  --vnir-csv reports/eda/vnir/pot_date_spectra.csv \
  --swir-csv reports/eda/swir/pot_date_spectra.csv \
  --vnir-audit data/processed/vnir_roi_audit.json \
  --swir-audit data/processed/swir_roi_audit.json \
  --output-dir models/day9_sensor_comparison \
  --target-column VERIFIED_TARGET_COLUMN \
  --target-semantics treatment_assignment \
  --date-value VERIFIED_DATE_YYYYMMDD \
  --genotype-column VERIFIED_GENOTYPE_COLUMN \
  --n-splits 5 --random-state 42
```

Uppercase names are placeholders. Replace only after inspecting actual CSV schemas and verifying the target. Treatment assignment means experimental group discrimination, not symptom detection. Use `validated_reflectance` only after completing and documenting the Day 3 Spectralon procedure; the default is dark-current-corrected intensity.

## Outputs

`matched_pot_date_samples.csv`, `shared_split_assignments.csv`, `sensor_comparison_metrics.csv`, `sensor_comparison_fold_metrics.csv`, three `oof_predictions_*.csv` files, three confusion matrices and `sensor_comparison_report.json`.

## Interpretation and limitations

This is same-date classification, not forecasting. Forecasting requires stable repeated biological identities, future symptom/severity labels and chronological evaluation with biological groups held out. Selecting the best of three OOF scores adds selection optimism; confirm any selected sensor configuration on an untouched, separately predeclared evaluation. The source study is controlled growth-chamber research, not field validation. Spectra remain intensity, not reflectance, until calibration is verified.

## Verification status

Eight focused synthetic tests passed locally, including exact sample matching, label consistency, duplicate rows, treatment consistency, wavelength validation, overlap exclusion, shared group folds and end-to-end artifacts. Python compilation and CLI help passed. The tests use synthetic data only; no real sensor comparison or model score is claimed.

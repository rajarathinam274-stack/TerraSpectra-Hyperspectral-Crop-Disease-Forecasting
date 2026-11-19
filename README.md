# TerraSpectra: Hyperspectral Crop Disease Forecasting

Research project investigating hyperspectral signatures associated with Septoria infection in wheat, with a focus on early detection and temporal progression.

## Research scope

Primary source: the public wheat Septoria hyperspectral imaging dataset hosted by Recherche Data Gouv (DOI 10.57745/WVP0FJ). See docs/dataset_provenance.md, docs/day2_annotation_semantics.md, docs/day3_hsi_ingestion_calibration.md, docs/day4_roi_extraction.md and docs/day5_exploratory_spectral_analysis.md before interpreting fields or spectral data.

**Scientific distinction:** classification or early detection identifies infection status at an observed time point. Forecasting predicts a future disease state. This project will only claim forecasting if stable repeated biological identities and valid future-state labels are demonstrated.

## Dataset metadata workflow

    pip install -r requirements.txt
    python scripts/download_metadata.py
    python scripts/audit_annotations.py
    python scripts/build_sample_map.py
    python scripts/inspect_metadata.py
    pytest -q

The downloader retrieves only the three small annotation CSVs and records file inventory, checksums and SHA-256 hashes. Large VNIR/SWIR image ZIP archives are intentionally not downloaded automatically.

## HSI ingestion and calibration

    python scripts/inspect_hsi.py /path/to/image.hdr --image /path/to/image.hyspex --modality VNIR --output reports/image_header.json

Use --modality SWIR for SWIR files. See docs/day3_hsi_ingestion_calibration.md for dark-current and Spectralon rules. Published .hyspex files are described as dark-current corrected; do not subtract dark current twice. Do not claim reflectance until the Spectralon reference workflow is validated.

## Leaf ROI extraction

    python scripts/extract_leaf_spectra.py \
      --root /path/to/extracted/VNIR \
      --modality VNIR \
      --coordinate-base 0 \
      --coordinate-frame source_image \
      --output data/processed/vnir_leaf_spectra.csv \
      --audit data/processed/vnir_roi_audit.json \
      --max-images 1

The coordinate base and frame must be verified from the actual archive. For reframed coordinates, provide verified row/column offsets. See docs/day4_roi_extraction.md.

## Exploratory spectral analysis (Day 5)

After real ROI spectra are extracted, run unlabelled QC and date profiles:

    python scripts/explore_spectra.py \
      --spectra-csv data/processed/vnir_leaf_spectra.csv \
      --audit-json data/processed/vnir_roi_audit.json \
      --output-dir reports/eda/vnir

For class/genotype summaries, join only verified annotations using explicit keys and actual inspected column names. Example syntax is documented in docs/day5_exploratory_spectral_analysis.md. The EDA aggregates ROIs to pot-date units before summaries/PCA, flags outliers without deleting them, and refuses inconsistent wavelength axes.

PCA is descriptive only. For predictive models, imputation, scaling and dimensionality reduction must be fitted within training folds. Treatment assignment is not a symptom/severity outcome and is not a forecasting target.

## Google Colab

Open the [Day 1 validation notebook](https://colab.research.google.com/github/rajarathinam274-stack/TerraSpectra-Hyperspectral-Crop-Disease-Forecasting/blob/main/notebooks/01_dataset_validation.ipynb). If using local compute, connect the notebook to a local Jupyter runtime.

## Repository structure

- config/: dataset and experiment configuration
- docs/: dataset provenance, annotation semantics, roadmap and work logs
- scripts/: metadata acquisition, sample mapping, HSI, ROI, EDA and model utilities
- notebooks/: Colab notebooks
- data/metadata/: downloaded metadata and audit outputs (not committed)
- data/raw/, data/processed/: source and derived data (not committed)

## Methodology safeguards

1. Preserve source data and record provenance.
2. Split by pot, the treatment-assignment unit, unless stronger validated identifiers justify another design.
3. Keep both sides and every date from a pot in the same validation partition.
4. Do not randomly split pixels, spectra or related images from the same biological unit.
5. Use chronological evaluation for future-state prediction, with biological groups held out.
6. Fit imputation, scaling and feature selection on training data only.
7. Report macro-F1, class-wise precision/recall and confusion matrices; accuracy alone is insufficient.
8. Controlled growth-chamber results must not be presented as field-validated performance.

## Current status

Days 1–4 provide dataset, HSI and ROI-processing scaffolds; their real-data exit conditions remain open. Days 5–8 add pot-date EDA, grouped baseline/nonlinear classifiers and nested model selection. Day 9 adds a matched-sample VNIR/SWIR/fusion comparison with wavelength-axis validation, shared pot-grouped folds and training-fold-only preprocessing.

The actual annotation CSVs, ENVI cubes, coordinate registration, Spectralon reference and real Day 5 pot-date tables remain unverified in the execution environment. Day 9 has eight passing focused synthetic tests, but no real sensor comparison or model metric is claimed.

## Logistic-regression baseline (Day 6)

After Day 5 has produced a pot-date table with verified annotation labels, run one fixed acquisition date:

    python scripts/train_baseline.py \
      --input-csv reports/eda/vnir/pot_date_spectra.csv \
      --output-dir models/day6_vnir \
      --target-column ACTUAL_VERIFIED_LABEL_COLUMN \
      --target-semantics treatment_assignment \
      --date-value VERIFIED_DATE_YYYYMMDD \
      --n-splits 5 --random-state 42

Inspect docs/day6_logistic_regression_baseline.md before choosing target semantics. The baseline uses pot-grouped 5-fold validation and train-fold-only imputation/scaling. Treatment-assignment classification is not symptom detection or forecasting.

## Fixed model comparison (Day 7)

Run the fixed LR/SVM/RF comparison on the same verified pot-date table:

    python scripts/compare_models.py \
      --input-csv reports/eda/vnir/pot_date_spectra.csv \
      --output-dir models/day7_vnir \
      --target-column ACTUAL_VERIFIED_LABEL_COLUMN \
      --target-semantics treatment_assignment \
      --date-value VERIFIED_DATE_YYYYMMDD \
      --n-splits 5 --random-state 42

See docs/day7_model_comparison.md for model settings, shared folds, outputs and selection limitations. Day 7 settings are not tuned. Day 8 must use nested group-aware validation. No real model metrics are claimed until verified annotations and real spectral features are available.


## Nested model selection (Day 8)

Run nested pot-grouped tuning only after the Day 5 pot-date table has verified annotations and real ROI spectra:

    python scripts/nested_model_selection.py \
      --input-csv reports/eda/vnir/pot_date_spectra.csv \
      --output-dir models/day8_vnir \
      --target-column ACTUAL_VERIFIED_LABEL_COLUMN \
      --target-semantics treatment_assignment \
      --date-value VERIFIED_DATE_YYYYMMDD \
      --outer-splits 5 --inner-splits 3 --random-state 42 --n-jobs 1

See docs/day8_nested_model_selection.md. Inner folds tune parameters; outer folds evaluate each predeclared model/feature-selection procedure. Imputation, scaling and ANOVA selection are fitted inside training folds. Treatment-assignment classification is not symptom detection or future forecasting. No real metrics are claimed until verified annotations and spectra are available.


## Sensor comparison (Day 9)

After producing separately annotated Day 5 VNIR and SWIR pot-date tables and verifying their Day 4 wavelength audits, run `scripts/compare_sensors.py`. It requires exact pot/date matching, consistent labels and axes, then compares VNIR, SWIR and non-overlapping fusion using identical pot-grouped folds. See `docs/day9_sensor_comparison.md` for the full command, overlap handling and interpretation. No real-data sensor metric is claimed until the annotation joins, ROI extraction and wavelength audits are validated.


## Date-wise early-detection analysis (Day 10)

After producing a verified VNIR pot-date spectral table and confirming the acquisition-date-to-DPI mapping in the actual metadata, run:

```bash
python scripts/analyze_early_detection.py \
  --input-csv reports/eda/vnir/pot_date_spectra.csv \
  --output-dir models/day10_vnir \
  --target-column VERIFIED_TREATMENT_COLUMN \
  --dpi-column VERIFIED_DPI_COLUMN \
  --n-splits 5 --random-state 42 --bootstrap-reps 1000
```

The target is the experimental inoculation assignment. The script fits one separate same-date model per date and reuses pot-level folds across dates. It reports treatment-discrimination metrics, not symptom detection or future forecasting. Symptom status is not inferred from treatment labels. See `docs/day10_early_detection_analysis.md` for the scientific boundary and outputs. The focused GitHub Actions test is defined in `.github/workflows/day10-tests.yml`.

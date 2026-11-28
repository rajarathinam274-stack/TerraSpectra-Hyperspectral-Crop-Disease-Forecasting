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

The downloader retrieves only the three small annotation CSVs and records file inventory, checksum verification methods and SHA-256 hashes. The version-1 metadata files were downloaded and verified against both Dataverse and pinned publisher MD5 checksums. Large VNIR/SWIR image ZIP archives are intentionally not downloaded automatically. See `docs/day17_metadata_acquisition.md` for the verified schema findings and remaining scientific gates.

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

The three version-1 annotation CSVs have been acquired and checksum-verified. Their dataset-specific semicolon/CP1252 parsing and count-level audit are being corrected in PR #5 after the first main-branch audit exposed the source layout. ENVI cubes, coordinate registration, Spectralon reference and real Day 5 pot-date spectra remain unverified. Day 9 has eight passing focused synthetic tests, but no real sensor comparison or model metric is claimed.

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


## Dataset metadata integrity check

Download the three small annotation files from the [official Data INRAE record](https://doi.org/10.57745/WVP0FJ) into `data/metadata/`, then verify the published MD5 checksums before parsing:

```bash
md5sum data/metadata/Data_description.csv \
       data/metadata/VNIR_data.csv \
       data/metadata/SWIR_data.csv
```

Expected values:
- `Data_description.csv`: `2efd148e433016da14a3209e6db575df`
- `VNIR_data.csv`: `181f1f7a63b0434210d57841e3d7d7f8`
- `SWIR_data.csv`: `12dc1a89b7f0d648948750247ef488a3`

These are publisher-listed checksums; downloading and matching them remains a local/Colab action. Do not infer the date-to-DPI map or symptom labels from the folder names alone.


## Day 11 — forecasting feasibility

Day 11 records a **no-go** for genuine future disease-state forecasting with the currently documented annotations. Pot-level repeated observations are structurally possible, but a complete independently assessed future symptom-status table is not documented. Treatment assignment is not a future disease outcome. See \`docs/day11_forecasting_feasibility.md\` and run \`scripts/audit_forecasting_feasibility.py\` on any candidate outcome manifest before modeling.

## Day 12 — inference demo scaffold

A guarded CLI inference utility is available at scripts/predict.py. It loads a trusted model bundle produced by scripts/train_baseline.py, requires the exact training acquisition date and spectral feature columns, checks one row per pot, and writes predictions/probabilities with explicit target semantics. See docs/day12_demo_pipeline.md for the input contract and command. The scaffold has synthetic tests only: no real-data model artifact or real predictions are available yet. Treatment-assignment classification is not symptom detection or forecasting.


## Day 15 — reproducibility and handover

The final handover and evidence-qualified status are documented in [`docs/day15_handover.md`](docs/day15_handover.md). The project runtime is declared as Python 3.11 in `.python-version`. The Day 15 GitHub Actions workflow runs the complete synthetic/unit test suite, Python compilation and CLI smoke checks, and uploads a resolved environment report. `requirements.txt` is not an exact lockfile; see the handover guide for environment reproduction and the outstanding real-data validation gates.


## Day 16 — Streamlit demo

A guarded Streamlit interface is available in `demo/app.py`. It accepts a trusted fitted joblib bundle and a date-matched pot-level spectra CSV, displays same-date predictions and supports CSV export. Install `demo/requirements.txt` and launch `streamlit run demo/app.py`. See [`docs/day16_streamlit_demo.md`](docs/day16_streamlit_demo.md) for the input contract and security/scientific limitations. The app smoke test is separate from the core test suite; no real-data model artifact or biological results are available yet.

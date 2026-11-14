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
- scripts/: metadata acquisition, sample mapping, HSI, ROI and EDA utilities
- notebooks/: Colab notebooks
- data/metadata/: downloaded metadata and audit outputs (not committed)
- data/raw/, data/processed/: source and derived data (not committed)

## Methodology safeguards

1. Preserve source data and record provenance.
2. Split by pot, the treatment-assignment unit, unless stronger validated identifiers justify another design.
3. Keep both sides and every date from a pot in the same validation partition.
4. Do not randomly split pixels, spectra or related images from the same biological unit.
5. Use chronological evaluation for future-state prediction, with biological groups held out.
6. Fit preprocessing and feature selection on training data only.
7. Report macro-F1, class-wise precision/recall and confusion matrices; accuracy alone is insufficient.
8. Controlled growth-chamber results must not be presented as field-validated performance.

## Current status

Days 1–4 have committed research, acquisition, HSI and ROI-processing scaffolds with synthetic validation. Day 5 adds pot-date aggregated spectral EDA, annotation-join checks, wavelength-axis consistency checks, outlier reporting and descriptive PCA. The actual annotation CSVs, ENVI cubes, coordinate convention, crop offsets and Spectralon reference remain unverified in the execution environment. No real spectral trend, model metric or forecasting result is claimed.

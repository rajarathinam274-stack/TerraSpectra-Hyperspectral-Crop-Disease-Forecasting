# TerraSpectra: Hyperspectral Crop Disease Forecasting

Research project investigating hyperspectral signatures associated with Septoria infection in wheat, with a focus on early detection and temporal progression.

## Research scope

Primary source: the public wheat Septoria hyperspectral imaging dataset hosted by Recherche Data Gouv (DOI 10.57745/WVP0FJ). See docs/dataset_provenance.md, docs/day2_annotation_semantics.md and docs/day3_hsi_ingestion_calibration.md before interpreting fields or spectral data.

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

Inspect an extracted ENVI header and its matching HySpex binary:

    python scripts/inspect_hsi.py /path/to/image.hdr --image /path/to/image.hyspex --modality VNIR --output reports/image_header.json

Use --modality SWIR for SWIR files. The script compares observed header metadata with paper-reported sensor profiles without forcing a reshape. See docs/day3_hsi_ingestion_calibration.md for the dark-current and Spectralon reflectance rules.

The published .hyspex files are described as dark-current corrected. Do not subtract dark current a second time. Do not claim reflectance until the Spectralon reference panel/acquisition and any certified reflectance curve have been validated.

## Google Colab

Open the [Day 1 validation notebook](https://colab.research.google.com/github/rajarathinam274-stack/TerraSpectra-Hyperspectral-Crop-Disease-Forecasting/blob/main/notebooks/01_dataset_validation.ipynb). If using local compute, connect the notebook to a local Jupyter runtime.

## Repository structure

- config/: dataset and experiment configuration
- docs/: dataset provenance, annotation semantics, roadmap and work logs
- scripts/: reproducible metadata acquisition, sample mapping and HSI utilities
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

Day 1 provenance and metadata workflow are committed. Day 2 has a source-supported pot-level hierarchy and candidate-map builder. Day 3 adds ENVI header inspection and calibration functions with synthetic tests. Actual annotation CSVs and .hyspex archives have not yet been downloaded in the execution environment, so exact annotation columns, persistent plant/leaf IDs, real header values and reflectance calibration remain unverified. No model performance or forecasting result is claimed.

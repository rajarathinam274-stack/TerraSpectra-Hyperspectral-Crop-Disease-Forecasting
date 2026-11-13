# TerraSpectra: Hyperspectral Crop Disease Forecasting

Research project investigating hyperspectral signatures associated with Septoria infection in wheat, with a focus on early detection and temporal progression.

## Research scope

Primary source: the public wheat Septoria hyperspectral imaging dataset hosted by Recherche Data Gouv (DOI 10.57745/WVP0FJ). See docs/dataset_provenance.md, docs/day2_annotation_semantics.md, docs/day3_hsi_ingestion_calibration.md and docs/day4_roi_extraction.md before interpreting fields or spectral data.

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

Use --modality SWIR for SWIR files. See docs/day3_hsi_ingestion_calibration.md for the dark-current and Spectralon reflectance rules. The published .hyspex files are described as dark-current corrected; do not subtract dark current a second time. Do not claim reflectance until the Spectralon reference panel/acquisition and any certified reflectance curve have been validated.

## Leaf ROI extraction

The Day 4 extractor reads one coordinate CSV per leaf and writes one mean spectrum per leaf ROI:

    python scripts/extract_leaf_spectra.py \
      --root /path/to/extracted/VNIR \
      --modality VNIR \
      --coordinate-base 0 \
      --coordinate-frame source_image \
      --output data/processed/vnir_leaf_spectra.csv \
      --audit data/processed/vnir_roi_audit.json \
      --max-images 1

The coordinate base and coordinate frame must be verified from the actual archive before running. If the CSV coordinates refer to a cropped/reframed image, use --coordinate-frame reframed_image and supply verified --row-offset and --col-offset values. The extractor rejects out-of-bounds coordinates; it does not guess indexing or crop transforms. See docs/day4_roi_extraction.md.

Output is explicitly labelled dark-current-corrected intensity, not reflectance, until the Spectralon reference workflow is validated.

## Google Colab

Open the [Day 1 validation notebook](https://colab.research.google.com/github/rajarathinam274-stack/TerraSpectra-Hyperspectral-Crop-Disease-Forecasting/blob/main/notebooks/01_dataset_validation.ipynb). If using local compute, connect the notebook to a local Jupyter runtime.

## Repository structure

- config/: dataset and experiment configuration
- docs/: dataset provenance, annotation semantics, roadmap and work logs
- scripts/: reproducible metadata acquisition, sample mapping, HSI and ROI utilities
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

Days 1–3 have committed provenance, annotation/sample-map, ENVI inspection and calibration scaffolds with synthetic tests. Day 4 adds per-leaf ROI extraction with explicit coordinate-base/frame declarations and synthetic tests. Actual annotation CSVs, .hyspex archives, coordinate indexing convention, crop offsets and Spectralon reference representation remain unverified in the execution environment. No real spectral table, model performance or forecasting result is claimed.

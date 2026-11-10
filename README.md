# TerraSpectra: Hyperspectral Crop Disease Forecasting

Research project investigating hyperspectral signatures associated with Septoria infection in wheat, with a focus on early detection and temporal progression.

## Research scope

Primary source: the public wheat Septoria hyperspectral imaging dataset hosted by Recherche Data Gouv ([DOI 10.57745/WVP0FJ](https://doi.org/10.57745/WVP0FJ)). See [dataset provenance and scientific scope](docs/dataset_provenance.md) before interpreting the annotations.

**Scientific distinction:** classification or early detection identifies infection status at an observed time point. Forecasting predicts a future disease state. This project will only claim forecasting if stable repeated biological identities and valid future-state labels are demonstrated.

## Day 1: dataset validation

The Day 1 workflow inventories the Dataverse dataset, downloads only the three small annotation CSVs, verifies file sizes and advertised checksums where available, records SHA-256 hashes, and audits annotation schemas.

    pip install -r requirements.txt
    python scripts/download_metadata.py
    python scripts/audit_annotations.py
    python scripts/inspect_metadata.py
    pytest -q

Raw hyperspectral image ZIP archives are intentionally not downloaded by the metadata script. The dataset contains large image archives; choose a small sample only after the annotation structure and available compute/storage are understood.

## Google Colab

Open the [Day 1 validation notebook](https://colab.research.google.com/github/rajarathinam274-stack/TerraSpectra-Hyperspectral-Crop-Disease-Forecasting/blob/main/notebooks/01_dataset_validation.ipynb).

If using local compute, connect the notebook to a local Jupyter runtime before running it. The notebook clones the repository if it is not already in the current working directory.

## Repository structure

- config/: dataset and experiment configuration
- docs/dataset_provenance.md: verified source facts and scientific limitations
- docs/15_day_roadmap.md: day-by-day deliverables
- scripts/: reproducible metadata acquisition and audit utilities
- notebooks/: Colab notebooks
- data/metadata/: downloaded metadata and audit outputs (not committed)
- data/raw/, data/processed/: source and derived data (not committed)
- models/, reports/generated/: generated artifacts (not committed)

## Methodology safeguards

1. Preserve source data and record provenance.
2. Verify calibration, wavelength metadata, labels and acquisition-time semantics before preprocessing.
3. Split by leaf/plant/pot or another verified biological unit; do not randomly split pixels or spectra from the same sample.
4. Use time-aware evaluation for any future-state prediction claim.
5. Fit preprocessing and feature selection on training data only.
6. Report macro-F1, per-class precision/recall and confusion matrices; accuracy alone is insufficient.
7. Controlled growth-chamber results must not be presented as field-validated performance.

## Current status

Day 1 repository workflow and dataset provenance documentation are committed. See the [Day 1 work log](docs/day1_work_log.md). The metadata download, Colab execution and complete test run remain pending; no model performance or forecasting result is claimed.

# TerraSpectra: Hyperspectral Crop Disease Forecasting

Research project investigating hyperspectral signatures associated with Septoria infection in wheat, with a focus on early detection and temporal progression.

## Research scope

Primary source: the public wheat Septoria hyperspectral imaging dataset hosted by Recherche Data Gouv ([DOI 10.57745/WVP0FJ](https://doi.org/10.57745/WVP0FJ)). Inspect the actual files, annotation schema, sample identifiers, acquisition dates and experimental design before modelling.

**Scientific distinction:** classification or early detection identifies infection status at an observed time point. Forecasting predicts a future disease state. This project will only claim forecasting if temporal labels and repeated observations support a valid future-time prediction experiment.

## Repository structure

- `config/`: dataset and experiment configuration
- `scripts/`: reproducible data acquisition and inspection utilities
- `notebooks/`: exploratory analysis and modelling notebooks
- `data/raw/`: downloaded source data (not committed)
- `data/processed/`: derived data (not committed)
- `models/`: trained model artifacts (not committed)
- `reports/`: figures and reports

## Setup

```bash
python -m venv .venv
# Windows: .venv\Scripts\activate
# macOS/Linux: source .venv/bin/activate
pip install -r requirements.txt
```

## Dataset metadata workflow

```bash
python scripts/download_metadata.py
python scripts/inspect_metadata.py
```

The downloader inventories the Dataverse dataset and retrieves selected annotation/metadata CSV files only. It does not automatically download large hyperspectral image archives.

## Methodology safeguards

1. Preserve source data and record provenance.
2. Verify calibration, wavelength metadata, labels and acquisition-time semantics before preprocessing.
3. Split by plant/leaf or other experimental unit to prevent related observations leaking across train and test sets.
4. Use time-aware evaluation for any future-state prediction claim.
5. Fit preprocessing and feature-selection steps on training data only.
6. Report macro-F1, per-class precision/recall, confusion matrix and uncertainty where feasible.

## Current status

Project scaffold and metadata-validation workflow are being initialized. No model performance or forecasting result is claimed at this stage.

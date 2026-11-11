# TerraSpectra: Hyperspectral Crop Disease Forecasting

Research project investigating hyperspectral signatures associated with Septoria infection in wheat, with a focus on early detection and temporal progression.

## Research scope

Primary source: the public wheat Septoria hyperspectral imaging dataset hosted by Recherche Data Gouv ([DOI 10.57745/WVP0FJ](https://doi.org/10.57745/WVP0FJ)). See [dataset provenance](docs/dataset_provenance.md) and the [Day 2 annotation semantics](docs/day2_annotation_semantics.md) before interpreting fields.

**Scientific distinction:** classification or early detection identifies infection status at an observed time point. Forecasting predicts a future disease state. This project will only claim forecasting if stable repeated biological identities and valid future-state labels are demonstrated.

## Dataset metadata and annotation workflow

```bash
pip install -r requirements.txt
python scripts/download_metadata.py
python scripts/audit_annotations.py
python scripts/build_sample_map.py
python scripts/inspect_metadata.py
pytest -q
```

The downloader retrieves only the three small annotation CSVs and records file inventory, checksums and SHA-256 hashes. Large VNIR/SWIR image ZIP archives are intentionally not downloaded automatically.

The sample-map builder extracts candidate date and pot-side keys. It does not infer missing plant/leaf identities, genotype assignments or treatment labels. Read the Day 2 documentation and inspect its JSON output before modelling.

## Google Colab

Open the [Day 1 validation notebook](https://colab.research.google.com/github/rajarathinam274-stack/TerraSpectra-Hyperspectral-Crop-Disease-Forecasting/blob/main/notebooks/01_dataset_validation.ipynb). If using local compute, connect the notebook to a local Jupyter runtime.

## Repository structure

- `config/`: dataset and experiment configuration
- `docs/dataset_provenance.md`: dataset facts and limitations
- `docs/day2_annotation_semantics.md`: biological hierarchy, data dictionary and leakage policy
- `docs/15_day_roadmap.md`: day-by-day deliverables
- `scripts/`: reproducible metadata acquisition and audit utilities
- `notebooks/`: Colab notebooks
- `data/metadata/`: downloaded metadata and audit outputs (not committed)
- `data/raw/`, `data/processed/`: source and derived data (not committed)

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

Day 1 provenance and metadata workflow are committed. Day 2 has a source-supported pot-level hierarchy, provisional data dictionary and candidate-map builder. The actual annotation CSVs have not yet been downloaded in the execution environment, so exact headers, row-level mapping and persistent plant/leaf identities remain unverified. No model performance or forecasting result is claimed.

# Day 1 work log — 2026-11-10

## Objective

Establish dataset provenance and create a reproducible, metadata-only validation workflow before downloading hyperspectral image archives or training models.

## Research findings verified from primary sources

- The selected source is Recherche Data Gouv dataset version 1.0, DOI 10.57745/WVP0FJ.
- The data paper reports two durum wheat genotypes under controlled growth-chamber conditions and the pathogen Zymoseptoria tritici.
- The paper reports 18 acquisition dates spanning one day before inoculation to 20 days after inoculation.
- VNIR: 216 bands, 411–993 nm; SWIR: 256 bands, 964–2,494 nm.
- Each modality reports 1,175 images and 3,326 leaves. Infected: 588 images / 1,652 leaves; non-infected: 587 images / 1,674 leaves.
- The dataset page lists the three annotation CSVs: Data_description.csv, VNIR_data.csv and SWIR_data.csv. The image archives are large and are not part of the Day 1 metadata-only download.
- The repository page states Etalab Open License 2.0.

References:
- Dataset: https://doi.org/10.57745/WVP0FJ
- Data paper: https://doi.org/10.1016/j.dib.2025.111404

## Repository work committed

- Added dataset provenance and scientific-scope documentation.
- Added the 15-day implementation roadmap.
- Hardened the metadata downloader with file-size and advertised-checksum checks, plus SHA-256 manifest output.
- Added a schema audit that reports candidate identity/time/label columns without assigning semantics automatically.
- Added the Day 1 Colab notebook and a focused test for column-hint detection.
- Updated README with setup commands, notebook link and current execution status.

## Verification status

- GitHub files were fetched back from the requested public repository on branch main.
- The notebook was fetched and parsed as valid notebook JSON (nbformat 4, 11 cells).
- A focused isolated fixture covering the configuration and candidate-column checks passed: 2 tests passed. This was not a full checkout-based repository test run.
- A full Git clone from the execution runner failed because github.com could not be resolved from that environment.
- The Dataverse metadata download and Colab notebook have not yet been executed. No raw hyperspectral archives have been downloaded, and no model has been trained or evaluated.

## Scientific decision

The 18-date acquisition design supports investigating early detection and disease progression. It does not, by itself, prove stable repeated leaf identities or a valid future-state target. Forecasting remains a hypothesis until the annotation IDs, pot/side structure and date semantics are inspected.

## Next action

Run notebooks/01_dataset_validation.ipynb in Google Colab (connected to the local runtime if local compute is required). Preserve the outputs from file_inventory.json, download_manifest.json and annotation_audit.json. Use those actual fields to build the Day 2 data dictionary and leakage-safe sample grouping plan.

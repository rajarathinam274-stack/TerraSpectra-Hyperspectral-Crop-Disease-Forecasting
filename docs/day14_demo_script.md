# TerraSpectra — technical demonstration script

**Target duration:** 5–6 minutes  
**Audience:** Internship mentor / technical reviewer  
**Current demo mode:** Software workflow and validation gates. A real-data disease prediction must not be shown until the data and fitted artifact are verified.

## 0. Before the demo

Use a clean Python 3.11 environment or Google Colab. Confirm the repository branch and commit:

```bash
git clone https://github.com/rajarathinam274-stack/TerraSpectra-Hyperspectral-Crop-Disease-Forecasting.git
cd TerraSpectra-Hyperspectral-Crop-Disease-Forecasting
git checkout main
git pull --ff-only origin main
git log -1 --oneline
```

Install the project dependencies (note: `requirements.txt` currently specifies direct dependencies without exact version pins; use the Day 15 CI environment artifact for the resolved package versions):

```bash
python -m venv .venv
# Linux/macOS:
source .venv/bin/activate
# Windows PowerShell:
# .venv\Scripts\Activate.ps1

python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

Do not claim a clean full-suite result until the command has actually completed in the demonstration environment.

## 1. Explain the dataset (45 seconds)

Show:
- `docs/dataset_provenance.md`
- `docs/day2_annotation_semantics.md`
- the source paper: https://doi.org/10.1016/j.dib.2025.111404

Say: “The paper reports 48 pots, two durum-wheat genotypes, 18 acquisition dates, and two HSI modalities. Our evaluation groups by pot because inoculation was assigned at pot level.”

## 2. Demonstrate metadata acquisition and validation (60–90 seconds)

```bash
python scripts/download_metadata.py
python scripts/audit_annotations.py
python scripts/build_sample_map.py
python scripts/inspect_metadata.py
```

Inspect:
- `data/metadata/download_manifest.json`
- `data/metadata/sample_map_candidates.csv`
- `data/metadata/sample_map_audit.json`

Verify the publisher-listed checksum results and actual CSV columns. If any download or checksum fails, stop and show the blocker; do not proceed using guessed column names.

## 3. Demonstrate one real HSI header (60 seconds)

Only after one image archive is downloaded and extracted:

```bash
python scripts/inspect_hsi.py /path/to/sample.hdr \
  --image /path/to/sample.hyspex \
  --modality VNIR \
  --output reports/sample_vnir_header.json
```

Repeat with `--modality SWIR` for a SWIR header. Compare observed wavelengths, dimensions, dtype, interleave and byte order with the publication. Do not call the output reflectance until the Spectralon reference path is validated. The published `.hyspex` data are described as dark-current corrected; do not subtract dark current twice.

## 4. Demonstrate ROI extraction (60 seconds)

Before extraction, inspect a matching JPEG preview and coordinate CSV. Confirm coordinate base, row/column order, image frame, crop offsets and overlay registration.

Then perform a one-image smoke test:

```bash
python scripts/extract_leaf_spectra.py \
  --root /path/to/extracted/VNIR \
  --modality VNIR \
  --coordinate-base VERIFIED_0_OR_1 \
  --coordinate-frame VERIFIED_SOURCE_OR_REFRAMED \
  --output data/processed/vnir_leaf_spectra.csv \
  --audit data/processed/vnir_roi_audit.json \
  --max-images 1
```

The uppercase values are placeholders. Replace them only after visual verification. Do not run full extraction until the one-image audit passes.

## 5. Explain the modelling and leakage controls (60 seconds)

Show:
- `docs/day6_logistic_regression_baseline.md`
- `docs/day8_nested_model_selection.md`
- `docs/day9_sensor_comparison.md`
- `docs/day11_forecasting_feasibility.md`

Explain:
- aggregate leaves/sides to one pot-date record;
- hold out pots as groups;
- fit imputation/scaling/feature selection only within training folds;
- use macro-F1 and class-wise metrics;
- treatment assignment is not symptom status;
- future-state prediction requires a later independently assessed outcome.

## 6. Show the software test evidence (30–45 seconds)

Run the focused suites:

```bash
python -m pytest -q tests/test_predict.py
python -m pytest -q tests/test_robustness_interpretation.py
```

The repository's Day 12 and Day 13 GitHub Actions workflows previously passed these focused synthetic tests. In a live demonstration, show the current command output rather than relying only on the historical run.

## 7. Inference demo — only with a verified model artifact

Do not fabricate a model artifact or use random spectra as if they were biological observations.

If a real model is later trained from verified data:

```bash
python scripts/predict.py \
  --input-csv /path/to/verified_new_pot_date_spectra.csv \
  --model /path/to/trusted_fitted_pipeline.joblib \
  --output-csv reports/generated/day12_predictions.csv
```

The input date must match the model's selected date. The model bundle and feature-column order must be preserved. Only load trusted joblib files.

If no real model artifact exists, show `python scripts/predict.py --help` and explain that the inference scaffold is tested but no real predictions are available.

## 8. Close (20 seconds)

“The software architecture and focused synthetic tests are in place. The remaining scientific gate is verified real data: annotation checksums, HSI headers, ROI registration, and pot-date spectral features. We will report biological metrics only after those gates pass. The current forecasting decision remains no-go because a complete future symptom-label table has not been verified.”

## Demo failure protocol

- **Checksum mismatch:** stop data processing; preserve the downloaded file and report expected versus observed checksum.
- **Header mismatch:** do not overwrite observed wavelength metadata with paper specifications.
- **ROI overlay mismatch:** stop extraction; revisit coordinate base/frame/offsets.
- **Missing class in a fold:** do not silently reduce the number of classes; revise the split design before training.
- **No verified symptom labels:** report treatment-discrimination only, not symptom detection.
- **No future outcome and timestamp:** retain the forecasting no-go.

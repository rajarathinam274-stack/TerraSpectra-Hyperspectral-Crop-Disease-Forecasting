# TerraSpectra — Day 15 reproducibility and handover

**Date:** 2026-11-24  
**Roadmap:** 15-day implementation roadmap  
**Handover status:** Software scaffold and documentation handed over; real-data scientific validation remains incomplete.

## 1. What this handover contains

The repository provides a reproducible *workflow scaffold* for the public wheat–Septoria hyperspectral dataset:

- provenance and annotation-semantics documentation;
- annotation acquisition, inventory, schema-audit and candidate sample-map scripts;
- ENVI header inspection and ROI extraction utilities;
- pot-date EDA and grouped baseline/model-comparison workflows;
- nested model selection, sensor comparison and date-wise treatment-discrimination analysis;
- a documented no-go audit for genuine future disease-state forecasting;
- guarded inference and robustness/interpretation utilities;
- synthetic tests and focused CI workflows;
- a technical report draft, presentation outline and demo script.

This is not a claim that the full biological experiment has been reproduced. The source dataset is not stored in Git.

## 2. Runtime and dependency reproducibility

The project runtime is declared in `.python-version` as **Python 3.11**.

`requirements.txt` currently specifies direct dependencies but does **not** pin exact versions or hashes. Do not describe it as a lockfile. The Day 15 GitHub Actions workflow installs those requirements, records the resolved package versions using `pip freeze --all`, hashes the environment input files, and uploads both records as a workflow artifact for 30 days.

### Clean checkout

```bash
git clone https://github.com/rajarathinam274-stack/TerraSpectra-Hyperspectral-Crop-Disease-Forecasting.git
cd TerraSpectra-Hyperspectral-Crop-Disease-Forecasting
git checkout main
git pull --ff-only origin main

python -m venv .venv
# Linux/macOS
source .venv/bin/activate
# Windows PowerShell: .venv\\Scripts\\Activate.ps1

python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

### Full software checks

```bash
python -m pytest -q
python -m compileall -q scripts tests

for script in \
  scripts/inspect_hsi.py \
  scripts/extract_leaf_spectra.py \
  scripts/explore_spectra.py \
  scripts/train_baseline.py \
  scripts/compare_models.py \
  scripts/nested_model_selection.py \
  scripts/compare_sensors.py \
  scripts/analyze_early_detection.py \
  scripts/audit_forecasting_feasibility.py \
  scripts/predict.py \
  scripts/robustness_interpretation.py
do
  python "$script" --help >/dev/null || exit 1
done
```

The Day 15 workflow runs these checks on GitHub-hosted Ubuntu with Python 3.11. After the workflow completes, download its `terraspectra-python-environment-<commit-sha>` artifact. On a compatible Python 3.11/Linux environment, the captured exact package set can be installed with:

```bash
python -m pip install -r environment-report.txt
```

The environment report is a resolved package-version snapshot for that CI run, not a cross-platform lockfile. The SHA-256 file records the exact `requirements.txt` and `.python-version` inputs used by the run.

### Verified Day 15 CI result

The first full Day 15 workflow completed successfully on GitHub-hosted Ubuntu with **Python 3.11.18** and **pip 26.3**:

- Workflow run: [45426718311 — Day 15 reproducibility and handover](https://github.com/rajarathinam274-stack/TerraSpectra-Hyperspectral-Crop-Disease-Forecasting/actions/runs/45426718311)
- Full test suite: **79 passed** (6 warnings; no test failures).
- Python compilation: passed.
- CLI smoke checks: all 11 executable interfaces passed.
- Resolved environment artifact: `terraspectra-python-environment-44db4113a440860844d971646f8fcb569d636b87` (uploaded; 30-day retention).

One scikit-learn `FutureWarning` reports that `SVC(probability=True)` is deprecated in scikit-learn 1.9 and will be removed in 1.11. It does not fail the current tests, but the SVM probability-calibration implementation should be migrated before upgrading to scikit-learn 1.11. Other warnings were runner/action deprecation notices.

The clean clone attempt from the separate execution container could not resolve `github.com`; therefore, the 79-test result is specifically the GitHub Actions run above, not a local run.

## 3. Dataset acquisition and validation

Primary dataset: Latchoumane et al., *Early detection of Zymoseptoria tritici infection on wheat leaves using hyperspectral imaging data*, Data in Brief 59 (2025), 111404. Dataset DOI: [10.57745/WVP0FJ](https://doi.org/10.57745/WVP0FJ). Retain the source citation and license attribution.

The downloader is intentionally limited to the three small annotation CSVs; it does not download the large hyperspectral image archives.

```bash
python scripts/download_metadata.py
python scripts/audit_annotations.py
python scripts/build_sample_map.py
python scripts/inspect_metadata.py
```

Review these local, git-ignored outputs:

- `data/metadata/dataset_metadata.json`
- `data/metadata/file_inventory.json`
- `data/metadata/download_manifest.json`
- `data/metadata/annotation_audit.json`
- `data/metadata/sample_map_candidates.csv`
- `data/metadata/sample_map_audit.json`

Check `dataverse_checksum_verified` in the manifest. A value of `true` is required when the publisher provides a supported checksum. Preserve the downloaded files and stop if a size or checksum mismatch is reported. Candidate identifiers and column-name hints are not confirmed semantics; manually verify them against `Data_description.csv` and the paper before modelling.

Raw archives, downloaded metadata, derived spectra, fitted models and generated reports are excluded from Git. Store their provenance, checksums, configuration and reproducible processing commands instead.

## 4. Real-data validation gates still open

The repository audit for this handover did not establish the following:

| Gate | Handover status |
|---|---|
| Three annotation CSVs downloaded in the current execution environment | Not verified |
| Publisher checksums matched against local copies | Not verified |
| Actual annotation schemas and date-to-DPI mapping audited from local files | Not verified |
| Real VNIR and SWIR ENVI header/binary pairs inspected | Not verified |
| Spectralon reference and reflectance calibration validated | Not verified |
| ROI coordinate base/frame/crop offsets visually registered | Not verified |
| Real leaf/pot-date spectral table generated | Not available |
| Real-data model evaluation or biological metrics | Not available |
| Real-data inference artifact and predictions | Not available |

The local clean clone/test attempt in the Day 15 execution environment was blocked because that environment could not resolve `github.com`. This is why no local full-suite result is claimed here; the repository's Day 15 GitHub Actions workflow is the authoritative execution route for the complete software checks.

## 5. Scientific interpretation rules

Keep these targets separate:

1. **Treatment-assignment classification:** predicts the inoculation/control assignment made at pot level. It is not an observed symptom label.
2. **Observed disease/symptom classification:** predicts independently assessed infection status or severity at the same observation time. This requires verified outcome annotations.
3. **Future disease-state forecasting:** predicts a separately assessed future symptom/severity outcome at a later timestamp for a stable biological unit.

The current forecasting decision remains **NO-GO**. Repeated acquisition dates and pot-side folders do not by themselves prove stable leaf identity or a complete future symptom-status table. Do not synthesize symptom-onset labels from cohort-level statements in the paper.

For any future predictive analysis:

- aggregate related ROIs/sides/leaves to the treatment-assignment unit before evaluation;
- keep both sides and all repeated observations from a pot in the same group partition;
- for genuine forecasting, enforce predictor time < outcome-assessment time and use chronological evaluation with biological groups held out;
- fit imputation, scaling, feature selection and dimensionality reduction only within training folds;
- report macro-F1, balanced accuracy, class-wise precision/recall, confusion matrices and uncertainty;
- describe the study as controlled-environment research, not field validation.

## 6. Final handover decision

**Software handover:** The repository contains the planned analysis and inference scaffolds, documentation, synthetic test modules, and a Day 15 full-check workflow. Its final CI result must be read from the linked workflow run for the handover commit.

**Scientific handover:** Incomplete pending real annotation acquisition, checksum/schema validation, real HSI header and ROI verification, and a verified pot-date spectral table. No real-data accuracy, disease-detection score, wavelength ranking, or forecast metric is available at this checkpoint.

**Recommended next research action:** Run the annotation downloader in Google Colab or a network-enabled local environment, preserve the generated manifest, inspect actual CSV semantics, then validate one real VNIR and one real SWIR image/header/ROI set before extracting the full dataset.

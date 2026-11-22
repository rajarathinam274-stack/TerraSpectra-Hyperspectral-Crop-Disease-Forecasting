# Day 13 work log — 2026-11-22

## Repository and roadmap review

- Reviewed the 15-day roadmap; Day 13's concrete deliverable is robustness and interpretation: error analysis, feature interpretation and sensitivity checks.
- Verified the public repository and main branch. The current head before Day 13 work was 8d2e079e0998ce9e9f5710fce7f137214928e8cf (guarded Day 12 inference pipeline).
- Verified GitHub Actions run 44920198240 for Day 12 completed successfully on commit 8d2e079e0998ce9e9f5710fce7f137214928e8cf.
- Confirmed the tracked repository tree contains source, tests and documentation but no downloaded data directory or real model outputs. The Day 12 work log also records that no real spectra or fitted real-data artifact are available.

## Implementation

- Added scripts/robustness_interpretation.py to evaluate one predeclared classifier on one selected date using pot-grouped StratifiedGroupKFold.
- Added held-out out-of-fold predictions and fold metrics for error analysis.
- Added held-out per-band permutation importance, training-median band ablation and Gaussian-noise sensitivity. Noise scale is estimated from each training fold only.
- Kept imputation and scaling inside the fitted training-fold Pipeline. The script rejects duplicate pot/date rows, treatment-label drift, insufficient independent groups, class-missing folds, missing columns and all-missing training bands.
- Added synthetic tests and a focused Day 13 GitHub Actions workflow.
- Added the Day 13 analysis guide and this work log.

## Local verification

- python -m pytest -q tests/test_robustness_interpretation.py: 6 passed in a local isolated test workspace using synthetic data.
- python -m py_compile scripts/robustness_interpretation.py: passed.
- python scripts/robustness_interpretation.py --help: passed.
- The local test workspace was not a clone of the repository; no real-data experiment was run. GitHub Actions verification is pending until the Day 13 commit is pushed.

## Scientific status

- No real-data metrics, feature rankings, or robustness results are reported.
- Treatment-assignment classification remains distinct from observed symptom classification and genuine future disease forecasting.
- The Day 11 forecasting feasibility decision remains NO-GO until independently assessed future symptom/severity labels, assessment timestamps and stable pot IDs are available.
- Controlled-environment results must not be represented as field validation.

## Next action

Resolve the existing real-data dependency: download the three official annotation CSVs, verify their publisher-listed MD5 checksums, inspect the exact schema and date/DPI mapping, then validate at least one real image/header/ROI-coordinate set before producing pot-date spectra. Only then run the Day 13 analysis on real observations.

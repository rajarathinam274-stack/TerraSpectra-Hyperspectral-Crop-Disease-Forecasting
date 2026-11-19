# Day 10 work log — 2026-11-19

Reviewed the current main branch, Day 9 sensor comparison, Day 5 pot-date schema, Day 2 annotation semantics and the 15-day roadmap.

Research review confirms that the paper reports visual inspection, progressive necrosis from 7 DPI, later pycnidia, and ambiguity with senescence. The publication describes sample/leaf-count annotation tables but does not establish a complete per-pot/date symptom-status field. The source's disease-confidence annotation must not be mistaken for an observed binary symptom label.

Added a date-wise treatment-discrimination pipeline. It trains a separate same-date Logistic Regression model for each date, reuses one pot-level StratifiedGroupKFold assignment across dates, fits preprocessing only on each training fold, and exports date/fold metrics, OOF predictions, pot-fold assignments, plot and JSON audit.

Verification: a local development prototype passed five focused synthetic tests, compilation and CLI smoke checks using 20 synthetic pots, two classes, four dates and four bands. The committed GitHub source and test files were fetched back and verified, but the exact fetched repository copy was not executed in this run. The Day 10 GitHub Actions workflow was added; no status/check result was returned at verification time. Run `pytest -q tests/test_analyze_early_detection.py` after pulling before treating the committed copy as execution-verified. No real dataset rows or spectra were used.

Scientific boundary: treatment assignment is known at inoculation. The output is same-date inoculation-associated spectral discrimination, not symptom detection or future forecasting. Symptom status remains not assessed. No earliest pre-symptomatic date or real performance score is claimed.

Blocker: the official repository metadata is indexed, but direct data-host access failed in this runtime. Actual annotation CSVs, ENVI images, validated ROI spectra and the authoritative date-to-DPI mapping are still required. Next action: download/checksum the annotation CSVs in Colab, inspect the actual headers and DPI mapping, then run Day 10 on verified pot-date VNIR spectra.


## Published annotation-file integrity metadata

The official dataset record lists these public annotation CSVs and MD5 values (published 2024-11-15):
- `Data_description.csv`, 9.2 KB, MD5 `2efd148e433016da14a3209e6db575df`
- `VNIR_data.csv`, 5.5 KB, MD5 `181f1f7a63b0434210d57841e3d7d7f8`
- `SWIR_data.csv`, 5.5 KB, MD5 `12dc1a89b7f0d648948750247ef488a3`

These checksums are published metadata, not proof that the files have been downloaded in this runtime. The next acquisition step is to download the three small CSVs from the official dataset page, verify the checksums, then inspect their actual columns and rows.

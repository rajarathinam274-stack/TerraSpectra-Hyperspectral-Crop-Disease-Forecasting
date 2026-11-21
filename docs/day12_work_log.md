# Day 12 work log — 2026-11-21

- Audited the public GitHub repository and confirmed main is the default branch with push permission for the authenticated account.
- Reviewed the 15-day roadmap: Day 12 deliverable is a lightweight inference/demo interface.
- Reviewed the Day 6 model artifact schema: fitted pipeline, exact feature list, target semantics, selected acquisition date and grouping field.
- Added scripts/predict.py to load a trusted Day 6 artifact, enforce matching acquisition date and exact spectral features, run inference without refitting preprocessing, preserve input metadata, and export labels/probabilities with explicit task semantics.
- Added synthetic tests for valid inference, mixed/wrong dates, missing features, all-missing spectra, missing date metadata, duplicate pot IDs and semantic separation from forecasting.
- Added a focused GitHub Actions workflow for the Day 12 inference tests.
- No real model artifact or real spectra are present in the repository; the demo cannot yet produce scientifically meaningful real-data predictions.
- Next action: acquire and verify the three official annotation CSVs, inspect actual schema and date/DPI mapping, then validate a real ROI/pot-date table before fitting the baseline artifact.

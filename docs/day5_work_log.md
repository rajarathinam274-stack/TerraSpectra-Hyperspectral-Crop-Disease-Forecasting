# Day 5 work log — 2026-11-14

## Objective

Implement leakage-aware exploratory spectral analysis (EDA) for Day 4 leaf ROI spectra.

## Research decisions

- The source dataset contains VNIR/SWIR spectra collected over 18 dates; the published paper describes per-leaf mean spectra and class/date mean spectra.
- Pot remains the conservative biological grouping unit because infection treatment was assigned at pot level.
- Spectral-temporal studies of Septoria have noted that single-date reflectance can be confounded by genotype and environment; temporal change can add useful context. This motivates date-stratified EDA, but does not establish forecasting from this controlled dataset.
- Treatment assignment is not symptom onset or severity. Classification of treatment status is not future disease prediction.

## Implementation

Added `scripts/explore_spectra.py`:
- Reads Day 4 band columns and optional per-image wavelength axes.
- Rejects non-matching wavelength axes instead of silently comparing different bands.
- Supports explicit, validated many-to-one annotation joins.
- Aggregates leaf ROIs to pot-date means before class/date summaries and PCA.
- Reports missingness and IQR outlier flags without automatic deletion.
- Writes pot-date spectra, class/date summaries, ROI quality, per-date profiles, PCA scores/plot and JSON audit.
- Keeps intensity labelled as non-reflectance when that is the Day 4 input domain.

Added six focused tests for band ordering, pot-date aggregation, duplicate annotation keys, wavelength mismatch rejection, end-to-end EDA outputs and missing biological grouping keys.

## Verification

- Focused synthetic tests: 6 passed.
- Python compileall: passed.
- CLI help: passed.
- Synthetic end-to-end output generation (CSV, JSON, profile plots and PCA plot): passed.
- Real dataset download/ROI extraction/EDA: not run; no actual source image, coordinates or annotation CSV were available to this run.
- Full repository test suite: not run.

## Day 5 status

Implementation and synthetic validation complete. Scientific EDA remains pending actual spectra and verified annotation joins. No real spectral trend, PCA separation, classification result or forecasting result is claimed.

## Next action

Acquire and validate one actual VNIR image/header/coordinate trio, generate its Day 4 ROI spectra, and run Day 5 EDA. Then repeat for SWIR only after wavelength alignment is confirmed. Day 6 baseline modelling must wait for verified labels and pot-level grouping keys.

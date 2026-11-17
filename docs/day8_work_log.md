# Day 8 work log — 2026-11-17

## Repository review

- Authenticated account verified as rajarathinam274-stack.
- Repository: rajarathinam274-stack/TerraSpectra-Hyperspectral-Crop-Disease-Forecasting.
- Default branch main; public; authenticated account has admin/push permission.
- Reviewed the 15-day roadmap, Day 7 work log/methodology/script/tests, Day 6 baseline and Day 5 EDA implementation.
- Latest commit before Day 8: 4fc146cad481556439e1dfc22219c1d95ae453e6.

## Implementation

Added scripts/nested_model_selection.py and tests/test_nested_model_selection.py.

- Nested outer/inner StratifiedGroupKFold; pot IDs remain disjoint at both levels.
- Same materialized outer folds are reused for all six predeclared combinations: three model families × no selection/ANOVA SelectKBest.
- Inner folds are materialized once per outer training set and shared across all six searches.
- GridSearchCV optimizes macro-F1 inside each outer training partition.
- Imputation, scaling and ANOVA selection are inside Pipelines and fitted only on training partitions.
- Records outer/inner group membership, best inner parameters, outer predictions, class metrics and confusion matrices.
- No all-data model artifact is saved; Day 8 is an evaluation protocol deliverable.

## Verification

- Five focused synthetic tests passed.
- Python compileall passed.
- CLI help invocation passed.
- Synthetic fixture: 20 independent pots, two classes, two acquisition dates, six spectral bands; tests used three outer folds and two inner folds to keep CI/runtime small.
- Full repository test suite and GitHub CI were not run.

## Data and scientific blockers

The public dataset DOI is 10.57745/WVP0FJ. Indexed metadata continues to describe 1,175 images per modality and 3,326 leaves over 18 dates. The official Recherche Data Gouv page timed out on direct retrieval in this run. No real annotation CSVs, ENVI cubes, coordinate files or verified Day 4 spectra were available locally. No real model was trained.

Treatment assignment is not an observed symptom label. Same-date classification is not forecasting. Forecasting remains conditional on stable repeated biological identities and future symptom/severity labels.

## Next action

Acquire and audit actual metadata and one real ROI/spectral sample in Colab before reporting any scientific score. Then run Day 8 on a verified one-date pot-level table, or document that the available labels support treatment discrimination only.


## Day 8 verification refinement

A post-commit review found that deterministic inner split lists were being regenerated for each strategy. The implementation now materializes each outer fold's inner split list once and reuses it across all six strategies. It also records selected band names and their frequency across outer folds for descriptive feature-selection stability analysis. The focused synthetic suite was rerun after this refinement: five tests passed; compileall and CLI help passed.

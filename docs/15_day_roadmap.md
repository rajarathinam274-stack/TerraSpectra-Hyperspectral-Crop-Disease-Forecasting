# TerraSpectra — 15-day implementation roadmap

A day is complete only when its artifact exists and its validation status is stated. Do not report model metrics before running a reproducible evaluation.

| Day | Focus | Concrete deliverable | Exit condition |
|---:|---|---|---|
| 1 | Dataset provenance and acquisition | Dataset citation, file inventory, verified annotation CSV downloads, metadata audit | File checksums and annotation schemas recorded; blockers documented |
| 2 | Annotation semantics and sample map | Data dictionary, ID hierarchy, date/DPI mapping, treatment/label audit | Pot-level grouping is source-supported; exact CSV semantics and longitudinal IDs verified from actual files |
| 3 | HSI ingestion and calibration | ENVI reader, header parser, raw-to-reflectance calibration plan | Synthetic calibration tests pass; real header wavelengths, units, dtype, interleave, byte order, dimensions and reference workflow validated |
| 4 | Leaf ROI and spectral extraction | Reproducible ROI extraction and per-leaf spectra table | Coordinate conventions and extraction checks pass on sample images |
| 5 | Exploratory spectral analysis | Class/date/genotype summaries, spectral plots, PCA | EDA uses correctly grouped samples and documents missingness/outliers |
| 6 | Baseline classifier | Logistic-regression baseline with train-only preprocessing | Group-aware validation and baseline metrics are reproducible |
| 7 | Nonlinear classifiers | SVM and Random Forest comparison | Macro-F1, per-class recall and confusion matrices reported |
| 8 | Model selection | Group-aware tuning and feature-selection comparison | No preprocessing or feature-selection leakage |
| 9 | Sensor comparison | VNIR vs SWIR vs carefully aligned fusion experiment | Modality comparison uses matched samples and fair splits |
| 10 | Early-detection analysis | Performance by acquisition date / days post inoculation | Earliest reliable pre-symptomatic detection is assessed without time leakage |
| 11 | Forecasting feasibility | Future-state target specification and time-aware split, or documented no-go decision | Forecasting attempted only if stable repeated identities and future labels exist |
| 12 | Demonstration pipeline | Lightweight inference/demo interface | Inputs, outputs, model provenance and limitations are explicit |
| 13 | Robustness and interpretation | Error analysis, feature interpretation and sensitivity checks | Weaknesses, uncertainty and controlled-environment limits are documented |
| 14 | Final report and presentation | Technical report, figures, slides and demo script | Claims match verified experiments and limitations |
| 15 | Reproducibility and handover | Clean setup, pinned environment, final checks and release | Another user can reproduce the documented workflow |

## Non-negotiable research rules

1. Classification at time t is not forecasting at time t + delta.
2. Do not infer repeated leaf identity from date-stamped folders alone.
3. Group related pixels, spectra, images and repeated observations by the strongest verified biological unit.
4. For future-state evaluation, train on earlier time points and test on later dates, with biological groups held out.
5. Fit imputation, scaling, feature selection and dimensionality reduction inside training folds.
6. Report macro-F1 and class-wise precision/recall; do not rely on accuracy alone.
7. Keep raw data out of Git. Track provenance, checksums, configuration and derived summaries instead.
8. Controlled growth-chamber results must not be described as field-validated performance.

## Day 2 progress

The source-supported experiment hierarchy and pot-level grouping policy are documented in docs/day2_annotation_semantics.md. A conservative candidate-map builder is available at scripts/build_sample_map.py. Day 2 remains **partially complete** until the actual annotation CSVs are downloaded and their exact columns, pot/genotype/treatment mapping and repeated biological IDs are inspected.

## Day 3 progress

Added scripts/hsi_io.py for lazy ENVI header inspection, memory-mapped cube opening, wavelength-unit conversion, sensor-profile comparison and separate reflectance paths. Added scripts/inspect_hsi.py, synthetic calibration tests and docs/day3_hsi_ingestion_calibration.md. The paper reports that .hyspex data are already dark-current corrected, so the published-data path does not subtract dark current twice.

Day 3 remains **partially complete** until a real .hdr/.hyspex pair is inspected and the Spectralon SRS99 reference representation is confirmed. No real reflectance cube has been produced.

## Day 4 progress

Added scripts/extract_leaf_spectra.py, tests/test_extract_leaf_spectra.py and docs/day4_roi_extraction.md. The extractor discovers per-image leaf coordinate CSVs, reads the paper-specified (vertical row, horizontal column) coordinate order, computes one mean spectrum per ROI from a BIP memory map, records pot/date/image provenance candidates, and emits a JSON audit. It requires explicit coordinate indexing base and coordinate frame; reframed-image offsets must be supplied. It rejects out-of-bounds coordinates and labels the output as dark-current-corrected intensity rather than reflectance.

Eight synthetic tests, Python compilation, CLI help and a mocked batch smoke test passed. Day 4 remains **partially complete** until one real image/header/coordinate trio is inspected and coordinate base, frame, crop offsets and overlay registration are confirmed. No real spectra were extracted.

## Day 5 progress

Added scripts/explore_spectra.py, tests/test_explore_spectra.py, docs/day5_exploratory_spectral_analysis.md and docs/day5_work_log.md. The EDA pipeline validates explicit annotation joins, checks per-image wavelength-axis consistency, aggregates ROIs to pot-date means, reports missingness and IQR outlier flags, generates date-specific spectra plots and descriptive PCA.

Six focused synthetic tests, Python compilation, CLI help and synthetic end-to-end output generation passed. Day 5 implementation is complete, but real EDA remains **blocked** until verified annotations and at least one real Day 4 spectral table are generated. No real class/date trend or PCA separation is claimed.

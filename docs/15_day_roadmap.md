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

## Day 6 progress

Added scripts/train_baseline.py, tests/test_train_baseline.py and docs/day6_logistic_regression_baseline.md. The baseline accepts Day 5 pot-date spectra at one preselected acquisition date, requires explicit target semantics and exactly one row per pot, and uses 5-fold StratifiedGroupKFold by pot. Median imputation and standard scaling are inside the model Pipeline and are fitted on training folds only. It writes out-of-fold predictions, fold assignments, classification metrics, confusion matrix and a separately all-data-fitted pipeline artifact.

Six focused synthetic tests, Python compilation and CLI help passed locally. No real dataset model was trained because verified annotation labels and Day 4 spectra are not available in the execution environment. No real metric is claimed.

During Day 6 review, corrected a double-escaped digit pattern in the Day 5 EDA band-column detector; the intended band_001 columns now match the regex. Day 5's existing band-order test should be included in the next complete test run.

Day 6 implementation is complete; scientific model evaluation remains **blocked** pending actual annotation downloads, validated ROI extraction and a verified target label. A treatment-assignment target supports treatment discrimination only, not symptom detection or future forecasting.

## Day 7 progress

Added scripts/compare_models.py, tests/test_compare_models.py, docs/day7_model_comparison.md and docs/day7_work_log.md. The comparison includes the Day 6 Logistic Regression baseline, RBF-SVM and Random Forest with fixed, untuned specifications. A single 5-fold StratifiedGroupKFold split list is materialized once and reused across all three models. Pot overlap is explicitly rejected; median imputation and scaling are fitted within each training fold, with scaling omitted for Random Forest.

Four focused synthetic-fixture tests passed. Python compilation and CLI help passed. The tests validate shared group folds, artifact generation and input guards on synthetic data only. No actual annotation CSVs or real Day 4 spectra were available, so no real model metric or winning model is reported. Day 7 implementation is complete; real-data comparison remains blocked.

The Day 7 comparison is exploratory. Choosing a model using the same OOF scores creates selection optimism; Day 8 must use nested group-aware validation for tuning and model selection. Treatment-assignment classification remains distinct from symptom detection and future disease forecasting.


## Day 8 progress

Added scripts/nested_model_selection.py, tests/test_nested_model_selection.py, docs/day8_nested_model_selection.md and docs/day8_work_log.md. The workflow compares three model families crossed with no feature selection and ANOVA SelectKBest. Five outer pot-grouped folds estimate each predeclared tuned procedure; three inner pot-grouped folds tune hyperparameters by macro-F1. Outer folds are shared across all strategies; inner folds are shared within each outer training partition. Imputation, scaling and feature selection remain inside Pipelines and are fitted only on training partitions.

Five focused synthetic tests, Python compilation and CLI help passed. The tests use 20 synthetic pots and do not establish biological performance. The official dataset page timed out during direct retrieval; actual annotations, ENVI data, coordinate registration and real Day 4 spectra remain unavailable. No real model metric or forecast result is claimed.

Day 8 implementation is complete after commit verification; real-data model selection remains blocked. The six outer-CV strategy scores are estimates for predeclared procedures. Choosing the best among those six after inspecting results adds another selection step; a final choice requires an untouched external or separately predeclared evaluation.

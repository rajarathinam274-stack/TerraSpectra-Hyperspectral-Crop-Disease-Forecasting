# TerraSpectra — 15-day implementation roadmap

A day is complete only when its artifact exists and its validation status is stated. Do not report model metrics before running a reproducible evaluation.

| Day | Focus | Concrete deliverable | Exit condition |
|---:|---|---|---|
| 1 | Dataset provenance and acquisition | Dataset citation, file inventory, verified annotation CSV downloads, metadata audit | File checksums and annotation schemas recorded; blockers documented |
| 2 | Annotation semantics and sample map | Data dictionary, ID hierarchy, date/DPI mapping, treatment/label audit | Biological unit and leakage-safe grouping strategy justified |
| 3 | HSI ingestion and calibration | ENVI reader, header parser, raw-to-reflectance calibration plan | Wavelengths, units, dark/white references and data types validated |
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
4. For future-state evaluation, train on earlier time points and test on later time points, with biological groups held out.
5. Fit imputation, scaling, feature selection and dimensionality reduction inside training folds.
6. Report macro-F1 and class-wise precision/recall; do not rely on accuracy alone.
7. Keep raw data out of Git. Track provenance, checksums, configuration and derived summaries instead.
8. Controlled growth-chamber results must not be described as field-validated performance.

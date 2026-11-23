# TerraSpectra: Hyperspectral Analysis of Wheat Septoria Infection

**Technical report draft — v0.1**  
**Prepared:** 23 November 2026  
**Project checkpoint:** Day 14 of the 15-day implementation roadmap  
**Evidence status:** Engineering scaffolds and synthetic CI checks verified; real-data scientific evaluation pending.

> **Important status statement:** This is a methods-and-engineering report draft, not a completed empirical disease-detection study. No real-data model metrics, wavelength rankings, disease forecasts, or field-performance claims are available at this checkpoint.

## Abstract

TerraSpectra is a reproducible research pipeline for investigating whether visible–near-infrared (VNIR) and short-wave infrared (SWIR) hyperspectral measurements contain information associated with Septoria tritici infection in durum wheat. The selected public dataset contains repeated observations of two durum-wheat genotypes under controlled growth-chamber conditions. The project implements data-provenance checks, ENVI ingestion and calibration utilities, leaf-region spectral extraction, pot-date exploratory analysis, group-aware model workflows, sensor-comparison utilities, early-detection and forecasting-feasibility audits, guarded inference, and robustness/interpretation tooling.

The central experimental constraint is the pot-level treatment assignment. Spectra, leaves, image sides, and repeated dates from the same pot are not independent replicates. Accordingly, the project specifies pot-grouped validation and training-fold-only preprocessing. The current source description documents repeated hyperspectral acquisition and visual symptom monitoring, but does not establish a complete independently assessed future symptom-status table linked to every pot and prediction date. Genuine disease-outcome forecasting is therefore not justified at this checkpoint.

The repository's focused Day 12 and Day 13 GitHub Actions workflows passed their respective synthetic tests. The actual annotation CSVs, raw ENVI image archives, verified ROI coordinate registration, and real pot-date spectra have not been validated in the execution environment. Consequently, this report records the reproducible method and implementation status without inventing empirical results.

## 1. Research problem and objectives

Septoria tritici blotch / leaf blotch is caused by the fungal pathogen *Zymoseptoria tritici*. Visual symptom assessment can be difficult when disease-related necrosis overlaps with natural senescence. Hyperspectral imaging provides spatially resolved measurements across many wavelengths and may reveal spectral changes associated with infection.

The project has four bounded objectives:

1. Establish a provenance-preserving pipeline for the public wheat HSI dataset.
2. Extract and aggregate spectral observations at a defensible biological unit.
3. Compare conventional chemometric and machine-learning classifiers under leakage-resistant validation.
4. Assess whether the available labels support same-date classification, early detection, or genuine future-state forecasting.

The project does **not** claim a deployable field diagnostic system. The selected experiment is controlled-environment research material.

## 2. Dataset and experimental design

### 2.1 Source

- **Dataset:** Early detection of Septoria infection on wheat leaves using hyperspectral imaging data.
- **Dataset DOI:** https://doi.org/10.57745/WVP0FJ
- **Data paper:** Latchoumane et al. (2025), *Data in Brief*, 59, 111404.
- **Article DOI:** https://doi.org/10.1016/j.dib.2025.111404
- **Full text:** https://pmc.ncbi.nlm.nih.gov/articles/PMC11919375/

The study reports two susceptible durum-wheat genotypes (EPO_067 and EPO_068), 48 pots in total, and 24 pots per genotype. For each genotype, 12 pots were assigned to the infected treatment and 12 to the non-infected control. Six plants were arranged in each pot across two sides. The archive uses a `NUM_SIDE` convention, where the number identifies the pot and D/G identifies the measured side.

### 2.2 Acquisition

The study reports 18 acquisition dates spanning one day before inoculation through 20 days post inoculation (DPI). No HSI acquisition was made at 1, 2, 3, or 9 DPI. The published article reports 1,175 images and 3,326 leaves for each modality.

| Modality | Sensor | Bands | Published wavelength range |
|---|---|---:|---:|
| VNIR | HySpex VNIR-1800 | 216 | 411–993 nm |
| SWIR | HySpex SWIR-384 | 256 | 964–2,494 nm |

The modalities overlap in wavelength from approximately 964 to 993 nm. The paper describes ENVI-format `.hyspex` image binaries, `.hdr` metadata, reconstructed JPEG previews, and per-image leaf pixel-coordinate CSV files. These published specifications are expected reference values, not substitutes for checking each downloaded header.

### 2.3 Labels and biological unit

The experiment's infected/control status is assigned at pot level. This label represents **inoculation treatment assignment**. It does not establish that a pot or leaf was visibly symptomatic on every acquisition date.

The paper describes visual monitoring, progressive necrosis beginning around 7 DPI, pycnidia in later stages, and pathologist confirmation at the end of the experiment. It also notes that senescence can complicate symptom assessment. The paper's data-description section characterizes the annotation CSVs as sample information and leaf counts per image/day. A complete per-pot/per-date independently assessed symptom-status table has not been verified from the actual CSV contents.

Therefore, the project keeps three targets distinct:

- `treatment_assignment`: infected versus control inoculation group;
- `observed_infection_status` / `symptom_severity`: only valid if independently assessed and documented at the prediction date;
- `future_symptom_status`: only valid if linked to a later assessment timestamp and a stable biological unit.

## 3. Methodology

### 3.1 Provenance and acquisition

The repository provides a metadata downloader and audit workflow for the three small annotation CSVs. Each downloaded file should be checked against publisher metadata where a checksum is available, and a local SHA-256 manifest should be retained. The large image archives are intentionally not downloaded automatically.

Required evidence before real analysis:
- downloaded file inventory and file sizes;
- publisher checksum comparison and local SHA-256;
- exact annotation column names, row counts, missingness, and duplicate audit;
- explicit key mapping between image/sample records and pot/date/side;
- verified date-to-DPI mapping from the experiment timetable.

### 3.2 HSI ingestion and calibration

The project includes ENVI header inspection and memory-mapped cube access. Each real header must be checked for dimensions, band count, data type, interleave, byte order, header offset, wavelength array, and wavelength units.

The paper states that the published `.hyspex` files already contain dark-current-corrected intensity. Its reflectance equation is:

`R(λ) = (I(λ) - I_d(λ)) / (I_0(λ) - I_d(λ))`

The published-data path must not subtract dark current a second time. The Spectralon SRS99 reference representation and any certified wavelength-dependent reference curve must be checked before describing extracted values as reflectance. Until those checks pass, outputs must be labelled as dark-current-corrected intensity or the precisely verified intermediate quantity.

### 3.3 ROI extraction and aggregation

Leaf pixel coordinates are documented as vertical row followed by horizontal column. However, the coordinate indexing base, coordinate frame after image reframing, crop offsets, and overlay registration must be validated on a real image/header/coordinate trio before full extraction.

The extractor computes a mean spectrum for each leaf ROI. For supervised evaluation, related leaf ROIs and both pot sides must then be aggregated to one pot-date feature vector. Leaf ROIs, pixels, image sides, and repeated dates from the same pot must not be counted as independent biological replicates.

### 3.4 Exploratory analysis

Planned descriptive outputs include:
- band-wise missingness and wavelength-axis QA;
- pot-date mean spectra and variability;
- date- and treatment-stratified descriptive summaries, clearly labelled as treatment summaries if no symptom labels exist;
- outlier flags retained for review rather than silently removed;
- PCA as descriptive visualization only.

PCA and all learned transformations used in predictive modelling must be fitted on training partitions only.

### 3.5 Predictive modelling and validation

The repository provides workflows for Logistic Regression, RBF-SVM, Random Forest, nested group-aware model selection, matched VNIR/SWIR comparison, date-wise treatment-discrimination analysis, and robustness interpretation.

The primary independent grouping key is pot ID. At a fixed acquisition date, use one aggregated row per pot and a stratified group split. Imputation, scaling, feature selection, and dimensionality reduction must be fitted inside each training fold. For model selection, nested group-aware validation is required; choosing a model on the same scores used to report its final performance introduces selection optimism.

Pre-specified metrics:
- balanced accuracy;
- macro-F1;
- per-class precision and recall;
- confusion matrix;
- fold-level scores and independent-pot counts;
- confidence intervals at the pot level where the resampling design is valid.

VNIR, SWIR, and fusion comparisons must use exactly matched pot-date samples and shared group folds. Wavelength overlap must be handled explicitly and actual header wavelength axes must be verified.

### 3.6 Early detection versus forecasting

A same-date classifier estimates a label at the observed time. A treatment-assignment classifier distinguishes inoculated from control pots; it does not demonstrate symptom detection. A pre-symptomatic detection claim additionally requires independently assessed symptom-negative status at the prediction origin.

A genuine forecast requires:

`X(p,t) → Y(p,t+h)`

where `Y(p,t+h)` is an independently assessed symptom or severity outcome at a documented future assessment time, with a predeclared horizon `h`. For pre-symptomatic forecasting, the prediction origin must also be symptom-negative. Evaluation must be chronological and must hold out biological groups. Do not infer a per-pot future label from the cohort-level statement that symptoms began around 7 DPI.

The Day 11 repository decision is **NO-GO** for a disease-outcome forecasting model using the currently documented annotations.

## 4. Implementation status at Day 14

| Workstream | Repository implementation | Evidence status |
|---|---|---|
| Dataset provenance and annotation audit | Metadata download, annotation audit, sample-map utilities | Code documented; actual local files/checksums not verified |
| HSI ingestion | ENVI header inspection and calibration utilities | Synthetic checks; real header/reference validation pending |
| ROI extraction | Coordinate-driven leaf spectral extraction | Synthetic checks; real coordinate registration pending |
| EDA | Pot-date aggregation, QA, spectral profiles and PCA | Synthetic checks; no real EDA outputs verified |
| Baseline/model comparison | LR, SVM, RF, nested selection | Synthetic test coverage; no real model metrics |
| Sensor comparison | Matched VNIR/SWIR/fusion workflow | Synthetic checks; no real sensor comparison |
| Early-detection analysis | Date-wise pot-grouped treatment discrimination | Implementation present; symptom labels not verified |
| Forecast feasibility | Manifest audit and documented NO-GO | Decision documented; no forecast model |
| Inference | Guarded same-date prediction utility | Day 12 focused CI passed; no real model artifact |
| Robustness/interpretation | OOF error analysis, permutation, ablation and noise sensitivity | Day 13 focused CI passed; no real-data interpretation |

### Verified engineering checks

- Day 12 GitHub Actions run: **success**, focused inference tests, compilation, and CLI help.
- Day 13 GitHub Actions run: **success**, six focused robustness/interpretation tests, compilation, and CLI help.
- Day 13 tests use synthetic fixtures. They validate software behavior and input guards, not biological performance.
- The current main branch checkpoint before the Day 14 documentation commit was `ba277f5aa7bacdf218b08c9233a6de5a857382fd`.

No full repository-wide test result is asserted in this report.

## 5. Results

### 5.1 Empirical results

**No real-data predictive result is available at Day 14.** The project has not verified the actual annotation downloads, a real ENVI cube/header pair, a registered ROI-coordinate set, or a real pot-date spectral feature table. Consequently, this report does not provide:
- accuracy, balanced accuracy, macro-F1, ROC-AUC, or confusion matrices from real observations;
- an identified best model;
- a ranked list of disease-discriminative wavelengths;
- an earliest pre-symptomatic detection date;
- a future disease forecast.

### 5.2 Engineering results

The repository contains a modular research implementation and focused synthetic CI tests for its Day 12 and Day 13 components. These tests reduce software-regression risk but do not close the dataset-validation gap.

## 6. Limitations and threats to validity

1. **No real-data verification in the current execution environment.** Dataset specifications are taken from the publication; local files and checksums remain unverified.
2. **Label semantics.** Inoculation assignment is not equivalent to visible symptom status or severity.
3. **Longitudinal identity.** Pot identity is supported by the archive hierarchy; persistent individual-leaf identity across dates is not established by image-specific pixel coordinates.
4. **Senescence confounding.** The paper explicitly reports difficulty distinguishing natural senescence from disease symptoms.
5. **Small biological sample.** The experiment has 48 pots; image and leaf counts must not be mistaken for independent sample size.
6. **Controlled environment.** The growth-chamber study does not establish performance on field-grown wheat, other cultivars, locations, seasons, or sensors.
7. **Sensor alignment.** VNIR/SWIR wavelength overlap and acquisition correspondence require verification from real headers and sample maps.
8. **Calibration.** Reflectance claims require validation of the Spectralon reference and the dark-current-correction path.
9. **Model selection.** Nested validation reduces tuning leakage, but final claims still need an untouched evaluation or a clearly predeclared analysis plan.

## 7. Priority actions after Day 14

1. Download the three annotation CSVs and verify publisher checksums and local SHA-256.
2. Inspect actual schemas and confirm pot, side, treatment, genotype, date, and DPI mappings.
3. Download one representative VNIR image/header/coordinate set and one SWIR set.
4. Validate wavelength units, cube layout, reflectance reference handling, coordinate indexing, crop offsets, and visual ROI overlays.
5. Generate a small real-data ROI sample and audit it before full extraction.
6. Produce the first verified pot-date table; only then run the predeclared model workflow.
7. Replace this draft's status tables with measured results only after the corresponding artifacts and logs exist.

## 8. Conclusion

TerraSpectra has a documented and testable software architecture for hyperspectral data validation, preprocessing, group-aware classification, sensor comparison, guarded inference, and robustness analysis. The scientific design explicitly treats pot as the conservative validation group and prevents treatment assignment from being misrepresented as symptom status or future disease.

At Day 14, the project is best described as a **research pipeline under data-validation**, not a validated disease-detection or forecasting system. The next decisive milestone is the first verified real-data path from publisher annotation files through a registered HSI/ROI sample to an audited pot-date spectral table.

## References

1. Latchoumane, L. et al. (2025). *Early detection of Zymoseptoria tritici infection on wheat leaves using hyperspectral imaging data*. Data in Brief, 59, 111404. https://doi.org/10.1016/j.dib.2025.111404
2. Latchoumane, L. (2024). *Early detection of septoria infection on wheat leaves using hyperspectral imaging data*. Recherche Data Gouv. https://doi.org/10.57745/WVP0FJ
3. Lowe, A., Harrison, N., & French, A. P. (2017). Hyperspectral image analysis techniques for the detection and classification of the early onset of plant disease and stress. *Plant Methods*, 13, 80. https://doi.org/10.1186/s13007-017-0233-z
4. Thomas, S. et al. (2018). Benefits of hyperspectral imaging for plant disease detection and plant protection: a technical perspective. *Journal of Plant Diseases and Protection*, 125, 5–20. https://doi.org/10.1007/s41348-017-0124-6

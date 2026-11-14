# Day 5 — Exploratory spectral analysis

## Objective

Produce reproducible descriptive summaries and plots from Day 4 per-ROI spectra while respecting the experiment's pot-level treatment assignment. This stage is not a classifier and does not establish forecasting ability.

## Research basis

Latchoumane et al. (2025), *Early detection of Zymoseptoria tritici infection on wheat leaves using hyperspectral imaging data*, describes 1,175 images and 3,326 leaves per modality across 18 dates. Its published analysis first calculated mean spectra per leaf, then summarized infected and non-infected leaves by date. The authors identify the dataset as a basis for infection-status classification and future work on symptom-appearance prediction.

The paper reports VNIR as 411–993 nm (216 bands) and SWIR as 964–2,494 nm (256 bands). Day 4 preserves the wavelength axis per image. Day 5 refuses to compare images if their axes differ; documented resampling is required first.

## Implementation

`scripts/explore_spectra.py`:

- Reads the Day 4 per-leaf ROI spectra table and identifies ordered `band_NNN` columns.
- Optionally joins verified annotation labels through explicit keys; duplicate keys, unmatched rows and missing requested labels are rejected.
- Requires a biological group and acquisition-date field. The default group is `pot_id_candidate` because treatment was assigned at pot level.
- Aggregates ROI rows within each pot-date (and explicit treatment/genotype, if supplied) before class/date summaries. Multiple leaves and both sides do not count as independent biological replicates.
- Computes between-pot means and standard deviations for each class/date/band.
- Reports missingness and flags 1.5-IQR outliers without automatically deleting them.
- Produces date-specific spectral profiles and exploratory PCA on pot-date mean spectra.
- Retains the Day 4 intensity-versus-reflectance warning.

Outputs: `pot_date_spectra.csv`, `roi_quality.csv`, optional `spectral_summary_by_class_date.csv`, `spectral_profiles_by_date/*.png`, optional `pca_pot_date_scores.csv` and `pca_pot_date.png`, plus `eda_report.json`.

## Leakage and interpretation safeguards

1. Leaf ROIs are aggregated to pot-date rows before summaries/PCA; they are not treated as independent samples.
2. Annotation joins are explicit and many-to-one. Treatment/genotype must come from verified annotation fields, not pot-number inference.
3. The pot is the conservative group because treatment was assigned at pot level; both sides and every date for a pot stay together in later model splits.
4. PCA is descriptive only. Its imputer and components are fitted to the EDA table for visualization; they must be re-fitted inside training folds for prediction.
5. Treatment assignment is not a symptom/severity label. Classifying infected-treatment versus control at time t is not a forecast of future symptom onset.
6. Intensity spectra are not called reflectance until the Spectralon reference workflow is validated.
7. Outliers are flagged for review, never silently removed.

## Execution

Without labels (quality control and unlabelled profiles):

```bash
python scripts/explore_spectra.py \
  --spectra-csv data/processed/vnir_leaf_spectra.csv \
  --audit-json data/processed/vnir_roi_audit.json \
  --output-dir reports/eda/vnir
```

With verified labels (example column names only; inspect the actual annotation CSV first):

```bash
python scripts/explore_spectra.py \
  --spectra-csv data/processed/vnir_leaf_spectra.csv \
  --audit-json data/processed/vnir_roi_audit.json \
  --labels-csv data/metadata/VNIR_data.csv \
  --spectrum-keys pot_id_candidate,date_folder_yyyymmdd_candidate \
  --label-keys Pot,AcquisitionDate \
  --class-column Treatment \
  --genotype-column Genotype \
  --output-dir reports/eda/vnir
```

Do not copy example annotation column names without inspecting the actual CSV. If the annotation table does not provide a unique pot-date key, construct a verified mapping rather than joining on pot alone where labels may vary by date.

## Verification status

The script is validated on synthetic data only. No real `.hyspex` image, coordinate file or annotation CSV was available in the execution environment, so no real class/date spectra, PCA plot or dataset finding is claimed. Real EDA remains blocked until the Day 1–4 acquisition and extraction steps are executed in Colab or a local internet-enabled runtime.

## Sources

- Latchoumane et al. (2025), *Data in Brief* 59, 111404. https://doi.org/10.1016/j.dib.2025.111404
- Public dataset record, DOI 10.57745/WVP0FJ. https://doi.org/10.57745/WVP0FJ
- Anderegg et al. (2019), spectral-temporal features for in-field Septoria tritici blotch assessment. https://doi.org/10.3389/fpls.2019.01705

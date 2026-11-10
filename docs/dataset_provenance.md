# Dataset provenance and scientific scope

## Primary dataset

- **Title:** Early detection of septoria infection on wheat leaves using hyperspectral imaging data
- **Dataset author/depositor:** Lorraine Latchoumane (INRAE)
- **Repository:** Recherche Data Gouv, version 1.0
- **Persistent identifier:** [https://doi.org/10.57745/WVP0FJ](https://doi.org/10.57745/WVP0FJ)
- **Data paper:** Latchoumane et al., *Early detection of Zymoseptoria tritici infection on wheat leaves using hyperspectral imaging data*, Data in Brief 59 (2025), 111404. [https://doi.org/10.1016/j.dib.2025.111404](https://doi.org/10.1016/j.dib.2025.111404)
- **Dataset license shown by the repository:** Etalab Open License 2.0 (compatible with CC-BY 2.0). Retain the dataset citation and attribution.

## Experiment and observations reported by the source

The experiment used two durum wheat genotypes grown under controlled growth-chamber conditions. The pathogen is *Zymoseptoria tritici*, which causes Septoria tritici blotch / leaf blotch. Hyperspectral images were acquired on 18 dates spanning one day before inoculation to 20 days after inoculation. The source paper describes non-destructive in-planta imaging of the first ligulated leaf.

| Modality | Sensor / bands | Wavelength range | Images | Leaves |
|---|---|---:|---:|---:|
| VNIR | HySpex VNIR-1800, 216 bands | 411–993 nm | 1,175 | 3,326 |
| SWIR | HySpex SWIR-384, 256 bands | 964–2,494 nm | 1,175 | 3,326 |

For each modality, the paper reports:

| Treatment | Images | Leaves |
|---|---:|---:|
| Infected | 588 | 1,652 |
| Non-infected | 587 | 1,674 |
| Total | 1,175 | 3,326 |

The VNIR and SWIR wavelength ranges overlap from 964 to 993 nm. Treat them as separate sensor modalities until wavelength calibration, band alignment and acquisition correspondence have been checked.

## Public repository structure

The data paper describes three annotation CSVs in the Data annotation folder:

- **Data_description.csv** — dataset description.
- **VNIR_data.csv** — VNIR image/sample and leaf-count information.
- **SWIR_data.csv** — SWIR image/sample and leaf-count information.

The image data are separated into VNIR and SWIR directories with date-specific ZIP archives. The paper describes ENVI hyperspectral data (.hyspex) with header metadata (.hdr), reconstructed JPEGs, and CSV pixel-coordinate files for leaf regions. The source repository page indicates that the full dataset is too large for one-click download and should be downloaded selectively.

The Day 1 downloader retrieves only the small annotation CSVs and saves the Dataverse file inventory, source metadata, checksum results and a local SHA-256 manifest. It intentionally does not download multi-gigabyte image archives.

## What this dataset can and cannot establish

**Supported research directions:**

1. Infection-status classification at a specified observation date.
2. Early / pre-symptomatic detection, if labels and timing identify infected leaves before visible symptoms.
3. Disease progression analysis across acquisition dates.
4. A future-state prediction experiment, but only if stable sample identities and valid temporal targets can be established from the annotations and image hierarchy.

**Forecasting is not yet validated.** Eighteen acquisition dates establish a temporal acquisition design, but do not by themselves prove that the same individual leaf can be linked across dates or that a future disease-state label exists for every predictor observation. Verify the actual identifiers, pot/side hierarchy, genotype, inoculation status, date semantics and repeated-observation pattern before defining a forecast target.

## Leakage and generalisation safeguards

- Never randomly split individual spectra or pixels if they originate from the same leaf or image.
- Use a group split at the strongest available biological unit (leaf, plant/pot, or experimental unit) after the ID hierarchy is confirmed.
- For future-state prediction, train only on earlier observations and evaluate on later dates; keep related biological units grouped across partitions.
- Keep all preprocessing, scaling, wavelength selection and feature selection inside the training fold.
- Report controlled-environment leaf-level performance separately from any claim about field deployment. This dataset is not a field-scale validation set.

## Day 1 validation checklist

- [ ] Fetch dataset metadata from the Dataverse API.
- [ ] Save the file inventory and download the three annotation CSVs.
- [ ] Verify downloaded file sizes and checksums.
- [ ] Record rows, columns, missing values, duplicate rows and candidate identifier/time/label columns.
- [ ] Compare VNIR and SWIR annotation schemas.
- [ ] Manually verify candidate key semantics using Data_description.csv and the data paper.
- [ ] Decide whether repeated leaf-level identity is demonstrable; do not assume it.

## References

1. Latchoumane, L. et al. (2025). *Early detection of Zymoseptoria tritici infection on wheat leaves using hyperspectral imaging data*. Data in Brief, 59, 111404. [https://doi.org/10.1016/j.dib.2025.111404](https://doi.org/10.1016/j.dib.2025.111404)
2. Latchoumane, L. (2024). *Early detection of septoria infection on wheat leaves using hyperspectral imaging data*, Recherche Data Gouv, Version 1.0. [https://doi.org/10.57745/WVP0FJ](https://doi.org/10.57745/WVP0FJ)

# Day 17 — Verified metadata acquisition and schema findings

**Evidence status:** dataset version 1 annotation files downloaded and independently checksum-verified from the GitHub Actions artifact. Schema parsing remediation is in PR #5 and CI is pending.

## 1. Acquisition evidence

GitHub Actions workflow run: [#46154397157](https://github.com/rajarathinam274-stack/TerraSpectra-Hyperspectral-Crop-Disease-Forecasting/actions/runs/46154397157)

- Dataset: Recherche Data Gouv DOI 10.57745/WVP0FJ, version 1.
- The download step completed successfully and uploaded the three annotation CSVs, manifest and inventory.
- The subsequent annotation audit failed because the first implementation read the source tables as UTF-8/comma-delimited; the actual CSVs are semicolon-delimited CP1252 with title/header rows and footnotes.
- The dataset artifact was retrieved and its manifest and file bytes inspected.

## 2. Checksum verification

The artifact manifest reported both the Dataverse-advertised MD5 and the pinned publisher MD5 as verified. The file bytes were independently re-hashed after artifact retrieval.

| File | Bytes | MD5 | SHA-256 |
|---|---:|---|---|
| Data_description.csv | 9,415 | 2efd148e433016da14a3209e6db575df | 525eb83f3415542ea79bda7c8cc86c8aca56a65024a59e159192b0c8c9818d0c |
| VNIR_data.csv | 5,642 | 181f1f7a63b0434210d57841e3d7d7f8 | 20e3e570bc7537632af819be0353f5833ae754308de1f25e89bae6ba28413d99 |
| SWIR_data.csv | 5,640 | 12dc1a89b7f0d648948750247ef488a3 | f55facca363df0948f604d6ca20d192d2f4b2b28f0a29ec94219748256a0aea5 |

## 3. Actual schema findings

### Data_description.csv

- 279 records and 48 pots.
- 279 unique `Pot/Side/Leaf` keys; no duplicate keys.
- 87 pot-side keys have three leaf entries; 9 have two.
- Genotype counts by leaf record: EPO_67 140; EPO_68 139.
- Treatment-assignment counts by leaf record: Infected 139; Non-infected 140.
- Confidence level: 246 level-1; 33 level-2.
- The pot-level allocation table has 12 pots in each genotype/treatment cell.

The `Treatment` field is static inoculation/control assignment. The confidence note is based on visual symptom evaluation, but this table is not time-stamped. It cannot serve as a date-specific symptom trajectory or future outcome table.

### VNIR_data.csv and SWIR_data.csv

After excluding the six trailing footnote rows:

- 48 pot rows.
- 18 DPI values: -1, 0, 4, 5, 6, 7, 8, 10, 11, 12, 13, 14, 15, 16, 17, 18, 19, 20.
- 36 side-count columns per pot.
- Each modality has 1,175 numeric count cells and a sum of 3,326 leaves across the acquisition timeline.
- Each modality has 552 empty cells and one literal `NA` technical-missing cell.

The count matrices differ at 12 pot/DPI/side keys. Ten are numeric count disagreements; two are a numeric count versus a technical-missing cell.

| Pot | DPI | Side | VNIR | SWIR |
|---|---:|---|---:|---:|
| 13 | -1 | G | 2 | 1 |
| 13 | -1 | D | 1 | 2 |
| 25 | -1 | G | 2 | 3 |
| 25 | -1 | D | 3 | 2 |
| 20 | 4 | G | 2 | 3 |
| 20 | 4 | D | 3 | 2 |
| 13 | 7 | G | 2 | 3 |
| 13 | 7 | D | 3 | 2 |
| 20 | 7 | G | 3 | 2 |
| 20 | 7 | D | 2 | 3 |
| 23 | 10 | G | 3 | NA |
| 47 | 10 | G | NA | 3 |

The missing values above refer to the source's literal technical-missing `NA`, not a fabricated count. These count-level differences must be reconciled before matched VNIR/SWIR fusion. They do not establish individual ROI registration.

## 4. Parser remediation

PR #5 adds:
- a CP1252/semicolon parser for the three dataset-specific tables;
- footnote filtering for the count matrices;
- a long pot/DPI/side acquisition-count inventory that preserves blank versus `NA` status;
- a cross-modality count audit that lists mismatches;
- tests for the parsing layout and missing-cell handling.

The PR's software CI is pending. The real-data parser has not yet been executed on the repository's main branch. The next push-to-main acquisition run will produce a fresh schema and inventory artifact.

## 5. Scientific gates

- **Treatment-assignment classification:** static Infected/Non-infected label; assignment known in advance.
- **Observed disease classification:** not established by the count tables; requires date-specific symptom labels linked to image/ROI identity.
- **Future-outcome forecasting:** NO-GO. The CSVs provide acquisition counts and a static leaf-treatment/confidence table, not independently assessed future symptom outcomes with predictor/outcome timestamps.
- **ROI registration and fusion:** NO-GO until actual image archives, ENVI headers and coordinate CSVs are inspected and validated.

No real model metrics, disease-detection results, spectral interpretation or forecasting results are claimed.

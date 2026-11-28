# Day 2 — Annotation semantics and biological sample map

**Status: version-1 metadata CSVs downloaded and checksum-verified; date-specific labels, image identity and ROI registration remain unverified.**

## 1. Source-confirmed experimental hierarchy

The data paper and verified `Data_description.csv` establish 48 pots of durum wheat, two genotypes (EPO_067 and EPO_068), and 12 infected-treatment and 12 non-infected-control pots within each genotype. The leaf table contains 279 unique pot-side-leaf keys, with no duplicate keys. Eighty-seven pot-side records contain three leaf entries and nine contain two.

The archive folder convention is `NUM_SIDE`:
- `NUM`: pot number, 01–48.
- `D`: right side of the pot.
- `G`: left side of the pot.

The archive is date-organized using date-coded folders (YYYYMMDD), with VNIR and SWIR stored separately. Images were acquired non-destructively on the first ligulated leaf when possible. Each image may therefore contain multiple plant leaves; image rows and pixel spectra are not independent biological replicates.

**Leakage-safe grouping decision:** use `pot_id` as the conservative grouping unit for model validation. Both sides (`D` and `G`) and every date from the same pot must remain in one partition. Treatment was assigned at pot level, so splitting only by side, image, leaf ROI or pixel would leak pot-level information.

## 2. Verified annotation schema

The three version-1 CSVs were downloaded from the public Dataverse record and their Dataverse-advertised MD5 and publisher-pinned MD5 checksums both matched. The metadata audit workflow's first parser attempt failed because the tables are semicolon-delimited CP1252 files with introductory rows and footnotes; a dataset-specific parser is being added.

`Data_description.csv`:
- 279 rows; 48 pots; 279 unique `Pot/Side/Leaf` keys; zero duplicate keys.
- `G`: 140 leaf rows; `D`: 139.
- Genotype row counts: EPO_67 140; EPO_68 139.
- Treatment-assignment row counts: Infected 139; Non-infected 140.
- Confidence: 246 level-1; 33 level-2.

The table's static `Treatment` column is Infected/Non-infected. The confidence note describes confidence based on visual symptom evaluation (1 high, 2 low). These fields are not date-specific symptom-status labels: the table has no acquisition timestamp.

The VNIR and SWIR CSVs are pot/date/side acquisition-count matrices, not leaf/image identifiers or spectra:
- 48 pot rows after footnote removal.
- 18 DPI values: -1, 0, 4, 5, 6, 7, 8, 10, 11, 12, 13, 14, 15, 16, 17, 18, 19, 20.
- 36 side-count cells per pot (18 dates × 2 sides).
- Each modality: 1,175 numeric cells and 3,326 total leaf-count entries across acquisition dates.
- Each modality has 552 blank cells (no acquisition) and one literal `NA` (technical malfunction).

The count matrices are mostly aligned, but 12 pot/DPI/side cells differ between modalities: ten numeric count disagreements and two count-versus-technical-missing disagreements. These must be audited before matched-sensor fusion; count-level agreement is not proof of ROI registration.

## 3. Candidate date-to-DPI mapping

The verified count-table headers provide DPI values, not calendar acquisition dates. The data paper and archive folder structure describe 18 acquisitions from -1 through 20 DPI, with no acquisition at 1, 2, 3 or 9 DPI. The calendar date mapping and inoculation timestamp still need verification against the actual image archive/experimental timetable before calendar timestamps are used.

## 4. Treatment labels versus disease outcomes

- `Treatment = Infected` or `Non-infected` is experimental inoculation/control assignment at pot level; it is not proof of visible symptoms at every acquisition date.
- A same-date classifier of treatment assignment is not an observed symptom classifier and is not a future disease forecast.
- The static confidence field is not a timestamped symptom trajectory.
- A date-specific observed disease classifier needs a verified label linked to the actual ROI/image at that acquisition date.
- A genuine future symptom forecast needs an independently assessed future outcome, stable biological identity and a predictor time strictly earlier than the outcome.

## 5. Forecasting feasibility gate

**Not yet passed.** The count tables establish repeated pot-level acquisition counts, but do not establish stable leaf identity across dates or independently assessed future symptom outcomes. Repeated pot IDs and static treatment assignment alone are insufficient.

Proceed with true forecasting only if the downloaded image/annotation material establishes:
1. a stable biological ID repeated across dates;
2. an independently assessed future symptom/severity outcome tied to that ID;
3. a predictor timestamp strictly earlier than the outcome timestamp; and
4. chronological evaluation with biological groups held out.

Otherwise, document a no-go for genuine forecasting and focus on leakage-safe treatment discrimination, descriptive disease progression only where valid symptom labels exist, and spectral QC.

## 6. Metadata parsing and acquisition inventory

The parser remediation PR adds dataset-specific CP1252/semicolon parsing and a long pot/DPI/side count inventory. The inventory is explicitly not an individual leaf/image map. After it is merged, the acquisition workflow will rerun and upload the schema/count audit artifact.

```bash
python scripts/download_metadata.py
python scripts/audit_annotations.py
python scripts/build_sample_map.py
python scripts/inspect_metadata.py
pytest -q
```

The scripts write:
- `data/metadata/annotation_audit.json`
- `data/metadata/sample_map_candidates.csv`
- `data/metadata/sample_map_audit.json`

Raw VNIR/SWIR HSI archives, ENVI headers, binary integrity, ROI coordinate registration, reflectance-reference calibration and real spectra extraction remain pending.

## 7. Source references

1. Latchoumane et al. (2025), *Early detection of Zymoseptoria tritici infection on wheat leaves using hyperspectral imaging data*, Data in Brief 59, 111404. https://doi.org/10.1016/j.dib.2025.111404
2. Latchoumane (2024), Recherche Data Gouv, version 1.0, DOI 10.57745/WVP0FJ. https://doi.org/10.57745/WVP0FJ. The public record lists the three annotation CSVs, their sizes and MD5 checksums, and the Etalab Open License 2.0.

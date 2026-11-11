# Day 2 — Annotation semantics and biological sample map

**Status: source-level design documented; annotation-file verification still pending.**

## 1. Source-confirmed experimental hierarchy

The data paper describes 48 pots of durum wheat, with two genotypes (EPO_067 and EPO_068), 24 pots per genotype. Within each genotype, 12 pots were assigned to the infected treatment and 12 to the non-infected control. Each pot contained six plants arranged as two groups of three on opposite sides.

The archive folder convention is `NUM_SIDE`:
- `NUM`: pot number, 01–48.
- `D`: right side of the pot.
- `G`: left side of the pot.

The archive is date-organized using date-coded folders (YYYYMMDD), with VNIR and SWIR stored separately. Images were acquired non-destructively on the first ligulated leaf when possible. Each image may therefore contain multiple plant leaves; image rows and pixel spectra are not independent biological replicates.

**Leakage-safe grouping decision:** use `pot_id` as the conservative grouping unit for model validation. Both sides (`D` and `G`) and every date from the same pot must remain in one partition. Treatment was assigned at pot level, so splitting only by side, image, leaf ROI or pixel would leak pot-level information.

## 2. Provisional data dictionary

| Concept | Source-supported meaning | Status / modelling rule |
|---|---|---|
| Acquisition date | Date-coded archive folder, YYYYMMDD | Parse from folder/file metadata; verify all 18 dates |
| DPI | Days post inoculation | 18 acquisition dates span -1 to 20 DPI; validate the exact inoculation date before finalizing |
| Pot number (`NUM`) | Pot identifier 01–48 | Strongest known biological grouping key |
| Side (`SIDE`) | D = right, G = left | Nested within pot; never use as independent group |
| `NUM_SIDE` | Pot number plus measured side | Image-location key, not a leaf identifier |
| Genotype | EPO_067 or EPO_068 | Do not map pot numbers to genotypes without an explicit annotation field |
| Treatment | Infected or non-infected control | Assigned at pot level; not a per-leaf severity score |
| Plant identity | Six plants per pot, three per side | A persistent plant ID in the annotation tables has not been verified |
| Leaf identity | First ligulated leaf imaged non-destructively when possible | A stable leaf ID across dates has not been verified |
| Image/sample row | Image/sample information and number of leaves collected per image/day | Acquisition record; not automatically a biological replicate |
| Leaf ROI coordinates | Pixel coordinates delimiting each leaf in an image | The paper describes coordinate CSVs; confirm their file naming and row semantics before extraction |
| Modality | VNIR or SWIR camera | Keep separate until matching image/sample keys are verified |

The paper states that the annotation directory contains a general description CSV and VNIR/SWIR tables describing samples and the number of leaves collected per image each day. The exact column headers and values must be read from the downloaded files; this document deliberately does not invent them.

## 3. Candidate date-to-DPI mapping

The paper reports 18 acquisition dates from one day before inoculation through 20 DPI, with no hyperspectral acquisition at 1, 2, 3 or 9 DPI. The public archive page shows date-coded folders including 20210311 and 20210401. These constraints imply a **candidate** inoculation date of 2021-03-12 and the following daily schedule:

| Candidate date | Candidate DPI |
|---|---:|
| 2021-03-11 | -1 |
| 2021-03-12 | 0 |
| 2021-03-16 to 2021-03-20 | 4 to 8 |
| 2021-03-22 to 2021-04-01 | 10 to 20 |

This is a derived mapping, not a substitute for the actual annotation table. Confirm the full set of 18 archive dates and the inoculation date in `Data_description.csv` / the experimental timetable before using DPI as a model feature or evaluation axis. In particular, never derive DPI from a filename without recording the rule and source.

## 4. Treatment labels versus disease outcomes

The experiment assigned infected and non-infected treatments at the pot level. The paper reports that visible necrosis began around 7 DPI and pycnidia appeared in later infection stages. It also notes that senescence could be confused with disease symptoms, requiring a disease-confidence level.

Therefore:
- `treatment = infected` means inoculated treatment assignment; it does not prove that visible symptoms are present at every date.
- A pre-symptomatic classifier may distinguish inoculated from control pots at an early date, if evaluated on held-out pots.
- This is not automatically a forecast of future disease onset: treatment assignment is already known before the prediction.
- A genuine symptom-onset forecast needs a clearly defined future outcome (for example, first confirmed symptom date or future severity) and a valid identity link for the same biological unit across time.

## 5. Forecasting feasibility gate

**Not yet passed.** The paper confirms repeated date-level acquisition and pot-side folders, but the available source description does not establish persistent plant/leaf IDs in the annotation CSVs. Repeated pot IDs alone can support pot-level longitudinal summaries, but do not establish leaf-level trajectories. A pot's assigned treatment is static, so predicting that treatment at a later date is not a meaningful disease forecast.

Proceed with true forecasting only if the downloaded annotations or per-image files establish:
1. a stable biological ID (plant or leaf) repeated across dates;
2. a future symptom/severity outcome tied to that same ID;
3. a predictor time strictly earlier than the outcome time; and
4. a test design that holds out biological groups and future dates.

Otherwise, document a no-go for genuine forecasting and focus on leakage-safe early infection-status classification and disease-progression description.

## 6. Run the candidate sample-map builder

After downloading the three annotation CSVs:

```bash
python scripts/download_metadata.py
python scripts/audit_annotations.py
python scripts/build_sample_map.py
python scripts/inspect_metadata.py
pytest -q
```

The builder writes:
- `data/metadata/sample_map_candidates.csv`
- `data/metadata/sample_map_audit.json`

It extracts date and `NUM_SIDE` candidates from explicit columns or text tokens, keeps explicitly named genotype/treatment/plant/leaf fields separate, and does not invent missing identifiers. Review the output against `Data_description.csv` and the data paper before modelling.

## 7. Source references

1. Latchoumane et al. (2025), *Early detection of Zymoseptoria tritici infection on wheat leaves using hyperspectral imaging data*, Data in Brief 59, 111404. [https://doi.org/10.1016/j.dib.2025.111404](https://doi.org/10.1016/j.dib.2025.111404)
2. Latchoumane (2024), Recherche Data Gouv, version 1.0, DOI [10.57745/WVP0FJ](https://doi.org/10.57745/WVP0FJ). The public record lists the three annotation CSVs, their sizes and MD5 checksums, and the Etalab Open License 2.0.

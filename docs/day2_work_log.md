# Day 2 work log — 2026-11-11

## Objective

Define the source-supported biological hierarchy, provisional data dictionary, date/DPI interpretation and leakage-safe grouping plan. Add a conservative script to build a candidate sample map once the annotation CSVs are available.

## Research completed

The data paper describes:
- 48 pots, two durum wheat genotypes (EPO_067 and EPO_068), 24 pots per genotype.
- 12 infected and 12 non-infected pots per genotype.
- Six plants per pot, three plants arranged on each of two opposite pot sides.
- Archive folder labels `NUM_SIDE`, with NUM as pot number 01–48 and D/G as right/left side.
- Date-organized VNIR and SWIR image archives, 18 dates from -1 to 20 DPI; no acquisitions at 1, 2, 3 or 9 DPI.
- Non-destructive acquisition of the first ligulated leaf when possible; multiple leaves may occur in an image.
- Per-image leaf pixel-coordinate CSVs, with vertical coordinate in the first column and horizontal coordinate in the second.

The dataset page lists annotation files and public checksums:
- `Data_description.csv`: 9.2 KB, MD5 `2efd148e433016da14a3209e6db575df`.
- `SWIR_data.csv`: 5.5 KB, MD5 `12dc1a89b7f0d648948750247ef488a3`.
- `VNIR_data.csv`: 5.5 KB, MD5 `181f1f7a63b0434210d57841e3d7d7f8`.

## Scientific decisions

- Conservative validation grouping unit: pot ID. Keep both pot sides and all dates for one pot in the same partition because treatment assignment was at pot level.
- Pot-side and image identifiers are not leaf identifiers.
- The candidate inoculation date is 2021-03-12, inferred from date-coded archive examples (2021-03-11 at -1 DPI and 2021-04-01 at 20 DPI) plus the paper's stated acquisition window and skipped dates. This must be confirmed against the actual metadata before DPI is locked.
- A treatment classifier is not a disease-onset forecast. True forecasting requires a future symptom/severity outcome linked to the same biological unit over time.

## Implementation

- Added `scripts/build_sample_map.py` to extract candidate date and pot-side keys conservatively from annotation columns/text.
- Added tests for date token parsing, NUM_SIDE parsing and separation of explicit labels from inferred path tokens.
- Added a provisional data dictionary, sample hierarchy, date/DPI caveat, leakage policy and forecasting gate.
- Updated README and roadmap to expose the Day 2 workflow and its remaining validation condition.

## Verification

- Three focused synthetic-fixture tests passed locally (`3 passed`).
- Python syntax/import validation was performed in the isolated test environment.
- The GitHub repository state was inspected before changes; Day 1 files and the latest commit were fetched from the requested repository.
- The execution container cannot resolve `entrepot.recherche.data.gouv.fr` (DNS resolution failure). Therefore the three annotation CSVs were not downloaded or read in this run.
- No exact CSV column names, row-level pot/genotype mapping, persistent plant/leaf identity, model metrics or forecasting result are claimed.

## Day 2 status

**Partially complete.** The source-supported pot-level hierarchy and leakage-safe grouping strategy are documented and implemented as a candidate-map workflow. The exit condition remains pending until the actual CSVs are downloaded and their columns/rows are checked.

## Next action

Run the Day 1 notebook or the terminal workflow in Google Colab/local Jupyter with internet access. Then run `python scripts/build_sample_map.py` and inspect `sample_map_audit.json` plus `sample_map_candidates.csv`. Use the actual annotation columns to finalize the data dictionary and decide whether stable longitudinal leaf/plant IDs exist.

# Day 14 work log — 2026-11-23

## Roadmap and repository audit

- Reviewed `docs/15_day_roadmap.md`; Day 14 deliverable is the technical report, figures, presentation, and demo script, with all claims constrained to verified experiments.
- Verified repository: `rajarathinam274-stack/TerraSpectra-Hyperspectral-Crop-Disease-Forecasting`.
- Verified visibility: public; default branch: `main`; linked account has push permission.
- Verified main HEAD before Day 14 documentation: `ba277f5aa7bacdf218b08c9233a6de5a857382fd`.
- Verified Day 12 workflow run `44920198240`: completed successfully; focused inference tests, compilation, and CLI help passed.
- Verified Day 13 workflow run `45039651094`: completed successfully; six focused synthetic tests, compilation, and CLI help passed.

## Day 14 deliverables

- Added `reports/terra_spectra_technical_report_draft.md`: a methods-and-status report that clearly states no real-data metrics are available.
- Added `docs/day14_presentation.md`: a 12-slide outline with speaker notes and evidence-qualified claims.
- Added `docs/day14_demo_script.md`: a reproducible 5–6 minute demonstration sequence with explicit gates for metadata, HSI headers, ROI registration, modelling, and inference.
- This work log records the verification scope and blockers.

## Research verification

The primary paper was checked at https://pmc.ncbi.nlm.nih.gov/articles/PMC11919375/ and the dataset DOI at https://doi.org/10.57745/WVP0FJ.

The paper reports:
- 48 pots across two durum-wheat genotypes; 12 infected-treatment and 12 control pots per genotype;
- 18 acquisition dates from -1 to 20 DPI, with no HSI acquisition at 1, 2, 3, or 9 DPI;
- 1,175 images and 3,326 leaves per modality;
- VNIR 216 bands (411–993 nm) and SWIR 256 bands (964–2,494 nm);
- visual symptom monitoring, necrosis beginning around 7 DPI, pycnidia in later stages, pathologist confirmation at experiment end, and senescence as a symptom-assessment confound.

The paper describes annotation CSVs as sample information and leaf counts per image/day. The actual CSV contents have not been downloaded and inspected in this run. No complete per-pot/per-date symptom outcome table has been verified.

## Scientific status

- Day 14 documentation is a non-empirical draft.
- No real-data accuracy, macro-F1, confusion matrix, feature importance, earliest symptom-detection date, or forecast result is claimed.
- Day 11 forecasting feasibility remains NO-GO until stable biological IDs and independently assessed future symptom/severity labels with timestamps are verified.
- Controlled growth-chamber data must not be represented as field validation.
- No real data were downloaded or processed during this documentation run.

## Next action — Day 15

Complete reproducibility and handover:
1. Verify the final GitHub tree and documentation links.
2. Check setup instructions and focused tests.
3. Add an explicit dataset acquisition/checksum status and list unresolved real-data gates.
4. Produce the final handover/release notes without marking scientific validation complete.

## Day 14 documentation commits

- `d5b3595859cc97907694c9a81c0f9fa50e33dc35` — `reports/terra_spectra_technical_report_draft.md`
- `41f3d0aa9915eabc97b5f3ddc45c07dde7bc365a` — `docs/day14_presentation.md`
- `7e7dad506b94b9f721752943cd5952ac4b367405` — `docs/day14_demo_script.md`

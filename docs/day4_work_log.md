# Day 4 work log — 2026-11-13

## Objective

Implement reproducible per-leaf ROI extraction from ENVI hyperspectral cubes using the dataset's per-leaf pixel-coordinate CSVs.

## Research findings

The 2025 Data in Brief paper and Figure 1 confirm:
- Archive hierarchy includes acquisition-date folders, pot-side folders and per-image files.
- A sample image folder contains a matching `.hdr`, `.hyspex`, `.jpg`, and coordinate files named like `26_G_leaf1.csv`, `26_G_leaf2.csv`, `26_G_leaf3.csv`.
- Coordinate CSV column 1 is vertical row/y; column 2 is horizontal column/x.
- The published analysis reframed images to the inoculated area (VNIR 1370×781, SWIR 420×306), extracted leaf pixels and averaged spectra per leaf.
- Original acquisition dimensions are reported separately (VNIR 1370×1024 typical, SWIR 420×320).

## Implementation

Added `scripts/extract_leaf_spectra.py`:
- Recursively discovers ENVI headers and matching HySpex binaries.
- Locates adjacent per-leaf coordinate CSV files.
- Requires explicit coordinate base (0 or 1) and coordinate frame.
- Requires explicit row/column crop offsets for reframed-image coordinates.
- Deduplicates coordinate pairs, audits nonnumeric rows and rejects out-of-bounds coordinates.
- Extracts only selected ROI pixels from a BIP memory map and computes per-band arithmetic mean.
- Writes one row per leaf ROI with provenance columns and band columns, plus a JSON extraction audit.
- Marks output as dark-current-corrected intensity, not reflectance.
- Does not infer treatment/genotype or persistent leaf identity.

Added `tests/test_extract_leaf_spectra.py` with seven unit tests and one mocked batch smoke test.

Added `docs/day4_roi_extraction.md`.

## Verification

- Focused synthetic tests: 8 passed.
- Python compileall for the new script/tests: passed.
- CLI `--help`: passed.
- Mocked end-to-end directory discovery and CSV output: passed.
- Real archive/coordinate/image execution: not run. No actual `.hdr`, `.hyspex`, or coordinate CSV is present in this execution environment.
- No real spectra, reflectance products, model metrics or forecasting results are claimed.

## Scientific risks controlled

- CSV indexing base is required explicitly; MATLAB usage is not assumed to prove 1-based exported coordinates.
- Coordinate frame is required explicitly because the paper distinguishes acquisition image dimensions from reframed analysis dimensions.
- Crop offsets are mandatory for reframed-frame coordinates.
- No out-of-bounds clipping.
- A leaf ID is scoped to one image; it is not treated as persistent over dates.
- Pot-level grouping remains the conservative split because treatment assignment was by pot.
- Output intensity is not mislabeled as reflectance.

## Day 4 status

**Implementation complete; scientific exit condition partially complete.** The code and synthetic tests are ready. The exit condition requires a real sample image, header and coordinate CSV to verify the indexing convention, coordinate frame/crop offsets and overlay registration.

## Next action

In Colab or a local runtime, download/extract one small VNIR or SWIR date archive, inspect one image/coordinate trio, determine the coordinate convention and crop transform from the actual data, and run `--max-images 1`. Visually overlay the coordinates on the matching JPG before running the full archive.

# Day 4 — Leaf ROI extraction and spectral feature generation

**Status: extraction implementation and synthetic tests complete; real archive validation pending.**

## Source-backed dataset structure

Latchoumane et al. (2025) describe a directory tree with date folders (`YYYYMMDD`), pot-side folders (`NUM_SIDE`), one ENVI `.hdr`/`.hyspex` pair per image, reconstructed `.jpg` previews, and one coordinate CSV per leaf. Figure 1 shows an example directory containing `26_G.hdr`, `26_G.hyspex`, `26_G_leaf1.csv`, `26_G_leaf2.csv`, `26_G_leaf3.csv`, and `26_G.jpg`.

The paper specifies that coordinate CSV column 1 is the vertical pixel coordinate (row/y) and column 2 is the horizontal pixel coordinate (column/x). It also reports that its analysis reframed images to the inoculated region (1370×781 for VNIR and 420×306 for SWIR), then extracted inoculated-leaf pixels and calculated the average spectrum for each leaf.

Source: https://pmc.ncbi.nlm.nih.gov/articles/PMC11919375/

## Implementation

- `scripts/extract_leaf_spectra.py` recursively discovers `.hdr` files below a modality root.
- For each header, it pairs the `.hyspex` file and adjacent `<image_stem>_leaf*.csv` coordinate files.
- It uses `scripts/hsi_io.py` to open the ENVI cube as a BIP memory map. Only ROI pixel spectra are materialized.
- It reads the first two CSV columns as `(row, column)`, maps them to zero-based source-cube indices, removes duplicate coordinates and calculates the per-band arithmetic mean, matching the paper's described leaf average.
- It writes one row per coordinate-defined leaf ROI, with `band_000` ... `band_NNN` columns, and a JSON audit with coordinate counts, finite-value fraction, path-derived date/pot-side candidates, per-image native wavelength arrays, recognized nm conversions and failures.
- Treatment and genotype are deliberately not inferred from pot number. They must be joined from verified annotation tables.
- `leaf_id_within_image` is not treated as a persistent longitudinal leaf ID.
- Spectra are labelled `dark_current_corrected_intensity_not_reflectance`. Day 3's white-reference uncertainty remains unresolved; this script does not silently call raw intensity reflectance.

## Coordinate safety gates

The source paper establishes coordinate order but the actual archive CSVs and binary headers have not yet been inspected in this runtime. Therefore the script requires explicit declarations:

1. `--coordinate-base 0` or `--coordinate-base 1`. The source article says MATLAB R2021a was used for analysis, but this alone is not sufficient proof of the coordinate export's indexing convention. Inspect actual coordinate extrema and the producing workflow; do not guess.
2. `--coordinate-frame source_image` when coordinates refer directly to the binary cube, or `--coordinate-frame reframed_image` when coordinates refer to the cropped/reframed image.
3. For `reframed_image`, both `--row-offset` and `--col-offset` are mandatory. They translate crop-frame coordinates into the original source-cube coordinate system. Never infer crop offsets from the target dimensions.
4. Coordinates outside the cube raise an error. The extractor never clips or silently drops out-of-bounds pixels.
5. Non-numeric/header rows are audited. Duplicate pixels are deduplicated and counted.

The paper's acquisition dimensions and its analysis-frame dimensions differ. This is why coordinate-frame and crop-offset declarations are mandatory rather than assuming that coordinates are already in source-image space.

## Run

First extract the relevant modality archive so its hierarchy is available locally. Then inspect a sample header and coordinate file, establish the indexing convention and coordinate frame, and run a one-image smoke test.

Example only — use `--coordinate-base 0` or `1` only after checking the source convention:

    python scripts/inspect_hsi.py /path/to/VNIR/20210311/26_G/26_G.hdr --image /path/to/VNIR/20210311/26_G/26_G.hyspex --modality VNIR

    python scripts/extract_leaf_spectra.py \
      --root /path/to/VNIR \
      --modality VNIR \
      --coordinate-base 0 \
      --coordinate-frame source_image \
      --output data/processed/vnir_leaf_spectra.csv \
      --audit data/processed/vnir_roi_audit.json \
      --max-images 1

For coordinates in a cropped frame, replace `source_image` with `reframed_image` and supply verified offsets:

    --row-offset <verified_crop_top> --col-offset <verified_crop_left>

Run the full modality only after the smoke test has been visually checked against the JPG preview and the coordinate overlay.

## Tests and verification

`tests/test_extract_leaf_spectra.py` contains synthetic tests for:
- mean spectrum calculation from row/column coordinates;
- explicit one-based to zero-based conversion;
- CSV header/non-numeric row audit and duplicate-coordinate handling;
- out-of-bounds rejection;
- non-integer coordinate rejection;
- explicit crop-offset mapping;
- batch discovery with a mocked ENVI reader and path provenance.

Synthetic tests validate indexing and aggregation logic only. They do not validate the real dataset's CSV schema, indexing convention, crop offsets, pixel registration, or reflectance calibration.

## Scientific interpretation and leakage control

Each output row is a leaf ROI in one image. It is not automatically an independent plant, pot, or longitudinal leaf observation. For evaluation, group all rows by the verified pot ID, keeping both pot sides and all dates in one partition, because inoculation was assigned at pot level. A date-specific classification result is not a future disease forecast. Future-state forecasting still requires a stable biological identity and a future symptom/severity target.

## References

Latchoumane et al. (2025). *Early detection of Zymoseptoria tritici infection on wheat leaves using hyperspectral imaging data*. Data in Brief 59, 111404. https://doi.org/10.1016/j.dib.2025.111404

Dataset: Recherche Data Gouv, DOI https://doi.org/10.57745/WVP0FJ

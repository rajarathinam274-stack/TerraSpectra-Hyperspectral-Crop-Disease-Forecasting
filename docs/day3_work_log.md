# Day 3 work log — 2026-11-12

## Objective

Implement ENVI ingestion and header validation for the dataset's .hyspex/.hdr pairs, define a reflectance-calibration plan, and add unit tests without pretending that real image data have been processed.

## Research findings

Latchoumane et al. (2025), Data in Brief 59, 111404, specifies:
- Raw image data are .hyspex files paired with ENVI .hdr metadata.
- Per-image leaf pixel-coordinate CSVs and reconstructed JPEGs are also included.
- VNIR: HySpex VNIR-1800, 216 bands, 411–993 nm; typical 1370 × 1024 resolution, with a larger final-date acquisition.
- SWIR: HySpex SWIR-384, 256 bands, 964–2494 nm; 420 × 320 resolution.
- A Spectralon SRS99 standard was used for reflectance normalization.
- The paper gives R = (I - Id) / (I0 - Id) and explicitly says .hyspex files already contain dark-current-corrected intensity.

## Scientific and implementation decisions

- Added separate calibration functions for genuinely raw sample/white/dark arrays and for the published dark-current-corrected .hyspex path.
- The published path divides corrected sample intensity by corrected white-reference intensity; it does not subtract dark current a second time.
- A certified Spectralon reflectance curve can be supplied and wavelength-aligned. Otherwise, the unity-reference assumption must be documented.
- No white-reference ROI is guessed. The actual archive/reference acquisition must be inspected before calibrated reflectance is claimed.
- ENVI data are opened through Spectral Python lazily and as a memory map to avoid reading full scenes into RAM.
- Header wavelength units are converted only when recognized. Missing or ambiguous units are reported rather than assumed to be nm.
- VNIR/SWIR paper specifications are comparison checks, never used to force a reshape or overwrite actual header metadata.
- Reflectance is not clipped to [0, 1]; QA statistics expose out-of-range values for investigation.

## Files added

- scripts/hsi_io.py
- scripts/inspect_hsi.py
- tests/test_hsi_io.py
- docs/day3_hsi_ingestion_calibration.md

## Verification

- Ten synthetic unit tests passed locally (10 passed).
- Python compileall passed for scripts and tests.
- The header-inspection CLI help output ran successfully.
- The runner could not install Spectral Python because external package-index DNS resolution failed.
- The dataset host is not reachable from the execution environment due DNS failure; no real .hdr/.hyspex file was inspected and no reflectance cube was produced.

## Day 3 status

**Partially complete.** The ingestion/calibration implementation and synthetic arithmetic tests exist. The roadmap exit condition is not complete until a real header confirms wavelengths, units, dtype, interleave, byte order, dimensions and the white-reference workflow.

## Next action

In Google Colab or a local internet-enabled runtime, download/extract one sample image pair from the public dataset, install requirements, and run scripts/inspect_hsi.py with the correct modality. Identify the Spectralon reference pixels/acquisition and verify whether the reference is dark-current corrected before running reflectance calibration. Do not begin model training until Day 4 leaf ROI coordinate semantics are validated.

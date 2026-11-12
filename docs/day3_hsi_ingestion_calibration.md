# Day 3 — HSI ingestion and reflectance calibration

**Status: implementation scaffold and synthetic unit tests complete; real archive validation pending.**

## Source-backed file and sensor facts

The dataset paper states that the archive stores raw hyperspectral images as .hyspex binaries with matching ENVI .hdr files, reconstructed JPEGs, and per-image leaf-pixel coordinate CSVs. The VNIR camera is HySpex VNIR-1800 (216 bands, 411–993 nm; typical image 1370 × 1024, with a larger final-date resolution). The SWIR camera is HySpex SWIR-384 (256 bands, 964–2494 nm; 420 × 320 pixels). The archive is separated by modality and acquisition date.

The paper states that a Spectralon SRS99 standard was used as a reflectance reference and gives:

    R(lambda) = (I(lambda) - Id(lambda)) / (I0(lambda) - Id(lambda))

It further states that .hyspex files directly contain intensity corrected for dark current. Accordingly, the implementation has two distinct paths:

1. reflectance_from_raw(sample, white, dark) for genuinely uncorrected sample and reference data.
2. reflectance_from_dark_corrected(sample, white_dark_corrected) for the published .hyspex path; this does not subtract dark current again.

If a certified wavelength-dependent reflectance curve for the Spectralon standard is supplied, both paths can multiply by it. If no certified curve is available, the default ratio assumes unity reference reflectance, matching the paper's normalized ratio convention. Confirm how the reference panel is represented in the downloaded image(s) and headers before using either path on real files.

## Implementation

- scripts/hsi_io.py: lazy Spectral Python ENVI reader, metadata extraction, wavelength-unit conversion, memory-mapped cube opening, dark-corrected and raw reflectance functions, reflectance diagnostics and sensor-profile comparison.
- scripts/inspect_hsi.py: command-line header inspection and JSON report.
- tests/test_hsi_io.py: synthetic tests for both calibration equations, row-wise and band-wise reference broadcasting, invalid denominators, wavelength conversion, sensor-profile checks and no silent clipping.

The reader uses a memory map to avoid loading large cubes into RAM. It reports rows/columns/bands, dtype, interleave, byte order, header offset, wavelength metadata, binary file size and the minimum byte count implied by the header. It rejects a wavelength-count/band-count mismatch and does not assume that missing wavelength units mean nanometres. The paper-reported VNIR/SWIR profiles are comparison targets only; observed header metadata is never overwritten.

## Run

    pip install -r requirements.txt
    python scripts/inspect_hsi.py /path/to/image.hdr --image /path/to/image.hyspex --modality VNIR --output reports/image_header.json
    pytest -q tests/test_hsi_io.py

Use --modality SWIR for SWIR files.

## Calibration quality gates before real reflectance extraction

1. Verify the actual .hdr wavelength array and unit for each modality; compare observed ranges and band counts with the paper, but do not overwrite header metadata with expected values.
2. Confirm ENVI shape, dtype, interleave, byte order, header offset and binary byte size.
3. Identify the Spectralon reference panel in the image or the corresponding reference acquisition. Confirm whether reference intensities are dark-current corrected in the same way as sample pixels.
4. Do not subtract dark current twice from the published .hyspex data.
5. If a certified reflectance curve is available, use its wavelength-aligned values; otherwise document the unity-reference assumption.
6. Do not clip reflectance to [0, 1] silently. Record finite fraction, extrema and out-of-range fraction for QA; investigate saturation, shadow, bad bands or reference mismatch.
7. Apply bad-band removal only from documented sensor/header metadata or an explicitly justified QA rule, and record removed wavelengths.
8. Keep raw files immutable and out of Git. Store header reports, checksums and processing configuration as provenance.

## Important limitation

The annotation CSVs and .hyspex archives have not been downloaded in the current execution environment. Therefore the code has not yet been tested against a real HySpex header or cube. Synthetic tests validate calibration arithmetic and shape handling only. Spectral Python could not be installed in this runner because external package-index DNS resolution failed; it remains listed in requirements.txt.

## References

Latchoumane et al. (2025), *Early detection of Zymoseptoria tritici infection on wheat leaves using hyperspectral imaging data*, Data in Brief 59, 111404. https://doi.org/10.1016/j.dib.2025.111404. The paper specifies .hyspex + .hdr, VNIR/SWIR sensor characteristics, Spectralon SRS99 reference and dark-current-corrected intensity.

Dataset: Recherche Data Gouv, DOI https://doi.org/10.57745/WVP0FJ.

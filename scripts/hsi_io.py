"""ENVI hyperspectral I/O, header validation and reflectance calibration.

Spectral Python is imported lazily so calibration helpers can be tested
independently. Raw cubes are opened as memory maps to limit RAM use.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

import numpy as np


class HSIValidationError(ValueError):
    """Raised when an ENVI cube or its metadata fails validation."""


def _spectral_envi():
    try:
        from spectral.io import envi
    except ImportError as exc:
        raise RuntimeError(
            "Spectral Python is required for ENVI reading. Install it with pip install spectral."
        ) from exc
    return envi


def wavelength_values_to_nm(values: Any, units: str | None) -> np.ndarray | None:
    """Convert recognized wavelength units to nm; return None if ambiguous."""
    if values is None or units is None:
        return None
    try:
        wavelengths = np.asarray(values, dtype=np.float64).reshape(-1)
    except (TypeError, ValueError):
        return None
    unit = str(units).strip().lower().replace("_", " ")
    unit = " ".join(unit.split())
    if unit in {"nm", "nanometer", "nanometers", "nanometre", "nanometres"}:
        factor = 1.0
    elif unit in {"um", "µm", "micron", "microns", "micrometer", "micrometers", "micrometre", "micrometres"}:
        factor = 1000.0
    elif unit in {"m", "meter", "meters", "metre", "metres"}:
        factor = 1e9
    elif unit in {"cm-1", "cm^-1", "1/cm", "wavenumber"}:
        if np.any(wavelengths <= 0):
            raise HSIValidationError("Wavenumbers must be positive to convert to nm.")
        return 1e7 / wavelengths
    else:
        return None
    return wavelengths * factor


def inspect_envi_header(header_path: str | Path, image_path: str | Path | None = None) -> dict:
    """Open an ENVI header and return validated metadata without loading cube data."""
    header_path = Path(header_path)
    if not header_path.is_file():
        raise FileNotFoundError(f"ENVI header not found: {header_path}")
    if image_path is None:
        candidate = header_path.with_suffix(".hyspex")
        if not candidate.is_file():
            raise FileNotFoundError(
                f"Could not infer the binary image beside {header_path}; pass --image explicitly."
            )
        image_path = candidate
    image_path = Path(image_path)
    if not image_path.is_file():
        raise FileNotFoundError(f"Hyperspectral binary not found: {image_path}")

    envi = _spectral_envi()
    spy_image = envi.open(str(header_path), str(image_path))
    metadata = dict(spy_image.metadata)
    shape = tuple(int(v) for v in spy_image.shape)
    if len(shape) != 3:
        raise HSIValidationError(f"Expected a 3D ENVI cube (rows, columns, bands), got {shape}")
    rows, columns, bands = shape

    wavelengths = metadata.get("wavelength")
    wavelength_units = metadata.get("wavelength units") or metadata.get("wavelength_units")
    wavelength_nm = wavelength_values_to_nm(wavelengths, wavelength_units)
    wavelength_count = None if wavelengths is None else len(wavelengths)
    if wavelength_count is not None and wavelength_count != bands:
        raise HSIValidationError(
            f"Header has {wavelength_count} wavelength entries but cube has {bands} bands."
        )
    if wavelength_nm is not None and not np.all(np.isfinite(wavelength_nm)):
        raise HSIValidationError("Wavelength metadata contains non-finite values.")

    file_info = image_path.stat()
    dtype = np.dtype(spy_image.dtype)
    header_offset = int(metadata.get("header offset", 0) or 0)
    expected_minimum_bytes = header_offset + rows * columns * bands * dtype.itemsize
    return {
        "header_path": str(header_path),
        "image_path": str(image_path),
        "shape_rows_columns_bands": [rows, columns, bands],
        "dtype": str(dtype),
        "dtype_itemsize_bytes": int(dtype.itemsize),
        "interleave": metadata.get("interleave"),
        "byte_order": metadata.get("byte order"),
        "header_offset": header_offset,
        "wavelength_units": wavelength_units,
        "wavelengths_native": None if wavelengths is None else [float(v) for v in wavelengths],
        "wavelengths_nm": None if wavelength_nm is None else wavelength_nm.tolist(),
        "wavelength_conversion_status": (
            "converted_to_nm" if wavelength_nm is not None else "unknown_or_missing_units"
        ),
        "binary_size_bytes": file_info.st_size,
        "expected_minimum_binary_size_bytes": expected_minimum_bytes,
        "binary_size_at_least_header_requirement": bool(file_info.st_size >= expected_minimum_bytes),
        "metadata": metadata,
    }


def open_envi_memmap(header_path: str | Path, image_path: str | Path | None = None,
                     interleave: str | None = None):
    """Return (SpyFile, memory map); None preserves source interleave."""
    header_path = Path(header_path)
    if image_path is None:
        image_path = header_path.with_suffix(".hyspex")
    image_path = Path(image_path)
    if not header_path.is_file() or not image_path.is_file():
        raise FileNotFoundError(f"Missing ENVI pair: {header_path}, {image_path}")
    envi = _spectral_envi()
    spy_image = envi.open(str(header_path), str(image_path))
    cube = spy_image.open_memmap(interleave=interleave)
    if cube.ndim != 3:
        raise HSIValidationError(f"Expected 3D cube, got shape {cube.shape}")
    return spy_image, cube


def _broadcast_reference(reference: Any, target_shape: tuple[int, ...], name: str) -> np.ndarray:
    ref = np.asarray(reference, dtype=np.float32)
    bands = target_shape[-1]
    if ref.ndim == 0:
        return np.broadcast_to(ref, target_shape)
    if ref.ndim == 1:
        if ref.shape[0] != bands:
            raise HSIValidationError(f"{name} spectrum has {ref.shape[0]} bands; expected {bands}.")
        ref = ref.reshape((1,) * (len(target_shape) - 1) + (bands,))
    elif ref.ndim == 2 and len(target_shape) == 3 and ref.shape == (target_shape[0], bands):
        ref = ref[:, np.newaxis, :]
    try:
        return np.broadcast_to(ref, target_shape)
    except ValueError as exc:
        raise HSIValidationError(
            f"{name} shape {ref.shape} cannot broadcast to sample shape {target_shape}."
        ) from exc


def reflectance_from_raw(sample: Any, white_reference: Any, dark_reference: Any,
                         white_reflectance: Any | None = None,
                         denominator_epsilon: float = 1e-8) -> np.ndarray:
    """Calibrate uncorrected intensity using (sample-dark)/(white-dark)."""
    sample_arr = np.asarray(sample, dtype=np.float32)
    if sample_arr.ndim < 2:
        raise HSIValidationError("Sample data must have spatial/pixel dimensions and a band axis.")
    white = _broadcast_reference(white_reference, sample_arr.shape, "white_reference")
    dark = _broadcast_reference(dark_reference, sample_arr.shape, "dark_reference")
    numerator = sample_arr - dark
    denominator = white - dark
    output = np.full(sample_arr.shape, np.nan, dtype=np.float32)
    valid = (
        np.isfinite(numerator) & np.isfinite(denominator)
        & (denominator > denominator_epsilon)
    )
    np.divide(numerator, denominator, out=output, where=valid)
    if white_reflectance is not None:
        factor = _broadcast_reference(white_reflectance, sample_arr.shape, "white_reflectance_curve")
        if not np.all(np.isfinite(factor)) or np.any(factor <= 0):
            raise HSIValidationError("White-reference reflectance values must be finite and positive.")
        output *= factor
    return output


def reflectance_from_dark_corrected(sample: Any, white_reference_dark_corrected: Any,
                                    white_reflectance: Any | None = None,
                                    denominator_epsilon: float = 1e-8) -> np.ndarray:
    """Normalize dark-current-corrected sample intensity by corrected white.

    Use this path for the published .hyspex files. Do not subtract dark current again.
    """
    sample_arr = np.asarray(sample, dtype=np.float32)
    if sample_arr.ndim < 2:
        raise HSIValidationError("Sample data must have spatial/pixel dimensions and a band axis.")
    white = _broadcast_reference(
        white_reference_dark_corrected, sample_arr.shape, "white_reference_dark_corrected"
    )
    output = np.full(sample_arr.shape, np.nan, dtype=np.float32)
    valid = np.isfinite(sample_arr) & np.isfinite(white) & (white > denominator_epsilon)
    np.divide(sample_arr, white, out=output, where=valid)
    if white_reflectance is not None:
        factor = _broadcast_reference(white_reflectance, sample_arr.shape, "white_reflectance_curve")
        if not np.all(np.isfinite(factor)) or np.any(factor <= 0):
            raise HSIValidationError("White-reference reflectance values must be finite and positive.")
        output *= factor
    return output


SENSOR_PROFILES = {
    "VNIR": {"expected_bands": 216, "expected_wavelength_range_nm": [411.0, 993.0]},
    "SWIR": {"expected_bands": 256, "expected_wavelength_range_nm": [964.0, 2494.0]},
}


def compare_sensor_profile(report: dict, modality: str) -> dict:
    """Compare header values with paper-reported specifications; never overwrite them."""
    modality = modality.upper()
    if modality not in SENSOR_PROFILES:
        raise HSIValidationError(f"Unknown modality {modality!r}; expected VNIR or SWIR.")
    expected = SENSOR_PROFILES[modality]
    observed_shape = report.get("shape_rows_columns_bands") or []
    observed_bands = observed_shape[2] if len(observed_shape) == 3 else None
    wavelengths = report.get("wavelengths_nm")
    observed_range = None
    if wavelengths:
        observed_range = [float(np.nanmin(wavelengths)), float(np.nanmax(wavelengths))]
    warnings = []
    if observed_bands != expected["expected_bands"]:
        warnings.append(
            f"Band-count mismatch: expected {expected['expected_bands']} from paper, "
            f"observed {observed_bands}. Inspect header; do not force a reshape."
        )
    if observed_range is None:
        warnings.append("Wavelength units missing or unrecognized; cannot compare wavelength range.")
    else:
        low, high = expected["expected_wavelength_range_nm"]
        if not (
            low - 10 <= observed_range[0] <= low + 10
            and high - 10 <= observed_range[1] <= high + 10
        ):
            warnings.append(
                f"Wavelength range differs from paper-reported {low:g}-{high:g} nm; "
                f"observed {observed_range[0]:g}-{observed_range[1]:g} nm."
            )
    return {
        "modality": modality,
        "paper_reference_profile": expected,
        "observed_bands": observed_bands,
        "observed_wavelength_range_nm": observed_range,
        "warnings": warnings,
        "status": "match" if not warnings else "review_required",
    }


def summarize_reflectance(cube: Any) -> dict:
    """Return finite/range diagnostics without clipping reflectance."""
    arr = np.asarray(cube)
    finite = np.isfinite(arr)
    if not finite.any():
        return {
            "shape": list(arr.shape), "finite_fraction": 0.0,
            "min": None, "max": None, "mean": None,
            "outside_zero_one_fraction": None,
        }
    values = arr[finite]
    return {
        "shape": list(arr.shape),
        "finite_fraction": float(finite.mean()),
        "min": float(values.min()),
        "max": float(values.max()),
        "mean": float(values.mean()),
        "outside_zero_one_fraction": float(np.mean((values < 0) | (values > 1))),
    }

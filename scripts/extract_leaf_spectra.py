"""Extract one mean spectrum per annotated wheat-leaf ROI from ENVI cubes.

Coordinate CSVs: first column is vertical row (y), second is horizontal column (x).
Index base and coordinate frame are mandatory declarations; crop offsets are never guessed.
"""
from __future__ import annotations

import argparse
import json
import re
import warnings
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

try:
    from .hsi_io import open_envi_memmap, wavelength_values_to_nm
except ImportError:
    from hsi_io import open_envi_memmap, wavelength_values_to_nm

DATE_RE = re.compile(r"^(20\d{6})$")
POT_SIDE_RE = re.compile(r"^(\d{1,2})_([DG])$", re.IGNORECASE)


class ROIValidationError(ValueError):
    """Raised when ROI coordinates cannot be safely mapped to an image cube."""


def load_leaf_coordinates(csv_path, coordinate_base, row_offset=0, col_offset=0):
    """Read first two CSV columns as (row, column), map to zero-based cube coordinates."""
    if coordinate_base not in (0, 1):
        raise ROIValidationError("coordinate_base must be explicitly 0 or 1.")
    path = Path(csv_path)
    if not path.is_file():
        raise FileNotFoundError(path)
    try:
        frame = pd.read_csv(path, header=None, sep=None, engine="python")
    except Exception as exc:
        raise ROIValidationError(f"Could not parse {path}: {exc}") from exc
    if frame.shape[1] < 2:
        raise ROIValidationError(f"Expected at least two columns (vertical y, horizontal x), got {frame.shape[1]}.")
    numeric = frame.iloc[:, :2].apply(pd.to_numeric, errors="coerce").to_numpy(dtype=np.float64)
    finite = np.isfinite(numeric).all(axis=1)
    integer = finite & np.isclose(numeric, np.round(numeric), atol=1e-6).all(axis=1)
    valid = numeric[integer]
    if len(valid) == 0:
        raise ROIValidationError("No finite integer coordinate pairs found.")
    indices = np.rint(valid).astype(np.int64)
    indices[:, 0] = indices[:, 0] - coordinate_base + int(row_offset)
    indices[:, 1] = indices[:, 1] - coordinate_base + int(col_offset)
    unique = np.unique(indices, axis=0)
    audit = {
        "coordinate_rows_in_file": int(len(frame)),
        "valid_integer_coordinate_rows": int(len(valid)),
        "dropped_non_numeric_or_non_integer_rows": int(len(frame) - len(valid)),
        "duplicate_coordinate_rows": int(len(indices) - len(unique)),
        "unique_pixel_count": int(len(unique)),
        "coordinate_base_declared": int(coordinate_base),
        "row_offset_applied": int(row_offset),
        "column_offset_applied": int(col_offset),
    }
    return unique, audit


def extract_roi_spectrum(cube: Any, coordinates_yx: np.ndarray, *, coordinate_base: int,
                         row_offset: int = 0, col_offset: int = 0):
    """Return per-band arithmetic mean and extraction QA for an N x 2 (row, col) ROI."""
    if coordinate_base not in (0, 1):
        raise ROIValidationError("coordinate_base must be explicitly 0 or 1.")
    if getattr(cube, "ndim", None) != 3:
        raise ROIValidationError(f"Expected (rows, columns, bands) cube; got {getattr(cube, 'shape', None)}.")
    n_rows, n_cols, n_bands = map(int, cube.shape)
    coords = np.asarray(coordinates_yx)
    if coords.ndim != 2 or coords.shape[1] != 2 or not len(coords):
        raise ROIValidationError("coordinates_yx must be a non-empty N x 2 array.")
    if not np.issubdtype(coords.dtype, np.integer):
        if not np.all(np.isfinite(coords)) or not np.allclose(coords, np.round(coords)):
            raise ROIValidationError("ROI coordinates must be finite integer pixel indices.")
        coords = np.rint(coords).astype(np.int64)
    else:
        coords = coords.astype(np.int64, copy=False)
    mapped = coords.copy()
    mapped[:, 0] = mapped[:, 0] - coordinate_base + int(row_offset)
    mapped[:, 1] = mapped[:, 1] - coordinate_base + int(col_offset)
    mapped = np.unique(mapped, axis=0)
    valid = ((mapped[:, 0] >= 0) & (mapped[:, 0] < n_rows)
             & (mapped[:, 1] >= 0) & (mapped[:, 1] < n_cols))
    if not np.all(valid):
        raise ROIValidationError(
            f"{int((~valid).sum())} coordinates outside cube {(n_rows, n_cols, n_bands)}; "
            f"examples: {mapped[~valid][:5].tolist()}. Check index base, frame and crop offsets."
        )
    pixels = np.asarray(cube[mapped[:, 0], mapped[:, 1], :], dtype=np.float32)
    finite_fraction = float(np.isfinite(pixels).mean())
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", RuntimeWarning)
        spectrum = np.nanmean(pixels, axis=0).astype(np.float32)
    if not np.isfinite(spectrum).any():
        raise ROIValidationError("All extracted ROI spectral values are non-finite.")
    return spectrum, {
        "rows": n_rows, "columns": n_cols, "bands": n_bands,
        "unique_roi_pixels": int(len(mapped)),
        "pixel_band_finite_fraction": finite_fraction,
        "bands_without_finite_values": int((~np.isfinite(spectrum)).sum()),
    }


def _path_metadata(header: Path, root: Path, coordinate_csv: Path):
    date_folder = ""
    for parent in (header.parent, *header.parents):
        if DATE_RE.fullmatch(parent.name):
            date_folder = parent.name
            break
    pot_side = header.parent.name
    match = POT_SIDE_RE.fullmatch(pot_side) or POT_SIDE_RE.fullmatch(header.stem)
    if match:
        pot_side = match.group(0)
        pot_id, side = match.group(1).zfill(2), match.group(2).upper()
    else:
        pot_id, side = "", ""
    leaf_id = coordinate_csv.stem
    prefix = f"{pot_side}_"
    if prefix and leaf_id.startswith(prefix):
        leaf_id = leaf_id[len(prefix):]
    try:
        relative_image = str(header.relative_to(root))
    except ValueError:
        relative_image = str(header)
    return {
        "date_folder_yyyymmdd_candidate": date_folder,
        "pot_id_candidate": pot_id,
        "side_candidate": side,
        "pot_side_candidate": f"{pot_id}_{side}" if pot_id and side else "",
        "leaf_id_within_image": leaf_id,
        "image_relative_path": relative_image,
    }


def extract_image_rois(header_path, coordinate_base, modality, coordinate_frame,
                       row_offset=None, col_offset=None, image_path=None, root=None):
    """Extract all <image_stem>_leaf*.csv files adjacent to one ENVI pair."""
    header = Path(header_path)
    image = Path(image_path) if image_path else header.with_suffix(".hyspex")
    if coordinate_frame not in {"source_image", "reframed_image"}:
        raise ROIValidationError("coordinate_frame must be source_image or reframed_image.")
    if coordinate_frame == "reframed_image" and (row_offset is None or col_offset is None):
        raise ROIValidationError("Reframed-image coordinates require explicit row and column offsets.")
    row_offset = 0 if row_offset is None else int(row_offset)
    col_offset = 0 if col_offset is None else int(col_offset)
    coordinate_files = sorted(header.parent.glob(f"{header.stem}_leaf*.csv"))
    if not coordinate_files:
        raise FileNotFoundError(f"No {header.stem}_leaf*.csv coordinate files beside {header}.")
    root = Path(root) if root else header.parent
    spy_image, cube = open_envi_memmap(header, image, interleave="bip")
    wavelengths = spy_image.metadata.get("wavelength")
    wavelength_units = spy_image.metadata.get("wavelength units") or spy_image.metadata.get("wavelength_units")
    if wavelengths is not None and len(wavelengths) != cube.shape[-1]:
        raise ROIValidationError("Header wavelength count does not match cube band count.")
    wavelengths_nm = wavelength_values_to_nm(wavelengths, wavelength_units)
    spectral_axis = {
        "wavelengths_native": None if wavelengths is None else [float(value) for value in wavelengths],
        "wavelength_units": wavelength_units or "",
        "wavelengths_nm": None if wavelengths_nm is None else wavelengths_nm.tolist(),
    }

    records, audits = [], []
    for coordinate_csv in coordinate_files:
        coords, coord_audit = load_leaf_coordinates(
            coordinate_csv, coordinate_base, row_offset, col_offset
        )
        # Coordinates are already mapped to zero-based source-cube indices.
        spectrum, cube_audit = extract_roi_spectrum(cube, coords, coordinate_base=0)
        metadata = _path_metadata(header, root, coordinate_csv)
        record = {
            **metadata, "modality": modality.upper(),
            "header_file": header.name, "coordinate_file": coordinate_csv.name,
            "coordinate_base_declared": coordinate_base,
            "coordinate_frame_declared": coordinate_frame,
            "row_offset_applied": row_offset, "column_offset_applied": col_offset,
            "spectrum_domain": "dark_current_corrected_intensity_not_reflectance",
            "roi_pixel_count": coord_audit["unique_pixel_count"],
            "coordinate_rows_dropped": coord_audit["dropped_non_numeric_or_non_integer_rows"],
            "duplicate_coordinate_rows": coord_audit["duplicate_coordinate_rows"],
            "finite_pixel_band_fraction": cube_audit["pixel_band_finite_fraction"],
        }
        for band, value in enumerate(spectrum):
            record[f"band_{band:03d}"] = float(value) if np.isfinite(value) else np.nan
        records.append(record)
        audits.append({**metadata, "modality": modality.upper(),
                       "coordinate_file": coordinate_csv.name,
                       "coordinate_audit": coord_audit, "cube_audit": cube_audit,
                       "spectral_axis": spectral_axis})
    return records, audits


def run_batch(root, modality, coordinate_base, coordinate_frame, output_csv, audit_json,
              row_offset=None, col_offset=None, max_images=None):
    root, output_csv, audit_json = Path(root), Path(output_csv), Path(audit_json)
    headers = sorted(root.rglob("*.hdr"))
    if max_images is not None:
        headers = headers[:max_images]
    if not headers:
        raise FileNotFoundError(f"No .hdr files found under {root}")
    all_records, all_audits, skipped = [], [], []
    for header in headers:
        image = header.with_suffix(".hyspex")
        if not image.exists():
            skipped.append({"header": str(header), "reason": "matching .hyspex missing"})
            continue
        try:
            records, audits = extract_image_rois(
                header, coordinate_base, modality, coordinate_frame,
                row_offset, col_offset, image, root
            )
            all_records.extend(records)
            all_audits.extend(audits)
        except Exception as exc:
            skipped.append({"header": str(header), "reason": f"{type(exc).__name__}: {exc}"})
    if not all_records:
        raise RuntimeError(f"No leaf spectra extracted; first failures: {skipped[:3]}")
    output_csv.parent.mkdir(parents=True, exist_ok=True)
    audit_json.parent.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(all_records).to_csv(output_csv, index=False)
    spectral_axes_by_image = {}
    for item in all_audits:
        spectral_axes_by_image[item["image_relative_path"]] = item["spectral_axis"]
        item.pop("spectral_axis", None)
    audit = {
        "root": str(root), "modality": modality.upper(),
        "spectral_axes_by_image": spectral_axes_by_image,
        "coordinate_base": coordinate_base, "coordinate_frame": coordinate_frame,
        "row_offset": row_offset, "column_offset": col_offset,
        "headers_discovered": len(headers), "leaf_spectra_extracted": len(all_records),
        "headers_skipped_or_failed": skipped, "leaf_audits": all_audits,
        "scientific_notes": [
            "One row is one coordinate-defined leaf ROI in one image, not an independent biological replicate.",
            "leaf_id_within_image is not a persistent cross-date leaf identity.",
            "Group validation by pot because inoculation treatment was assigned at pot level.",
            "Spectra are dark-current-corrected intensity, not reflectance, until Spectralon references are validated.",
            "Treatment and genotype must be joined from verified annotations, never inferred from pot numbers.",
        ],
    }
    audit_json.write_text(json.dumps(audit, indent=2), encoding="utf-8")
    return audit


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--modality", choices=["VNIR", "SWIR"], required=True)
    parser.add_argument("--coordinate-base", type=int, choices=[0, 1], required=True)
    parser.add_argument("--coordinate-frame", choices=["source_image", "reframed_image"], required=True)
    parser.add_argument("--row-offset", type=int, default=None)
    parser.add_argument("--col-offset", type=int, default=None)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--audit", type=Path, required=True)
    parser.add_argument("--max-images", type=int, default=None)
    args = parser.parse_args()
    audit = run_batch(args.root, args.modality, args.coordinate_base, args.coordinate_frame,
                      args.output, args.audit, args.row_offset, args.col_offset, args.max_images)
    print(json.dumps({
        "modality": audit["modality"],
        "headers_discovered": audit["headers_discovered"],
        "leaf_spectra_extracted": audit["leaf_spectra_extracted"],
        "headers_skipped_or_failed": len(audit["headers_skipped_or_failed"]),
        "output": str(args.output), "audit": str(args.audit),
    }, indent=2))


if __name__ == "__main__":
    main()

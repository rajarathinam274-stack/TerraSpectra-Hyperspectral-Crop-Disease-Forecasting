import numpy as np
import pytest

from scripts.extract_leaf_spectra import (
    ROIValidationError,
    extract_roi_spectrum,
    load_leaf_coordinates,
)


def test_extract_mean_spectrum_from_yx_coordinates():
    cube = np.zeros((4, 5, 3), dtype=np.float32)
    cube[1, 2, :] = [1, 2, 3]
    cube[2, 2, :] = [3, 4, 5]
    spectrum, audit = extract_roi_spectrum(cube, np.array([[1, 2], [2, 2]]), coordinate_base=0)
    np.testing.assert_allclose(spectrum, [2, 3, 4])
    assert audit["unique_roi_pixels"] == 2


def test_coordinate_csv_maps_one_based_indices_to_zero_based(tmp_path):
    path = tmp_path / "leaf.csv"
    path.write_text("2,3\n3,3\n", encoding="utf-8")
    coords, audit = load_leaf_coordinates(path, coordinate_base=1)
    np.testing.assert_array_equal(coords, [[1, 2], [2, 2]])
    assert audit["unique_pixel_count"] == 2


def test_coordinate_loader_deduplicates_and_audits_header(tmp_path):
    path = tmp_path / "leaf.csv"
    path.write_text("vertical,horizontal\n1,2\n1,2\n2,2\n", encoding="utf-8")
    coords, audit = load_leaf_coordinates(path, coordinate_base=1)
    np.testing.assert_array_equal(coords, [[0, 1], [1, 1]])
    assert audit["duplicate_coordinate_rows"] == 1
    assert audit["dropped_non_numeric_or_non_integer_rows"] == 1


def test_out_of_bounds_coordinates_fail_instead_of_clipping():
    cube = np.zeros((2, 2, 3), dtype=np.float32)
    with pytest.raises(ROIValidationError, match="outside cube"):
        extract_roi_spectrum(cube, np.array([[0, 2]]), coordinate_base=0)


def test_non_integer_coordinates_are_rejected():
    cube = np.zeros((3, 3, 2), dtype=np.float32)
    with pytest.raises(ROIValidationError, match="integer"):
        extract_roi_spectrum(cube, np.array([[0.2, 1.0]]), coordinate_base=0)


def test_offsets_are_applied_for_crop_to_source_mapping():
    cube = np.zeros((10, 10, 2), dtype=np.float32)
    cube[5, 6, :] = [4, 8]
    spectrum, _ = extract_roi_spectrum(
        cube, np.array([[1, 2]]), coordinate_base=0, row_offset=4, col_offset=4
    )
    np.testing.assert_allclose(spectrum, [4, 8])


def test_invalid_coordinate_base_rejected():
    cube = np.zeros((2, 2, 2), dtype=np.float32)
    with pytest.raises(ROIValidationError, match="0 or 1"):
        extract_roi_spectrum(cube, np.array([[0, 0]]), coordinate_base=2)


def test_batch_extracts_per_leaf_rows_and_preserves_provenance(tmp_path, monkeypatch):
    import pandas as pd
    from scripts import extract_leaf_spectra as module

    class FakeSpy:
        metadata = {"wavelength": [500.0, 600.0], "wavelength units": "nm"}

    sample_dir = tmp_path / "20210311" / "26_G"
    sample_dir.mkdir(parents=True)
    header = sample_dir / "26_G.hdr"
    image = sample_dir / "26_G.hyspex"
    header.write_text("synthetic header", encoding="utf-8")
    image.write_bytes(b"synthetic binary")
    (sample_dir / "26_G_leaf1.csv").write_text("1,1\n1,2\n", encoding="utf-8")

    cube = np.zeros((3, 4, 2), dtype=np.float32)
    cube[0, 0, :] = [2.0, 4.0]
    cube[0, 1, :] = [4.0, 6.0]
    monkeypatch.setattr(module, "open_envi_memmap", lambda *a, **k: (FakeSpy(), cube))

    output = tmp_path / "processed" / "spectra.csv"
    audit_path = tmp_path / "processed" / "audit.json"
    audit = module.run_batch(tmp_path, "VNIR", 1, "source_image", output, audit_path)
    frame = pd.read_csv(output)
    assert audit["leaf_spectra_extracted"] == 1
    assert frame.loc[0, "date_folder_yyyymmdd_candidate"] == 20210311
    assert frame.loc[0, "pot_id_candidate"] == 26
    assert frame.loc[0, "side_candidate"] == "G"
    assert frame.loc[0, "leaf_id_within_image"] == "leaf1"
    assert frame.loc[0, "spectrum_domain"] == "dark_current_corrected_intensity_not_reflectance"
    assert frame.loc[0, "band_000"] == pytest.approx(3.0)
    assert frame.loc[0, "band_001"] == pytest.approx(5.0)
    axis = audit["spectral_axes_by_image"]["20210311/26_G/26_G.hdr"]
    assert axis["wavelengths_nm"] == [500.0, 600.0]

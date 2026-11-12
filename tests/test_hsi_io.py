import numpy as np
import pytest

from scripts.hsi_io import (
    HSIValidationError,
    compare_sensor_profile,
    reflectance_from_dark_corrected,
    reflectance_from_raw,
    summarize_reflectance,
    wavelength_values_to_nm,
)


def test_raw_reflectance_uses_dark_white_equation():
    sample = np.array([[[60.0, 90.0]]])
    white = np.array([[[110.0, 210.0]]])
    dark = np.array([[[10.0, 10.0]]])
    result = reflectance_from_raw(sample, white, dark)
    np.testing.assert_allclose(result, [[[0.5, 0.4]]])


def test_dark_corrected_reflectance_does_not_subtract_dark_again():
    sample = np.array([[[50.0, 80.0]]])
    white = np.array([100.0, 200.0])
    result = reflectance_from_dark_corrected(sample, white)
    np.testing.assert_allclose(result, [[[0.5, 0.4]]])


def test_per_row_reference_broadcasts_over_columns():
    sample = np.full((2, 3, 2), 50.0)
    white_by_row = np.array([[100.0, 100.0], [200.0, 200.0]])
    result = reflectance_from_dark_corrected(sample, white_by_row)
    np.testing.assert_allclose(result[0], 0.5)
    np.testing.assert_allclose(result[1], 0.25)


def test_zero_reference_produces_nan_not_infinity():
    result = reflectance_from_dark_corrected(
        np.array([[1.0, 2.0]]), np.array([0.0, 2.0])
    )
    assert np.isnan(result[0, 0])
    assert result[0, 1] == pytest.approx(1.0)


def test_white_reference_curve_applied_per_band():
    result = reflectance_from_dark_corrected(
        np.array([[50.0, 50.0]]), np.array([100.0, 100.0]),
        white_reflectance=np.array([0.98, 0.95])
    )
    np.testing.assert_allclose(result, [[0.49, 0.475]])


def test_scalar_certified_white_reflectance_is_broadcast():
    result = reflectance_from_dark_corrected(
        np.array([[50.0, 50.0]]), np.array([100.0, 100.0]),
        white_reflectance=0.99
    )
    np.testing.assert_allclose(result, [[0.495, 0.495]])


def test_rejects_wrong_band_count():
    with pytest.raises(HSIValidationError):
        reflectance_from_dark_corrected(np.ones((2, 3, 4)), np.ones(3))


def test_wavelength_units_convert_to_nm():
    np.testing.assert_allclose(
        wavelength_values_to_nm([0.5, 1.0], "micrometers"), [500, 1000]
    )
    np.testing.assert_allclose(
        wavelength_values_to_nm([10000, 5000], "cm-1"), [1000, 2000]
    )
    assert wavelength_values_to_nm([500, 600], "unknown") is None


def test_sensor_profile_comparison_reports_match_without_mutating_header():
    report = {
        "shape_rows_columns_bands": [10, 20, 216],
        "wavelengths_nm": [411.0, 700.0, 993.0],
    }
    check = compare_sensor_profile(report, "VNIR")
    assert check["status"] == "match"
    assert report["shape_rows_columns_bands"][2] == 216


def test_reflectance_summary_does_not_clip_out_of_range_values():
    summary = summarize_reflectance(np.array([[[-0.1, 1.2, np.nan]]]))
    assert summary["finite_fraction"] == pytest.approx(2 / 3)
    assert summary["outside_zero_one_fraction"] == pytest.approx(1.0)

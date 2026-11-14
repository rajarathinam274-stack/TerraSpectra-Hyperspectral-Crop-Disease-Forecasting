import json
import pandas as pd
import pytest

from scripts.explore_spectra import (
    EDAValidationError, aggregate_pot_date, attach_annotations,
    band_columns, resolve_wavelength_axis, run_eda,
)


def fixture_spectra(tmp_path):
    rows = []
    for pot, treatment in [("01", "Control"), ("02", "Infected"),
                           ("03", "Control"), ("04", "Infected")]:
        for date, offset in [("20210311", 0.0), ("20210320", 0.2)]:
            for leaf in ["leaf1", "leaf2"]:
                value = (1.0 if treatment == "Infected" else 0.5) + offset
                rows.append({
                    "pot_id_candidate": pot,
                    "date_folder_yyyymmdd_candidate": date,
                    "image_relative_path": f"{date}/{int(pot):02d}_D/{int(pot):02d}_D.hdr",
                    "leaf_id_within_image": leaf,
                    "spectrum_domain": "dark_current_corrected_intensity_not_reflectance",
                    "band_000": value, "band_001": value + 0.1, "band_002": value + 0.2,
                })
    path = tmp_path / "spectra.csv"
    pd.DataFrame(rows).to_csv(path, index=False)
    return path


def test_band_columns_are_sorted_numerically():
    assert band_columns(["band_010", "band_002", "x", "band_001"]) == [
        "band_001", "band_002", "band_010"
    ]


def test_pot_date_aggregation_prevents_leaf_roi_pseudoreplication(tmp_path):
    frame = pd.read_csv(fixture_spectra(tmp_path))
    grouped, _ = aggregate_pot_date(
        frame, ["band_000", "band_001", "band_002"],
        "pot_id_candidate", "date_folder_yyyymmdd_candidate", None, None
    )
    assert len(frame) == 16
    assert len(grouped) == 8
    assert grouped["pot_id_candidate"].nunique() == 4


def test_annotation_join_rejects_duplicate_keys(tmp_path):
    spectra = pd.DataFrame({"sample_id": ["a"], "band_000": [1], "band_001": [2]})
    labels_path = tmp_path / "labels.csv"
    pd.DataFrame({"sample_id": ["a", "a"], "status": ["Control", "Infected"]}).to_csv(labels_path, index=False)
    with pytest.raises(EDAValidationError, match="not unique"):
        attach_annotations(spectra, labels_path, ["sample_id"], ["sample_id"], "status", None)


def test_wavelength_axis_rejects_cross_image_mismatch(tmp_path):
    frame = pd.DataFrame({"image_relative_path": ["a", "b"]})
    audit = {"spectral_axes_by_image": {
        "a": {"wavelengths_nm": [500, 600]},
        "b": {"wavelengths_nm": [501, 600]},
    }}
    path = tmp_path / "audit.json"
    path.write_text(json.dumps(audit))
    with pytest.raises(EDAValidationError, match="Wavelength axis differs"):
        resolve_wavelength_axis(path, frame, ["band_000", "band_001"])


def test_end_to_end_eda_writes_grouped_outputs_and_pca(tmp_path):
    spectra = fixture_spectra(tmp_path)
    labels = tmp_path / "labels.csv"
    pd.DataFrame({
        "pot": ["01", "02", "03", "04"],
        "status": ["Control", "Infected", "Control", "Infected"],
        "genotype": ["EPO_067", "EPO_067", "EPO_068", "EPO_068"],
    }).to_csv(labels, index=False)
    out = tmp_path / "out"
    report = run_eda(
        spectra, out, labels_csv=labels,
        spectrum_keys=["pot_id_candidate"], label_keys=["pot"],
        class_column="status", genotype_column="genotype",
    )
    grouped = pd.read_csv(out / "pot_date_spectra.csv")
    assert report["roi_rows"] == 16
    assert report["pot_date_units"] == 8
    assert set(grouped["status"]) == {"Control", "Infected"}
    assert report["pca"]["status"] == "completed_descriptive_only"
    assert (out / "pca_pot_date.png").exists()
    assert (out / "spectral_summary_by_class_date.csv").exists()


def test_missing_pot_group_is_not_silently_replaced(tmp_path):
    frame = pd.read_csv(fixture_spectra(tmp_path)).drop(columns=["pot_id_candidate"])
    with pytest.raises(EDAValidationError, match="grouping column"):
        aggregate_pot_date(
            frame, ["band_000", "band_001"],
            "pot_id_candidate", "date_folder_yyyymmdd_candidate", None, None
        )

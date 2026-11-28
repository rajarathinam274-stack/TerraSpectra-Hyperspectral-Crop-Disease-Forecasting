from pathlib import Path

import pytest
import yaml

from scripts.metadata_utils import parse_count_table, read_source_metadata_csv, selected_metadata_csv_paths


def test_configured_source_csvs_are_selected_in_config_order(tmp_path):
    metadata = tmp_path / "metadata"
    metadata.mkdir()
    names = ["Data_description.csv", "VNIR_data.csv", "SWIR_data.csv"]
    for name in names:
        (metadata / name).write_text("a,b\n1,2\n", encoding="utf-8")
    config = tmp_path / "dataset.yaml"
    config.write_text(yaml.safe_dump({"dataset": {"selected_metadata_files": names}}), encoding="utf-8")
    assert selected_metadata_csv_paths(metadata, config) == [metadata / name for name in names]


def test_missing_configured_source_file_fails_instead_of_globbing_outputs(tmp_path):
    metadata = tmp_path / "metadata"
    metadata.mkdir()
    (metadata / "sample_map_candidates.csv").write_text("derived\n1\n", encoding="utf-8")
    config = tmp_path / "dataset.yaml"
    config.write_text(yaml.safe_dump({"dataset": {
        "selected_metadata_files": ["VNIR_data.csv", "SWIR_data.csv"]
    }}), encoding="utf-8")
    with pytest.raises(FileNotFoundError, match="Configured source metadata"):
        selected_metadata_csv_paths(metadata, config)


def test_data_description_semicolon_cp1252_layout(tmp_path):
    path = tmp_path / "Data_description.csv"
    path.write_text(
        "title;;;;;;;;\n;;;;;;;;\n"
        "Pot [1];Side [2];Leaf [3];Genotype [4];Treatment [5];Confidence level [6];;note\n"
        "1;G;1;EPO_68;Infected;1;;note\n",
        encoding="cp1252",
    )
    frame = read_source_metadata_csv(path)
    assert frame.shape == (1, 6)
    assert frame.iloc[0, 1] == "G"
    assert frame.iloc[0, 4] == "Infected"


def test_count_table_preserves_empty_and_na_as_distinct_statuses(tmp_path):
    path = tmp_path / "VNIR_data.csv"
    path.write_text(
        "title;;;;;;;;\n;;;;;;;;\n"
        ";;Date (dpi) [1];-1;;0;\n"
        "Pot [2];Genotype [3];Treatment [4];G [5];D [6];G;D\n"
        "01;EPO_68;Infected;2;1;NA;\n"
        "02;EPO_67;Non-infected;;;2;1\n"
        "[1]: footer;;;;;;\n",
        encoding="cp1252",
    )
    long = parse_count_table(path)
    assert len(long) == 8
    assert set(long["dpi"]) == {-1, 0}
    assert long.loc[(long.pot_id == "01") & (long.dpi == 0) & (long.side == "G"), "acquisition_status"].iloc[0] == "technical_missing"
    assert long.loc[(long.pot_id == "01") & (long.dpi == 0) & (long.side == "D"), "acquisition_status"].iloc[0] == "no_acquisition"
    assert long.loc[(long.pot_id == "02") & (long.dpi == 0) & (long.side == "G"), "leaf_count"].iloc[0] == 2

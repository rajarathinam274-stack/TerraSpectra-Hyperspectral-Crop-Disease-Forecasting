from pathlib import Path

import pytest
import yaml

from scripts.metadata_utils import selected_metadata_csv_paths


def test_configured_source_csvs_are_selected_in_config_order(tmp_path):
    metadata = tmp_path / "metadata"
    metadata.mkdir()
    names = ["Data_description.csv", "VNIR_data.csv", "SWIR_data.csv"]
    for name in names:
        (metadata / name).write_text("a,b\n1,2\n", encoding="utf-8")
    config = tmp_path / "dataset.yaml"
    config.write_text(yaml.safe_dump({"dataset": {"selected_metadata_files": names}}),
                      encoding="utf-8")

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

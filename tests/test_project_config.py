from pathlib import Path

import yaml


ROOT = Path(__file__).resolve().parents[1]


def test_dataset_config_has_public_source_and_safe_forecasting_default():
    config = yaml.safe_load(
        (ROOT / "config" / "dataset.yaml").read_text(encoding="utf-8")
    )
    assert config["dataset"]["doi"] == "10.57745/WVP0FJ"
    assert config["dataset"]["dataverse_api"].startswith("https://")
    assert config["research"]["forecasting_claim_allowed"] is False

"""Resolve source metadata CSVs from the dataset configuration, not directory globs."""
from __future__ import annotations

from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
CONFIG_PATH = ROOT / "config" / "dataset.yaml"
METADATA_DIR = ROOT / "data" / "metadata"


def selected_metadata_csv_paths(metadata_dir: Path | None = None,
                                config_path: Path | None = None) -> list[Path]:
    """Return configured source CSV paths in config order; fail if any are absent."""
    metadata_dir = Path(metadata_dir) if metadata_dir is not None else METADATA_DIR
    config_path = Path(config_path) if config_path is not None else CONFIG_PATH
    with config_path.open("r", encoding="utf-8") as handle:
        config = yaml.safe_load(handle) or {}
    filenames = config.get("dataset", {}).get("selected_metadata_files", [])
    if not filenames:
        raise ValueError(f"No dataset.selected_metadata_files configured in {config_path}")
    paths = [metadata_dir / str(filename) for filename in filenames]
    missing = [path for path in paths if not path.is_file()]
    if missing:
        raise FileNotFoundError(
            "Configured source metadata CSVs are missing: "
            + ", ".join(str(path) for path in missing)
        )
    return paths

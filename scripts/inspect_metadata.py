"""Inspect configured source metadata CSVs without modifying source files."""
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
METADATA_DIR = ROOT / "data" / "metadata"
try:
    from .metadata_utils import read_source_metadata_csv, selected_metadata_csv_paths
except ImportError:
    from metadata_utils import read_source_metadata_csv, selected_metadata_csv_paths


def inspect_csv(path: Path) -> None:
    print(f"\n{'=' * 72}\nFILE: {path.name}")
    frame = read_source_metadata_csv(path)
    print(f"Shape: {frame.shape}")
    print("\nColumns and dtypes:")
    print(frame.dtypes.to_string())
    print("\nMissing values:")
    print(frame.isna().sum().to_string())
    print("\nSample rows:")
    print(frame.head(5).to_string(index=False))


def main() -> None:
    for path in selected_metadata_csv_paths(METADATA_DIR):
        inspect_csv(path)


if __name__ == "__main__":
    main()

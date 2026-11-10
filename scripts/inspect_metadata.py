"""Inspect downloaded CSV metadata without modifying source files."""
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
METADATA_DIR = ROOT / "data" / "metadata"


def inspect_csv(path: Path) -> None:
    print(f"\n{'=' * 72}\nFILE: {path.name}")
    frame = pd.read_csv(path, encoding="utf-8-sig", low_memory=False)
    print(f"Shape: {frame.shape}")
    print("\nColumns and dtypes:")
    print(frame.dtypes.to_string())
    print("\nMissing values:")
    print(frame.isna().sum().to_string())
    print("\nSample rows:")
    print(frame.head(5).to_string(index=False))


def main() -> None:
    csv_files = sorted(METADATA_DIR.glob("*.csv"))
    if not csv_files:
        raise FileNotFoundError(
            f"No metadata CSV files found in {METADATA_DIR}. "
            "Run scripts/download_metadata.py first."
        )
    for path in csv_files:
        inspect_csv(path)


if __name__ == "__main__":
    main()

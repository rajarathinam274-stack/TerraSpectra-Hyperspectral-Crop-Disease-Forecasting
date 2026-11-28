"""Dataset-specific parsing helpers for the Dataverse annotation tables."""
from __future__ import annotations

import csv
import re
from pathlib import Path

import pandas as pd
import yaml

ROOT = Path(__file__).resolve().parents[1]
CONFIG_PATH = ROOT / "config" / "dataset.yaml"
METADATA_DIR = ROOT / "data" / "metadata"
POT_RE = re.compile(r"\d{2}")


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


def read_source_metadata_csv(path: Path) -> pd.DataFrame:
    """Read the three source tables using their verified semicolon/CP1252 layout.

    Data_description.csv starts after a title and blank line. VNIR/SWIR tables
    have three introductory/header lines and six trailing footnote rows.
    """
    path = Path(path)
    if path.name == "Data_description.csv":
        return pd.read_csv(
            path, sep=";", encoding="cp1252", skiprows=2,
            usecols=range(6), low_memory=False,
        )
    if path.name in {"VNIR_data.csv", "SWIR_data.csv"}:
        frame = pd.read_csv(
            path, sep=";", encoding="cp1252", skiprows=3,
            low_memory=False, keep_default_na=False,
        )
        pot_column = frame.columns[0]
        valid_pots = frame[pot_column].astype(str).str.fullmatch(POT_RE)
        return frame.loc[valid_pots].copy().reset_index(drop=True)
    raise ValueError(f"Unsupported source metadata file: {path.name}")


def parse_count_table(path: Path) -> pd.DataFrame:
    """Parse a modality's 48-pot x 18-DPI x 2-side count matrix into long rows.

    Each output row is a pot/DPI/side acquisition-count record, not a leaf/image
    identity. Blank cells and literal NA are retained as distinct statuses.
    """
    path = Path(path)
    if path.name not in {"VNIR_data.csv", "SWIR_data.csv"}:
        raise ValueError(f"Not a VNIR/SWIR count table: {path.name}")

    lines = path.read_text(encoding="cp1252").splitlines()
    if len(lines) < 4:
        raise ValueError(f"Unexpected short count table: {path.name}")
    date_header = next(csv.reader([lines[2]], delimiter=";"))
    side_header = next(csv.reader([lines[3]], delimiter=";"))
    frame = read_source_metadata_csv(path)

    if len(frame.columns) < 5:
        raise ValueError(f"Unexpected count-table width in {path.name}")
    count_column_count = len(frame.columns) - 3
    if count_column_count % 2:
        raise ValueError(f"Expected paired side-count columns in {path.name}")
    if len(date_header) != len(frame.columns) or len(side_header) != len(frame.columns):
        raise ValueError(f"Header width mismatch in {path.name}")

    records = []
    for count_start in range(3, len(frame.columns), 2):
        date_token = str(date_header[count_start]).strip()
        try:
            dpi = int(date_token)
        except ValueError as exc:
            raise ValueError(
                f"Invalid DPI header at column {count_start} in {path.name}: {date_token!r}"
            ) from exc
        sides = [
            str(side_header[count_start]).strip().split()[0].upper(),
            str(side_header[count_start + 1]).strip().split()[0].upper(),
        ]
        if sides != ["G", "D"]:
            raise ValueError(
                f"Unexpected side order at DPI {dpi} in {path.name}: {sides}"
            )

        for _, row in frame.iterrows():
            pot_id = str(row.iloc[0]).strip()
            genotype = str(row.iloc[1]).strip()
            treatment = str(row.iloc[2]).strip()
            for offset, side in enumerate(sides):
                raw_count = str(row.iloc[count_start + offset]).strip()
                if raw_count == "":
                    status, count = "no_acquisition", None
                elif raw_count.upper() == "NA":
                    status, count = "technical_missing", None
                else:
                    parsed = pd.to_numeric(raw_count, errors="coerce")
                    if pd.isna(parsed) or float(parsed) < 0 or not float(parsed).is_integer():
                        status, count = "invalid_count", None
                    else:
                        status, count = "observed_count", int(parsed)
                records.append({
                    "modality": path.stem.replace("_data", "").upper(),
                    "source_file": path.name,
                    "pot_id": pot_id,
                    "genotype": genotype,
                    "treatment_assignment": treatment,
                    "dpi": dpi,
                    "side": side,
                    "raw_count": raw_count,
                    "leaf_count": count,
                    "acquisition_status": status,
                })
    return pd.DataFrame(records)

"""Build a conservative candidate sample map from dataset annotation CSVs.

Only explicit columns and date/NUM_SIDE tokens are extracted. This script does
not infer genotype, treatment, leaf identity, plant identity or disease state
from pot numbers. Review its JSON audit before modelling.
"""
from __future__ import annotations

import json
import re
from datetime import datetime
from pathlib import Path
from typing import Any

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
METADATA_DIR = ROOT / "data" / "metadata"

ALIASES = {
    "date": {"date", "acquisition_date", "acquisitiondate", "image_date", "yyyymmdd"},
    "pot": {"pot", "pot_id", "pot_number", "potno", "num", "pot_num"},
    "side": {"side", "pot_side", "measured_side"},
    "genotype": {"genotype", "genotype_name", "cultivar", "variety"},
    "treatment": {"treatment", "infection_status", "infected_status", "status", "condition", "label"},
    "image": {"image", "image_id", "image_name", "filename", "file_name", "filepath", "file_path", "path", "sample"},
    "leaf": {"leaf", "leaf_id", "leaf_number", "leaf_no"},
    "plant": {"plant", "plant_id", "plant_number", "plant_no"},
}

DATE_RE = re.compile(r"(?<!\d)(20\d{6})(?!\d)")
POT_SIDE_RE = re.compile(r"(?<!\d)(\d{1,2})_([DG])(?=$|[^A-Za-z])", re.IGNORECASE)


def normalize_column(value: Any) -> str:
    return re.sub(r"[^a-z0-9]+", "_", str(value).strip().lower()).strip("_")


def find_column(columns, role: str) -> str | None:
    normalized = {normalize_column(column): str(column) for column in columns}
    for alias in ALIASES[role]:
        if alias in normalized:
            return normalized[alias]
    token_sets = {
        "date": {"date", "acquisition_date"},
        "pot": {"pot", "pot_id", "pot_number"},
        "side": {"side"},
        "genotype": {"genotype", "cultivar", "variety"},
        "treatment": {"treatment", "infection_status", "status", "condition", "label"},
        "image": {"image", "filename", "file_path", "filepath", "path", "sample"},
        "leaf": {"leaf", "leaf_id"},
        "plant": {"plant", "plant_id"},
    }
    for norm, original in normalized.items():
        if role in {"pot", "side"} and norm in {"num_side", "pot_side"}:
            continue
        if set(norm.split("_")) & token_sets[role]:
            return original
    return None


def parse_date_token(text: str) -> str | None:
    match = DATE_RE.search(str(text))
    if not match:
        return None
    try:
        return datetime.strptime(match.group(1), "%Y%m%d").date().isoformat()
    except ValueError:
        return None


def parse_pot_side_token(text: str) -> tuple[str | None, str | None]:
    match = POT_SIDE_RE.search(str(text))
    if not match:
        return None, None
    return match.group(1).zfill(2), match.group(2).upper()


def scalar_text(value: Any) -> str:
    if pd.isna(value):
        return ""
    return str(value).strip()


def candidate_record(row: pd.Series, columns: dict[str, str | None],
                     modality: str, source_csv: str, row_number: int) -> dict:
    values = [scalar_text(value) for value in row.tolist()]
    combined_text = " | ".join(value for value in values if value)
    image_value = scalar_text(row[columns["image"]]) if columns["image"] else ""
    date_value = scalar_text(row[columns["date"]]) if columns["date"] else ""
    pot_value = scalar_text(row[columns["pot"]]) if columns["pot"] else ""
    side_value = scalar_text(row[columns["side"]]) if columns["side"] else ""

    date_iso = parse_date_token(date_value) or parse_date_token(combined_text)
    if not date_iso and date_value:
        parsed = pd.to_datetime(date_value, errors="coerce", dayfirst=True)
        if not pd.isna(parsed):
            date_iso = parsed.date().isoformat()

    pot_id, side = parse_pot_side_token(combined_text)
    if not pot_id and pot_value:
        digits = re.search(r"\d{1,2}", pot_value)
        if digits:
            number = int(digits.group())
            if 1 <= number <= 48:
                pot_id = f"{number:02d}"
    if not side and side_value.upper() in {"D", "G"}:
        side = side_value.upper()

    def explicit(role: str) -> str:
        column = columns[role]
        return scalar_text(row[column]) if column else ""

    return {
        "modality": modality,
        "source_csv": source_csv,
        "source_row_1based": row_number,
        "date_iso_candidate": date_iso or "",
        "pot_id_candidate": pot_id or "",
        "side_candidate": side or "",
        "pot_side_candidate": f"{pot_id}_{side}" if pot_id and side else "",
        "pot_group_candidate": pot_id or "",
        "genotype_explicit": explicit("genotype"),
        "treatment_explicit": explicit("treatment"),
        "image_or_sample_identifier": image_value,
        "leaf_identifier_explicit": explicit("leaf"),
        "plant_identifier_explicit": explicit("plant"),
        "raw_identity_context": combined_text,
    }


def summarize_table(path: Path) -> tuple[list[dict], dict]:
    frame = pd.read_csv(path, encoding="utf-8-sig", low_memory=False)
    columns = {role: find_column(frame.columns, role) for role in ALIASES}
    records = [
        candidate_record(
            row, columns, path.stem.replace("_data", "").upper(),
            path.name, index + 1
        )
        for index, (_, row) in enumerate(frame.iterrows())
    ]
    mapped = pd.DataFrame(records)
    summary = {
        "file": path.name,
        "rows": int(len(frame)),
        "columns": [str(column) for column in frame.columns],
        "recognized_columns": columns,
        "rows_with_date_candidate": int(mapped["date_iso_candidate"].ne("").sum()),
        "rows_with_pot_candidate": int(mapped["pot_id_candidate"].ne("").sum()),
        "unique_pots_candidate": sorted(mapped.loc[
            mapped["pot_id_candidate"].ne(""), "pot_id_candidate"
        ].unique().tolist()),
        "unique_dates_candidate": sorted(mapped.loc[
            mapped["date_iso_candidate"].ne(""), "date_iso_candidate"
        ].unique().tolist()),
        "unique_pot_sides_candidate": int(mapped.loc[
            mapped["pot_side_candidate"].ne(""), "pot_side_candidate"
        ].nunique()),
        "leaf_id_column_detected": bool(columns["leaf"]),
        "plant_id_column_detected": bool(columns["plant"]),
        "warning": (
            "Candidates come from explicit column names or date/pot-side tokens. "
            "They are not verified semantic labels; pot-side is not a leaf ID."
        ),
    }
    return records, summary


def main() -> None:
    paths = [METADATA_DIR / name for name in ("VNIR_data.csv", "SWIR_data.csv")]
    missing = [path.name for path in paths if not path.exists()]
    if missing:
        raise FileNotFoundError(
            "Missing annotation files: " + ", ".join(missing)
            + ". Run scripts/download_metadata.py first."
        )

    all_records: list[dict] = []
    summaries = {}
    for path in paths:
        records, summary = summarize_table(path)
        all_records.extend(records)
        summaries[path.name] = summary

    output_csv = METADATA_DIR / "sample_map_candidates.csv"
    pd.DataFrame(all_records).to_csv(output_csv, index=False)
    vnir, swir = summaries["VNIR_data.csv"], summaries["SWIR_data.csv"]
    audit = {
        "source_doi": "10.57745/WVP0FJ",
        "table_summaries": summaries,
        "cross_modality": {
            "same_candidate_date_set": vnir["unique_dates_candidate"] == swir["unique_dates_candidate"],
            "same_candidate_pot_set": vnir["unique_pots_candidate"] == swir["unique_pots_candidate"],
        },
        "grouping_recommendation": (
            "Use pot_id as the conservative biological grouping unit because treatment "
            "was assigned at pot level. Keep both sides and all dates of a pot together."
        ),
        "forecasting_gate": (
            "No leaf-level longitudinal identity is established by this script. "
            "Require stable repeated biological IDs and future outcome labels before "
            "claiming forecasting."
        ),
        "outputs": {"candidate_map_csv": str(output_csv.relative_to(ROOT))},
    }
    output_json = METADATA_DIR / "sample_map_audit.json"
    output_json.write_text(
        json.dumps(audit, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    print(f"Candidate rows written: {len(all_records)} -> {output_csv}")
    for filename, summary in summaries.items():
        print(
            f"{filename}: {summary['rows']} rows; "
            f"{summary['rows_with_date_candidate']} date candidates; "
            f"{summary['rows_with_pot_candidate']} pot candidates; "
            f"leaf ID column={summary['leaf_id_column_detected']}; "
            f"plant ID column={summary['plant_id_column_detected']}"
        )
    print(f"Audit written: {output_json}")
    print("Review candidates against Data_description.csv and the data paper before modelling.")


if __name__ == "__main__":
    main()

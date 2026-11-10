"""Create a schema-only audit of the downloaded annotation CSV files."""
from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
METADATA_DIR = ROOT / "data" / "metadata"

COLUMN_HINTS = {
    "identity_or_grouping": (
        "leaf", "plant", "pot", "sample", "image", "side", "replicate",
        "specimen", "barcode", "id",
    ),
    "time_or_acquisition": ("date", "day", "dpi", "time", "acquisition"),
    "label_or_treatment": (
        "infection", "infected", "disease", "status", "treatment",
        "label", "class", "condition",
    ),
    "genotype_or_cultivar": ("genotype", "cultivar", "variety"),
}


def candidate_columns(columns) -> dict[str, list[str]]:
    """Return column-name hints; do not assign semantic roles automatically."""
    return {
        role: [
            str(column)
            for column in columns
            if any(token in str(column).lower() for token in tokens)
        ]
        for role, tokens in COLUMN_HINTS.items()
    }


def summarize_csv(path: Path) -> dict:
    frame = pd.read_csv(path, encoding="utf-8-sig", low_memory=False)
    columns = []
    for name in frame.columns:
        series = frame[name]
        columns.append({
            "name": str(name),
            "dtype": str(series.dtype),
            "missing": int(series.isna().sum()),
            "unique_non_null": int(series.nunique(dropna=True)),
        })
    return {
        "filename": path.name,
        "rows": int(frame.shape[0]),
        "column_count": int(frame.shape[1]),
        "columns": columns,
        "duplicate_full_rows": int(frame.duplicated().sum()),
        "candidate_columns": candidate_columns(frame.columns),
    }


def main() -> None:
    paths = sorted(METADATA_DIR.glob("*.csv"))
    if not paths:
        raise FileNotFoundError(
            f"No annotation CSVs found in {METADATA_DIR}. "
            "Run scripts/download_metadata.py first."
        )

    summaries = {path.name: summarize_csv(path) for path in paths}
    comparison = {}
    left, right = "VNIR_data.csv", "SWIR_data.csv"
    if left in summaries and right in summaries:
        left_cols = [item["name"] for item in summaries[left]["columns"]]
        right_cols = [item["name"] for item in summaries[right]["columns"]]
        comparison[f"{left}__vs__{right}"] = {
            "same_column_names_in_same_order": left_cols == right_cols,
            "left_only_columns": sorted(set(left_cols) - set(right_cols)),
            "right_only_columns": sorted(set(right_cols) - set(left_cols)),
            "row_count_difference": summaries[left]["rows"] - summaries[right]["rows"],
        }

    audit = {
        "source": "Recherche Data Gouv DOI 10.57745/WVP0FJ",
        "files": summaries,
        "spectral_table_comparison": comparison,
        "interpretation_warning": (
            "Column-name hints are not confirmed semantics. Verify sample identity, "
            "date meaning, infection labels, treatment allocation and repeated observations "
            "against Data_description.csv and the data paper before modelling."
        ),
    }
    output = METADATA_DIR / "annotation_audit.json"
    output.write_text(json.dumps(audit, indent=2, ensure_ascii=False), encoding="utf-8")

    for filename, summary in summaries.items():
        print(
            f"{filename}: {summary['rows']} rows x {summary['column_count']} columns; "
            f"{summary['duplicate_full_rows']} duplicate full rows"
        )
        print("  Candidate columns:", summary["candidate_columns"])
    print(f"Audit JSON written to: {output}")


if __name__ == "__main__":
    main()

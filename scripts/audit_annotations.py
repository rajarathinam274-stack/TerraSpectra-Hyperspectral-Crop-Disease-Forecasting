"""Audit the verified source annotation schemas and acquisition count tables."""
from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
METADATA_DIR = ROOT / "data" / "metadata"
try:
    from .metadata_utils import parse_count_table, read_source_metadata_csv, selected_metadata_csv_paths
except ImportError:
    from metadata_utils import parse_count_table, read_source_metadata_csv, selected_metadata_csv_paths

COLUMN_HINTS = {
    "identity_or_grouping": ("leaf", "plant", "pot", "sample", "image", "side", "replicate", "specimen", "barcode", "id"),
    "time_or_acquisition": ("date", "day", "dpi", "time", "acquisition"),
    "label_or_treatment": ("infection", "infected", "disease", "status", "treatment", "label", "class", "condition"),
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


def count_table_profile(path: Path) -> dict:
    long = parse_count_table(path)
    statuses = long["acquisition_status"].value_counts().to_dict()
    return {
        "pot_count": int(long["pot_id"].nunique()),
        "dpi_values": sorted(long["dpi"].unique().tolist()),
        "records": int(len(long)),
        "observed_count_cells": int((long["acquisition_status"] == "observed_count").sum()),
        "leaf_count_sum": int(long["leaf_count"].sum(skipna=True)),
        "status_counts": {str(k): int(v) for k, v in statuses.items()},
    }


def summarize_csv(path: Path) -> dict:
    frame = read_source_metadata_csv(path)
    columns = []
    for name in frame.columns:
        series = frame[name]
        columns.append({
            "name": str(name),
            "dtype": str(series.dtype),
            "missing": int(series.isna().sum()),
            "unique_non_null": int(series.nunique(dropna=True)),
        })
    summary = {
        "filename": path.name,
        "rows": int(frame.shape[0]),
        "column_count": int(frame.shape[1]),
        "columns": columns,
        "duplicate_full_rows": int(frame.duplicated().sum()),
        "candidate_columns": candidate_columns(frame.columns),
    }
    if path.name == "Data_description.csv":
        pot, side, leaf, genotype, treatment, confidence = frame.columns
        keys = frame[[pot, side, leaf]]
        summary["leaf_identity_table_profile"] = {
            "unique_pots": int(frame[pot].nunique()),
            "side_counts": {str(k): int(v) for k, v in frame[side].value_counts().to_dict().items()},
            "unique_pot_side_leaf_keys": int(keys.drop_duplicates().shape[0]),
            "duplicate_pot_side_leaf_keys": int(keys.duplicated().sum()),
            "genotype_counts": {str(k): int(v) for k, v in frame[genotype].value_counts().to_dict().items()},
            "treatment_assignment_counts": {str(k): int(v) for k, v in frame[treatment].value_counts().to_dict().items()},
            "confidence_level_counts": {str(k): int(v) for k, v in frame[confidence].value_counts().to_dict().items()},
            "warning": "This static table has no acquisition timestamp; treatment and confidence are not date-specific symptom outcomes.",
        }
    else:
        summary["acquisition_count_table_profile"] = count_table_profile(path)
    return summary


def compare_modalities(vnir_path: Path, swir_path: Path) -> dict:
    vnir = parse_count_table(vnir_path)
    swir = parse_count_table(swir_path)
    keys = ["pot_id", "dpi", "side"]
    merged = vnir.merge(swir, on=keys, suffixes=("_vnir", "_swir"), how="outer", indicator=True)
    count_diff = merged["leaf_count_vnir"].fillna(-1).ne(merged["leaf_count_swir"].fillna(-1))
    mismatch = (
        merged["_merge"].ne("both")
        | merged["acquisition_status_vnir"].ne(merged["acquisition_status_swir"])
        | count_diff
        | merged["genotype_vnir"].ne(merged["genotype_swir"])
        | merged["treatment_assignment_vnir"].ne(merged["treatment_assignment_swir"])
    )
    records = merged.loc[mismatch, [
        "pot_id", "dpi", "side", "leaf_count_vnir", "leaf_count_swir",
        "acquisition_status_vnir", "acquisition_status_swir",
    ]].to_dict("records")
    return {
        "matched_pot_dpi_side_keys": int((merged["_merge"] == "both").sum()),
        "mismatch_count": int(mismatch.sum()),
        "mismatch_records": records,
        "warning": "Count-level matching is not proof that individual VNIR/SWIR leaf ROIs are registered.",
    }


def main() -> None:
    paths = selected_metadata_csv_paths(METADATA_DIR)
    summaries = {path.name: summarize_csv(path) for path in paths}
    comparison = {}
    if "VNIR_data.csv" in summaries and "SWIR_data.csv" in summaries:
        comparison["VNIR_data.csv__vs__SWIR_data.csv"] = compare_modalities(
            METADATA_DIR / "VNIR_data.csv", METADATA_DIR / "SWIR_data.csv"
        )
    audit = {
        "source": "Recherche Data Gouv DOI 10.57745/WVP0FJ, dataset version 1",
        "files": summaries,
        "spectral_count_table_comparison": comparison,
        "interpretation_warning": (
            "The source CSVs are semicolon-delimited CP1252 tables. The VNIR/SWIR files are "
            "pot/date/side acquisition-count matrices, not individual leaf spectra or symptom labels. "
            "Verify biological identities, ROI registration and timestamp semantics before modelling."
        ),
    }
    output = METADATA_DIR / "annotation_audit.json"
    output.write_text(json.dumps(audit, indent=2, ensure_ascii=False), encoding="utf-8")
    for filename, summary in summaries.items():
        print(f"{filename}: {summary['rows']} rows x {summary['column_count']} columns")
    print(f"Audit JSON written to: {output}")


if __name__ == "__main__":
    main()

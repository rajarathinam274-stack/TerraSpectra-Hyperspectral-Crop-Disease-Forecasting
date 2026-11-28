"""Build a pot/DPI/side acquisition-count inventory, not a leaf identity map."""
from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
METADATA_DIR = ROOT / "data" / "metadata"
try:
    from .metadata_utils import parse_count_table
except ImportError:
    from metadata_utils import parse_count_table


def summarize_table(path: Path) -> tuple[pd.DataFrame, dict]:
    long = parse_count_table(path)
    statuses = long["acquisition_status"].value_counts().to_dict()
    summary = {
        "file": path.name,
        "modality": path.stem.replace("_data", "").upper(),
        "pot_count": int(long["pot_id"].nunique()),
        "dpi_values": sorted(long["dpi"].unique().tolist()),
        "records": int(len(long)),
        "observed_count_cells": int((long["acquisition_status"] == "observed_count").sum()),
        "leaf_count_sum": int(long["leaf_count"].sum(skipna=True)),
        "status_counts": {str(k): int(v) for k, v in statuses.items()},
    }
    return long, summary


def compare_modalities(vnir: pd.DataFrame, swir: pd.DataFrame) -> dict:
    keys = ["pot_id", "dpi", "side"]
    merged = vnir.merge(swir, on=keys, suffixes=("_vnir", "_swir"), how="outer", indicator=True)
    mismatch = (
        merged["_merge"].ne("both")
        | merged["acquisition_status_vnir"].ne(merged["acquisition_status_swir"])
        | merged["leaf_count_vnir"].ne(merged["leaf_count_swir"])
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
    paths = [METADATA_DIR / name for name in ("VNIR_data.csv", "SWIR_data.csv")]
    missing = [path.name for path in paths if not path.is_file()]
    if missing:
        raise FileNotFoundError(
            "Missing annotation files: " + ", ".join(missing)
            + ". Run scripts/download_metadata.py first."
        )
    long_tables, summaries = {}, {}
    for path in paths:
        long, summary = summarize_table(path)
        long_tables[summary["modality"]] = long
        summaries[path.name] = summary
    output_csv = METADATA_DIR / "sample_map_candidates.csv"
    pd.concat(long_tables.values(), ignore_index=True).to_csv(output_csv, index=False)
    cross = compare_modalities(long_tables["VNIR"], long_tables["SWIR"])
    audit = {
        "source_doi": "10.57745/WVP0FJ",
        "table_summaries": summaries,
        "cross_modality_count_comparison": cross,
        "mapping_unit": "pot_dpi_side_acquisition_count",
        "interpretation": (
            "This inventory records counts of leaves collected at each pot/DPI/side for each modality. "
            "It is not a leaf/image identity map, symptom-label table or registered VNIR/SWIR ROI dataset."
        ),
        "grouping_recommendation": "Keep all dates and both sides of a pot in one validation partition.",
        "forecasting_gate": "No date-specific future symptom labels or stable leaf trajectories are established by these count tables.",
        "outputs": {"candidate_map_csv": str(output_csv.relative_to(ROOT))},
    }
    output_json = METADATA_DIR / "sample_map_audit.json"
    output_json.write_text(json.dumps(audit, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"Count inventory rows written: {len(pd.concat(long_tables.values()))} -> {output_csv}")
    print(f"Audit written: {output_json}")
    print("Review count-level differences and verify individual ROI registration before fusion/modeling.")


if __name__ == "__main__":
    main()

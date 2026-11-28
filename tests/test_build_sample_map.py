from pathlib import Path

from scripts.build_sample_map import compare_modalities, summarize_table


def _write_count_table(path: Path, counts: str):
    path.write_text(
        "title;;;;;;;;\n;;;;;;;;\n"
        ";;Date (dpi) [1];-1;;0;\n"
        "Pot [2];Genotype [3];Treatment [4];G [5];D [6];G;D\n"
        + counts,
        encoding="cp1252",
    )


def test_long_inventory_summary_and_modality_mismatch(tmp_path):
    vnir = tmp_path / "VNIR_data.csv"
    swir = tmp_path / "SWIR_data.csv"
    _write_count_table(vnir, "01;EPO_68;Infected;2;1;3;2\n")
    _write_count_table(swir, "01;EPO_68;Infected;2;1;3;1\n")
    long_vnir, summary = summarize_table(vnir)
    long_swir, _ = summarize_table(swir)
    assert summary["records"] == 4
    assert summary["pot_count"] == 1
    assert summary["leaf_count_sum"] == 8
    comparison = compare_modalities(long_vnir, long_swir)
    assert comparison["matched_pot_dpi_side_keys"] == 4
    assert comparison["mismatch_count"] == 1
    assert comparison["mismatch_records"][0]["dpi"] == 0
    assert comparison["mismatch_records"][0]["side"] == "D"

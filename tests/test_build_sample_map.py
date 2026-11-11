import pandas as pd

from scripts.build_sample_map import (
    candidate_record,
    find_column,
    parse_date_token,
    parse_pot_side_token,
)


def test_parse_date_and_pot_side_from_documented_folder_pattern():
    assert parse_date_token("20210311/45_G/image.hyspex") == "2021-03-11"
    assert parse_pot_side_token("20210311/45_G/image.hyspex") == ("45", "G")


def test_candidate_record_keeps_explicit_fields_separate_from_inferred_tokens():
    row = pd.Series({
        "Folder": "20210311/45_G",
        "Image_File": "image_001.hyspex",
        "Treatment": "Infected",
    })
    columns = {
        "date": None, "pot": None, "side": None, "genotype": None,
        "treatment": "Treatment", "image": "Image_File",
        "leaf": None, "plant": None,
    }
    result = candidate_record(row, columns, "VNIR", "VNIR_data.csv", 1)
    assert result["date_iso_candidate"] == "2021-03-11"
    assert result["pot_id_candidate"] == "45"
    assert result["side_candidate"] == "G"
    assert result["treatment_explicit"] == "Infected"
    assert result["leaf_identifier_explicit"] == ""


def test_column_detection_does_not_invent_missing_leaf_id():
    assert find_column(["Date", "Pot", "Treatment"], "leaf") is None
def test_combined_pot_side_column_is_not_misreported_as_separate_fields():
    assert find_column(["NUM_SIDE"], "pot") is None
    assert find_column(["NUM_SIDE"], "side") is None

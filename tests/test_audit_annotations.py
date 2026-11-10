from scripts.audit_annotations import candidate_columns


def test_candidate_columns_are_hints_not_fixed_schema():
    columns = [
        "plant_pot", "leaf_id", "acquisition_date",
        "infection_status", "genotype_name", "reflectance",
    ]
    hints = candidate_columns(columns)

    assert "plant_pot" in hints["identity_or_grouping"]
    assert "leaf_id" in hints["identity_or_grouping"]
    assert "acquisition_date" in hints["time_or_acquisition"]
    assert "infection_status" in hints["label_or_treatment"]
    assert "genotype_name" in hints["genotype_or_cultivar"]
    assert "reflectance" not in hints["label_or_treatment"]

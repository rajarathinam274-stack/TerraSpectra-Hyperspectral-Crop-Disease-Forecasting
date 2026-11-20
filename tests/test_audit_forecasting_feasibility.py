import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from audit_forecasting_feasibility import audit_table


def valid_table():
    rows = []
    for pot, status in [("P01", 0), ("P02", 1), ("P03", 0), ("P04", 1)]:
        for dpi in [1, 4, 7]:
            rows.append({
                "pot_id_candidate": pot,
                "observation_date": f"2026-01-{dpi:02d}",
                "dpi": dpi,
                "future_symptom_status": status,
                "future_assessment_date": f"2026-01-{dpi + 3:02d}",
                "symptom_assessment_method": "visual_pathologist",
                "symptom_status_at_origin": "asymptomatic",
                "treatment_assignment": "infected" if status else "control",
            })
    return pd.DataFrame(rows)


def run(df, **kwargs):
    return audit_table(df, target_semantics="future_symptom_status", **kwargs)


def test_valid_future_symptom_table_is_only_conditionally_eligible():
    report = run(valid_table())
    assert report["decision"] == "CONDITIONALLY_ELIGIBLE_FOR_SPLIT_DESIGN"
    assert report["checks"]["independent_pots"] == 4


def test_missing_future_outcome_fields_is_no_go():
    df = valid_table().drop(columns=["future_symptom_status", "future_assessment_date"])
    report = run(df)
    assert report["decision"] == "NO_GO"
    assert "future_symptom_status" in report["missing_columns"]


def test_treatment_assignment_semantics_is_rejected():
    report = audit_table(valid_table(), target_semantics="treatment_assignment")
    assert report["decision"] == "NO_GO"
    assert any("not forecasts" in reason for reason in report["reasons"])


def test_target_must_be_assessed_after_fixed_horizon():
    df = valid_table()
    df.loc[0, "future_assessment_date"] = df.loc[0, "observation_date"]
    report = run(df, horizon_days=3)
    assert report["decision"] == "NO_GO"
    assert any("horizon" in reason for reason in report["reasons"])


def test_duplicate_pot_time_rows_are_rejected():
    df = valid_table()
    df = pd.concat([df, df.iloc[[0]]], ignore_index=True)
    report = run(df)
    assert report["decision"] == "NO_GO"
    assert any("Duplicate pot/observation-time" in reason for reason in report["reasons"])


def test_insufficient_repeated_pot_coverage_is_rejected():
    df = valid_table()
    df = df[df["observation_date"] == "2026-01-01"]
    report = run(df, min_repeated_group_fraction=0.8)
    assert report["decision"] == "NO_GO"
    assert any("repeated observations" in reason for reason in report["reasons"])


def test_missing_assessment_method_is_rejected():
    df = valid_table()
    df.loc[0, "symptom_assessment_method"] = ""
    report = run(df)
    assert report["decision"] == "NO_GO"
    assert any("assessment method" in reason for reason in report["reasons"])


def test_symptomatic_prediction_origin_is_not_pre_symptomatic():
    df = valid_table()
    df.loc[0, "symptom_status_at_origin"] = "symptomatic"
    report = run(df)
    assert report["decision"] == "NO_GO"
    assert any("symptom-negative" in reason for reason in report["reasons"])


def test_future_target_identical_to_treatment_is_rejected():
    df = valid_table()
    df["future_symptom_status"] = df["treatment_assignment"]
    report = run(df)
    assert report["decision"] == "NO_GO"
    assert any("reproduce treatment assignment" in reason for reason in report["reasons"])

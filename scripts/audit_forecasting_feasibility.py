"""Fail-closed audit for a genuine future symptom-status forecasting table.

This script audits data prerequisites only. It does not train a model.
Treatment assignment is explicitly not accepted as a future disease outcome.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import pandas as pd

DEFAULTS = {
    "group_column": "pot_id_candidate",
    "observation_time_column": "observation_date",
    "dpi_column": "dpi",
    "target_column": "future_symptom_status",
    "target_time_column": "future_assessment_date",
    "assessment_method_column": "symptom_assessment_method",
    "baseline_status_column": "symptom_status_at_origin",
    "treatment_column": "treatment_assignment",
}


def audit_table(
    df: pd.DataFrame,
    *,
    target_semantics: str,
    horizon_days: int = 3,
    min_repeated_group_fraction: float = 0.8,
    **columns: str,
) -> dict:
    """Return a fail-closed feasibility report for future symptom prediction."""
    cfg = {**DEFAULTS, **columns}
    group = cfg["group_column"]
    obs_time = cfg["observation_time_column"]
    dpi = cfg["dpi_column"]
    target = cfg["target_column"]
    target_time = cfg["target_time_column"]
    method = cfg["assessment_method_column"]
    baseline_status = cfg["baseline_status_column"]
    treatment = cfg["treatment_column"]

    required = [group, obs_time, dpi, target, target_time, method, baseline_status]
    missing = [c for c in required if c not in df.columns]
    reasons: list[str] = []
    if missing:
        reasons.append(f"Missing required future-forecast fields: {missing}")
    if target_semantics != "future_symptom_status":
        reasons.append(
            "Target semantics must be future_symptom_status; treatment assignment, "
            "same-date infection class, and date-wise discrimination are not forecasts."
        )
    if target == treatment or target.lower() in {"treatment", "inoculation", "treatment_assignment"}:
        reasons.append("The selected target is treatment/inoculation assignment, not a future symptom outcome.")
    if horizon_days < 1:
        reasons.append("Forecast horizon must be at least one day.")
    if not 0 < min_repeated_group_fraction <= 1:
        reasons.append("min_repeated_group_fraction must be in (0, 1].")

    report = {
        "decision": "NO_GO",
        "analysis": "future symptom-status forecasting feasibility audit only; no model trained",
        "target_semantics": target_semantics,
        "horizon_days": horizon_days,
        "columns": cfg,
        "missing_columns": missing,
        "rows": int(len(df)),
        "reasons": reasons.copy(),
        "checks": {},
        "next_requirements": [
            "Stable pot identifier repeated across acquisition dates.",
            "Independently assessed symptom status at a timestamp later than each prediction origin.",
            "Documented assessment method/assessor and symptom scoring definition.",
            "A pre-symptomatic prediction cohort: symptom-negative at the prediction origin.",
            "Chronological evaluation with pot groups held out for new-pot generalization.",
        ],
    }
    if missing:
        return report

    work = df[required + ([treatment] if treatment in df.columns and treatment not in required else [])].copy()
    for col in [group, target, method, baseline_status]:
        work[col] = work[col].astype("string").str.strip()
        if work[col].isna().any() or work[col].eq("").any():
            reasons.append(f"Blank or missing values in {col}.")

    work[obs_time] = pd.to_datetime(work[obs_time], errors="coerce", utc=True)
    work[target_time] = pd.to_datetime(work[target_time], errors="coerce", utc=True)
    work[dpi] = pd.to_numeric(work[dpi], errors="coerce")
    if work[obs_time].isna().any() or work[target_time].isna().any():
        reasons.append("Observation and future-assessment timestamps must parse as dates.")
    if work[dpi].isna().any() or not work[dpi].map(lambda x: abs(float(x)) < float("inf")).all():
        reasons.append("DPI must contain finite numeric values.")

    if not work[[group, obs_time]].duplicated().any():
        report["checks"]["unique_group_observation_time"] = True
    else:
        report["checks"]["unique_group_observation_time"] = False
        reasons.append("Duplicate pot/observation-time rows found; aggregate views/ROIs before auditing.")

    if work[target].notna().all():
        classes = sorted(work[target].astype(str).unique().tolist())
        report["checks"]["future_target_classes"] = classes
        if len(classes) < 2:
            reasons.append("Future symptom target has fewer than two observed classes.")
    else:
        reasons.append("Future symptom target contains missing labels.")

    if work[method].notna().all() and work[method].astype(str).str.strip().ne("").all():
        report["checks"]["assessment_methods"] = sorted(work[method].astype(str).unique().tolist())
    else:
        reasons.append("Independent symptom-assessment method is missing for one or more target labels.")

    symptom_free_values = {"0", "false", "no", "asymptomatic", "absent", "none", "symptom_free"}
    baseline_values = set(work[baseline_status].astype(str).str.strip().str.lower())
    report["checks"]["baseline_symptom_status_values"] = sorted(baseline_values)
    if not baseline_values or not baseline_values.issubset(symptom_free_values):
        reasons.append("Pre-symptomatic forecasting requires every prediction origin to be independently symptom-negative.")

    if work[obs_time].notna().all() and work[target_time].notna().all():
        gaps = (work[target_time] - work[obs_time]).dt.total_seconds() / 86400.0
        report["checks"]["minimum_observed_target_gap_days"] = float(gaps.min())
        if (gaps < horizon_days).any():
            reasons.append(
                f"At least one target is assessed less than the required {horizon_days}-day horizon after its predictor."
            )

    group_dates = work.groupby(group, dropna=False)[obs_time].nunique()
    repeated_fraction = float((group_dates >= 2).mean()) if len(group_dates) else 0.0
    report["checks"]["independent_pots"] = int(work[group].nunique())
    report["checks"]["repeated_pot_fraction"] = repeated_fraction
    if repeated_fraction < min_repeated_group_fraction:
        reasons.append(
            f"Only {repeated_fraction:.1%} of pots have repeated observations; "
            f"required at least {min_repeated_group_fraction:.1%}."
        )

    if work[dpi].notna().all():
        ordered = work.sort_values([group, obs_time])
        monotone = ordered.groupby(group)[dpi].apply(lambda s: s.is_monotonic_increasing).all()
        report["checks"]["dpi_monotonic_within_pot"] = bool(monotone)
        if not monotone:
            reasons.append("DPI is not monotonic with observation time within every pot.")

    if treatment in work.columns:
        report["checks"]["treatment_assignments_available"] = True
        report["checks"]["target_is_distinct_column_from_treatment"] = target != treatment
        if target == treatment:
            reasons.append("Future target aliases the known treatment-assignment column.")
        elif work[target].astype(str).reset_index(drop=True).equals(work[treatment].astype(str).reset_index(drop=True)):
            reasons.append("Future target values exactly reproduce treatment assignment; this is not a future symptom outcome.")

    report["reasons"] = reasons
    report["decision"] = "CONDITIONALLY_ELIGIBLE_FOR_SPLIT_DESIGN" if not reasons else "NO_GO"
    if not reasons:
        report["warning"] = (
            "Passing this schema audit is not proof that labels are biologically valid. "
            "Manually verify the scoring protocol and pre-symptomatic eligibility before modeling."
        )
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input-csv", required=True)
    parser.add_argument("--output-json", required=True)
    parser.add_argument("--target-semantics", required=True)
    parser.add_argument("--horizon-days", type=int, default=3)
    parser.add_argument("--group-column", default=DEFAULTS["group_column"])
    parser.add_argument("--observation-time-column", default=DEFAULTS["observation_time_column"])
    parser.add_argument("--dpi-column", default=DEFAULTS["dpi_column"])
    parser.add_argument("--target-column", default=DEFAULTS["target_column"])
    parser.add_argument("--target-time-column", default=DEFAULTS["target_time_column"])
    parser.add_argument("--assessment-method-column", default=DEFAULTS["assessment_method_column"])
    parser.add_argument("--baseline-status-column", default=DEFAULTS["baseline_status_column"])
    parser.add_argument("--treatment-column", default=DEFAULTS["treatment_column"])
    args = parser.parse_args()
    df = pd.read_csv(args.input_csv, low_memory=False)
    report = audit_table(
        df,
        target_semantics=args.target_semantics,
        horizon_days=args.horizon_days,
        group_column=args.group_column,
        observation_time_column=args.observation_time_column,
        dpi_column=args.dpi_column,
        target_column=args.target_column,
        target_time_column=args.target_time_column,
        assessment_method_column=args.assessment_method_column,
        baseline_status_column=args.baseline_status_column,
        treatment_column=args.treatment_column,
    )
    path = Path(args.output_json)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(report, indent=2))
    return 0 if report["decision"] == "CONDITIONALLY_ELIGIBLE_FOR_SPLIT_DESIGN" else 2


if __name__ == "__main__":
    raise SystemExit(main())

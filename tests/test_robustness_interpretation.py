import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

import json
import numpy as np
import pandas as pd
import pytest
from robustness_interpretation import RobustnessError, bands_from, prepare, run

DATE, GROUP = "date_folder_yyyymmdd_candidate", "pot_id_candidate"

def make_table(tmp_path, n=10):
    rng = np.random.default_rng(17); rows = []
    for label_i, label in enumerate(["Control", "Inoculated"]):
        for i in range(n):
            pot = f"{label_i*n+i+1:02d}"; signal = float(label_i)
            for date in ["20210311", "20210320"]:
                rows.append({GROUP: pot, DATE: date, "treatment": label,
                    "band_010": rng.normal(0, .2), "band_002": signal*.7+rng.normal(0,.1),
                    "band_001": signal+rng.normal(0,.08)})
    path = tmp_path / "pot_date.csv"; pd.DataFrame(rows).to_csv(path, index=False); return path

def test_band_order_is_numeric():
    assert bands_from(["band_010", "band_002", "band_001"]) == ["band_001", "band_002", "band_010"]

def test_duplicate_pot_date_is_rejected(tmp_path):
    f = pd.read_csv(make_table(tmp_path), dtype={GROUP:str, DATE:str}); f = pd.concat([f, f.iloc[[0]]])
    with pytest.raises(RobustnessError, match="one aggregated pot-date"):
        prepare(f, "treatment", "20210311", DATE, GROUP, "treatment_assignment")

def test_treatment_label_drift_is_rejected(tmp_path):
    f = pd.read_csv(make_table(tmp_path), dtype={GROUP:str, DATE:str})
    f.loc[(f[GROUP]=="01") & (f[DATE]=="20210320"), "treatment"] = "Inoculated"
    with pytest.raises(RobustnessError, match="changes within a pot"):
        prepare(f, "treatment", "20210311", DATE, GROUP, "treatment_assignment")

def test_grouped_run_writes_auditable_outputs(tmp_path):
    out = tmp_path / "out"
    report = run(make_table(tmp_path), out, target_column="treatment", target_semantics="treatment_assignment",
        date_value="20210311", n_splits=5, permutation_repeats=2, noise_repeats=2, random_state=42)
    assert report["task"] == "same_date_classification" and report["group_overlap"] is False
    assert report["n_independent_pots"] == 20 and "not symptom detection" in report["target_interpretation"]
    for name in ["oof_predictions.csv", "fold_metrics.csv", "permutation_importance.csv",
                 "band_ablation.csv", "noise_sensitivity.csv", "robustness_report.json"]:
        assert (out/name).exists()
    oof = pd.read_csv(out/"oof_predictions.csv", dtype={GROUP:str})
    assert len(oof)==20 and oof[GROUP].nunique()==20 and oof.fold.between(1,5).all()
    saved = json.loads((out/"robustness_report.json").read_text())
    assert saved["pooled_oof_metrics"]["macro_f1"] == pytest.approx(report["pooled_oof_metrics"]["macro_f1"])

def test_requires_five_independent_groups_per_class(tmp_path):
    with pytest.raises(RobustnessError, match="at least 5 independent pots"):
        run(make_table(tmp_path, n=4), tmp_path/"out", target_column="treatment",
            target_semantics="treatment_assignment", date_value="20210311", n_splits=5)

def test_negative_noise_fraction_is_rejected(tmp_path):
    with pytest.raises(RobustnessError, match="noise_sd_fraction"):
        run(make_table(tmp_path), tmp_path/"out", target_column="treatment",
            target_semantics="treatment_assignment", date_value="20210311", noise_sd_fraction=-.1)

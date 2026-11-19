import sys
from pathlib import Path
import numpy as np
import pandas as pd
import pytest
sys.path.insert(0, str(Path(__file__).resolve().parents[1]/"scripts"))
from analyze_early_detection import run

def fixture():
    rng=np.random.default_rng(4); rows=[]
    dates={"20210311":-1,"20210312":0,"20210316":4,"20210320":8}
    for i in range(20):
        pot=f"{i+1:02d}"; label="infected" if i<10 else "control"
        for date,dpi in dates.items():
            v=rng.normal(.3 if label=="infected" else 0,.1,4)
            rows.append({"pot_id_candidate":pot,"date_folder_yyyymmdd_candidate":date,
                         "dpi":dpi,"treatment":label,**{f"band_{j:03d}":v[j] for j in range(4)}})
    return pd.DataFrame(rows)

def test_datewise_oof_and_shared_pot_folds(tmp_path):
    f=fixture(); src=tmp_path/"x.csv"; f.to_csv(src,index=False)
    r=run(src,tmp_path/"out",target="treatment",dpi_column="dpi",n_splits=5,bootstrap_reps=100)
    o=pd.read_csv(tmp_path/"out"/"oof_predictions_by_date.csv",dtype={"pot_id_candidate":str})
    assert len(r["date_results"])==4 and len(o)==80
    assert o.groupby("pot_id_candidate").fold.nunique().max()==1
    assert all(x.get("symptom_status")=="not_assessed" for x in r["date_results"] if x.get("scorable"))
    assert (tmp_path/"out"/"date_performance.png").is_file()

def test_duplicate_pot_date_rejected(tmp_path):
    f=fixture(); f=pd.concat([f,f.iloc[[0]]]); src=tmp_path/"x.csv"; f.to_csv(src,index=False)
    with pytest.raises(ValueError,match="Duplicate pot-date"):
        run(src,tmp_path/"out",target="treatment",dpi_column="dpi",bootstrap_reps=100)

def test_treatment_drift_rejected(tmp_path):
    f=fixture(); f.loc[(f.pot_id_candidate=="01")&(f.date_folder_yyyymmdd_candidate=="20210320"),"treatment"]="control"
    src=tmp_path/"x.csv"; f.to_csv(src,index=False)
    with pytest.raises(ValueError,match="changes within pot"):
        run(src,tmp_path/"out",target="treatment",dpi_column="dpi",bootstrap_reps=100)

def test_invalid_dpi_order_rejected(tmp_path):
    f=fixture(); f.loc[f.date_folder_yyyymmdd_candidate=="20210312","dpi"]=-2
    src=tmp_path/"x.csv"; f.to_csv(src,index=False)
    with pytest.raises(ValueError,match="strictly increasing"):
        run(src,tmp_path/"out",target="treatment",dpi_column="dpi",bootstrap_reps=100)

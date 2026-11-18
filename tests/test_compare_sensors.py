import json
import numpy as np
import pandas as pd
import pytest
from scripts.compare_sensors import (
    SensorComparisonError, load_matched, load_axis, make_features, run
)

def fixture(tmp_path, pots=20):
    rng = np.random.default_rng(7)
    vrows, srows = [], []
    for i in range(pots):
        pot = f"{i+1:02d}"
        label = "infected" if i < pots//2 else "control"
        for date in ["20210311", "20210312"]:
            base = 0.7 if label == "infected" else -0.7
            v = rng.normal(base, .3, 4); s = rng.normal(base*.8, .3, 5)
            common = {"pot_id_candidate":pot,"date_folder_yyyymmdd_candidate":date,
                      "treatment":label,"genotype":"EPO_067" if i%2==0 else "EPO_068"}
            vrows.append({**common,**{f"band_{j:03d}":v[j] for j in range(4)}})
            srows.append({**common,**{f"band_{j:03d}":s[j] for j in range(5)}})
    vcsv, scsv = tmp_path/"vnir.csv", tmp_path/"swir.csv"
    pd.DataFrame(vrows).to_csv(vcsv,index=False); pd.DataFrame(srows).to_csv(scsv,index=False)
    va, sa = tmp_path/"va.json", tmp_path/"sa.json"
    va.write_text(json.dumps({"modality":"VNIR","spectral_axes_by_image":{
        "v1":{"wavelengths_nm":[410,600,800,990]},"v2":{"wavelengths_nm":[410,600,800,990]}}}))
    sa.write_text(json.dumps({"modality":"SWIR","spectral_axes_by_image":{
        "s1":{"wavelengths_nm":[960,1200,1600,2000,2490]},"s2":{"wavelengths_nm":[960,1200,1600,2000,2490]}}}))
    return vcsv,scsv,va,sa

def load(v,s):
    return load_matched(v,s,target="treatment",semantics="treatment_assignment",
                        date_value="20210312",genotype_col="genotype")

def test_exact_matching_and_group_counts(tmp_path):
    v,s,_,_=fixture(tmp_path); d=load(v,s)
    assert d["matched_pots"]==20
    assert d["class_counts"]=={"control":10,"infected":10}
    assert d["X_vnir"].shape==(20,4) and d["X_swir"].shape==(20,5)

def test_unmatched_keys_rejected_and_leading_zeroes_preserved(tmp_path):
    v,s,_,_=fixture(tmp_path)
    sw=pd.read_csv(s,dtype={"pot_id_candidate":"string","date_folder_yyyymmdd_candidate":"string"})
    sw=sw[sw.pot_id_candidate!="01"]; sw.to_csv(s,index=False)
    with pytest.raises(SensorComparisonError,match="keys differ"): load(v,s)

def test_label_disagreement_rejected(tmp_path):
    v,s,_,_=fixture(tmp_path)
    sw=pd.read_csv(s,dtype={"pot_id_candidate":"string","date_folder_yyyymmdd_candidate":"string"})
    sw.loc[sw.pot_id_candidate=="01","treatment"]="control"; sw.to_csv(s,index=False)
    with pytest.raises(SensorComparisonError,match="annotations disagree"): load(v,s)

def test_duplicate_pot_date_rejected(tmp_path):
    v,s,_,_=fixture(tmp_path)
    vf=pd.read_csv(v,dtype={"pot_id_candidate":"string","date_folder_yyyymmdd_candidate":"string"})
    vf=pd.concat([vf,vf.iloc[[1]]],ignore_index=True); vf.to_csv(v,index=False)
    with pytest.raises(SensorComparisonError,match="one pot-date row"): load(v,s)

def test_treatment_assignment_constant_across_dates(tmp_path):
    v,s,_,_=fixture(tmp_path)
    vf=pd.read_csv(v,dtype={"pot_id_candidate":"string","date_folder_yyyymmdd_candidate":"string"})
    vf.loc[(vf.pot_id_candidate=="01") & (vf.date_folder_yyyymmdd_candidate=="20210311"),"treatment"]="control"
    vf.to_csv(v,index=False)
    with pytest.raises(SensorComparisonError,match="treatment-assignment label changes"): load(v,s)

def test_wavelength_axis_consistency(tmp_path):
    v,s,va,sa=fixture(tmp_path)
    axis,info=load_axis(va,"VNIR",4); assert len(axis)==4 and info["image_count"]==2
    a=json.loads(va.read_text()); a["spectral_axes_by_image"]["v2"]["wavelengths_nm"]=[410,590,800,990]
    va.write_text(json.dumps(a))
    with pytest.raises(SensorComparisonError,match="axes differ"): load_axis(va,"VNIR",4)

def test_fusion_uses_nonoverlapping_union(tmp_path):
    v,s,va,sa=fixture(tmp_path); d=load(v,s)
    vx,_=load_axis(va,"VNIR",4); sx,_=load_axis(sa,"SWIR",5)
    sets,info=make_features(d,vx,sx,.5)
    assert sets["FUSION_NONOVERLAP"].shape[1]==8
    assert info["swir_bands_excluded"]==["band_000"]
    assert info["swir_bands_retained"]==["band_001","band_002","band_003","band_004"]

def test_end_to_end_shared_group_folds_and_outputs(tmp_path):
    v,s,va,sa=fixture(tmp_path); out=tmp_path/"out"
    report=run(v,s,va,sa,out,target="treatment",semantics="treatment_assignment",
               date_value="20210312",genotype_col="genotype",n_splits=5,random_state=42)
    assert set(report["metrics"])=={"VNIR","SWIR","FUSION_NONOVERLAP"}
    split=pd.read_csv(out/"shared_split_assignments.csv",dtype={"pot_id_candidate":"string"})
    assert split.fold.nunique()==5 and not split.pot_id_candidate.duplicated().any()
    for name in ["vnir","swir","fusion_nonoverlap"]:
        pred=pd.read_csv(out/f"oof_predictions_{name}.csv")
        assert len(pred)==20 and pred.predicted_label.notna().all()
    assert (out/"sensor_comparison_report.json").is_file()

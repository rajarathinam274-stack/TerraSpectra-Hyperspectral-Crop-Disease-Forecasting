"""Date-wise pot-grouped treatment discrimination; not temporal forecasting."""
import argparse, json, re
from pathlib import Path
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from sklearn.impute import SimpleImputer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import accuracy_score, balanced_accuracy_score, f1_score, precision_score, recall_score, roc_auc_score
from sklearn.model_selection import StratifiedGroupKFold
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler

GROUP = "pot_id_candidate"
DATE = "date_folder_yyyymmdd_candidate"
BAND = re.compile(r"^band_(\d+)$")

def run(input_csv, output_dir, *, target, dpi_column, date_column=DATE, group_column=GROUP,
        n_splits=5, random_state=42, bootstrap_reps=1000):
    df = pd.read_csv(input_csv, low_memory=False, dtype={target:"string", date_column:"string", group_column:"string"})
    required = {target, date_column, group_column, dpi_column}
    missing = sorted(required - set(df.columns))
    if missing:
        raise ValueError(f"Missing columns: {missing}")
    for col in [target, date_column, group_column]:
        if df[col].isna().any() or df[col].astype(str).str.strip().eq("").any():
            raise ValueError(f"Missing/blank values in {col}")
        df[col] = df[col].astype(str).str.strip()
    if df.duplicated([group_column, date_column]).any():
        raise ValueError("Duplicate pot-date rows; expected one aggregate per pot/date.")
    if (df.groupby(group_column)[target].nunique() > 1).any():
        raise ValueError("Treatment assignment changes within pot.")
    band_pairs = sorted((int(m.group(1)), c) for c in df.columns if (m := BAND.fullmatch(str(c))))
    if len(band_pairs) < 2 or len({i for i, _ in band_pairs}) != len(band_pairs):
        raise ValueError("At least two unique band_NNN columns are required.")
    bands = [c for _, c in band_pairs]
    X = df[bands].apply(pd.to_numeric, errors="coerce").replace([np.inf, -np.inf], np.nan)
    if X.isna().all().any():
        raise ValueError("At least one spectral band is entirely missing.")
    df[bands] = X
    df["_dpi"] = pd.to_numeric(df[dpi_column], errors="coerce")
    if df["_dpi"].isna().any() or not np.isfinite(df["_dpi"].to_numpy(float)).all():
        raise ValueError("DPI must be finite numeric values.")
    if (df.groupby(date_column)["_dpi"].nunique() != 1).any():
        raise ValueError("Each acquisition date must map to exactly one DPI.")
    dpi = {str(k):float(v) for k,v in df.groupby(date_column)["_dpi"].first().items()}
    ordered = [dpi[k] for k in sorted(dpi)]
    if len(set(ordered)) != len(ordered) or any(a >= b for a,b in zip(ordered, ordered[1:])):
        raise ValueError("DPI values must be unique and strictly increasing by date.")
    pots = df[[group_column, target]].drop_duplicates()
    labels = sorted(pots[target].unique())
    if len(labels) != 2:
        raise ValueError("Day 10 treatment-discrimination baseline requires exactly two treatment classes.")
    counts = pots[target].value_counts()
    if counts.min() < n_splits or df[group_column].nunique() < n_splits:
        raise ValueError(f"Each class needs at least {n_splits} independent pots; counts={counts.to_dict()}")
    splitter = StratifiedGroupKFold(n_splits=n_splits, shuffle=True, random_state=random_state)
    fold_map = {}
    for fold, (_, test_idx) in enumerate(splitter.split(pots, pots[target], pots[group_column]), 1):
        for pot in pots.iloc[test_idx][group_column].astype(str):
            fold_map[pot] = fold
    df["fold"] = df[group_column].astype(str).map(fold_map)
    date_rows, fold_rows, oof_rows = [], [], []
    for date in sorted(dpi, key=lambda x: dpi[x]):
        q = df.loc[df[date_column] == date].copy().reset_index(drop=True)
        y = q[target].astype(str)
        base = {"date":date, "dpi":dpi[date], "pots":int(q[group_column].nunique()),
                "cohort_pots":int(df[group_column].nunique()),
                "coverage":float(q[group_column].nunique()/df[group_column].nunique())}
        if set(y.unique()) != set(labels):
            date_rows.append({**base, "scorable":False, "reason":"one or more classes absent"})
            continue
        pred = np.full(len(q), "", dtype=object)
        prob = np.full((len(q), 2), np.nan)
        local, valid, reason = [], True, ""
        for fold in range(1, n_splits+1):
            train = q["fold"].to_numpy() != fold
            test = q["fold"].to_numpy() == fold
            if not test.any():
                continue
            if set(y[train].unique()) != set(labels) or set(y[test].unique()) != set(labels):
                valid, reason = False, f"fold {fold} lacks a class"
                break
            model = make_pipeline(SimpleImputer(strategy="median", keep_empty_features=True),
                StandardScaler(), LogisticRegression(C=1.0, class_weight="balanced", max_iter=5000,
                                                     random_state=random_state))
            model.fit(q.loc[train, bands], y[train])
            pred[test] = model.predict(q.loc[test, bands])
            raw = model.predict_proba(q.loc[test, bands])
            classes = list(model[-1].classes_)
            prob[test] = np.column_stack([raw[:, classes.index(c)] for c in labels])
            local.append({"date":date, "dpi":dpi[date], "fold":fold,
                          "macro_f1":float(f1_score(y[test], pred[test], average="macro")),
                          "balanced_accuracy":float(balanced_accuracy_score(y[test], pred[test]))})
        if not valid or (pred == "").any() or not np.isfinite(prob).all():
            date_rows.append({**base, "scorable":False, "reason":reason or "incomplete OOF predictions"})
            continue
        fold_rows.extend(local)
        metric = {
            "accuracy":float(accuracy_score(y, pred)),
            "balanced_accuracy":float(balanced_accuracy_score(y, pred)),
            "macro_f1":float(f1_score(y, pred, average="macro")),
            "macro_precision":float(precision_score(y, pred, average="macro", zero_division=0)),
            "macro_recall":float(recall_score(y, pred, average="macro", zero_division=0)),
            "roc_auc":float(roc_auc_score((y.to_numpy()==labels[1]).astype(int), prob[:,1]))
        }
        rng = np.random.default_rng(random_state + abs(int(dpi[date]*1000)))
        class_idx = [np.flatnonzero(y.to_numpy()==c) for c in labels]
        boot = []
        for _ in range(bootstrap_reps):
            idx = np.concatenate([rng.choice(ix, len(ix), replace=True) for ix in class_idx])
            boot.append(f1_score(y.to_numpy()[idx], pred[idx], average="macro", zero_division=0))
        ci = [float(v) for v in np.quantile(boot, [0.025, 0.975])]
        date_rows.append({**base, "scorable":True, **metric, "macro_f1_ci95":ci,
                          "symptom_status":"not_assessed"})
        for i, row in q.iterrows():
            oof_rows.append({group_column:row[group_column], date_column:date, "dpi":dpi[date],
                             target:y.iloc[i], "predicted":pred[i], "fold":int(row["fold"]),
                             f"prob_{labels[0]}":float(prob[i,0]), f"prob_{labels[1]}":float(prob[i,1])})
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)
    dates = pd.DataFrame(date_rows).sort_values("dpi")
    dates.to_csv(out/"date_metrics.csv", index=False)
    pd.DataFrame(fold_rows).to_csv(out/"date_fold_metrics.csv", index=False)
    pd.DataFrame(oof_rows).to_csv(out/"oof_predictions_by_date.csv", index=False)
    split = pots.copy()
    split["fold"] = split[group_column].astype(str).map(fold_map)
    split.to_csv(out/"shared_pot_fold_assignments.csv", index=False)
    valid = dates.loc[dates.scorable == True] if "scorable" in dates else pd.DataFrame()
    if not valid.empty:
        fig, ax = plt.subplots(figsize=(8,4.5))
        ax.plot(valid.dpi, valid.macro_f1, marker="o")
        ax.fill_between(valid.dpi, [x[0] for x in valid.macro_f1_ci95],
                        [x[1] for x in valid.macro_f1_ci95], alpha=.2)
        ax.set(xlabel="Days post inoculation (DPI)", ylabel="Macro-F1", ylim=(0,1),
               title="Same-date pot-grouped treatment discrimination")
        ax.grid(alpha=.25); fig.tight_layout()
        fig.savefig(out/"date_performance.png", dpi=160); plt.close(fig)
    report = {
        "analysis":"one same-date treatment classifier per acquisition date",
        "target_semantics":"treatment_assignment",
        "interpretation":"Inoculation-assignment spectral discrimination; not symptom detection or future forecasting.",
        "independent_pots":int(df[group_column].nunique()),
        "validation":{"method":"StratifiedGroupKFold", "folds":n_splits,
                      "pot_folds_shared_across_dates":True, "pot_overlap":False,
                      "preprocessing":"median imputation and scaling fitted inside each training fold"},
        "symptom_evidence":"No independent symptom labels supplied; pre-symptomatic status cannot be established.",
        "date_results":date_rows,
        "limitations":["Treatment assignment is known at inoculation, not a future disease outcome.",
                       "Pre-symptomatic status requires independent symptom annotations and full cohort coverage.",
                       "DPI mapping must be verified from source metadata.",
                       "Pot is the validation group; no stable leaf identity is inferred across dates.",
                       "Controlled-environment results are not field validation."]
    }
    (out/"early_detection_report.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    return report

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--input-csv", required=True); p.add_argument("--output-dir", required=True)
    p.add_argument("--target-column", required=True); p.add_argument("--dpi-column", required=True)
    p.add_argument("--date-column", default=DATE); p.add_argument("--group-column", default=GROUP)
    p.add_argument("--n-splits", type=int, default=5); p.add_argument("--random-state", type=int, default=42)
    p.add_argument("--bootstrap-reps", type=int, default=1000); a=p.parse_args()
    r=run(a.input_csv,a.output_dir,target=a.target_column,dpi_column=a.dpi_column,
          date_column=a.date_column,group_column=a.group_column,n_splits=a.n_splits,
          random_state=a.random_state,bootstrap_reps=a.bootstrap_reps)
    print(json.dumps({"independent_pots":r["independent_pots"],"date_results":r["date_results"]},indent=2))
if __name__ == "__main__":
    main()

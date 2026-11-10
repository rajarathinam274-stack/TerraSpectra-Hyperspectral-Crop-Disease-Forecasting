# Day 11 — Disease Progression Prediction Evaluation Readiness

**Roadmap item:** `11 feat: evaluate disease progression prediction`

**Status:** Blocked pending the implementation and dataset artifacts from Days 1–10.

## Verified repository state

Checked on 2026-11-10:

- Branch: `main`
- HEAD: `43f9d47 Initial commit`
- Working tree: clean before this document was added
- Repository contents before this document: an empty `README.md` only
- Available branches: `main` only
- Available tags: none
- Issues and pull requests: none
- No dataset, metadata table, preprocessing code, trained model, predictions, or prior metrics are present

Therefore, no disease-progression result can be computed or reported yet. Reporting an accuracy, F1 score, AUROC, forecast horizon, or temporal gain at this point would be fabricated.

## Evaluation contract to implement when the prior artifacts arrive

Day 11 must evaluate a **future disease state**, not merely classify the disease label of the same observation.

A valid row-level evaluation table should contain at least:

```text
sample_id, plant_id_or_plot_id, acquisition_time, target_time,
features_or_feature_path, current_state, future_state
```

The target must satisfy:

```text
target_time > acquisition_time
```

If the dataset has no repeated observations for the same plant, plot, or field over time, the project can support disease classification but not genuine temporal forecasting. That limitation must be stated explicitly.

### Leakage-safe protocol

1. Sort observations by acquisition time.
2. Define the forecast horizon before fitting the model.
3. Split by time, and by plant/plot/field when those identifiers exist.
4. Fit preprocessing transforms only on the training split.
5. Do not use future labels, post-target spectra, or measurements collected after the prediction timestamp as features.
6. Keep a final untouched test period for the reported result.
7. Compare against a persistence baseline: predict the current disease state as the future state.
8. Report sample counts, class support, confusion matrix, macro-F1, balanced accuracy, and per-class recall. Add AUROC/average precision only when the class support makes them meaningful.
9. Report forecast horizon, split boundaries, missingness, duplicate handling, and confidence intervals or repeated split variability.

### Minimum comparison

The Day 11 report should compare:

- Persistence baseline: future state equals current state.
- A leakage-safe model from the previous day, if one exists.
- Optional progression target such as `future_state != current_state`, only if its definition is documented and clinically/agronomically justified.

The key result is improvement over the persistence baseline on the untouched future period—not performance on randomly mixed samples.

## Reproducible commands once artifacts exist

From the repository root:

```bash
python -m venv .venv
. .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
python -m pytest -q
python -m src.evaluate_progression --config configs/day11.yaml
```

The final command is intentionally not run now because `requirements.txt`, `src/`, `configs/`, the dataset, and a trained model do not exist in this repository.

## Current blocker and next action

**Blocker:** Days 1–10 artifacts are absent from the repository and sandbox.

**Next action:** restore or commit the dataset manifest/metadata, preprocessing pipeline, trained model artifact or training command, and the Day 1–10 roadmap. Then implement the evaluation command above using the actual project interfaces, run it on a leakage-safe time/group split, and commit the verified metrics and methodology.

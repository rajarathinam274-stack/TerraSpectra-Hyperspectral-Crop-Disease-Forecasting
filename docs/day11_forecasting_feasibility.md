# Day 11 — Forecasting feasibility and target audit

## Decision: NO-GO for a disease-outcome forecasting model with the currently documented annotations

The source paper describes a longitudinal experiment, but longitudinal acquisition alone does not provide a supervised future disease target.

### What the source supports

The published experiment contains 48 pots, with 24 pots per genotype (EPO_067 and EPO_068). Within each genotype, 12 pots were inoculated with *Zymoseptoria tritici* and 12 received the control solution. The folder naming convention \`NUM_SIDE\` encodes pot number and the measured side (D/G). Images were acquired on 18 dates from one day before inoculation through 20 days post-inoculation. Six plants per pot were arranged in groups of three on opposite sides. The first ligulated leaf was imaged non-destructively. Per-image CSV files contain leaf pixel coordinates.

This supports reconstructing repeated **pot-level** observations and grouping both sides and all leaves from a pot together. It does not establish persistent individual-leaf IDs across dates: coordinates are image-specific, and the published description does not specify a cross-date leaf identifier.

### What is missing for forecasting

The published annotation directory is described as a general dataset description plus VNIR/SWIR tables containing sample information and leaf counts per image/date. It is not documented as containing baseline symptom-negative status for each prediction origin or a future symptom-status label with its assessment timestamp. The paper reports visual disease monitoring and symptom progression (necrosis from approximately 7 DPI, later pycnidia), but the documented annotation tables are not described as containing an independently assessed symptom-status or severity outcome for every pot/date. The pathogen confirmation assays on selected dates do not, by themselves, create a complete future symptom label for every pot and prediction origin.

Known inoculation assignment is not an acceptable future outcome: it is fixed at inoculation and is available before the first spectral observation. Predicting it at a later date is treatment-discrimination classification, not forecasting disease progression.

Therefore, no genuine future disease-state model is justified until an independent pot/date symptom assessment table is obtained and linked to the pot IDs. Do not manufacture onset labels from the cohort-level statement that symptoms began around 7 DPI.

## Pre-specified forecasting target if outcome records become available

For pot \`p\`, prediction origin \`t\`, and fixed horizon \`h\`:

\`X[p,t] -> Y[p,t+h]\`

\`Y[p,t+h]\` must be an independently assessed symptom state (or severity) at a documented assessment timestamp at least \`h\` days after \`t\`. For a pre-symptomatic task, require symptom-negative status at \`t\`; exclude rows already symptomatic at the prediction origin. Record the scoring method, assessor/pathologist, severity scale, and any uncertainty/confidence code. Do not use treatment assignment as the target.

A three-day horizon is a candidate protocol only; it must be fixed before inspecting model performance and aligned to actual assessment dates. If assessment dates are irregular, define the horizon using the nearest scheduled assessment and report the realized interval.

## Validation design if the missing target is recovered

1. Aggregate both pot sides and all image/leaf ROIs to one pot-origin feature vector; never treat leaves or pixels as independent biological replicates.
2. Keep pot ID as the group. Do not infer leaf identity from image coordinates.
3. Use a chronological cutoff: training outcomes must have been assessed before the cutoff; test prediction origins must occur after the cutoff.
4. Hold out pot IDs for a new-pot generalization estimate. Report the number of independent pots and class counts; with only 48 pots (24 inoculated), uncertainty will be substantial.
5. Fit imputation, scaling, feature selection and dimensionality reduction only inside training folds.
6. Compare against a prevalence-only baseline and report macro-F1, balanced accuracy, sensitivity, specificity, calibration and pot-level confidence intervals.
7. Do not report controlled growth-chamber performance as field validation.

## Audit utility

\`scripts/audit_forecasting_feasibility.py\` fails closed unless the manifest contains a stable pot ID, observation date/DPI, a future symptom-status label, a later outcome-assessment date, a documented assessment method, and symptom-negative status at the prediction origin. It rejects treatment-assignment semantics and duplicate pot/date rows. A pass means only that the table is conditionally eligible for split design; biological label provenance still requires manual review. It does not train a model.

Run on a candidate pot-level manifest:

\`\`\`bash
python scripts/audit_forecasting_feasibility.py \\
  --input-csv data/processed/forecasting_manifest.csv \\
  --output-json reports/day11/forecasting_feasibility.json \\
  --target-semantics future_symptom_status \\
  --horizon-days 3
\`\`\`

Expected result with the currently documented treatment-only table: \`NO_GO\`, because future symptom status, future assessment timestamp, baseline symptom status and assessment-method fields are absent. Do not fabricate these fields to make the audit pass.

## Source

Latchoumane et al. (2025), “Early detection of *Zymoseptoria tritici* infection on wheat leaves using hyperspectral imaging data,” *Data in Brief* 59, 111404. DOI: https://doi.org/10.1016/j.dib.2025.111404. Dataset DOI: https://doi.org/10.57745/WVP0FJ.

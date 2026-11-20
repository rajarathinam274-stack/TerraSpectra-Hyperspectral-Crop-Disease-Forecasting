# Day 11 work log — 2026-11-20

- Reviewed the current \`main\` branch, Day 10 analysis script and 15-day roadmap.
- Reviewed the source paper and repository description for longitudinal identifiers and outcome annotations.
- Decision: no-go for supervised future disease-state forecasting from the currently documented annotations.
- Important distinction: pot identity is recoverable from the \`NUM_SIDE\` folder structure and can support pot-level longitudinal grouping. The documented files do not establish persistent leaf IDs or a complete independent pot/date symptom-status table.
- Added a fail-closed schema/provenance audit utility and nine synthetic tests. The utility requires an independently symptom-negative prediction origin, a future symptom label, later assessment timestamp, and documented assessment method. It does not train a model and rejects treatment assignment as a future target.
- Real-data forecast evaluation was not run. The actual annotation CSVs were not downloaded or checksum-verified in this run. A treatment-only synthetic manifest was passed through the CLI and correctly returned \`NO_GO\` with exit code 2 and the missing future-outcome fields listed.

- Added `.github/workflows/day11-tests.yml` to run the focused feasibility tests on relevant pushes and pull requests. The workflow file is committed; no completed GitHub Actions run/status was available at verification time.

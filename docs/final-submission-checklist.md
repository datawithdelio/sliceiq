# SliceIQ Final Submission Checklist

Use this checklist to confirm the project is ready for submission and demo.

## Latest Validation Snapshot (2026-03-11)

- Notebook order executed: `00 -> 01 -> 02 -> 03 -> 04 -> 05 -> 06 -> 07 -> 08`
- Model version: `v20260311045627`
- Notebook 07 decision: `ship` (`44 pass / 0 warn / 0 fail`)
- Notebook 08 decision: `ship` (`32 pass / 0 warn / 0 fail`)
- Final strict validator: `pass` (`31 pass / 0 warn / 0 fail`)
- Validator artifacts:
  - `ml/data/reports/churn/final_submission_validation.json`
  - `ml/data/reports/churn/final_submission_validation.md`

## Pre-Submit Commands

Run from repo root:

```bash
python -m ml.pipelines.production_preflight
python -m ml.pipelines.causal_decision_gate
python -m ml.pipelines.final_submission_validate --fail-on-warn
```

If final validator fails, fix the failing checks and rerun before submitting.

## Core Acceptance Checks

- [ ] Notebook run order completed and saved:
  - `ml/notebooks/00_data_cleaning.ipynb`
  - `ml/notebooks/01_advanced_eda.ipynb`
  - `ml/notebooks/02_feature_engineering_and_selection.ipynb`
  - `ml/notebooks/03_training_and_evaluation.ipynb`
  - `ml/notebooks/04_causal_inference_ab_did.ipynb`
  - `ml/notebooks/05_cohort_time_series.ipynb`
  - `ml/notebooks/06_deployment_scoring.ipynb`
  - `ml/notebooks/07_production_readiness.ipynb`
  - `ml/notebooks/08_causal_production_decisioning.ipynb`

- [ ] Model quality metrics meet target:
  - Test ROC-AUC >= `0.60`
  - Test PR-AUC >= `0.40`
  - Test Brier <= `0.20`

- [ ] Deployment outputs generated:
  - `ml/data/churn_scoring_latest.csv`
  - `ml/data/churn_scoring_top_watchlist.csv`
  - `ml/data/reports/churn/deployment_scoring_summary.json`

- [ ] Causal outputs generated:
  - `ml/data/reports/causal/ab_test/ab_test_results.json`
  - `ml/data/reports/causal/did/did_results.json`
  - `ml/data/reports/causal/causal_release_decision.json`

- [ ] Cohort/time-series outputs generated:
  - `ml/data/reports/causal/cohort_time_series/cohort_time_series_summary.json`
  - `ml/data/reports/causal/cohort_time_series/cohort_retention_matrix.csv`
  - `ml/data/reports/causal/cohort_time_series/daily_timeseries_metrics.csv`

- [ ] Production readiness outputs generated:
  - `ml/models/release_preflight_report.json`
  - `ml/models/release_preflight_report.md`
  - `ml/data/reports/churn/production_monitoring.json`
  - `ml/data/reports/churn/study_guide_implementation_audit.json`
  - `ml/data/reports/churn/production_readiness_checks.csv`

- [ ] Final strict validation artifacts generated:
  - `ml/data/reports/churn/final_submission_validation.json`
  - `ml/data/reports/churn/final_submission_validation.md`
  - `final_status` in JSON is `pass`

## Data Science Best-Practice Sign-Off

- [ ] No data leakage: train/validation/test split logic preserved.
- [ ] Metrics include discrimination (`ROC-AUC`, `PR-AUC`) and calibration (`Brier`).
- [ ] Cohort and time-series diagnostics reviewed (`cohorts`, `max_period`, anomalies).
- [ ] Watchlist is generated and sorted by highest churn probability.

## SWE Best-Practice Sign-Off

- [ ] Artifact outputs are versioned and reproducible from notebook order.
- [ ] Model version is consistent across metrics and deployment summary.
- [ ] Both production gates are `ship` with zero fails.
- [ ] Final validator passes in strict mode (`--fail-on-warn`).

## Notebook Save Conflict Tip (VS Code)

If VS Code shows:

`Failed to save ... The content of the file is newer. Do you want to overwrite the file with your changes?`

- Click `Overwrite` when you just re-ran the notebook and want to keep the latest outputs.
- Use `Revert` only if you intentionally want to discard your unsaved edits.


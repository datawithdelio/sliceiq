# SliceIQ ML - Killer Project Blueprint

This workspace now includes a full, production-style path for:
- Advanced EDA
- Advanced feature engineering
- Feature selection
- Model training and evaluation
- Deployment-ready scoring

## Flagship Project

**Goal:** predict whether a customer will place another order in the next 30 days (`will_order_next_30d`), then convert that into churn risk (`1 - reorder_probability`).

Why this is strong for your portfolio:
- Uses cohort and time-series logic (point-in-time snapshots).
- Uses behavioral features (RFM, order gaps, promo behavior, cancellation behavior, review quality).
- Supports both batch scoring and API scoring.
- Ties directly to retention and revenue actions in your app.

## Notebook-First Workflow (Recommended)

Open and run notebooks in this order:

1. `ml/notebooks/00_data_cleaning.ipynb`
2. `ml/notebooks/01_advanced_eda.ipynb`
3. `ml/notebooks/02_feature_engineering_and_selection.ipynb`
4. `ml/notebooks/03_training_and_evaluation.ipynb`
5. `ml/notebooks/04_causal_inference_ab_did.ipynb`
6. `ml/notebooks/05_cohort_time_series.ipynb`
7. `ml/notebooks/06_deployment_scoring.ipynb`
8. `ml/notebooks/07_production_readiness.ipynb`
9. `ml/notebooks/08_causal_production_decisioning.ipynb`

This follows common DS best practice:
- clean and validate once,
- then analyze,
- then engineer/select features,
- then train/evaluate,
- then run causal analysis,
- then deploy/score,
- then run production gates for model and causal rollout decisions.

## Pipeline Commands (Script Equivalents)

Run from repo root:

```bash
python -m pip install -r ml/requirements.txt
```

```bash
python -m ml.pipelines.churn_build_dataset
```

```bash
python -m ml.pipelines.churn_advanced_eda
```

```bash
python -m ml.pipelines.churn_train
```

```bash
python -m ml.pipelines.churn_batch_score --write-predictions-table
```

## Causal Inference + Experiments Commands

```bash
python -m ml.pipelines.cohort_time_series
```

```bash
python -m ml.pipelines.causal_ab_test \
  --input ml/data/experiments/ab_checkout.csv \
  --variant-col variant \
  --user-col user_id \
  --binary-metric converted \
  --continuous-metric revenue_30d \
  --pre-metric pre_revenue_30d
```

```bash
python -m ml.pipelines.causal_diff_in_diff \
  --input ml/data/experiments/did_panel.csv \
  --unit-col user_id \
  --time-col period \
  --outcome-col orders_per_user \
  --treatment-col treated \
  --post-col post \
  --fixed-effects
```

## Production Operations Commands

```bash
python -m ml.pipelines.production_preflight
```

```bash
python -m ml.pipelines.churn_production_monitor
```

```bash
python -m ml.pipelines.causal_decision_gate
```

## Outputs

- Dataset: `ml/data/churn_training_dataset.csv`
- EDA report: `ml/data/reports/churn/eda_report.md`
- Model artifact: `ml/models/churn_reorder_model.joblib`
- Metrics: `ml/models/churn_reorder_metrics.json`
- Feature importance: `ml/models/churn_feature_importance.csv`
- Batch scores: `ml/data/churn_scoring_latest.csv`
- Cohort/time-series outputs: `ml/data/reports/causal/cohort_time_series/*`
- A/B outputs: `ml/data/reports/causal/ab_test/*`
- DiD outputs: `ml/data/reports/causal/did/*`
- Production preflight report: `ml/models/release_preflight_report.json`
- Production drift report: `ml/data/reports/churn/production_monitoring.json`
- Causal release decision: `ml/data/reports/causal/causal_release_decision.json`

## How This Maps to Your Notes

- Chapter 3 (time series): snapshot trends + anomaly z-scores.
- Chapter 4 (cohorts): cohort retention matrix by snapshot period.
- Chapter 6 (anomaly detection): gap-based churn anomaly (`days_since_last_order` vs average gap).
- Chapter 7 (experiments): this model provides pre-experiment segmentation and post-test uplift slicing.
- Chapter 8 (complex datasets): CTE-driven feature dataset, reusable pipeline scripts, and model artifacts.

## Advanced Extensions You Can Add Next

1. Product-level demand forecasting (daily item quantity per product).
2. Uplift modeling for promo targeting (`send promo` vs `no promo` treatment effect).
3. Real-time anomaly monitor writing to `audit_log`.
4. Feature store tables/materialized views for low-latency scoring.

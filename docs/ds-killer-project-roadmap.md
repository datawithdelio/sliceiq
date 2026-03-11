# SliceIQ Data Science Killer Project Roadmap

## Project Theme

Build a **Customer Retention Intelligence System** that predicts reorder propensity, flags churn risk, monitors anomalies, and supports experiment analysis.

## Core Deliverable (already scaffolded)

1. Point-in-time churn dataset generation:
   - `python -m ml.pipelines.churn_build_dataset`
2. Advanced EDA:
   - `python -m ml.pipelines.churn_advanced_eda`
3. Feature selection + model training:
   - `python -m ml.pipelines.churn_train`
4. Batch scoring and prediction persistence:
   - `python -m ml.pipelines.churn_batch_score --write-predictions-table`
5. Live API scoring:
   - `GET /ml/churn/{user_id}` (admin protected)
6. Production release gates:
   - `python -m ml.pipelines.production_preflight`
   - `python -m ml.pipelines.churn_production_monitor`
   - `python -m ml.pipelines.causal_decision_gate`

## What Makes It Advanced

- Time-aware snapshots prevent leakage.
- Cohort retention analysis from model dataset.
- Gap-based anomaly logic for silent churn.
- Feature selection using mutual information + permutation importance.
- Validation/test split by time windows, not random row split.
- Deployment path includes model artifact + scoring endpoint + prediction logging.
- Production gates include preflight checks, score drift monitoring, and causal rollout decisioning.

## Feature Families

- RFM-like:
  - `orders_30d`, `orders_60d`, `orders_90d`
  - `revenue_lookback`, `avg_order_value_lookback`
  - `days_since_last_order`
- Behavioral:
  - `weekend_order_ratio_lookback`, `dinner_order_ratio_lookback`
  - `cancel_ratio_lookback`, `promo_order_ratio_lookback`
  - `avg_items_per_order_lookback`, `avg_distinct_products_per_order_lookback`
- Stability and engagement:
  - `avg_gap_days_lookback`, `std_gap_days_lookback`, `max_gap_days_lookback`
  - `order_count_lifetime`, `revenue_lifetime`
  - `avg_rating_lifetime`, `review_count_lifetime`

## Mapping to Your SQL Study Chapters

- Chapter 2: clean joins, null handling, data shaping.
- Chapter 3: time bucketing and trend diagnostics.
- Chapter 4: cohort retention matrix and period-normalized comparison.
- Chapter 6: anomaly detection with z-scores and gap-based disappearance.
- Chapter 7: experiment analysis readiness with cohort-compatible metrics.
- Chapter 8: CTE-first complex dataset construction and reusable code organization.

## High-Impact Next Iterations

1. Product demand forecasting (daily/weekly quantity by product).
2. Uplift targeting model for promo optimization.
3. Real-time anomaly alerts into `audit_log`.
4. Segment-level explainability dashboards for retention actions.

## Causal Inference Expansion

For advanced causal workflows (A/B, DiD, cohort/time-series support), see:
- `docs/causal-inference-playbook.md`
- `ml/pipelines/causal_ab_test.py`
- `ml/pipelines/causal_diff_in_diff.py`
- `ml/pipelines/cohort_time_series.py`
- `ml/pipelines/causal_decision_gate.py`

## Notebook-First Production Sequence

1. `ml/notebooks/00_data_cleaning.ipynb`
2. `ml/notebooks/01_advanced_eda.ipynb`
3. `ml/notebooks/02_feature_engineering_and_selection.ipynb`
4. `ml/notebooks/03_training_and_evaluation.ipynb`
5. `ml/notebooks/04_causal_inference_ab_did.ipynb`
6. `ml/notebooks/05_cohort_time_series.ipynb`
7. `ml/notebooks/06_deployment_scoring.ipynb`
8. `ml/notebooks/07_production_readiness.ipynb`
9. `ml/notebooks/08_causal_production_decisioning.ipynb`

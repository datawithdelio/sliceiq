# SliceIQ Causal Inference Playbook

## What to Use, When

1. **A/B Test (Randomized)**  
Use when you can randomize exposure (checkout UX, promo banner, recommendation ranker).

2. **Difference-in-Differences (Quasi-Experimental)**  
Use when randomization is impossible, but treatment starts at a known time for one group and not another.

3. **Cohort + Time-Series Diagnostics**  
Use before and after either method to validate stability, seasonality, and retention behavior.

## Notebook Entry Point

Run causal workflows from:
- `ml/notebooks/04_causal_inference_ab_did.ipynb`
- `ml/notebooks/05_cohort_time_series.ipynb`
- `ml/notebooks/08_causal_production_decisioning.ipynb`

## A/B Testing - Advanced Checklist

1. Pre-register:
   - Primary metric (binary or continuous)
   - Experiment window
   - Guardrail metrics (cancel ratio, refund rate)
2. Validate assignment:
   - 50/50 split (or planned ratio)
   - No user in multiple variants
   - Pre-period balance (SMD near zero)
3. Estimate effects:
   - Binary: proportion z-test + confidence interval
   - Continuous: Welch t-test + Mann-Whitney
   - Variance reduction: CUPED with pre-period metric
4. Interpret with business context:
   - Statistical significance
   - Effect size / lift
   - Practical significance (margin impact)

Use script:

```bash
python -m ml.pipelines.causal_ab_test --input ml/data/experiments/ab_checkout.csv
```

### Expected A/B CSV Schema

- `user_id`
- `variant` (`control` or `treatment`)
- `converted` (0/1)
- `revenue_30d` (float)
- `pre_revenue_30d` (float, optional but recommended for CUPED)

## Difference-in-Differences - Advanced Checklist

1. Define treated vs control groups and intervention start date.
2. Confirm multiple pre-periods for parallel-trends testing.
3. Estimate:
   - Manual 2x2 mean differences
   - Regression DiD (`treated:post`)
   - Optional two-way fixed effects
4. Validate assumptions:
   - Pre-trend interaction not significant
   - No concurrent shock affecting only treated group
   - Stable composition of units

Use script:

```bash
python -m ml.pipelines.causal_diff_in_diff \
  --input ml/data/experiments/did_panel.csv \
  --fixed-effects
```

### Expected DiD CSV Schema

- `user_id` (or store/region id)
- `period` (date/month)
- `outcome` (orders, revenue, conversion, etc.)
- `treated` (0/1)
- `post` (0/1)
- Optional covariates (e.g., `pre_orders`, `device_mix`)

## Cohort + Time-Series (Support Layer)

Use script:

```bash
python -m ml.pipelines.cohort_time_series
```

Outputs:
- Cohort retention matrix
- Revenue retention by cohort period
- Daily trend with rolling windows
- Anomaly flags via rolling z-score

## SliceIQ-Specific Advanced Ideas

1. **Promo causal impact**
   - Treatment: users exposed to promo campaign.
   - Outcome: 30-day reorder rate, gross margin/user.
   - Method: A/B if randomized, otherwise DiD by launch date.

2. **Checkout redesign impact**
   - Primary metric: purchase conversion.
   - Guardrails: average order value, cancel ratio.
   - Method: A/B with CUPED.

3. **City/region rollout analysis**
   - Treatment: region where feature was launched first.
   - Outcome: orders/user, revenue/user.
   - Method: DiD with fixed effects.

4. **Retention program effectiveness**
   - Use cohort curves pre/post intervention to verify long-tail retention change.

## SQL Starters (Postgres)

### Build A/B user-level outcome table

```sql
SELECT
  a.user_id,
  a.variant,
  MAX(CASE WHEN o.created_at <= a.exp_start + interval '30 day' THEN 1 ELSE 0 END) AS converted,
  COALESCE(SUM(CASE WHEN o.created_at <= a.exp_start + interval '30 day' THEN o.total_amount ELSE 0 END), 0) AS revenue_30d,
  COALESCE(SUM(CASE WHEN o.created_at < a.exp_start THEN o.total_amount ELSE 0 END), 0) AS pre_revenue_30d
FROM exp_assignment a
LEFT JOIN orders o ON o.user_id = a.user_id
GROUP BY a.user_id, a.variant;
```

### Build DiD panel by month

```sql
WITH monthly AS (
  SELECT
    user_id,
    date_trunc('month', created_at)::date AS period,
    COUNT(*) AS orders,
    SUM(total_amount) AS revenue
  FROM orders
  GROUP BY 1, 2
)
SELECT
  m.user_id,
  m.period,
  m.orders::float AS outcome,
  CASE WHEN u.address->>'region' IN ('pilot_region') THEN 1 ELSE 0 END AS treated,
  CASE WHEN m.period >= DATE '2026-02-01' THEN 1 ELSE 0 END AS post
FROM monthly m
JOIN users u ON u.id = m.user_id;
```

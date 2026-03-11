# SliceIQ Notebook Run Order

1. `00_data_cleaning.ipynb`
2. `01_advanced_eda.ipynb`
3. `02_feature_engineering_and_selection.ipynb`
4. `03_training_and_evaluation.ipynb`
5. `04_causal_inference_ab_did.ipynb`
6. `05_cohort_time_series.ipynb`
7. `06_deployment_scoring.ipynb`
8. `07_production_readiness.ipynb`
9. `08_causal_production_decisioning.ipynb`

Notes:
- Run top-to-bottom in each notebook.
- Keep one notebook focused on one stage.
- Persist outputs (`ml/data/*`, `ml/models/*`) between stages.
- Re-run `00_data_cleaning.ipynb` whenever source data changes significantly.
- `07` is the release gate for model production.
- `08` is the release gate for causal experiment rollout decisions.

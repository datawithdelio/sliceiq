# SliceIQ Study Guide Implementation Audit

- Generated at (UTC): 2026-03-11T05:03:07.846168+00:00
- Pass: 26
- Warn: 0
- Fail: 0

## Detailed Checks
- [PASS] ch7 :: ab_multiple_testing_control :: value=True :: threshold=True
- [PASS] ch7 :: ab_sample_ratio_mismatch :: value=False :: threshold=False
- [PASS] ch7 :: causal_release_decision :: value=ship :: threshold=ship
- [PASS] ch7 :: did_effect_significance :: value=True :: threshold=True
- [PASS] ch7 :: did_parallel_trends_guardrail :: value=True :: threshold=True
- [PASS] ch7 :: did_placebo_guardrail :: value=True :: threshold=True
- [PASS] ch7 :: did_ready_for_regression :: value=True :: threshold=True
- [PASS] ch4 :: cohort_daily_anomalies :: value=6 :: threshold=<= 12 (warn <= 20)
- [PASS] ch3 :: date_scaffold_continuity :: value=0 :: threshold=0 missing days
- [PASS] ch3 :: lag_rolling_zscore_features_present :: value=4 :: threshold=4 of 4
- [PASS] ch3 :: rolling_window_count_integrity :: value=1.0 :: threshold=>= 0.90 mature rows with full 28-row context
- [PASS] ch3 :: seasonality_features_present :: value=3 :: threshold=3 of 3
- [PASS] ch4 :: cohort_artifacts_present :: value=True :: threshold=True
- [PASS] ch4 :: cohort_period0_anchor_integrity :: value=True :: threshold=True
- [PASS] ch4 :: fixed_window_fairness_metrics :: value=0.6666666666666666 :: threshold=>= 0.40 mature 90d cohorts (warn-only)
- [PASS] ch4 :: retention_values_within_bounds :: value=True :: threshold=True
- [PASS] ch5 :: categorical_text_normalization :: value=True :: threshold=True
- [PASS] ch5 :: text_artifact_or_proxy_signal :: value=True :: threshold=True
- [PASS] ch5 :: text_proxy_features_present :: value=True :: threshold=True
- [PASS] ch6 :: anomaly_feature_pack :: value=True :: threshold=True
- [PASS] ch6 :: daily_anomaly_report_exists :: value=True :: threshold=True
- [PASS] ch6 :: gap_anomaly_prevalence :: value={'is_gap_anomaly_2x': 0.5266821345707656, 'is_gap_anomaly_3x': 0.47447795823665895} :: threshold=pass when 10%-70% for 2x flag and 3x flag <= 2x flag
- [PASS] ch6 :: outlier_impact_global_vs_subgroup :: value=8.251775555312836 :: threshold=warn only when ratio >= 2 and subgroup impact >= 5%
- [PASS] ch8 :: dimensionality_reduction_flags :: value=True :: threshold=True
- [PASS] ch8 :: governance_artifacts_present :: value=True :: threshold=True
- [PASS] ch8 :: scoring_output_pii_hygiene :: value=0 :: threshold=== 0 PII-like columns
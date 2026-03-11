# Causal Study Guide Implementation Audit

- Generated at (UTC): 2026-03-11T05:14:51.100362+00:00
- Pass: 26
- Warn: 0
- Fail: 0

## Detailed Checks
- [PASS] ch7 :: ab_binary_effect_quality :: value={'p_value': 9.857681621527965e-12, 'rate_diff': 0.13666666666666666, 'practical_ok': True} :: threshold=p<0.05 and lift>=0.005
- [PASS] ch7 :: ab_binary_ready :: value=True :: threshold=True
- [PASS] ch7 :: ab_continuous_ready :: value=True :: threshold=True
- [PASS] ch7 :: ab_covariate_balance_smd :: value=0.03102386096898505 :: threshold=<= 0.10 (warn <= 0.20)
- [PASS] ch7 :: ab_cuped_effect_quality :: value={'p_value': 1.4718815382231834e-14, 'difference': 24.334055040235526, 'variance_reduction': 0.016433091395768318} :: threshold=p<0.05 and difference>=0.0
- [PASS] ch7 :: ab_heterogeneity_coverage :: value={'binary_bands': 3, 'continuous_bands': 3} :: threshold=>= 2 risk bands per metric
- [PASS] ch7 :: ab_heterogeneity_ready :: value=True :: threshold=True
- [PASS] ch7 :: ab_multiple_testing_control :: value=True :: threshold=True
- [PASS] ch7 :: ab_srm_guardrail :: value=False :: threshold=False
- [PASS] ch3 :: did_pre_post_period_integrity :: value=True :: threshold=True
- [PASS] ch7 :: did_parallel_trends_guardrail :: value=True :: threshold=True
- [PASS] ch7 :: did_placebo_guardrail :: value=True :: threshold=True
- [PASS] ch7 :: did_primary_effect_practical :: value=True :: threshold=True
- [PASS] ch7 :: did_primary_effect_significance :: value=True :: threshold=True
- [PASS] ch7 :: did_ready_for_regression :: value=True :: threshold=True
- [PASS] ch3 :: cohort_period_depth :: value=6 :: threshold=>= 4 periods
- [PASS] ch3 :: daily_anomaly_pressure :: value=6 :: threshold=<= 12 (warn <= 20)
- [PASS] ch4 :: cohort_coverage :: value=7 :: threshold=>= 3 cohorts
- [PASS] ch4 :: fixed_window_fairness_coverage :: value=0.6666666666666666 :: threshold=>= 0.40 cohorts with mature 90d window
- [PASS] ch8 :: ab_to_live_population_shift_high_band :: value=0.36166666666666664 :: threshold=<= 0.40 (warn <= 0.55)
- [PASS] ch8 :: deployment_sample_size :: value=200 :: threshold=>= 100
- [PASS] ch8 :: model_production_gate_status :: value=ship :: threshold=ship
- [PASS] ch5 :: text_proxy_signals_available :: value=True :: threshold=True
- [PASS] ch5 :: variant_label_normalization :: value={'control': 'control', 'treatment': 'treatment'} :: threshold=distinct lower-case labels
- [PASS] ch8 :: causal_output_pii_hygiene :: value=0 :: threshold=0 pii-like keys
- [PASS] ch8 :: governance_artifact_bundle :: value=True :: threshold=True
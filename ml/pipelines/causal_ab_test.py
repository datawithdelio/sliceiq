from __future__ import annotations

import argparse
from datetime import UTC, datetime
import json
from pathlib import Path
from typing import Any

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from scipy import stats
from statsmodels.stats.proportion import proportions_ztest

try:
    from statsmodels.stats.proportion import confint_proportions_2indep
except ImportError:  # pragma: no cover - fallback for older statsmodels
    confint_proportions_2indep = None  # type: ignore[assignment]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Advanced A/B testing analysis with optional CUPED."
    )
    parser.add_argument("--input", required=True, help="CSV with experiment data.")
    parser.add_argument("--variant-col", default="variant")
    parser.add_argument("--user-col", default="user_id")
    parser.add_argument("--binary-metric", default="converted")
    parser.add_argument("--continuous-metric", default="revenue_30d")
    parser.add_argument(
        "--pre-metric",
        default="pre_revenue_30d",
        help="Pre-period metric for CUPED adjustment.",
    )
    parser.add_argument("--control-label", default="control")
    parser.add_argument("--treatment-label", default="treatment")
    parser.add_argument("--alpha", type=float, default=0.05)
    parser.add_argument("--output-dir", default="ml/data/reports/causal/ab_test")
    return parser.parse_args()


def _resolve_variants(
    df: pd.DataFrame,
    *,
    variant_col: str,
    control_label: str,
    treatment_label: str,
) -> tuple[str, str]:
    variants = sorted(df[variant_col].dropna().astype(str).unique().tolist())
    if len(variants) != 2:
        raise RuntimeError(
            f"Expected exactly 2 variants in `{variant_col}`, found {len(variants)}: {variants}"
        )

    if control_label in variants and treatment_label in variants:
        return control_label, treatment_label

    # Fallback deterministic mapping if labels differ.
    return variants[0], variants[1]


def _binary_analysis(
    df: pd.DataFrame,
    *,
    variant_col: str,
    binary_metric: str,
    control: str,
    treatment: str,
    alpha: float,
) -> dict[str, Any]:
    work = df[[variant_col, binary_metric]].dropna().copy()
    work[binary_metric] = work[binary_metric].astype(int)

    grouped = (
        work.groupby(variant_col)[binary_metric]
        .agg(["sum", "count", "mean"])
        .rename(columns={"sum": "successes", "count": "n", "mean": "rate"})
    )
    if control not in grouped.index or treatment not in grouped.index:
        raise RuntimeError("Control/treatment labels missing after grouping.")

    c = grouped.loc[control]
    t = grouped.loc[treatment]
    count = np.array([t["successes"], c["successes"]], dtype=float)
    nobs = np.array([t["n"], c["n"]], dtype=float)
    z_stat, p_value = proportions_ztest(count, nobs, alternative="two-sided")

    rate_diff = float(t["rate"] - c["rate"])
    relative_lift = float((t["rate"] / c["rate"]) - 1.0) if c["rate"] > 0 else float("nan")

    if confint_proportions_2indep is not None:
        ci_low, ci_high = confint_proportions_2indep(
            int(t["successes"]),
            int(t["n"]),
            int(c["successes"]),
            int(c["n"]),
            method="wald",
            compare="diff",
            alpha=alpha,
        )
    else:
        # Normal approximation fallback.
        se = np.sqrt(t["rate"] * (1 - t["rate"]) / t["n"] + c["rate"] * (1 - c["rate"]) / c["n"])
        z_crit = stats.norm.ppf(1 - alpha / 2)
        ci_low = rate_diff - z_crit * se
        ci_high = rate_diff + z_crit * se

    return {
        "control_n": int(c["n"]),
        "treatment_n": int(t["n"]),
        "control_rate": float(c["rate"]),
        "treatment_rate": float(t["rate"]),
        "rate_diff": rate_diff,
        "relative_lift": relative_lift,
        "z_stat": float(z_stat),
        "p_value": float(p_value),
        "ci_low": float(ci_low),
        "ci_high": float(ci_high),
        "statistically_significant": bool(p_value < alpha),
    }


def _continuous_summary(
    df: pd.DataFrame,
    *,
    variant_col: str,
    metric_col: str,
    control: str,
    treatment: str,
    alpha: float,
) -> dict[str, Any]:
    work = df[[variant_col, metric_col]].dropna().copy()
    work[metric_col] = pd.to_numeric(work[metric_col], errors="coerce")
    work = work.dropna(subset=[metric_col])

    c_values = work.loc[work[variant_col] == control, metric_col].to_numpy(dtype=float)
    t_values = work.loc[work[variant_col] == treatment, metric_col].to_numpy(dtype=float)
    if len(c_values) == 0 or len(t_values) == 0:
        raise RuntimeError(f"Metric `{metric_col}` has empty group after cleaning.")

    t_stat, p_value = stats.ttest_ind(t_values, c_values, equal_var=False, nan_policy="omit")
    u_stat, u_p_value = stats.mannwhitneyu(t_values, c_values, alternative="two-sided")

    c_mean = float(np.mean(c_values))
    t_mean = float(np.mean(t_values))
    diff = t_mean - c_mean
    relative_lift = (t_mean / c_mean) - 1.0 if c_mean != 0 else float("nan")

    c_var = np.var(c_values, ddof=1)
    t_var = np.var(t_values, ddof=1)
    se = np.sqrt(c_var / len(c_values) + t_var / len(t_values))
    z_crit = stats.norm.ppf(1 - alpha / 2)
    ci_low = diff - z_crit * se
    ci_high = diff + z_crit * se

    pooled_std = np.sqrt(
        ((len(c_values) - 1) * c_var + (len(t_values) - 1) * t_var)
        / max(1, (len(c_values) + len(t_values) - 2))
    )
    cohen_d = diff / pooled_std if pooled_std > 0 else 0.0

    return {
        "metric": metric_col,
        "control_n": int(len(c_values)),
        "treatment_n": int(len(t_values)),
        "control_mean": c_mean,
        "treatment_mean": t_mean,
        "difference": float(diff),
        "relative_lift": float(relative_lift),
        "ci_low": float(ci_low),
        "ci_high": float(ci_high),
        "welch_t_stat": float(t_stat),
        "welch_p_value": float(p_value),
        "mann_whitney_u_stat": float(u_stat),
        "mann_whitney_p_value": float(u_p_value),
        "cohen_d": float(cohen_d),
        "statistically_significant": bool(p_value < alpha),
    }


def _cuped_analysis(
    df: pd.DataFrame,
    *,
    variant_col: str,
    outcome_col: str,
    pre_metric_col: str,
    control: str,
    treatment: str,
    alpha: float,
) -> dict[str, Any]:
    work = df[[variant_col, outcome_col, pre_metric_col]].dropna().copy()
    work[outcome_col] = pd.to_numeric(work[outcome_col], errors="coerce")
    work[pre_metric_col] = pd.to_numeric(work[pre_metric_col], errors="coerce")
    work = work.dropna(subset=[outcome_col, pre_metric_col])
    if work.empty:
        raise RuntimeError("CUPED columns are present but no valid numeric rows are available.")

    x = work[pre_metric_col].to_numpy(dtype=float)
    y = work[outcome_col].to_numpy(dtype=float)
    x_var = float(np.var(x, ddof=1))
    if x_var <= 0:
        theta = 0.0
    else:
        theta = float(np.cov(y, x, ddof=1)[0, 1] / x_var)
    y_adj = y - theta * (x - x.mean())
    work["cuped_adjusted"] = y_adj

    summary = _continuous_summary(
        work,
        variant_col=variant_col,
        metric_col="cuped_adjusted",
        control=control,
        treatment=treatment,
        alpha=alpha,
    )
    summary["theta"] = theta
    summary["pre_metric"] = pre_metric_col
    summary["raw_metric"] = outcome_col
    return summary


def _balance_checks(
    df: pd.DataFrame,
    *,
    variant_col: str,
    control: str,
    treatment: str,
    pre_metric: str,
) -> dict[str, Any]:
    sample_sizes = df[variant_col].value_counts(dropna=False).to_dict()
    result: dict[str, Any] = {
        "sample_sizes": sample_sizes,
        "sample_ratio_mismatch": None,
        "pre_metric_smd": None,
    }

    if control in sample_sizes and treatment in sample_sizes and sample_sizes[control] > 0:
        ratio = sample_sizes[treatment] / sample_sizes[control]
        result["sample_ratio_mismatch"] = float(abs(ratio - 1.0))

    if pre_metric in df.columns:
        work = df[[variant_col, pre_metric]].dropna().copy()
        if not work.empty:
            c = pd.to_numeric(
                work.loc[work[variant_col] == control, pre_metric], errors="coerce"
            ).dropna()
            t = pd.to_numeric(
                work.loc[work[variant_col] == treatment, pre_metric], errors="coerce"
            ).dropna()
            if len(c) > 1 and len(t) > 1:
                c_mean = c.mean()
                t_mean = t.mean()
                c_var = c.var(ddof=1)
                t_var = t.var(ddof=1)
                pooled_sd = np.sqrt((c_var + t_var) / 2)
                smd = float((t_mean - c_mean) / pooled_sd) if pooled_sd > 0 else 0.0
                result["pre_metric_smd"] = smd

    return result


def _write_plot(
    df: pd.DataFrame,
    *,
    variant_col: str,
    metric_col: str,
    control: str,
    treatment: str,
    output_path: Path,
) -> None:
    work = df[[variant_col, metric_col]].dropna().copy()
    work[metric_col] = pd.to_numeric(work[metric_col], errors="coerce")
    work = work.dropna(subset=[metric_col])
    if work.empty:
        return

    c_vals = work.loc[work[variant_col] == control, metric_col].to_numpy(dtype=float)
    t_vals = work.loc[work[variant_col] == treatment, metric_col].to_numpy(dtype=float)

    fig, ax = plt.subplots(figsize=(10, 5))
    ax.hist(c_vals, bins=30, alpha=0.6, label=control, density=True)
    ax.hist(t_vals, bins=30, alpha=0.6, label=treatment, density=True)
    ax.set_title(f"Distribution: {metric_col}")
    ax.set_xlabel(metric_col)
    ax.set_ylabel("Density")
    ax.legend()
    ax.grid(alpha=0.2)
    fig.tight_layout()
    fig.savefig(output_path, dpi=150)
    plt.close(fig)


def _to_markdown(
    *,
    report_path: Path,
    control: str,
    treatment: str,
    binary_results: dict[str, Any] | None,
    continuous_results: dict[str, Any] | None,
    cuped_results: dict[str, Any] | None,
    balance: dict[str, Any],
) -> None:
    lines: list[str] = [
        "# SliceIQ A/B Test Analysis Report",
        "",
        f"- Generated at (UTC): {datetime.now(UTC).isoformat()}",
        f"- Control label: `{control}`",
        f"- Treatment label: `{treatment}`",
        "",
        "## Randomization and Balance Checks",
        f"- Sample sizes: {balance.get('sample_sizes', {})}",
        f"- Sample ratio mismatch (`|treatment/control - 1|`): {balance.get('sample_ratio_mismatch')}",
        f"- Pre-metric SMD: {balance.get('pre_metric_smd')}",
        "",
    ]

    if binary_results is not None:
        lines.extend(
            [
                "## Binary Outcome Results",
                f"- Control rate: {binary_results['control_rate']:.6f}",
                f"- Treatment rate: {binary_results['treatment_rate']:.6f}",
                f"- Absolute diff: {binary_results['rate_diff']:.6f}",
                f"- Relative lift: {binary_results['relative_lift']:.6f}",
                f"- 95% CI (diff): [{binary_results['ci_low']:.6f}, {binary_results['ci_high']:.6f}]",
                f"- Z-test p-value: {binary_results['p_value']:.6g}",
                f"- Significant: {binary_results['statistically_significant']}",
                "",
            ]
        )

    if continuous_results is not None:
        lines.extend(
            [
                "## Continuous Outcome Results",
                f"- Metric: `{continuous_results['metric']}`",
                f"- Control mean: {continuous_results['control_mean']:.6f}",
                f"- Treatment mean: {continuous_results['treatment_mean']:.6f}",
                f"- Absolute diff: {continuous_results['difference']:.6f}",
                f"- Relative lift: {continuous_results['relative_lift']:.6f}",
                f"- 95% CI (diff): [{continuous_results['ci_low']:.6f}, {continuous_results['ci_high']:.6f}]",
                f"- Welch p-value: {continuous_results['welch_p_value']:.6g}",
                f"- Mann-Whitney p-value: {continuous_results['mann_whitney_p_value']:.6g}",
                f"- Cohen's d: {continuous_results['cohen_d']:.6f}",
                f"- Significant: {continuous_results['statistically_significant']}",
                "",
            ]
        )

    if cuped_results is not None:
        lines.extend(
            [
                "## CUPED-Adjusted Results",
                f"- Theta: {cuped_results['theta']:.6f}",
                f"- Raw metric: `{cuped_results['raw_metric']}`",
                f"- Pre metric: `{cuped_results['pre_metric']}`",
                f"- Adjusted diff: {cuped_results['difference']:.6f}",
                f"- Adjusted Welch p-value: {cuped_results['welch_p_value']:.6g}",
                f"- Significant: {cuped_results['statistically_significant']}",
                "",
            ]
        )

    report_path.write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    args = parse_args()
    input_path = Path(args.input)
    if not input_path.exists():
        raise FileNotFoundError(f"Input CSV not found: {input_path}")

    df = pd.read_csv(input_path)
    required = {args.variant_col, args.user_col}
    missing = required - set(df.columns)
    if missing:
        raise RuntimeError(f"Missing required columns: {sorted(missing)}")

    control, treatment = _resolve_variants(
        df,
        variant_col=args.variant_col,
        control_label=args.control_label,
        treatment_label=args.treatment_label,
    )

    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    balance = _balance_checks(
        df,
        variant_col=args.variant_col,
        control=control,
        treatment=treatment,
        pre_metric=args.pre_metric,
    )

    binary_results = None
    if args.binary_metric in df.columns:
        binary_results = _binary_analysis(
            df,
            variant_col=args.variant_col,
            binary_metric=args.binary_metric,
            control=control,
            treatment=treatment,
            alpha=args.alpha,
        )

    continuous_results = None
    if args.continuous_metric in df.columns:
        continuous_results = _continuous_summary(
            df,
            variant_col=args.variant_col,
            metric_col=args.continuous_metric,
            control=control,
            treatment=treatment,
            alpha=args.alpha,
        )
        _write_plot(
            df,
            variant_col=args.variant_col,
            metric_col=args.continuous_metric,
            control=control,
            treatment=treatment,
            output_path=output_dir / "continuous_metric_distribution.png",
        )

    cuped_results = None
    if args.continuous_metric in df.columns and args.pre_metric in df.columns:
        cuped_results = _cuped_analysis(
            df,
            variant_col=args.variant_col,
            outcome_col=args.continuous_metric,
            pre_metric_col=args.pre_metric,
            control=control,
            treatment=treatment,
            alpha=args.alpha,
        )

    if binary_results is None and continuous_results is None:
        raise RuntimeError(
            "No analyzable metrics found. Provide columns for --binary-metric and/or --continuous-metric."
        )

    payload = {
        "generated_at_utc": datetime.now(UTC).isoformat(),
        "control_label": control,
        "treatment_label": treatment,
        "binary_results": binary_results,
        "continuous_results": continuous_results,
        "cuped_results": cuped_results,
        "balance_checks": balance,
    }

    json_path = output_dir / "ab_test_results.json"
    json_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    _to_markdown(
        report_path=output_dir / "ab_test_report.md",
        control=control,
        treatment=treatment,
        binary_results=binary_results,
        continuous_results=continuous_results,
        cuped_results=cuped_results,
        balance=balance,
    )

    if continuous_results is not None:
        metrics_df = pd.DataFrame([continuous_results])
        metrics_df.to_csv(output_dir / "continuous_metric_summary.csv", index=False)
    if binary_results is not None:
        pd.DataFrame([binary_results]).to_csv(output_dir / "binary_metric_summary.csv", index=False)

    print(f"[done] A/B report generated at {output_dir}")


if __name__ == "__main__":
    main()


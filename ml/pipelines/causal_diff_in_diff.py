from __future__ import annotations

import argparse
from datetime import UTC, datetime
import json
from pathlib import Path
from typing import Any

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import statsmodels.formula.api as smf


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Difference-in-Differences (DiD) analysis with optional fixed effects."
    )
    parser.add_argument("--input", required=True, help="Panel CSV for DiD analysis.")
    parser.add_argument("--unit-col", default="user_id")
    parser.add_argument("--time-col", default="period")
    parser.add_argument("--outcome-col", default="outcome")
    parser.add_argument("--treatment-col", default="treated")
    parser.add_argument("--post-col", default="post")
    parser.add_argument(
        "--covariates",
        default="",
        help="Comma-separated covariate columns, e.g. pre_orders,pre_revenue",
    )
    parser.add_argument(
        "--fixed-effects",
        action="store_true",
        help="Run two-way fixed effects model with C(unit) + C(time).",
    )
    parser.add_argument(
        "--cluster-col",
        default="",
        help="Cluster-robust standard errors by this column (defaults to unit).",
    )
    parser.add_argument("--output-dir", default="ml/data/reports/causal/did")
    return parser.parse_args()


def _standardize_columns(df: pd.DataFrame, args: argparse.Namespace) -> tuple[pd.DataFrame, list[str]]:
    required = {
        args.unit_col,
        args.time_col,
        args.outcome_col,
        args.treatment_col,
        args.post_col,
    }
    missing = required - set(df.columns)
    if missing:
        raise RuntimeError(f"Missing required columns: {sorted(missing)}")

    covariates = [c.strip() for c in args.covariates.split(",") if c.strip()]
    missing_covs = [c for c in covariates if c not in df.columns]
    if missing_covs:
        raise RuntimeError(f"Covariate columns missing in input: {missing_covs}")

    rename_map = {
        args.unit_col: "unit_id",
        args.time_col: "time_raw",
        args.outcome_col: "outcome",
        args.treatment_col: "treated",
        args.post_col: "post",
    }
    for idx, cov in enumerate(covariates):
        rename_map[cov] = f"cov_{idx}"

    work = df.rename(columns=rename_map).copy()
    work["treated"] = pd.to_numeric(work["treated"], errors="coerce").fillna(0).astype(int)
    work["post"] = pd.to_numeric(work["post"], errors="coerce").fillna(0).astype(int)
    work["outcome"] = pd.to_numeric(work["outcome"], errors="coerce")
    work = work.dropna(subset=["unit_id", "time_raw", "outcome"])
    parsed_time = pd.to_datetime(work["time_raw"], errors="coerce")
    if parsed_time.notna().all():
        work["time_raw"] = parsed_time
    else:
        work["time_raw"] = work["time_raw"].astype(str)
    work["treated_post"] = work["treated"] * work["post"]

    mapped_covariates = [f"cov_{i}" for i in range(len(covariates))]
    for cov in mapped_covariates:
        work[cov] = pd.to_numeric(work[cov], errors="coerce")

    return work, mapped_covariates


def _group_means_table(df: pd.DataFrame) -> pd.DataFrame:
    means = (
        df.groupby(["treated", "post"], as_index=False)["outcome"]
        .mean()
        .rename(columns={"outcome": "mean_outcome"})
    )
    return means


def _did_manual_estimate(means: pd.DataFrame) -> dict[str, float]:
    lookup = {(int(r["treated"]), int(r["post"])): float(r["mean_outcome"]) for _, r in means.iterrows()}
    control_pre = lookup.get((0, 0), float("nan"))
    control_post = lookup.get((0, 1), float("nan"))
    treat_pre = lookup.get((1, 0), float("nan"))
    treat_post = lookup.get((1, 1), float("nan"))

    control_diff = control_post - control_pre
    treat_diff = treat_post - treat_pre
    did = treat_diff - control_diff
    return {
        "control_pre": control_pre,
        "control_post": control_post,
        "treatment_pre": treat_pre,
        "treatment_post": treat_post,
        "control_diff": control_diff,
        "treatment_diff": treat_diff,
        "did_manual": did,
    }


def _fit_model(
    df: pd.DataFrame,
    *,
    covariates: list[str],
    fixed_effects: bool,
    cluster_col: str | None,
) -> tuple[Any, str]:
    cov_terms = " + ".join(covariates) if covariates else ""
    base_terms = "treated + post + treated:post"
    rhs = base_terms if not cov_terms else f"{base_terms} + {cov_terms}"

    if fixed_effects:
        # Keep only interaction with FE to reduce strict collinearity risk.
        rhs_fe = "treated:post"
        if cov_terms:
            rhs_fe = f"{rhs_fe} + {cov_terms}"
        rhs_fe = f"{rhs_fe} + C(unit_id) + C(time_str)"
        formula = f"outcome ~ {rhs_fe}"
    else:
        formula = f"outcome ~ {rhs}"

    if cluster_col:
        model = smf.ols(formula=formula, data=df).fit(
            cov_type="cluster",
            cov_kwds={"groups": df[cluster_col]},
        )
    else:
        model = smf.ols(formula=formula, data=df).fit(cov_type="HC3")

    return model, formula


def _parallel_trends_test(df: pd.DataFrame) -> dict[str, float | None]:
    pre = df[df["post"] == 0].copy()
    if pre.empty or pre["treated"].nunique() < 2:
        return {"coef": None, "p_value": None}

    unique_time = sorted(pre["time_str"].unique().tolist())
    if len(unique_time) < 3:
        return {"coef": None, "p_value": None}

    time_map = {key: idx for idx, key in enumerate(unique_time)}
    pre["time_num"] = pre["time_str"].map(time_map).astype(float)
    model = smf.ols("outcome ~ treated + time_num + treated:time_num", data=pre).fit(cov_type="HC3")
    coef = model.params.get("treated:time_num", np.nan)
    p_value = model.pvalues.get("treated:time_num", np.nan)
    return {
        "coef": float(coef) if pd.notna(coef) else None,
        "p_value": float(p_value) if pd.notna(p_value) else None,
    }


def _write_plot(df: pd.DataFrame, output_path: Path) -> None:
    series = (
        df.groupby(["time_str", "treated"], as_index=False)["outcome"]
        .mean()
        .sort_values(["time_str", "treated"])
    )
    if series.empty:
        return

    treated_series = series[series["treated"] == 1]
    control_series = series[series["treated"] == 0]

    fig, ax = plt.subplots(figsize=(10, 5))
    ax.plot(control_series["time_str"], control_series["outcome"], marker="o", label="control")
    ax.plot(treated_series["time_str"], treated_series["outcome"], marker="o", label="treated")
    ax.set_title("Outcome Trends by Group (DiD)")
    ax.set_xlabel("Time")
    ax.set_ylabel("Mean Outcome")
    ax.legend()
    ax.grid(alpha=0.2)
    for label in ax.get_xticklabels():
        label.set_rotation(30)
        label.set_ha("right")
    fig.tight_layout()
    fig.savefig(output_path, dpi=150)
    plt.close(fig)


def _to_markdown(
    *,
    output_path: Path,
    manual: dict[str, float],
    model_name: str,
    formula: str,
    coef: float | None,
    p_value: float | None,
    ci_low: float | None,
    ci_high: float | None,
    parallel_trends: dict[str, float | None],
) -> None:
    lines = [
        "# SliceIQ Difference-in-Differences Report",
        "",
        f"- Generated at (UTC): {datetime.now(UTC).isoformat()}",
        f"- Model type: `{model_name}`",
        f"- Formula: `{formula}`",
        "",
        "## Manual DiD (2x2 Means)",
        f"- Control pre: {manual['control_pre']:.6f}",
        f"- Control post: {manual['control_post']:.6f}",
        f"- Treatment pre: {manual['treatment_pre']:.6f}",
        f"- Treatment post: {manual['treatment_post']:.6f}",
        f"- Control diff: {manual['control_diff']:.6f}",
        f"- Treatment diff: {manual['treatment_diff']:.6f}",
        f"- DiD estimate: {manual['did_manual']:.6f}",
        "",
        "## Regression Estimate (treated:post)",
        f"- Coefficient: {coef}",
        f"- p-value: {p_value}",
        f"- 95% CI: [{ci_low}, {ci_high}]",
        "",
        "## Parallel Trends (Pre-Period Interaction Test)",
        f"- Coef (treated x time): {parallel_trends['coef']}",
        f"- p-value: {parallel_trends['p_value']}",
        "",
    ]
    output_path.write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    args = parse_args()
    input_path = Path(args.input)
    if not input_path.exists():
        raise FileNotFoundError(f"Input CSV not found: {input_path}")

    raw = pd.read_csv(input_path)
    df, covariates = _standardize_columns(raw, args)
    df["time_str"] = df["time_raw"].astype(str)

    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    means = _group_means_table(df)
    means.to_csv(output_dir / "group_means_2x2.csv", index=False)
    manual = _did_manual_estimate(means)

    cluster_col = "unit_id" if args.cluster_col == "" else args.cluster_col
    if cluster_col and cluster_col not in df.columns:
        cluster_col = None

    model, formula = _fit_model(
        df,
        covariates=covariates,
        fixed_effects=args.fixed_effects,
        cluster_col=cluster_col,
    )
    coef = model.params.get("treated:post", np.nan)
    p_value = model.pvalues.get("treated:post", np.nan)
    ci = model.conf_int().loc["treated:post"] if "treated:post" in model.params.index else [np.nan, np.nan]
    ci_low = float(ci[0]) if pd.notna(ci[0]) else None
    ci_high = float(ci[1]) if pd.notna(ci[1]) else None

    parallel_trends = _parallel_trends_test(df)
    _write_plot(df, output_dir / "did_group_trends.png")

    results = {
        "generated_at_utc": datetime.now(UTC).isoformat(),
        "model_type": "two_way_fixed_effects" if args.fixed_effects else "standard_did",
        "formula": formula,
        "manual": manual,
        "regression": {
            "coef_treated_post": float(coef) if pd.notna(coef) else None,
            "p_value": float(p_value) if pd.notna(p_value) else None,
            "ci_low": ci_low,
            "ci_high": ci_high,
            "r_squared": float(model.rsquared),
            "n_obs": int(model.nobs),
        },
        "parallel_trends_test": parallel_trends,
    }
    (output_dir / "did_results.json").write_text(json.dumps(results, indent=2), encoding="utf-8")

    _to_markdown(
        output_path=output_dir / "did_report.md",
        manual=manual,
        model_name=results["model_type"],
        formula=formula,
        coef=results["regression"]["coef_treated_post"],
        p_value=results["regression"]["p_value"],
        ci_low=results["regression"]["ci_low"],
        ci_high=results["regression"]["ci_high"],
        parallel_trends=parallel_trends,
    )

    print(f"[done] DiD report generated at {output_dir}")


if __name__ == "__main__":
    main()

from __future__ import annotations

import argparse
from datetime import UTC, datetime
import json
from pathlib import Path
from typing import Any


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Decision gate for causal analyses (A/B and DiD) before production rollout."
    )
    parser.add_argument(
        "--ab-results-json",
        default="ml/data/reports/causal/ab_test/ab_test_results.json",
        help="A/B results JSON from causal_ab_test.py",
    )
    parser.add_argument(
        "--did-results-json",
        default="ml/data/reports/causal/did/did_results.json",
        help="DiD results JSON from causal_diff_in_diff.py",
    )
    parser.add_argument(
        "--alpha",
        type=float,
        default=0.05,
        help="Significance threshold.",
    )
    parser.add_argument(
        "--min-binary-lift",
        type=float,
        default=0.005,
        help="Minimum absolute binary lift required to ship.",
    )
    parser.add_argument(
        "--min-continuous-lift",
        type=float,
        default=0.0,
        help="Minimum absolute continuous lift required to ship.",
    )
    parser.add_argument(
        "--output-json",
        default="ml/data/reports/causal/causal_release_decision.json",
        help="Decision JSON output path.",
    )
    parser.add_argument(
        "--output-md",
        default="ml/data/reports/causal/causal_release_decision.md",
        help="Decision markdown output path.",
    )
    return parser.parse_args()


def _ab_decision(payload: dict[str, Any], alpha: float, min_binary_lift: float, min_cont_lift: float) -> dict[str, Any]:
    binary = payload.get("binary_results")
    continuous = payload.get("continuous_results")
    cuped = payload.get("cuped_results")

    binary_pass = None
    if isinstance(binary, dict):
        binary_pass = (
            float(binary.get("p_value", 1.0)) < alpha
            and float(binary.get("rate_diff", 0.0)) >= min_binary_lift
        )

    continuous_pass = None
    if isinstance(continuous, dict):
        continuous_pass = (
            float(continuous.get("welch_p_value", 1.0)) < alpha
            and float(continuous.get("difference", 0.0)) >= min_cont_lift
        )

    cuped_pass = None
    if isinstance(cuped, dict):
        cuped_pass = (
            float(cuped.get("welch_p_value", 1.0)) < alpha
            and float(cuped.get("difference", 0.0)) >= min_cont_lift
        )

    any_pass = any(flag is True for flag in [binary_pass, continuous_pass, cuped_pass])
    return {
        "binary_pass": binary_pass,
        "continuous_pass": continuous_pass,
        "cuped_pass": cuped_pass,
        "ab_recommend_ship": any_pass,
    }


def _did_decision(payload: dict[str, Any], alpha: float, min_cont_lift: float) -> dict[str, Any]:
    reg = payload.get("regression", {})
    coef = float(reg.get("coef_treated_post", 0.0) or 0.0)
    p_value = float(reg.get("p_value", 1.0) or 1.0)

    pre = payload.get("parallel_trends_test", {})
    pre_p = pre.get("p_value")
    pre_ok = True if pre_p is None else float(pre_p) >= alpha

    did_pass = (p_value < alpha) and (coef >= min_cont_lift) and pre_ok
    return {
        "did_coef": coef,
        "did_p_value": p_value,
        "parallel_trends_ok": pre_ok,
        "did_recommend_ship": did_pass,
    }


def _write_md(path: Path, report: dict[str, Any]) -> None:
    lines = [
        "# Causal Release Decision",
        "",
        f"- Generated at (UTC): {report['generated_at_utc']}",
        f"- Final decision: `{report['final_decision']}`",
        "",
        "## A/B Decision",
        f"- Recommend ship: {report['ab_decision']['ab_recommend_ship']}",
        f"- Binary pass: {report['ab_decision']['binary_pass']}",
        f"- Continuous pass: {report['ab_decision']['continuous_pass']}",
        f"- CUPED pass: {report['ab_decision']['cuped_pass']}",
        "",
        "## DiD Decision",
        f"- Recommend ship: {report['did_decision']['did_recommend_ship']}",
        f"- DiD coefficient: {report['did_decision']['did_coef']}",
        f"- DiD p-value: {report['did_decision']['did_p_value']}",
        f"- Parallel trends OK: {report['did_decision']['parallel_trends_ok']}",
        "",
        "## Rules",
        "- `ship` if A/B or DiD recommends ship",
        "- `iterate` otherwise",
    ]
    path.write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    args = parse_args()
    ab_path = Path(args.ab_results_json)
    did_path = Path(args.did_results_json)
    if not ab_path.exists():
        raise FileNotFoundError(f"A/B results not found: {ab_path}")
    if not did_path.exists():
        raise FileNotFoundError(f"DiD results not found: {did_path}")

    ab_payload = json.loads(ab_path.read_text(encoding="utf-8"))
    did_payload = json.loads(did_path.read_text(encoding="utf-8"))

    ab_decision = _ab_decision(
        ab_payload,
        alpha=args.alpha,
        min_binary_lift=args.min_binary_lift,
        min_cont_lift=args.min_continuous_lift,
    )
    did_decision = _did_decision(
        did_payload,
        alpha=args.alpha,
        min_cont_lift=args.min_continuous_lift,
    )

    final_decision = (
        "ship"
        if (ab_decision["ab_recommend_ship"] or did_decision["did_recommend_ship"])
        else "iterate"
    )

    report = {
        "generated_at_utc": datetime.now(UTC).isoformat(),
        "final_decision": final_decision,
        "ab_decision": ab_decision,
        "did_decision": did_decision,
        "inputs": {
            "ab_results_json": str(ab_path),
            "did_results_json": str(did_path),
        },
    }

    output_json = Path(args.output_json)
    output_json.parent.mkdir(parents=True, exist_ok=True)
    output_json.write_text(json.dumps(report, indent=2), encoding="utf-8")

    output_md = Path(args.output_md)
    output_md.parent.mkdir(parents=True, exist_ok=True)
    _write_md(output_md, report)
    print(f"[done] causal decision generated: {output_json}")


if __name__ == "__main__":
    main()


from __future__ import annotations

import argparse
from datetime import UTC, datetime
import json
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Monitor production score drift and risk mix for churn model."
    )
    parser.add_argument(
        "--scoring-path",
        default="ml/data/churn_scoring_latest.csv",
        help="CSV output from churn_batch_score.py",
    )
    parser.add_argument(
        "--baseline-path",
        default="ml/models/churn_drift_baseline.json",
        help="Baseline output from churn_train.py",
    )
    parser.add_argument(
        "--psi-alert-threshold",
        type=float,
        default=0.25,
        help="PSI threshold above which drift alert is raised.",
    )
    parser.add_argument(
        "--max-high-risk-rate",
        type=float,
        default=0.45,
        help="Alert if high-risk users exceed this share.",
    )
    parser.add_argument(
        "--output-json",
        default="ml/data/reports/churn/production_monitoring.json",
        help="Monitoring JSON report path.",
    )
    parser.add_argument(
        "--output-md",
        default="ml/data/reports/churn/production_monitoring.md",
        help="Monitoring markdown report path.",
    )
    return parser.parse_args()


def _safe_ratio(counts: np.ndarray) -> np.ndarray:
    total = float(counts.sum())
    if total <= 0:
        return np.ones_like(counts, dtype=float) / len(counts)
    return counts / total


def _psi(expected: np.ndarray, actual: np.ndarray) -> float:
    eps = 1e-9
    expected = np.clip(expected, eps, None)
    actual = np.clip(actual, eps, None)
    return float(np.sum((actual - expected) * np.log(actual / expected)))


def _write_markdown(
    *,
    output_path: Path,
    report: dict[str, Any],
) -> None:
    lines = [
        "# SliceIQ Churn Production Monitoring",
        "",
        f"- Generated at (UTC): {report['generated_at_utc']}",
        f"- Model version: {report.get('model_version')}",
        f"- Scored users: {report['scored_users']}",
        "",
        "## Drift Metrics",
        f"- PSI: {report['psi']:.6f}",
        f"- Mean score (current): {report['current_mean_score']:.6f}",
        f"- Mean score (baseline): {report['baseline_mean_score']:.6f}",
        f"- Drift alert: {report['alerts']['psi_alert']}",
        "",
        "## Risk Mix",
        f"- High risk rate: {report['high_risk_rate']:.6f}",
        f"- Medium risk rate: {report['medium_risk_rate']:.6f}",
        f"- Low risk rate: {report['low_risk_rate']:.6f}",
        f"- Risk mix alert: {report['alerts']['high_risk_alert']}",
        "",
    ]
    output_path.write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    args = parse_args()
    scoring_path = Path(args.scoring_path)
    baseline_path = Path(args.baseline_path)
    if not scoring_path.exists():
        raise FileNotFoundError(f"Scoring CSV not found: {scoring_path}")
    if not baseline_path.exists():
        raise FileNotFoundError(f"Drift baseline not found: {baseline_path}")

    scores = pd.read_csv(scoring_path)
    if "reorder_probability_30d" not in scores.columns:
        raise RuntimeError("Scoring CSV missing reorder_probability_30d.")
    if "risk_bucket" not in scores.columns:
        raise RuntimeError("Scoring CSV missing risk_bucket.")

    baseline = json.loads(baseline_path.read_text(encoding="utf-8"))
    bin_edges = np.array(baseline.get("bin_edges", []), dtype=float)
    expected_dist = np.array(baseline.get("test_distribution", []), dtype=float)
    if len(bin_edges) < 2 or len(expected_dist) != len(bin_edges) - 1:
        raise RuntimeError("Invalid baseline bin configuration.")

    current_scores = pd.to_numeric(scores["reorder_probability_30d"], errors="coerce").dropna().to_numpy()
    if len(current_scores) == 0:
        raise RuntimeError("No valid scores in scoring CSV.")

    current_counts, _ = np.histogram(current_scores, bins=bin_edges)
    current_dist = _safe_ratio(current_counts)
    psi_value = _psi(expected_dist, current_dist)

    high_rate = float((scores["risk_bucket"] == "high").mean())
    med_rate = float((scores["risk_bucket"] == "medium").mean())
    low_rate = float((scores["risk_bucket"] == "low").mean())

    model_version = str(baseline.get("model_version", "unknown"))
    report = {
        "generated_at_utc": datetime.now(UTC).isoformat(),
        "model_version": model_version,
        "scored_users": int(len(scores)),
        "psi": psi_value,
        "current_mean_score": float(np.mean(current_scores)),
        "baseline_mean_score": float(baseline.get("test_mean_score", np.nan)),
        "high_risk_rate": high_rate,
        "medium_risk_rate": med_rate,
        "low_risk_rate": low_rate,
        "alerts": {
            "psi_alert": bool(psi_value >= args.psi_alert_threshold),
            "high_risk_alert": bool(high_rate >= args.max_high_risk_rate),
        },
        "thresholds": {
            "psi_alert_threshold": args.psi_alert_threshold,
            "max_high_risk_rate": args.max_high_risk_rate,
        },
        "score_distribution": {
            "bin_edges": bin_edges.tolist(),
            "expected_dist": expected_dist.tolist(),
            "current_dist": current_dist.tolist(),
        },
    }

    output_json = Path(args.output_json)
    output_json.parent.mkdir(parents=True, exist_ok=True)
    output_json.write_text(json.dumps(report, indent=2), encoding="utf-8")

    output_md = Path(args.output_md)
    output_md.parent.mkdir(parents=True, exist_ok=True)
    _write_markdown(output_path=output_md, report=report)

    print(f"[done] monitoring report generated: {output_json}")


if __name__ == "__main__":
    main()


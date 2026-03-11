from __future__ import annotations

import argparse
from datetime import UTC, datetime
import json
from pathlib import Path
from typing import Any

import pandas as pd


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run production preflight checks before model release."
    )
    parser.add_argument(
        "--dataset-path",
        default="ml/data/churn_training_dataset.csv",
        help="Training dataset path.",
    )
    parser.add_argument(
        "--model-path",
        default="ml/models/churn_reorder_model.joblib",
        help="Trained model artifact path.",
    )
    parser.add_argument(
        "--metrics-path",
        default="ml/models/churn_reorder_metrics.json",
        help="Training metrics JSON path.",
    )
    parser.add_argument(
        "--drift-baseline-path",
        default="ml/models/churn_drift_baseline.json",
        help="Drift baseline path from training.",
    )
    parser.add_argument(
        "--min-roc-auc",
        type=float,
        default=0.60,
        help="Minimum acceptable ROC-AUC on test.",
    )
    parser.add_argument(
        "--min-pr-auc",
        type=float,
        default=0.40,
        help="Minimum acceptable PR-AUC on test.",
    )
    parser.add_argument(
        "--max-positive-rate-gap",
        type=float,
        default=0.20,
        help="Max allowed |train_positive_rate - test_positive_rate|.",
    )
    parser.add_argument(
        "--output-json",
        default="ml/models/release_preflight_report.json",
        help="Output JSON path.",
    )
    parser.add_argument(
        "--output-md",
        default="ml/models/release_preflight_report.md",
        help="Output markdown path.",
    )
    return parser.parse_args()


def _check_file_exists(path: Path, name: str, findings: list[dict[str, Any]]) -> bool:
    if not path.exists():
        findings.append(
            {"check": f"{name}_exists", "status": "fail", "detail": f"Missing file: {path}"}
        )
        return False
    findings.append(
        {"check": f"{name}_exists", "status": "pass", "detail": f"Found file: {path}"}
    )
    return True


def _write_markdown(
    *,
    output_path: Path,
    findings: list[dict[str, Any]],
    passed: bool,
    release_blocked: bool,
) -> None:
    lines = [
        "# SliceIQ Model Release Preflight",
        "",
        f"- Generated at (UTC): {datetime.now(UTC).isoformat()}",
        f"- Overall pass: {passed}",
        f"- Release blocked: {release_blocked}",
        "",
        "## Checks",
    ]
    for row in findings:
        lines.append(f"- `{row['check']}`: {row['status']} - {row['detail']}")
    output_path.write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    args = parse_args()
    findings: list[dict[str, Any]] = []

    dataset_path = Path(args.dataset_path)
    model_path = Path(args.model_path)
    metrics_path = Path(args.metrics_path)
    drift_baseline_path = Path(args.drift_baseline_path)

    data_ok = _check_file_exists(dataset_path, "dataset", findings)
    model_ok = _check_file_exists(model_path, "model", findings)
    metrics_ok = _check_file_exists(metrics_path, "metrics", findings)
    drift_ok = _check_file_exists(drift_baseline_path, "drift_baseline", findings)

    if data_ok:
        dataset = pd.read_csv(dataset_path)
        min_rows = 200
        if len(dataset) >= min_rows:
            findings.append(
                {
                    "check": "dataset_size",
                    "status": "pass",
                    "detail": f"rows={len(dataset)} (>= {min_rows})",
                }
            )
        else:
            findings.append(
                {
                    "check": "dataset_size",
                    "status": "fail",
                    "detail": f"rows={len(dataset)} (< {min_rows})",
                }
            )

    metrics_payload: dict[str, Any] = {}
    if metrics_ok:
        metrics_payload = json.loads(metrics_path.read_text(encoding="utf-8"))
        test_metrics = metrics_payload.get("test_metrics", {})
        roc_auc = float(test_metrics.get("roc_auc", 0.0))
        pr_auc = float(test_metrics.get("pr_auc", 0.0))
        if roc_auc >= args.min_roc_auc:
            findings.append(
                {
                    "check": "test_roc_auc",
                    "status": "pass",
                    "detail": f"{roc_auc:.4f} >= {args.min_roc_auc:.4f}",
                }
            )
        else:
            findings.append(
                {
                    "check": "test_roc_auc",
                    "status": "fail",
                    "detail": f"{roc_auc:.4f} < {args.min_roc_auc:.4f}",
                }
            )

        if pr_auc >= args.min_pr_auc:
            findings.append(
                {
                    "check": "test_pr_auc",
                    "status": "pass",
                    "detail": f"{pr_auc:.4f} >= {args.min_pr_auc:.4f}",
                }
            )
        else:
            findings.append(
                {
                    "check": "test_pr_auc",
                    "status": "fail",
                    "detail": f"{pr_auc:.4f} < {args.min_pr_auc:.4f}",
                }
            )

        class_balance = metrics_payload.get("class_balance", {})
        train_rate = float(class_balance.get("train_positive_rate", 0.0))
        test_rate = float(class_balance.get("test_positive_rate", 0.0))
        rate_gap = abs(train_rate - test_rate)
        if rate_gap <= args.max_positive_rate_gap:
            findings.append(
                {
                    "check": "class_balance_stability",
                    "status": "pass",
                    "detail": (
                        f"|train-test|={rate_gap:.4f} <= "
                        f"{args.max_positive_rate_gap:.4f}"
                    ),
                }
            )
        else:
            findings.append(
                {
                    "check": "class_balance_stability",
                    "status": "fail",
                    "detail": (
                        f"|train-test|={rate_gap:.4f} > "
                        f"{args.max_positive_rate_gap:.4f}"
                    ),
                }
            )

        selected = metrics_payload.get("selected_features", [])
        if isinstance(selected, list) and len(selected) >= 5:
            findings.append(
                {
                    "check": "selected_features_count",
                    "status": "pass",
                    "detail": f"{len(selected)} features selected",
                }
            )
        else:
            findings.append(
                {
                    "check": "selected_features_count",
                    "status": "fail",
                    "detail": "Selected features missing or too few (<5)",
                }
            )

        if data_ok and isinstance(selected, list):
            missing_selected = [f for f in selected if f not in dataset.columns]
            if not missing_selected:
                findings.append(
                    {
                        "check": "selected_features_in_dataset",
                        "status": "pass",
                        "detail": "All selected features found in dataset",
                    }
                )
            else:
                findings.append(
                    {
                        "check": "selected_features_in_dataset",
                        "status": "fail",
                        "detail": f"Missing in dataset: {missing_selected}",
                    }
                )

    if drift_ok:
        drift_payload = json.loads(drift_baseline_path.read_text(encoding="utf-8"))
        has_edges = isinstance(drift_payload.get("bin_edges"), list)
        has_dist = isinstance(drift_payload.get("test_distribution"), list)
        if has_edges and has_dist:
            findings.append(
                {
                    "check": "drift_baseline_structure",
                    "status": "pass",
                    "detail": "bin_edges and test_distribution are present",
                }
            )
        else:
            findings.append(
                {
                    "check": "drift_baseline_structure",
                    "status": "fail",
                    "detail": "Invalid drift baseline format",
                }
            )

    failed_checks = [f for f in findings if f["status"] == "fail"]
    passed = len(failed_checks) == 0
    release_blocked = not passed

    report = {
        "generated_at_utc": datetime.now(UTC).isoformat(),
        "passed": passed,
        "release_blocked": release_blocked,
        "checks": findings,
    }

    output_json = Path(args.output_json)
    output_json.parent.mkdir(parents=True, exist_ok=True)
    output_json.write_text(json.dumps(report, indent=2), encoding="utf-8")

    output_md = Path(args.output_md)
    output_md.parent.mkdir(parents=True, exist_ok=True)
    _write_markdown(
        output_path=output_md,
        findings=findings,
        passed=passed,
        release_blocked=release_blocked,
    )

    if release_blocked:
        raise RuntimeError(
            f"Preflight failed with {len(failed_checks)} failing checks. See {output_json}"
        )

    print(f"[done] preflight passed. report={output_json}")


if __name__ == "__main__":
    main()


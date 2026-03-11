from __future__ import annotations

import argparse
from datetime import UTC, datetime
import json
from pathlib import Path
from typing import Any

import pandas as pd


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Validate final DS/SWE submission readiness from generated notebook artifacts."
        )
    )
    parser.add_argument(
        "--metrics-path",
        default="ml/models/churn_reorder_metrics.json",
        help="Model metrics JSON.",
    )
    parser.add_argument(
        "--model-release-path",
        default="ml/models/release_preflight_report.json",
        help="Notebook 07 release report JSON.",
    )
    parser.add_argument(
        "--causal-release-path",
        default="ml/data/reports/causal/causal_release_decision.json",
        help="Notebook 08 causal decision JSON.",
    )
    parser.add_argument(
        "--deploy-summary-path",
        default="ml/data/reports/churn/deployment_scoring_summary.json",
        help="Deployment scoring summary JSON.",
    )
    parser.add_argument(
        "--cohort-summary-path",
        default="ml/data/reports/causal/cohort_time_series/cohort_time_series_summary.json",
        help="Cohort/time-series summary JSON.",
    )
    parser.add_argument(
        "--scoring-latest-path",
        default="ml/data/churn_scoring_latest.csv",
        help="Batch scoring output CSV.",
    )
    parser.add_argument(
        "--watchlist-path",
        default="ml/data/churn_scoring_top_watchlist.csv",
        help="Top watchlist CSV.",
    )
    parser.add_argument(
        "--min-roc-auc",
        type=float,
        default=0.60,
        help="Minimum test ROC-AUC.",
    )
    parser.add_argument(
        "--min-pr-auc",
        type=float,
        default=0.40,
        help="Minimum test PR-AUC.",
    )
    parser.add_argument(
        "--max-brier",
        type=float,
        default=0.20,
        help="Maximum test Brier score.",
    )
    parser.add_argument(
        "--min-scored-users",
        type=int,
        default=100,
        help="Minimum scored users required for stable deployment monitoring.",
    )
    parser.add_argument(
        "--min-cohorts",
        type=int,
        default=3,
        help="Minimum cohort count.",
    )
    parser.add_argument(
        "--min-periods",
        type=int,
        default=4,
        help="Minimum max cohort period.",
    )
    parser.add_argument(
        "--max-daily-anomalies",
        type=int,
        default=12,
        help="Maximum daily anomalies for a clean pass.",
    )
    parser.add_argument(
        "--output-json",
        default="ml/data/reports/churn/final_submission_validation.json",
        help="Validation report JSON output path.",
    )
    parser.add_argument(
        "--output-md",
        default="ml/data/reports/churn/final_submission_validation.md",
        help="Validation report markdown output path.",
    )
    parser.add_argument(
        "--fail-on-warn",
        action="store_true",
        help="Treat warnings as failures for strict enforcement.",
    )
    return parser.parse_args()


def _safe_float(value: Any) -> float:
    try:
        parsed = float(value)
        if pd.isna(parsed):
            return float("nan")
        return parsed
    except (TypeError, ValueError):
        return float("nan")


def _safe_int(value: Any) -> int | None:
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _status(ok: bool, *, warn: bool = False) -> str:
    if ok:
        return "pass"
    return "warn" if warn else "fail"


def _read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _add_result(
    rows: list[dict[str, Any]],
    *,
    domain: str,
    check: str,
    status: str,
    value: Any,
    threshold: Any,
    evidence: str,
    detail: str,
) -> None:
    rows.append(
        {
            "domain": domain,
            "check": check,
            "status": status,
            "value": value,
            "threshold": threshold,
            "evidence": evidence,
            "detail": detail,
        }
    )


def _to_markdown(report: dict[str, Any]) -> str:
    lines = [
        "# Final Submission Validation",
        "",
        f"- Generated at (UTC): {report['generated_at_utc']}",
        f"- Final status: `{report['final_status']}`",
        f"- Pass checks: {report['summary']['pass']}",
        f"- Warn checks: {report['summary']['warn']}",
        f"- Fail checks: {report['summary']['fail']}",
        f"- Fail on warn: {report['config']['fail_on_warn']}",
        "",
        "## Findings",
    ]
    for row in report["checks"]:
        lines.append(
            f"- [{row['status'].upper()}] {row['domain']}::{row['check']} | "
            f"value={row['value']} | threshold={row['threshold']} | {row['detail']}"
        )
    return "\n".join(lines)


def main() -> None:
    args = parse_args()

    metrics_path = Path(args.metrics_path)
    model_release_path = Path(args.model_release_path)
    causal_release_path = Path(args.causal_release_path)
    deploy_summary_path = Path(args.deploy_summary_path)
    cohort_summary_path = Path(args.cohort_summary_path)
    scoring_latest_path = Path(args.scoring_latest_path)
    watchlist_path = Path(args.watchlist_path)

    output_json = Path(args.output_json)
    output_md = Path(args.output_md)

    checks: list[dict[str, Any]] = []

    required_paths = {
        "metrics_path": metrics_path,
        "model_release_path": model_release_path,
        "causal_release_path": causal_release_path,
        "deploy_summary_path": deploy_summary_path,
        "cohort_summary_path": cohort_summary_path,
        "scoring_latest_path": scoring_latest_path,
        "watchlist_path": watchlist_path,
    }
    for name, path in required_paths.items():
        _add_result(
            checks,
            domain="artifacts",
            check=f"{name}_exists",
            status=_status(path.exists()),
            value=path.exists(),
            threshold=True,
            evidence=str(path),
            detail="Required artifact must exist for submission.",
        )

    metrics: dict[str, Any] = {}
    if metrics_path.exists():
        metrics = _read_json(metrics_path)
        test_metrics = metrics.get("test_metrics", {})
        roc_auc = _safe_float(test_metrics.get("roc_auc"))
        pr_auc = _safe_float(test_metrics.get("pr_auc"))
        brier = _safe_float(
            test_metrics.get("brier_score")
            if "brier_score" in test_metrics
            else test_metrics.get("brier")
        )
        model_version = metrics.get("model_version")

        _add_result(
            checks,
            domain="model_quality",
            check="test_roc_auc",
            status=_status(roc_auc >= args.min_roc_auc),
            value=roc_auc,
            threshold=f">= {args.min_roc_auc}",
            evidence="churn_reorder_metrics.json :: test_metrics.roc_auc",
            detail="AUC threshold for ranking quality.",
        )
        _add_result(
            checks,
            domain="model_quality",
            check="test_pr_auc",
            status=_status(pr_auc >= args.min_pr_auc),
            value=pr_auc,
            threshold=f">= {args.min_pr_auc}",
            evidence="churn_reorder_metrics.json :: test_metrics.pr_auc",
            detail="PR-AUC threshold for positive-class quality.",
        )
        _add_result(
            checks,
            domain="model_quality",
            check="test_brier_score",
            status=_status(brier <= args.max_brier),
            value=brier,
            threshold=f"<= {args.max_brier}",
            evidence="churn_reorder_metrics.json :: test_metrics.brier_score",
            detail="Calibration quality for probability outputs.",
        )
        _add_result(
            checks,
            domain="model_quality",
            check="model_version_present",
            status=_status(bool(model_version)),
            value=model_version,
            threshold="non-empty",
            evidence="churn_reorder_metrics.json :: model_version",
            detail="Versioned model artifacts support reproducibility.",
        )

    model_release: dict[str, Any] = {}
    if model_release_path.exists():
        model_release = _read_json(model_release_path)
        preflight_decision = str(model_release.get("final_decision", "")).lower()
        blocked = bool(model_release.get("release_blocked"))
        preflight_fail = _safe_int(model_release.get("check_counts", {}).get("fail"))
        preflight_warn = _safe_int(model_release.get("check_counts", {}).get("warn"))
        readiness_score = _safe_float(model_release.get("readiness_score"))

        _add_result(
            checks,
            domain="gates",
            check="notebook_07_final_decision",
            status=_status(preflight_decision == "ship"),
            value=preflight_decision,
            threshold="ship",
            evidence="release_preflight_report.json :: final_decision",
            detail="Model system must pass production readiness gate.",
        )
        _add_result(
            checks,
            domain="gates",
            check="notebook_07_release_blocked",
            status=_status(blocked is False),
            value=blocked,
            threshold=False,
            evidence="release_preflight_report.json :: release_blocked",
            detail="Release should not be blocked at model gate.",
        )
        _add_result(
            checks,
            domain="gates",
            check="notebook_07_fail_count",
            status=_status((preflight_fail or 0) == 0),
            value=preflight_fail,
            threshold=0,
            evidence="release_preflight_report.json :: check_counts.fail",
            detail="No failing checks allowed in production preflight.",
        )
        _add_result(
            checks,
            domain="gates",
            check="notebook_07_warn_count",
            status=_status((preflight_warn or 0) == 0, warn=True),
            value=preflight_warn,
            threshold=0,
            evidence="release_preflight_report.json :: check_counts.warn",
            detail="Warnings should be zero for a clean final handoff.",
        )
        _add_result(
            checks,
            domain="gates",
            check="notebook_07_readiness_score",
            status=_status(readiness_score >= 0.95),
            value=readiness_score,
            threshold=">= 0.95",
            evidence="release_preflight_report.json :: readiness_score",
            detail="High readiness score reduces launch risk.",
        )

    causal_release: dict[str, Any] = {}
    if causal_release_path.exists():
        causal_release = _read_json(causal_release_path)
        causal_decision = str(causal_release.get("final_decision", "")).lower()
        causal_fail = _safe_int(causal_release.get("check_counts", {}).get("fail"))
        causal_warn = _safe_int(causal_release.get("check_counts", {}).get("warn"))
        causal_readiness = _safe_float(causal_release.get("readiness_score"))

        _add_result(
            checks,
            domain="gates",
            check="notebook_08_final_decision",
            status=_status(causal_decision == "ship"),
            value=causal_decision,
            threshold="ship",
            evidence="causal_release_decision.json :: final_decision",
            detail="Causal rollout must pass production decisioning gate.",
        )
        _add_result(
            checks,
            domain="gates",
            check="notebook_08_fail_count",
            status=_status((causal_fail or 0) == 0),
            value=causal_fail,
            threshold=0,
            evidence="causal_release_decision.json :: check_counts.fail",
            detail="No failing checks allowed in causal gate.",
        )
        _add_result(
            checks,
            domain="gates",
            check="notebook_08_warn_count",
            status=_status((causal_warn or 0) == 0, warn=True),
            value=causal_warn,
            threshold=0,
            evidence="causal_release_decision.json :: check_counts.warn",
            detail="Warnings should be zero for final submission quality.",
        )
        _add_result(
            checks,
            domain="gates",
            check="notebook_08_readiness_score",
            status=_status(causal_readiness >= 0.95),
            value=causal_readiness,
            threshold=">= 0.95",
            evidence="causal_release_decision.json :: readiness_score",
            detail="High readiness score indicates robust causal diagnostics.",
        )

    deploy_summary: dict[str, Any] = {}
    if deploy_summary_path.exists():
        deploy_summary = _read_json(deploy_summary_path)
        scored_users = _safe_int(deploy_summary.get("scored_users"))
        missing_selected = deploy_summary.get("missing_selected_features", [])
        deploy_version = deploy_summary.get("model_version")

        _add_result(
            checks,
            domain="deployment",
            check="deployment_scored_users",
            status=_status((scored_users or 0) >= args.min_scored_users),
            value=scored_users,
            threshold=f">= {args.min_scored_users}",
            evidence="deployment_scoring_summary.json :: scored_users",
            detail="Small batches produce unstable monitoring and cohort rates.",
        )
        _add_result(
            checks,
            domain="deployment",
            check="deployment_missing_selected_features",
            status=_status(len(missing_selected) == 0),
            value=len(missing_selected),
            threshold=0,
            evidence="deployment_scoring_summary.json :: missing_selected_features",
            detail="Scoring should use the same selected feature set as training.",
        )
        _add_result(
            checks,
            domain="deployment",
            check="deployment_model_version_present",
            status=_status(bool(deploy_version)),
            value=deploy_version,
            threshold="non-empty",
            evidence="deployment_scoring_summary.json :: model_version",
            detail="Deployment report should be tied to a concrete model version.",
        )

    if metrics and deploy_summary:
        metrics_version = metrics.get("model_version")
        deploy_version = deploy_summary.get("model_version")
        _add_result(
            checks,
            domain="consistency",
            check="model_version_consistency_metrics_vs_deploy",
            status=_status(bool(metrics_version) and metrics_version == deploy_version),
            value={"metrics": metrics_version, "deploy": deploy_version},
            threshold="equal non-empty model_version",
            evidence="metrics.model_version vs deployment_scoring_summary.model_version",
            detail="Cross-artifact version consistency is required for auditability.",
        )

    cohort_summary: dict[str, Any] = {}
    if cohort_summary_path.exists():
        cohort_summary = _read_json(cohort_summary_path)
        cohorts = _safe_int(cohort_summary.get("cohorts"))
        max_period = _safe_int(cohort_summary.get("max_period"))
        anomalies = _safe_int(cohort_summary.get("daily_anomalies"))

        _add_result(
            checks,
            domain="cohort_timeseries",
            check="cohort_count",
            status=_status((cohorts or 0) >= args.min_cohorts),
            value=cohorts,
            threshold=f">= {args.min_cohorts}",
            evidence="cohort_time_series_summary.json :: cohorts",
            detail="Sufficient cohort breadth improves external validity.",
        )
        _add_result(
            checks,
            domain="cohort_timeseries",
            check="cohort_period_depth",
            status=_status((max_period or 0) >= args.min_periods),
            value=max_period,
            threshold=f">= {args.min_periods}",
            evidence="cohort_time_series_summary.json :: max_period",
            detail="Sufficient period depth is needed for robust retention trends.",
        )
        anomaly_status = _status((anomalies or 0) <= args.max_daily_anomalies, warn=True)
        _add_result(
            checks,
            domain="cohort_timeseries",
            check="daily_anomaly_pressure",
            status=anomaly_status,
            value=anomalies,
            threshold=f"<= {args.max_daily_anomalies}",
            evidence="cohort_time_series_summary.json :: daily_anomalies",
            detail="Large anomaly counts can invalidate short-term comparisons.",
        )

    if scoring_latest_path.exists():
        scoring_df = pd.read_csv(scoring_latest_path)
        _add_result(
            checks,
            domain="scoring_outputs",
            check="scoring_latest_row_count",
            status=_status(len(scoring_df) >= args.min_scored_users),
            value=len(scoring_df),
            threshold=f">= {args.min_scored_users}",
            evidence=str(scoring_latest_path),
            detail="Scoring file should have enough rows to match deployment summary.",
        )
        available_columns = set(scoring_df.columns)
        has_probability_column = bool(
            {"churn_probability_30d", "churn_probability"}.intersection(available_columns)
        )
        has_risk_label = bool(
            {"predicted_churn_risk_30d", "churn_risk"}.intersection(available_columns)
        )
        has_bucket = "risk_bucket" in available_columns
        _add_result(
            checks,
            domain="scoring_outputs",
            check="scoring_latest_has_risk_columns",
            status=_status(has_probability_column and has_risk_label and has_bucket),
            value=sorted(
                list(
                    {
                        "churn_probability_30d",
                        "churn_probability",
                        "predicted_churn_risk_30d",
                        "churn_risk",
                        "risk_bucket",
                    }.intersection(available_columns)
                )
            ),
            threshold=(
                "contains risk probability column + risk label column + risk_bucket"
            ),
            evidence=str(scoring_latest_path),
            detail="Downstream dashboards and interventions require standard risk fields.",
        )

    if watchlist_path.exists():
        watchlist_df = pd.read_csv(watchlist_path)
        _add_result(
            checks,
            domain="scoring_outputs",
            check="watchlist_non_empty",
            status=_status(len(watchlist_df) > 0),
            value=len(watchlist_df),
            threshold="> 0",
            evidence=str(watchlist_path),
            detail="Top-watchlist should be materialized for business actioning.",
        )
        sort_col = None
        for candidate in ("churn_probability_30d", "churn_probability"):
            if candidate in watchlist_df.columns:
                sort_col = candidate
                break
        is_sorted = bool(watchlist_df[sort_col].is_monotonic_decreasing) if sort_col else False
        _add_result(
            checks,
            domain="scoring_outputs",
            check="watchlist_sorted_by_churn_probability",
            status=_status(is_sorted),
            value={"sorted": is_sorted, "column": sort_col},
            threshold="descending by churn_probability_30d or churn_probability",
            evidence=str(watchlist_path),
            detail="Watchlist ordering should prioritize highest-risk users first.",
        )

    summary = {
        "pass": sum(1 for row in checks if row["status"] == "pass"),
        "warn": sum(1 for row in checks if row["status"] == "warn"),
        "fail": sum(1 for row in checks if row["status"] == "fail"),
        "total": len(checks),
    }

    has_failures = summary["fail"] > 0
    has_warnings = summary["warn"] > 0
    final_status = (
        "pass"
        if not has_failures and (not args.fail_on_warn or not has_warnings)
        else "fail"
    )

    report = {
        "generated_at_utc": datetime.now(UTC).isoformat(),
        "final_status": final_status,
        "summary": summary,
        "config": {
            "min_roc_auc": args.min_roc_auc,
            "min_pr_auc": args.min_pr_auc,
            "max_brier": args.max_brier,
            "min_scored_users": args.min_scored_users,
            "min_cohorts": args.min_cohorts,
            "min_periods": args.min_periods,
            "max_daily_anomalies": args.max_daily_anomalies,
            "fail_on_warn": args.fail_on_warn,
        },
        "checks": checks,
    }

    output_json.parent.mkdir(parents=True, exist_ok=True)
    output_json.write_text(json.dumps(report, indent=2), encoding="utf-8")
    output_md.parent.mkdir(parents=True, exist_ok=True)
    output_md.write_text(_to_markdown(report), encoding="utf-8")

    print(
        "[final-submission-validate]",
        f"status={final_status}",
        f"pass={summary['pass']}",
        f"warn={summary['warn']}",
        f"fail={summary['fail']}",
    )

    if final_status != "pass":
        failed = [row for row in checks if row["status"] in {"fail", "warn"}]
        for row in failed:
            print(
                f"- [{row['status'].upper()}] {row['domain']}::{row['check']} "
                f"value={row['value']} threshold={row['threshold']}"
            )
        raise SystemExit(1)


if __name__ == "__main__":
    main()

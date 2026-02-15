from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def write_json_report(report: dict[str, Any], output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(report, indent=2), encoding="utf-8")


def write_markdown_report(report: dict[str, Any], output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(_to_markdown(report), encoding="utf-8")


def _to_markdown(report: dict[str, Any]) -> str:
    metadata = report["metadata"]
    summary = report["summary"]
    issue_lbs = report["issue_load_balancers"]

    lines: list[str] = []
    lines.append("# OCI Load Balancer Readiness Report")
    lines.append("")
    lines.append(f"- Generated (UTC): `{metadata['generated_at_utc']}`")
    lines.append(f"- Region: `{metadata['region']}`")
    lines.append(f"- Tenancy: `{metadata['tenancy_ocid']}`")
    lines.append("")

    lines.append("## Summary")
    lines.append("")
    lines.append("| Metric | Value |")
    lines.append("|---|---:|")
    lines.append(f"| Scanned Compartments | {summary['scanned_compartment_count']} |")
    lines.append(f"| Skipped Compartments | {summary['skipped_compartment_count']} |")
    lines.append(f"| Load Balancers | {summary['total_load_balancers']} |")
    lines.append(f"| Private LBs | {summary['total_private_load_balancers']} |")
    lines.append(f"| Public LBs | {summary['total_public_load_balancers']} |")
    lines.append(f"| Listeners | {summary['total_listeners']} |")
    lines.append(f"| Backend Sets | {summary['total_backend_sets']} |")
    lines.append(f"| Backends | {summary['total_backends']} |")
    lines.append(f"| LBs with Issues | {summary['load_balancers_with_issues']} |")
    lines.append("")

    lines.append("## Backend Set Health Status")
    lines.append("")
    lines.append("| Status | Count |")
    lines.append("|---|---:|")
    for status, count in sorted(summary["backend_set_health_status_counts"].items()):
        lines.append(f"| {status} | {count} |")
    if not summary["backend_set_health_status_counts"]:
        lines.append("| - | 0 |")
    lines.append("")

    lines.append("## LBs With Issues (Top 50)")
    lines.append("")
    lines.append("| Compartment | LB Name | State | Private | Issue Backend Sets |")
    lines.append("|---|---|---|---|---|")

    for lb in issue_lbs[:50]:
        issue_sets = [f"{item['name']}:{item['health_status']}" for item in lb["backend_sets"] if item["health_status"] != "OK"]
        lines.append(
            f"| {lb['compartment_name']} | {lb['display_name']} | {lb['lifecycle_state']} | "
            f"{lb['is_private']} | {', '.join(issue_sets) if issue_sets else '-'} |"
        )

    if not issue_lbs:
        lines.append("| - | - | - | - | No load balancer backend issues found. |")

    lines.append("")
    lines.append("## Full Data")
    lines.append("")
    lines.append("- Full machine-readable details are available in the JSON artifact.")

    return "\n".join(lines)

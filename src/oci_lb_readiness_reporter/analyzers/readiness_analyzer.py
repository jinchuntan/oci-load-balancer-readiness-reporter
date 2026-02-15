from __future__ import annotations

from collections import Counter
from datetime import datetime, timezone
from typing import Any


class ReadinessAnalyzer:
    def analyze(
        self,
        generated_at: datetime,
        region: str,
        tenancy_ocid: str,
        scanned_compartments: list[dict[str, Any]],
        skipped_compartments: list[dict[str, str]],
    ) -> dict[str, Any]:
        lb_rows: list[dict[str, Any]] = []

        backend_set_status_counter = Counter()
        backend_status_counter = Counter()
        total_listeners = 0
        total_backend_sets = 0
        total_backends = 0
        private_lb_count = 0
        public_lb_count = 0

        for compartment_data in scanned_compartments:
            compartment = compartment_data["compartment"]
            infra = compartment_data["infra"]

            for lb in compartment_data["load_balancers"]:
                lb_rows.append(
                    {
                        "compartment_id": compartment.id,
                        "compartment_name": compartment.name,
                        **lb,
                    }
                )

                total_listeners += lb["listener_count"]
                total_backend_sets += lb["backend_set_count"]
                total_backends += lb["backend_count"]

                if lb["is_private"]:
                    private_lb_count += 1
                else:
                    public_lb_count += 1

                for item in lb["backend_sets"]:
                    backend_set_status_counter[item["health_status"]] += 1
                    for backend in item["backends"]:
                        backend_status_counter[backend["health_status"]] += 1

                lb["infra_context"] = {
                    "instance_count_in_compartment": infra["instance_count"],
                    "vnic_attachment_count_in_compartment": infra["vnic_attachment_count"],
                }

        issue_lbs = [
            row
            for row in lb_rows
            if any(bs["health_status"] not in {"OK"} for bs in row["backend_sets"])
        ]

        issue_lbs.sort(
            key=lambda row: (
                0 if row["lifecycle_state"] != "ACTIVE" else 1,
                row["compartment_name"].lower(),
                row["display_name"].lower(),
            )
        )

        return {
            "metadata": {
                "report_name": "load_balancer_readiness_report",
                "generated_at_utc": generated_at.astimezone(timezone.utc).isoformat(),
                "region": region,
                "tenancy_ocid": tenancy_ocid,
            },
            "summary": {
                "scanned_compartment_count": len(scanned_compartments),
                "skipped_compartment_count": len(skipped_compartments),
                "total_load_balancers": len(lb_rows),
                "total_private_load_balancers": private_lb_count,
                "total_public_load_balancers": public_lb_count,
                "total_listeners": total_listeners,
                "total_backend_sets": total_backend_sets,
                "total_backends": total_backends,
                "backend_set_health_status_counts": dict(backend_set_status_counter),
                "backend_health_status_counts": dict(backend_status_counter),
                "load_balancers_with_issues": len(issue_lbs),
            },
            "skipped_compartments": skipped_compartments,
            "issue_load_balancers": issue_lbs,
            "load_balancers": lb_rows,
        }

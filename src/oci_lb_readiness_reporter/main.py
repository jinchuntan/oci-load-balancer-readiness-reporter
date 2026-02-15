from __future__ import annotations

import argparse
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from oci.exceptions import ServiceError

from .analyzers import ReadinessAnalyzer
from .clients import create_clients, create_oci_config
from .collectors import IdentityCollector, InfraCollector, LoadBalancerCollector
from .config import AppConfig
from .helpers import ObjectStorageUploader, write_json_report, write_markdown_report


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generate OCI Load Balancer readiness report.")
    parser.add_argument(
        "--skip-upload",
        action="store_true",
        help="Generate local reports only, do not upload to Object Storage.",
    )
    return parser.parse_args()


def discover_candidate_buckets(
    object_storage_client: Any,
    namespace: str,
    compartment_ids: list[str],
) -> list[str]:
    seen: set[str] = set()
    buckets: list[str] = []

    for compartment_id in compartment_ids:
        try:
            response = object_storage_client.list_buckets(
                namespace_name=namespace,
                compartment_id=compartment_id,
            )
        except ServiceError:
            continue

        for bucket in response.data:
            name = getattr(bucket, "name", None)
            if not name or name in seen:
                continue
            seen.add(name)
            buckets.append(name)

    return sorted(buckets)


def _map_lb_ip_addresses(lb: Any) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for item in getattr(lb, "ip_addresses", []) or []:
        rows.append(
            {
                "ip_address": getattr(item, "ip_address", None),
                "is_public": getattr(item, "is_public", None),
            }
        )
    return rows


def _map_subnets(lb: Any, subnet_by_id: dict[str, dict[str, str]]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for subnet_id in getattr(lb, "subnet_ids", []) or []:
        meta = subnet_by_id.get(subnet_id)
        rows.append(
            {
                "subnet_id": subnet_id,
                "subnet_name": meta.get("display_name") if meta else "UNKNOWN_SUBNET",
                "cidr_block": meta.get("cidr_block") if meta else "",
            }
        )
    return rows


def _map_nsgs(lb: Any, nsg_by_id: dict[str, dict[str, str]]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for nsg_id in getattr(lb, "network_security_group_ids", []) or []:
        meta = nsg_by_id.get(nsg_id)
        rows.append(
            {
                "nsg_id": nsg_id,
                "nsg_name": meta.get("display_name") if meta else "UNKNOWN_NSG",
            }
        )
    return rows


def _collect_lb_detail(
    lb: Any,
    lb_collector: LoadBalancerCollector,
    ip_to_instance: dict[str, dict[str, str]],
    subnet_by_id: dict[str, dict[str, str]],
    nsg_by_id: dict[str, dict[str, str]],
) -> dict[str, Any]:
    listeners = getattr(lb, "listeners", {}) or {}
    backend_sets = getattr(lb, "backend_sets", {}) or {}

    listener_rows = []
    for listener_name, listener in listeners.items():
        listener_rows.append(
            {
                "name": listener_name,
                "protocol": getattr(listener, "protocol", None),
                "port": getattr(listener, "port", None),
                "default_backend_set_name": getattr(listener, "default_backend_set_name", None),
                "path_route_set_name": getattr(listener, "path_route_set_name", None),
            }
        )

    backend_set_rows = []
    backend_count = 0

    for backend_set_name, backend_set in backend_sets.items():
        try:
            backend_set_health = lb_collector.get_backend_set_health(lb.id, backend_set_name)
            backend_set_status = getattr(backend_set_health, "status", "UNKNOWN")
        except Exception as exc:  # noqa: BLE001
            backend_set_health = None
            backend_set_status = "UNAVAILABLE"
            backend_set_health_error = str(exc)
        else:
            backend_set_health_error = None

        backend_rows = []

        for backend in getattr(backend_set, "backends", []) or []:
            backend_count += 1
            backend_name = getattr(backend, "name", "UNKNOWN_BACKEND")
            backend_ip = getattr(backend, "ip_address", None)

            try:
                backend_health = lb_collector.get_backend_health(lb.id, backend_set_name, backend_name)
                backend_status = getattr(backend_health, "status", "UNKNOWN")
            except Exception as exc:  # noqa: BLE001
                backend_status = "UNAVAILABLE"
                backend_health_error = str(exc)
            else:
                backend_health_error = None

            instance_meta = ip_to_instance.get(backend_ip or "", {})

            backend_rows.append(
                {
                    "name": backend_name,
                    "ip_address": backend_ip,
                    "port": getattr(backend, "port", None),
                    "weight": getattr(backend, "weight", None),
                    "backup": getattr(backend, "backup", None),
                    "drain": getattr(backend, "drain", None),
                    "offline": getattr(backend, "offline", None),
                    "health_status": backend_status,
                    "health_error": backend_health_error,
                    "mapped_instance_id": instance_meta.get("instance_id"),
                    "mapped_instance_name": instance_meta.get("instance_name"),
                    "mapped_vnic_id": instance_meta.get("vnic_id"),
                    "mapped_subnet_id": instance_meta.get("subnet_id"),
                }
            )

        backend_set_rows.append(
            {
                "name": backend_set_name,
                "policy": getattr(backend_set, "policy", None),
                "health_status": backend_set_status,
                "health_error": backend_set_health_error,
                "backend_count": len(backend_rows),
                "backends": backend_rows,
            }
        )

    return {
        "load_balancer_id": lb.id,
        "display_name": lb.display_name,
        "lifecycle_state": lb.lifecycle_state,
        "is_private": bool(getattr(lb, "is_private", False)),
        "shape_name": getattr(lb, "shape_name", None),
        "time_created": lb.time_created.astimezone(timezone.utc).isoformat() if getattr(lb, "time_created", None) else None,
        "ip_addresses": _map_lb_ip_addresses(lb),
        "subnets": _map_subnets(lb, subnet_by_id),
        "network_security_groups": _map_nsgs(lb, nsg_by_id),
        "listener_count": len(listener_rows),
        "listeners": listener_rows,
        "backend_set_count": len(backend_set_rows),
        "backend_count": backend_count,
        "backend_sets": backend_set_rows,
    }


def main() -> int:
    args = parse_args()

    try:
        app_config = AppConfig.from_env()
        oci_config = create_oci_config(app_config)
        clients = create_clients(oci_config)
    except Exception as exc:  # noqa: BLE001
        print(f"[ERROR] Failed to initialize: {exc}")
        return 1

    identity_collector = IdentityCollector(clients["identity"])
    lb_collector = LoadBalancerCollector(clients["load_balancer"])
    infra_collector = InfraCollector(clients["compute"], clients["network"])

    tenancy_ocid = oci_config["tenancy"]
    region = oci_config["region"]

    try:
        compartments = identity_collector.list_compartments(
            tenancy_ocid=tenancy_ocid,
            root_compartment_ocid=app_config.root_compartment_ocid,
            include_subcompartments=app_config.include_subcompartments,
        )
    except Exception as exc:  # noqa: BLE001
        print(f"[ERROR] Failed to list compartments: {exc}")
        return 1

    print(f"[INFO] Discovered {len(compartments)} accessible compartments.")

    scanned_compartments: list[dict[str, Any]] = []
    skipped_compartments: list[dict[str, str]] = []

    for index, compartment in enumerate(compartments, start=1):
        print(f"[INFO] [{index}/{len(compartments)}] Processing compartment: {compartment.name}")

        try:
            infra = infra_collector.build_context(compartment.id)
        except Exception as exc:  # noqa: BLE001
            skipped_compartments.append(
                {
                    "compartment_id": compartment.id,
                    "reason": f"infra collection failed: {exc}",
                }
            )
            print(f"[WARN] Skipping compartment infra collection: {compartment.name} ({exc})")
            continue

        try:
            lb_summaries = lb_collector.list_load_balancers(compartment.id)
        except Exception as exc:  # noqa: BLE001
            skipped_compartments.append(
                {
                    "compartment_id": compartment.id,
                    "reason": f"load balancer listing failed: {exc}",
                }
            )
            print(f"[WARN] Skipping compartment LB listing: {compartment.name} ({exc})")
            continue

        lb_rows: list[dict[str, Any]] = []

        for lb_summary in lb_summaries:
            try:
                lb = lb_collector.get_load_balancer(lb_summary.id)
                lb_rows.append(
                    _collect_lb_detail(
                        lb=lb,
                        lb_collector=lb_collector,
                        ip_to_instance=infra["ip_to_instance"],
                        subnet_by_id=infra["subnet_by_id"],
                        nsg_by_id=infra["nsg_by_id"],
                    )
                )
            except Exception as exc:  # noqa: BLE001
                print(f"[WARN] Failed to collect LB {lb_summary.display_name}: {exc}")

        scanned_compartments.append(
            {
                "compartment": compartment,
                "infra": infra,
                "load_balancers": lb_rows,
            }
        )

    generated_at = datetime.now(timezone.utc)
    analyzer = ReadinessAnalyzer()
    report = analyzer.analyze(
        generated_at=generated_at,
        region=region,
        tenancy_ocid=tenancy_ocid,
        scanned_compartments=scanned_compartments,
        skipped_compartments=skipped_compartments,
    )

    timestamp = generated_at.strftime("%Y%m%dT%H%M%SZ")
    output_dir = Path(app_config.output_dir)
    json_path = output_dir / f"lb_readiness_report_{timestamp}.json"
    markdown_path = output_dir / f"lb_readiness_report_{timestamp}.md"

    write_json_report(report, json_path)
    write_markdown_report(report, markdown_path)

    print(f"[INFO] JSON report written: {json_path}")
    print(f"[INFO] Markdown report written: {markdown_path}")

    if args.skip_upload:
        print("[INFO] Upload skipped (--skip-upload).")
        return 0

    try:
        namespace = app_config.object_storage_namespace or clients["object_storage"].get_namespace().data
    except Exception as exc:  # noqa: BLE001
        print(f"[ERROR] Failed to resolve Object Storage namespace: {exc}")
        return 2 if app_config.fail_on_upload_error else 0

    bucket_candidates: list[str] = []
    if app_config.object_storage_bucket:
        bucket_candidates.append(app_config.object_storage_bucket)

    if app_config.auto_discover_bucket:
        discovered = discover_candidate_buckets(
            object_storage_client=clients["object_storage"],
            namespace=namespace,
            compartment_ids=[item.id for item in compartments],
        )
        for bucket in discovered:
            if bucket not in bucket_candidates:
                bucket_candidates.append(bucket)

    if not bucket_candidates:
        print("[ERROR] No accessible Object Storage bucket found.")
        return 2 if app_config.fail_on_upload_error else 0

    upload_success = False
    last_error: str | None = None

    for bucket in bucket_candidates:
        uploader = ObjectStorageUploader(
            object_storage_client=clients["object_storage"],
            namespace=namespace,
            bucket=bucket,
            prefix=app_config.object_storage_prefix,
        )

        print(f"[INFO] Attempting upload using bucket: {bucket}")

        try:
            json_result = uploader.upload_file(json_path, "application/json")
            md_result = uploader.upload_file(markdown_path, "text/markdown")
            print(f"[INFO] Uploaded: {json_result.uri}")
            print(f"[INFO] Uploaded: {md_result.uri}")
            upload_success = True
            break
        except Exception as exc:  # noqa: BLE001
            last_error = str(exc)
            print(f"[WARN] Upload failed in bucket {bucket}: {exc}")

    if not upload_success:
        print("[ERROR] Upload failed for all bucket candidates.")
        if last_error:
            print(f"[ERROR] Last upload error: {last_error}")
        if app_config.fail_on_upload_error:
            return 2

    return 0


if __name__ == "__main__":
    raise SystemExit(main())

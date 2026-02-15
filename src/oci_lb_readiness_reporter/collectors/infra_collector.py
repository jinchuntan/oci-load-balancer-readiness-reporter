from __future__ import annotations

from collections import defaultdict
from typing import Any

from oci.pagination import list_call_get_all_results


class InfraCollector:
    def __init__(self, compute_client: Any, network_client: Any) -> None:
        self.compute_client = compute_client
        self.network_client = network_client

    def build_context(self, compartment_ocid: str) -> dict[str, Any]:
        instances = list_call_get_all_results(
            self.compute_client.list_instances,
            compartment_id=compartment_ocid,
        ).data

        instance_name_by_id = {item.id: item.display_name for item in instances}

        vnic_attachments = list_call_get_all_results(
            self.compute_client.list_vnic_attachments,
            compartment_id=compartment_ocid,
        ).data

        ip_to_instance: dict[str, dict[str, str]] = {}

        for attachment in vnic_attachments:
            vnic_id = getattr(attachment, "vnic_id", None)
            instance_id = getattr(attachment, "instance_id", None)
            if not vnic_id:
                continue

            vnic = self.network_client.get_vnic(vnic_id=vnic_id).data
            private_ip = getattr(vnic, "private_ip", None)
            if not private_ip:
                continue

            ip_to_instance[private_ip] = {
                "instance_id": instance_id or "",
                "instance_name": instance_name_by_id.get(instance_id, "UNKNOWN_INSTANCE"),
                "vnic_id": vnic_id,
                "subnet_id": getattr(vnic, "subnet_id", ""),
            }

        subnets = list_call_get_all_results(
            self.network_client.list_subnets,
            compartment_id=compartment_ocid,
        ).data

        subnet_by_id = {
            subnet.id: {
                "id": subnet.id,
                "display_name": subnet.display_name,
                "cidr_block": getattr(subnet, "cidr_block", ""),
                "vcn_id": subnet.vcn_id,
            }
            for subnet in subnets
        }

        nsgs = list_call_get_all_results(
            self.network_client.list_network_security_groups,
            compartment_id=compartment_ocid,
        ).data

        nsg_by_id = {
            nsg.id: {
                "id": nsg.id,
                "display_name": nsg.display_name,
                "vcn_id": nsg.vcn_id,
            }
            for nsg in nsgs
        }

        instances_by_subnet: dict[str, int] = defaultdict(int)
        for item in ip_to_instance.values():
            subnet_id = item.get("subnet_id", "")
            if subnet_id:
                instances_by_subnet[subnet_id] += 1

        return {
            "instance_count": len(instances),
            "vnic_attachment_count": len(vnic_attachments),
            "ip_to_instance": ip_to_instance,
            "subnet_by_id": subnet_by_id,
            "nsg_by_id": nsg_by_id,
            "instances_by_subnet": dict(instances_by_subnet),
        }

from __future__ import annotations

from typing import Any

from oci.pagination import list_call_get_all_results


class LoadBalancerCollector:
    def __init__(self, load_balancer_client: Any) -> None:
        self.load_balancer_client = load_balancer_client

    def list_load_balancers(self, compartment_ocid: str) -> list[Any]:
        return list_call_get_all_results(
            self.load_balancer_client.list_load_balancers,
            compartment_id=compartment_ocid,
        ).data

    def get_load_balancer(self, load_balancer_ocid: str) -> Any:
        return self.load_balancer_client.get_load_balancer(load_balancer_ocid).data

    def get_backend_set_health(self, load_balancer_ocid: str, backend_set_name: str) -> Any:
        return self.load_balancer_client.get_backend_set_health(
            load_balancer_id=load_balancer_ocid,
            backend_set_name=backend_set_name,
        ).data

    def get_backend_health(self, load_balancer_ocid: str, backend_set_name: str, backend_name: str) -> Any:
        return self.load_balancer_client.get_backend_health(
            load_balancer_id=load_balancer_ocid,
            backend_set_name=backend_set_name,
            backend_name=backend_name,
        ).data

import json
import subprocess
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

from dashboard.providers.base import BaseResourceProvider, Resource, ResourceMetrics, MetricPoint


def _load_config():
    try:
        with open("dashboard_config.json") as f:
            return json.load(f)
    except FileNotFoundError:
        return {}


def _tccli(service: str, action: str, region: str, payload: Optional[Dict] = None) -> Dict[str, Any]:
    cmd = ["tccli", service, action, "--region", region, "--output", "json"]
    if payload:
        cmd.extend(["--cli-input-json", json.dumps(payload)])
    result = subprocess.run(cmd, capture_output=True, text=True, check=True)
    return json.loads(result.stdout)


class TencentProvider(BaseResourceProvider):
    @property
    def name(self) -> str:
        return "tencent"

    def is_enabled(self) -> bool:
        cfg = _load_config().get("providers", {}).get("tencent", {})
        return cfg.get("enabled", False)

    def regions(self) -> List[str]:
        cfg = _load_config().get("providers", {}).get("tencent", {})
        return cfg.get("regions", [])

    def resource_types(self) -> List[str]:
        return ["cvm", "lighthouse"]

    def discover_resources(self, region: str, resource_type: Optional[str] = None) -> List[Resource]:
        results = []
        types_to_query = [resource_type] if resource_type else self.resource_types()
        for rt in types_to_query:
            if rt == "cvm":
                results.extend(self._discover_cvm(region))
            elif rt == "lighthouse":
                results.extend(self._discover_lighthouse(region))
        return results

    def _discover_cvm(self, region: str) -> List[Resource]:
        data = _tccli("cvm", "DescribeInstances", region)
        resources = []
        for inst in data.get("InstanceSet", []):
            resources.append(Resource(
                provider="tencent",
                resource_type="cvm",
                region=region,
                id=inst["InstanceId"],
                name=inst.get("InstanceName", inst["InstanceId"]),
                status=inst.get("InstanceState", "UNKNOWN"),
                class_type=inst.get("InstanceType"),
                os_or_engine=inst.get("OsName"),
                tags={t["Key"]: t["Value"] for t in inst.get("Tags", [])},
                meta={"CreatedTime": inst.get("CreatedTime")},
            ))
        return resources

    def _discover_lighthouse(self, region: str) -> List[Resource]:
        data = _tccli("lighthouse", "DescribeInstances", region)
        resources = []
        for inst in data.get("InstanceSet", []):
            resources.append(Resource(
                provider="tencent",
                resource_type="lighthouse",
                region=region,
                id=inst["InstanceId"],
                name=inst.get("InstanceName", inst["InstanceId"]),
                status=inst.get("InstanceState", "UNKNOWN"),
                class_type=inst.get("BundleId"),
                os_or_engine=inst.get("OsName"),
                tags={},
                meta={"CreatedTime": inst.get("CreatedTime")},
            ))
        return resources

    def get_metrics(self, resource: Resource, range_days: int = 7) -> ResourceMetrics:
        end = datetime.utcnow()
        start = end - timedelta(days=range_days)
        namespace = "QCE/CVM" if resource.resource_type == "cvm" else "QCE/LIGHTHOUSE"
        payload = {
            "Namespace": namespace,
            "MetricName": "CPUUsage",
            "Instances": [{"Dimensions": [{"Name": "InstanceId", "Value": resource.id}]}],
            "Period": 3600,
            "StartTime": start.isoformat(),
            "EndTime": end.isoformat(),
        }
        data = _tccli("monitor", "GetMonitorData", resource.region, payload)
        points = []
        for dp in data.get("DataPoints", []):
            for ts, val in zip(dp.get("Timestamps", []), dp.get("Values", [])):
                points.append(MetricPoint(timestamp=datetime.utcfromtimestamp(ts), value=val))
        points.sort(key=lambda p: p.timestamp)
        return ResourceMetrics(
            resource_id=resource.unique_id,
            metric_name="cpu_utilization",
            points_7d=points,
            points_30d=[],
        )

    def sync_metrics_to_store(self, store, backfill_days: int = 1) -> None:
        for region in self.regions():
            for rt in self.resource_types():
                for resource in self.discover_resources(region, rt):
                    metrics = self.get_metrics(resource, range_days=backfill_days)
                    for p in metrics.points_7d:
                        store.write_hourly([
                            (resource.unique_id, "cpu_utilization", int(p.timestamp.timestamp()), p.value, resource.region)
                        ])

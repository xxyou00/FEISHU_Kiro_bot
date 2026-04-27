import json
import pytest
from unittest.mock import patch, MagicMock
from dashboard.providers.tencent import TencentProvider
from dashboard.providers.base import Resource


@pytest.fixture
def provider():
    with patch("dashboard.providers.tencent._load_config") as m:
        m.return_value = {"providers": {"tencent": {"enabled": True, "regions": ["ap-tokyo"]}}}
        yield TencentProvider()


def test_name(provider):
    assert provider.name == "tencent"


def test_resource_types(provider):
    assert set(provider.resource_types()) == {"cvm", "lighthouse"}


@patch("dashboard.providers.tencent.subprocess.run")
def test_discover_cvm(mock_run, provider):
    with open("tests/fixtures/tencent_cvm_describe.json") as f:
        data = json.load(f)
    mock_run.return_value = MagicMock(stdout=json.dumps(data), returncode=0)
    resources = provider.discover_resources("ap-tokyo", "cvm")
    assert len(resources) == 1
    assert resources[0].id == "ins-123456"
    assert resources[0].provider == "tencent"
    assert resources[0].resource_type == "cvm"
    assert resources[0].unique_id == "tencent:cvm:ap-tokyo:ins-123456"


@patch("dashboard.providers.tencent.subprocess.run")
def test_get_metrics(mock_run, provider):
    with open("tests/fixtures/tencent_monitor_cpu.json") as f:
        data = json.load(f)
    mock_run.return_value = MagicMock(stdout=json.dumps(data), returncode=0)
    r = Resource(provider="tencent", resource_type="cvm", region="ap-tokyo", id="ins-123456", name="t", status="RUNNING")
    metrics = provider.get_metrics(r, range_days=7)
    assert metrics.metric_name == "cpu_utilization"
    assert len(metrics.points_7d) == 2

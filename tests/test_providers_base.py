import pytest
from dashboard.providers.base import Resource, MetricPoint, ResourceMetrics, BaseResourceProvider


def test_resource_unique_id():
    r = Resource(provider="aws", type="ec2", region="cn-north-1", id="i-123", name="test", status="running")
    assert r.unique_id == "aws:ec2:cn-north-1:i-123"


def test_resource_defaults():
    r = Resource(provider="tencent", type="cvm", region="ap-tokyo", id="ins-1", name="t", status="RUNNING")
    assert r.tags == {}
    assert r.meta == {}
    assert r.class_type is None


def test_base_provider_is_abstract():
    with pytest.raises(TypeError):
        BaseResourceProvider()

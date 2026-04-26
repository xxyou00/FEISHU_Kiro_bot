# tests/test_sync_resource_metrics.py
from datetime import datetime, timedelta, timezone
from unittest.mock import patch, MagicMock

from dashboard.resources import Resource

from scripts.sync_resource_metrics import parse_args


def test_parse_args_backfill():
    args = parse_args(["--backfill"])
    assert args.backfill is True
    assert args.incremental is False


def test_parse_args_incremental():
    args = parse_args(["--incremental"])
    assert args.backfill is False
    assert args.incremental is True


def test_parse_args_downsample():
    args = parse_args(["--downsample", "2026", "3"])
    assert args.downsample == [2026, 3]


def test_backfill_flow():
    resource = Resource(
        id="ec2:us-east-1:i-123",
        type="ec2",
        name="test",
        raw_id="i-123",
        status="running",
        meta={"region": "us-east-1"},
    )

    mock_point_time = datetime(2026, 4, 25, 10, 0, 0, tzinfo=timezone.utc)
    mock_cw_response = {
        "Datapoints": [
            {"Timestamp": mock_point_time, "Average": 15.5},
        ]
    }

    with patch("scripts.sync_resource_metrics.discover_all", return_value=[resource]):
        with patch("boto3.client") as mock_client:
            mock_cw = MagicMock()
            mock_cw.get_metric_statistics.return_value = mock_cw_response
            mock_client.return_value = mock_cw
            from scripts.sync_resource_metrics import run_backfill
            import tempfile
            with tempfile.TemporaryDirectory() as tmpdir:
                count = run_backfill(base_dir=tmpdir)
                assert count >= 1

#!/usr/bin/env python3
# scripts/sync_resource_metrics.py
import argparse
import datetime
import logging
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from dashboard.resources import discover_all
from dashboard.metrics_store import MetricsStore

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
logger = logging.getLogger("sync_resource_metrics")


def parse_args(argv=None):
    parser = argparse.ArgumentParser(description="Sync resource metrics from CloudWatch to local SQLite")
    parser.add_argument("--backfill", action="store_true", help="Backfill past 30 days of hourly data")
    parser.add_argument("--incremental", action="store_true", help="Sync previous 24 hours")
    parser.add_argument("--downsample", nargs=2, type=int, metavar=("YEAR", "MONTH"), help="Downsample a specific month")
    parser.add_argument("--base-dir", default=None, help="Override metrics base directory")
    return parser.parse_args(argv)


def fetch_cloudwatch_hourly(resource, metric_name="CPUUtilization", hours=24, end=None):
    try:
        import boto3
    except ImportError:
        logger.warning("boto3 not installed, skipping CloudWatch fetch")
        return []

    region = resource.meta.get("region")
    kwargs = {"region_name": region} if region else {}
    client = boto3.client("cloudwatch", **kwargs)

    if end is None:
        end = datetime.datetime.utcnow()
    start = end - datetime.timedelta(hours=hours)

    if resource.type == "ec2":
        namespace = "AWS/EC2"
        dimension_name = "InstanceId"
        dimension_value = resource.raw_id
    elif resource.type == "rds":
        namespace = "AWS/RDS"
        dimension_name = "DBInstanceIdentifier"
        dimension_value = resource.raw_id
    else:
        return []

    resp = client.get_metric_statistics(
        Namespace=namespace,
        MetricName=metric_name,
        Dimensions=[{"Name": dimension_name, "Value": dimension_value}],
        StartTime=start,
        EndTime=end,
        Period=3600,
        Statistics=["Average"],
    )

    points = sorted(resp.get("Datapoints", []), key=lambda x: x["Timestamp"])
    records = []
    for p in points:
        ts = int(p["Timestamp"].replace(tzinfo=datetime.timezone.utc).timestamp())
        # Round to nearest hour
        ts = ts // 3600 * 3600
        records.append((resource.id, metric_name, ts, round(p["Average"], 2), region))
    return records

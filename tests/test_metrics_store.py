import os
import sqlite3
import tempfile
from datetime import datetime

import pytest

from dashboard.metrics_store import (
    MetricsStore,
    _raw_db_path,
    _aggregated_db_path,
)


def test_raw_db_path_format():
    path = _raw_db_path(2026, 4, base_dir="/tmp/metrics")
    assert path == "/tmp/metrics/raw_metrics_2026_04.db"


def test_aggregated_db_path():
    path = _aggregated_db_path(base_dir="/tmp/metrics")
    assert path == "/tmp/metrics/aggregated_metrics.db"

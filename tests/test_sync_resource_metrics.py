# tests/test_sync_resource_metrics.py
from unittest.mock import patch, MagicMock
import pytest

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

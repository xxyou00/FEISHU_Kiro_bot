import json
import os
import pytest
from dashboard.config_store import ConfigStore


@pytest.fixture
def old_config_file(tmp_path):
    path = tmp_path / "dashboard_config.json"
    path.write_text(json.dumps({"regions": ["cn-north-1"], "pins": ["ec2:cn-north-1:i-1"]}))
    return str(path)


@pytest.fixture
def new_config_file(tmp_path):
    path = tmp_path / "dashboard_config.json"
    path.write_text(json.dumps({
        "providers": {"aws": {"enabled": True, "regions": ["cn-north-1"]}},
        "pins": ["aws:ec2:cn-north-1:i-1"]
    }))
    return str(path)


def test_migrate_old_config(old_config_file, monkeypatch):
    monkeypatch.setattr("dashboard.config_store.CONFIG_PATH", old_config_file)
    store = ConfigStore()
    cfg = store.load()
    assert "providers" in cfg
    assert cfg["providers"]["aws"]["regions"] == ["cn-north-1"]
    assert cfg["pins"] == ["aws:ec2:cn-north-1:i-1"]


def test_read_new_config(new_config_file, monkeypatch):
    monkeypatch.setattr("dashboard.config_store.CONFIG_PATH", new_config_file)
    store = ConfigStore()
    cfg = store.load()
    assert cfg["providers"]["aws"]["enabled"] is True

#!/usr/bin/env python3
"""Tests for dashboard event CRUD API routes."""

import os
import pytest
from flask import Flask

from dashboard import dashboard_bp, _sessions
import dashboard.api  # noqa: F401 — registers routes via side effect
from event_store import EventStore


@pytest.fixture
def client(monkeypatch, tmp_path):
    """Create a test client with the dashboard blueprint registered."""
    monkeypatch.setattr("dashboard.DASHBOARD_TOKEN", "test-secret-token")
    _sessions.clear()

    # Use a temporary database for events
    test_db = str(tmp_path / "test_events.db")
    monkeypatch.setattr("event_store.DB_NAME", test_db)
    monkeypatch.setenv("ALERT_NOTIFY_USER_ID", "test-user")

    app = Flask(__name__)
    app.register_blueprint(dashboard_bp)
    with app.test_client() as c:
        yield c
    _sessions.clear()


@pytest.fixture
def auth_client(client):
    """Log in and return an authenticated test client."""
    resp = client.post("/api/dashboard/auth", json={"token": "test-secret-token"})
    assert resp.status_code == 200
    return client


def test_events_crud(auth_client):
    # 1. Create event via POST
    payload = {
        "id": "evt-dashboard-001",
        "event_type": "系统变更",
        "title": "Dashboard test event",
        "description": "Created from dashboard API",
        "source": "dashboard",
        "severity": "high",
    }
    resp = auth_client.post("/api/dashboard/events", json=payload)
    assert resp.status_code == 200
    assert resp.json["ok"] is True
    assert "event_id" in resp.json
    event_id = resp.json["event_id"]

    # 2. List events with source filter
    resp = auth_client.get("/api/dashboard/events?source=dashboard")
    assert resp.status_code == 200
    assert resp.json["ok"] is True
    events = resp.json["events"]
    assert len(events) >= 1
    ids = [e["id"] for e in events]
    assert event_id in ids

    # Verify event fields
    evt = next(e for e in events if e["id"] == event_id)
    assert evt["title"] == "Dashboard test event"
    assert evt["source"] == "dashboard"
    assert evt["severity"] == "high"

    # 3. Delete event
    resp = auth_client.delete(f"/api/dashboard/events/{event_id}")
    assert resp.status_code == 200
    assert resp.json == {"ok": True}

    # 4. Verify event is gone
    resp = auth_client.get("/api/dashboard/events?source=dashboard")
    assert resp.status_code == 200
    events = resp.json["events"]
    ids = [e["id"] for e in events]
    assert event_id not in ids

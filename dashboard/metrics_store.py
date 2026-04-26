import os
import sqlite3
from datetime import datetime, timedelta


DEFAULT_BASE_DIR = os.path.join(os.path.dirname(__file__), "..", "memory_db")


def _raw_db_path(year: int, month: int, base_dir: str | None = None) -> str:
    d = base_dir or DEFAULT_BASE_DIR
    return os.path.join(d, f"raw_metrics_{year}_{month:02d}.db")


def _aggregated_db_path(base_dir: str | None = None) -> str:
    d = base_dir or DEFAULT_BASE_DIR
    return os.path.join(d, "aggregated_metrics.db")


def _ensure_hourly_table(conn: sqlite3.Connection):
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS hourly_metrics (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            resource_id TEXT NOT NULL,
            metric_name TEXT NOT NULL,
            timestamp INTEGER NOT NULL,
            value REAL NOT NULL,
            region TEXT,
            created_at INTEGER DEFAULT (strftime('%s','now')),
            UNIQUE(resource_id, metric_name, timestamp)
        )
        """
    )
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_hourly_lookup ON hourly_metrics(resource_id, metric_name, timestamp)"
    )
    conn.commit()


def _ensure_daily_table(conn: sqlite3.Connection):
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS daily_aggregated (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            resource_id TEXT NOT NULL,
            metric_name TEXT NOT NULL,
            date TEXT NOT NULL,
            min_value REAL NOT NULL,
            avg_value REAL NOT NULL,
            p95_value REAL NOT NULL,
            max_value REAL NOT NULL,
            region TEXT,
            UNIQUE(resource_id, metric_name, date)
        )
        """
    )
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_daily_lookup ON daily_aggregated(resource_id, metric_name, date)"
    )
    conn.commit()


class MetricsStore:
    def __init__(self, base_dir: str | None = None):
        self.base_dir = base_dir or DEFAULT_BASE_DIR
        os.makedirs(self.base_dir, exist_ok=True)
        self._raw_conns: dict[str, sqlite3.Connection] = {}
        self._agg_conn: sqlite3.Connection | None = None

    def _raw_conn(self, year: int, month: int) -> sqlite3.Connection:
        key = f"{year}_{month:02d}"
        if key not in self._raw_conns:
            path = _raw_db_path(year, month, self.base_dir)
            conn = sqlite3.connect(path)
            _ensure_hourly_table(conn)
            self._raw_conns[key] = conn
        return self._raw_conns[key]

    def _agg_conn(self) -> sqlite3.Connection:
        if self._agg_conn is None:
            path = _aggregated_db_path(self.base_dir)
            conn = sqlite3.connect(path)
            _ensure_daily_table(conn)
            self._agg_conn = conn
        return self._agg_conn

    def close(self):
        for conn in self._raw_conns.values():
            conn.close()
        self._raw_conns.clear()
        if self._agg_conn:
            self._agg_conn.close()
            self._agg_conn = None

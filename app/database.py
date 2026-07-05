"""
SQLite persistence layer.

Chosen over a heavier TSDB (InfluxDB etc.) to keep the app to a single
container with zero external dependencies, while still fully satisfying
the "store metrics for historical analysis" requirement. Swapping this
module for InfluxDB/Timescale later is a drop-in change since all access
goes through the functions below.
"""
import sqlite3
import os
import json
import time
from contextlib import contextmanager
from . import config

os.makedirs(os.path.dirname(config.DB_PATH) or ".", exist_ok=True)


@contextmanager
def get_conn():
    conn = sqlite3.connect(config.DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def init_db():
    with get_conn() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS metrics (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                ts REAL NOT NULL,
                cpu_percent REAL,
                ram_used_gb REAL,
                ram_total_gb REAL,
                ram_percent REAL,
                disk_used_gb REAL,
                disk_total_gb REAL,
                disk_percent REAL,
                uptime_hours REAL,
                temp_celsius REAL
            )
        """)
        conn.execute("CREATE INDEX IF NOT EXISTS idx_metrics_ts ON metrics(ts)")

        conn.execute("""
            CREATE TABLE IF NOT EXISTS thresholds (
                metric TEXT PRIMARY KEY,
                value REAL NOT NULL
            )
        """)

        conn.execute("""
            CREATE TABLE IF NOT EXISTS alert_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                ts REAL NOT NULL,
                metric TEXT,
                value REAL,
                threshold REAL,
                message TEXT
            )
        """)

        # seed default thresholds if empty
        existing = conn.execute("SELECT COUNT(*) c FROM thresholds").fetchone()["c"]
        if existing == 0:
            for metric, value in config.DEFAULT_THRESHOLDS.items():
                conn.execute("INSERT INTO thresholds (metric, value) VALUES (?, ?)", (metric, value))


def insert_metric(sample: dict):
    with get_conn() as conn:
        conn.execute("""
            INSERT INTO metrics (ts, cpu_percent, ram_used_gb, ram_total_gb, ram_percent,
                                  disk_used_gb, disk_total_gb, disk_percent, uptime_hours, temp_celsius)
            VALUES (:ts, :cpu_percent, :ram_used_gb, :ram_total_gb, :ram_percent,
                    :disk_used_gb, :disk_total_gb, :disk_percent, :uptime_hours, :temp_celsius)
        """, sample)


def get_history(hours: float = 24):
    cutoff = time.time() - hours * 3600
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT * FROM metrics WHERE ts >= ? ORDER BY ts ASC", (cutoff,)
        ).fetchall()
        return [dict(r) for r in rows]


def get_latest():
    with get_conn() as conn:
        row = conn.execute("SELECT * FROM metrics ORDER BY ts DESC LIMIT 1").fetchone()
        return dict(row) if row else None


def get_thresholds():
    with get_conn() as conn:
        rows = conn.execute("SELECT metric, value FROM thresholds").fetchall()
        return {r["metric"]: r["value"] for r in rows}


def set_thresholds(new_values: dict):
    with get_conn() as conn:
        for metric, value in new_values.items():
            conn.execute("""
                INSERT INTO thresholds (metric, value) VALUES (?, ?)
                ON CONFLICT(metric) DO UPDATE SET value=excluded.value
            """, (metric, value))


def log_alert(metric, value, threshold, message):
    with get_conn() as conn:
        conn.execute(
            "INSERT INTO alert_log (ts, metric, value, threshold, message) VALUES (?, ?, ?, ?, ?)",
            (time.time(), metric, value, threshold, message)
        )


def get_recent_alerts(limit=20):
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT * FROM alert_log ORDER BY ts DESC LIMIT ?", (limit,)
        ).fetchall()
        return [dict(r) for r in rows]


def prune_old(days: int = 30):
    cutoff = time.time() - days * 86400
    with get_conn() as conn:
        conn.execute("DELETE FROM metrics WHERE ts < ?", (cutoff,))

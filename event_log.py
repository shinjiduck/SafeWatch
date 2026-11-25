"""Lưu lịch sử các lần cảnh báo SOS (Ngã đã leo thang, cử chỉ tay SOS, chuỗi
Signal for Help) vào SQLite — dùng chung giữa app.py (trang theo dõi trực
tiếp, ghi log) và pages/ (trang lịch sử, đọc log).

SQLite là lựa chọn nhẹ nhất cho demo/đồ án: 1 file, không cần cài server
riêng, có sẵn trong Python (module sqlite3).
"""

import os
import sqlite3
from datetime import datetime, timedelta

DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data", "events.db")


def _get_connection():
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    return sqlite3.connect(DB_PATH)


def init_db():
    with _get_connection() as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TEXT NOT NULL,
                event_type TEXT NOT NULL,
                details TEXT
            )
            """
        )
        # Nhật ký trạng thái hệ thống (mất/khôi phục camera, mất/khôi phục
        # quan sát người) — tách khỏi bảng events để không bị đếm thành "sự cố".
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS status_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TEXT NOT NULL,
                state TEXT NOT NULL,
                details TEXT
            )
            """
        )


def log_status(state, details=""):
    with _get_connection() as conn:
        conn.execute(
            "INSERT INTO status_log (timestamp, state, details) VALUES (?, ?, ?)",
            (datetime.now().isoformat(timespec="seconds"), state, details),
        )


def get_status_log(limit=200):
    with _get_connection() as conn:
        cursor = conn.execute(
            "SELECT timestamp, state, details FROM status_log ORDER BY id DESC LIMIT ?",
            (limit,),
        )
        return cursor.fetchall()


def log_event(event_type, details=""):
    with _get_connection() as conn:
        conn.execute(
            "INSERT INTO events (timestamp, event_type, details) VALUES (?, ?, ?)",
            (datetime.now().isoformat(timespec="seconds"), event_type, details),
        )


def get_events(limit=200):
    with _get_connection() as conn:
        cursor = conn.execute(
            "SELECT timestamp, event_type, details FROM events ORDER BY id DESC LIMIT ?",
            (limit,),
        )
        return cursor.fetchall()


def count_events_by_type():
    with _get_connection() as conn:
        cursor = conn.execute(
            "SELECT event_type, COUNT(*) FROM events GROUP BY event_type ORDER BY COUNT(*) DESC"
        )
        return cursor.fetchall()


def clear_events():
    with _get_connection() as conn:
        conn.execute("DELETE FROM events")


def prune_older_than(days):
    cutoff = (datetime.now() - timedelta(days=days)).isoformat(timespec="seconds")
    with _get_connection() as conn:
        cursor = conn.execute("DELETE FROM events WHERE timestamp < ?", (cutoff,))
        conn.execute("DELETE FROM status_log WHERE timestamp < ?", (cutoff,))
        return cursor.rowcount


# Phân loại sự kiện cho giao diện (Nhật ký, Tổng quan, Trực tiếp) — 1 chỗ duy nhất.
GROUP_FALL, GROUP_SOS = "Ngã", "SOS"
STATUS_ALARM, STATUS_RECOVERED, STATUS_VERIFYING = "Đã báo động", "Đã phục hồi", "Bắt đầu xác minh"


def classify(event_type):
    """Trả về (nhóm, trạng thái) của 1 loại sự kiện trong bảng events."""
    t = event_type or ""
    if t.startswith("Ngã - đã phục hồi"):
        return GROUP_FALL, STATUS_RECOVERED
    if t.startswith("Nghi ngã"):
        return GROUP_FALL, STATUS_VERIFYING
    if t.startswith("Ngã"):
        return GROUP_FALL, STATUS_ALARM
    return GROUP_SOS, STATUS_ALARM


def count_alarms_today():
    """Số lần THẬT SỰ báo động hôm nay (không tính lần đã phục hồi / lần nghi ngã đang xác minh)."""
    import time

    today = time.strftime("%Y-%m-%d")
    return sum(1 for ts, t, _ in get_events(limit=2000) if ts.startswith(today) and classify(t)[1] == STATUS_ALARM)

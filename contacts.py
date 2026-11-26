"""Lưu danh sách người liên hệ khẩn cấp — SQLite, CRUD thật (khác với mục
Camera/Tài khoản là mock tĩnh), vì đây là dữ liệu người dùng thực sự nhập
và cần giữ lại giữa các lần chạy app.
"""

import os
import sqlite3

DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data", "events.db")


def _get_connection():
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    return sqlite3.connect(DB_PATH)


def init_db():
    with _get_connection() as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS contacts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                relationship TEXT,
                phone TEXT,
                email TEXT,
                priority INTEGER DEFAULT 3,
                notify_enabled INTEGER DEFAULT 1
            )
            """
        )
        # DB tạo từ bản cũ chưa có cột này — thêm vào thay vì bắt xoá DB.
        columns = {row[1] for row in conn.execute("PRAGMA table_info(contacts)")}
        if "telegram_chat_id" not in columns:
            conn.execute("ALTER TABLE contacts ADD COLUMN telegram_chat_id TEXT")


def add_contact(name, relationship, phone, email, priority, telegram_chat_id=None):
    with _get_connection() as conn:
        conn.execute(
            "INSERT INTO contacts (name, relationship, phone, email, priority, notify_enabled, telegram_chat_id) "
            "VALUES (?, ?, ?, ?, ?, 1, ?)",
            (name, relationship, phone, email, priority, telegram_chat_id or None),
        )


def get_contacts():
    with _get_connection() as conn:
        cursor = conn.execute(
            "SELECT id, name, relationship, phone, email, priority, notify_enabled, telegram_chat_id "
            "FROM contacts ORDER BY priority ASC, id ASC"
        )
        return cursor.fetchall()


def get_alert_recipients():
    """Người liên hệ đang bật nhận cảnh báo, theo thứ tự ưu tiên (1 = cao nhất)
    — thứ tự này quyết định ai được chuyển tiếp trước (xem notifier.py)."""
    keys = ["id", "name", "relationship", "phone", "email", "priority", "notify_enabled", "telegram_chat_id"]
    return [dict(zip(keys, row)) for row in get_contacts() if row[6]]


def update_contact(contact_id, name, relationship, phone, email, priority, telegram_chat_id=None):
    """Sửa toàn bộ thông tin 1 người liên hệ (giữ nguyên trạng thái bật/tắt nhận cảnh báo)."""
    with _get_connection() as conn:
        conn.execute(
            "UPDATE contacts SET name = ?, relationship = ?, phone = ?, email = ?, priority = ?, telegram_chat_id = ? "
            "WHERE id = ?",
            (name, relationship, phone, email, priority, telegram_chat_id or None, contact_id),
        )


def set_telegram_chat_id(contact_id, chat_id):
    with _get_connection() as conn:
        conn.execute("UPDATE contacts SET telegram_chat_id = ? WHERE id = ?", (chat_id or None, contact_id))


def delete_contact(contact_id):
    with _get_connection() as conn:
        conn.execute("DELETE FROM contacts WHERE id = ?", (contact_id,))


def set_notify_enabled(contact_id, enabled):
    with _get_connection() as conn:
        conn.execute("UPDATE contacts SET notify_enabled = ? WHERE id = ?", (1 if enabled else 0, contact_id))

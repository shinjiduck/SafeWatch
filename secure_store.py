"""Mã hoá các trường dữ liệu cá nhân nhạy cảm khi lưu (số điện thoại, email, Telegram Chat ID, hồ sơ sức khoẻ).

Dùng Fernet (AES-128-CBC + HMAC-SHA256, thư viện `cryptography`). Lấy được file events.db / profile.json mà không
có khoá thì không đọc được các trường này.

Khoá lấy theo thứ tự:
  1. biến môi trường SAFEWATCH_DATA_KEY,
  2. `DATA_KEY` trong .streamlit/secrets.toml,
  3. file data/.data_key (tự tạo lần đầu, quyền 600). Cách 3 chỉ bảo vệ khi file CSDL bị chép riêng ra ngoài;
     muốn chắc hơn thì đặt khoá ở 1 hoặc 2 (khác chỗ với dữ liệu).
Mất khoá = mất các trường đã mã hoá -> sao lưu khoá cẩn thận.

Giá trị cũ chưa mã hoá (từ bản trước) vẫn đọc được; lần ghi tiếp theo sẽ mã hoá.
"""

import os
import threading

from cryptography.fernet import Fernet, InvalidToken

PREFIX = "enc1:"
KEY_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data", ".data_key")
_lock = threading.Lock()
_fernet = None


def _load_key():
    key = os.environ.get("SAFEWATCH_DATA_KEY", "")
    if not key:
        try:
            import streamlit as st

            key = str(st.secrets.get("DATA_KEY", ""))
        except Exception:  # noqa: BLE001 — không có secrets.toml / chạy ngoài Streamlit
            key = ""
    if key:
        return key.encode()
    if os.path.exists(KEY_FILE):
        with open(KEY_FILE, "rb") as f:
            return f.read().strip()
    os.makedirs(os.path.dirname(KEY_FILE), exist_ok=True)
    new = Fernet.generate_key()
    fd = os.open(KEY_FILE, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, "wb") as f:
        f.write(new)
    return new


def _f():
    global _fernet
    with _lock:
        if _fernet is None:
            _fernet = Fernet(_load_key())
        return _fernet


def reset_key_cache():
    """Kiểm thử đổi khoá."""
    global _fernet
    with _lock:
        _fernet = None


def encrypt(text):
    if text is None or text == "":
        return text
    text = str(text)
    if text.startswith(PREFIX):
        return text
    return PREFIX + _f().encrypt(text.encode("utf-8")).decode()


def decrypt(value):
    if not isinstance(value, str) or not value.startswith(PREFIX):
        return value
    try:
        return _f().decrypt(value[len(PREFIX):].encode()).decode("utf-8")
    except InvalidToken:
        return "(không giải mã được — sai khoá dữ liệu)"


def mask(value, keep=3):
    """Che bớt khi hiển thị: 0912345678 -> 091•••678; ten@gmail.com -> te•••@gmail.com."""
    v = str(value or "")
    if "@" in v:
        name, _, domain = v.partition("@")
        return (name[:2] + "•••@" + domain) if name else v
    return v if len(v) <= keep * 2 else v[:keep] + "•••" + v[-keep:]

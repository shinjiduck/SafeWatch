"""Hồ sơ người được giám sát (họ tên, ngày sinh, địa chỉ, ghi chú sức khoẻ...) — 1 hồ sơ, lưu file JSON.

Ghi chú sức khoẻ là dữ liệu nhạy cảm, nên CẢ hồ sơ được mã hoá khi lưu (secure_store, khoá riêng): mở file
profile.json chỉ thấy 1 chuỗi mã hoá. File cũ chưa mã hoá vẫn đọc được; lần lưu tiếp theo sẽ mã hoá.
"""

import json
import os

from secure_store import PREFIX, decrypt, encrypt

PROFILE_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data", "profile.json")

DEFAULT_PROFILE = {
    "name": "Người được giám sát",
    "email": "",
    "phone": "",
    "birth_date": "",
    "address": "",
    "health_notes": "",
    "watch_area": "Phòng khách",
}


def load_profile():
    merged = dict(DEFAULT_PROFILE)
    if not os.path.exists(PROFILE_PATH):
        return merged
    with open(PROFILE_PATH, "r", encoding="utf-8") as f:
        raw = json.load(f)
    if isinstance(raw, dict) and isinstance(raw.get("data"), str) and raw["data"].startswith(PREFIX):
        try:
            raw = json.loads(decrypt(raw["data"]))
        except ValueError:
            raw = {}
    merged.update({k: v for k, v in raw.items() if k in DEFAULT_PROFILE})
    return merged


def save_profile(profile):
    os.makedirs(os.path.dirname(PROFILE_PATH), exist_ok=True)
    data = {k: profile.get(k, DEFAULT_PROFILE[k]) for k in DEFAULT_PROFILE}
    payload = {"data": encrypt(json.dumps(data, ensure_ascii=False))}
    tmp = PROFILE_PATH + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(payload, f)
    if os.name != "nt":
        os.chmod(tmp, 0o600)
    os.replace(tmp, PROFILE_PATH)


def delete_profile():
    """Xoá hồ sơ (ghi đè rồi xoá file). Trả True nếu có file để xoá."""
    if not os.path.exists(PROFILE_PATH):
        return False
    size = os.path.getsize(PROFILE_PATH)
    with open(PROFILE_PATH, "r+b") as f:
        f.write(b"\0" * size)
        f.flush()
        os.fsync(f.fileno())
    os.remove(PROFILE_PATH)
    return True

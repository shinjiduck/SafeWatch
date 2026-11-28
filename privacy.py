"""Quyền riêng tư của người được giám sát (đặc tả chặng 2, mục 4.3 – 4.6):

- Sự đồng ý: lưu ai đồng ý, tự bấm hay ghi thay (bắt buộc lý do), phiên bản nội dung, lúc nào, lúc rút lại.
  Không có sự đồng ý còn hiệu lực -> không bắt đầu giám sát được.
- Tạm dừng vì riêng tư: tối đa MAX_PAUSE_MINUTES, tự bật lại; lúc tạm dừng AI không xử lý khung hình nào.
- Hạn lưu: tự xoá dữ liệu quá hạn ở cả 4 bảng (events, status_log, alerts, deliveries), không xoá cảnh báo đang chờ.
- Xoá 4 mức: 1 sự kiện / theo khoảng ngày / toàn bộ lịch sử / toàn bộ dữ liệu cá nhân. Xoá thật: DELETE trong 1 giao
  dịch với secure_delete (ghi đè số 0) rồi VACUUM; trả số dòng đã xoá từng bảng; ghi nhật ký truy cập.
- Video: không có gì để xoá — SafeWatch không lưu hình (tests/test_dong_bo_tai_lieu.py: test_khong_luu_hinh_anh_camera).
"""

import os
import time
from datetime import date, datetime, timedelta

import auth
import event_log
import profile_store

RETENTION_DEFAULT_DAYS = 30
RETENTION_MIN_DAYS, RETENTION_MAX_DAYS = 7, 365
MAX_PAUSE_MINUTES = 60
PAUSE_CHOICES = (15, 30, 60)
CONSENT_VERSION = "1"
from notifier import DISCLAIMER  # noqa: E402 — 1 câu duy nhất cho app, email, màn hình đồng ý

# Nội dung màn hình đồng ý (phiên bản CONSENT_VERSION — đổi nội dung thì tăng phiên bản để hỏi lại).
CONSENT_POINTS = [
    ("Camera dùng để làm gì", "Chỉ để phát hiện ngã không tự đứng dậy được và cử chỉ tay cầu cứu, rồi báo người nhà."),
    ("Không lưu video", "Hình ảnh chỉ nằm trong bộ nhớ vài phần trăm giây để tìm khung xương, rồi bị bỏ. Không ghi "
     "ra đĩa, không gửi cho người nhà, không ai xem lại được."),
    ("Nơi xử lý", "Bản đặt tại nhà xử lý ngay trên máy, ảnh không rời nhà. Bản trải nghiệm trên Streamlit Cloud gửi "
     "khung hình qua Internet (có mã hoá) lên máy chủ để xử lý, cũng không lưu."),
    ("Lưu gì, bao lâu", "Chỉ lưu chữ: loại sự cố, thời gian, ai đã xác nhận. Tự xoá sau thời hạn lưu (mặc định 30 ngày)."),
    ("Ai nhận cảnh báo", "Những người liên hệ khẩn cấp trong danh sách, qua Telegram / Email / SMS."),
    ("Quyền của bạn", "Tạm dừng giám sát bất cứ lúc nào (tối đa 60 phút, tự bật lại); xem và xoá lịch sử; rút lại sự "
     "đồng ý — rút lại thì giám sát dừng ngay."),
    ("Lưu ý", "Trong lúc tạm dừng, nếu ngã sẽ không có cảnh báo. " + DISCLAIMER),
]


def _conn():
    return event_log._get_connection()


def init_db():
    with _conn() as conn:
        conn.execute("CREATE TABLE IF NOT EXISTS settings_kv (key TEXT PRIMARY KEY, value TEXT)")
        conn.execute(
            """CREATE TABLE IF NOT EXISTS consents (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                version TEXT NOT NULL,
                given_by TEXT NOT NULL,
                given_by_role TEXT NOT NULL,
                on_behalf INTEGER NOT NULL DEFAULT 0,
                reason TEXT,
                given_at REAL NOT NULL,
                withdrawn_at REAL,
                withdrawn_by TEXT
            )"""
        )


def _get(key, default=None):
    with _conn() as conn:
        row = conn.execute("SELECT value FROM settings_kv WHERE key = ?", (key,)).fetchone()
    return default if row is None else row[0]


def _set(key, value):
    with _conn() as conn:
        conn.execute("INSERT INTO settings_kv (key, value) VALUES (?, ?) "
                     "ON CONFLICT(key) DO UPDATE SET value = excluded.value", (key, str(value)))


# ------------------------------------------------------------------ sự đồng ý

def active_consent():
    with _conn() as conn:
        conn.row_factory = auth._row
        return conn.execute("SELECT * FROM consents WHERE version = ? AND withdrawn_at IS NULL "
                            "ORDER BY id DESC LIMIT 1", (CONSENT_VERSION,)).fetchone()


def consent_history(limit=50):
    with _conn() as conn:
        conn.row_factory = auth._row
        return conn.execute("SELECT * FROM consents ORDER BY id DESC LIMIT ?", (limit,)).fetchall()


def give_consent(user, on_behalf=False, reason="", now=None):
    """user = tài khoản đang đăng nhập. Trả None nếu được, hoặc lý do bị từ chối."""
    role = user["role"]
    if on_behalf:
        if not auth.role_can(role, auth.CONSENT_ON_BEHALF):
            return "Chỉ quản trị được ghi thay sự đồng ý."
        if len((reason or "").strip()) < 10:
            return "Ghi thay cần nêu lý do cụ thể (ít nhất 10 ký tự), VD: người được giám sát bị sa sút trí nhớ."
    elif not auth.role_can(role, auth.CONSENT_SELF):
        return "Người được giám sát phải tự bấm đồng ý (hoặc quản trị ghi thay kèm lý do)."
    if active_consent():
        return None
    with _conn() as conn:
        conn.execute("INSERT INTO consents (version, given_by, given_by_role, on_behalf, reason, given_at) "
                     "VALUES (?, ?, ?, ?, ?, ?)", (CONSENT_VERSION, user["username"], role, 1 if on_behalf else 0,
                                                   (reason or "").strip()[:300], time.time() if now is None else now))
    auth.audit("ghi_thay_dong_y" if on_behalf else "dong_y_giam_sat", (reason or "").strip()[:200],
               who=(user["username"], role))
    return None


def withdraw_consent(user, now=None):
    if not auth.role_can(user["role"], auth.WITHDRAW_CONSENT):
        return "Bạn không có quyền rút lại sự đồng ý."
    with _conn() as conn:
        n = conn.execute("UPDATE consents SET withdrawn_at = ?, withdrawn_by = ? WHERE withdrawn_at IS NULL",
                         (time.time() if now is None else now, user["username"])).rowcount
    if n:
        auth.audit("rut_lai_dong_y", who=(user["username"], user["role"]))
        event_log.log_status("Đã rút lại sự đồng ý", f"Giám sát dừng — bởi {user['display_name']}")
    return None


# ------------------------------------------------------------------ tạm dừng vì riêng tư

def pause_until(now=None):
    """Thời điểm hết tạm dừng (epoch) nếu đang tạm dừng, ngược lại 0."""
    now = time.time() if now is None else now
    until = float(_get("pause_until", 0) or 0)
    return until if until > now else 0.0


def pause(minutes, who_label, now=None):
    now = time.time() if now is None else now
    minutes = max(1, min(int(minutes), MAX_PAUSE_MINUTES))
    until = now + minutes * 60
    _set("pause_until", until)
    event_log.log_status("Tạm dừng giám sát (riêng tư)",
                         f"{minutes} phút, tự bật lại lúc {datetime.fromtimestamp(until):%H:%M} — bởi {who_label}")
    auth.audit("tam_dung_giam_sat", f"{minutes} phút")
    return until


def resume(who_label):
    if pause_until():
        _set("pause_until", 0)
        event_log.log_status("Bật lại giám sát", f"Trước giờ hẹn — bởi {who_label}")
        auth.audit("bat_lai_giam_sat")


# ------------------------------------------------------------------ hạn lưu

def retention_days():
    try:
        return max(RETENTION_MIN_DAYS, min(int(_get("retention_days", RETENTION_DEFAULT_DAYS)), RETENTION_MAX_DAYS))
    except (TypeError, ValueError):
        return RETENTION_DEFAULT_DAYS


def set_retention_days(days):
    days = max(RETENTION_MIN_DAYS, min(int(days), RETENTION_MAX_DAYS))
    _set("retention_days", days)
    auth.audit("dat_han_luu", f"{days} ngày")
    return days


def _delete_alerts(conn, where, params):
    ids = [r[0] for r in conn.execute(f"SELECT id FROM alerts WHERE {where}", params).fetchall()]
    if not ids:
        return 0, 0
    marks = ",".join("?" * len(ids))
    deliveries = conn.execute(f"DELETE FROM deliveries WHERE alert_id IN ({marks})", ids).rowcount
    alerts = conn.execute(f"DELETE FROM alerts WHERE id IN ({marks})", ids).rowcount
    return alerts, deliveries


def _vacuum():
    conn = event_log._get_connection()
    try:
        conn.execute("VACUUM")
    finally:
        conn.close()


def prune(now=None, days=None):
    """Tự xoá dữ liệu quá hạn lưu (chạy lúc khởi động và mỗi giờ trong luồng gửi cảnh báo).
    Cảnh báo đang chờ xác nhận không bao giờ bị xoá ở đây."""
    now = time.time() if now is None else now
    days = retention_days() if days is None else days
    cutoff = now - days * 86400
    cutoff_iso = datetime.fromtimestamp(cutoff).isoformat(timespec="seconds")
    audit_cutoff = now - auth.AUDIT_RETENTION_DAYS * 86400
    with _conn() as conn:
        counts = {
            "events": conn.execute("DELETE FROM events WHERE timestamp < ?", (cutoff_iso,)).rowcount,
            "status_log": conn.execute("DELETE FROM status_log WHERE timestamp < ?", (cutoff_iso,)).rowcount,
        }
        counts["alerts"], counts["deliveries"] = _delete_alerts(conn, "raised_at < ? AND status != 'open'", (cutoff,))
        counts["audit_log"] = conn.execute("DELETE FROM audit_log WHERE at < ?", (audit_cutoff,)).rowcount
    if any(counts.values()):
        auth.audit("tu_xoa_qua_han", _fmt(counts), who=("(hệ thống)", ""))
    return counts


# ------------------------------------------------------------------ xoá theo yêu cầu

TABLE_NAMES = {"events": "sự cố", "status_log": "trạng thái hệ thống", "alerts": "cảnh báo",
               "deliveries": "lần gửi", "contacts": "người liên hệ", "consents": "lần đồng ý",
               "users": "tài khoản", "profile": "hồ sơ", "audit_log": "nhật ký truy cập"}


def _fmt(counts):
    return ", ".join(f"{n} {TABLE_NAMES.get(k, k)}" for k, n in counts.items() if n) or "không có dòng nào"


def _finish(level, counts, who):
    _vacuum()
    auth.audit(f"xoa_{level}", _fmt(counts), who=who)
    return counts


def delete_event(event_id, who=None):
    """Mức 1: 1 dòng sự cố trong Nhật ký."""
    with _conn() as conn:
        counts = {"events": conn.execute("DELETE FROM events WHERE id = ?", (int(event_id),)).rowcount}
    return _finish("1_su_kien", counts, who)


def delete_alert(alert_id, who=None):
    """Mức 1: 1 cảnh báo + các lần gửi của nó (đang gửi thì dừng luôn: bộ gửi chỉ đọc cảnh báo còn tồn tại)."""
    with _conn() as conn:
        counts = dict(zip(("alerts", "deliveries"), _delete_alerts(conn, "id = ?", (int(alert_id),))))
    return _finish("1_canh_bao", counts, who)


def delete_range(start, end, who=None):
    """Mức 2: mọi sự cố, trạng thái, cảnh báo, lần gửi từ ngày start tới hết ngày end (date)."""
    if isinstance(start, date) and not isinstance(start, datetime):
        start = datetime.combine(start, datetime.min.time())
    if isinstance(end, date) and not isinstance(end, datetime):
        end = datetime.combine(end, datetime.min.time()) + timedelta(days=1)
    lo, hi = start.isoformat(timespec="seconds"), end.isoformat(timespec="seconds")
    with _conn() as conn:
        counts = {
            "events": conn.execute("DELETE FROM events WHERE timestamp >= ? AND timestamp < ?", (lo, hi)).rowcount,
            "status_log": conn.execute("DELETE FROM status_log WHERE timestamp >= ? AND timestamp < ?",
                                       (lo, hi)).rowcount,
        }
        counts["alerts"], counts["deliveries"] = _delete_alerts(conn, "raised_at >= ? AND raised_at < ?",
                                                                (start.timestamp(), end.timestamp()))
    return _finish("2_khoang_ngay", counts, who)


def count_range(start, end):
    """Số dòng SẼ bị xoá nếu xoá theo khoảng ngày (để hiện trước khi xác nhận)."""
    s = datetime.combine(start, datetime.min.time())
    e = datetime.combine(end, datetime.min.time()) + timedelta(days=1)
    lo, hi = s.isoformat(timespec="seconds"), e.isoformat(timespec="seconds")
    with _conn() as conn:
        return {
            "events": conn.execute("SELECT COUNT(*) FROM events WHERE timestamp >= ? AND timestamp < ?",
                                   (lo, hi)).fetchone()[0],
            "status_log": conn.execute("SELECT COUNT(*) FROM status_log WHERE timestamp >= ? AND timestamp < ?",
                                       (lo, hi)).fetchone()[0],
            "alerts": conn.execute("SELECT COUNT(*) FROM alerts WHERE raised_at >= ? AND raised_at < ?",
                                   (s.timestamp(), e.timestamp())).fetchone()[0],
        }


def delete_all_history(who=None):
    """Mức 3: cả 4 bảng lịch sử."""
    with _conn() as conn:
        counts = {t: conn.execute(f"DELETE FROM {t}").rowcount for t in ("events", "status_log", "deliveries", "alerts")}
    return _finish("3_toan_bo_lich_su", counts, who)


def delete_all_personal(who=None):
    """Mức 4: mức 3 + người liên hệ + hồ sơ + lần đồng ý + mọi tài khoản trừ quản trị. Giám sát dừng (không còn
    sự đồng ý). Nhật ký truy cập giữ lại (chỉ có ai làm gì, lúc nào) để biết đã có lần xoá này."""
    with _conn() as conn:
        counts = {t: conn.execute(f"DELETE FROM {t}").rowcount
                  for t in ("events", "status_log", "deliveries", "alerts", "contacts", "consents")}
        counts["users"] = auth.delete_non_admin_users(conn)
        conn.execute("DELETE FROM settings_kv WHERE key = 'pause_until'")
    counts["profile"] = int(profile_store.delete_profile())
    return _finish("4_toan_bo_du_lieu", counts, who)


def seed_demo_events(n=20, days=10, now=None):
    """Sự cố MẪU (ghi rõ là mẫu) trải trên `days` ngày gần nhất — để trình diễn xoá theo ngày / toàn bộ."""
    import random

    now = time.time() if now is None else now
    rng = random.Random(7)
    kinds = [("Ngã (không đứng lên lại)", "[Dữ liệu mẫu] Sau 30s theo dõi"),
             ("Ngã - đã phục hồi", "[Dữ liệu mẫu] Đứng lên lại trong lúc theo dõi, không báo động"),
             ("Need Help", "[Dữ liệu mẫu] Độ tin cậy 91%")]
    with _conn() as conn:
        for _ in range(n):
            t = datetime.fromtimestamp(now - rng.uniform(0, days * 86400)).isoformat(timespec="seconds")
            kind, details = rng.choice(kinds)
            conn.execute("INSERT INTO events (timestamp, event_type, details) VALUES (?, ?, ?)", (t, kind, details))
    return n


def encrypt_existing():
    """Mã hoá dữ liệu nhạy cảm còn lưu dạng chữ thường từ bản cũ (SĐT, email, Chat ID, địa chỉ gửi, hồ sơ), rồi dọn
    khỏi file. Chạy lúc khởi động; dữ liệu đã mã hoá thì bỏ qua. Trả số dòng đã mã hoá."""
    from secure_store import PREFIX, encrypt

    def plain(v):
        return v not in (None, "") and not str(v).startswith(PREFIX)

    changed = 0
    with _conn() as conn:
        for cid, p, e, t in conn.execute("SELECT id, phone, email, telegram_chat_id FROM contacts").fetchall():
            if plain(p) or plain(e) or plain(t):
                conn.execute("UPDATE contacts SET phone = ?, email = ?, telegram_chat_id = ? WHERE id = ?",
                             (encrypt(p), encrypt(e), encrypt(t), cid))
                changed += 1
        for did, target in conn.execute("SELECT id, target FROM deliveries").fetchall():
            if plain(target):
                conn.execute("UPDATE deliveries SET target = ? WHERE id = ?", (encrypt(target), did))
                changed += 1
    if os.path.exists(profile_store.PROFILE_PATH):
        with open(profile_store.PROFILE_PATH, encoding="utf-8") as f:
            is_plain = PREFIX not in f.read()
        if is_plain:  # đọc xong, đóng file rồi mới ghi đè (Windows không thay được file đang mở)
            profile_store.save_profile(profile_store.load_profile())
            changed += 1
    if changed:
        _vacuum()
    return changed


def init_all():
    """Tạo mọi bảng cần cho phân quyền / quyền riêng tư và mã hoá dữ liệu cũ (gọi 1 lần lúc khởi động)."""
    event_log.init_db()
    import contacts
    import notifier

    contacts.init_db()
    notifier.init_db()
    auth.init_db()
    init_db()
    encrypt_existing()


def data_files():
    """Các file chứa dữ liệu cá nhân (cho trang Quyền riêng tư)."""
    base = os.path.dirname(event_log.DB_PATH)
    return [p for p in (event_log.DB_PATH, os.path.join(base, "profile.json")) if os.path.exists(p)]

"""Kiểm thử quyền riêng tư (privacy.py, secure_store.py, notifier): xoá 4 mức là xoá THẬT (không còn trong file),
hạn lưu tự xoá nhưng giữ cảnh báo đang chờ, sự đồng ý (ghi thay phải có lý do, rút lại được), tạm dừng,
mã hoá trường nhạy cảm, link xác nhận hết hạn sau 24 giờ.

Chạy: python -X utf8 tests/test_privacy.py   (hoặc pytest tests/)
"""

import os
import sys
import tempfile
import time
from datetime import date, datetime, timedelta

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from cryptography.fernet import Fernet  # noqa: E402

os.environ["SAFEWATCH_DATA_KEY"] = Fernet.generate_key().decode()  # khoá riêng cho kiểm thử, không đụng khoá thật

import auth  # noqa: E402
import contacts  # noqa: E402
import event_log  # noqa: E402
import notifier  # noqa: E402
import privacy  # noqa: E402
import profile_store  # noqa: E402
import secure_store  # noqa: E402

ADMIN = {"username": "boss", "role": auth.ROLE_ADMIN, "display_name": "Boss"}
CARE = {"username": "lan", "role": auth.ROLE_CAREGIVER, "display_name": "Lan"}
SUBJ = {"username": "ba", "role": auth.ROLE_SUBJECT, "display_name": "Ba"}


def fresh():
    secure_store.reset_key_cache()
    d = tempfile.mkdtemp()
    event_log.DB_PATH = contacts.DB_PATH = os.path.join(d, "events.db")
    profile_store.PROFILE_PATH = os.path.join(d, "profile.json")
    privacy.init_all()
    return event_log.DB_PATH


def add_event(ts, kind="Ngã (không đứng lên lại)", details="chi tiết"):
    with event_log._get_connection() as conn:
        conn.execute("INSERT INTO events (timestamp, event_type, details) VALUES (?, ?, ?)",
                     (datetime.fromtimestamp(ts).isoformat(timespec="seconds"), kind, details))


def count(table):
    with event_log._get_connection() as conn:
        return conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]


def test_xoa_toan_bo_lich_su_khong_con_trong_file():
    path = fresh()
    add_event(time.time(), details="BI-MAT-SU-CO-123")
    notifier.raise_alert("Ngã", "BI-MAT-CANH-BAO-456")
    counts = privacy.delete_all_history(who=("boss", auth.ROLE_ADMIN))
    assert counts["events"] == 1 and counts["alerts"] == 1
    for t in ("events", "status_log", "alerts", "deliveries"):
        assert count(t) == 0, t
    raw = open(path, "rb").read()
    assert b"BI-MAT-SU-CO-123" not in raw and b"BI-MAT-CANH-BAO-456" not in raw, "dữ liệu đã xoá còn nằm trong file"
    assert any(r["action"] == "xoa_3_toan_bo_lich_su" for r in auth.get_audit()), "phải có trong nhật ký truy cập"


def test_xoa_theo_khoang_ngay_chi_xoa_trong_khoang():
    fresh()
    now = time.time()
    add_event(now - 10 * 86400)
    add_event(now - 3 * 86400)
    add_event(now)
    today = date.today()
    assert privacy.count_range(today - timedelta(days=4), today - timedelta(days=2))["events"] == 1
    privacy.delete_range(today - timedelta(days=4), today - timedelta(days=2))
    assert count("events") == 2


def test_xoa_mot_canh_bao_dang_gui_thi_dung_gui():
    fresh()
    contacts.add_contact("Lan", "Con", "0912345678", "", 1)

    class Ch:
        name = "sms"
        sent = []

        def target_for(self, c):
            return c.get("phone")

        def send(self, target, alert, ack_url=None):
            self.sent.append(target)

    ch = Ch()
    d = notifier.Dispatcher([ch])
    aid = notifier.raise_alert("Ngã", "x")
    privacy.delete_alert(aid)
    d.tick()
    assert ch.sent == [] and count("deliveries") == 0


def test_xoa_toan_bo_du_lieu_ca_nhan_giu_quan_tri():
    fresh()
    auth.create_user("boss", "Boss", auth.ROLE_ADMIN, "Quan-tri-2026")
    auth.create_user("lan", "Lan", auth.ROLE_CAREGIVER, "Hoa-sen-2026")
    contacts.add_contact("Lan", "Con", "0912345678", "lan@example.com", 1)
    profile_store.save_profile({"name": "Ông Ba", "health_notes": "Tiểu đường"})
    privacy.give_consent(SUBJ)
    counts = privacy.delete_all_personal(who=("boss", auth.ROLE_ADMIN))
    assert counts["contacts"] == 1 and counts["users"] == 1 and counts["consents"] == 1 and counts["profile"] == 1
    assert [u["username"] for u in auth.list_users()] == ["boss"]
    assert privacy.active_consent() is None, "không còn sự đồng ý -> không giám sát được"
    assert not os.path.exists(profile_store.PROFILE_PATH)


def test_han_luu_tu_xoa_nhung_giu_canh_bao_dang_cho():
    fresh()
    now = time.time()
    add_event(now - 40 * 86400)
    add_event(now - 1 * 86400)
    old_open = notifier.raise_alert("Ngã", "đang chờ", now=now - 40 * 86400)
    old_acked = notifier.raise_alert("Ngã", "đã xong", now=now - 40 * 86400)
    with event_log._get_connection() as conn:
        conn.execute("UPDATE alerts SET status = 'acked' WHERE id = ?", (old_acked,))
    counts = privacy.prune(now=now, days=30)
    assert counts["events"] == 1 and counts["alerts"] == 1
    ids = [a["id"] for a in notifier.get_alerts()]
    assert old_open in ids and old_acked not in ids, "cảnh báo đang chờ xác nhận không được tự xoá"


def test_dong_y_ghi_thay_phai_co_ly_do_va_rut_lai_duoc():
    fresh()
    assert privacy.give_consent(CARE) is not None, "người chăm sóc không tự đồng ý thay được"
    assert privacy.give_consent(ADMIN, on_behalf=True, reason="ngắn") is not None
    assert privacy.give_consent(ADMIN, on_behalf=True, reason="Bố bị sa sút trí nhớ, tôi là người giám hộ") is None
    c = privacy.active_consent()
    assert c["on_behalf"] == 1 and "giám hộ" in c["reason"]
    assert privacy.withdraw_consent(SUBJ) is None
    assert privacy.active_consent() is None
    assert privacy.give_consent(SUBJ) is None and privacy.active_consent()["on_behalf"] == 0


def test_tam_dung_toi_da_60_phut():
    fresh()
    now = 1_000_000.0
    until = privacy.pause(500, "Ba", now=now)
    assert until == now + privacy.MAX_PAUSE_MINUTES * 60
    assert privacy.pause_until(now=now + 10) == until
    assert privacy.pause_until(now=until + 1) == 0.0, "hết giờ tự bật lại"


def test_ma_hoa_truong_nhay_cam_khi_luu():
    path = fresh()
    contacts.add_contact("Lan", "Con", "0912345678", "lan@example.com", 1, "123456789")
    profile_store.save_profile({"name": "Ông Ba", "health_notes": "Tieu-duong-type-2"})
    raw = open(path, "rb").read()
    assert b"0912345678" not in raw and b"lan@example.com" not in raw and b"123456789" not in raw
    assert b"Tieu-duong-type-2" not in open(profile_store.PROFILE_PATH, "rb").read()
    c = contacts.get_alert_recipients()[0]
    assert (c["phone"], c["email"], c["telegram_chat_id"]) == ("0912345678", "lan@example.com", "123456789")
    assert profile_store.load_profile()["health_notes"] == "Tieu-duong-type-2"


def test_dia_chi_gui_trong_bang_deliveries_cung_ma_hoa():
    path = fresh()
    contacts.add_contact("Lan", "Con", "0912345678", "", 1)

    class Ch:
        name = "sms"
        got = []

        def target_for(self, c):
            return c.get("phone")

        def send(self, target, alert, ack_url=None):
            self.got.append(target)

    ch = Ch()
    notifier.raise_alert("Ngã", "x")
    notifier.Dispatcher([ch]).tick()
    assert ch.got == ["0912345678"], "gửi phải dùng số đã giải mã"
    assert b"0912345678" not in open(path, "rb").read()


def test_link_xac_nhan_het_han_sau_24_gio():
    fresh()
    now = time.time()
    aid = notifier.raise_alert("Ngã", "x", now=now - notifier.LINK_TTL_SECONDS - 60)
    a = next(a for a in notifier.get_alerts() if a["id"] == aid)
    assert notifier.link_expired(a, now=now)
    assert not notifier.ack(a["ack_token"], via="web-link", now=now, max_age=notifier.LINK_TTL_SECONDS)
    fresh_id = notifier.raise_alert("Ngã", "y", now=now)
    b = next(a for a in notifier.get_alerts() if a["id"] == fresh_id)
    assert notifier.ack(b["ack_token"], via="web-link", now=now + 10, max_age=notifier.LINK_TTL_SECONDS)
    assert len(b["ack_token"]) >= 20, "mã trong link đủ dài để không đoán được"


def test_du_lieu_cu_chua_ma_hoa_duoc_ma_hoa_khi_khoi_dong():
    path = fresh()
    with event_log._get_connection() as conn:
        conn.execute("INSERT INTO contacts (name, phone, email, priority, notify_enabled) VALUES (?, ?, ?, 1, 1)",
                     ("Cũ", "0987654321", "cu@example.com"))
    import json
    with open(profile_store.PROFILE_PATH, "w", encoding="utf-8") as f:
        json.dump({"name": "Ông Ba", "health_notes": "Huyet-ap-cao"}, f)
    assert privacy.encrypt_existing() >= 2
    assert b"0987654321" not in open(path, "rb").read() and b"cu@example.com" not in open(path, "rb").read()
    assert b"Huyet-ap-cao" not in open(profile_store.PROFILE_PATH, "rb").read()
    assert contacts.get_alert_recipients()[0]["phone"] == "0987654321"
    assert profile_store.load_profile()["health_notes"] == "Huyet-ap-cao"


if __name__ == "__main__":
    tests = [(n, f) for n, f in sorted(globals().items()) if n.startswith("test_")]
    failed = 0
    for name, fn in tests:
        try:
            fn()
            print(f"PASS  {name}")
        except AssertionError as e:
            failed += 1
            print(f"FAIL  {name}: {e}")
        except Exception as e:  # noqa: BLE001
            failed += 1
            print(f"ERROR {name}: {type(e).__name__}: {e}")
    print(f"\n{len(tests) - failed}/{len(tests)} ca đạt")
    sys.exit(1 if failed else 0)

"""Kiểm thử chuỗi cảnh báo (yêu cầu cải tiến số 1) — offline, kênh giả, đồng hồ giả.

Chạy: python tests/test_notifier.py
"""

import os
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

import contacts  # noqa: E402
import event_log  # noqa: E402
import notifier  # noqa: E402


class Clock:
    def __init__(self):
        self.t = 1_000_000.0

    def __call__(self):
        return self.t


class FakeChannel:
    """Giả kênh Telegram: `down=True` mô phỏng mất mạng."""

    name = "telegram"

    def __init__(self):
        self.down = False
        self.sent = []  # (target, alert_kind)

    def target_for(self, contact):
        return contact.get("telegram_chat_id")

    def send(self, target, alert, ack_url=None):
        if self.down:
            raise OSError("Network is unreachable")
        self.sent.append((target, alert["kind"]))


def setup(n_contacts=2):
    fd, path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    event_log.DB_PATH = contacts.DB_PATH = path
    notifier.init_db()
    for i in range(n_contacts):
        contacts.add_contact(f"Người {i + 1}", "Người thân", "0900", "", i + 1, telegram_chat_id=str(100 + i))
    clock = Clock()
    channel = FakeChannel()
    return clock, channel, notifier.Dispatcher([channel], clock=clock, ack_timeout=60, max_rounds=3)


def run(dispatcher, clock, seconds, step=1.0):
    for _ in range(int(seconds / step)):
        clock.t += step
        dispatcher.tick()


def alert(alert_id):
    return next(a for a in notifier.get_alerts() if a["id"] == alert_id)


def test_binh_thuong_gui_va_xac_nhan():
    clock, ch, d = setup()
    aid = notifier.raise_alert("Ngã", detected_at=clock.t - 120, now=clock.t)
    run(d, clock, 2)
    assert ch.sent == [("100", "Ngã")], "chỉ người ưu tiên 1 nhận ở vòng đầu"
    assert notifier.ack(alert(aid)["ack_token"], by="A", via="telegram", now=clock.t + 5)
    run(d, clock, 200)
    assert len(ch.sent) == 1, "đã xác nhận thì không gửi thêm"
    row = notifier.latency_rows()[0]
    assert row["status"] == notifier.STATUS_ACKED
    assert abs(row["verify_s"] - 120) < 1e-6
    assert row["total_s"] > row["verify_s"]


def test_mat_mang_thi_thu_lai_va_gui_duoc_khi_co_mang():
    clock, ch, d = setup()
    ch.down = True
    aid = notifier.raise_alert("Ngã", now=clock.t)
    run(d, clock, 30)
    deliveries = notifier.get_deliveries(aid)
    assert deliveries[0]["status"] == "failed" and deliveries[0]["attempts"] >= 3
    assert "unreachable" in deliveries[0]["error"]
    ch.down = False
    run(d, clock, 30)
    deliveries = notifier.get_deliveries(aid)
    assert deliveries[0]["status"] == "sent"
    assert notifier.latency_rows()[0]["failed_attempts"] >= 3


def test_khong_ai_xac_nhan_thi_gui_lai_va_chuyen_tiep():
    clock, ch, d = setup(n_contacts=2)
    aid = notifier.raise_alert("Ngã", now=clock.t)
    run(d, clock, 30)
    assert ch.sent == [("100", "Ngã")]
    run(d, clock, 40)  # qua 60s -> vòng 2: gửi lại người 1 + chuyển tiếp người 2
    assert sorted(ch.sent) == [("100", "Ngã"), ("100", "Ngã"), ("101", "Ngã")]
    run(d, clock, 200)  # hết 3 vòng
    assert alert(aid)["status"] == notifier.STATUS_UNACKED


def test_xac_nhan_hai_lan_giu_moc_thoi_gian_dau():
    clock, ch, d = setup()
    aid = notifier.raise_alert("Ngã", now=clock.t)
    run(d, clock, 2)
    token = alert(aid)["ack_token"]
    assert notifier.ack(token, by="A", via="telegram", now=clock.t + 3)
    first = alert(aid)["acked_at"]
    assert not notifier.ack(token, by="B", via="web-link", now=clock.t + 50)
    assert alert(aid)["acked_at"] == first and alert(aid)["acked_by"] == "A"


def test_xac_nhan_khi_dang_mat_mang_thi_huy_lan_gui_con_treo():
    clock, ch, d = setup()
    ch.down = True
    aid = notifier.raise_alert("Ngã", now=clock.t)
    run(d, clock, 10)
    notifier.ack(alert(aid)["ack_token"], by="A", via="web-ui", now=clock.t)
    ch.down = False
    run(d, clock, 60)
    assert ch.sent == []
    assert all(x["status"] == "cancelled" for x in notifier.get_deliveries(aid))


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
    print(f"\n{len(tests) - failed}/{len(tests)} ca đạt")
    sys.exit(1 if failed else 0)

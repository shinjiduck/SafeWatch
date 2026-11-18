"""Kiểm thử trạng thái an toàn khi mất hình (yêu cầu cải tiến số 3).

Chạy: python tests/test_observation_safety.py   (hoặc pytest tests/)

Không cần webcam/model thật: MediaPipe được thay bằng detector giả (điều
khiển được có/không có người, có/không có tay), predict_fall/predict_hand
được thay bằng hàm trả nhãn theo kịch bản, đồng hồ là đồng hồ giả, DB ghi
ra file tạm — chỉ kiểm tra LOGIC trạng thái của DetectionVideoProcessor.
"""

import os
import sys
import tempfile
import types

import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
os.environ.setdefault("TF_CPP_MIN_LOG_LEVEL", "3")

import av  # noqa: E402

import detection_engine as engine  # noqa: E402
import event_log  # noqa: E402
import webrtc_processor  # noqa: E402

FPS = 30.0


class FakeClock:
    def __init__(self):
        self.t = 1_000_000.0

    def time(self):
        return self.t


class FakeLandmark:
    x = y = z = 0.5


class FakeDetector:
    """Trả về kết quả giống MediaPipe; self.visible điều khiển có thấy hay không."""

    def __init__(self, kind):
        self.kind = kind
        self.visible = True

    def process(self, _img):
        if self.kind == "pose":
            lm = types.SimpleNamespace(landmark=[FakeLandmark()] * 33) if self.visible else None
            return types.SimpleNamespace(pose_landmarks=lm)
        hands = [types.SimpleNamespace(landmark=[FakeLandmark()] * 21)] if self.visible else None
        return types.SimpleNamespace(multi_hand_landmarks=hands)


class Harness:
    def __init__(self, grace=5.0):
        self.clock = FakeClock()
        webrtc_processor.time = types.SimpleNamespace(time=self.clock.time)
        self.fall_result = "NotFall"
        self.hand_result = ("No SOS", 0.99)
        engine.predict_fall = lambda _m, window: (self._check_window(window), self.fall_result)[1]
        engine.predict_hand = lambda _m, _v, _t: self.hand_result
        self.pose = FakeDetector("pose")
        self.hands = FakeDetector("hands")
        self.hands.visible = False
        config = {
            "enable_fall": True,
            "enable_hand": True,
            "enable_signal": False,
            "fall_grace_seconds": grace,
            "hand_confidence_threshold": 0.8,
            "signal_confidence_threshold": 0.7,
            "mirror_camera": False,
            "alert_hold_seconds": 2.0,
            "show_overlay": False,
        }
        self.p = webrtc_processor.DetectionVideoProcessor(None, None, None, self.pose, self.hands, config)
        self.frame = av.VideoFrame.from_ndarray(np.zeros((48, 64, 3), dtype=np.uint8), format="bgr24")
        self.windows_seen = []

    def _check_window(self, window):
        self.windows_seen.append(len(window))

    def run(self, seconds):
        """Camera gửi frame đều 30fps trong `seconds` giây."""
        for _ in range(int(round(seconds * FPS))):
            self.clock.t += 1 / FPS
            self.p.recv(self.frame)
            self.p.tick()

    def stall(self, seconds, tick_every=0.3):
        """Camera ngừng gửi frame; chỉ thread giao diện gọi tick()."""
        for _ in range(int(round(seconds / tick_every))):
            self.clock.t += tick_every
            self.p.tick()

    @property
    def s(self):
        return self.p.get_state()


def statuses():
    return [row[1] for row in reversed(event_log.get_status_log(1000))]


def events():
    return [(row[1], row[2]) for row in reversed(event_log.get_events(1000))]


def fresh_db():
    fd, path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    event_log.DB_PATH = path
    event_log.init_db()


# ---------------------------------------------------------------- các ca thử


def test_mat_landmark_thi_xoa_cua_so_va_bao_khong_du_du_lieu():
    fresh_db()
    h = Harness()
    h.run(3)  # 40 frame khởi động + đủ cửa sổ
    assert h.s["fall_label"] == "NotFall"
    assert not h.s["observation_lost"]

    h.pose.visible = False
    h.run(1.0)  # < 1.5s: chưa báo mất, nhưng cửa sổ đã bị xoá
    assert len(h.p.fall_lm_window) == 0
    assert not h.s["observation_lost"]
    h.run(1.0)  # tổng 2s > 1.5s
    assert h.s["observation_lost"]
    assert h.s["fall_label"] == engine.NO_DATA_LABEL
    assert "Mất quan sát người" in statuses()


def test_khoi_phuc_quan_sat_can_cua_so_moi_day_du():
    fresh_db()
    h = Harness()
    h.run(3)
    h.pose.visible = False
    h.run(2)
    h.windows_seen.clear()
    h.pose.visible = True
    h.run(0.5)  # 15 frame = 5 frame xử lý < 10: chưa được predict
    assert h.s["fall_label"] == engine.NO_DATA_LABEL
    assert h.windows_seen == []
    assert "Quan sát đã khôi phục" in statuses()
    h.run(1.0)
    assert h.s["fall_label"] == "NotFall"
    assert h.windows_seen and all(n == engine.FALL_TIMESTEPS for n in h.windows_seen)


def test_khoang_trong_ngan_khong_noi_du_lieu_cu_voi_moi():
    fresh_db()
    h = Harness()
    h.run(3)
    h.pose.visible = False
    h.run(0.3)  # mất ngắn, chưa tới ngưỡng báo
    h.pose.visible = True
    h.windows_seen.clear()
    h.run(0.6)  # 6 frame xử lý mới — chưa đủ 10, không được predict
    assert h.windows_seen == [], "không được predict trên cửa sổ nối dữ liệu trước & sau khoảng trống"


def test_nga_roi_mat_hinh_khong_bi_coi_la_da_phuc_hoi_va_van_bao_dong():
    fresh_db()
    h = Harness(grace=5.0)
    h.run(3)
    h.fall_result = "Fall"
    h.run(1)
    assert h.s["fall_down_since"] is not None
    h.pose.visible = False
    h.run(2)
    assert h.s["observation_lost"]
    assert h.s["fall_down_since"] is not None, "mất hình không được huỷ theo dõi sau ngã"
    assert not any(t.startswith("Ngã - đã phục hồi") for t, _ in events())
    h.run(4)
    assert h.s["fall_escalated"] and h.s["sos_alert"]
    fall_events = [d for t, d in events() if t == "Ngã (không đứng lên lại)"]
    assert fall_events and "không còn thấy người" in fall_events[0]


def test_mat_camera_phat_hien_qua_tick_va_khoi_phuc():
    fresh_db()
    h = Harness()
    h.run(3)
    h.stall(2.0)
    assert not h.s["camera_lost"]
    h.stall(2.0)  # tổng 4s > 3s
    assert h.s["camera_lost"]
    assert h.s["fall_label"] == engine.NO_DATA_LABEL
    assert "Mất tín hiệu camera" in statuses()
    h.run(0.1)
    assert not h.s["camera_lost"]
    assert statuses()[-1] == "Camera đã khôi phục"


def test_mat_camera_trong_luc_theo_doi_sau_nga_van_bao_dong():
    fresh_db()
    h = Harness(grace=5.0)
    h.run(3)
    h.fall_result = "Fall"
    h.run(1)
    h.stall(8)  # camera chết, không còn frame nào tới
    assert h.s["fall_escalated"] and h.s["sos_alert"]
    fall_events = [d for t, d in events() if t == "Ngã (không đứng lên lại)"]
    assert fall_events and "camera mất tín hiệu" in fall_events[0]


def test_mat_camera_khong_giu_nhan_sos_tay_cu():
    fresh_db()
    h = Harness()
    h.hands.visible = True
    h.hand_result = ("Need Help", 0.95)
    h.run(3)
    assert h.s["sos_alert"]
    h.stall(6)  # camera chết: nhãn tay SOS cũ phải bị xoá, cảnh báo hết sau thời gian giữ
    assert h.s["hand_label"] == "No hands"
    assert not h.s["sos_alert"]


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

"""Kiểm thử phân tích video tải lên (video_demo.py, trang Thử bằng video).

Chạy: python tests/test_video_demo.py   (hoặc pytest tests/)

Không cần model / MediaPipe thật: dùng detector giả của test_observation_safety. Kiểm tra:
  - đồng hồ theo thời gian video: cảnh báo ngã đúng sau thời gian xác minh tính bằng giây VIDEO;
  - sự kiện / cảnh báo chỉ vào kết quả phân tích, KHÔNG vào nhật ký thật, KHÔNG gửi cho người liên hệ;
  - camera trực tiếp (không truyền sink) vẫn ghi nhật ký như cũ;
  - file không phải video -> probe trả None (trang báo "không đọc được").
"""

import os
import sys
import tempfile

import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
os.environ.setdefault("TF_CPP_MIN_LOG_LEVEL", "3")

import av  # noqa: E402

import detection_engine as engine  # noqa: E402
import event_log  # noqa: E402
import notifier  # noqa: E402
import video_demo  # noqa: E402
import webrtc_processor  # noqa: E402
from test_observation_safety import FakeDetector, events, fresh_db  # noqa: E402

CONFIG = {"enable_fall": True, "enable_hand": True, "enable_signal": False, "fall_grace_seconds": 5.0,
          "hand_confidence_threshold": 0.8, "signal_confidence_threshold": 0.7, "mirror_camera": False,
          "alert_hold_seconds": 2.0, "show_overlay": False}
FRAME = av.VideoFrame.from_ndarray(np.zeros((48, 64, 3), dtype=np.uint8), format="bgr24")


def _video_processor(fall_after):
    """Bộ xử lý như video_demo.analyze: đồng hồ video, sink riêng, 10 khung / giây, không làm nóng."""
    clock = video_demo._Clock()
    sink = video_demo._Sink(clock, clock.t)
    state = {"t": 0.0}
    engine.predict_fall = lambda _m, _w: "Fall" if state["t"] >= fall_after else "NotFall"
    engine.predict_hand = lambda _m, _v, _t: ("No SOS", 0.99)
    hands = FakeDetector("hands")
    hands.visible = False
    p = webrtc_processor.DetectionVideoProcessor(None, None, None, FakeDetector("pose"), hands, dict(CONFIG),
                                                 clock=clock, sink=sink)
    p.PROCESS_EVERY_N_FRAMES = 1
    p.frame_count = engine.WARMUP_FRAMES

    def play(seconds):
        base = clock.t - state["t"]
        for _ in range(int(round(seconds * video_demo.HZ))):
            state["t"] += 1 / video_demo.HZ
            clock.t = base + state["t"]
            p.recv(FRAME)

    return p, sink, play


def test_canh_bao_theo_gio_video_va_khong_ghi_nhat_ky_that():
    fresh_db()
    sent = []
    real = notifier.raise_alert
    notifier.raise_alert = lambda *a, **k: sent.append(a)
    try:
        p, sink, play = _video_processor(fall_after=2.0)
        play(12.0)  # ngã ở giây ~2, nằm yên tới giây 12 (> 5 s xác minh)
    finally:
        notifier.raise_alert = real
    assert len(sink.alerts) == 1, f"phải có đúng 1 cảnh báo, có {sink.alerts}"
    a = sink.alerts[0]
    assert 6.5 <= a["t"] <= 8.5, f"cảnh báo phải ở khoảng giây 7 của video (2 + 5 s xác minh + cửa sổ), là {a['t']}"
    assert a["phat_hien_t"] < a["t"], "mốc phát hiện phải trước mốc cảnh báo"
    assert sent == [], "phân tích video không được gửi cảnh báo thật"
    assert events() == [], f"phân tích video không được ghi vào nhật ký thật: {events()}"
    kinds = [e["ten"] for e in sink.items]
    assert kinds.count("Ngã (không đứng lên lại)") == 1, f"cảnh báo không được ghi 2 lần: {kinds}"


def test_khong_nga_thi_khong_canh_bao():
    fresh_db()
    _, sink, play = _video_processor(fall_after=1e9)
    play(10.0)
    assert sink.alerts == [] and events() == []


def test_camera_truc_tiep_van_ghi_nhat_ky():
    """Không truyền sink (camera trực tiếp) -> vẫn ghi nhật ký thật như trước."""
    fresh_db()
    p = webrtc_processor.DetectionVideoProcessor(None, None, None, FakeDetector("pose"), FakeDetector("hands"),
                                                 dict(CONFIG))
    p._log_event("Thử", "ghi thật")
    assert ("Thử", "ghi thật") in events()


def test_file_khong_phai_video():
    fd, path = tempfile.mkstemp(suffix=".mp4")
    with os.fdopen(fd, "wb") as f:
        f.write(b"day khong phai video")
    try:
        assert video_demo.probe(path) is None
    finally:
        os.remove(path)


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

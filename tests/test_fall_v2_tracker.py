"""Kiểm thử logic 3 bước của FallV2Tracker (model giả, khung xương tổng hợp).

Chạy: python tests/test_fall_v2_tracker.py
"""

import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
os.environ.setdefault("TF_CPP_MIN_LOG_LEVEL", "3")

import detection_engine as engine  # noqa: E402


def body(upright):
    pts = [[0.5, 0.6, 0.0, 1.0] for _ in range(33)]
    if upright:
        spec = {0: (0.5, 0.3), 11: (0.45, 0.4), 12: (0.55, 0.4), 23: (0.47, 0.6), 24: (0.53, 0.6),
                27: (0.47, 0.9), 28: (0.53, 0.9)}
    else:
        spec = {0: (0.2, 0.8), 11: (0.3, 0.78), 12: (0.3, 0.82), 23: (0.5, 0.78), 24: (0.5, 0.82),
                27: (0.8, 0.78), 28: (0.8, 0.82)}
    for i, (x, y) in spec.items():
        pts[i] = [x, y, 0.0, 1.0]
    for i in range(33):
        if i not in spec:
            pts[i] = [0.5, pts[23][1], 0.0, 1.0] if upright else [0.5, 0.8, 0.0, 1.0]
    return pts


class FakeModel:
    window = 15
    threshold = 0.5

    def __init__(self):
        self.p = 0.0

    def prob(self, _window):
        return self.p


def feed(tracker, upright, steps, t0, dt=0.1):
    labels = []
    for i in range(steps):
        labels.append(tracker.update(body(upright), t0 + i * dt))
    return labels, t0 + steps * dt


def test_can_du_cua_so_moi_du_doan():
    m = FakeModel()
    tr = engine.FallV2Tracker(m)
    labels, _ = feed(tr, True, 14, 0)
    assert all(lbl is None for lbl in labels)
    labels, _ = feed(tr, True, 1, 1.4)
    assert labels == ["NotFall"]


def test_mot_lan_vuot_nguong_chua_du_hai_lan_lien_tiep_moi_bao():
    m = FakeModel()
    tr = engine.FallV2Tracker(m)
    _, t = feed(tr, True, 15, 0)
    m.p = 0.9
    labels, t = feed(tr, True, 1, t)
    assert labels == ["NotFall"]
    labels, t = feed(tr, False, 1, t)
    assert labels == ["Fall"]


def test_nam_yen_sau_nga_van_la_nga_dung_day_du_2s_moi_huy():
    m = FakeModel()
    tr = engine.FallV2Tracker(m)
    _, t = feed(tr, True, 15, 0)
    m.p = 0.9
    _, t = feed(tr, False, 2, t)
    m.p = 0.0
    labels, t = feed(tr, False, 50, t)  # nằm 5 s
    assert set(labels) == {"Fall"}
    labels, t = feed(tr, True, 15, t)  # đứng 1.5 s: chưa đủ
    assert set(labels) == {"Fall"}
    labels, t = feed(tr, True, 10, t)
    assert labels[-1] == "NotFall"


def test_mat_hinh_khong_xoa_trang_thai_da_nga():
    m = FakeModel()
    tr = engine.FallV2Tracker(m)
    _, t = feed(tr, True, 15, 0)
    m.p = 0.9
    _, t = feed(tr, False, 2, t)
    m.p = 0.0
    tr.clear_window()  # processor gọi khi mất người / mất camera
    labels, t = feed(tr, False, 3, t + 10)
    assert set(labels) == {"Fall"}, "quay lại vẫn nằm thì vẫn đang theo dõi sau ngã"


def test_dung_day_xen_ke_nam_khong_duoc_tinh_la_hoi_phuc():
    m = FakeModel()
    tr = engine.FallV2Tracker(m)
    _, t = feed(tr, True, 15, 0)
    m.p = 0.9
    _, t = feed(tr, False, 2, t)
    m.p = 0.0
    for _ in range(5):
        labels, t = feed(tr, True, 15, t)  # đứng 1.5 s
        assert labels[-1] == "Fall"
        _, t = feed(tr, False, 2, t)  # lại nằm -> đếm lại từ đầu


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

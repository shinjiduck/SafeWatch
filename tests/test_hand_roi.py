"""Kiểm thử nhận cử chỉ khi đứng xa (hand_roi.py) và việc không nhắc "lùi ra xa" lúc đang giơ tay.

Chạy: python tests/test_hand_roi.py   (hoặc pytest tests/)
"""

import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import hand_roi  # noqa: E402
from test_observation_safety import Harness, fresh_db  # noqa: E402


def body(cx=0.5, top=0.3, shoulder_w=0.15, wrist_y=None, vis=0.99):
    """Người đứng; wrist_y = độ cao cổ tay phải (None = buông xuôi ngang hông)."""
    lm = [[cx, top - 0.08, 0.0, vis] for _ in range(33)]
    half = shoulder_w / 2
    lm[11], lm[12] = [cx + half, top, 0, vis], [cx - half, top, 0, vis]
    lm[23], lm[24] = [cx + half * 0.7, top + 0.25, 0, vis], [cx - half * 0.7, top + 0.25, 0, vis]
    wy = top + 0.25 if wrist_y is None else wrist_y
    for side, x in ((0, cx + half + 0.02), (1, cx - half - 0.02)):
        w, p, i, t = hand_roi.HAND_POINTS[side]
        y = wy if side == 1 else top + 0.25
        lm[w] = [x, y, 0, vis]
        lm[p], lm[i], lm[t] = [x, y - 0.02, 0, vis], [x + 0.01, y - 0.03, 0, vis], [x - 0.01, y - 0.02, 0, vis]
    for k in range(25, 33):
        lm[k] = [cx, min(top + 0.6, 0.98), 0, vis]
    return lm


def test_doi_toa_do_o_cat_ve_khung_goc():
    pts = hand_roi.to_frame_coords([(0.0, 0.0, 0.1), (1.0, 1.0, 0.0), (0.5, 0.25, -0.2)], (100, 50, 200), 640, 480)
    assert pts[0][:2] == (100 / 640, 50 / 480)
    assert pts[1][:2] == (300 / 640, 250 / 480)
    assert abs(pts[2][0] - 200 / 640) < 1e-9 and abs(pts[2][1] - 100 / 480) < 1e-9
    assert abs(pts[0][2] - 0.1 * 200 / 640) < 1e-9


def test_o_cat_nam_trong_khung_va_tay_gio_cao_xep_truoc():
    lm = body(wrist_y=0.2)  # tay phải giơ cao hơn vai
    rois = hand_roi.candidate_rois(lm, 640, 480)
    assert len(rois) == 2
    for x0, y0, side in rois:
        assert x0 >= 0 and y0 >= 0 and x0 + side <= 640 and y0 + side <= 480 and side >= hand_roi.MIN_SIDE_PX
    assert rois[0][1] < rois[1][1]  # ô của tay giơ cao (y nhỏ hơn) đứng trước


def test_co_tay_ngoai_khung_thi_khong_cat():
    lm = body()
    for w, *_ in hand_roi.HAND_POINTS:
        lm[w] = [lm[w][0], 1.3, 0, 0.99]
    assert hand_roi.candidate_rois(lm, 640, 480) == []


def test_gio_tay_cao_hon_vai():
    assert hand_roi.hand_raised(body(wrist_y=0.15))
    assert not hand_roi.hand_raised(body())


def test_ket_qua_gia_dung_duoc_nhu_mediapipe():
    import detection_engine as engine

    r = hand_roi.as_results([(0.1 * i, 0.2, 0.0) for i in range(21)])
    vec = engine.hand_landmarks_to_vector(r)
    assert len(vec) == 63 and abs(vec[3] - 0.1) < 1e-6


class _ScriptedPose:
    def __init__(self, lm):
        self.lm = lm

    def process(self, _img):
        import types

        pts = [types.SimpleNamespace(x=p[0], y=p[1], z=p[2], visibility=p[3]) for p in self.lm]
        return types.SimpleNamespace(pose_landmarks=types.SimpleNamespace(landmark=pts))


def test_dung_gan_nhung_dang_gio_tay_thi_khong_nhac_lui_ra():
    fresh_db()
    h = Harness()
    h.pose = h.p.pose_detector = _ScriptedPose(body(shoulder_w=0.5, wrist_y=0.15))  # quá gần + giơ tay
    h.run(6)
    assert h.s["framing_status"] == "too_close" and h.s["voice_seq"] == 0
    h.pose.lm = body(shoulder_w=0.5)  # hạ tay xuống -> giờ mới nhắc
    h.run(4)
    assert h.s["voice_cue"] == "too_close" and h.s["voice_seq"] >= 1


class _HandsAt:
    """Detector tay giả: 21 điểm, cổ tay ở độ cao y."""

    def __init__(self, y):
        self.y = y

    def process(self, _img):
        import types

        pts = [types.SimpleNamespace(x=0.5, y=self.y, z=0.0) for _ in range(21)]
        return types.SimpleNamespace(multi_hand_landmarks=[types.SimpleNamespace(landmark=pts)])


def _sos_harness(hand_y, sos_filter=True, above_shoulder=False):
    fresh_db()
    h = Harness()
    h.p.config["sos_filter"] = sos_filter
    h.p.config["sos_above_shoulder"] = above_shoulder
    h.hand_result = ("Need Help", 0.99)
    h.pose = h.p.pose_detector = _ScriptedPose(body())  # vai ở y = 0.3
    h.hands = h.p.hand_detector = _HandsAt(hand_y)
    return h


def test_loc_sos_tay_thap_khong_bao_khi_bat_dieu_kien_cao_hon_vai():
    h = _sos_harness(hand_y=0.6, above_shoulder=True)
    h.run(5)
    assert not h.s["sos_alert"] and h.s["hand_label"] == "Uncertain"


def test_loc_sos_mac_dinh_khong_can_gio_cao_chi_can_giu_2_giay():
    """Mặc định: tay thấp (VD người đã ngã nằm dưới sàn) vẫn ra hiệu được, chỉ cần giữ cử chỉ đủ 2 s."""
    h = _sos_harness(hand_y=0.6)
    h.run(1.4 + 1.5)
    assert h.s["hand_label"] == "Need Help" and not h.s["sos_alert"], "chưa đủ 2 s thì chưa báo"
    h.run(1.0)
    assert h.s["sos_alert"]


def test_loc_sos_gio_tay_phai_giu_du_2_giay():
    h = _sos_harness(hand_y=0.15)
    h.run(1.4 + 1.5)  # 40 frame khởi động (~1.3 s) + chưa đủ 2 s giữ cử chỉ
    assert h.s["hand_label"] == "Need Help" and not h.s["sos_alert"]
    assert h.s["hand_sos_hold"] is not None and h.s["hand_sos_hold"] > 0
    h.run(1.0)
    assert h.s["sos_alert"]


def test_tat_loc_thi_giu_hanh_vi_cu():
    h = _sos_harness(hand_y=0.6, sos_filter=False)
    h.run(2.0)
    assert h.s["sos_alert"]


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

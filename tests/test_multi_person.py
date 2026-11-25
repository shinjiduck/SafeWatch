"""Kiểm thử chế độ theo dõi nhiều người (multi_person.py + nhánh nhiều người trong webrtc_processor).

Chạy: python tests/test_multi_person.py   (hoặc pytest tests/)

Model ngã giả: báo "ngã" khi thân người nằm ngang (góc thân > 1 rad) — chỉ để kích hoạt, logic cần kiểm là
việc gán đúng người, không để người khác đứng làm huỷ cú ngã, và các luật xác minh như bản 1 người.
"""

import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import detection_engine as engine  # noqa: E402
import multi_person  # noqa: E402
from test_observation_safety import Harness, events, fresh_db, lying, standing  # noqa: E402


class ScriptedPeople:
    def __init__(self):
        self.poses = []

    def detect(self, _rgb, _now):
        return self.poses


def multi_harness(grace=5.0):
    h = Harness(grace=grace)
    model = engine.FallV2Model.__new__(engine.FallV2Model)
    model.window, model.threshold, model.consecutive = 15, 0.9, 2
    model.prob = lambda feats: 1.0 if feats[-1][66] > 1.0 else 0.0
    h.p.fall_tracker = engine.FallV2Tracker(model)
    h.p.multi = ScriptedPeople()
    h.p.people = multi_person.PeopleTracker(lambda: engine.FallV2Tracker(model))
    return h


def test_gan_ma_on_dinh_va_loc_trung():
    t = multi_person.PeopleTracker(lambda: None)
    a, b = standing(cx=0.25), standing(cx=0.75)
    first = {p.id: p.center[0] for p in t.update([a, b], 0.0)}
    for k in range(1, 20):  # 2 người đi chậm về phía nhau, mã không đổi
        t.update([standing(cx=0.25 + 0.005 * k), standing(cx=0.75 - 0.005 * k)], k * 0.1)
    assert sorted(t.people) == sorted(first)
    left = min(t.people.values(), key=lambda p: p.center[0])
    assert first[left.id] < 0.5
    dup = [[x + 0.01, y, z, v] for x, y, z, v in a]
    assert len(multi_person.remove_duplicates([a, dup, b])) == 2


def test_mot_nguoi_nga_nguoi_kia_dung_van_bao_dong():
    fresh_db()
    h = multi_harness(grace=5.0)
    h.p.multi.poses = [standing(cx=0.25), standing(cx=0.75)]
    h.run(3)
    assert h.s["people_count"] == 2 and h.s["fall_down_since"] is None
    h.p.multi.poses = [lying(cx=0.3), standing(cx=0.75)]  # người bên trái ngã, người bên phải vẫn đứng
    h.run(2)
    assert h.s["fall_down_since"] is not None
    assert [x < 0.5 for _pid, x in h.s["people_down"]] == [True]
    h.run(5)
    assert h.s["fall_escalated"] and h.s["sos_alert"]
    assert "1 người khác" in dict(events())["Ngã (không đứng lên lại)"]


def test_nguoi_nga_dung_day_thi_huy():
    fresh_db()
    h = multi_harness(grace=30.0)
    h.p.multi.poses = [standing(cx=0.25), standing(cx=0.75)]
    h.run(3)
    h.p.multi.poses = [lying(cx=0.3), standing(cx=0.75)]
    h.run(2)
    assert h.s["fall_down_since"] is not None
    for i in range(1, 16):  # đứng dậy từ từ trong 1.5 s
        k = i / 15
        up = [[a * (1 - k) + b * k for a, b in zip(p, q)] for p, q in zip(lying(cx=0.3), standing(cx=0.3))]
        h.p.multi.poses = [up, standing(cx=0.75)]
        h.run(0.1)
    h.run(3)
    assert h.s["fall_down_since"] is None and not h.s["sos_alert"]
    assert "Ngã - đã phục hồi" in [k for k, _ in events()]


def test_nguoi_khac_roi_khung_khong_lam_huy_nguoi_dang_nga():
    fresh_db()
    h = multi_harness(grace=5.0)
    h.p.multi.poses = [standing(cx=0.25), standing(cx=0.75)]
    h.run(3)
    h.p.multi.poses = [lying(cx=0.3), standing(cx=0.75)]
    h.run(2)
    h.p.multi.poses = [lying(cx=0.3)]  # người kia đi ra ngoài
    h.run(5)
    assert h.s["fall_escalated"]


def test_nga_khuat_sau_vat_can_trong_che_do_nhieu_nguoi():
    fresh_db()
    h = multi_harness(grace=5.0)
    h.p.multi.poses = [standing(cx=0.3), standing(cx=0.75)]
    h.run(3)
    for i in range(1, 6):
        h.p.multi.poses = [standing(top=0.3 + 0.03 * i, cx=0.3), standing(cx=0.75)]
        h.run(0.1)
    h.p.multi.poses = [standing(cx=0.75)]  # người bên trái khuất sau vật cản
    h.run(2)
    assert h.s["fall_down_since"] is not None and h.s["vanish_suspected"]
    h.run(4)
    assert h.s["fall_escalated"]


def test_khong_ai_thi_khong_co_nguoi():
    fresh_db()
    h = multi_harness()
    h.p.multi.poses = [standing(cx=0.5)]
    h.run(3)
    h.p.multi.poses = []
    h.run(2)
    assert h.s["observation_lost"] and h.s["fall_label"] == engine.NO_DATA_LABEL and h.s["people_count"] == 0


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

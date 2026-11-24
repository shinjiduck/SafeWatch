"""Kiểm thử nhắc đứng đúng chỗ (framing.py): quá gần, bị khuất, rời khung hình, giọng nói.

Chạy: python tests/test_framing.py   (hoặc pytest tests/)
"""

import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

import framing  # noqa: E402
from framing import GONE, OK, PARTIAL, TOO_CLOSE  # noqa: E402


def body(cx=0.5, shoulder_w=0.15, torso_h=0.25, top=0.3, hide=(), vis=0.99):
    """33 điểm của 1 người đứng thẳng, giữa vai ở (cx, top)."""
    lm = [[cx, top - 0.08, 0.0, vis] for _ in range(33)]  # mặt
    half = shoulder_w / 2
    lm[7], lm[8] = [cx + half * 0.4, top - 0.08, 0, vis], [cx - half * 0.4, top - 0.08, 0, vis]
    lm[11], lm[12] = [cx + half, top, 0, vis], [cx - half, top, 0, vis]
    lm[23], lm[24] = [cx + half * 0.7, top + torso_h, 0, vis], [cx - half * 0.7, top + torso_h, 0, vis]
    for i in range(25, 33):
        lm[i] = [cx, min(top + torso_h * 2.6, 0.98), 0, vis]
    for i in hide:
        lm[i] = [lm[i][0], lm[i][1], 0, 0.05]
    return lm


def test_dung_xa_la_ok():
    assert framing.assess(body()) == OK


def test_vai_qua_rong_la_qua_gan():
    assert framing.assess(body(shoulder_w=0.5, torso_h=0.4)) == TOO_CLOSE


def test_ngoi_sat_laptop_khong_thay_hong_la_qua_gan():
    lm = body(shoulder_w=0.3, top=0.7, torso_h=0.5)  # hông rơi ra ngoài đáy khung hình (y > 1)
    assert framing.assess(lm) == TOO_CLOSE


def test_than_qua_dai_la_qua_gan():
    assert framing.assess(body(shoulder_w=0.3, torso_h=0.6, top=0.2)) == TOO_CLOSE


def test_bi_che_mot_ben_hong_la_mot_phan():
    assert framing.assess(body(hide=(23,))) == PARTIAL


def test_sat_mep_vai_ra_ngoai_la_mot_phan():
    assert framing.assess(body(cx=0.97, shoulder_w=0.15)) == PARTIAL


def test_huong_roi_khung():
    assert framing.exit_side(body(cx=0.05)) == "left"
    assert framing.exit_side(body(cx=0.93)) == "right"
    assert framing.exit_side(body(cx=0.5)) is None


def test_phai_keo_dai_moi_bao_va_tat():
    m = framing.FramingMonitor(hold_s=2.0, clear_s=1.0)
    assert m.observe(TOO_CLOSE, 0.0) == OK
    assert m.observe(TOO_CLOSE, 1.9) == OK
    assert m.observe(TOO_CLOSE, 2.0) == TOO_CLOSE
    assert m.observe(OK, 2.5) == TOO_CLOSE  # mới đứng đúng 0.5 s
    assert m.observe(OK, 3.5) == OK


def test_nhap_nhay_khong_bao():
    m = framing.FramingMonitor(hold_s=2.0)
    t = 0.0
    for _ in range(20):  # quá gần 1 s rồi ổn 1 s, lặp lại
        m.observe(TOO_CLOSE, t)
        m.observe(OK, t + 1.0)
        t += 2.0
    assert m.status == OK and m.cue_seq == 0


def test_giong_noi_lap_lai_cach_quang():
    m = framing.FramingMonitor(hold_s=2.0, repeat_s=20.0)
    t = 0.0
    while t <= 45.0:
        m.observe(TOO_CLOSE, t)
        t += 0.1
    # phát lúc 2 s, 22 s, 42 s
    assert m.cue == TOO_CLOSE and m.cue_seq == 3


def test_im_lang_khi_dang_theo_doi_sau_nga():
    m = framing.FramingMonitor(hold_s=2.0)
    for i in range(50):
        m.observe(PARTIAL, i * 0.1, quiet=True)
    m.person_lost(6.0, quiet=True)
    assert m.cue_seq == 0


def test_roi_khung_nhac_mot_lan():
    m = framing.FramingMonitor(repeat_s=20.0)
    m.person_lost(0.0)
    m.person_lost(5.0)  # vào rồi ra lại ngay -> không nói lại
    assert m.cue == GONE and m.cue_seq == 1
    m.person_lost(25.0)
    assert m.cue_seq == 2


def test_file_giong_noi_co_du():
    for name in framing.VOICE_FILES.values():
        path = os.path.join(ROOT, "assets", "voice", name)
        assert os.path.getsize(path) > 1000, path


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

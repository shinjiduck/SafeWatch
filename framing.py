"""Người dùng đứng có hợp với camera không: quá gần, bị khuất / ra rìa, hay đã rời khung hình.

Mục đích: khung xương thiếu (đứng sát webcam, bị vật che, đi ra rìa) là lúc phát hiện ngã
kém nhất (xem training/fall_eval: thử che 1 góc, cảnh sát camera báo nhầm nhiều). Thay vì
lặng lẽ đoán, hệ thống NÓI cho người dùng biết để họ đứng lại cho đúng.

- assess(lm): đánh giá 1 frame từ 33 landmark MediaPipe (x, y theo tỉ lệ khung hình, visibility).
- FramingMonitor: chỉ đổi trạng thái khi tình trạng kéo dài đủ lâu (tránh nhấp nháy), và hẹn
  lời nhắc bằng giọng nói (mỗi loại tối đa 1 lần / VOICE_REPEAT_SECONDS).

Không phụ thuộc Streamlit / thời gian thật -> kiểm thử offline (tests/test_framing.py).
"""

OK = "ok"
TOO_CLOSE = "too_close"
PARTIAL = "partial"
GONE = "gone"

VISIBLE = 0.5  # visibility tối thiểu để coi 1 điểm là "thấy được"
EDGE = 0.02  # cho phép điểm lệch ra ngoài khung 1 chút
# Ngưỡng "quá gần" (tỉ lệ chiều rộng/cao khung hình). Webcam ~60°: đứng cách 1 m thì vai
# rộng ~0.35 khung; ngồi sát laptop ~0.55. Đứng 2-3 m (vị trí khuyên dùng) chỉ ~0.12-0.18.
TOO_CLOSE_SHOULDER_W = 0.40
TOO_CLOSE_TORSO_H = 0.55  # vai -> hông theo chiều dọc
NO_HIPS_SHOULDER_W = 0.25  # không thấy hông (thường là ngồi / đứng sát) mà vai đã rộng thế này
NO_HIPS_EAR_W = 0.12
EDGE_ZONE = 0.15  # người biến mất khi đang ở trong 15% sát mép trái/phải -> coi là đi ra khỏi khung

HOLD_SECONDS = 2.0  # tình trạng phải kéo dài bấy nhiêu mới báo
CLEAR_SECONDS = 1.0  # đứng đúng lại bấy nhiêu mới tắt báo
VOICE_REPEAT_SECONDS = 20.0

SHOULDERS, HIPS, EARS = (11, 12), (23, 24), (7, 8)
TORSO = SHOULDERS + HIPS

VOICE_FILES = {TOO_CLOSE: "too_close.mp3", PARTIAL: "partial.mp3", GONE: "gone.mp3"}
VOICE_TEXT = {
    TOO_CLOSE: "Xin mời quý vị rời xa camera một chút.",
    PARTIAL: "Xin mời quý vị di chuyển vào giữa khung hình.",
    GONE: "Hệ thống không còn thấy quý vị trong khung hình.",
}


def _seen(p):
    vis = p[3] if len(p) > 3 else 1.0
    return vis >= VISIBLE and -EDGE <= p[0] <= 1 + EDGE and -EDGE <= p[1] <= 1 + EDGE


def _mid(a, b):
    return (a[0] + b[0]) / 2, (a[1] + b[1]) / 2


def assess(lm):
    """lm: 33 điểm [x, y, z, visibility]. Trả về TOO_CLOSE, PARTIAL hoặc OK."""
    shoulders_seen = all(_seen(lm[i]) for i in SHOULDERS)
    hips_seen = any(_seen(lm[i]) for i in HIPS)
    shoulder_w = abs(lm[11][0] - lm[12][0]) if shoulders_seen else 0.0
    ear_w = abs(lm[7][0] - lm[8][0]) if all(_seen(lm[i]) for i in EARS) else 0.0
    torso_h = 0.0
    if shoulders_seen and all(_seen(lm[i]) for i in HIPS):
        torso_h = abs(_mid(lm[23], lm[24])[1] - _mid(lm[11], lm[12])[1])

    if shoulder_w > TOO_CLOSE_SHOULDER_W or torso_h > TOO_CLOSE_TORSO_H:
        return TOO_CLOSE
    if not hips_seen and (shoulder_w > NO_HIPS_SHOULDER_W or ear_w > NO_HIPS_EAR_W):
        return TOO_CLOSE
    if not all(_seen(lm[i]) for i in TORSO):
        return PARTIAL
    return OK


def exit_side(lm):
    """Lần cuối thấy người ở đâu: 'left' / 'right' (sát mép -> đã đi ra khỏi khung), None nếu ở giữa."""
    xs = [lm[i][0] for i in TORSO if len(lm[i]) < 4 or lm[i][3] >= VISIBLE]
    if not xs:
        return None
    x = sum(xs) / len(xs)
    if x < EDGE_ZONE:
        return "left"
    if x > 1 - EDGE_ZONE:
        return "right"
    return None


class FramingMonitor:
    def __init__(self, hold_s=HOLD_SECONDS, clear_s=CLEAR_SECONDS, repeat_s=VOICE_REPEAT_SECONDS):
        self.hold_s, self.clear_s, self.repeat_s = hold_s, clear_s, repeat_s
        self.status = OK
        self._candidate, self._since = OK, None
        self._last_voice = {}
        self.cue, self.cue_seq = None, 0  # lời nhắc mới nhất; cue_seq tăng mỗi lần cần phát

    def observe(self, frame_status, now, quiet=False):
        """Gọi mỗi frame thấy người. quiet=True (VD đang theo dõi sau ngã) -> không hẹn giọng nói."""
        if frame_status != self._candidate:
            self._candidate, self._since = frame_status, now
        need = self.clear_s if frame_status == OK else self.hold_s
        if frame_status != self.status and now - self._since >= need:
            self.status = frame_status
        if self.status != OK:
            self._cue(self.status, now, quiet)
        return self.status

    def person_lost(self, now, quiet=False):
        """Gọi 1 lần khi chuyển sang 'không thấy người'."""
        self.status, self._candidate, self._since = OK, OK, None
        self._cue(GONE, now, quiet)

    def _cue(self, name, now, quiet):
        if quiet:
            return
        last = self._last_voice.get(name)
        if last is None or now - last >= self.repeat_s:
            self._last_voice[name] = now
            self.cue = name
            self.cue_seq += 1

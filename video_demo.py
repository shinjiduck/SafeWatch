"""Phân tích 1 video tải lên bằng ĐÚNG bộ nhận diện của camera trực tiếp (DetectionVideoProcessor + MediaPipe + model
thật, cùng cấu hình) — dùng khi không demo trực tiếp được (phòng thi chật, không có chỗ để ngã).

Khác camera trực tiếp ở 3 điểm, đều để kết quả giống hệt như khi người đó đứng trước camera:
  - Đồng hồ chạy theo thời gian trong video (không theo đồng hồ máy), AI xử lý 10 khung mỗi giây video — đúng nhịp
    model được huấn luyện và nhịp của camera trực tiếp.
  - Sự kiện / cảnh báo ghi vào kết quả phân tích, KHÔNG vào nhật ký thật và KHÔNG gửi cho người liên hệ (trang có tuỳ
    chọn gửi thử, đánh dấu "giả lập").
  - Bỏ giai đoạn làm nóng 40 khung đầu (camera cần, video thì không) để không lỡ cú ngã ở đầu video.

Video chỉ nằm trong file tạm trong lúc xử lý; trang xoá file ngay sau đó.
"""

import os
import tempfile
import time

import av
import cv2
import numpy as np

import detection_engine as engine
from webrtc_processor import DetectionVideoProcessor

HZ = 10  # khung AI mỗi giây video (như camera trực tiếp)
MAX_SECONDS = 180  # video dài hơn thì từ chối (máy chủ dùng chung, xử lý ~3 giây cho mỗi 10 giây video)
MAX_WIDTH = 640  # như camera trực tiếp
MAX_SNAPSHOTS = 6

FONT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "static", "fonts")

# Trạng thái trên dải thời gian: (mã, chữ trên video, màu nền BGR)
OK, WATCH, HOLD, ALERT, LOST = "ok", "watch", "hold", "alert", "lost"
STATUS_TEXT = {
    OK: "Bình thường",
    WATCH: "Nghi ngã — đang xác minh",
    HOLD: "Đang giữ cử chỉ SOS",
    ALERT: "CẢNH BÁO",
    LOST: "Không thấy người",
}
# Cùng màu trạng thái với giao diện (theme.COLOR_SAFE / MONITORING / ACCENT / EMERGENCY / NODATA)
STATUS_HEX = {OK: "#15803D", WATCH: "#B45309", HOLD: "#0262C9", ALERT: "#DC2626", LOST: "#52525B"}
STATUS_BGR = {k: (int(v[5:7], 16), int(v[3:5], 16), int(v[1:3], 16)) for k, v in STATUS_HEX.items()}


class _Clock:
    def __init__(self):
        self.t = time.time()

    def __call__(self):
        return self.t


class _Sink:
    """Nhận sự kiện / cảnh báo của bộ xử lý thay cho nhật ký thật và bộ gửi tin."""

    def __init__(self, clock, base):
        self.clock, self.base = clock, base
        self.items = []  # dict(t, loai, ten, chi_tiet)
        self.alerts = []  # dict(t, ten, chi_tiet, phat_hien_t)

    def _t(self, now=None):
        return round((self.clock() if now is None else now) - self.base, 2)

    def log_event(self, kind, details=""):
        if kind.startswith("Ngã (không") or kind in engine.SOS_HAND_LABELS or kind.startswith("Signal"):
            return  # cảnh báo đã có trong raise_alert bên dưới, không ghi 2 lần
        self.items.append({"t": self._t(), "loai": "su_kien", "ten": kind, "chi_tiet": details})

    def log_status(self, state, details=""):
        self.items.append({"t": self._t(), "loai": "trang_thai", "ten": state, "chi_tiet": details})

    def raise_alert(self, kind, details="", detected_at=None, now=None, **_):
        t = self._t(now)
        a = {"t": t, "ten": kind, "chi_tiet": details,
             "phat_hien_t": self._t(detected_at) if detected_at is not None else t}
        self.alerts.append(a)
        self.items.append({"t": t, "loai": "canh_bao", "ten": kind, "chi_tiet": details})


def probe(path):
    """(số giây, khung/giây, rộng, cao) của video; đọc không được thì None."""
    cap = cv2.VideoCapture(path)
    try:
        if not cap.isOpened():
            return None
        fps = cap.get(cv2.CAP_PROP_FPS) or 0
        n = cap.get(cv2.CAP_PROP_FRAME_COUNT) or 0
        w, h = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH)), int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        if fps <= 1 or w <= 0:
            return None
        return (n / fps if n > 0 else 0.0), fps, w, h
    finally:
        cap.release()


def _sampled(path):
    """(giây, khung) lấy đều 10 khung mỗi giây video."""
    cap = cv2.VideoCapture(path)
    fps = cap.get(cv2.CAP_PROP_FPS) or 30.0
    fps = fps if fps > 1 else 30.0
    i = k = 0
    try:
        while True:
            ok, frame = cap.read()
            if not ok:
                break
            t = i / fps
            if t + 1e-6 >= k / HZ:
                yield t, frame
                while k / HZ <= t + 1e-6:
                    k += 1
            i += 1
    finally:
        cap.release()


def _fit(img):
    h, w = img.shape[:2]
    scale = min(1.0, MAX_WIDTH / w)
    nw, nh = int(w * scale) // 2 * 2, int(h * scale) // 2 * 2  # H.264 cần cạnh chẵn
    return cv2.resize(img, (nw, nh)) if (nw, nh) != (w, h) else img


def _font(size, bold=False):
    try:
        from PIL import ImageFont

        name = "BeVietnamPro-SemiBold.ttf" if bold else "BeVietnamPro-Medium.ttf"
        return ImageFont.truetype(os.path.join(FONT_DIR, name), size)
    except Exception:  # noqa: BLE001
        return None


class _Banner:
    """Thanh trạng thái tiếng Việt trên đầu mỗi khung (OpenCV không vẽ được dấu tiếng Việt -> dùng Pillow)."""

    def __init__(self):
        self.big, self.small = _font(17, bold=True), _font(13)

    def draw(self, img, status, text, clock_text):
        h, w = img.shape[:2]
        bar = 34
        cv2.rectangle(img, (0, 0), (w, bar), STATUS_BGR[status], -1)
        if self.big is None:
            cv2.putText(img, clock_text, (8, 23), cv2.FONT_HERSHEY_SIMPLEX, 0.55, (255, 255, 255), 1)
            return img
        from PIL import Image, ImageDraw

        top = Image.fromarray(cv2.cvtColor(img[:bar], cv2.COLOR_BGR2RGB))
        d = ImageDraw.Draw(top)
        d.text((10, 7), text, font=self.big, fill=(255, 255, 255))
        tw = d.textlength(clock_text, font=self.small)
        d.text((w - tw - 10, 10), clock_text, font=self.small, fill=(255, 255, 255))
        img[:bar] = cv2.cvtColor(np.asarray(top), cv2.COLOR_RGB2BGR)
        return img


def _status(state):
    """Trạng thái trên dải thời gian từ public_state của bộ xử lý."""
    if state.get("sos_alert"):
        return ALERT
    if state.get("fall_down_since") is not None:
        return WATCH
    if state.get("hand_sos_hold") is not None:
        return HOLD
    if state.get("observation_lost") or state.get("fall_label") == engine.NO_DATA_LABEL:
        return LOST
    return OK


def _mmss(t):
    return f"{int(t // 60):02d}:{t % 60:04.1f}"


class _Writer:
    """Ghi MP4 H.264 (trình duyệt phát được). Máy không có bộ mã hoá H.264 thì ok=False, vẫn phân tích bình thường."""

    def __init__(self, path, w, h):
        self.ok = False
        self.out = None
        for codec in ("libx264", "h264", "libopenh264", "h264_mf"):
            try:
                out = av.open(path, "w", format="mp4", options={"movflags": "faststart"})
                stream = out.add_stream(codec, rate=HZ)
                stream.width, stream.height, stream.pix_fmt = w, h, "yuv420p"
                if codec == "libx264":
                    stream.options = {"crf": "27", "preset": "veryfast"}
                self.out, self.stream, self.ok = out, stream, True
                return
            except Exception:  # noqa: BLE001 — thử bộ mã hoá kế tiếp
                try:
                    out.close()
                except Exception:  # noqa: BLE001
                    pass

    def write(self, img):
        if not self.ok:
            return
        try:
            for packet in self.stream.encode(av.VideoFrame.from_ndarray(img, format="bgr24")):
                self.out.mux(packet)
        except Exception:  # noqa: BLE001 — lỗi mã hoá giữa chừng: bỏ video kết quả, giữ phần phân tích
            self.ok = False

    def close(self):
        if self.out is None:
            return
        try:
            if self.ok:
                for packet in self.stream.encode():
                    self.out.mux(packet)
            self.out.close()
        except Exception:  # noqa: BLE001
            self.ok = False


def analyze(path, config, fall_model, hand_model, signal_model, progress=None):
    """Chạy video qua bộ nhận diện. config = cấu hình như trang Trực tiếp. progress(phần_đã_xong 0..1).

    Trả về dict: thoi_luong, so_khung, xu_ly_giay, su_kien (list), canh_bao (list), dai_trang_thai [(t0, t1, mã)],
    anh (list (t, tên, jpeg bytes)), video (bytes MP4 hoặc None), dang_xac_minh (giây đã nằm nếu video hết giữa
    chừng lúc đang xác minh, else None)."""
    from mediapipe.python import solutions as mp_solutions

    import multi_person

    info = probe(path)
    duration = info[0] if info else 0.0
    clock = _Clock()
    base = clock.t
    sink = _Sink(clock, base)
    cfg = dict(config)
    cfg["mirror_camera"] = False  # video đã đúng chiều
    pose = mp_solutions.pose.Pose()
    hands = mp_solutions.hands.Hands(static_image_mode=False, max_num_hands=1, min_detection_confidence=0.5)
    multi = (multi_person.MultiPoseDetector()
             if cfg.get("multi_person") and engine.is_fall_v2(fall_model) else None)
    p = DetectionVideoProcessor(fall_model, hand_model, signal_model, pose, hands, cfg, multi_detector=multi,
                                clock=clock, sink=sink)
    p.PROCESS_EVERY_N_FRAMES = 1  # đã lấy mẫu 10 khung/giây ở _sampled
    p.frame_count = engine.WARMUP_FRAMES  # video không cần làm nóng camera

    fd, out_path = tempfile.mkstemp(suffix=".mp4")
    os.close(fd)
    writer = None
    banner = _Banner()
    grace = float(cfg["fall_grace_seconds"])
    strip, snaps = [], []
    prev_down, alerts_seen, n, t, started = None, 0, 0, 0.0, time.perf_counter()
    try:
        for t, frame in _sampled(path):
            if t > MAX_SECONDS:
                break
            img = np.ascontiguousarray(_fit(frame))
            if writer is None:
                writer = _Writer(out_path, img.shape[1], img.shape[0])
            clock.t = base + t
            out = p.recv(av.VideoFrame.from_ndarray(img, format="bgr24")).to_ndarray(format="bgr24")
            state = p.get_state()
            status = _status(state)

            new_marks = []  # khoảnh khắc đáng chụp ảnh ở khung này
            down = state.get("fall_down_since")
            if down is not None and prev_down is None:
                sink.items.append({"t": round(down - base, 2), "loai": "su_kien", "ten": "Phát hiện ngã",
                                   "chi_tiet": f"Bắt đầu xác minh {grace:.0f}s: nằm yên suốt thời gian này thì báo"})
                new_marks.append("Phát hiện ngã")
            prev_down = down
            new_marks += [a["ten"] for a in sink.alerts[alerts_seen:]]
            alerts_seen = len(sink.alerts)

            if status == WATCH:
                text = f"Nghi ngã — đang xác minh {min(t - (down - base), grace):.0f}/{grace:.0f} s"
            elif status == HOLD:
                text = f"Đang giữ cử chỉ SOS · còn {state['hand_sos_hold']:.1f} s"
            elif status == ALERT:
                text = "CẢNH BÁO — " + (sink.alerts[-1]["ten"] if sink.alerts else "đã gửi")
            else:
                text = STATUS_TEXT[status]
            out = banner.draw(out, status, text, _mmss(t))
            writer.write(out)

            if not strip or strip[-1][2] != status:
                if strip:
                    strip[-1][1] = t
                strip.append([t, t, status])
            for name in new_marks:
                if len(snaps) < MAX_SNAPSHOTS:
                    ok, jpg = cv2.imencode(".jpg", out, [cv2.IMWRITE_JPEG_QUALITY, 85])
                    if ok:
                        snaps.append((round(t, 1), name, jpg.tobytes()))

            n += 1
            if progress and duration > 0 and n % 5 == 0:
                progress(min(1.0, t / min(duration, MAX_SECONDS)))
        if strip:
            strip[-1][1] = t
    finally:
        pose.close()
        hands.close()
        if writer is not None:
            writer.close()
    video = None
    if writer is not None and writer.ok:
        with open(out_path, "rb") as f:
            video = f.read()
    try:
        os.remove(out_path)
    except OSError:
        pass

    final = p.get_state()
    pending = None
    if final.get("fall_down_since") is not None and not final.get("fall_escalated"):
        pending = round(clock.t - final["fall_down_since"], 1)
    return {
        "thoi_luong": round(t, 1), "so_khung": n, "xu_ly_giay": round(time.perf_counter() - started, 1),
        "su_kien": sorted(sink.items, key=lambda e: e["t"]), "canh_bao": sink.alerts,
        "dai_trang_thai": [tuple(s) for s in strip], "anh": snaps, "video": video, "dang_xac_minh": pending,
        "xac_minh_giay": grace,
    }

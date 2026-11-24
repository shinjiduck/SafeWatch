"""VideoProcessor cho streamlit-webrtc — thay cho cv2.VideoCapture(0) đọc
webcam CỦA MÁY CHẠY SERVER (chỉ work khi chạy local). Với streamlit-webrtc,
trình duyệt của MỖI NGƯỜI XEM tự capture webcam của HỌ qua WebRTC, gửi từng
frame lên hàm recv() dưới đây để xử lý, rồi phát video đã xử lý ngược lại —
đây là điều kiện bắt buộc để app hoạt động đúng khi deploy lên 1 địa chỉ
web thật cho nhiều người dùng riêng biệt.

Khác biệt lớn nhất so với vòng lặp while cũ trong live_view.py: recv() được
gọi bởi streamlit-webrtc trên 1 THREAD RIÊNG, liên tục, độc lập với vòng đời
script Streamlit chính (script chính chạy xong gần như ngay sau khi gọi
webrtc_streamer(), nhưng recv() vẫn tiếp tục chạy). Mọi state cần giữ giữa
các frame (buffer landmark, vote, timer...) phải nằm trong instance của
class này (self.*), không phải biến cục bộ trong script chính. Để script
chính (chạy trên thread khác) đọc được kết quả mới nhất, dùng self.lock +
self.public_state (dict) — ghi trong recv(), đọc ở script chính qua
get_state().
"""

import threading
import time
from collections import deque

import av
import cv2
from streamlit_webrtc import VideoProcessorBase

import detection_engine as engine
import event_log
import framing
import notifier
from hand_features import SIGNAL_SEQUENCE_LENGTH


class DetectionVideoProcessor(VideoProcessorBase):
    def __init__(self, fall_model, hand_model, signal_model, pose_detector, hand_detector, config):
        self.fall_model = fall_model
        self.hand_model = hand_model
        self.signal_model = signal_model
        self.pose_detector = pose_detector
        self.hand_detector = hand_detector

        # Snapshot cấu hình tại thời điểm bắt đầu stream — đổi ở trang Cấu
        # hình trong lúc đang stream sẽ KHÔNG áp dụng ngay, cần dừng/bắt đầu
        # lại stream để nhận cấu hình mới (đơn giản hoá, chấp nhận được).
        self.config = config

        self.lock = threading.Lock()
        self.public_state = {
            "fall_label": "Warmup...",
            "hand_label": "Warmup...",
            "hand_confidence": 0.0,
            "signal_detected": False,
            "signal_probability": 0.0,
            "fall_down_since": None,
            "fall_escalated": False,
            "sos_alert": False,
            "fps": 0.0,
            "monitor_start_time": time.time(),
        }

        self.fall_lm_window = deque(maxlen=engine.FALL_TIMESTEPS)
        self.fall_votes = deque(maxlen=engine.FALL_VOTE_WINDOW)
        self.hand_votes = deque(maxlen=engine.HAND_VOTE_WINDOW)
        self.signal_window = deque(maxlen=SIGNAL_SEQUENCE_LENGTH)

        self.fall_label = "Warmup..."
        self.fall_down_since = None
        self.fall_escalated = False
        self.was_fall_monitoring = False
        self.episode_escalated = False
        self.recovered_message_until = 0.0
        self.hand_label = "Warmup..."
        self.hand_confidence = 0.0
        self.signal_detected = False
        self.signal_probability = 0.0
        self.signal_consecutive_count = 0
        self.alert_until = 0.0
        self.was_alerting = False
        self.frame_count = 0
        self.prev_time = time.time()

        # Trạng thái quan sát (yêu cầu cải tiến số 3). recv() chạy trên thread
        # của streamlit-webrtc, tick() chạy trên thread script chính -> cùng
        # đụng vào state nên dùng chung 1 lock.
        self.state_lock = threading.Lock()
        self.last_frame_time = time.time()
        self.pose_last_seen = time.time()
        self.observation_lost = False
        self.camera_lost = False
        # Đứng quá gần / bị khuất / rời khung hình -> nhắc bằng chữ + giọng nói (framing.py).
        self.framing = framing.FramingMonitor()
        self.last_landmarks = None
        self.exit_side = None  # "left" / "right" / "middle" lúc mất người; None = chưa từng thấy ai

        # Model ngã v2 (app truyền vào FallV2Model) dùng bộ theo dõi 3 bước riêng;
        # không có thì giữ nguyên đường cũ (LSTM 10 frame + bỏ phiếu đa số).
        self.fall_tracker = (
            engine.FallV2Tracker(fall_model) if isinstance(fall_model, engine.FallV2Model) else None
        )

        event_log.init_db()
        notifier.init_db()

    def get_state(self):
        with self.lock:
            return dict(self.public_state)

    # Webcam thường gửi ~30 frame/giây, nhưng recv() phải xử lý XONG mỗi
    # frame mới được trả về hiển thị — chỉ chạy AI mỗi PROCESS_EVERY_N_FRAMES
    # frame, các frame còn lại trả về ngay (không chờ AI) để video mượt.
    PROCESS_EVERY_N_FRAMES = 3

    def recv(self, frame):
        img = frame.to_ndarray(format="bgr24")
        cfg = self.config
        now = time.time()

        if cfg["mirror_camera"]:
            img = cv2.flip(img, 1)

        self.frame_count += 1
        should_process = (
            self.frame_count > engine.WARMUP_FRAMES
            and self.frame_count % self.PROCESS_EVERY_N_FRAMES == 0
        )

        with self.state_lock:
            self.last_frame_time = now
            if self.camera_lost:
                self.camera_lost = False
                event_log.log_status("Camera đã khôi phục", "Nhận lại hình ảnh từ camera")
            if should_process:
                img = self._process_frame(img, now)
            self._update_alerts(now)

        fps = 1 / (now - self.prev_time) if now > self.prev_time else 0
        self.prev_time = now
        with self.lock:
            self.public_state["fps"] = fps

        return av.VideoFrame.from_ndarray(img, format="bgr24")

    def tick(self, now=None):
        """Gọi định kỳ từ thread script chính (views/live_view.py). Khi camera
        ngừng gửi frame thì recv() không còn được gọi, nên phần kiểm tra mất
        camera + đếm giờ sau ngã phải chạy được ở đây, độc lập với frame."""
        now = time.time() if now is None else now
        with self.state_lock:
            if not self.camera_lost and now - self.last_frame_time >= engine.CAMERA_STALL_SECONDS:
                self.camera_lost = True
                self._reset_observation_windows()
                self.fall_label = engine.NO_DATA_LABEL
                event_log.log_status(
                    "Mất tín hiệu camera",
                    f"Không nhận được frame nào trong {engine.CAMERA_STALL_SECONDS:.0f}s",
                )
            if self.camera_lost:
                self._update_alerts(now)

    def _reset_observation_windows(self):
        """Xoá mọi cửa sổ/vote cũ — không được nối dữ liệu trước và sau khi mất
        quan sát thành 1 chuỗi, cũng không được giữ nhãn tay SOS cũ."""
        self.fall_lm_window.clear()
        self.fall_votes.clear()
        if self.fall_tracker is not None:
            self.fall_tracker.clear_window()
        self.hand_votes.clear()
        self.hand_label = "No hands"
        self.hand_confidence = 0.0
        self.signal_window.clear()
        self.signal_consecutive_count = 0
        self.signal_detected = False

    def _process_frame(self, img, now):
        cfg = self.config
        img_rgb = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
        pose_results = self.pose_detector.process(img_rgb) if cfg["enable_fall"] else None
        hand_results = self.hand_detector.process(img_rgb) if cfg["enable_hand"] else None

        if cfg["enable_fall"]:
            if pose_results.pose_landmarks:
                self.fall_lm_window.append(engine.pose_landmarks_to_vector(pose_results))
                self.pose_last_seen = now
                landmarks = [[lm.x, lm.y, lm.z, lm.visibility] for lm in pose_results.pose_landmarks.landmark]
                self.last_landmarks = landmarks
                self.exit_side = None
                # Đang theo dõi sau ngã / đang báo động: không nhắc "đứng lại cho đúng".
                self.framing.observe(framing.assess(landmarks), now, quiet=self._busy(now))
                if self.fall_tracker is not None:
                    label = self.fall_tracker.update(landmarks, now)
                    if label is not None:
                        self.fall_label = label
                if self.observation_lost:
                    self.observation_lost = False
                    event_log.log_status("Quan sát đã khôi phục", "Thấy lại người trong khung hình")
                if cfg["show_overlay"]:
                    img = engine.draw_pose(img, pose_results)
            else:
                # Có khoảng trống trong chuỗi -> cửa sổ hiện tại không còn liên
                # tục, bỏ đi thay vì predict trên dữ liệu cũ.
                self.fall_lm_window.clear()
                if self.fall_tracker is not None:
                    label = self.fall_tracker.missing(now)
                    if label is not None and not self.observation_lost:
                        self.fall_label = label
                if not self.observation_lost and now - self.pose_last_seen >= engine.POSE_LOST_SECONDS:
                    self.observation_lost = True
                    self.fall_votes.clear()
                    self.fall_label = engine.NO_DATA_LABEL
                    if self.last_landmarks is not None:
                        self.exit_side = framing.exit_side(self.last_landmarks) or "middle"
                        self.framing.person_lost(now, quiet=self._busy(now))
                    event_log.log_status(
                        "Mất quan sát người",
                        f"Không thấy landmark tư thế trong {engine.POSE_LOST_SECONDS:.1f}s"
                        + {None: "", "left": " — đi ra mép trái", "right": " — đi ra mép phải",
                           "middle": " — mất dấu giữa khung hình (có thể bị che)"}[self.exit_side],
                    )

        raw_vector = None
        if cfg["enable_hand"]:
            if hand_results.multi_hand_landmarks:
                if cfg["show_overlay"]:
                    img = engine.draw_hand(img, hand_results)
                raw_vector = engine.hand_landmarks_to_vector(hand_results)
                self.signal_window.append(raw_vector)
            else:
                self.hand_votes.clear()
                self.hand_label = "No hands"
                self.signal_window.clear()
                self.signal_consecutive_count = 0
                self.signal_detected = False

        if cfg["enable_fall"] and self.fall_tracker is None and len(self.fall_lm_window) == engine.FALL_TIMESTEPS:
            self.fall_votes.append(engine.predict_fall(self.fall_model, list(self.fall_lm_window)))
            self.fall_label = engine.majority_label(self.fall_votes, self.fall_label)

        if cfg["enable_hand"] and raw_vector is not None:
            raw_label, self.hand_confidence = engine.predict_hand(
                self.hand_model, raw_vector, cfg["hand_confidence_threshold"]
            )
            self.hand_votes.append(raw_label)
            self.hand_label = engine.majority_label(self.hand_votes, self.hand_label)

        if (
            cfg["enable_hand"]
            and cfg["enable_signal"]
            and self.signal_model is not None
            and raw_vector is not None
            and len(self.signal_window) == SIGNAL_SEQUENCE_LENGTH
        ):
            raw_signal, self.signal_probability = engine.predict_signal_sequence(
                self.signal_model, list(self.signal_window), cfg["signal_confidence_threshold"]
            )
            self.signal_consecutive_count = self.signal_consecutive_count + 1 if raw_signal else 0
            self.signal_detected = self.signal_consecutive_count >= engine.SIGNAL_CONSECUTIVE_REQUIRED

        return img

    def _busy(self, now):
        return self.fall_down_since is not None or now < self.alert_until

    def _update_alerts(self, now):
        cfg = self.config

        if cfg["enable_fall"]:
            if self.fall_label == "Fall":
                if self.fall_down_since is None:
                    self.fall_down_since = now
                    self.was_fall_monitoring = True
                    self.episode_escalated = False
            elif self.fall_label == engine.NO_DATA_LABEL:
                # Mất quan sát KHÔNG phải bằng chứng đã đứng dậy: giữ nguyên
                # đồng hồ theo dõi sau ngã (nếu đang chạy), không huỷ, không
                # ghi "đã phục hồi". Hết giờ vẫn báo động như bình thường.
                pass
            else:
                if self.was_fall_monitoring and not self.episode_escalated:
                    event_log.log_event("Ngã - đã phục hồi", "Đứng lên lại trong lúc theo dõi, không báo động")
                    self.recovered_message_until = now + 4.0
                self.was_fall_monitoring = False
                self.fall_down_since = None
            self.fall_escalated = self.fall_down_since is not None and (now - self.fall_down_since) >= cfg[
                "fall_grace_seconds"
            ]
            if self.fall_escalated:
                self.episode_escalated = True
        else:
            self.fall_down_since = None
            self.fall_escalated = False

        raw_sos = (
            (cfg["enable_fall"] and self.fall_escalated)
            or (cfg["enable_hand"] and self.hand_label in engine.SOS_HAND_LABELS)
            or (cfg["enable_hand"] and cfg["enable_signal"] and self.signal_detected)
        )
        if raw_sos:
            self.alert_until = now + cfg["alert_hold_seconds"]
        sos_alert = now < self.alert_until

        if sos_alert and not self.was_alerting:
            if cfg["enable_fall"] and self.fall_escalated:
                note = ""
                if self.camera_lost:
                    note = " — camera mất tín hiệu trong lúc theo dõi"
                elif self.observation_lost:
                    note = " — không còn thấy người trong khung hình"
                details = f"Sau {cfg['fall_grace_seconds']:.0f}s theo dõi{note}"
                event_log.log_event("Ngã (không đứng lên lại)", details)
                # detected_at = lúc model thấy ngã lần đầu, để bảng thời gian
                # tách được đoạn "chờ xác minh" khỏi đoạn gửi/nhận.
                notifier.raise_alert("Ngã (không đứng lên lại)", details, detected_at=self.fall_down_since, now=now)
            elif cfg["enable_hand"] and self.hand_label in engine.SOS_HAND_LABELS:
                details = f"Độ tin cậy {self.hand_confidence * 100:.0f}%"
                event_log.log_event(self.hand_label, details)
                notifier.raise_alert(f"Cử chỉ SOS: {self.hand_label}", details, now=now)
            elif cfg["enable_hand"] and cfg["enable_signal"] and self.signal_detected:
                details = f"Xác suất {self.signal_probability * 100:.0f}%"
                event_log.log_event("Signal for Help (chuỗi động tác)", details)
                notifier.raise_alert("Signal for Help (chuỗi động tác)", details, now=now)
        self.was_alerting = sos_alert

        with self.lock:
            self.public_state.update(
                {
                    "fall_label": self.fall_label,
                    "hand_label": self.hand_label,
                    "hand_confidence": self.hand_confidence,
                    "signal_detected": self.signal_detected,
                    "signal_probability": self.signal_probability,
                    "fall_down_since": self.fall_down_since,
                    "fall_escalated": self.fall_escalated,
                    "sos_alert": sos_alert,
                    "recovered_message_until": self.recovered_message_until,
                    "observation_lost": self.observation_lost,
                    "camera_lost": self.camera_lost,
                    "last_frame_time": self.last_frame_time,
                    "framing_status": self.framing.status,
                    "voice_cue": self.framing.cue,
                    "voice_seq": self.framing.cue_seq,
                    "exit_side": self.exit_side,
                }
            )

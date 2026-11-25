"""Engine nhận diện dùng chung — tách từ app.py để các trang trong views/
(live_view, settings, dashboard) đều import cùng 1 nguồn, không lặp code.

app.py (bản gốc, 1 trang) vẫn giữ nguyên hoạt động độc lập như 1 fallback
đơn giản; views/live_view.py là bản giao diện mới, dùng module này.
"""

import os
from collections import Counter

import mediapipe as mp

# Bản mediapipe mới (0.10.35, xem lịch sử git — bump từ 0.10.21 để né bug
# PermissionError trên Streamlit Cloud) không tự gắn `mp.solutions` vào
# namespace gốc nữa (package __init__.py giờ chỉ eager-import Tasks API
# mới). API cũ (Pose/Hands) vẫn còn, chỉ cần import submodule trực tiếp
# thay vì trông cậy vào thuộc tính `mp.solutions`.
from mediapipe.python import solutions as mp_solutions
import numpy as np
import streamlit as st
import tensorflow as tf
from keras.layers import LSTM, Dense, Dropout
from keras.models import Sequential

from hand_features import load_hand_labels, normalize_hand_landmarks, normalize_hand_sequence

# Mặc định TensorFlow tự spawn nhiều thread nội bộ (intra/inter-op) CHO MỖI
# model. Ở đây có 3 model (Ngã, Tay, Signal) + 2 MediaPipe Solution (cũng tự
# có thread pool riêng) + thread mình tự tạo để chạy song song Pose/Hands
# (xem views/live_view.py) — tổng số thread thực tế dễ vượt xa số nhân CPU
# thật, gây tranh chấp CPU (oversubscription) khiến chạy CHẬM HƠN thay vì
# nhanh hơn. Giới hạn TF về ít thread nội bộ (nhường chỗ cho thread mình tự
# quản lý) sửa đúng vấn đề này. Phải set TRƯỚC khi TF chạy op đầu tiên.
try:
    tf.config.threading.set_intra_op_parallelism_threads(2)
    tf.config.threading.set_inter_op_parallelism_threads(2)
except RuntimeError:
    pass  # TF đã init rồi (module bị import lại) -- không set lại được, bỏ qua.

MODELS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "models")
FALL_MODEL_PATH = os.path.join(MODELS_DIR, "LSTM_model.h5")
HAND_MODEL_PATH = os.path.join(MODELS_DIR, "HandLandMarks_Model_Extended.keras")
SIGNAL_MODEL_PATH = os.path.join(MODELS_DIR, "SignalForHelpSequenceModel.keras")

FALL_TIMESTEPS = 10
WARMUP_FRAMES = 40

# Trạng thái an toàn khi mất hình (yêu cầu cải tiến số 3):
# - Không thấy landmark Pose liên tục quá POSE_LOST_SECONDS -> "NoData": xoá
#   cửa sổ cũ, KHÔNG coi là bình thường, KHÔNG huỷ theo dõi sau ngã.
# - Không nhận được frame nào quá CAMERA_STALL_SECONDS -> mất camera.
NO_DATA_LABEL = "NoData"
POSE_LOST_SECONDS = 1.5
CAMERA_STALL_SECONDS = 3.0

HAND_LABELS = load_hand_labels()
SOS_HAND_LABELS = {"Need Ambulance", "Need Help", "Signal For Help"}
UNCERTAIN_LABEL = "Uncertain"

FALL_VOTE_WINDOW = 5
HAND_VOTE_WINDOW = 5
ALERT_HOLD_SECONDS = 2.0
SIGNAL_CONSECUTIVE_REQUIRED = 5

DEFAULT_FALL_GRACE_SECONDS = 120
DEFAULT_HAND_CONFIDENCE_THRESHOLD = 0.8
DEFAULT_SIGNAL_CONFIDENCE_THRESHOLD = 0.7
DEFAULT_ENABLE_FALL = True
DEFAULT_ENABLE_HAND = True
DEFAULT_ENABLE_SIGNAL = False

# Nhãn kỹ thuật -> văn bản thân thiện hiển thị cho người dùng cuối (yêu cầu
# UX: không hiện "NotFall"/"class_id" trực tiếp trên giao diện chính).
FALL_LABEL_DISPLAY = {
    "Warmup...": "Đang khởi động...",
    "NotFall": "Không phát hiện ngã",
    "Fall": "Đã phát hiện ngã",
    NO_DATA_LABEL: "Không có người trong khung hình",
}
HAND_LABEL_DISPLAY = {
    "Warmup...": "Đang khởi động...",
    "No hands": "Không thấy tay",
    "Uncertain": "Không rõ cử chỉ",
}


def friendly_fall_label(raw_label):
    return FALL_LABEL_DISPLAY.get(raw_label, raw_label)


def friendly_hand_label(raw_label):
    return HAND_LABEL_DISPLAY.get(raw_label, raw_label)


CAMERA_RESOLUTIONS = {
    "320x240": (320, 240),
    "640x480": (640, 480),
    "1280x720": (1280, 720),
}

SETTINGS_DEFAULTS = {
    "fall_model_version": "v2",
    "multi_person": False,
    "hand_roi": False,  # nhận cử chỉ khi đứng xa — bật/tắt theo kết quả training/hand_eval/KIEM_DINH_TAY_XA.md
    "enable_fall": DEFAULT_ENABLE_FALL,
    "enable_hand": DEFAULT_ENABLE_HAND,
    "enable_signal": DEFAULT_ENABLE_SIGNAL,
    "fall_grace_seconds": DEFAULT_FALL_GRACE_SECONDS,
    "hand_confidence_threshold": DEFAULT_HAND_CONFIDENCE_THRESHOLD,
    "signal_confidence_threshold": DEFAULT_SIGNAL_CONFIDENCE_THRESHOLD,
    "alert_hold_seconds": ALERT_HOLD_SECONDS,
    "show_overlay": True,
    "mirror_camera": False,
    "camera_resolution": "640x480",
    "sound_alert": True,
    "voice_prompts": True,
    "silent_monitoring": True,
    "notify_email": False,
    "notify_sms": False,
    "notify_push": False,
    "retention_days": 30,
    "save_snapshot": False,
    "save_video": False,
}


def ensure_settings_defaults():
    """Gọi ở đầu mỗi trang cần đọc cấu hình — đảm bảo session_state luôn có
    đủ key với giá trị mặc định, để Live View/Dashboard chạy được cả khi
    người dùng chưa từng mở trang Cấu hình."""
    for key, value in SETTINGS_DEFAULTS.items():
        if key not in st.session_state:
            st.session_state[key] = value


def majority_label(votes, default):
    if not votes:
        return default
    return Counter(votes).most_common(1)[0][0]


def build_fall_model():
    model = Sequential()
    model.add(LSTM(units=50, return_sequences=True, input_shape=(FALL_TIMESTEPS, 99)))
    model.add(Dropout(0.2))
    model.add(LSTM(units=50, return_sequences=True))
    model.add(Dropout(0.2))
    model.add(LSTM(units=50, return_sequences=True))
    model.add(Dropout(0.2))
    model.add(LSTM(units=50))
    model.add(Dropout(0.2))
    model.add(Dense(units=1, activation="sigmoid"))
    model.load_weights(FALL_MODEL_PATH)
    return model


FALL_V2_MODEL_PATH = os.path.join(MODELS_DIR, "fall_v2.keras")
FALL_V2_META_PATH = os.path.join(MODELS_DIR, "fall_v2_meta.json")
FALL_V2_CONSECUTIVE = 2  # số lần xử lý liên tiếp vượt ngưỡng mới tính là 1 cú ngã
FALL_V2_RECOVER_SECONDS = 2.0  # đứng thẳng liên tục bao lâu mới coi là đã đứng dậy


class FallV2Model:
    """Model ngã v2 (training/fall_eval): nhận ra CÚ RƠI NHANH trên cửa sổ 1.5 s
    đặc trưng khung xương đã chuẩn hoá + vận tốc — xem fall_v2.py."""

    def __init__(self):
        import json

        self.model = tf.keras.models.load_model(FALL_V2_MODEL_PATH)
        with open(FALL_V2_META_PATH, encoding="utf-8") as f:
            meta = json.load(f)
        self.window = int(meta["window"])
        self.threshold = float(meta["threshold"])
        # số lần xử lý liên tiếp vượt ngưỡng — chọn trên validation cùng ngưỡng (model cũ không ghi -> 2)
        self.consecutive = int(meta.get("consecutive", FALL_V2_CONSECUTIVE))
        # Cổng "thấy rõ vai + hông": bật đúng như lúc train model này (meta không ghi -> tắt)
        import fall_v2

        fall_v2.GATE_VIS = meta.get("gate_vis")
        self.mean = np.asarray(meta["mean"], dtype=np.float32)
        self.std = np.asarray(meta["std"], dtype=np.float32)
        self._fn = tf.function(lambda x: self.model(x, training=False), reduce_retracing=True)

    def prob(self, window_features):
        x = (np.asarray([window_features], dtype=np.float32) - self.mean) / self.std
        return float(self._fn(x).numpy()[0, 0])


class FallV2Tracker:
    """Trạng thái ngã theo 3 bước: (1) model thấy cú rơi nhanh -> "Fall";
    (2) giữ "Fall" (processor đếm giờ xác minh); (3) chỉ trả "NotFall" khi người
    ĐỨNG/NGỒI THẲNG lại liên tục FALL_V2_RECOVER_SECONDS giây. Nằm xuống giường
    chủ động không có cú rơi nhanh nên không bị báo.

    Mất quan sát chỉ xoá cửa sổ đặc trưng, KHÔNG xoá trạng thái đã ngã — người
    quay lại khung hình mà vẫn nằm thì vẫn đang theo dõi sau ngã."""

    def __init__(self, model):
        from collections import deque

        import fall_v2

        self.fv = fall_v2
        self.model = model
        self.features = deque(maxlen=model.window)
        self.prev = None
        self.hits = 0
        self.down = False
        self.upright_since = None
        self.last_prob = 0.0

    def clear_window(self):
        self.features.clear()
        self.prev = None
        self.hits = 0
        self.missing_run = 0

    def mark_down(self):
        """Nghi ngã mà model không kịp thấy (VD ngã khuất sau vật cản, framing.vanished_after_drop): coi như
        đã ngã -> người quay lại khung hình vẫn phải đứng thẳng đủ lâu mới được tính là đã dậy."""
        self.down = True
        self.upright_since = None

    def missing(self, now):
        """Lần xử lý không thấy người. Thiếu <= fall_v2.MAX_BRIDGE lần liên tiếp
        (0.2 s — MediaPipe hay mất người đúng lúc đang ngã) thì nối bằng giá trị
        trước, giống hệt lúc train; dài hơn thì xoá cửa sổ."""
        self.missing_run = getattr(self, "missing_run", 0) + 1
        if not self.features or self.missing_run > self.fv.MAX_BRIDGE:
            self.clear_window()
            return None
        self.prev = None
        return self._decide(self.fv.bridge_feature(self.features[-1]), now)

    def update(self, landmarks, now):
        """landmarks: 33 x [x, y, z, visibility]. Trả nhãn hoặc None (chưa đủ dữ liệu)."""
        feature, self.prev = self.fv.feature_step(landmarks, self.prev)
        if feature is None:
            return self.missing(now)
        self.missing_run = 0
        return self._decide(feature, now)

    def _decide(self, feature, now):
        self.features.append(feature)
        if self.down:
            if self.fv.is_upright(feature):
                self.upright_since = self.upright_since or now
                if now - self.upright_since >= FALL_V2_RECOVER_SECONDS:
                    self.down = False
                    self.upright_since = None
                    self.hits = 0
                    return "NotFall"
            else:
                self.upright_since = None
            return "Fall"
        if len(self.features) < self.model.window:
            return None
        self.last_prob = self.model.prob(list(self.features))
        self.hits = self.hits + 1 if self.last_prob >= self.model.threshold else 0
        if self.hits >= getattr(self.model, "consecutive", FALL_V2_CONSECUTIVE):
            self.down = True
            self.upright_since = None
            return "Fall"
        return "NotFall"


def fall_v2_available():
    return os.path.exists(FALL_V2_MODEL_PATH) and os.path.exists(FALL_V2_META_PATH)


def is_fall_v2(model):
    """Model ngã v2 hay không — xét theo khả năng (có prob + window), KHÔNG dùng isinstance: Streamlit nạp lại
    module khi file đổi lúc server đang chạy, còn model trong @st.cache_resource vẫn là object của class CŨ ->
    isinstance(model, FallV2Model) sai -> app gọi model v2 theo kiểu model cũ và lỗi."""
    return model is not None and hasattr(model, "prob") and hasattr(model, "window")


@st.cache_resource
def load_fall_v2():
    return FallV2Model() if fall_v2_available() else None


def build_hand_model():
    return tf.keras.models.load_model(HAND_MODEL_PATH)


def build_signal_model():
    if not os.path.exists(SIGNAL_MODEL_PATH):
        return None
    return tf.keras.models.load_model(SIGNAL_MODEL_PATH)


@st.cache_resource
def load_models():
    return build_fall_model(), build_hand_model(), build_signal_model()


def warm_up_models(fall_model, hand_model, signal_model):
    """Gọi predict 1 lần với input giả (toàn số 0) để TF trace/biên dịch
    graph ngay bây giờ, không phải lúc frame thật đầu tiên tới (mới thấy
    chậm rõ ở vài giây đầu, kể cả khi model đã cache qua @st.cache_resource
    -- cache chỉ tránh load lại file, không tránh được chi phí lần predict
    đầu tiên)."""
    if is_fall_v2(fall_model):
        import fall_v2

        fall_model.prob([[0.0] * fall_v2.N_FEATURES] * fall_model.window)
    else:
        dummy_fall = [[0.0] * 99 for _ in range(FALL_TIMESTEPS)]
        predict_fall(fall_model, dummy_fall)

    dummy_hand = [0.0] * 63
    predict_hand(hand_model, dummy_hand, confidence_threshold=1.1)  # threshold>1 -> luôn "Uncertain", không quan trọng

    if signal_model is not None:
        from hand_features import SIGNAL_SEQUENCE_LENGTH

        dummy_signal = [[0.0] * 63 for _ in range(SIGNAL_SEQUENCE_LENGTH)]
        predict_signal_sequence(signal_model, dummy_signal, confidence_threshold=1.1)


@st.cache_resource
def get_mediapipe():
    # Dùng model_complexity mặc định (1, "full") — KHÔNG đổi xuống 0 (lite):
    # (1) model Ngã được train trên landmark sinh ra từ complexity=1, đổi
    # sẽ lệch phân phối input; (2) complexity=0 buộc MediaPipe copy/chọn
    # lại file .tflite khác lúc runtime (thao tác ghi), gây
    # PermissionError trên filesystem chỉ đọc như Streamlit Cloud —
    # complexity=1 dùng đúng file đã có sẵn, không cần ghi gì.
    mp_pose = mp_solutions.pose.Pose()
    mp_hands = mp_solutions.hands.Hands(static_image_mode=False, max_num_hands=1, min_detection_confidence=0.5)
    return mp_pose, mp_hands


def pose_landmarks_to_vector(results):
    lm = []
    for landmark in results.pose_landmarks.landmark:
        lm.extend([landmark.x, landmark.y, landmark.z])
    return lm


def make_roi_hands():
    """Bộ Hands riêng cho ô cắt quanh bàn tay (hand_roi.py) — từng ô độc lập nên static_image_mode=True."""
    return mp_solutions.hands.Hands(static_image_mode=True, max_num_hands=1, min_detection_confidence=0.5)


def hand_landmarks_to_vector(results):
    lm = []
    for landmark in results.multi_hand_landmarks[0].landmark:
        lm.extend([landmark.x, landmark.y, landmark.z])
    return lm


# Gọi model Keras kiểu eager (model(x)) với lớp LSTM rất chậm: đo được ~85ms
# mỗi lần cho model ~1MB, vì TF chạy từng op của từng bước thời gian bằng
# Python. Bọc trong tf.function để TF biên dịch thành graph 1 lần rồi tái
# sử dụng: ~1.8ms, output giống hệt (đã kiểm tra lệch = 0). Đây là nguyên
# nhân chính gây lag, không phải MediaPipe (~33ms cho Pose + Hands).
_compiled_models = {}


def _fast(model):
    entry = _compiled_models.get(id(model))
    if entry is None:
        # Giữ tham chiếu tới model trong entry để id() không bị tái sử dụng.
        entry = (model, tf.function(lambda x: model(x, training=False), reduce_retracing=True))
        _compiled_models[id(model)] = entry
    return entry[1]


def predict_fall(model, lm_list):
    data = np.expand_dims(np.array(lm_list, dtype=np.float32), axis=0)
    result = _fast(model)(data).numpy()
    return "Fall" if result[0][0] > 0.5 else "NotFall"


def predict_hand(model, lm_vector, confidence_threshold):
    normalized = normalize_hand_landmarks(lm_vector)
    lstm_input = np.array(normalized, dtype=np.float32).reshape(1, 21, 3)
    dnn_input = np.array(normalized, dtype=np.float32).reshape(1, 63)
    result = _fast(model)([lstm_input, dnn_input]).numpy()[0]
    confidence = float(np.max(result))
    if confidence < confidence_threshold:
        return UNCERTAIN_LABEL, confidence
    return HAND_LABELS[int(np.argmax(result))], confidence


def predict_signal_sequence(model, frame_sequence, confidence_threshold):
    normalized = normalize_hand_sequence(frame_sequence)
    data = np.expand_dims(np.array(normalized, dtype=np.float32), axis=0)
    probability = float(_fast(model)(data).numpy()[0][0])
    return probability >= confidence_threshold, probability


def draw_pose(img, results):
    mp_solutions.drawing_utils.draw_landmarks(img, results.pose_landmarks, mp_solutions.pose.POSE_CONNECTIONS)
    return img


def draw_hand(img, results):
    for hand_lms in results.multi_hand_landmarks:
        mp_solutions.drawing_utils.draw_landmarks(img, hand_lms, mp_solutions.hands.HAND_CONNECTIONS)
    return img

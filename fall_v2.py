"""Đặc trưng, nạp dữ liệu và đánh giá THEO SỰ KIỆN cho model ngã (yêu cầu 2).

Dùng chung giữa train/đánh giá (train_eval.py) và app (detection_engine.py)
để tiền xử lý lúc train và lúc chạy luôn khớp nhau.

Nhịp xử lý: app chạy AI 1/3 frame của webcam 30 fps -> ~10 lần/giây.
Mọi chuỗi (URFD 30 fps, video tự quay bất kỳ fps) đều được lấy mẫu về đúng
nhịp đó trước khi tính đặc trưng.
"""

import csv
import math
import os

import numpy as np

PROCESS_HZ = 10.0
WINDOW = 15  # 1.5 s ở 10 Hz — đủ chứa trọn 1 cú ngã (~0.5–1 s) + đoạn trước/sau

L_SH, R_SH, L_HIP, R_HIP, NOSE = 11, 12, 23, 24, 0
N_STATIC = 66 + 4
N_FEATURES = N_STATIC + 4


# ------------------------------------------------------------------ đặc trưng


def frame_static(lm):
    """lm: (33, >=2) toạ độ chuẩn hoá ảnh [0..1]. Trả (vector 70, scale, valid)."""
    pts = np.asarray(lm, dtype=np.float32)[:, :2]
    if np.isnan(pts).any():
        return None
    hip = (pts[L_HIP] + pts[R_HIP]) / 2
    sh = (pts[L_SH] + pts[R_SH]) / 2
    torso = sh - hip
    scale = float(np.linalg.norm(torso))
    scale = max(scale, 1e-3)
    norm = ((pts - hip) / scale).reshape(-1)
    angle = math.atan2(abs(torso[0]), abs(torso[1]) + 1e-6)  # 0 = thẳng đứng, pi/2 = nằm ngang
    span = pts.max(axis=0) - pts.min(axis=0)
    aspect = float(span[1] / (span[0] + 1e-3))  # cao/rộng: đứng >1, nằm <1
    return np.concatenate([norm, [angle, aspect, hip[1], pts[NOSE][1]]]).astype(np.float32), scale


def feature_step(lm, prev):
    """Đặc trưng 1 lần xử lý. prev = trạng thái trả về từ lần trước (None nếu
    lần trước không thấy người). Trả (vector N_FEATURES hoặc None, trạng thái mới).
    Vận tốc tính theo đơn vị chiều dài thân / giây ở nhịp PROCESS_HZ."""
    res = frame_static(lm)
    if res is None:
        return None, None
    static, scale = res
    if prev is None:
        vel = np.zeros(4, dtype=np.float32)
    else:
        d = static[-4:] - prev[0][-4:]
        vel = np.array([d[0], d[1], d[2] / scale, d[3] / scale], dtype=np.float32) * PROCESS_HZ
    return np.concatenate([static, vel]), (static, scale)


def is_upright(feature):
    """Tư thế đứng/ngồi thẳng: thân lệch < 35° so với phương thẳng đứng và
    khung người cao hơn rộng. Dùng để nhận ra người đã đứng dậy sau ngã."""
    return feature[66] < math.radians(35) and feature[67] > 1.2


MAX_BRIDGE = 2  # khoảng trống <= 2 lần xử lý (0.2 s) được nối; dài hơn thì xoá cửa sổ


def bridge_feature(last):
    """Giá trị lấp cho 1 lần xử lý bị thiếu ngắn: giữ tư thế trước, vận tốc = 0."""
    filled = last.copy()
    filled[N_STATIC:] = 0.0
    return filled


def sequence_features(landmarks):
    """landmarks: (P, 33, k) ĐÃ lấy mẫu ở PROCESS_HZ. Trả (P, N_FEATURES); NaN ở
    frame không thấy người, trừ khoảng trống ngắn (<= MAX_BRIDGE) được nối —
    MediaPipe hay mất người vài trăm ms đúng lúc đang ngã."""
    out = np.full((len(landmarks), N_FEATURES), np.nan, dtype=np.float32)
    prev = None
    for i, lm in enumerate(landmarks):
        feat, prev = feature_step(lm, prev)
        if feat is not None:
            out[i] = feat
    i = 0
    while i < len(out):
        if np.isnan(out[i, 0]):
            j = i
            while j < len(out) and np.isnan(out[j, 0]):
                j += 1
            if i > 0 and j < len(out) and j - i <= MAX_BRIDGE:
                out[i:j] = bridge_feature(out[i - 1])
            i = j
        else:
            i += 1
    return out


def resample(landmarks, fps):
    """Lấy mẫu chuỗi gốc (fps bất kỳ) về PROCESS_HZ. Trả (chuỗi, chỉ số frame gốc)."""
    step = max(1, int(round(fps / PROCESS_HZ)))
    idx = np.arange(0, len(landmarks), step)
    return landmarks[idx], idx


def windows(features, window=WINDOW):
    """Cửa sổ trượt bước 1; cửa sổ nào có frame thiếu (không thấy người) bị bỏ —
    đúng như app: mất quan sát thì xoá cửa sổ cũ."""
    xs, ends = [], []
    for end in range(window, len(features) + 1):
        w = features[end - window:end]
        if not np.isnan(w).any():
            xs.append(w)
            ends.append(end - 1)
    if not xs:
        return np.zeros((0, window, features.shape[1]), np.float32), np.zeros(0, int)
    return np.stack(xs), np.asarray(ends)


# --------------------------------------------------------------- nạp dữ liệu


class Sequence:
    def __init__(self, name, landmarks, fps, is_fall, frame_labels=None, fall_start_s=None, fall_end_s=None,
                 group=None):
        self.name = name
        self.fps = float(fps)
        self.is_fall = bool(is_fall)
        self.group = group or name
        sampled, idx = resample(landmarks, fps)
        self.sample_times = idx / self.fps
        self.features = sequence_features(sampled)
        # Nhãn mỗi frame đã lấy mẫu: 1 = đang trong pha ngã, 0 = không
        self.falling = np.zeros(len(idx), dtype=bool)
        if frame_labels is not None:
            lab = np.asarray(frame_labels)
            self.falling = lab[np.minimum(idx, len(lab) - 1)] == 0
            onset_frames = np.flatnonzero(lab == 0)
            if len(onset_frames):
                fall_start_s = onset_frames[0] / self.fps
                fall_end_s = (onset_frames[-1] + 1) / self.fps
        elif is_fall and fall_start_s is not None:
            self.falling = (self.sample_times >= fall_start_s) & (self.sample_times <= fall_end_s)
        self.fall_start_s = fall_start_s
        self.fall_end_s = fall_end_s
        self.duration_s = len(landmarks) / self.fps


def load_urfd(pose_dir, labels_dir):
    """URFD: nhãn mỗi frame trong urfall-cam0-{falls,adls}.csv
    (-1 = không nằm, 0 = đang ngã, 1 = đã nằm)."""
    labels = {}
    for fname in ("urfall-cam0-falls.csv", "urfall-cam0-adls.csv"):
        with open(os.path.join(labels_dir, fname), newline="") as f:
            for row in csv.reader(f):
                if len(row) < 3:
                    continue
                labels.setdefault(row[0], {})[int(row[1])] = int(row[2])
    seqs = []
    for name in sorted(os.listdir(pose_dir)):
        if not name.endswith(".npz"):
            continue
        seq = name[:-4]
        data = np.load(os.path.join(pose_dir, name))
        lm = data["landmarks"]
        frame_map = labels.get(seq, {})
        # frame trong CSV đánh số từ 1; frame không có trong CSV coi là -1
        lab = np.array([frame_map.get(i + 1, -1) for i in range(len(lm))])
        is_fall = seq.startswith("fall")
        # Chuỗi sinh hoạt (adl) cũng có nhãn 0 cho đoạn CHỦ ĐỘNG nằm xuống — đó
        # chính là ca khó không được báo, nên bỏ nhãn 0 của adl.
        seqs.append(Sequence(seq, lm, float(data["fps"]), is_fall, frame_labels=lab if is_fall else None))
    return seqs


def load_recorded(pose_dir, labels_csv):
    """Video tự quay. labels.csv: video,nguoi,loai(fall|adl),fall_start_s,fall_end_s
    — `nguoi` dùng để chia theo người (không để cùng 1 người ở cả train và test)."""
    seqs = []
    with open(labels_csv, newline="", encoding="utf-8-sig") as f:
        for row in csv.DictReader(f):
            stem = os.path.splitext(row["video"])[0]
            path = os.path.join(pose_dir, f"{stem}.npz")
            if not os.path.exists(path):
                print(f"Thiếu khung xương cho {row['video']} — chạy extract_pose.py trước")
                continue
            data = np.load(path)
            is_fall = row["loai"].strip().lower() == "fall"
            seqs.append(
                Sequence(
                    stem, data["landmarks"], float(data["fps"]), is_fall,
                    fall_start_s=float(row["fall_start_s"]) if is_fall else None,
                    fall_end_s=float(row["fall_end_s"]) if is_fall else None,
                    group=row.get("nguoi") or stem,
                )
            )
    return seqs


def window_dataset(seqs, flip=False):
    """X: cửa sổ, y: 1 nếu cửa sổ chứa >= 2 frame ĐANG NGÃ; bỏ cửa sổ mơ hồ
    (đúng 1 frame đang ngã)."""
    xs, ys = [], []
    for s in seqs:
        X, ends = windows(s.features)
        if not len(X):
            continue
        count = np.array([s.falling[e - WINDOW + 1:e + 1].sum() for e in ends])
        keep = count != 1
        xs.append(X[keep])
        ys.append((count[keep] >= 2).astype(np.float32))
    if not xs:
        return np.zeros((0, WINDOW, N_FEATURES), np.float32), np.zeros(0, np.float32)
    X, y = np.concatenate(xs), np.concatenate(ys)
    if flip:
        Xf = X.copy()
        Xf[:, :, 0:66:2] *= -1  # lật ngang: đổi dấu toạ độ x đã chuẩn hoá
        X, y = np.concatenate([X, Xf]), np.concatenate([y, y])
    return X, y


# ------------------------------------------------------- đánh giá theo sự kiện

MATCH_BEFORE_S = 0.5  # sự kiện báo sớm hơn lúc bắt đầu ngã tối đa 0.5 s vẫn tính đúng
MATCH_AFTER_S = 2.0  # và trễ tối đa 2 s sau khi kết thúc pha ngã
REFRACTORY_S = 5.0  # 2 lần báo cách nhau < 5 s tính là 1 sự kiện


def detect_events(probs, times, threshold, consecutive=2):
    """Báo sự kiện khi xác suất >= ngưỡng ở `consecutive` lần xử lý liên tiếp."""
    events, run, last = [], 0, -1e9
    for p, t in zip(probs, times):
        run = run + 1 if p >= threshold else 0
        if run >= consecutive and t - last >= REFRACTORY_S:
            events.append(t)
            last = t
    return events


def score_sequence(seq, events):
    """Trả (bắt được ngã?, số báo nhầm, độ trễ s)."""
    if not seq.is_fall:
        return False, len(events), None
    lo, hi = seq.fall_start_s - MATCH_BEFORE_S, seq.fall_end_s + MATCH_AFTER_S
    hits = [t for t in events if lo <= t <= hi]
    false = len(events) - (1 if hits else 0)
    return bool(hits), false, (hits[0] - seq.fall_start_s) if hits else None


def summarize(results):
    """results: list (seq, detected, n_false, latency)."""
    falls = [r for r in results if r[0].is_fall]
    adls = [r for r in results if not r[0].is_fall]
    adl_hours = sum(r[0].duration_s for r in adls) / 3600
    all_hours = sum(r[0].duration_s for r in results) / 3600
    detected = sum(1 for r in falls if r[1])
    lat = [r[3] for r in falls if r[3] is not None]
    fa_adl = sum(r[2] for r in adls)
    fa_all = sum(r[2] for r in results)
    return {
        "so_ca_nga": len(falls),
        "bat_duoc": detected,
        "bo_sot": len(falls) - detected,
        "recall": detected / len(falls) if falls else float("nan"),
        "so_chuoi_sinh_hoat": len(adls),
        "chuoi_sinh_hoat_bi_bao_nham": sum(1 for r in adls if r[2] > 0),
        "bao_nham_trong_sinh_hoat": fa_adl,
        "gio_sinh_hoat": adl_hours,
        "bao_nham_moi_gio_sinh_hoat": fa_adl / adl_hours if adl_hours else float("nan"),
        "bao_nham_tong": fa_all,
        "bao_nham_moi_gio_tong": fa_all / all_hours if all_hours else float("nan"),
        "do_tre_trung_vi_s": float(np.median(lat)) if lat else float("nan"),
    }

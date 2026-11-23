"""Trích khung xương MediaPipe Pose từ dữ liệu ngã -> 1 file .npz / chuỗi.

Nguồn hỗ trợ:
  - URFD: file zip ảnh PNG (fall-01-cam0-rgb.zip ...), 30 fps.
  - Video tự quay (.mp4/.mov/.avi...): fps đọc từ file.

Dùng đúng cấu hình MediaPipe như app (model_complexity mặc định = 1,
static_image_mode=False) để landmark khớp phân phối lúc chạy thật.

Chạy:
  python -I extract_pose.py <thư mục nguồn> <thư mục ra>
Đầu ra mỗi chuỗi: <tên>.npz gồm
  landmarks: (T, 33, 4) float32 — x, y, z, visibility; NaN nếu frame đó không thấy người
  fps: float
"""

import os
import sys
import zipfile

import cv2
import numpy as np
from mediapipe.python import solutions as mp_solutions

VIDEO_EXTS = {".mp4", ".mov", ".avi", ".mkv", ".webm", ".m4v"}


def _frames_from_zip(path):
    with zipfile.ZipFile(path) as zf:
        names = sorted(n for n in zf.namelist() if n.lower().endswith((".png", ".jpg", ".jpeg")))
        for name in names:
            data = np.frombuffer(zf.read(name), dtype=np.uint8)
            img = cv2.imdecode(data, cv2.IMREAD_COLOR)
            if img is not None:
                yield img


def _frames_from_video(path):
    cap = cv2.VideoCapture(path)
    try:
        while True:
            ok, img = cap.read()
            if not ok:
                break
            yield img
    finally:
        cap.release()


def _video_fps(path):
    cap = cv2.VideoCapture(path)
    fps = cap.get(cv2.CAP_PROP_FPS) or 30.0
    cap.release()
    return float(fps) if fps > 1 else 30.0


# Ngưỡng tin cậy MediaPipe: phải trùng với app (detection_engine.load_mediapipe).
# Đặt POSE_MIN_CONF=0.3 để thử ngưỡng thấp hơn (giữ dấu người tốt hơn lúc ngã nhanh / thiếu sáng).
POSE_MIN_CONF = float(os.environ.get("POSE_MIN_CONF", "0.5"))
# Độ phức tạp model tư thế: 1 = full (mặc định app), 2 = heavy (giữ khung xương tốt hơn khi tối / che khuất)
POSE_COMPLEXITY = int(os.environ.get("POSE_COMPLEXITY", "1"))


def extract(frames, max_width=640):
    pose = mp_solutions.pose.Pose(model_complexity=POSE_COMPLEXITY, min_detection_confidence=POSE_MIN_CONF,
                                  min_tracking_confidence=POSE_MIN_CONF)
    out = []
    try:
        for img in frames:
            h, w = img.shape[:2]
            if w > max_width:  # app nhận ~640x480; ảnh lớn hơn thì thu nhỏ cho giống
                img = cv2.resize(img, (max_width, int(h * max_width / w)))
            result = pose.process(cv2.cvtColor(img, cv2.COLOR_BGR2RGB))
            if result.pose_landmarks:
                out.append([[lm.x, lm.y, lm.z, lm.visibility] for lm in result.pose_landmarks.landmark])
            else:
                out.append(np.full((33, 4), np.nan).tolist())
    finally:
        pose.close()
    return np.asarray(out, dtype=np.float32).reshape(-1, 33, 4)


def main(src_dir, out_dir, shard=0, shards=1):
    os.makedirs(out_dir, exist_ok=True)
    # Duyệt cả thư mục con (CAUCAFall: Subject.N/<hành động>/<video>.avi); tên file phải khác nhau
    items = sorted(
        os.path.relpath(os.path.join(d, n), src_dir) for d, _, files in os.walk(src_dir) for n in files
        if os.path.splitext(n)[1].lower() in VIDEO_EXTS | {".zip"}
    )
    for i, rel in enumerate(items, 1):
        if (i - 1) % shards != shard:  # chạy nhiều tiến trình song song, mỗi tiến trình 1 phần
            continue
        path = os.path.join(src_dir, rel)
        name = os.path.basename(rel)
        stem, ext = os.path.splitext(name)
        ext = ext.lower()
        if ext == ".zip":
            seq = stem.replace("-cam0-rgb", "")
            frames, fps = _frames_from_zip(path), 30.0
        elif ext in VIDEO_EXTS:
            seq = stem
            frames, fps = _frames_from_video(path), _video_fps(path)
        else:
            continue
        target = os.path.join(out_dir, f"{seq}.npz")
        if os.path.exists(target):
            continue
        try:
            landmarks = extract(frames)
        except (zipfile.BadZipFile, OSError) as exc:
            print(f"[{i}/{len(items)}] BỎ QUA {name}: {exc}", flush=True)
            continue
        tmp = target + ".tmp.npz"  # ghi tạm rồi đổi tên: dừng giữa chừng không để lại file hỏng
        np.savez_compressed(tmp, landmarks=landmarks, fps=fps)
        os.replace(tmp, target)
        seen = np.mean(~np.isnan(landmarks[:, 0, 0])) * 100 if len(landmarks) else 0
        print(f"[{i}/{len(items)}] {seq}: {len(landmarks)} frame, thấy người {seen:.0f}%", flush=True)


if __name__ == "__main__":
    if len(sys.argv) not in (3, 5):
        sys.exit(__doc__ + "\nTuỳ chọn: thêm <shard> <số_shard> để chạy song song.")
    main(sys.argv[1], sys.argv[2], *(int(a) for a in sys.argv[3:5]))

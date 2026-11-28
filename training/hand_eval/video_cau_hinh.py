"""Chạy 1 video qua ĐÚNG bộ xử lý của app (DetectionVideoProcessor + MediaPipe thật + model thật) với cấu hình trình
diễn (detection_engine.SETTINGS_DEFAULTS), ghi lại mọi cảnh báo app sẽ gửi và nhãn tay theo thời gian.

Khác replay_eval.py (phát lại khung xương đã trích, chỉ phần ngã): script này đi từ điểm ảnh, bật cả phát hiện ngã lẫn
cử chỉ tay như app thật. Đồng hồ được giả lập theo thời gian video, AI xử lý 10 lần/giây (đúng nhịp app).

Chạy (trong training/hand_eval):
  python -X utf8 -I video_cau_hinh.py <video> <ra.json> [cắt=x0,y0,x1,y1] [khoá=giá trị ...]
VD: python -X utf8 -I video_cau_hinh.py sos.mp4 ra.json cat=476,120,1476,870 sos_filter=1
"""

import json
import os
import sys
import tempfile
import types

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "training", "fall_eval"))
os.environ.setdefault("TF_CPP_MIN_LOG_LEVEL", "3")


def run(video, out_json, *opts):
    import av
    import cv2
    from mediapipe.python import solutions as mp_solutions

    import detection_engine as engine
    import event_log
    import webrtc_processor
    from replay_eval import _Clock, sampled

    crop, overrides = None, {}
    for o in opts:
        k, v = o.split("=", 1)
        if k == "cat":
            crop = [int(x) for x in v.split(",")]
        else:
            overrides[k] = v.lower() in ("1", "true", "bat") if v.lower() in ("0", "1", "true", "false", "bat", "tat") else float(v)

    config = dict(engine.SETTINGS_DEFAULTS)
    config.update(overrides)
    config["show_overlay"] = False

    clock = _Clock()
    webrtc_processor.time = types.SimpleNamespace(time=clock.time)
    engine.WARMUP_FRAMES = 0
    webrtc_processor.DetectionVideoProcessor.PROCESS_EVERY_N_FRAMES = 1
    fd, db = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    event_log.DB_PATH = db
    alerts = []
    base = clock.t
    # Ghi lại cảnh báo thay vì gửi thật (CSDL đã trỏ sang file tạm ở trên)
    webrtc_processor.notifier.raise_alert = lambda kind, details, now=None, **kw: alerts.append(
        {"t": round(float(now) - base, 2), "loai": kind, "chi_tiet": details})

    fall_model = engine.FallV2Model() if config.get("fall_model_version", "v2") == "v2" else engine.build_fall_model()
    hand_model = engine.build_hand_model()
    signal_model = engine.build_signal_model() if config.get("enable_signal") else None
    pose = mp_solutions.pose.Pose()
    hands = mp_solutions.hands.Hands(static_image_mode=False, max_num_hands=1, min_detection_confidence=0.5)
    p = webrtc_processor.DetectionVideoProcessor(fall_model, hand_model, signal_model, pose, hands, config)

    timeline = []
    for t, img in sampled(video):
        if crop:
            x0, y0, x1, y1 = crop
            img = img[y0:y1, x0:x1]
        if img.shape[1] > 640:
            img = cv2.resize(img, (640, int(img.shape[0] * 640 / img.shape[1])))
        clock.t = base + float(t)
        p.recv(av.VideoFrame.from_ndarray(np.ascontiguousarray(img), format="bgr24"))
        timeline.append([round(float(t), 2), p.hand_label, p.fall_label, p.framing.status])
    pose.close()
    hands.close()
    out = {"video": video, "config": {k: config[k] for k in sorted(config) if not k.startswith("notify")},
           "alerts": alerts, "timeline": timeline}
    json.dump(out, open(out_json, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(f"{out_json}: {len(timeline)} khung, {len(alerts)} cảnh báo")
    for a in alerts:
        print(f"  {a['t']:7.1f}s  {a['loai']}  ({a['chi_tiet']})")


if __name__ == "__main__":
    if len(sys.argv) < 3:
        sys.exit(__doc__)
    run(*sys.argv[1:])

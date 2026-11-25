"""Lưu dữ liệu từng frame của phần cử chỉ tay trên video, để thử các luật lọc SOS offline (KIEM_DINH_TAY_XA.md).

Mỗi frame (10 lần/giây, như app): nhãn cao nhất của model 14 nhãn + độ tin cậy (chưa áp ngưỡng), và bàn tay có
giơ cao hơn vai không (cổ tay theo Hands so với vai theo Pose). Chỉ dùng Hands trên cả khung hình (như app mặc định).

Chạy: python -X utf8 -I sos_frames.py <ra.json> <shard> <số shard> <danh sách .txt | video | thư mục> [...]
"""

import glob
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "training", "fall_eval"))
os.environ.setdefault("TF_CPP_MIN_LOG_LEVEL", "3")
VIDEO_EXTS = (".mp4", ".avi", ".mov", ".mkv", ".webm")


def list_videos(sources):
    videos = []
    for src in sources:
        if src.lower().endswith(".txt"):
            videos += [line.strip() for line in open(src, encoding="utf-8") if line.strip()]
        elif os.path.isdir(src):
            videos += sorted(glob.glob(os.path.join(src, "*")))
        else:
            videos.append(src)
    return [v for v in videos if v.lower().endswith(VIDEO_EXTS)]


def main(out_json, shard, shards, *sources):
    import cv2
    from mediapipe.python import solutions as mp_solutions

    import detection_engine as engine
    from replay_eval import sampled

    model = engine.build_hand_model()
    videos = [v for i, v in enumerate(list_videos(sources)) if i % int(shards) == int(shard)]
    out = {}
    for path in videos:
        pose = mp_solutions.pose.Pose()
        hands = mp_solutions.hands.Hands(static_image_mode=False, max_num_hands=1, min_detection_confidence=0.5)
        frames = []
        for t, frame in sampled(path):
            if frame.shape[1] > 640:
                frame = cv2.resize(frame, (640, int(frame.shape[0] * 640 / frame.shape[1])))
            rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            pr, hr = pose.process(rgb), hands.process(rgb)
            if not hr.multi_hand_landmarks:
                frames.append([round(t, 2), None, 0.0, None])
                continue
            label, conf = engine.predict_hand(model, engine.hand_landmarks_to_vector(hr), 0.0)
            raised = None
            if pr.pose_landmarks:
                sh = [pr.pose_landmarks.landmark[i] for i in (11, 12)]
                if all(p.visibility >= 0.5 for p in sh):
                    raised = hr.multi_hand_landmarks[0].landmark[0].y < min(p.y for p in sh)
            frames.append([round(t, 2), label, round(float(conf), 4), raised])
        pose.close()
        hands.close()
        out[path] = frames
        print(os.path.basename(path), len(frames), flush=True)
    json.dump(out, open(out_json, "w", encoding="utf-8"))


if __name__ == "__main__":
    if len(sys.argv) < 5:
        sys.exit(__doc__)
    main(*sys.argv[1:])

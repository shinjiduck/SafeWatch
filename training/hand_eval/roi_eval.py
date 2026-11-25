"""Đo hand_roi.py trên video sinh hoạt (không có cử chỉ cầu cứu): số lần báo SOS nhầm và tỉ lệ thấy tay,
có / không dùng ô quanh bàn tay. Dùng đúng chuỗi xử lý tay của app: model 14 nhãn, ngưỡng tin cậy, bỏ phiếu 5 lần,
giữ báo động 2 s. Xem KIEM_DINH_TAY_XA.md.

Chạy (trong training/hand_eval):
  python -X utf8 -I roi_eval.py <ra.json> <shard> <số shard> <video | thư mục | danh sách .txt> [...]
  python -X utf8 -I roi_eval.py report <ra*.json>
"""

import glob
import json
import os
import sys
from collections import Counter, deque

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "training", "fall_eval"))
os.environ.setdefault("TF_CPP_MIN_LOG_LEVEL", "3")

CONF = 0.8  # = DEFAULT_HAND_CONFIDENCE_THRESHOLD
HOLD = 2.0  # = ALERT_HOLD_SECONDS
VIDEO_EXTS = (".mp4", ".avi", ".mov", ".mkv", ".webm")


class HandPipeline:
    """Bản sao logic tay trong webrtc_processor: bỏ phiếu đa số 5 lần, mất tay -> xoá phiếu, SOS giữ HOLD s."""

    def __init__(self):
        import detection_engine as engine

        self.engine = engine
        self.votes = deque(maxlen=engine.HAND_VOTE_WINDOW)
        self.label = "No hands"
        self.alert_until = -1.0
        self.alerts = 0
        self.alert_labels = Counter()

    def step(self, model, vector, now):
        e = self.engine
        if vector is None:
            self.votes.clear()
            self.label = "No hands"
        else:
            raw, _conf = e.predict_hand(model, vector, CONF)
            self.votes.append(raw)
            self.label = e.majority_label(self.votes, self.label)
        if self.label in e.SOS_HAND_LABELS:
            if now >= self.alert_until:  # cạnh lên: cảnh báo mới
                self.alerts += 1
                self.alert_labels[self.label] += 1
            self.alert_until = now + HOLD


def run(out_json, shard, shards, *sources):
    import cv2
    from mediapipe.python import solutions as mp_solutions

    import detection_engine as engine
    import hand_roi
    from replay_eval import sampled

    videos = []
    for src in sources:
        if src.lower().endswith(".txt"):  # danh sách đường dẫn, mỗi dòng 1 video
            videos += [line.strip() for line in open(src, encoding="utf-8") if line.strip()]
        else:
            videos += sorted(glob.glob(os.path.join(src, "*"))) if os.path.isdir(src) else [src]
    videos = [v for i, v in enumerate(v for v in videos if v.lower().endswith(VIDEO_EXTS)) if i % int(shards) == int(shard)]
    model = engine.build_hand_model()
    results = {}
    for path in videos:
        pose = mp_solutions.pose.Pose()
        hands = mp_solutions.hands.Hands(static_image_mode=False, max_num_hands=1, min_detection_confidence=0.5)
        hands_roi = mp_solutions.hands.Hands(static_image_mode=True, max_num_hands=1, min_detection_confidence=0.5)
        base, roi = HandPipeline(), HandPipeline()
        n = wrist_frames = seen_base = seen_roi = 0
        dur = 0.0
        for t, frame in sampled(path):
            if frame.shape[1] > 640:
                frame = cv2.resize(frame, (640, int(frame.shape[0] * 640 / frame.shape[1])))
            rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            pr, hr = pose.process(rgb), hands.process(rgb)
            full = engine.hand_landmarks_to_vector(hr) if hr.multi_hand_landmarks else None
            extra = None
            pose_lm = [[p.x, p.y, p.z, p.visibility] for p in pr.pose_landmarks.landmark] if pr.pose_landmarks else None
            if pose_lm is not None and hand_roi.candidate_rois(pose_lm, rgb.shape[1], rgb.shape[0]):
                wrist_frames += 1
                seen_base += full is not None
                if full is None:
                    r = hand_roi.detect(hands_roi, rgb, pose_lm)
                    extra = engine.hand_landmarks_to_vector(r) if r is not None else None
                seen_roi += (full is not None) or (extra is not None)
            base.step(model, full, t)
            roi.step(model, full if full is not None else extra, t)
            n += 1
            dur = t
        for d in (pose, hands, hands_roi):
            d.close()
        results[path] = {"frames": n, "seconds": dur, "wrist_frames": wrist_frames, "seen_base": seen_base,
                         "seen_roi": seen_roi, "alerts_base": base.alerts, "alerts_roi": roi.alerts,
                         "labels_base": dict(base.alert_labels), "labels_roi": dict(roi.alert_labels)}
        print(os.path.basename(path), results[path]["alerts_base"], results[path]["alerts_roi"], flush=True)
    json.dump(results, open(out_json, "w", encoding="utf-8"))


def report(*patterns):
    r = {}
    for p in patterns:
        for f in glob.glob(p):
            r.update(json.load(open(f, encoding="utf-8")))
    hours = sum(v["seconds"] for v in r.values()) / 3600
    wf = sum(v["wrist_frames"] for v in r.values())
    ab, ar = sum(v["alerts_base"] for v in r.values()), sum(v["alerts_roi"] for v in r.values())
    lb, lr = Counter(), Counter()
    for v in r.values():
        lb.update(v["labels_base"])
        lr.update(v["labels_roi"])
    print(f"{len(r)} video, {hours:.2f} giờ sinh hoạt (không có cử chỉ cầu cứu)")
    print(f"  Thấy tay khi Pose thấy cổ tay: {sum(v['seen_base'] for v in r.values()) / wf * 100:.1f}% -> "
          f"{sum(v['seen_roi'] for v in r.values()) / wf * 100:.1f}% (có ô quanh bàn tay)")
    print(f"  SOS báo nhầm: {ab} ({ab / hours:.1f}/giờ) -> {ar} ({ar / hours:.1f}/giờ)")
    print(f"  Nhãn SOS nhầm — không ô: {dict(lb)} | có ô: {dict(lr)}")


if __name__ == "__main__":
    if len(sys.argv) >= 3 and sys.argv[1] == "report":
        report(*sys.argv[2:])
    elif len(sys.argv) >= 5:
        run(*sys.argv[1:])
    else:
        sys.exit(__doc__)

"""Chế độ theo dõi NHIỀU NGƯỜI (tuỳ chọn trong Cấu hình). Bản 1 người giữ nguyên ở đường cũ
(MediaPipe Pose legacy) — tag git `app-1nguoi-v1` là bản trước khi có file này.

- MultiPoseDetector: MediaPipe PoseLandmarker, tối đa MAX_PEOPLE người, 33 điểm như bản cũ nên model ngã
  v2 dùng lại được. Ngưỡng phát hiện 0.3 (0.5 bỏ sót người đang ngồi khi có 2 người) + lọc khung xương trùng.
- PeopleTracker: gán mã ổn định cho từng người qua các frame (ghép theo vị trí giữa thân). Mỗi người có bộ
  theo dõi ngã v2, lịch sử độ cao hông (luật khuất sau vật cản) riêng.

Kiểm định: training/fall_eval/KIEM_DINH_NHIEU_NGUOI.md.
"""

import math
import os
from collections import deque

import numpy as np

import framing

MODEL_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "models", "pose_landmarker_full.task")
MAX_PEOPLE = 3
DETECTION_CONF = 0.3
PRESENCE_CONF = 0.5
TRACKING_CONF = 0.5
DUPLICATE_DIST = 0.05  # 2 khung xương lệch trung bình < 5% khung hình -> cùng 1 người

MATCH_DIST = 0.20  # ghép người giữa 2 lần xử lý: giữa thân dịch < 20% khung hình
DOWN_MATCH_DIST = 0.30  # người đang bị coi là đã ngã: đứng dậy / xuất hiện lại gần chỗ cũ vẫn nhận đúng người
FORGET_SECONDS = 3.0  # người đã mất dấu (không bị nghi ngã) quá lâu thì xoá


class MultiPoseDetector:
    def __init__(self, max_people=MAX_PEOPLE, model_path=MODEL_PATH):
        from mediapipe.tasks import python as mp_tasks
        from mediapipe.tasks.python import vision

        options = vision.PoseLandmarkerOptions(
            base_options=mp_tasks.BaseOptions(model_asset_path=model_path),
            running_mode=vision.RunningMode.VIDEO,
            num_poses=max_people,
            min_pose_detection_confidence=DETECTION_CONF,
            min_pose_presence_confidence=PRESENCE_CONF,
            min_tracking_confidence=TRACKING_CONF,
        )
        self._landmarker = vision.PoseLandmarker.create_from_options(options)
        self._last_ms = -1

    def detect(self, rgb, now):
        """rgb: ảnh RGB uint8. Trả về danh sách người, mỗi người 33 điểm [x, y, z, visibility]."""
        import mediapipe as mp

        ms = max(int(now * 1000), self._last_ms + 1)  # chế độ VIDEO đòi mốc thời gian tăng dần
        self._last_ms = ms
        image = mp.Image(image_format=mp.ImageFormat.SRGB, data=np.ascontiguousarray(rgb))
        result = self._landmarker.detect_for_video(image, ms)
        poses = [[[p.x, p.y, p.z, p.visibility] for p in person] for person in result.pose_landmarks]
        return remove_duplicates(poses)

    def close(self):
        self._landmarker.close()


def remove_duplicates(poses):
    kept = []
    for pose in sorted(poses, key=lambda p: -np.mean([q[3] for q in p])):
        xy = np.asarray(pose)[:, :2]
        if all(np.mean(np.abs(xy - np.asarray(k)[:, :2])) >= DUPLICATE_DIST for k in kept):
            kept.append(pose)
    return kept


def center(lm):
    pts = [lm[i] for i in framing.TORSO]
    return sum(p[0] for p in pts) / 4, sum(p[1] for p in pts) / 4


class Person:
    def __init__(self, pid, lm, now, fall_tracker):
        self.id = pid
        self.lm = lm
        self.center = center(lm)
        self.last_seen = now
        self.seen_now = True
        self.lost = False
        self.fall = fall_tracker
        self.hips = deque(maxlen=30)
        self.down_since = None  # đang bị coi là đã ngã từ lúc này (None = không)
        self.vanish_suspected = False


def draw_people(img, people):
    """Vẽ khung xương từng người: xanh = bình thường, đỏ = đang bị coi là đã ngã; kèm mã người."""
    import cv2
    from mediapipe.python.solutions.pose import POSE_CONNECTIONS

    h, w = img.shape[:2]
    for person in people:
        color = (40, 40, 230) if person.down_since is not None else (80, 200, 80)
        pts = [(int(p[0] * w), int(p[1] * h)) for p in person.lm]
        for a, b in POSE_CONNECTIONS:
            if person.lm[a][3] > 0.3 and person.lm[b][3] > 0.3:
                cv2.line(img, pts[a], pts[b], color, 2)
        cx, cy = int(person.center[0] * w), int(min(p[1] for p in person.lm[:11]) * h) - 10
        cv2.putText(img, f"#{person.id}", (max(0, cx - 12), max(15, cy)), cv2.FONT_HERSHEY_SIMPLEX, 0.6, color, 2)
    return img


class PeopleTracker:
    def __init__(self, make_fall_tracker):
        self.make_fall_tracker = make_fall_tracker
        self.people = {}
        self._next_id = 1

    def update(self, poses, now):
        """Ghép các khung xương mới với người đã biết (gần nhất trước), người mới thì cấp mã mới."""
        for person in self.people.values():
            person.seen_now = False
        pairs = []
        for i, pose in enumerate(poses):
            c = center(pose)
            for person in self.people.values():
                limit = DOWN_MATCH_DIST if person.down_since is not None else MATCH_DIST
                d = math.dist(c, person.center)
                if d <= limit:
                    pairs.append((d, i, person.id))
        used_pose, used_person = set(), set()
        for _d, i, pid in sorted(pairs):
            if i in used_pose or pid in used_person:
                continue
            used_pose.add(i)
            used_person.add(pid)
            person = self.people[pid]
            person.lm, person.center, person.last_seen = poses[i], center(poses[i]), now
            person.seen_now, person.lost = True, False
        for i, pose in enumerate(poses):
            if i not in used_pose:
                person = Person(self._next_id, pose, now, self.make_fall_tracker())
                self.people[person.id] = person
                self._next_id += 1
        for pid in [p.id for p in self.people.values()
                    if not p.seen_now and p.down_since is None and now - p.last_seen > FORGET_SECONDS]:
            del self.people[pid]
        return [p for p in self.people.values() if p.seen_now]

    def visible(self):
        return [p for p in self.people.values() if p.seen_now]

    def down(self):
        return [p for p in self.people.values() if p.down_since is not None]

"""Nhận cử chỉ tay khi đứng XA camera.

Vấn đề: vị trí tốt cho phát hiện ngã (cách camera ~2-3 m, thấy toàn thân) làm bàn tay chỉ còn ~8-9% khung hình
-> MediaPipe Hands trên cả khung hình hay bỏ sót. Đứng gần thì tay to nhưng hay ra ngoài khung (đo trên video
quay thử: training/fall_eval — xem README).

Cách làm: khung xương toàn thân (Pose) vẫn thấy cổ tay / ngón khi đứng xa. Khi Hands trên cả khung hình KHÔNG thấy
tay, cắt 1 ô vuông quanh bàn tay theo Pose, phóng to rồi chạy Hands trên ô đó; toạ độ được đổi ngược về khung
hình gốc nên vector đưa vào model cử chỉ y hệt lúc tay ở gần (model không cần train lại). Đứng gần (Hands đã thấy
tay) thì không chạy gì thêm.
"""

import math
from types import SimpleNamespace

import numpy as np

# Pose: (cổ tay, ngón út, ngón trỏ, ngón cái) của tay trái / tay phải
HAND_POINTS = ((15, 17, 19, 21), (16, 18, 20, 22))
SHOULDERS = (11, 12)
VISIBLE = 0.5
ROI_INPUT_PX = 256  # ô cắt được phóng về cỡ này trước khi đưa vào Hands
MIN_SIDE_PX = 40
SIDE_PER_HAND = 3.2  # cạnh ô = 3.2 x (cổ tay -> đầu ngón xa nhất theo Pose) — đủ chứa cả bàn tay xoè
SIDE_PER_SHOULDER = 0.55  # hoặc 0.55 x bề rộng vai, lấy số lớn hơn


def _seen(p):
    return p[3] >= VISIBLE and 0.0 <= p[0] <= 1.0 and 0.0 <= p[1] <= 1.0


def hand_raised(pose_lm):
    """Có cổ tay nào giơ cao hơn vai không (thường là đang ra hiệu) — dùng để KHÔNG nhắc "lùi ra xa" lúc đó."""
    shoulder_ys = [pose_lm[i][1] for i in SHOULDERS if pose_lm[i][3] >= VISIBLE]
    if not shoulder_ys:
        return False
    top = min(shoulder_ys)
    return any(_seen(pose_lm[w]) and pose_lm[w][1] < top for w, *_ in HAND_POINTS)


def candidate_rois(pose_lm, width, height):
    """Các ô vuông (x0, y0, cạnh) theo pixel quanh từng bàn tay thấy được, tay giơ cao hơn xếp trước."""
    shoulder_w = 0.0
    if all(pose_lm[i][3] >= VISIBLE for i in SHOULDERS):
        shoulder_w = abs(pose_lm[11][0] - pose_lm[12][0]) * width
    rois = []
    for idx in HAND_POINTS:
        wrist = pose_lm[idx[0]]
        if not _seen(wrist):
            continue
        pts = [(pose_lm[i][0] * width, pose_lm[i][1] * height) for i in idx if pose_lm[i][3] >= VISIBLE * 0.6]
        cx = sum(x for x, _ in pts) / len(pts)
        cy = sum(y for _, y in pts) / len(pts)
        wx, wy = wrist[0] * width, wrist[1] * height
        reach = max((math.dist((wx, wy), p) for p in pts[1:]), default=0.0)
        side = int(max(MIN_SIDE_PX, SIDE_PER_HAND * reach, SIDE_PER_SHOULDER * shoulder_w))
        side = min(side, width, height)
        x0 = int(min(max(cx - side / 2, 0), width - side))
        y0 = int(min(max(cy - side / 2, 0), height - side))
        rois.append((wy, (x0, y0, side)))
    return [roi for _, roi in sorted(rois)]


def to_frame_coords(points, roi, width, height):
    """Toạ độ Hands trong ô cắt (0..1) -> toạ độ chuẩn hoá theo khung hình gốc (như khi Hands chạy cả khung)."""
    x0, y0, side = roi
    return [((x0 + x * side) / width, (y0 + y * side) / height, z * side / width) for x, y, z in points]


def detect(hands, rgb, pose_lm, max_rois=1):
    """Chạy Hands trên ô quanh bàn tay. Trả về kết quả dạng giống MediaPipe Hands (multi_hand_landmarks) với toạ độ
    khung hình gốc, hoặc None. hands: 1 đối tượng mp.solutions.hands.Hands(static_image_mode=True)."""
    import cv2

    height, width = rgb.shape[:2]
    for roi in candidate_rois(pose_lm, width, height)[:max_rois]:
        x0, y0, side = roi
        crop = np.ascontiguousarray(rgb[y0:y0 + side, x0:x0 + side])
        if crop.size == 0:
            continue
        result = hands.process(cv2.resize(crop, (ROI_INPUT_PX, ROI_INPUT_PX)))
        if not result.multi_hand_landmarks:
            continue
        pts = [(p.x, p.y, p.z) for p in result.multi_hand_landmarks[0].landmark]
        mapped = to_frame_coords(pts, roi, width, height)
        return as_results(mapped)
    return None


def as_results(points):
    """21 điểm (x, y, z) -> đối tượng giống kết quả MediaPipe Hands (dùng được với engine.hand_landmarks_to_vector
    và hàm vẽ của MediaPipe)."""
    try:
        from mediapipe.framework.formats import landmark_pb2

        lm_list = landmark_pb2.NormalizedLandmarkList(
            landmark=[landmark_pb2.NormalizedLandmark(x=x, y=y, z=z) for x, y, z in points])
    except ImportError:  # môi trường kiểm thử không có mediapipe
        lm_list = SimpleNamespace(landmark=[SimpleNamespace(x=x, y=y, z=z) for x, y, z in points])
    return SimpleNamespace(multi_hand_landmarks=[lm_list], from_roi=True)

"""Dựng video phân tích ca khó (yêu cầu cải tiến số 2).

Đầu vào là traces.json do `train_eval.py cv` (hoặc `test`) ghi ra: xác suất ngã của
model mới tại từng thời điểm, lấy từ model KHÔNG thấy chuỗi đó lúc train, cùng
quyết định của model cũ trên cùng chuỗi.

Mỗi video gồm:
  - hình gốc + khung xương MediaPipe (đỏ "MẤT KHUNG XƯƠNG" khi không thấy người)
  - đồ thị xác suất ngã của model mới, vạch ngưỡng, vùng "đang ngã" theo nhãn
  - dải báo của model cũ, dải mất khung xương, con trỏ thời gian
  - dòng tiêu đề: kết quả 2 model và lý do (đo được, không đoán) khi bỏ sót

Nhóm ca:
  1_bat_duoc   model mới bắt được (ưu tiên ca model cũ bỏ sót)
  2_bo_sot     model mới bỏ sót (tất cả)
  3_v2_bao_nham  sinh hoạt bị model mới báo nhầm (tất cả)
  4_cu_bao_nham  sinh hoạt model cũ báo nhầm nhưng model mới không

Chạy:
  python -X utf8 -I make_case_videos.py <traces.json> <thư mục ra> <thư mục video> [<thư mục video> ...]
Thư mục video: nơi chứa video/zip gốc (CAUCAFall, URFD zips, video tự quay) — tìm theo tên.
"""

import csv
import json
import os
import subprocess
import sys
import zipfile

import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageFont

VID_W, VID_H = 640, 480
HEAD_H, PLOT_H = 84, 200
W, H = VID_W, HEAD_H + VID_H + PLOT_H
PAD_L, PAD_R = 118, 14
FONT_DIR = os.path.join(os.environ.get("WINDIR", "C:/Windows"), "Fonts")
MAX_CATCH, MAX_OLD_FALSE = 8, 8
VIDEO_EXTS = (".avi", ".mp4", ".mov", ".mkv", ".webm", ".m4v")

# Màu (RGB cho PIL; đổi sang BGR khi vẽ bằng OpenCV)
C_BG, C_TEXT, C_DIM = (24, 24, 28), (235, 235, 235), (150, 150, 160)
C_NEW, C_OLD, C_FALL, C_LOST, C_TH = (80, 190, 255), (255, 160, 40), (60, 200, 110), (230, 70, 70), (230, 70, 70)

CAUCA_TYPES = {
    "Fall backwards": "Ngã ngửa ra sau", "Fall forward": "Ngã về trước (về phía camera)",
    "Fall left": "Ngã sang trái", "Fall right": "Ngã sang phải", "Fall sitting": "Ngã từ tư thế ngồi",
    "Hop": "Nhảy lò cò", "Kneel": "Quỳ xuống", "Pick up object": "Cúi nhặt đồ", "Sit down": "Ngồi xuống ghế",
    "Walk": "Đi lại",
}
POSE_CONNECTIONS = [
    (11, 12), (11, 13), (13, 15), (12, 14), (14, 16), (11, 23), (12, 24), (23, 24), (23, 25), (25, 27),
    (24, 26), (26, 28), (27, 29), (29, 31), (27, 31), (28, 30), (30, 32), (28, 32), (0, 11), (0, 12),
]


def bgr(rgb):
    return tuple(int(c) for c in rgb[::-1])


_fonts = {}


def font(size, bold=False):
    key = (size, bold)
    if key not in _fonts:
        for name in (("arialbd.ttf", "segoeuib.ttf") if bold else ("arial.ttf", "segoeui.ttf")):
            try:
                _fonts[key] = ImageFont.truetype(os.path.join(FONT_DIR, name), size)
                break
            except OSError:
                continue
        else:
            _fonts[key] = ImageFont.load_default()
    return _fonts[key]


def draw_texts(img_bgr, items):
    """items: [(x, y, chuỗi, cỡ, màu RGB, đậm)] — PIL để hiện đúng dấu tiếng Việt."""
    pil = Image.fromarray(cv2.cvtColor(img_bgr, cv2.COLOR_BGR2RGB))
    d = ImageDraw.Draw(pil)
    for x, y, s, size, color, bold in items:
        d.text((x, y), s, font=font(size, bold), fill=color)
    return cv2.cvtColor(np.asarray(pil), cv2.COLOR_RGB2BGR)


def badge(text, color, size=22):
    f = font(size, True)
    l, t, r, b = f.getbbox(text)
    img = np.zeros((b - t + 14, r - l + 20, 3), np.uint8)
    img[:] = bgr(color)
    return draw_texts(img, [(10 - l, 7 - t, text, size, (255, 255, 255), True)])


def paste(dst, src, x, y):
    h, w = src.shape[:2]
    dst[y:y + h, x:x + w] = src


# ------------------------------------------------------------------ nguồn hình


def index_sources(dirs):
    idx = {}
    for root in dirs:
        for d, _, files in os.walk(root):
            for n in files:
                stem, ext = os.path.splitext(n)
                if ext.lower() in VIDEO_EXTS + (".zip",):
                    idx.setdefault(stem, os.path.join(d, n))
    return idx


def find_source(name, idx):
    for stem in (name, name[len("cauca-"):] if name.startswith("cauca-") else None, f"{name}-cam0-rgb"):
        if stem and stem in idx:
            return idx[stem]
    return None


def read_frames(path):
    if path.lower().endswith(".zip"):
        with zipfile.ZipFile(path) as zf:
            for n in sorted(n for n in zf.namelist() if n.lower().endswith((".png", ".jpg", ".jpeg"))):
                img = cv2.imdecode(np.frombuffer(zf.read(n), np.uint8), cv2.IMREAD_COLOR)
                if img is not None:
                    yield img
        return
    cap = cv2.VideoCapture(path)
    try:
        while True:
            ok, img = cap.read()
            if not ok:
                break
            yield img
    finally:
        cap.release()


def letterbox(img):
    """Thu về VID_W x VID_H, giữ tỉ lệ. Trả (ảnh, vị trí + kích thước vùng ảnh thật)."""
    h, w = img.shape[:2]
    scale = min(VID_W / w, VID_H / h)
    nw, nh = int(w * scale), int(h * scale)
    out = np.zeros((VID_H, VID_W, 3), np.uint8)
    ox, oy = (VID_W - nw) // 2, (VID_H - nh) // 2
    out[oy:oy + nh, ox:ox + nw] = cv2.resize(img, (nw, nh))
    return out, (ox, oy, nw, nh)


def draw_skeleton(img, lm, box):
    ox, oy, nw, nh = box
    pts = [(int(ox + x * nw), int(oy + y * nh)) for x, y in lm[:, :2]]
    for a, b in POSE_CONNECTIONS:
        if lm[a, 3] > 0.3 and lm[b, 3] > 0.3:
            cv2.line(img, pts[a], pts[b], (80, 255, 120), 2, cv2.LINE_AA)
    for i in range(11, 33):
        if lm[i, 3] > 0.3:
            cv2.circle(img, pts[i], 3, (255, 255, 255), -1, cv2.LINE_AA)


# ------------------------------------------------------------------ phân tích


def describe(name, src_path):
    if name.startswith("cauca-"):
        action = os.path.basename(os.path.dirname(src_path)) if src_path else ""
        subject = os.path.basename(os.path.dirname(os.path.dirname(src_path))).replace("Subject.", "") if src_path else "?"
        return f"CAUCAFall · {CAUCA_TYPES.get(action, action)} · người {subject}", CAUCA_TYPES.get(action, action)
    if name.startswith("fall-"):
        return f"URFD · {name} · ngã", "URFD ngã"
    if name.startswith("adl-"):
        return f"URFD · {name} · sinh hoạt (ngồi / cúi / nằm xuống)", "URFD sinh hoạt"
    return name, name


def analyse(tr, landmarks, fps):
    times, probs = np.asarray(tr["times"]), np.asarray(tr["probs"])
    th = tr["threshold"]
    info = {"max_p": float(probs.max()) if len(probs) else 0.0}
    if tr["is_fall"]:
        lo, hi = tr["fall_start_s"] - 0.5, tr["fall_end_s"] + 2.0
        in_win = (times >= lo) & (times <= hi)
        info["max_p"] = float(probs[in_win].max()) if in_win.any() else 0.0
        run = best = 0
        for p in probs[in_win]:
            run = run + 1 if p >= th else 0
            best = max(best, run)
        info["above_run"] = best
        f0, f1 = int(tr["fall_start_s"] * fps), int((tr["fall_end_s"] + 0.5) * fps) + 1
        seg = landmarks[f0:f1, 0, 0]
        info["lost"] = float(np.isnan(seg).mean()) if len(seg) else 0.0
    else:
        info["lost"] = float(np.isnan(landmarks[:, 0, 0]).mean()) if len(landmarks) else 0.0
    new = ("BÁO ĐÚNG" if tr["detected"] else "KHÔNG BÁO") if tr["is_fall"] else (
        f"BÁO NHẦM {tr['n_false']} lần" if tr["n_false"] else "không báo (đúng)")
    old = ("báo đúng" if tr["old_detected"] else "không báo") if tr["is_fall"] else (
        f"báo nhầm {tr['old_n_false']} lần" if tr["old_n_false"] else "không báo")
    if tr["is_fall"] and tr["detected"]:
        lat = min(t for t in tr["events"] if tr["fall_start_s"] - 0.5 <= t <= tr["fall_end_s"] + 2.0)
        new += f" sau {lat - tr['fall_start_s']:.1f} s"
    reasons = []
    if tr["is_fall"] and not tr["detected"]:
        if info["lost"] >= 0.2:
            reasons.append(f"mất khung xương {info['lost']:.0%} thời gian ngã")
        if info["max_p"] >= th:
            reasons.append(f"xác suất vượt ngưỡng {th:g} chỉ {info['above_run']} lần, cần 2 lần liên tiếp")
        else:
            digits = 3 if round(info["max_p"], 2) >= th else 2
            reasons.append(f"xác suất cao nhất {info['max_p']:.{digits}f} < ngưỡng {th:g}")
    elif not tr["is_fall"] and tr["n_false"]:
        reasons.append(f"xác suất cao nhất {info['max_p']:.2f} ≥ ngưỡng {th:g}")
    info.update(new=new, old=old, reason="; ".join(reasons))
    return info


def pick_cases(traces):
    def cat_key(name):
        return 0 if name.startswith("cauca-") else 1

    falls = [n for n, t in traces.items() if t["is_fall"]]
    adls = [n for n, t in traces.items() if not t["is_fall"]]
    caught = sorted((n for n in falls if traces[n]["detected"]),
                    key=lambda n: (traces[n]["old_detected"], cat_key(n), n))
    cases = [("1_bat_duoc", n) for n in caught[:MAX_CATCH]]
    cases += [("2_bo_sot", n) for n in sorted(falls, key=lambda n: (cat_key(n), n)) if not traces[n]["detected"]]
    cases += [("3_v2_bao_nham", n) for n in sorted(adls) if traces[n]["n_false"]]
    old_only = [n for n in sorted(adls, key=lambda n: (cat_key(n), n))
                if traces[n]["old_n_false"] and not traces[n]["n_false"]]
    # đa dạng: lần lượt từng nhóm động tác (tiền tố tên CAUCAFall / URFD)
    seen, picked = set(), []
    for n in old_only:
        kind = "".join(ch for ch in n if not ch.isdigit())
        if kind not in seen:
            seen.add(kind)
            picked.append(n)
    picked += [n for n in old_only if n not in picked]
    cases += [("4_cu_bao_nham", n) for n in picked[:MAX_OLD_FALSE]]
    return cases


CAT_TITLES = {
    "1_bat_duoc": ("MODEL MỚI BẮT ĐƯỢC", C_FALL),
    "2_bo_sot": ("MODEL MỚI BỎ SÓT", C_LOST),
    "3_v2_bao_nham": ("MODEL MỚI BÁO NHẦM", C_OLD),
    "4_cu_bao_nham": ("MODEL CŨ BÁO NHẦM — MODEL MỚI KHÔNG", C_NEW),
}


# ------------------------------------------------------------------ dựng hình


def static_layers(tr, info, title, cat, landmarks, fps, duration):
    canvas = np.zeros((H, W, 3), np.uint8)
    canvas[:] = bgr(C_BG)
    cat_title, cat_color = CAT_TITLES[cat]
    texts = [
        (10, 6, f"{cat_title}", 19, cat_color, True),
        (10, 30, title, 16, C_TEXT, False),
        (10, 52, f"Model mới: {info['new']}   ·   Model cũ: {info['old']}", 15, C_TEXT, False),
    ]
    if info["reason"]:
        texts.append((10, 68, f"Lý do đo được: {info['reason']}", 13, (255, 200, 120), False))

    top = HEAD_H + VID_H
    x0, x1 = PAD_L, W - PAD_R
    gy0, gy1 = top + 10, top + 120  # đồ thị xác suất
    oy0, oy1 = top + 130, top + 146  # dải model cũ
    ly0, ly1 = top + 154, top + 170  # dải mất khung xương

    def X(t):
        return int(x0 + (x1 - x0) * min(max(t / duration, 0), 1))

    def Y(p):
        return int(gy1 - (gy1 - gy0) * p)

    cv2.rectangle(canvas, (x0, gy0), (x1, gy1), (45, 45, 52), -1)
    if tr["is_fall"]:
        cv2.rectangle(canvas, (X(tr["fall_start_s"]), gy0), (X(tr["fall_end_s"]), gy1), (60, 110, 60), -1)
    th = tr["threshold"]
    for xx in range(x0, x1, 10):
        cv2.line(canvas, (xx, Y(th)), (min(xx + 5, x1), Y(th)), bgr(C_TH), 1)
    pts = np.array([[X(t), Y(p)] for t, p in zip(tr["times"], tr["probs"])], np.int32)
    if len(pts) > 1:
        cv2.polylines(canvas, [pts], False, bgr(C_NEW), 2, cv2.LINE_AA)
    for t in tr["events"]:
        cv2.line(canvas, (X(t), gy0), (X(t), gy1), (0, 0, 255), 2)

    cv2.rectangle(canvas, (x0, oy0), (x1, oy1), (45, 45, 52), -1)
    times = tr["times"]
    for i, v in enumerate(tr["old_voted"]):
        if v:
            t_end = times[i + 1] if i + 1 < len(times) else duration
            cv2.rectangle(canvas, (X(times[i]), oy0), (max(X(t_end), X(times[i]) + 1), oy1), bgr(C_OLD), -1)
    for t in tr["old_events"]:
        cv2.line(canvas, (X(t), oy0 - 3), (X(t), oy1 + 3), (255, 255, 255), 2)

    cv2.rectangle(canvas, (x0, ly0), (x1, ly1), (45, 45, 52), -1)
    lost = np.isnan(landmarks[:, 0, 0])
    for i in np.flatnonzero(lost):
        cv2.rectangle(canvas, (X(i / fps), ly0), (max(X((i + 1) / fps), X(i / fps) + 1), ly1), bgr(C_LOST), -1)

    for s in range(0, int(duration) + 1):
        cv2.line(canvas, (X(s), ly1 + 2), (X(s), ly1 + 6), bgr(C_DIM), 1)
        texts.append((X(s) - 4, ly1 + 8, str(s), 11, C_DIM, False))
    texts += [
        (6, gy0 + 16, "Model mới:", 13, C_NEW, True), (6, gy0 + 33, "xác suất ngã", 12, C_NEW, False),
        (x1 - 78, Y(th) + 3, f"ngưỡng {th:g}", 12, C_TH, False),
        (6, gy1 - 30, "nền xanh =", 11, C_FALL, False), (6, gy1 - 16, "đang ngã (nhãn)", 11, C_FALL, False),
        (6, oy0 + 1, "Model cũ báo", 12, C_OLD, True), (6, ly0 + 1, "Mất khung xương", 12, C_LOST, True),
        (x1 - 40, ly1 + 8, "giây", 11, C_DIM, False),
    ]
    canvas = draw_texts(canvas, texts)
    return canvas, X, (gy0, ly1)


def render_case(cat, tr, name, src, out_path, writer_all):
    npz = np.load(tr["npz"])
    landmarks, fps = npz["landmarks"], float(npz["fps"])
    duration = max(len(landmarks) / fps, 1e-3)
    title, short = describe(name, src)
    info = analyse(tr, landmarks, fps)
    base, X, (py0, py1) = static_layers(tr, info, title, cat, landmarks, fps, duration)
    b_lost = badge("MẤT KHUNG XƯƠNG", C_LOST, 18)
    b_new = badge("MODEL MỚI BÁO NGÃ", (220, 40, 40), 22)
    b_old = badge("Model cũ báo ngã", C_OLD, 18)
    b_fall = badge("đang ngã (nhãn)", C_FALL, 15)

    writer = open_writer(out_path, fps)
    for i, img in enumerate(read_frames(src)):
        t = i / fps
        frame = base.copy()
        vid, box = letterbox(img)
        lm = landmarks[i] if i < len(landmarks) else None
        if lm is not None and not np.isnan(lm[0, 0]):
            draw_skeleton(vid, lm, box)
        else:
            paste(vid, b_lost, 10, VID_H - b_lost.shape[0] - 10)
        if any(0 <= t - e <= 2.0 for e in tr["events"]):
            paste(vid, b_new, VID_W - b_new.shape[1] - 10, 10)
        if any(0 <= t - e <= 2.0 for e in tr["old_events"]):
            paste(vid, b_old, VID_W - b_old.shape[1] - 10, 56)
        if tr["is_fall"] and tr["fall_start_s"] <= t <= tr["fall_end_s"]:
            paste(vid, b_fall, 10, 10)
        frame[HEAD_H:HEAD_H + VID_H] = vid
        cv2.line(frame, (X(t), py0), (X(t), py1), (255, 255, 255), 1)
        writer.write(frame)
        if writer_all is not None:
            writer_all.write(frame)
    writer.release()
    return title, short, info


def title_card(text, color, sub=""):
    card = np.zeros((H, W, 3), np.uint8)
    card[:] = bgr(C_BG)
    return draw_texts(card, [(30, H // 2 - 40, text, 26, color, True), (30, H // 2 + 4, sub, 16, C_TEXT, False)])


class FfmpegWriter:
    """H.264 qua ffmpeg (imageio-ffmpeg): file nhỏ, mở được trên trình duyệt / Zalo."""

    def __init__(self, exe, path, fps):
        self.proc = subprocess.Popen(
            [exe, "-y", "-loglevel", "error", "-f", "rawvideo", "-pix_fmt", "bgr24", "-s", f"{W}x{H}",
             "-r", f"{fps:g}", "-i", "-", "-c:v", "libx264", "-preset", "veryfast", "-crf", "26",
             "-pix_fmt", "yuv420p", "-movflags", "+faststart", path],
            stdin=subprocess.PIPE,
        )

    def write(self, frame):
        self.proc.stdin.write(np.ascontiguousarray(frame).tobytes())

    def release(self):
        self.proc.stdin.close()
        self.proc.wait()


def _ffmpeg_exe():
    try:
        import imageio_ffmpeg

        return imageio_ffmpeg.get_ffmpeg_exe()
    except Exception:  # noqa: BLE001 — không có thì dùng OpenCV
        return None


FFMPEG = _ffmpeg_exe()


def open_writer(path, fps):
    if FFMPEG:
        return FfmpegWriter(FFMPEG, path, fps)
    w = cv2.VideoWriter(path, cv2.VideoWriter_fourcc(*"mp4v"), fps, (W, H))
    if not w.isOpened():
        raise RuntimeError("Không mở được bộ ghi video")
    return w


def main(traces_path, out_dir, *video_dirs):
    with open(traces_path, encoding="utf-8") as f:
        traces = json.load(f)
    os.makedirs(out_dir, exist_ok=True)
    idx = index_sources(video_dirs)
    cases = pick_cases(traces)
    ALL_FPS = 20.0
    writer_all = open_writer(os.path.join(out_dir, "00_tong_hop.mp4"), ALL_FPS)
    rows, last_cat = [], None
    for k, (cat, name) in enumerate(cases, 1):
        src = find_source(name, idx)
        if not src:
            print(f"[{k}/{len(cases)}] KHÔNG TÌM THẤY video gốc của {name} — bỏ", flush=True)
            continue
        if cat != last_cat:
            n_cat = sum(1 for c, _ in cases if c == cat)
            card = title_card(CAT_TITLES[cat][0], CAT_TITLES[cat][1], f"{n_cat} ca")
            for _ in range(int(ALL_FPS * 2)):
                writer_all.write(card)
            last_cat = cat
        out_name = f"{cat}__{name}.mp4"
        # Video tổng hợp ghi ở 20 fps; nguồn 30 fps (URFD) sẽ chậm lại 1.5 lần — chấp nhận để xem kỹ.
        title, short, info = render_case(cat, traces[name], name, src, os.path.join(out_dir, out_name),
                                         writer_all)
        rows.append([cat, name, short, info["new"], info["old"], info["reason"], f"{info['lost']:.2f}",
                     f"{info['max_p']:.2f}", out_name])
        print(f"[{k}/{len(cases)}] {out_name}: {info['new']} | {info['reason']}", flush=True)
    writer_all.release()
    with open(os.path.join(out_dir, "danh_sach_ca.csv"), "w", newline="", encoding="utf-8-sig") as f:
        w = csv.writer(f)
        w.writerow(["nhom", "chuoi", "dong_tac", "model_moi", "model_cu", "ly_do", "ti_le_mat_khung_xuong",
                    "xac_suat_cao_nhat", "file"])
        w.writerows(rows)
    print(f"Xong {len(rows)} video -> {out_dir}")


if __name__ == "__main__":
    if len(sys.argv) < 4:
        sys.exit(__doc__)
    main(*sys.argv[1:])

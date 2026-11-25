"""Kiểm định chế độ 1 người / nhiều người bằng cách PHÁT LẠI khung xương vào đúng bộ xử lý của app.

Xem KIEM_DINH_NHIEU_NGUOI.md (cách làm + tiêu chí ghi trước khi chạy).

Các lệnh (chạy trong training/fall_eval, nhớ -X utf8 -I):
  lists <thư mục danh sách>
      Tạo danh sách bài thử: gmd.csv (GMDCSA-24), cauca.csv (CAUCAFall), charades.csv (Charades, chỉ sinh
      hoạt), ghep.csv (2 người: ghép 2 clip GMDCSA-24 của 2 người khác nhau cạnh nhau).
  extract <single|multi> <danh sách.csv> <thư mục ra> [<shard> <số shard>]
      Trích khung xương ở 10 lần/giây (đúng nhịp app). single = MediaPipe Pose cũ (như app 1 người),
      multi = multi_person.MultiPoseDetector (như app nhiều người). Lưu poses (T, P, 33, 4), times, ms.
  replay <single|multi> <phiên bản model> <danh sách.csv> <thư mục khung xương> <file kết quả.json> [<shard> <n>]
      Phát lại từng clip vào DetectionVideoProcessor (thời gian xác minh 30 s), ghi lại lúc bắt đầu theo
      dõi sau ngã, cảnh báo có gửi không, vị trí người bị coi là ngã.
  report <file kết quả.json> [...]
      Gộp + in bảng.
"""

import csv
import glob
import json
import math
import os
import re
import sys
import tempfile
import time
import types

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, ROOT)
sys.path.insert(0, HERE)
os.environ.setdefault("TF_CPP_MIN_LOG_LEVEL", "3")

DATA = "D:/DeTaiAI/datasets"
HZ = 10.0
GRACE = 30.0
MATCH_BEFORE, MATCH_AFTER = 0.5, 2.0  # = fall_v2.MATCH_BEFORE_S / MATCH_AFTER_S
CROP = 0.6  # ghép 2 người: lấy 60% giữa mỗi khung hình
MAX_PEOPLE_SAVED = 3

FIELDS = ["name", "main", "other", "side", "loai", "fall_start_s", "fall_end_s", "nguoi"]


# ------------------------------------------------------------------ danh sách bài thử


def cmd_lists(out_dir):
    os.makedirs(out_dir, exist_ok=True)
    gmd = list(csv.DictReader(open(f"{DATA}/gmdcsa24/labels.csv", encoding="utf-8-sig")))
    rows = [dict(name=r["video"][:-4], main=f"{DATA}/gmdcsa24/videos/{r['video']}", other="", side="",
                 loai=r["loai"], fall_start_s=r["fall_start_s"], fall_end_s=r["fall_end_s"], nguoi=r["nguoi"])
            for r in gmd]
    _write(f"{out_dir}/gmd.csv", rows)

    import fall_v2 as fv
    root = f"{DATA}/caucafall/CAUCAFall"
    folder_of = {os.path.splitext(n)[0]: d for d, _, fs in os.walk(root) for n in fs if n.lower().endswith(".avi")}
    rows = []
    for s in fv.load_caucafall(f"{DATA}/caucafall/pose", root):
        stem = s.name[len("cauca-"):]
        rows.append(dict(name=s.name, main=os.path.join(folder_of[stem], stem + ".avi").replace("\\", "/"), other="",
                         side="", loai="fall" if s.is_fall else "adl",
                         fall_start_s=s.fall_start_s if s.is_fall else "", fall_end_s=s.fall_end_s if s.is_fall else "",
                         nguoi=s.group))
    _write(f"{out_dir}/cauca.csv", rows)

    ch = list(csv.DictReader(open(f"{DATA}/charades/labels.csv", encoding="utf-8-sig")))
    rows = [dict(name=r["video"][:-4], main=f"{DATA}/charades/videos/{r['video']}", other="", side="", loai="adl",
                 fall_start_s="", fall_end_s="", nguoi=r["nguoi"]) for r in ch]
    _write(f"{out_dir}/charades.csv", rows)

    falls = [r for r in gmd if r["loai"] == "fall"]
    adls = [r for r in gmd if r["loai"] == "adl"]
    rows = []
    for i, f in enumerate(falls):  # ngã + sinh hoạt của 1 người KHÁC
        cands = [a for a in adls if a["nguoi"] != f["nguoi"]]
        a = cands[(i * 7) % len(cands)]
        rows.append(dict(name=f"ghep_nga_{i:02d}", main=f"{DATA}/gmdcsa24/videos/{f['video']}",
                         other=f"{DATA}/gmdcsa24/videos/{a['video']}", side="left" if i % 2 == 0 else "right",
                         loai="fall", fall_start_s=f["fall_start_s"], fall_end_s=f["fall_end_s"],
                         nguoi=f"{f['nguoi']}+{a['nguoi']}"))
    for j, a in enumerate(adls):  # sinh hoạt + sinh hoạt
        cands = [b for b in adls if b["nguoi"] != a["nguoi"]]
        b = cands[(j * 11 + 5) % len(cands)]
        rows.append(dict(name=f"ghep_sh_{j:02d}", main=f"{DATA}/gmdcsa24/videos/{a['video']}",
                         other=f"{DATA}/gmdcsa24/videos/{b['video']}", side="left" if j % 2 == 0 else "right",
                         loai="adl", fall_start_s="", fall_end_s="", nguoi=f"{a['nguoi']}+{b['nguoi']}"))
    _write(f"{out_dir}/ghep.csv", rows)
    print("xong:", {n: len(list(csv.DictReader(open(f"{out_dir}/{n}.csv", encoding="utf-8"))))
                    for n in ("gmd", "cauca", "charades", "ghep")})


def _write(path, rows):
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, FIELDS)
        w.writeheader()
        w.writerows(rows)


def _rows(path, shard=0, shards=1):
    rows = list(csv.DictReader(open(path, encoding="utf-8")))
    return [r for i, r in enumerate(rows) if i % shards == shard]


# ------------------------------------------------------------------ trích khung xương 10 lần/giây


def sampled(path):
    """(t, frame) theo thời gian, 10 lần/giây — cùng cách lấy mẫu với fall_v2.resample."""
    import cv2

    cap = cv2.VideoCapture(path)
    fps = cap.get(cv2.CAP_PROP_FPS) or 30.0
    fps = fps if fps > 1 else 30.0
    i = k = 0
    try:
        while True:
            ok, frame = cap.read()
            if not ok:
                break
            if i == math.floor(k * fps / HZ + 1e-6):
                yield i / fps, frame
                while math.floor(k * fps / HZ + 1e-6) <= i:
                    k += 1
            i += 1
    finally:
        cap.release()


def _crop(frame):
    import cv2

    h, w = frame.shape[:2]
    c = int(w * (1 - CROP) / 2)
    part = frame[:, c:w - c]
    return cv2.resize(part, (int(part.shape[1] * 360 / h), 360))


def frames_for(row):
    """Khung hình đưa vào nhận diện: clip thường (thu về rộng 640), hoặc ghép 2 người."""
    import cv2

    if not row["other"]:
        for t, f in sampled(row["main"]):
            if f.shape[1] > 640:
                f = cv2.resize(f, (640, int(f.shape[0] * 640 / f.shape[1])))
            yield t, f
        return
    other = [(t, _crop(f)) for t, f in sampled(row["other"])]
    dur = other[-1][0] + 1 / HZ
    for t, f in sampled(row["main"]):
        o = other[min(len(other) - 1, int((t % dur) * HZ))][1]
        m = _crop(f)
        img = np.hstack([m, o] if row["side"] == "left" else [o, m])
        yield t, cv2.resize(img, (640, int(img.shape[0] * 640 / img.shape[1])))


def cmd_extract(mode, list_csv, out_dir, shard="0", shards="1"):
    import cv2

    os.makedirs(out_dir, exist_ok=True)
    for row in _rows(list_csv, int(shard), int(shards)):
        target = os.path.join(out_dir, row["name"] + ".npz")
        if os.path.exists(target):
            continue
        if mode == "single":
            from mediapipe.python import solutions as mp_solutions

            pose = mp_solutions.pose.Pose()  # đúng cấu hình app (detection_engine.get_mediapipe)

            def detect(rgb, _t):
                r = pose.process(rgb)
                return [[[p.x, p.y, p.z, p.visibility] for p in r.pose_landmarks.landmark]] if r.pose_landmarks else []
        else:
            import multi_person

            pose = multi_person.MultiPoseDetector()

            def detect(rgb, t):
                return pose.detect(rgb, t)
        times, poses, ms = [], [], []
        for t, frame in frames_for(row):
            rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            t0 = time.perf_counter()
            people = detect(rgb, t)
            ms.append((time.perf_counter() - t0) * 1000)
            arr = np.full((MAX_PEOPLE_SAVED, 33, 4), np.nan, np.float32)
            for j, p in enumerate(people[:MAX_PEOPLE_SAVED]):
                arr[j] = p
            times.append(t)
            poses.append(arr)
        pose.close()
        tmp = target + ".tmp.npz"
        np.savez_compressed(tmp, poses=np.asarray(poses, np.float32).reshape(-1, MAX_PEOPLE_SAVED, 33, 4),
                            times=np.asarray(times), ms=np.asarray(ms, np.float32))
        os.replace(tmp, target)
        print(row["name"], len(times), flush=True)


# ------------------------------------------------------------------ phát lại vào app


class _Clock:
    t = 1_000_000.0

    def time(self):
        return self.t


class _ReplayPose:
    """Thay MediaPipe: trả đúng khung xương đã trích cho frame hiện tại (dạng legacy hoặc danh sách)."""

    def __init__(self):
        self.people = []

    def process(self, _rgb):
        if not self.people:
            return types.SimpleNamespace(pose_landmarks=None)
        pts = [types.SimpleNamespace(x=p[0], y=p[1], z=p[2], visibility=p[3]) for p in self.people[0]]
        return types.SimpleNamespace(pose_landmarks=types.SimpleNamespace(landmark=pts))

    def detect(self, _rgb, _now):
        return self.people


def cmd_replay(mode, version, list_csv, pose_dir, out_json, shard="0", shards="1"):
    import av

    import detection_engine as engine
    import event_log
    import multi_person
    import webrtc_processor

    engine.FALL_V2_MODEL_PATH = os.path.join(ROOT, "models", f"fall_v2_{version}.keras")
    engine.FALL_V2_META_PATH = os.path.join(ROOT, "models", f"fall_v2_{version}_meta.json")
    model = engine.FallV2Model()
    clock = _Clock()
    webrtc_processor.time = types.SimpleNamespace(time=clock.time)
    engine.WARMUP_FRAMES = 0
    webrtc_processor.DetectionVideoProcessor.PROCESS_EVERY_N_FRAMES = 1
    fd, db = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    event_log.DB_PATH = db
    config = {"enable_fall": True, "enable_hand": False, "enable_signal": False, "fall_grace_seconds": GRACE,
              "hand_confidence_threshold": 0.8, "signal_confidence_threshold": 0.7, "mirror_camera": False,
              "alert_hold_seconds": 2.0, "show_overlay": False}
    frame = av.VideoFrame.from_ndarray(np.zeros((48, 64, 3), dtype=np.uint8), format="bgr24")
    results = {}
    for row in _rows(list_csv, int(shard), int(shards)):
        path = os.path.join(pose_dir, row["name"] + ".npz")
        if not os.path.exists(path):
            continue
        d = np.load(path)
        poses, times = d["poses"], d["times"]
        replay = _ReplayPose()
        p = webrtc_processor.DetectionVideoProcessor(
            model, None, None, replay, None, config, multi_detector=replay if mode == "multi" else None)
        base = clock.t = clock.t + 10_000
        episodes, prev_down, prev_esc = [], None, False
        for t, frame_people in zip(times, poses):
            clock.t = base + float(t)
            replay.people = [x.tolist() for x in frame_people if not np.isnan(x[0, 0])]
            p.recv(frame)
            if p.fall_down_since is not None and prev_down is None:
                if p.people is not None:
                    xs = [x for _pid, x in [(q.id, q.center[0]) for q in p.people.down()]]
                elif p.last_landmarks is not None:
                    xs = [multi_person.center(p.last_landmarks)[0]]
                else:
                    xs = []
                episodes.append({"t": p.fall_down_since - base, "x": xs, "sent": False,
                                 "vanish": bool(p.vanish_suspected)})
            if p.fall_escalated and not prev_esc and episodes:
                episodes[-1]["sent"] = True
            prev_down, prev_esc = p.fall_down_since, p.fall_escalated
        if p.fall_down_since is not None and episodes and not p.fall_escalated:
            episodes[-1]["sent"] = True  # clip hết khi vẫn đang chờ xác minh -> tính là CÓ gửi (bất lợi cho mình)
            episodes[-1]["clip_end"] = True
        results[row["name"]] = {**row, "duration": float(times[-1]) + 1 / HZ if len(times) else 0.0,
                                "episodes": episodes, "ms": float(np.median(d["ms"])) if len(d["ms"]) else 0.0,
                                "people": float(np.mean([(~np.isnan(x[:, 0, 0])).sum() for x in poses])) if len(poses) else 0.0}
    os.makedirs(os.path.dirname(os.path.abspath(out_json)), exist_ok=True)
    json.dump(results, open(out_json, "w", encoding="utf-8"))
    print(f"{out_json}: {len(results)} clip")


# ------------------------------------------------------------------ báo cáo


def summarize(results):
    falls = caught = caught_sent = right_person = 0
    hours = adl_det = adl_sent = 0.0
    for r in results.values():
        if r["loai"] == "fall":
            falls += 1
            lo, hi = float(r["fall_start_s"]) - MATCH_BEFORE, float(r["fall_end_s"]) + MATCH_AFTER
            hits = [e for e in r["episodes"] if lo <= e["t"] <= hi]
            if hits:
                caught += 1
                caught_sent += hits[0]["sent"]
                if r["other"]:
                    want_left = r["side"] == "left"
                    right_person += any((x < 0.5) == want_left for x in hits[0]["x"])
        else:
            hours += r["duration"] / 3600
            adl_det += len(r["episodes"])
            adl_sent += sum(e["sent"] for e in r["episodes"])
    ms = [r["ms"] for r in results.values()]
    people = [r["people"] for r in results.values()]
    return {"falls": falls, "caught": caught, "caught_sent": caught_sent, "right_person": right_person,
            "adl_hours": hours, "adl_det_h": adl_det / hours if hours else None,
            "adl_sent_h": adl_sent / hours if hours else None, "ms": float(np.median(ms)) if ms else None,
            "people": float(np.mean(people)) if people else None, "n": len(results)}


def cmd_report(*paths):
    merged = {}
    for pattern in paths:
        for path in sorted(glob.glob(pattern)):
            key = re.sub(r"\.s\d+$", "", os.path.basename(path)[:-len(".json")])  # gmd_single.s3.json -> gmd_single
            merged.setdefault(key, {}).update(json.load(open(path, encoding="utf-8")))
    for key, results in merged.items():
        s = summarize(results)
        line = f"{key:28s} {s['n']:4d} clip | ngã bắt được {s['caught']}/{s['falls']} (gửi {s['caught_sent']})"
        if s["right_person"]:
            line += f", đúng người {s['right_person']}"
        if s["adl_hours"]:
            line += f" | sinh hoạt {s['adl_hours']:.2f} giờ: theo dõi {s['adl_det_h']:.1f}/giờ, GỬI {s['adl_sent_h']:.1f}/giờ"
        line += f" | {s['ms']:.0f} ms/frame, TB {s['people']:.2f} người/frame"
        print(line)


COMMANDS = {"lists": cmd_lists, "extract": cmd_extract, "replay": cmd_replay, "report": cmd_report}

if __name__ == "__main__":
    if len(sys.argv) < 2 or sys.argv[1] not in COMMANDS:
        sys.exit(__doc__)
    COMMANDS[sys.argv[1]](*sys.argv[2:])

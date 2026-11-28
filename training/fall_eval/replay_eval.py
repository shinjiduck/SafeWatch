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

FIELDS = ["name", "main", "other", "side", "loai", "fall_start_s", "fall_end_s", "nguoi", "nhom"]
OFSYN_ATTRS = ["camera_elevation", "camera_azimuth", "camera_distance", "environment_category", "age_group"]
OFSYN_MIN_LEAD = 1.0  # clip ngã phải có >= 1 s trước cú ngã (82% clip OF-Syn mở ra giữa lúc đang ngã)


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
    names = ["gmd", "cauca", "charades", "ghep"]
    if os.path.exists(f"{DATA}/omnifall/labels/of-syn.csv"):
        _write(f"{out_dir}/ofsyn.csv", ofsyn_rows())
        names.append("ofsyn")
    if os.path.isdir(f"{DATA}/le2i") and os.path.exists(f"{DATA}/omnifall/labels/le2i.csv"):
        _write(f"{out_dir}/le2i.csv", le2i_rows())
        names.append("le2i")
    print("xong:", {n: len(list(csv.DictReader(open(f"{out_dir}/{n}.csv", encoding="utf-8")))) for n in names})


def le2i_rows():
    """Le2i (Charfi et al. 2013; 9 người, 6 phòng = 6 góc camera / ánh sáng). Nhãn từ OmniFall (le2i.csv).
    Cùng quy tắc với OF-Syn: ngã cần >= OFSYN_MIN_LEAD s trước cú ngã; sinh hoạt = không có nhãn 1 / 2."""
    files = {}
    for d, _, fs in os.walk(f"{DATA}/le2i"):
        room = os.path.relpath(d, f"{DATA}/le2i").replace("\\", "/").split("/")[0]
        for n in fs:
            m = re.fullmatch(r"video \((\d+)\)\.avi", n)
            if m:
                files[(room, int(m.group(1)))] = os.path.join(d, n).replace("\\", "/")
    segs = {}
    for r in csv.DictReader(open(f"{DATA}/omnifall/labels/le2i.csv", encoding="utf-8")):
        segs.setdefault(r["path"], []).append(r)
    rows, missing = [], 0
    for path, ss in sorted(segs.items()):
        room, vid = path.split("/")
        main = files.get((room, int(vid.split("_")[1])))
        if main is None:
            missing += 1
            continue
        labels = {x["label"] for x in ss}
        base = dict(name=f"le2i_{room}_{vid}", main=main, other="", side="", nguoi=f"le2i-{ss[0]['subject']}",
                    nhom=f"phong={room};nguoi={ss[0]['subject']}")
        if "1" in labels:
            f = min((x for x in ss if x["label"] == "1"), key=lambda x: float(x["start"]))
            start, end = float(f["start"]), float(f["end"])
            if start >= OFSYN_MIN_LEAD:
                rows.append(dict(base, loai="fall", fall_start_s=start, fall_end_s=min(end, start + 1.5)))
        elif "2" not in labels:
            rows.append(dict(base, loai="adl", fall_start_s="", fall_end_s=""))
    if missing:
        print(f"le2i: thiếu {missing} video so với nhãn")
    return rows


def ofsyn_rows():
    """OF-Syn (OmniFall, video tổng hợp, CC BY-NC-SA): góc camera ghi sẵn cho từng clip.
    Ngã = clip có đoạn nhãn 1 (fall) bắt đầu >= OFSYN_MIN_LEAD s; pha rơi = [start, min(end, start + 1.5)].
    Sinh hoạt = clip không có nhãn 1 (fall) hay 2 (fallen). Còn lại (ngã ngay từ đầu clip, đã nằm sẵn) bỏ."""
    segs = {}
    for r in csv.DictReader(open(f"{DATA}/omnifall/labels/of-syn.csv", encoding="utf-8")):
        segs.setdefault(r["path"], []).append(r)
    rows = []
    for path, ss in sorted(segs.items()):
        labels = {s["label"] for s in ss}
        nhom = ";".join(f"{a}={ss[0][a]}" for a in OFSYN_ATTRS)
        base = dict(name="ofsyn_" + path.replace("/", "_"), main=f"{DATA}/omnifall/syn/{path}.mp4", other="", side="",
                    nguoi="ofsyn", nhom=nhom)
        if "1" in labels:
            f = min((s for s in ss if s["label"] == "1"), key=lambda s: float(s["start"]))
            start, end = float(f["start"]), float(f["end"])
            if start >= OFSYN_MIN_LEAD:
                rows.append(dict(base, loai="fall", fall_start_s=start, fall_end_s=min(end, start + 1.5)))
        elif "2" not in labels and path.split("/")[0] not in ("fall", "fallen"):  # thư mục ngã mà thiếu nhãn: mơ hồ, bỏ
            rows.append(dict(base, loai="adl", fall_start_s="", fall_end_s=""))
    return rows


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


def occlude(img):
    """Che vật cản giả lập: biến môi trường REPLAY_OCCLUDE = "<vùng>:<tỉ lệ>", vùng = b (cả dải dưới), bl / br / tl / tr
    (1 góc). VD "b:0.4" = tô đen 40% chiều cao phía dưới (như giường / sofa chắn trước)."""
    spec = os.environ.get("REPLAY_OCCLUDE")
    if not spec:
        return img
    where, frac = spec.split(":")
    h, w = img.shape[:2]
    ch, cw = int(h * float(frac)), int(w * float(frac))
    y0 = 0 if where[0] == "t" else h - ch
    x0, cw = (0, w) if len(where) == 1 else (0 if where[1] == "l" else w - cw, cw)
    img = img.copy()
    img[y0:y0 + ch, x0:x0 + cw] = 0
    return img


def frames_for(row):
    """Khung hình đưa vào nhận diện: clip thường (thu về rộng 640), hoặc ghép 2 người; có thể che vật cản (occlude)."""
    for t, f in _frames_for(row):
        yield t, occlude(f)


def _frames_for(row):
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
        duration = float(times[-1]) + 1 / HZ if len(times) else 0.0
        hold = float(os.environ.get("REPLAY_GIU_CUOI", "0") or 0)  # giữ khung xương cuối thêm N giây (người nằm / đứng yên)
        if hold > 0 and len(times):
            n = int(round(hold * HZ))
            times = np.concatenate([times, times[-1] + np.arange(1, n + 1) / HZ])
            poses = np.concatenate([poses, np.repeat(poses[-1:], n, axis=0)])
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
                episodes[-1]["t_sent"] = clock.t - base
            prev_down, prev_esc = p.fall_down_since, p.fall_escalated
        if p.fall_down_since is not None and episodes and not p.fall_escalated:
            episodes[-1]["sent"] = True  # clip hết khi vẫn đang chờ xác minh -> tính là CÓ gửi (bất lợi cho mình)
            episodes[-1]["clip_end"] = True
        results[row["name"]] = {**row, "duration": duration, "giu_cuoi_s": hold,
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


def cmd_breakdown(path, attr):
    """Tách kết quả theo 1 thuộc tính trong cột nhom (VD camera_elevation) — bộ OF-Syn."""
    results = json.load(open(path, encoding="utf-8"))
    groups = {}
    for k, r in results.items():
        tags = dict(x.split("=", 1) for x in (r.get("nhom") or "").split(";") if "=" in x)
        groups.setdefault(tags.get(attr, "?"), {})[k] = r
    print(f"{path} theo {attr}:")
    for g, rs in sorted(groups.items()):
        s = summarize(rs)
        n_adl = sum(1 for r in rs.values() if r["loai"] == "adl")
        n_fp = sum(1 for r in rs.values() if r["loai"] == "adl" and r["episodes"])
        print(f"  {g:22s} ngã bắt được {s['caught']}/{s['falls']} | clip sinh hoạt bị nghi ngã {n_fp}/{n_adl}"
              + (f" ({n_fp / n_adl * 100:.1f}%)" if n_adl else ""))


COMMANDS = {"lists": cmd_lists, "extract": cmd_extract, "replay": cmd_replay, "report": cmd_report,
            "breakdown": cmd_breakdown}

if __name__ == "__main__":
    if len(sys.argv) < 2 or sys.argv[1] not in COMMANDS:
        sys.exit(__doc__)
    COMMANDS[sys.argv[1]](*sys.argv[2:])

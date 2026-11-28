"""Đo tốc độ xử lý khung hình của SafeWatch bằng ĐÚNG bộ xử lý của app (DetectionVideoProcessor, MediaPipe thật,
model thật), trên video thật, giả lập camera 30 khung/giây.

Mỗi lần chạy đo 1 cấu hình, in 1 dòng JSON:
  - ai_ms_*      : thời gian 1 khung CÓ chạy AI (trung vị, 90%, chậm nhất)
  - bo_qua_ms    : thời gian 1 khung KHÔNG chạy AI (2/3 số khung)
  - fps_hien_thi : số khung trả về màn hình mỗi giây khi camera gửi 30 khung/giây (khung đến lúc đang bận thì bị
                   bỏ, giống hàng đợi 1 khung của app)
  - nhip_ai_hz   : số lần AI chạy mỗi giây (mục tiêu 10, model được huấn luyện ở 10 Hz)
  - tung_buoc_ms : thời gian trung bình từng bước trong 1 khung có AI
  - ram_mb, cpu_phan_tram (100% = 1 lõi)

Chạy (trong training/perf):
  python -X utf8 -I do_toc_do.py <video> [do_phan_giai=640x480] [cau_hinh=mac_dinh] [lop=1]
cau_hinh: mac_dinh | chi_nga | loc_sos | tay_xa | nhieu_nguoi | signal | day_du
lop=1   : giả lập máy chủ yếu (chỉ cho dùng 1 lõi CPU, như máy chủ dùng chung trên Cloud)
  python -X utf8 -I do_toc_do.py bao_mat      -> đo phần đăng nhập, mã hoá, kiểm tra quyền riêng tư
"""

import json
import os
import statistics
import sys
import tempfile
import time

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, ROOT)
os.environ.setdefault("TF_CPP_MIN_LOG_LEVEL", "3")

CAMERA_FPS = 30.0
SECONDS = 30.0  # thời lượng giả lập

CONFIGS = {
    "mac_dinh": {},
    "chi_nga": {"enable_hand": False},
    "loc_sos": {"sos_filter": True},
    "tay_xa": {"hand_roi": True},
    "nhieu_nguoi": {"multi_person": True},
    "signal": {"enable_signal": True},
    "day_du": {"sos_filter": True, "hand_roi": True, "multi_person": True, "enable_signal": True},
}


def _one_core():
    """Chỉ cho tiến trình dùng 1 lõi CPU (Windows / Linux) — gọi TRƯỚC khi nạp TensorFlow / MediaPipe."""
    os.environ["TF_NUM_INTRAOP_THREADS"] = os.environ["TF_NUM_INTEROP_THREADS"] = "1"
    os.environ["OMP_NUM_THREADS"] = "1"
    if os.name == "nt":
        import ctypes

        from ctypes import wintypes

        k = ctypes.windll.kernel32
        k.GetCurrentProcess.restype = wintypes.HANDLE
        k.SetProcessAffinityMask.argtypes = [wintypes.HANDLE, ctypes.c_size_t]
        if not k.SetProcessAffinityMask(k.GetCurrentProcess(), 1):
            raise OSError("không đặt được 1 lõi CPU")
    else:
        os.sched_setaffinity(0, {0})


def _ram_mb():
    if os.name == "nt":
        import ctypes
        from ctypes import wintypes

        class PMC(ctypes.Structure):
            _fields_ = [("cb", wintypes.DWORD), ("PageFaultCount", wintypes.DWORD),
                        ("PeakWorkingSetSize", ctypes.c_size_t), ("WorkingSetSize", ctypes.c_size_t),
                        ("QuotaPeakPagedPoolUsage", ctypes.c_size_t), ("QuotaPagedPoolUsage", ctypes.c_size_t),
                        ("QuotaPeakNonPagedPoolUsage", ctypes.c_size_t), ("QuotaNonPagedPoolUsage", ctypes.c_size_t),
                        ("PagefileUsage", ctypes.c_size_t), ("PeakPagefileUsage", ctypes.c_size_t)]

        pmc = PMC()
        pmc.cb = ctypes.sizeof(PMC)
        k32, psapi = ctypes.windll.kernel32, ctypes.windll.psapi
        k32.GetCurrentProcess.restype = wintypes.HANDLE
        psapi.GetProcessMemoryInfo.argtypes = [wintypes.HANDLE, ctypes.POINTER(PMC), wintypes.DWORD]
        psapi.GetProcessMemoryInfo(k32.GetCurrentProcess(), ctypes.byref(pmc), pmc.cb)
        return pmc.WorkingSetSize / 2 ** 20
    import resource

    return resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024


def _q(xs, k):
    xs = sorted(xs)
    return xs[min(len(xs) - 1, int(k * (len(xs) - 1)))] if xs else None


def bench_video(video, resolution="640x480", config_name="mac_dinh", one_core="0"):
    if one_core == "1":
        _one_core()
    import av
    import cv2

    import detection_engine as engine
    import event_log
    import hand_roi
    import multi_person
    import notifier
    import webrtc_processor

    fd, db = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    event_log.DB_PATH = db
    notifier.raise_alert = lambda *a, **k: None  # không gửi cảnh báo thật

    w, h = (int(x) for x in resolution.split("x"))
    cfg = dict(engine.SETTINGS_DEFAULTS)
    cfg.update(CONFIGS[config_name])
    cfg["show_overlay"] = True

    # --- đo từng bước: bọc các hàm nặng bằng bộ đếm thời gian
    stage = {}

    def timed(name, fn):
        def wrap(*a, **k):
            t0 = time.perf_counter()
            try:
                return fn(*a, **k)
            finally:
                stage[name] = stage.get(name, 0.0) + (time.perf_counter() - t0) * 1000
        return wrap

    from mediapipe.python import solutions as mp_solutions

    fall = engine.FallV2Model()
    fall.prob = timed("mo_hinh_nga", fall.prob)
    hand = engine.build_hand_model()
    signal = engine.build_signal_model() if cfg["enable_signal"] else None
    engine.predict_hand = timed("mo_hinh_cu_chi", engine.predict_hand)
    engine.predict_signal_sequence = timed("mo_hinh_signal", engine.predict_signal_sequence)
    hand_roi.detect = timed("tim_tay_o_xa", hand_roi.detect)
    pose = mp_solutions.pose.Pose()
    hands = mp_solutions.hands.Hands(static_image_mode=False, max_num_hands=1, min_detection_confidence=0.5)
    pose.process = timed("tim_khung_xuong", pose.process)
    hands.process = timed("tim_ban_tay", hands.process)
    multi = None
    if cfg["multi_person"]:
        multi = multi_person.MultiPoseDetector()
        multi.detect = timed("tim_nhieu_nguoi", multi.detect)
    engine.warm_up_models(fall, hand, signal)
    p = webrtc_processor.DetectionVideoProcessor(fall, hand, signal, pose, hands, cfg, multi_detector=multi)

    cap = cv2.VideoCapture(video)
    frames = []
    while len(frames) < 450:
        ok, f = cap.read()
        if not ok:
            break
        frames.append(av.VideoFrame.from_ndarray(cv2.resize(f, (w, h)), format="bgr24"))
    cap.release()

    # --- giả lập camera 30 khung/giây, hàng đợi 1 khung: đang bận thì khung mới đến thay khung cũ
    interval = 1 / CAMERA_FPS
    vt, out, ai_count = 0.0, 0, 0
    ai_ms, skip_ms, per_stage = [], [], []
    cpu0, wall0 = time.process_time(), time.perf_counter()
    warm = engine.WARMUP_FRAMES + 30
    while vt < SECONDS + warm * interval:
        idx = int(vt / interval)
        frame = frames[idx % len(frames)]
        stage.clear()
        before = p.frame_count
        t0 = time.perf_counter()
        p.recv(frame)
        dt = time.perf_counter() - t0
        is_ai = p.frame_count > engine.WARMUP_FRAMES and p.frame_count % p.PROCESS_EVERY_N_FRAMES == 0
        if before >= warm:
            out += 1
            if is_ai:
                ai_count += 1
                ai_ms.append(dt * 1000)
                per_stage.append(dict(stage))
            else:
                skip_ms.append(dt * 1000)
        vt = max(vt + dt, (idx + 1) * interval)  # xong việc thì chờ khung kế tiếp
    cpu = (time.process_time() - cpu0) / (time.perf_counter() - wall0) * 100
    keys = sorted({k for s in per_stage for k in s})
    return {
        "do_phan_giai": resolution, "cau_hinh": config_name, "may": "1 lõi" if one_core == "1" else "laptop",
        "ai_ms_trung_vi": round(statistics.median(ai_ms), 1), "ai_ms_90": round(_q(ai_ms, .9), 1),
        "ai_ms_cham_nhat": round(max(ai_ms), 1), "bo_qua_ms": round(statistics.median(skip_ms), 2),
        "fps_hien_thi": round(out / SECONDS, 1), "nhip_ai_hz": round(ai_count / SECONDS, 1),
        "tung_buoc_ms": {k: round(sum(s.get(k, 0) for s in per_stage) / len(per_stage), 1) for k in keys},
        "ram_mb": round(_ram_mb()), "cpu_phan_tram": round(cpu),
    }


def bench_security():
    """Chi phí của phần đăng nhập / mã hoá / quyền riêng tư mới thêm (đo trên CSDL tạm)."""
    from cryptography.fernet import Fernet

    os.environ["SAFEWATCH_DATA_KEY"] = Fernet.generate_key().decode()
    import auth
    import event_log
    import privacy
    import profile_store
    import secure_store

    d = tempfile.mkdtemp()
    event_log.DB_PATH = os.path.join(d, "e.db")
    import contacts

    contacts.DB_PATH = event_log.DB_PATH
    profile_store.PROFILE_PATH = os.path.join(d, "p.json")
    privacy.init_all()

    def ms(fn, n):
        t0 = time.perf_counter()
        for _ in range(n):
            fn()
        return round((time.perf_counter() - t0) * 1000 / n, 3)

    h = auth.hash_secret("Hoa-sen-2026")
    uid, _ = auth.create_user("lan", "Lan", auth.ROLE_CAREGIVER, "Hoa-sen-2026")
    enc = secure_store.encrypt("0912345678")
    return {
        "bam_mat_khau_ms": ms(lambda: auth.hash_secret("Hoa-sen-2026"), 5),
        "kiem_mat_khau_ms": ms(lambda: auth.verify_secret("Hoa-sen-2026", h), 5),
        "dang_nhap_ms": ms(lambda: auth.authenticate("lan", "Hoa-sen-2026"), 5),
        "doc_tai_khoan_moi_lan_chay_trang_ms": ms(lambda: auth.get_user(uid), 200),
        "kiem_tra_dong_y_va_tam_dung_ms (trang Trực tiếp, mỗi giây 1 lần)":
            ms(lambda: (privacy.active_consent(), privacy.pause_until()), 200),
        "ma_hoa_1_truong_ms": ms(lambda: secure_store.encrypt("0912345678"), 500),
        "giai_ma_1_truong_ms": ms(lambda: secure_store.decrypt(enc), 500),
    }


if __name__ == "__main__":
    if len(sys.argv) < 2:
        sys.exit(__doc__)
    if sys.argv[1] == "bao_mat":
        print(json.dumps(bench_security(), ensure_ascii=False))
    else:
        print(json.dumps(bench_video(*sys.argv[1:]), ensure_ascii=False))

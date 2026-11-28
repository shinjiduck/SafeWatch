"""Thông tin phiên bản — MỘT nguồn cho 3 nơi, để tài liệu không lệch khỏi code:

  - trang "Thông tin phiên bản" trong app (views/version.py)
  - bảng cấu hình trình diễn:  python -X utf8 version_info.py   (in bảng Markdown, dán vào tài liệu)
  - test đối chiếu tài liệu:   tests/test_dong_bo_tai_lieu.py   (README / landing ghi khác code -> test đỏ)

Thông số đọc thẳng từ hằng số trong code (không chép tay). Số kiểm định là kết quả đo, không suy ra được từ code,
nên ghi 1 lần ở KET_QUA kèm tên dữ liệu và tài liệu gốc.
"""

import filecmp
import json
import os
import re

import detection_engine as engine
import notifier
import webrtc_processor

ROOT = os.path.dirname(os.path.abspath(__file__))


# ------------------------------------------------------------------ commit đang chạy


def commit():
    """Mã commit ngắn đang chạy (đọc thẳng .git, không cần lệnh git). Không có .git -> biến môi trường
    SAFEWATCH_COMMIT, không có nữa -> None."""
    git = os.path.join(ROOT, ".git")
    try:
        head = open(os.path.join(git, "HEAD"), encoding="utf-8").read().strip()
        if not head.startswith("ref: "):
            return head[:7]
        ref = head[5:]
        path = os.path.join(git, *ref.split("/"))
        if os.path.exists(path):
            return open(path, encoding="utf-8").read().strip()[:7]
        packed = os.path.join(git, "packed-refs")
        for line in open(packed, encoding="utf-8"):
            if line.strip().endswith(" " + ref):
                return line.split()[0][:7]
    except OSError:
        pass
    return os.environ.get("SAFEWATCH_COMMIT") or None


# ------------------------------------------------------------------ model


def fall_model():
    """Model ngã app đang nạp: tên phiên bản (so khớp với các bản lưu trong models/) + thông số trong meta."""
    meta = json.load(open(engine.FALL_V2_META_PATH, encoding="utf-8"))
    name = None
    models = os.path.join(ROOT, "models")
    for f in sorted(os.listdir(models)):
        m = re.fullmatch(r"fall_v2_(.+)\.keras", f)
        if m and filecmp.cmp(os.path.join(models, f), engine.FALL_V2_MODEL_PATH, shallow=False):
            name = m.group(1)
            break
    return {"ten": name or "không rõ", "cua_so": int(meta["window"]), "hz": float(meta["process_hz"]),
            "nguong": float(meta["threshold"]), "lien_tiep": int(meta.get("consecutive", engine.FALL_V2_CONSECUTIVE))}


# ------------------------------------------------------------------ thông số


def _where(module, name):
    """'file.py:dòng' nơi khai báo hằng số name trong module (để người đọc mở đúng chỗ)."""
    path = module.__file__
    pat = re.compile(rf"^\s*{re.escape(name)}\s*=")
    for i, line in enumerate(open(path, encoding="utf-8"), 1):
        if pat.match(line):
            return f"{os.path.basename(path)}:{i}"
    return os.path.basename(path)


def _s(x):
    return f"{x:g}"


def thong_so():
    """[(nhóm, tên, giá trị, nơi khai báo)] — thông số của bản chạy mặc định."""
    m = fall_model()
    d = engine.SETTINGS_DEFAULTS
    return [
        ("Phát hiện ngã", "Model ngã", f"v2 `{m['ten']}` (Conv1D + GRU)", "models/MODEL_VERSIONS.md"),
        ("Phát hiện ngã", "Cửa sổ khung xương", f"{m['cua_so']} khung ở {_s(m['hz'])} Hz = {_s(m['cua_so'] / m['hz'])} s",
         "models/fall_v2_meta.json"),
        ("Phát hiện ngã", "Ngưỡng xác suất ngã", _s(m["nguong"]), "models/fall_v2_meta.json"),
        ("Phát hiện ngã", "Số lần liên tiếp vượt ngưỡng", str(m["lien_tiep"]), "models/fall_v2_meta.json"),
        ("Phát hiện ngã", "Thân thẳng liên tục bao lâu thì tính là đã dậy",
         f"{_s(engine.FALL_V2_RECOVER_SECONDS)} s", _where(engine, "FALL_V2_RECOVER_SECONDS")),
        ("Phát hiện ngã", "Thời gian xác minh sau ngã (người tự dậy thì huỷ)",
         f"{_s(engine.DEFAULT_FALL_GRACE_SECONDS)} s (chỉnh 5–300 s)", _where(engine, "DEFAULT_FALL_GRACE_SECONDS")),
        ("Cử chỉ tay", "Ngưỡng tin cậy cử chỉ", f"{engine.DEFAULT_HAND_CONFIDENCE_THRESHOLD:.0%}",
         _where(engine, "DEFAULT_HAND_CONFIDENCE_THRESHOLD")),
        ("Cử chỉ tay", "Giữ cử chỉ SOS khi bật bộ lọc", f"{_s(webrtc_processor.DetectionVideoProcessor.SOS_HOLD_SECONDS)} s",
         _where(webrtc_processor, "SOS_HOLD_SECONDS")),
        ("Cảnh báo", "Thời gian chờ xác nhận (hết thì gửi lại + chuyển người kế tiếp)",
         f"{_s(notifier.ACK_TIMEOUT_SECONDS)} s", _where(notifier, "ACK_TIMEOUT_SECONDS")),
        ("Cảnh báo", "Số vòng tối đa", str(notifier.MAX_ROUNDS), _where(notifier, "MAX_ROUNDS")),
        ("Cảnh báo", "Gửi lỗi thì thử lại sau",
         ", ".join(_s(x) for x in notifier.RETRY_BACKOFF_SECONDS) + " s", _where(notifier, "RETRY_BACKOFF_SECONDS")),
        ("Camera", "Nhịp AI", f"1/{webrtc_processor.DetectionVideoProcessor.PROCESS_EVERY_N_FRAMES} khung "
         f"(≈ {_s(30 / webrtc_processor.DetectionVideoProcessor.PROCESS_EVERY_N_FRAMES)} Hz khi camera 30 khung/giây)",
         _where(webrtc_processor, "PROCESS_EVERY_N_FRAMES")),
        ("Camera", "Độ phân giải mặc định", str(d["camera_resolution"]), _where(engine, "SETTINGS_DEFAULTS")),
    ]


# (khoá cấu hình, tên, trạng thái khi bật, ghi chú). Trạng thái bật/tắt mặc định đọc từ SETTINGS_DEFAULTS.
TINH_NANG = [
    ("enable_fall", "Phát hiện ngã", "Đang dùng", ""),
    ("enable_hand", "Cử chỉ tay (14 nhãn, 3 nhãn cầu cứu)", "Đang dùng", ""),
    ("sos_filter", "Bộ lọc chống báo SOS nhầm (giơ tay cao hơn vai + giữ 2 s)", "Đang dùng",
     "Giảm báo nhầm 132 → 1,9 / giờ; độ nhạy chưa đo bằng video cử chỉ thật"),
    ("enable_signal", "Signal for Help theo chuỗi động tác", "Thử nghiệm", "Học từ 60 chuỗi, chưa đánh giá độc lập"),
    ("multi_person", "Theo dõi nhiều người", "Thử nghiệm", "Chưa đạt tiêu chí ghi trước khi thử"),
    ("hand_roi", "Nhận cử chỉ khi đứng xa", "Thử nghiệm", "Thấy tay nhiều hơn nhưng báo nhầm 132 → 184 / giờ"),
]


def tinh_nang():
    """[(tên, bật mặc định?, trạng thái, ghi chú)]"""
    return [(ten, bool(engine.SETTINGS_DEFAULTS[k]), tt, gc) for k, ten, tt, gc in TINH_NANG]


# ------------------------------------------------------------------ kết quả kiểm định (đo, không suy ra từ code)

# (bài thử, kết quả, dữ liệu / điều kiện, tài liệu gốc)
KET_QUA = [
    ("Phát hiện ngã — Le2i", "121/129 ca ngã (94%)",
     "Dữ liệu chưa từng dùng: 9 người, 6 phòng", "training/fall_eval/KIEM_DINH_THEO_YEU_CAU_BTC.md"),
    ("Ngã rồi nằm yên 40 s — Le2i", "Gửi cảnh báo 94/122 ca (trung vị 30,8 s sau cú ngã)",
     "21 ca bắt được nhưng bị coi nhầm là đã đứng dậy (nằm dọc hướng camera) — đã rõ nguyên nhân, chưa sửa",
     "training/fall_eval/results_kich_ban/"),
    ("Ngã sau vật cản — Le2i", "115 / 105 / 74 trên 129 khi che 20% / 30% / 40%",
     "Che giả lập dải dưới khung hình", "training/fall_eval/results_che_goc_tong_hop.md"),
    ("Báo ngã nhầm — Charades", "8 cảnh báo / giờ (model cũ: 61 / giờ)",
     "5 giờ sinh hoạt thật, ~500 nhà, không ai ngã", "training/fall_eval/KIEM_DINH_NHIEU_NGUOI.md"),
    ("Báo SOS nhầm — Charades", "132 / giờ khi tắt bộ lọc; 1,9 / giờ khi bật",
     "3,2 giờ sinh hoạt, không ai ra hiệu", "training/hand_eval/KIEM_DINH_TAY_XA.md"),
    ("Cử chỉ tay — 14 nhãn", "99,54% trên tập kiểm tra nội bộ",
     "Chia ngẫu nhiên theo khung hình (44.400 khung): khung liền nhau của cùng người nằm ở cả 2 tập nên số này cao hơn "
     "thực tế. Độ nhạy ngoài thực tế chưa đo", "training/retrain_extended_hand_model.py"),
    ("Chuỗi cảnh báo", "Trung vị 1,1 s từ lúc phát cảnh báo tới lúc gửi được", "52 cảnh báo thật",
     "Trang Cảnh báo → bảng thời gian"),
]


# ------------------------------------------------------------------ in bảng


def bang_markdown():
    out = [f"Commit: `{commit() or 'không rõ'}`", "", "| Nhóm | Thông số | Giá trị | Khai báo ở |", "|---|---|---|---|"]
    out += [f"| {a} | {b} | {c} | `{d}` |" for a, b, c, d in thong_so()]
    out += ["", "| Tính năng | Mặc định | Trạng thái | Ghi chú |", "|---|---|---|---|"]
    out += [f"| {a} | {'Bật' if b else 'Tắt'} | {c} | {d} |" for a, b, c, d in tinh_nang()]
    out += ["", "| Bài thử | Kết quả | Dữ liệu / điều kiện | Tài liệu |", "|---|---|---|---|"]
    out += [f"| {a} | {b} | {c} | `{d}` |" for a, b, c, d in KET_QUA]
    return "\n".join(out)


if __name__ == "__main__":
    print(bang_markdown())

"""Đồng bộ tài liệu với code: README / landing / trang Kiểm định ghi thông số khác code thì test đỏ.

Thông số lấy từ version_info.py (đọc thẳng hằng số trong code). Sửa code mà quên sửa tài liệu -> test này báo đúng
chỗ cần sửa.

Chạy: python -X utf8 tests/test_dong_bo_tai_lieu.py   (hoặc pytest tests/)
"""

import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
os.environ.setdefault("TF_CPP_MIN_LOG_LEVEL", "3")

import version_info as vi  # noqa: E402

engine, notifier = vi.engine, vi.notifier


def _read(rel):
    with open(os.path.join(ROOT, rel), encoding="utf-8") as f:
        return f.read()


README = _read("README.md")
LANDING = _read("landing/index.html")
EVAL_PAGE = _read("views/evaluation.py")
DOCS = {"README.md": README, "landing/index.html": LANDING}


def _g(x):
    return f"{x:g}"


def test_thoi_gian_xac_minh_sau_nga():
    s = _g(engine.DEFAULT_FALL_GRACE_SECONDS)
    assert f"thời gian xác minh sau ngã {s} s" in README, f"README phải ghi 'thời gian xác minh sau ngã {s} s'"
    assert f"Xác minh {s} giây" in LANDING, f"landing phải ghi 'Xác minh {s} giây'"
    for name, text in DOCS.items():
        for m in re.finditer(r"[Xx]ác minh(?: sau ngã)? (\d+) (?:s|giây)", text):
            assert m.group(1) == s, f"{name}: '{m.group(0)}' khác code ({s} s)"


def test_thoi_gian_cho_xac_nhan():
    s = _g(notifier.ACK_TIMEOUT_SECONDS)
    assert f"thời gian chờ xác nhận {s} s" in README, f"README phải ghi 'thời gian chờ xác nhận {s} s'"
    assert f"{s} giây chưa ai nhận" in LANDING, f"landing phải ghi '{s} giây chưa ai nhận'"


def test_thu_lai_va_so_vong():
    retry = ", ".join(_g(x) for x in notifier.RETRY_BACKOFF_SECONDS)
    for name, text in DOCS.items():
        assert retry in text, f"{name} phải ghi lịch thử lại '{retry}'"
        assert f"tối đa {notifier.MAX_ROUNDS} vòng" in text, f"{name} phải ghi 'tối đa {notifier.MAX_ROUNDS} vòng'"


def test_cua_so_model_nga():
    m = vi.fall_model()
    assert m["ten"] == "all3", f"model ngã đang chạy là '{m['ten']}' — cập nhật README / MODEL_VERSIONS.md"
    assert f"chuỗi khung xương {_g(m['cua_so'] / m['hz']).replace('.', ',')} s" in README


def test_bo_loc_sos_dung_trang_thai_mac_dinh():
    """Tài liệu không được ngầm hiểu bộ lọc đang bật khi code để tắt (và ngược lại)."""
    bat = engine.SETTINGS_DEFAULTS["sos_filter"]
    if bat:
        assert "khi tắt bộ lọc (mặc định hiện tại)" not in README + LANDING, "code đã BẬT bộ lọc, tài liệu vẫn ghi tắt"
        assert "**Bộ lọc chống báo nhầm bật sẵn**" in README
        assert "5,6 lần / giờ với bộ lọc giữ 2 giây (mặc định)" in README and "bộ lọc giữ 2 giây (bật sẵn)" in LANDING
        assert '"5,6 / giờ"' in EVAL_PAGE, "trang Kiểm định phải hiện số báo nhầm của cấu hình mặc định"
    else:
        assert "**tắt mặc định**, bật trong trang Cấu hình" in README, "README phải ghi bộ lọc SOS tắt mặc định"
        assert "132 lần / giờ khi tắt bộ lọc (mặc định hiện tại)" in README
        assert "khi tắt bộ lọc (mặc định hiện tại)" in LANDING
        assert '"132 / giờ"' in EVAL_PAGE, "trang Kiểm định phải hiện số báo nhầm của cấu hình mặc định (tắt lọc)"


def test_tinh_nang_thu_nghiem_tat_va_duoc_ghi_ro():
    row = next(line for line in README.splitlines() if line.startswith("| **Thử nghiệm**"))
    for key, ten, tt, _ in vi.TINH_NANG:
        if tt == "Thử nghiệm":
            assert not engine.SETTINGS_DEFAULTS[key], f"'{ten}' là thử nghiệm nhưng đang BẬT mặc định"
    for word in ("Signal for Help", "nhiều người", "đứng xa"):
        assert word in row, f"dòng 'Thử nghiệm' trong README thiếu '{word}'"


def test_so_lieu_cong_bo_khop_nhau():
    """Số kiểm định (version_info.KET_QUA) phải giống nhau ở README, landing, trang Kiểm định."""
    assert "121/129" in README and "121 trên 129" in LANDING
    assert "**8 cảnh báo ngã nhầm / giờ**" in README and "<b>8/giờ</b>" in LANDING and '"8 / giờ"' in EVAL_PAGE
    assert any("8 cảnh báo / giờ" in b for _, b, _, _ in vi.KET_QUA)
    for name, text in {**DOCS, "views/evaluation.py": EVAL_PAGE}.items():
        assert not re.search(r"(?<![\d,.])9 ?/ ?giờ", text), f"{name} còn số Charades cũ 9/giờ"


def test_99_phan_tram_luon_kem_dieu_kien_do():
    for name, text in DOCS.items():
        for m in re.finditer(r"99[,.]5", text):
            ctx = text[m.start():m.start() + 400]
            assert "theo khung hình" in ctx, f"{name}: 99,5x% phải ghi kèm 'chia ngẫu nhiên theo khung hình'"


def test_khong_con_ban_app_cu():
    assert not os.path.exists(os.path.join(ROOT, "app.py")), "app.py cũ (120 s, 99.54%) đã bỏ — không thêm lại"


def test_khong_luu_hinh_anh_camera():
    """README §10: hình ảnh camera không được lưu hay đính kèm. Mã của app (ngoài training/) không có lệnh ghi ảnh/video."""
    bad = re.compile(r"cv2\.imwrite|VideoWriter|\.save\(|imencode")
    # Ngoại lệ duy nhất: trang Thử bằng video tạo video kết quả + ảnh khoảnh khắc từ video NGƯỜI DÙNG TẢI LÊN (không
    # phải camera), trong file tạm bị xoá ngay và trong bộ nhớ phiên — kiểm riêng ở test_video_tai_len_khong_luu_lai.
    allowed = {"video_demo.py"}
    for dirpath, dirs, files in os.walk(ROOT):
        dirs[:] = [d for d in dirs if d not in ("training", "tests", ".git", ".venv", "__pycache__", "landing")]
        for f in files:
            if f.endswith(".py") and not (dirpath == ROOT and f in allowed):
                text = open(os.path.join(dirpath, f), encoding="utf-8").read()
                m = bad.search(text)
                assert not m, f"{os.path.relpath(os.path.join(dirpath, f), ROOT)} có '{m.group(0)}'"


def test_video_tai_len_khong_luu_lai():
    """Trang Thử bằng video: video tải lên và video kết quả chỉ nằm trong file tạm, bị xoá ngay sau khi xử lý; không
    đụng tới camera trực tiếp; trang ghi rõ điều này cho người dùng."""
    core, page = _read("video_demo.py"), _read("views/video_demo.py")
    assert "tempfile.mkstemp" in core and "os.remove(out_path)" in core, "video kết quả phải là file tạm và bị xoá"
    assert "tempfile.mkstemp" in page and "os.remove(path)" in page and "finally:" in page, \
        "video tải lên phải là file tạm, xoá trong finally"
    assert "webrtc_streamer" not in core + page, "trang video không được dùng camera trực tiếp"
    assert "bị xoá ngay" in page, "trang phải nói cho người dùng biết video bị xoá"
    assert "Video tải lên" in _read("views/privacy_center.py"), "bảng dữ liệu ở trang Quyền riêng tư phải có dòng này"


def test_cau_khong_thay_the_nguoi_cham_soc_o_ca_3_noi():
    """Đặc tả chặng 2, mục 4.8: màn hình đồng ý, trang Trực tiếp, email cảnh báo."""
    import notifier
    import privacy

    d = notifier.DISCLAIMER
    assert "không thay thế người chăm sóc" in d
    assert any(d in text for _, text in privacy.CONSENT_POINTS), "thiếu ở màn hình đồng ý"
    assert "privacy.DISCLAIMER" in _read("views/live_view.py"), "thiếu ở trang Trực tiếp"
    alert = {"kind": "Ngã", "details": "", "detected_at": 0, "source": "live"}
    assert d in notifier.email_text(alert) and d in notifier.email_html(alert), "thiếu ở email"


if __name__ == "__main__":
    tests = [(n, f) for n, f in sorted(globals().items()) if n.startswith("test_")]
    failed = 0
    for name, fn in tests:
        try:
            fn()
            print(f"PASS  {name}")
        except AssertionError as e:
            failed += 1
            print(f"FAIL  {name}: {e}")
    print(f"\n{len(tests) - failed}/{len(tests)} ca đạt")
    sys.exit(1 if failed else 0)

"""Kiểm thử đăng nhập và phân quyền (auth.py): băm mật khẩu, khoá khi sai nhiều lần, chính sách mật khẩu / PIN,
luôn còn 1 quản trị, ma trận quyền đúng đặc tả chặng 2 (mục 3.2), nhật ký truy cập.

Chạy: python -X utf8 tests/test_auth.py   (hoặc pytest tests/)
"""

import os
import sqlite3
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

import auth  # noqa: E402
import event_log  # noqa: E402


def fresh_db():
    fd, path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    event_log.DB_PATH = path
    event_log.init_db()
    auth.init_db()
    return path


def test_mat_khau_khong_luu_dang_goc_va_kiem_dung():
    h = auth.hash_secret("Matkhau2026")
    assert "Matkhau2026" not in h and h.startswith("scrypt$")
    assert auth.verify_secret("Matkhau2026", h)
    assert not auth.verify_secret("matkhau2026", h)
    assert auth.hash_secret("Matkhau2026") != h, "mỗi lần băm phải có salt khác"


def test_file_csdl_khong_chua_mat_khau_goc():
    path = fresh_db()
    auth.create_user("an.nguyen", "An", auth.ROLE_ADMIN, "BiMat#2026x")
    assert b"BiMat#2026x" not in open(path, "rb").read()


def test_chinh_sach_mat_khau_va_pin():
    assert auth.password_problem("ngan1", "a") is not None
    assert auth.password_problem("12345678", "a") is not None
    assert auth.password_problem("abcdefgh", "a") is not None, "phải có cả chữ và số"
    assert auth.password_problem("an.nguyen99", "an.nguyen") is not None, "không chứa tên đăng nhập"
    assert auth.password_problem("Hoa-sen-2026", "lan") is None
    assert auth.password_problem("482915", "ba", auth.ROLE_SUBJECT) is None
    assert auth.password_problem("123456", "ba", auth.ROLE_SUBJECT) is not None
    assert auth.password_problem("111111", "ba", auth.ROLE_SUBJECT) is not None
    assert auth.password_problem("482915", "lan", auth.ROLE_CAREGIVER) is not None, "PIN chỉ dành cho người được giám sát"


def test_dang_nhap_dung_sai_va_khoa_sau_5_lan():
    fresh_db()
    auth.create_user("lan", "Lan", auth.ROLE_CAREGIVER, "Hoa-sen-2026")
    t = 1_000_000.0
    assert auth.authenticate("lan", "Hoa-sen-2026", now=t)["role"] == auth.ROLE_CAREGIVER
    assert auth.authenticate("LAN", "Hoa-sen-2026", now=t) is not None, "tên đăng nhập không phân biệt hoa thường"
    for i in range(auth.LOCK_AFTER):
        assert auth.authenticate("lan", "sai-mat-khau-1", now=t + i) is None
    assert auth.authenticate("lan", "Hoa-sen-2026", now=t + 10) is None, "đang bị khoá thì mật khẩu đúng cũng không vào"
    assert auth.authenticate("lan", "Hoa-sen-2026", now=t + 10 + auth.LOCK_SECONDS) is not None, "hết khoá thì vào được"


def test_khong_lo_ten_dang_nhap_co_that():
    fresh_db()
    auth.create_user("lan", "Lan", auth.ROLE_CAREGIVER, "Hoa-sen-2026")
    assert auth.authenticate("khong-co", "Hoa-sen-2026") is None
    assert auth.authenticate("lan", "sai-mat-khau-1") is None  # cùng 1 kết quả, cùng 1 câu báo lỗi (LOGIN_ERROR)


def test_tai_khoan_bi_khoa_khong_dang_nhap_duoc():
    fresh_db()
    auth.create_user("boss", "Boss", auth.ROLE_ADMIN, "Quan-tri-2026")
    uid, _ = auth.create_user("lan", "Lan", auth.ROLE_CAREGIVER, "Hoa-sen-2026")
    assert auth.set_disabled(uid, True) is None
    assert auth.authenticate("lan", "Hoa-sen-2026") is None


def test_luon_con_it_nhat_mot_quan_tri():
    fresh_db()
    a, _ = auth.create_user("boss", "Boss", auth.ROLE_ADMIN, "Quan-tri-2026")
    assert auth.set_role(a, auth.ROLE_CAREGIVER) is not None
    assert auth.set_disabled(a, True) is not None
    b, _ = auth.create_user("boss2", "Boss 2", auth.ROLE_ADMIN, "Quan-tri-2027")
    assert auth.set_role(a, auth.ROLE_CAREGIVER) is None, "còn quản trị khác thì đổi được"


def test_doi_mat_khau_phai_dung_mat_khau_cu():
    fresh_db()
    uid, _ = auth.create_user("lan", "Lan", auth.ROLE_CAREGIVER, "Hoa-sen-2026")
    assert auth.set_secret(uid, "Moi-hon-2027", old_secret="sai-1234") is not None
    assert auth.set_secret(uid, "Moi-hon-2027", old_secret="Hoa-sen-2026") is None
    assert auth.authenticate("lan", "Moi-hon-2027") is not None


def test_ma_tran_quyen_dung_dac_ta():
    A, C, S = auth.ROLE_ADMIN, auth.ROLE_CAREGIVER, auth.ROLE_SUBJECT
    expect = {  # đặc tả chặng 2, mục 3.2: (quản trị, người chăm sóc, người được giám sát)
        auth.MONITOR: (1, 1, 1), auth.PAUSE: (1, 1, 1), auth.ACK: (1, 1, 1), auth.VIEW_HISTORY: (1, 1, 1),
        auth.EXPORT: (1, 0, 1), auth.DELETE_HISTORY: (1, 0, 1), auth.DELETE_ALL: (1, 0, 1),
        auth.SET_RETENTION: (1, 0, 0), auth.VIEW_CONTACTS: (1, 1, 1), auth.EDIT_CONTACTS: (1, 0, 0),
        auth.VIEW_PROFILE: (1, 1, 1), auth.EDIT_PROFILE: (1, 0, 1), auth.EDIT_CONFIG: (1, 0, 0),
        auth.MANAGE_USERS: (1, 0, 0), auth.CONSENT_SELF: (0, 0, 1), auth.CONSENT_ON_BEHALF: (1, 0, 0),
        auth.WITHDRAW_CONSENT: (1, 0, 1), auth.VIEW_AUDIT: (1, 0, 1), auth.VIEW_REPORTS: (1, 1, 1),
        auth.TEST_ALERTS: (1, 0, 0),
    }
    for perm, (a, c, s) in expect.items():
        got = (auth.role_can(A, perm), auth.role_can(C, perm), auth.role_can(S, perm))
        assert got == (bool(a), bool(c), bool(s)), f"{perm}: {got}"
    assert not auth.role_can("khong-co-vai-tro", auth.MONITOR), "mặc định là không có quyền"


def test_nhat_ky_ghi_dang_nhap_va_khong_chua_mat_khau():
    path = fresh_db()
    auth.create_user("lan", "Lan", auth.ROLE_CAREGIVER, "Hoa-sen-2026")
    auth.authenticate("lan", "sai-mat-khau-9")
    auth.authenticate("lan", "Hoa-sen-2026")
    actions = [r["action"] for r in auth.get_audit()]
    assert "dang_nhap" in actions and "dang_nhap_sai" in actions
    rows = sqlite3.connect(path).execute("SELECT detail FROM audit_log").fetchall()
    assert not any("sai-mat-khau-9" in (r[0] or "") or "Hoa-sen-2026" in (r[0] or "") for r in rows)


def test_moi_quyen_deu_co_mo_ta_de_hieu():
    """Màn hình đăng nhập, nút "Quyền của tôi" và trang Tài khoản & quyền dùng chung PERMISSION_LABELS."""
    described = {p for p, _ in auth.PERMISSION_LABELS}
    every = set().union(*auth.PERMISSIONS.values())
    assert every <= described, f"quyền chưa có mô tả: {every - described}"
    assert set(auth.ROLE_SUMMARY) == set(auth.ROLE_NAMES)

def test_quen_mat_khau_gui_ma_qua_email():

    from cryptography.fernet import Fernet

    os.environ.setdefault("SAFEWATCH_DATA_KEY", Fernet.generate_key().decode())
    path = fresh_db()
    uid, _ = auth.create_user("lan", "Lan", auth.ROLE_CAREGIVER, "Hoa-sen-2026", email="lan@example.com")
    assert b"lan@example.com" not in open(path, "rb").read(), "email lưu mã hoá"
    sent = []
    t = 1_000_000.0
    msg = auth.request_password_reset("lan", lambda to, subj, text: sent.append((to, text)), now=t)
    assert sent and sent[0][0] == "lan@example.com"
    code = [w for w in sent[0][1].replace(".", " ").split() if w.isdigit() and len(w) == 6][0]
    assert auth.request_password_reset("khong-co", lambda *a: sent.append(a), now=t) == msg, "cùng 1 câu trả lời"
    assert len(sent) == 1, "tên không có thì không gửi gì"
    assert auth.reset_password_with_code("lan", "000000" if code != "000000" else "111111", "Moi-hon-2027", now=t + 60)
    assert auth.reset_password_with_code("lan", code, "Moi-hon-2027", now=t + 60) is None
    assert auth.authenticate("lan", "Moi-hon-2027") is not None
    assert auth.reset_password_with_code("lan", code, "Lai-nua-2028", now=t + 70) is not None, "mã dùng 1 lần"


def test_ma_dat_lai_het_han_va_sai_qua_5_lan():
    from cryptography.fernet import Fernet

    os.environ.setdefault("SAFEWATCH_DATA_KEY", Fernet.generate_key().decode())
    fresh_db()
    auth.create_user("lan", "Lan", auth.ROLE_CAREGIVER, "Hoa-sen-2026", email="lan@example.com")
    sent = []
    t = 1_000_000.0
    auth.request_password_reset("lan", lambda to, subj, text: sent.append(text), now=t)
    code = [w for w in sent[0].replace(".", " ").split() if w.isdigit() and len(w) == 6][0]
    assert auth.reset_password_with_code("lan", code, "Moi-hon-2027", now=t + 16 * 60) is not None, "quá 15 phút"
    auth.request_password_reset("lan", lambda to, subj, text: sent.append(text), now=t + 20 * 60)
    code2 = [w for w in sent[1].replace(".", " ").split() if w.isdigit() and len(w) == 6][0]
    wrong = "123456" if code2 != "123456" else "654321"
    for _ in range(auth.RESET_MAX_ATTEMPTS):
        auth.reset_password_with_code("lan", wrong, "Moi-hon-2027", now=t + 21 * 60)
    assert auth.reset_password_with_code("lan", code2, "Moi-hon-2027", now=t + 21 * 60) is not None, "sai 5 lần thì huỷ mã"


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

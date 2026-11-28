"""Tài khoản, phân quyền và nhật ký truy cập (đặc tả chặng 2, mục 3, 4.1, 4.2, 4.7).

- Mật khẩu / mã PIN KHÔNG lưu dạng gốc: băm bằng scrypt (hashlib, có sẵn trong Python), mỗi tài khoản 1 salt
  ngẫu nhiên 16 byte, so sánh bằng hmac.compare_digest (không lộ thông tin qua thời gian so sánh).
- Sai 5 lần liên tiếp -> khoá 5 phút. Mọi lỗi đăng nhập trả về CÙNG một câu, và tên không tồn tại vẫn tốn đúng
  một lần băm -> không dò được tên đăng nhập nào có thật.
- Quyền: mặc định là KHÔNG. PERMISSIONS liệt kê đúng ma trận trong đặc tả; trang và thao tác ghi / xoá đều gọi
  require() ngay trước khi chạm dữ liệu (ẩn nút thôi là chưa đủ).
- Nhật ký truy cập (audit_log): ai làm gì, lúc nào, phạm vi nào. KHÔNG chứa nội dung dữ liệu, không ai sửa / xoá
  được từ giao diện; chỉ tự dọn sau AUDIT_RETENTION_DAYS ngày (privacy.prune).

Phần thuần (băm, kiểm tra, CSDL) không phụ thuộc Streamlit -> kiểm thử được offline (tests/test_auth.py).
"""

import base64
import hashlib
import hmac
import os
import re
import time

import event_log

# ------------------------------------------------------------------ vai trò và quyền

ROLE_ADMIN = "quan_tri"
ROLE_CAREGIVER = "cham_soc"
ROLE_SUBJECT = "duoc_giam_sat"
ROLE_NAMES = {ROLE_ADMIN: "Quản trị gia đình", ROLE_CAREGIVER: "Người chăm sóc", ROLE_SUBJECT: "Người được giám sát"}
ROLES = list(ROLE_NAMES)

MONITOR = "giam_sat"                  # bắt đầu / dừng giám sát trên thiết bị
PAUSE = "tam_dung"                    # tạm dừng vì riêng tư
ACK = "xac_nhan_canh_bao"             # xem cảnh báo, bấm "Tôi đã nhận"
VIEW_HISTORY = "xem_lich_su"          # Nhật ký, Tổng quan
EXPORT = "xuat_csv"
DELETE_HISTORY = "xoa_lich_su"        # xoá 1 sự kiện / theo khoảng ngày / toàn bộ lịch sử
DELETE_ALL = "xoa_toan_bo_du_lieu"    # xoá toàn bộ dữ liệu cá nhân
SET_RETENTION = "dat_han_luu"
VIEW_CONTACTS = "xem_nguoi_lien_he"
EDIT_CONTACTS = "sua_nguoi_lien_he"
VIEW_PROFILE = "xem_ho_so"
EDIT_PROFILE = "sua_ho_so"
EDIT_CONFIG = "doi_cau_hinh"
MANAGE_USERS = "quan_ly_tai_khoan"
CONSENT_SELF = "tu_dong_y"            # tự cho phép / rút lại sự đồng ý
CONSENT_ON_BEHALF = "ghi_thay_dong_y"  # ghi thay (bắt buộc lý do)
WITHDRAW_CONSENT = "rut_lai_dong_y"
VIEW_AUDIT = "xem_nhat_ky_truy_cap"
VIEW_REPORTS = "xem_bao_cao"          # Kiểm định, Phiên bản, Quyền riêng tư
TEST_ALERTS = "thu_chuoi_canh_bao"    # gửi thử, giả lập sự kiện

_ALL = {MONITOR, PAUSE, ACK, VIEW_HISTORY, EXPORT, DELETE_HISTORY, DELETE_ALL, SET_RETENTION, VIEW_CONTACTS,
        EDIT_CONTACTS, VIEW_PROFILE, EDIT_PROFILE, EDIT_CONFIG, MANAGE_USERS, CONSENT_ON_BEHALF, WITHDRAW_CONSENT,
        VIEW_AUDIT, VIEW_REPORTS, TEST_ALERTS}
# Đúng ma trận mục 3.2 của đặc tả. Người chăm sóc KHÔNG xoá được lịch sử (không ai che giấu được sự cố).
PERMISSIONS = {
    ROLE_ADMIN: frozenset(_ALL),
    ROLE_CAREGIVER: frozenset({MONITOR, PAUSE, ACK, VIEW_HISTORY, VIEW_CONTACTS, VIEW_PROFILE, VIEW_REPORTS}),
    ROLE_SUBJECT: frozenset({MONITOR, PAUSE, ACK, VIEW_HISTORY, EXPORT, DELETE_HISTORY, DELETE_ALL, VIEW_CONTACTS,
                             VIEW_PROFILE, EDIT_PROFILE, CONSENT_SELF, WITHDRAW_CONSENT, VIEW_AUDIT, VIEW_REPORTS}),
}


# Mô tả dễ hiểu cho người dùng (màn hình đăng nhập, "Quyền của tôi", trang Tài khoản & quyền) — 1 nguồn duy nhất.
ROLE_SUMMARY = {
    ROLE_ADMIN: ("Người lắp đặt, thường là con cháu", "Làm được mọi việc: tạo tài khoản, người liên hệ, cấu hình, "
                 "hạn lưu, xoá dữ liệu. Luôn có ít nhất 1 người."),
    ROLE_CAREGIVER: ("Người thân, người giúp việc, nhân viên y tế", "Giám sát, nhận và xác nhận cảnh báo, xem lịch sử. "
                     "Không đổi cấu hình, không xoá lịch sử."),
    ROLE_SUBJECT: ("Ông bà — người được camera theo dõi", "Đăng nhập bằng PIN 6 số. Đồng ý hoặc rút lại việc giám sát, "
                   "tạm dừng vì riêng tư, xem và xoá dữ liệu của mình."),
}
PERMISSION_LABELS = [
    (MONITOR, "Bật / dừng giám sát trên thiết bị"),
    (PAUSE, "Tạm dừng giám sát vì riêng tư"),
    (ACK, "Xem cảnh báo, bấm “Tôi đã nhận”"),
    (VIEW_HISTORY, "Xem lịch sử, trang Tổng quan"),
    (VIEW_CONTACTS, "Xem người liên hệ"),
    (VIEW_PROFILE, "Xem hồ sơ người được giám sát"),
    (VIEW_REPORTS, "Xem trang Kiểm định, Phiên bản, Quyền riêng tư"),
    (EXPORT, "Xuất lịch sử ra file CSV"),
    (DELETE_HISTORY, "Xoá sự kiện / theo ngày / toàn bộ lịch sử"),
    (DELETE_ALL, "Xoá toàn bộ dữ liệu cá nhân"),
    (SET_RETENTION, "Đặt hạn lưu dữ liệu"),
    (EDIT_CONTACTS, "Thêm / sửa / xoá người liên hệ"),
    (EDIT_PROFILE, "Sửa hồ sơ"),
    (EDIT_CONFIG, "Đổi cấu hình phát hiện"),
    (MANAGE_USERS, "Tạo / khoá tài khoản, đổi vai trò, đặt lại mật khẩu"),
    (CONSENT_SELF, "Tự đồng ý được giám sát"),
    (CONSENT_ON_BEHALF, "Ghi thay sự đồng ý (bắt buộc nêu lý do)"),
    (WITHDRAW_CONSENT, "Rút lại sự đồng ý"),
    (VIEW_AUDIT, "Xem nhật ký truy cập (ai làm gì, lúc nào)"),
    (TEST_ALERTS, "Gửi tin thử, giả lập sự kiện"),
]


def role_can(role, permission):
    return permission in PERMISSIONS.get(role, frozenset())


# ------------------------------------------------------------------ băm mật khẩu

SCRYPT_N, SCRYPT_R, SCRYPT_P, SCRYPT_LEN = 2 ** 15, 8, 1, 32  # ~32 MB bộ nhớ mỗi lần băm: chậm với kẻ dò mật khẩu
LOCK_AFTER = 5
LOCK_SECONDS = 300
IDLE_SECONDS = 8 * 3600  # không thao tác 8 giờ thì phải đăng nhập lại
AUDIT_RETENTION_DAYS = 365
LOGIN_ERROR = "Sai tên đăng nhập hoặc mật khẩu, hoặc tài khoản đang tạm khoá. Thử lại sau ít phút."
USERNAME_RE = re.compile(r"^[a-z0-9_.-]{3,32}$")
_COMMON = {"12345678", "123456789", "1234567890", "password", "matkhau123", "qwerty123", "11111111", "abc12345",
           "iloveyou", "admin123", "safewatch", "00000000", "88888888", "password1"}


def _b64(raw):
    return base64.b64encode(raw).decode()


def hash_secret(secret):
    salt = os.urandom(16)
    dk = hashlib.scrypt(secret.encode("utf-8"), salt=salt, n=SCRYPT_N, r=SCRYPT_R, p=SCRYPT_P, dklen=SCRYPT_LEN,
                        maxmem=64 * 1024 * 1024)
    return f"scrypt${SCRYPT_N}${SCRYPT_R}${SCRYPT_P}${_b64(salt)}${_b64(dk)}"


def verify_secret(secret, stored):
    try:
        algo, n, r, p, salt, expected = stored.split("$")
        if algo != "scrypt":
            return False
        dk = hashlib.scrypt(secret.encode("utf-8"), salt=base64.b64decode(salt), n=int(n), r=int(r), p=int(p),
                            dklen=len(base64.b64decode(expected)), maxmem=64 * 1024 * 1024)
        return hmac.compare_digest(dk, base64.b64decode(expected))
    except (ValueError, TypeError):
        return False


_DUMMY_HASH = None


def _dummy_hash():
    global _DUMMY_HASH
    if _DUMMY_HASH is None:
        _DUMMY_HASH = hash_secret(os.urandom(12).hex())
    return _DUMMY_HASH


def password_problem(secret, username="", role=ROLE_CAREGIVER):
    """Lý do mật khẩu / PIN chưa đạt (None = đạt). Người được giám sát dùng PIN 6 số cho dễ nhớ."""
    secret = secret or ""
    if role == ROLE_SUBJECT and secret.isdigit():
        if len(secret) != 6:
            return "Mã PIN gồm đúng 6 chữ số."
        if len(set(secret)) == 1 or secret in ("123456", "654321", "012345", "123123"):
            return "Mã PIN quá dễ đoán."
        return None
    if len(secret) < 8:
        return "Mật khẩu cần ít nhất 8 ký tự."
    if secret.lower() in _COMMON or (username and username.lower() in secret.lower()):
        return "Mật khẩu quá dễ đoán (không dùng mật khẩu phổ biến hay chứa tên đăng nhập)."
    if secret.isdigit() or secret.isalpha():
        return "Mật khẩu cần có cả chữ và số."
    return None


# ------------------------------------------------------------------ CSDL

def _conn():
    return event_log._get_connection()


def init_db():
    with _conn() as conn:
        conn.execute(
            """CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT NOT NULL UNIQUE COLLATE NOCASE,
                display_name TEXT NOT NULL,
                role TEXT NOT NULL,
                secret_hash TEXT NOT NULL,
                disabled INTEGER NOT NULL DEFAULT 0,
                failed_count INTEGER NOT NULL DEFAULT 0,
                locked_until REAL NOT NULL DEFAULT 0,
                created_at REAL NOT NULL,
                last_login REAL
            )"""
        )
        conn.execute(
            """CREATE TABLE IF NOT EXISTS audit_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                at REAL NOT NULL,
                username TEXT,
                role TEXT,
                action TEXT NOT NULL,
                detail TEXT
            )"""
        )


def _row(cursor, row):
    return {c[0]: row[i] for i, c in enumerate(cursor.description)}


def _public(user):
    """Thông tin tài khoản an toàn để giữ trong phiên (không có mã băm)."""
    return None if user is None else {k: user[k] for k in ("id", "username", "display_name", "role", "disabled")}


def get_user(user_id):
    with _conn() as conn:
        conn.row_factory = _row
        return conn.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()


def list_users():
    with _conn() as conn:
        conn.row_factory = _row
        return [_public(u) | {"last_login": u["last_login"], "locked_until": u["locked_until"]}
                for u in conn.execute("SELECT * FROM users ORDER BY id").fetchall()]


def count_users():
    with _conn() as conn:
        return conn.execute("SELECT COUNT(*) FROM users").fetchone()[0]


def _active_admins(conn):
    return conn.execute("SELECT COUNT(*) FROM users WHERE role = ? AND disabled = 0", (ROLE_ADMIN,)).fetchone()[0]


def create_user(username, display_name, role, secret, now=None):
    """Tạo tài khoản. Trả (id, None) hoặc (None, lý do lỗi)."""
    username = (username or "").strip().lower()
    display_name = (display_name or "").strip()
    if not USERNAME_RE.match(username):
        return None, "Tên đăng nhập 3–32 ký tự: chữ thường không dấu, số, dấu . _ -"
    if not display_name or len(display_name) > 60:
        return None, "Cần tên hiển thị (tối đa 60 ký tự)."
    if role not in ROLE_NAMES:
        return None, "Vai trò không hợp lệ."
    problem = password_problem(secret, username, role)
    if problem:
        return None, problem
    with _conn() as conn:
        if conn.execute("SELECT 1 FROM users WHERE username = ?", (username,)).fetchone():
            return None, "Tên đăng nhập đã có."
        cur = conn.execute(
            "INSERT INTO users (username, display_name, role, secret_hash, created_at) VALUES (?, ?, ?, ?, ?)",
            (username, display_name, role, hash_secret(secret), time.time() if now is None else now))
        return cur.lastrowid, None


def authenticate(username, secret, now=None):
    """Trả tài khoản (không kèm mã băm) nếu đúng, None nếu sai / bị khoá / bị vô hiệu."""
    now = time.time() if now is None else now
    username = (username or "").strip().lower()
    with _conn() as conn:
        conn.row_factory = _row
        user = conn.execute("SELECT * FROM users WHERE username = ?", (username,)).fetchone()
    if user is None:
        verify_secret(secret or "", _dummy_hash())  # cùng thời gian xử lý với tên có thật
        audit("dang_nhap_sai", f"tên: {username[:32]}", who=("", ""))
        return None
    if user["disabled"] or user["locked_until"] > now:
        verify_secret(secret or "", _dummy_hash())
        audit("dang_nhap_bi_chan", "tài khoản bị khoá hoặc vô hiệu", who=(user["username"], user["role"]))
        return None
    if not verify_secret(secret or "", user["secret_hash"]):
        failed = user["failed_count"] + 1
        locked = now + LOCK_SECONDS if failed >= LOCK_AFTER else 0
        with _conn() as conn:
            conn.execute("UPDATE users SET failed_count = ?, locked_until = ? WHERE id = ?",
                         (0 if locked else failed, locked, user["id"]))
        audit("dang_nhap_sai", "khoá 5 phút" if locked else f"lần {failed}", who=(user["username"], user["role"]))
        return None
    with _conn() as conn:
        conn.execute("UPDATE users SET failed_count = 0, locked_until = 0, last_login = ? WHERE id = ?",
                     (now, user["id"]))
    audit("dang_nhap", who=(user["username"], user["role"]))
    return _public(user)


def set_role(user_id, role, actor=None):
    if role not in ROLE_NAMES:
        return "Vai trò không hợp lệ."
    with _conn() as conn:
        target = conn.execute("SELECT role, disabled, username FROM users WHERE id = ?", (user_id,)).fetchone()
        if target is None:
            return "Không có tài khoản này."
        if target[0] == ROLE_ADMIN and role != ROLE_ADMIN and not target[1] and _active_admins(conn) <= 1:
            return "Phải luôn còn ít nhất 1 quản trị."
        conn.execute("UPDATE users SET role = ? WHERE id = ?", (role, user_id))
    audit("doi_vai_tro", f"{target[2]} -> {ROLE_NAMES[role]}", who=actor)
    return None


def set_disabled(user_id, disabled, actor=None):
    with _conn() as conn:
        target = conn.execute("SELECT role, disabled, username FROM users WHERE id = ?", (user_id,)).fetchone()
        if target is None:
            return "Không có tài khoản này."
        if disabled and target[0] == ROLE_ADMIN and not target[1] and _active_admins(conn) <= 1:
            return "Phải luôn còn ít nhất 1 quản trị."
        conn.execute("UPDATE users SET disabled = ?, failed_count = 0, locked_until = 0 WHERE id = ?",
                     (1 if disabled else 0, user_id))
    audit("khoa_tai_khoan" if disabled else "mo_khoa_tai_khoan", target[2], who=actor)
    return None


def set_secret(user_id, new_secret, actor=None, old_secret=None):
    """Đổi / đặt lại mật khẩu. old_secret khác None = người dùng tự đổi (phải đúng mật khẩu cũ)."""
    user = get_user(user_id)
    if user is None:
        return "Không có tài khoản này."
    if old_secret is not None and not verify_secret(old_secret, user["secret_hash"]):
        return "Mật khẩu hiện tại không đúng."
    problem = password_problem(new_secret, user["username"], user["role"])
    if problem:
        return problem
    with _conn() as conn:
        conn.execute("UPDATE users SET secret_hash = ?, failed_count = 0, locked_until = 0 WHERE id = ?",
                     (hash_secret(new_secret), user_id))
    audit("doi_mat_khau" if old_secret is not None else "dat_lai_mat_khau", user["username"], who=actor)
    return None


def delete_non_admin_users(conn):
    """Dùng khi xoá toàn bộ dữ liệu cá nhân (privacy.delete_all_personal), trong cùng giao dịch."""
    return conn.execute("DELETE FROM users WHERE role != ?", (ROLE_ADMIN,)).rowcount


# ------------------------------------------------------------------ nhật ký truy cập

def audit(action, detail="", who=None, now=None):
    """Ghi 1 dòng nhật ký truy cập. who = (tên đăng nhập, vai trò); None = người đang đăng nhập (nếu có)."""
    if who is None:
        u = current_user(touch=False)
        who = (u["username"], u["role"]) if u else ("", "")
    with _conn() as conn:
        conn.execute("INSERT INTO audit_log (at, username, role, action, detail) VALUES (?, ?, ?, ?, ?)",
                     (time.time() if now is None else now, who[0], who[1], action, (detail or "")[:300]))


def get_audit(limit=500):
    with _conn() as conn:
        conn.row_factory = _row
        return conn.execute("SELECT * FROM audit_log ORDER BY id DESC LIMIT ?", (limit,)).fetchall()


# ------------------------------------------------------------------ phiên đăng nhập (Streamlit)

SESSION_KEY = "_auth_user"


def _state():
    try:
        import streamlit as st

        return st.session_state
    except Exception:  # noqa: BLE001 — chạy ngoài Streamlit (kiểm thử, script)
        return None


def current_user(touch=True):
    """Tài khoản đang đăng nhập (đọc lại từ CSDL mỗi lần: bị khoá / đổi vai trò có hiệu lực ngay), hoặc None."""
    s = _state()
    if s is None:
        return None
    try:
        sess = s.get(SESSION_KEY)
    except Exception:  # noqa: BLE001 — ngoài phiên Streamlit (thread nền)
        return None
    if not sess:
        return None
    now = time.time()
    if now - sess.get("seen", now) > IDLE_SECONDS:
        s.pop(SESSION_KEY, None)
        return None
    user = get_user(sess["id"])
    if user is None or user["disabled"]:
        s.pop(SESSION_KEY, None)
        return None
    if touch:
        sess["seen"] = now
    return _public(user)


def touch():
    current_user(touch=True)


def who():
    u = current_user(touch=False)
    return (u["username"], u["role"]) if u else ("", "")


def login(user):
    s = _state()
    s[SESSION_KEY] = {"id": user["id"], "seen": time.time()}


def logout():
    u = current_user(touch=False)
    if u:
        audit("dang_xuat", who=(u["username"], u["role"]))
    s = _state()
    if s is not None:
        for k in list(s.keys()):
            if k != "sidebar_status_placeholder":
                s.pop(k, None)


def can(permission):
    u = current_user(touch=False)
    return bool(u) and role_can(u["role"], permission)


def require(permission, message="Bạn không có quyền làm việc này."):
    """Chặn ngay nếu tài khoản hiện tại không có quyền (ghi nhật ký lần bị từ chối)."""
    if can(permission):
        return
    import streamlit as st

    audit("bi_tu_choi", permission)
    st.error(message)
    st.stop()

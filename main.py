"""Entry point của SafeWatch — nhiều trang qua st.navigation, menu chia nhóm theo việc người dùng cần làm:

  Giám sát  : Trực tiếp · Cảnh báo · Nhật ký
  Thiết lập : Người liên hệ · Camera & lắp đặt · Cấu hình
  Báo cáo   : Tổng quan · Kiểm định · Phiên bản
  Tài khoản : Hồ sơ · Tài khoản & quyền · Quyền riêng tư

Mọi trang đều cần đăng nhập (auth.py); menu chỉ hiện trang mà vai trò được xem. Riêng trang mở từ link
"Tôi đã nhận" trong tin nhắn thì không cần đăng nhập (chỉ xác nhận đúng 1 cảnh báo, link hết hạn sau 24 giờ).

Chạy: streamlit run main.py
"""

import os
import time

# Múi giờ của app = giờ Việt Nam (UTC+7) ở MỌI nơi chạy. Streamlit Cloud / Docker mặc định UTC -> giờ hiển thị trong
# bảng, email, Telegram, SMS bị lệch 7 tiếng. Chuỗi POSIX "ICT-7" = UTC+7, không cần cơ sở dữ liệu múi giờ của máy
# (image Docker slim thường thiếu). Đổi được bằng biến môi trường SAFEWATCH_TZ. Windows không có time.tzset ->
# giữ giờ của máy (máy ở VN đã đúng).
os.environ["TZ"] = os.environ.get("SAFEWATCH_TZ", "ICT-7")
if hasattr(time, "tzset"):
    time.tzset()

import base64  # noqa: E402

import streamlit as st  # noqa: E402

import auth  # noqa: E402
import notifier  # noqa: E402
import privacy  # noqa: E402
from theme import APP_NAME, ack_page_html, inject_global_theme, render_sidebar_profile, sidebar_status_html

ROOT = os.path.dirname(os.path.abspath(__file__))



@st.cache_data
def _data_uri(name):
    """Ảnh trong assets/ -> data URI. Logo / favicon nhúng thẳng vào trang: trên Streamlit Cloud, đường /media/ lỗi
    nén gzip của server Starlette, còn /app/static/... tính từ gốc tên miền không tới được app (Cloud chạy app dưới
    1 đường dẫn con) -> cả hai cách đều ra ảnh vỡ."""
    with open(os.path.join(ROOT, "assets", name), "rb") as f:
        return "data:image/png;base64," + base64.b64encode(f.read()).decode()


st.set_page_config(page_title=APP_NAME, page_icon=_data_uri("favicon.png"), layout="wide")
inject_global_theme()
st.logo(_data_uri("logo_light_sm.png"), size="large", icon_image=_data_uri("logo_icon_sm.png"))


@st.cache_resource
def start_notifier():
    """1 bộ gửi cảnh báo nền cho cả tiến trình server — chạy cả khi không ai mở trang (xem notifier.py).
    Cấu hình kênh đọc từ secrets.toml. Kèm việc dọn dữ liệu quá hạn lưu mỗi giờ (privacy.prune)."""
    privacy.init_all()
    config = notifier.load_config(st.secrets)
    dispatcher = notifier.Dispatcher(notifier.build_channels(config), public_base_url=config.get("PUBLIC_BASE_URL"),
                                     housekeeping=privacy.prune)
    dispatcher.start()
    return dispatcher


notifier.RUNNING = start_notifier()
# Cập nhật cấu trúc CSDL (thêm bảng / cột mới) ở MỖI lần chạy, không chỉ lúc khởi động: Streamlit Cloud nạp code mới
# khi app cũ vẫn chạy (start_notifier đã được cache) -> bản mới thiếu cột mới (VD users.email) nếu chỉ chạy 1 lần.
# Các lệnh đều "nếu chưa có thì tạo", tốn khoảng 1 ms.
auth.init_db()
privacy.init_db()
# Link "Tôi đã nhận" trong tin nhắn: secrets ghi localhost / để trống thì dùng địa chỉ thật mà người dùng đang mở app
# (VD https://safewatch.streamlit.app) — người nhận mở link trên điện thoại mới vào được.
# hasattr: Streamlit Cloud nạp main.py mới trước khi nạp lại notifier / bộ gửi đang chạy (bản cũ chưa có hàm này)
# -> bỏ qua đến lần khởi động lại, không làm sập cả app.
if (notifier.RUNNING is not None and hasattr(notifier, "choose_public_base_url")
        and hasattr(notifier.RUNNING, "configured_base_url")):
    try:
        _visitor_url = st.context.url
    except Exception:  # noqa: BLE001
        _visitor_url = None
    notifier.RUNNING.public_base_url = notifier.choose_public_base_url(
        notifier.RUNNING.configured_base_url, notifier.RUNNING.public_base_url, _visitor_url)

# Link xác nhận trong email / SMS / Telegram: <PUBLIC_BASE_URL>/?ack=<mã> -> trang xác nhận riêng, KHÔNG cần đăng
# nhập (người nhà đang gấp). Link chỉ xác nhận đúng cảnh báo đó và hết hạn sau notifier.LINK_TTL_SECONDS.
# Bỏ tham số khỏi URL để tải lại trang không xác nhận lần nữa.
_ack_token = st.query_params.get("ack")
if _ack_token:
    _alert = notifier.get_alert_by_token(_ack_token)
    if _alert is not None and _alert.get("acked_at") is None and notifier.link_expired(_alert):
        _view = "expired"
    else:
        _first = notifier.ack(_ack_token, by="(link xác nhận)", via="web-link", max_age=notifier.LINK_TTL_SECONDS)
        _alert = notifier.get_alert_by_token(_ack_token)
        _view = "new" if _first else "already" if _alert else "invalid"
    auth.audit("xac_nhan_qua_link", f"kết quả: {_view}", who=("(link trong tin nhắn)", ""))
    st.query_params.clear()
    st.markdown(ack_page_html(_view, _alert), unsafe_allow_html=True)
    st.caption("Muốn xem tất cả cảnh báo: mở SafeWatch và đăng nhập.")
    st.stop()


# ------------------------------------------------------------------ đăng nhập

def _email_sender():
    """Kênh email của bộ gửi cảnh báo (cấu hình SMTP trong secrets), hoặc None nếu chưa cài."""
    ch = notifier.RUNNING.channels.get("email") if notifier.RUNNING else None
    return ch.send_plain if ch is not None and hasattr(ch, "send_plain") else None


def _forgot_password():
    with st.expander("Quên mật khẩu?"):
        sender = _email_sender()
        if sender is None:
            st.write("Nhờ **quản trị gia đình** đặt lại mật khẩu cho bạn ở trang Tài khoản & quyền.")
            return
        st.caption("Nhập tên đăng nhập. Nếu tài khoản có email, SafeWatch gửi mã 6 số tới email đó. Không có email "
                   "(VD tài khoản dùng mã PIN) thì nhờ quản trị gia đình đặt lại.")
        with st.form("forgot_req", border=False):
            fu = st.text_input("Tên đăng nhập", key="fp_user")
            if st.form_submit_button("Gửi mã qua email"):
                time.sleep(0.5)
                st.session_state["_fp_user"] = fu.strip().lower()
                st.info(auth.request_password_reset(fu, sender))
        if st.session_state.get("_fp_user"):
            with st.form("forgot_set", border=False):
                code = st.text_input("Mã 6 số trong email", max_chars=6, key="fp_code")
                npw = st.text_input("Mật khẩu / PIN mới", type="password", key="fp_pw")
                npw2 = st.text_input("Nhập lại", type="password", key="fp_pw2")
                if st.form_submit_button("Đặt mật khẩu mới", type="primary"):
                    if npw != npw2:
                        st.error("Hai lần nhập không khớp.")
                    else:
                        time.sleep(0.5)
                        err = auth.reset_password_with_code(st.session_state["_fp_user"], code, npw)
                        if err:
                            st.error(err)
                        else:
                            st.session_state.pop("_fp_user", None)
                            st.success("Đã đặt mật khẩu mới. Đăng nhập lại ở trên.")


def _login_screen():
    _, mid, _ = st.columns([1, 1.3, 1])
    with mid:
        if auth.count_users() == 0:
            st.markdown("### Cài đặt lần đầu")
            st.caption("Chưa có tài khoản nào. **Người tạo tài khoản đầu tiên sẽ là quản trị gia đình**, sau đó duyệt "
                       "hoặc tạo tài khoản cho những người khác.")
            with st.form("first_setup"):
                username = st.text_input("Tên đăng nhập", placeholder="vd: an.nguyen")
                display = st.text_input("Tên hiển thị", placeholder="vd: Nguyễn Văn An (con trai)")
                email = st.text_input("Email (để tự lấy lại mật khẩu khi quên, không bắt buộc)",
                                      placeholder="vd: an.nguyen@gmail.com")
                pw = st.text_input("Mật khẩu (ít nhất 6 ký tự, hoặc mã PIN 6 số)", type="password")
                pw2 = st.text_input("Nhập lại mật khẩu", type="password")
                commit = st.checkbox("Tôi cam kết chỉ dùng SafeWatch khi người được giám sát đã được giải thích và đồng "
                                     "ý; không lắp đặt bí mật; giữ kín mật khẩu.")
                if st.form_submit_button("Tạo tài khoản quản trị", type="primary"):
                    if pw != pw2:
                        st.error("Hai lần nhập mật khẩu không khớp.")
                    elif not commit:
                        st.error("Cần đánh dấu cam kết sử dụng.")
                    else:
                        uid, err = auth.create_user(username, display, auth.ROLE_ADMIN, pw, email=email)
                        if err:
                            st.error(err)
                        else:
                            auth.audit("tao_quan_tri_dau_tien", who=(username.strip().lower(), auth.ROLE_ADMIN))
                            auth.login(auth.authenticate(username, pw))  # ghi luôn lần đăng nhập đầu
                            st.rerun()
            return
        st.markdown("### Đăng nhập SafeWatch")
        with st.form("login"):
            username = st.text_input("Tên đăng nhập")
            secret = st.text_input("Mật khẩu hoặc mã PIN", type="password")
            if st.form_submit_button("Đăng nhập", type="primary", width="stretch"):
                user = auth.authenticate(username, secret)
                if user is None:
                    time.sleep(1.0)  # làm chậm việc dò mật khẩu
                    st.error(auth.LOGIN_ERROR)
                else:
                    auth.login(user)
                    st.rerun()
        _forgot_password()
        st.caption("Nhận được cảnh báo? Bấm link trong tin nhắn để xác nhận, không cần đăng nhập.")
        with st.container(border=True, key="swbox_roles_intro"):
            st.markdown("**Mỗi người một tài khoản, mỗi vai trò một quyền**")
            for role, (who_txt, can_txt) in auth.ROLE_SUMMARY.items():
                st.markdown(f"**{auth.ROLE_NAMES[role]}** · {who_txt}" + "  " + chr(10) + can_txt)
            st.caption("Chưa có tài khoản? Nhờ **quản trị gia đình** tạo cho bạn ở trang Tài khoản & quyền. Quên mật "
                       "khẩu? Bấm **Quên mật khẩu?** (mã qua email) hoặc nhờ quản trị đặt lại. Sai 5 lần liên tiếp thì "
                       "tài khoản tạm khoá 5 phút.")


_user = auth.current_user()
if _user is None:
    _login_screen()
    st.stop()

# ------------------------------------------------------------------ menu theo vai trò
# (trang, tiêu đề, quyền cần có). Trang không có trong menu thì mở bằng URL cũng không tới được.
_PAGES = {
    "Giám sát": [
        ("views/live_view.py", "Trực tiếp", auth.MONITOR),
        ("views/video_demo.py", "Thử bằng video", auth.MONITOR),
        ("views/alerts.py", "Cảnh báo", auth.ACK),
        ("views/history.py", "Nhật ký", auth.VIEW_HISTORY),
    ],
    "Thiết lập": [
        ("views/emergency_contacts.py", "Người liên hệ", auth.VIEW_CONTACTS),
        ("views/camera_management.py", "Camera & lắp đặt", auth.MONITOR),
        ("views/settings.py", "Cấu hình", auth.EDIT_CONFIG),
    ],
    "Báo cáo": [
        ("views/dashboard.py", "Tổng quan", auth.VIEW_HISTORY),
        ("views/evaluation.py", "Kiểm định", auth.VIEW_REPORTS),
        ("views/version.py", "Phiên bản", auth.VIEW_REPORTS),
    ],
    "Tài khoản": [
        ("views/account.py", "Hồ sơ", auth.VIEW_PROFILE),
        ("views/users.py", "Tài khoản & quyền", None),
        ("views/privacy_center.py", "Quyền riêng tư", auth.VIEW_REPORTS),
    ],
}
pages = {}
for _group, _items in _PAGES.items():
    _allowed = [st.Page(path, title=title, default=(path == "views/live_view.py"))
                for path, title, perm in _items if perm is None or auth.role_can(_user["role"], perm)]
    if _allowed:
        pages[_group] = _allowed

nav = st.navigation(pages)

with st.sidebar:
    # Placeholder lưu vào session_state để views/live_view.py cập nhật LIÊN TỤC trong vòng lặp webcam (cùng 1
    # lần chạy script nên placeholder vẫn hợp lệ).
    st.session_state["sidebar_status_placeholder"] = st.empty()
    st.session_state["sidebar_status_placeholder"].markdown(
        sidebar_status_html(st.session_state.get("camera_online", False)), unsafe_allow_html=True
    )
    st.markdown("---")
    render_sidebar_profile(name=_user["display_name"], role=auth.ROLE_NAMES.get(_user["role"], ""))
    with st.popover("Quyền của tôi", width="stretch"):
        st.markdown(f"**{auth.ROLE_NAMES[_user['role']]}** — {auth.ROLE_SUMMARY[_user['role']][1]}")
        st.markdown(chr(10).join(f"- {'✅' if auth.role_can(_user['role'], p) else '⛔'} {text}"
                                 for p, text in auth.PERMISSION_LABELS))
        st.caption("Cần thêm quyền? Nhờ quản trị gia đình đổi vai trò ở trang Tài khoản & quyền.")
    if st.button("Đăng xuất", key="logout", width="stretch"):
        auth.logout()
        st.rerun()

nav.run()

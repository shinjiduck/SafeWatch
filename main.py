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

def _login_screen():
    _, mid, _ = st.columns([1, 1.3, 1])
    with mid:
        if auth.count_users() == 0:
            st.markdown("### Cài đặt lần đầu")
            st.caption("Tạo tài khoản quản trị gia đình. Cần **mã cài đặt** (SETUP_CODE trong .streamlit/secrets.toml) "
                       "để người lạ mở app trước không chiếm được quyền quản trị.")
            if auth.setup_code() is None:
                st.error("Chưa đặt mã cài đặt. Thêm dòng SETUP_CODE = \"<ít nhất 8 ký tự>\" vào .streamlit/secrets.toml "
                         "rồi tải lại trang.")
                return
            with st.form("first_setup"):
                code = st.text_input("Mã cài đặt", type="password")
                username = st.text_input("Tên đăng nhập", placeholder="vd: an.nguyen")
                display = st.text_input("Tên hiển thị", placeholder="vd: Nguyễn Văn An (con trai)")
                pw = st.text_input("Mật khẩu (ít nhất 8 ký tự, có chữ và số)", type="password")
                pw2 = st.text_input("Nhập lại mật khẩu", type="password")
                commit = st.checkbox("Tôi cam kết chỉ dùng SafeWatch khi người được giám sát đã được giải thích và đồng "
                                     "ý; không lắp đặt bí mật; giữ kín mật khẩu.")
                if st.form_submit_button("Tạo tài khoản quản trị", type="primary"):
                    if not auth.check_setup_code(code):
                        time.sleep(1.0)
                        auth.audit("cai_dat_sai_ma", who=("", ""))
                        st.error("Mã cài đặt không đúng.")
                    elif pw != pw2:
                        st.error("Hai lần nhập mật khẩu không khớp.")
                    elif not commit:
                        st.error("Cần đánh dấu cam kết sử dụng.")
                    else:
                        uid, err = auth.create_user(username, display, auth.ROLE_ADMIN, pw)
                        if err:
                            st.error(err)
                        else:
                            auth.audit("tao_quan_tri_dau_tien", who=(username.strip().lower(), auth.ROLE_ADMIN))
                            auth.login(auth.get_user(uid))
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
        st.caption("Nhận được cảnh báo? Bấm link trong tin nhắn để xác nhận, không cần đăng nhập.")


_user = auth.current_user()
if _user is None:
    _login_screen()
    st.stop()

# ------------------------------------------------------------------ menu theo vai trò
# (trang, tiêu đề, quyền cần có). Trang không có trong menu thì mở bằng URL cũng không tới được.
_PAGES = {
    "Giám sát": [
        ("views/live_view.py", "Trực tiếp", auth.MONITOR),
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
    if st.button("Đăng xuất", key="logout", width="stretch"):
        auth.logout()
        st.rerun()

nav.run()

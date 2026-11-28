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
            need_code = auth.setup_code_required(local=auth.local_setup_allowed())
            if need_code:
                st.caption("Tạo tài khoản quản trị gia đình. Nhập mã **SETUP_CODE** đã đặt trong "
                           "`.streamlit/secrets.toml` (trên Cloud: mục Secrets), để người lạ không chiếm được quyền "
                           "quản trị. Tạo xong thì không cần đến mã nữa.")
            else:
                st.caption("Chưa có tài khoản nào. **Người tạo tài khoản đầu tiên sẽ là quản trị gia đình**, sau đó tạo "
                           "hoặc duyệt tài khoản cho những người khác.")
            with st.form("first_setup"):
                code = st.text_input("Mã cài đặt", type="password") if need_code else ""
                username = st.text_input("Tên đăng nhập", placeholder="vd: an.nguyen")
                display = st.text_input("Tên hiển thị", placeholder="vd: Nguyễn Văn An (con trai)")
                pw = st.text_input("Mật khẩu (ít nhất 8 ký tự, có chữ và số)", type="password")
                pw2 = st.text_input("Nhập lại mật khẩu", type="password")
                commit = st.checkbox("Tôi cam kết chỉ dùng SafeWatch khi người được giám sát đã được giải thích và đồng "
                                     "ý; không lắp đặt bí mật; giữ kín mật khẩu.")
                if st.form_submit_button("Tạo tài khoản quản trị", type="primary"):
                    if need_code and not auth.check_setup_code(code):
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
                            auth.login(auth.authenticate(username, pw))  # ghi luôn lần đăng nhập đầu
                            st.rerun()
            return
        st.markdown("### SafeWatch")
        tab_in, tab_up = st.tabs(["Đăng nhập", "Đăng ký"])
        with tab_in, st.form("login", border=False):
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
        with tab_up:
            st.caption("Có **mã mời** từ quản trị gia đình thì nhập vào: dùng được ngay với đúng vai trò của mã. Không có "
                       "mã thì đăng ký vẫn được nhưng phải **chờ quản trị duyệt**." if auth.signup_enabled() else
                       "Cần **mã mời** từ quản trị gia đình để đăng ký.")
            with st.container():
                with st.form("signup", border=False, clear_on_submit=False):
                    r_code = st.text_input("Mã mời" + ("" if not auth.signup_enabled() else " (nếu có)"),
                                           placeholder="XXXX-XXXX-XXXX", key="su_code")
                    r_user = st.text_input("Tên đăng nhập", placeholder="vd: lan.nguyen", key="su_user")
                    r_name = st.text_input("Tên hiển thị", placeholder="vd: Nguyễn Thị Lan (con gái)", key="su_name")
                    r_pw = st.text_input("Mật khẩu (ít nhất 8 ký tự, có chữ và số)", type="password", key="su_pw")
                    r_pw2 = st.text_input("Nhập lại mật khẩu", type="password", key="su_pw2")
                    r_role = st.selectbox("Bạn muốn dùng SafeWatch với vai trò", [auth.ROLE_CAREGIVER, auth.ROLE_SUBJECT,
                                          auth.ROLE_ADMIN], format_func=lambda r: f"{auth.ROLE_NAMES[r]} — "
                                          f"{auth.ROLE_SUMMARY[r][0]}", key="su_role",
                                          help="Quản trị gia đình sẽ duyệt và có thể đổi vai trò. Có mã mời thì vai trò "
                                               "theo mã.")
                    if st.form_submit_button("Gửi yêu cầu đăng ký", type="primary", width="stretch"):
                        if r_pw != r_pw2:
                            st.error("Hai lần nhập mật khẩu không khớp.")
                        else:
                            time.sleep(0.5)
                            uid, err = auth.register(r_user, r_name, r_pw, ip=auth.client_ip(), invite=r_code,
                                                     requested_role=r_role)
                            if err:
                                st.error(err)
                            elif r_code.strip():
                                st.success("Đăng ký thành công. Đăng nhập ở thẻ **Đăng nhập** là dùng được ngay.")
                            else:
                                st.success("Đã gửi yêu cầu. Nhờ quản trị gia đình vào **Tài khoản & quyền** duyệt "
                                           "cho bạn, rồi đăng nhập ở thẻ Đăng nhập.")
        st.caption("Nhận được cảnh báo? Bấm link trong tin nhắn để xác nhận, không cần đăng nhập.")
        with st.container(border=True, key="swbox_roles_intro"):
            st.markdown("**Mỗi người một tài khoản, mỗi vai trò một quyền**")
            for role, (who_txt, can_txt) in auth.ROLE_SUMMARY.items():
                st.markdown(f"**{auth.ROLE_NAMES[role]}** · {who_txt}" + "  " + chr(10) + can_txt)
            st.caption("Chưa có tài khoản? Xin **mã mời** từ quản trị gia đình rồi bấm **Đăng ký**, hoặc đăng ký không "
                       "mã và chờ duyệt. Quên mật khẩu? Nhờ quản trị đặt lại. Sai 5 lần liên tiếp thì tài khoản tạm "
                       "khoá 5 phút.")


_user = auth.current_user()
if _user is None:
    _login_screen()
    st.stop()

if _user["role"] == auth.ROLE_PENDING:  # đã đăng ký, chưa được duyệt: không thấy gì của gia đình
    _, mid, _ = st.columns([1, 1.3, 1])
    with mid:
        st.markdown("### Đang chờ duyệt")
        st.info(f"Chào {_user['display_name']}. Tài khoản của bạn đã đăng ký nhưng **quản trị gia đình chưa duyệt**. "
                "Khi được duyệt và chọn vai trò, bạn đăng nhập lại là dùng được.")
        if st.button("Đăng xuất", width="stretch"):
            auth.logout()
            st.rerun()
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
    if auth.role_can(_user["role"], auth.MANAGE_USERS) and auth.list_pending():
        st.warning(f"{len(auth.list_pending())} tài khoản đăng ký đang chờ duyệt")
        st.page_link("views/users.py", label="Duyệt ở Tài khoản & quyền")
    with st.popover("Quyền của tôi", width="stretch"):
        st.markdown(f"**{auth.ROLE_NAMES[_user['role']]}** — {auth.ROLE_SUMMARY[_user['role']][1]}")
        st.markdown(chr(10).join(f"- {'✅' if auth.role_can(_user['role'], p) else '⛔'} {text}"
                                 for p, text in auth.PERMISSION_LABELS))
        st.caption("Cần thêm quyền? Nhờ quản trị gia đình đổi vai trò ở trang Tài khoản & quyền.")
    if st.button("Đăng xuất", key="logout", width="stretch"):
        auth.logout()
        st.rerun()

nav.run()

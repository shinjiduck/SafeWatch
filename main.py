"""Entry point của SafeWatch — nhiều trang qua st.navigation, menu chia nhóm theo việc người dùng cần làm:

  Giám sát  : Trực tiếp · Cảnh báo · Nhật ký
  Thiết lập : Người liên hệ · Camera & lắp đặt · Cấu hình
  Báo cáo   : Tổng quan · Kiểm định
  Tài khoản : Hồ sơ

(app.py cũ vẫn giữ, chạy độc lập như bản demo 1 trang.) Chạy: streamlit run main.py
"""

import os

import streamlit as st

import notifier
import profile_store
from theme import APP_NAME, ack_page_html, inject_global_theme, render_sidebar_profile, sidebar_status_html

ROOT = os.path.dirname(os.path.abspath(__file__))

# Logo / favicon đi qua static serving (/app/static/...), không qua /media/: trên Streamlit Cloud, đường /media/ của
# server Starlette lỗi nén gzip ("Expected ASGI message 'http.response.start'") -> ảnh logo bị vỡ.
st.set_page_config(page_title=APP_NAME, page_icon="/app/static/brand/favicon.png", layout="wide")
inject_global_theme()
st.logo("/app/static/brand/logo_light.png", size="large", icon_image="/app/static/brand/logo_icon.png")


@st.cache_resource
def start_notifier():
    """1 bộ gửi cảnh báo nền cho cả tiến trình server — chạy cả khi không ai mở trang (xem notifier.py).
    Cấu hình kênh đọc từ secrets.toml."""
    notifier.init_db()
    config = notifier.load_config(st.secrets)
    dispatcher = notifier.Dispatcher(notifier.build_channels(config), public_base_url=config.get("PUBLIC_BASE_URL"))
    dispatcher.start()
    return dispatcher


notifier.RUNNING = start_notifier()

# Link xác nhận trong email / SMS / Telegram: <PUBLIC_BASE_URL>/?ack=<mã> -> trang xác nhận riêng (thay cho trang
# thường ở lần chạy này). Bỏ tham số khỏi URL để tải lại trang không xác nhận lần nữa.
_ack_view = None
_ack_token = st.query_params.get("ack")
if _ack_token:
    _first = notifier.ack(_ack_token, by="(link xác nhận)", via="web-link")
    _alert = notifier.get_alert_by_token(_ack_token)
    _ack_view = ("new" if _first else "already" if _alert else "invalid", _alert)
    st.query_params.clear()

if "user_name" not in st.session_state:
    st.session_state["user_name"] = profile_store.load_profile()["name"]

# Dùng emoji thay cho :material/...: — font icon Material không tải được trên máy demo.
pages = {
    "Giám sát": [
        st.Page("views/live_view.py", title="Trực tiếp", default=True),
        st.Page("views/alerts.py", title="Cảnh báo"),
        st.Page("views/history.py", title="Nhật ký"),
    ],
    "Thiết lập": [
        st.Page("views/emergency_contacts.py", title="Người liên hệ"),
        st.Page("views/camera_management.py", title="Camera & lắp đặt"),
        st.Page("views/settings.py", title="Cấu hình"),
    ],
    "Báo cáo": [
        st.Page("views/dashboard.py", title="Tổng quan"),
        st.Page("views/evaluation.py", title="Kiểm định"),
    ],
    "Tài khoản": [
        st.Page("views/account.py", title="Hồ sơ"),
    ],
}

nav = st.navigation(pages)

with st.sidebar:
    # Placeholder lưu vào session_state để views/live_view.py cập nhật LIÊN TỤC trong vòng lặp webcam (cùng 1
    # lần chạy script nên placeholder vẫn hợp lệ).
    st.session_state["sidebar_status_placeholder"] = st.empty()
    st.session_state["sidebar_status_placeholder"].markdown(
        sidebar_status_html(st.session_state.get("camera_online", False)), unsafe_allow_html=True
    )
    st.markdown("---")
    render_sidebar_profile(
        name=st.session_state.get("user_name", "Người dùng"),
        role=profile_store.load_profile()["role"],
    )

if _ack_view is not None:
    st.markdown(ack_page_html(*_ack_view), unsafe_allow_html=True)
    _, mid, _ = st.columns([1, 1.2, 1])
    mid.page_link("views/alerts.py", label="Xem tất cả cảnh báo")
    st.stop()

nav.run()

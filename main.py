"""Entry point của SafeWatch — nhiều trang qua st.navigation, menu chia nhóm theo việc người dùng cần làm:

  Giám sát  : Trực tiếp · Cảnh báo · Nhật ký
  Thiết lập : Người liên hệ · Camera & lắp đặt · Cấu hình
  Báo cáo   : Tổng quan · Kiểm định
  Tài khoản : Hồ sơ

(app.py cũ vẫn giữ, chạy độc lập như bản demo 1 trang.) Chạy: streamlit run main.py
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

import notifier  # noqa: E402
import profile_store  # noqa: E402
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

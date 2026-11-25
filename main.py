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
from theme import APP_NAME, inject_global_theme, render_sidebar_profile, sidebar_status_html

ROOT = os.path.dirname(os.path.abspath(__file__))

st.set_page_config(page_title=APP_NAME, page_icon="🛡️", layout="wide")
inject_global_theme()
st.logo(os.path.join(ROOT, "assets", "logo_dark_bg.png"), size="large", icon_image=os.path.join(ROOT, "assets", "logo_icon.png"))


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

# Link xác nhận trong email / SMS: <PUBLIC_BASE_URL>/?ack=<mã>
_ack_token = st.query_params.get("ack")
if _ack_token:
    if notifier.ack(_ack_token, by="(link xác nhận)", via="web-link"):
        st.success("✅ Đã ghi nhận: bạn đã nhận được cảnh báo. Cảm ơn bạn!")
    else:
        st.info("Cảnh báo này đã được xác nhận trước đó, hoặc mã xác nhận không hợp lệ.")
    st.query_params.clear()

if "user_name" not in st.session_state:
    st.session_state["user_name"] = profile_store.load_profile()["name"]

# Dùng emoji thay cho :material/...: — font icon Material không tải được trên máy demo.
pages = {
    "Giám sát": [
        st.Page("views/live_view.py", title="Trực tiếp", icon="🎥", default=True),
        st.Page("views/alerts.py", title="Cảnh báo", icon="🔔"),
        st.Page("views/history.py", title="Nhật ký", icon="📋"),
    ],
    "Thiết lập": [
        st.Page("views/emergency_contacts.py", title="Người liên hệ", icon="📞"),
        st.Page("views/camera_management.py", title="Camera & lắp đặt", icon="📷"),
        st.Page("views/settings.py", title="Cấu hình", icon="⚙️"),
    ],
    "Báo cáo": [
        st.Page("views/dashboard.py", title="Tổng quan", icon="📊"),
        st.Page("views/evaluation.py", title="Kiểm định", icon="🧪"),
    ],
    "Tài khoản": [
        st.Page("views/account.py", title="Hồ sơ", icon="👤"),
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

nav.run()

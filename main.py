"""Entry point mới của SafeWatch — multi-page qua st.navigation, thay cho
app.py (vẫn giữ nguyên, chạy độc lập như bản demo 1 trang đơn giản hơn).

Chạy: streamlit run main.py
"""

import streamlit as st

import notifier
import profile_store
from theme import APP_NAME, inject_global_theme, render_sidebar_brand, render_sidebar_profile, sidebar_status_html

st.set_page_config(page_title=APP_NAME, page_icon="🛡️", layout="wide")
inject_global_theme()


@st.cache_resource
def start_notifier():
    """1 bộ gửi cảnh báo nền cho cả tiến trình server — chạy cả khi không ai
    mở trang (xem notifier.py). Cấu hình kênh đọc từ secrets.toml."""
    notifier.init_db()
    config = notifier.load_config(st.secrets)
    dispatcher = notifier.Dispatcher(notifier.build_channels(config), public_base_url=config.get("PUBLIC_BASE_URL"))
    dispatcher.start()
    return dispatcher


notifier.RUNNING = start_notifier()

# Link xác nhận trong email: <PUBLIC_BASE_URL>/?ack=<mã>
_ack_token = st.query_params.get("ack")
if _ack_token:
    if notifier.ack(_ack_token, by="(link email)", via="web-link"):
        st.success("Đã ghi nhận: bạn đã nhận được cảnh báo. Cảm ơn bạn!")
    else:
        st.info("Cảnh báo này đã được xác nhận trước đó, hoặc mã xác nhận không hợp lệ.")
    st.query_params.clear()

if "user_name" not in st.session_state:
    st.session_state["user_name"] = profile_store.load_profile()["name"]

with st.sidebar:
    render_sidebar_brand()

# Dùng emoji thay vì cú pháp :material/...: — font icon Material Symbols
# không load được trên máy này (kể cả icon nội bộ của Streamlit cũng bị lỗi
# hiện chữ thô), emoji thì luôn hiện đúng vì không phụ thuộc font ngoài.
pages = [
    st.Page("views/live_view.py", title="Trang chủ", icon="🏠", default=True),
    st.Page("views/alerts.py", title="Cảnh báo & xác nhận", icon="🔔"),
    st.Page("views/history.py", title="Lịch sử sự cố", icon="📋"),
    st.Page("views/dashboard.py", title="Dashboard", icon="📊"),
    st.Page("views/camera_management.py", title="Quản lý camera", icon="📷"),
    st.Page("views/emergency_contacts.py", title="Người liên hệ khẩn cấp", icon="📞"),
    st.Page("views/settings.py", title="Cấu hình", icon="⚙️"),
    st.Page("views/account.py", title="Tài khoản của tôi", icon="👤"),
    st.Page("views/logout.py", title="Đăng xuất", icon="🚪"),
]

nav = st.navigation(pages)

with st.sidebar:
    render_sidebar_profile(
        name=st.session_state.get("user_name", "Người dùng"),
        role=profile_store.load_profile()["role"],
    )
    # Placeholder này được lưu vào session_state để views/live_view.py lấy
    # lại và cập nhật LIÊN TỤC trong vòng lặp webcam của nó (cùng 1 script
    # đang chạy, nên placeholder vẫn hợp lệ) — sửa lỗi sidebar báo "Hệ
    # thống ngưng" dù camera đang live.
    st.session_state["sidebar_status_placeholder"] = st.empty()
    st.session_state["sidebar_status_placeholder"].markdown(
        sidebar_status_html(st.session_state.get("camera_online", False)), unsafe_allow_html=True
    )

nav.run()

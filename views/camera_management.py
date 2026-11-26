"""Trang Camera & lắp đặt — camera đang dùng, cài đặt hình ảnh (gom từ trang Cấu hình về đây cho đúng chỗ) và
hướng dẫn đặt camera. Bản demo chỉ có 1 camera: webcam của trình duyệt đang mở trang."""

import streamlit as st

import detection_engine as engine
from theme import badge_html, card, page_header, rows_html, section, steps_html

engine.ensure_settings_defaults()
page_header("Camera & lắp đặt", "Camera đang dùng, cài đặt hình ảnh và cách đặt camera để phát hiện ngã tốt nhất.", icon="📷")

s = st.session_state
online = s.get("camera_online", False)

left, right = st.columns([3, 2], gap="large")
with left:
    with card("cam_info"):
        c1, c2 = st.columns([3, 1], vertical_alignment="center")
        c1.markdown("**Camera 1 — Webcam của bạn**")
        c2.markdown(badge_html("safe", "Đang giám sát") if online else badge_html("idle", "Chưa bật"),
                    unsafe_allow_html=True)
        st.markdown(
            rows_html([
                ("Nguồn", "Webcam qua trình duyệt (WebRTC)"),
                ("Độ phân giải", s["camera_resolution"]),
                ("Phát hiện ngã", "Bật" if s["enable_fall"] else "Tắt"),
                ("Cử chỉ tay", "Bật" if s["enable_hand"] else "Tắt"),
                ("Theo dõi nhiều người", "Bật (thử nghiệm)" if s.get("multi_person") else "Tắt"),
            ]),
            unsafe_allow_html=True,
        )
        st.page_link("views/live_view.py", label="Mở giám sát trực tiếp")
    st.caption("Bản demo dùng 1 camera. Thêm IP camera / nhiều camera cần phần thu hình riêng — chưa hỗ trợ.")

    section("Cài đặt hình ảnh")
    with card("cam_settings"):
        s["camera_resolution"] = st.selectbox(
            "Độ phân giải", list(engine.CAMERA_RESOLUTIONS), index=list(engine.CAMERA_RESOLUTIONS).index(s["camera_resolution"]),
            help="640x480 là đủ cho phát hiện ngã; cao hơn tốn CPU hơn.",
        )
        s["mirror_camera"] = st.toggle("Lật ngang hình (như soi gương)", value=s["mirror_camera"])
        s["show_overlay"] = st.toggle("Vẽ khung xương lên video", value=s["show_overlay"])
        st.caption("Áp dụng khi bấm Dừng rồi Bắt đầu lại ở trang Trực tiếp.")

with right:
    section("Đặt camera thế nào")
    with card("cam_guide"):
        st.markdown(
            steps_html([
                ("Cao khoảng 2 m, chếch xuống", "Nhìn từ trên xuống thấy rõ người đứng lẫn người nằm."),
                ("Ở góc phòng, cách chỗ hay đi lại ~3 m", "Thấy được toàn thân — đứng quá gần sẽ bị nhắc lùi ra."),
                ("Vùng sàn không bị giường / bàn / sofa che", "Che vùng sàn làm bỏ sót nhiều ca ngã nhất."),
                ("Đủ sáng, tránh ngược sáng cửa sổ", "Ngược sáng làm khung xương chập chờn."),
                ("Cửa ra vào không nằm giữa khung hình", "Người đi khuất giữa khung dễ bị nghi ngã khuất."),
            ]),
            unsafe_allow_html=True,
        )
    st.info("Không có camera đặt cao? Dùng điện thoại làm webcam (DroidCam / Iriun) đặt lên tủ.")

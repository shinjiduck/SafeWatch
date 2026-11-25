"""Trang Tài khoản của tôi — demo không có auth thật (không có đăng nhập/
đăng ký/nhiều user), nên đây là 1 hồ sơ tĩnh duy nhất lưu vào file JSON."""

import streamlit as st

import detection_engine as engine
import profile_store
from theme import page_header, section

engine.ensure_settings_defaults()

page_header("Hồ sơ", "Thông tin của người được giám sát — gửi kèm khi cần hỗ trợ.")

profile = profile_store.load_profile()

with st.form("profile_form"):
    section("Thông tin cá nhân")
    c1, c2 = st.columns(2)
    with c1:
        name = st.text_input("Họ và tên", value=profile["name"])
        email = st.text_input("Email", value=profile["email"])
        phone = st.text_input("Số điện thoại", value=profile["phone"])
    with c2:
        birth_date = st.text_input("Ngày sinh", value=profile["birth_date"])
        address = st.text_input("Địa chỉ", value=profile["address"])
        role = st.selectbox(
            "Vai trò tài khoản",
            ["Người dùng cá nhân", "Người thân / Người giám hộ", "Quản trị viên"],
            index=["Người dùng cá nhân", "Người thân / Người giám hộ", "Quản trị viên"].index(profile["role"])
            if profile["role"] in ["Người dùng cá nhân", "Người thân / Người giám hộ", "Quản trị viên"]
            else 0,
        )

    section("Thông tin an toàn")
    health_notes = st.text_area("Ghi chú sức khoẻ (bệnh nền, thuốc đang dùng...)", value=profile["health_notes"])
    watch_area = st.text_input("Khu vực giám sát chính", value=profile["watch_area"])

    if st.form_submit_button("💾 Lưu thay đổi"):
        profile_store.save_profile(
            {
                "name": name,
                "email": email,
                "phone": phone,
                "birth_date": birth_date,
                "address": address,
                "role": role,
                "health_notes": health_notes,
                "watch_area": watch_area,
            }
        )
        st.session_state["user_name"] = name
        st.success("Đã lưu hồ sơ.")
        st.rerun()

st.caption("Đăng nhập, đổi mật khẩu, xác thực 2 bước: chưa có trong bản demo (1 hồ sơ duy nhất, lưu trên máy).")

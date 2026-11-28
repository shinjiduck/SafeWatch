"""Trang Hồ sơ người được giám sát — gửi kèm khi cần hỗ trợ. Hồ sơ (có ghi chú sức khoẻ) được mã hoá khi lưu
(profile_store). Ai đăng nhập cũng xem được; chỉ quản trị và chính người được giám sát sửa được."""

import streamlit as st

import auth
import detection_engine as engine
import profile_store
from theme import page_header, section

auth.require(auth.VIEW_PROFILE)
engine.ensure_settings_defaults()
CAN_EDIT = auth.can(auth.EDIT_PROFILE)

page_header("Hồ sơ", "Thông tin của người được giám sát — dùng trong email cảnh báo và khi cần hỗ trợ. Lưu mã hoá.",
            icon="👤")
if not CAN_EDIT:
    st.info("Bạn đang xem. Chỉ quản trị gia đình hoặc chính người được giám sát sửa được hồ sơ.")

profile = profile_store.load_profile()

with st.form("profile_form"):
    section("Thông tin cá nhân")
    c1, c2 = st.columns(2)
    with c1:
        name = st.text_input("Họ và tên", value=profile["name"], disabled=not CAN_EDIT)
        email = st.text_input("Email", value=profile["email"], disabled=not CAN_EDIT)
        phone = st.text_input("Số điện thoại", value=profile["phone"], disabled=not CAN_EDIT)
    with c2:
        birth_date = st.text_input("Ngày sinh", value=profile["birth_date"], disabled=not CAN_EDIT)
        address = st.text_input("Địa chỉ", value=profile["address"], disabled=not CAN_EDIT)
        watch_area = st.text_input("Khu vực giám sát chính", value=profile["watch_area"], disabled=not CAN_EDIT)

    section("Thông tin an toàn")
    health_notes = st.text_area("Ghi chú sức khoẻ (bệnh nền, thuốc đang dùng...)", value=profile["health_notes"],
                                disabled=not CAN_EDIT)

    if st.form_submit_button("Lưu thay đổi", type="primary", disabled=not CAN_EDIT):
        auth.require(auth.EDIT_PROFILE)
        profile_store.save_profile({"name": name, "email": email, "phone": phone, "birth_date": birth_date,
                                    "address": address, "health_notes": health_notes, "watch_area": watch_area})
        auth.audit("sua_ho_so")
        st.success("Đã lưu hồ sơ (mã hoá).")
        st.rerun()

st.caption("Tài khoản đăng nhập, đổi mật khẩu, vai trò: trang Tài khoản & quyền.")

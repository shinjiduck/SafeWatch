"""Trang Người liên hệ khẩn cấp — CRUD thật (lưu SQLite qua contacts.py).
Thứ tự ưu tiên quyết định ai nhận cảnh báo trước và ai được chuyển tiếp khi
người trước chưa xác nhận (xem notifier.py). Kênh gửi thật: Telegram (cần
Chat ID) và Email."""

import streamlit as st

import contacts
from theme import badge_html, card, empty_html, page_header, rows_html

contacts.init_db()

page_header(
    "Người liên hệ",
    "Cảnh báo gửi tới người ưu tiên 1 trước; chưa ai xác nhận thì gửi lại và chuyển tiếp lần lượt cho người kế "
    "tiếp. Nhận qua Telegram: nhắn /start cho bot của hệ thống để lấy Chat ID.",
    icon="📞",
)

rows = contacts.get_contacts()
with st.expander("+ Thêm người liên hệ", expanded=not rows):
    with st.form("add_contact_form", clear_on_submit=True):
        c1, c2 = st.columns(2)
        with c1:
            name = st.text_input("Họ và tên")
            relationship = st.selectbox("Quan hệ", ["Người thân chính", "Người giám hộ", "Cơ sở y tế", "Khác"])
            telegram_chat_id = st.text_input("Telegram Chat ID", help="Nhắn /start cho bot để nhận Chat ID.")
        with c2:
            phone = st.text_input("Số điện thoại")
            email = st.text_input("Email")
        priority = st.slider("Mức ưu tiên (1 = ưu tiên cao nhất)", 1, 5, 1)
        submitted = st.form_submit_button("Lưu người liên hệ", type="primary")
        if submitted:
            if not name or not phone:
                st.error("Cần ít nhất Họ tên và Số điện thoại.")
            else:
                contacts.add_contact(name, relationship, phone, email, priority, telegram_chat_id.strip())
                st.success(f"Đã thêm {name}.")
                st.rerun()

if not rows:
    st.markdown(empty_html("Chưa có ai nhận cảnh báo", "Thêm ít nhất 1 người thân ở mục “Thêm người liên hệ” phía "
                           "trên. Không có người nhận thì cảnh báo không tới được ai.", icon="users", tone="rose"),
                unsafe_allow_html=True)
else:
    for contact_id, name, relationship, phone, email, priority, notify_enabled, telegram_chat_id in rows:
        with card(f"contact_{contact_id}"):
            col1, col2, col3 = st.columns([3, 2, 1])
            with col1:
                kenh = [k for k, v in (("Telegram", telegram_chat_id), ("Email", email), ("SMS", phone)) if v]
                chips = (" ".join(badge_html("safe" if notify_enabled else "idle", k) for k in kenh)
                         or badge_html("emergency", "Chưa có kênh nhận"))
                st.markdown(
                    f'<div class="sw-alert-head"><span class="sw-alert-kind">{name}</span>'
                    f'{badge_html("info", f"Ưu tiên {priority}")}</div>'
                    f'<div class="sw-alert-meta">{relationship or "—"}</div><div style="margin-top:.6rem">{chips}</div>',
                    unsafe_allow_html=True,
                )
            with col2:
                st.markdown(rows_html([("Điện thoại", phone or "—"), ("Email", email or "—")]), unsafe_allow_html=True)
                new_chat_id = st.text_input(
                    "Telegram Chat ID", value=telegram_chat_id or "", key=f"tg_{contact_id}", label_visibility="collapsed",
                    placeholder="Telegram Chat ID",
                )
                if new_chat_id.strip() != (telegram_chat_id or ""):
                    contacts.set_telegram_chat_id(contact_id, new_chat_id.strip())
                    st.rerun()
            with col3:
                new_enabled = st.toggle("Nhận cảnh báo", value=bool(notify_enabled), key=f"notify_{contact_id}")
                if new_enabled != bool(notify_enabled):
                    contacts.set_notify_enabled(contact_id, new_enabled)
                    st.rerun()
                if st.button("Xoá", key=f"delete_{contact_id}"):
                    contacts.delete_contact(contact_id)
                    st.rerun()

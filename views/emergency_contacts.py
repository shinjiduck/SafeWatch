"""Trang Người liên hệ khẩn cấp — thêm / sửa / xoá thật (lưu SQLite qua contacts.py).
Thứ tự ưu tiên quyết định ai nhận cảnh báo trước và ai được chuyển tiếp khi người trước chưa xác nhận
(xem notifier.py). Kênh gửi: Telegram (cần Chat ID), Email, SMS (số điện thoại)."""

import re
from html import escape

import streamlit as st

import auth
import contacts
from secure_store import mask
from theme import badge_html, card, empty_html, page_header, rows_html

auth.require(auth.VIEW_CONTACTS)
contacts.init_db()
CAN_EDIT = auth.can(auth.EDIT_CONTACTS)  # chỉ quản trị thêm / sửa / xoá; vai trò khác chỉ xem (số đã che bớt)

RELATIONSHIPS = ["Người thân chính", "Người giám hộ", "Cơ sở y tế", "Khác"]
EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
PHONE_RE = re.compile(r"^\+?[\d\s.\-()]{8,20}$")
KEYS = ["id", "name", "relationship", "phone", "email", "priority", "notify_enabled", "telegram_chat_id"]

page_header(
    "Người liên hệ",
    "Cảnh báo gửi tới người ưu tiên 1 trước; chưa ai xác nhận thì gửi lại và chuyển tiếp lần lượt cho người kế "
    "tiếp. Nhận qua Telegram: nhắn /start cho bot của hệ thống để lấy Chat ID.",
    icon="📞",
)

s = st.session_state
_flash = s.pop("_contacts_flash", None)
if _flash:
    st.toast(_flash, icon="✅")


def validate(name, phone, email, telegram_chat_id):
    """Danh sách lỗi nhập liệu (rỗng = hợp lệ)."""
    errors = []
    if not name.strip():
        errors.append("Cần nhập họ và tên.")
    if not phone.strip():
        errors.append("Cần nhập số điện thoại.")
    elif not PHONE_RE.match(phone.strip()):
        errors.append("Số điện thoại chưa đúng dạng (VD: 0912 345 678 hoặc +84912345678).")
    if email.strip() and not EMAIL_RE.match(email.strip()):
        errors.append("Email chưa đúng dạng (VD: ten@gmail.com).")
    if telegram_chat_id.strip() and not re.fullmatch(r"-?\d{5,20}", telegram_chat_id.strip()):
        errors.append("Telegram Chat ID chỉ gồm chữ số (Chat ID của nhóm có dấu - ở đầu).")
    return errors


def contact_fields(prefix, current=None):
    """Các ô nhập dùng chung cho form Thêm và form Sửa. current = người liên hệ đang sửa (dict)."""
    cur = current or {}
    rel = cur.get("relationship")
    options = RELATIONSHIPS + ([rel] if rel and rel not in RELATIONSHIPS else [])
    c1, c2 = st.columns(2)
    with c1:
        name = st.text_input("Họ và tên", value=cur.get("name", ""), key=f"{prefix}_name")
        relationship = st.selectbox("Quan hệ", options, index=options.index(rel) if rel in options else 0,
                                    key=f"{prefix}_rel")
        telegram_chat_id = st.text_input("Telegram Chat ID", value=cur.get("telegram_chat_id") or "", key=f"{prefix}_tg",
                                         help="Nhắn /start cho bot SafeWatch để nhận Chat ID.")
    with c2:
        phone = st.text_input("Số điện thoại", value=cur.get("phone") or "", key=f"{prefix}_phone")
        email = st.text_input("Email", value=cur.get("email") or "", key=f"{prefix}_email")
        priority = st.slider("Mức ưu tiên (1 = nhận cảnh báo đầu tiên)", 1, 5, int(cur.get("priority") or 1),
                             key=f"{prefix}_prio")
    return name, relationship, phone, email, priority, telegram_chat_id


# ------------------------------------------------------------------ thêm người liên hệ
rows = contacts.get_contacts()
if CAN_EDIT:
    with st.expander("+ Thêm người liên hệ", expanded=not rows):
        with st.form("add_contact_form", clear_on_submit=True):
            name, relationship, phone, email, priority, tg = contact_fields("add")
            if st.form_submit_button("Lưu người liên hệ", type="primary"):
                auth.require(auth.EDIT_CONTACTS)
                errors = validate(name, phone, email, tg)
                if errors:
                    for e in errors:
                        st.error(e)
                else:
                    contacts.add_contact(name.strip(), relationship, phone.strip(), email.strip(), priority,
                                         tg.strip())
                    auth.audit("them_nguoi_lien_he", name.strip())
                    s["_contacts_flash"] = f"Đã thêm {name.strip()}."
                    st.rerun()
else:
    st.info("Bạn đang xem. Chỉ quản trị gia đình thêm / sửa / xoá được người liên hệ; số điện thoại và email đã được "
            "che bớt.")

if not rows:
    st.markdown(empty_html("Chưa có ai nhận cảnh báo", "Thêm ít nhất 1 người thân ở mục “Thêm người liên hệ” phía "
                           "trên. Không có người nhận thì cảnh báo không tới được ai.", icon="users", tone="rose"),
                unsafe_allow_html=True)


def show_edit(c):
    """Form sửa toàn bộ thông tin, điền sẵn giá trị hiện tại."""
    cid = c["id"]
    st.markdown(f'<div class="sw-alert-kind">Sửa thông tin: {escape(c["name"])}</div>', unsafe_allow_html=True)
    with st.form(f"edit_contact_{cid}"):
        name, relationship, phone, email, priority, tg = contact_fields(f"edit{cid}", c)
        b1, b2, _ = st.columns([1.3, 1, 3])
        save = b1.form_submit_button("Lưu thay đổi", type="primary", width="stretch")
        cancel = b2.form_submit_button("Huỷ", width="stretch")
    if save:
        auth.require(auth.EDIT_CONTACTS)
        errors = validate(name, phone, email, tg)
        if errors:
            for e in errors:
                st.error(e)
            return
        contacts.update_contact(cid, name.strip(), relationship, phone.strip(), email.strip(), priority, tg.strip())
        auth.audit("sua_nguoi_lien_he", name.strip())
        s.pop("_editing_contact", None)
        s["_contacts_flash"] = f"Đã lưu thay đổi cho {name.strip()}."
        st.rerun()
    if cancel:
        s.pop("_editing_contact", None)
        st.rerun()


def show_view(c):
    """Thông tin 1 người liên hệ + bật/tắt nhận cảnh báo + Sửa / Xoá (xoá phải xác nhận)."""
    cid = c["id"]
    col1, col2, col3 = st.columns([3, 2.2, 1.4])
    with col1:
        kenh = [k for k, v in (("Telegram", c["telegram_chat_id"]), ("Email", c["email"]), ("SMS", c["phone"])) if v]
        chips = (" ".join(badge_html("safe" if c["notify_enabled"] else "idle", k) for k in kenh)
                 or badge_html("emergency", "Chưa có kênh nhận"))
        prio = badge_html("info", f"Ưu tiên {c['priority']}")
        st.markdown(
            f'<div class="sw-alert-head"><span class="sw-alert-kind">{escape(c["name"])}</span>{prio}</div>'
            f'<div class="sw-alert-meta">{escape(c["relationship"] or "—")}</div>'
            f'<div style="margin-top:.6rem">{chips}</div>',
            unsafe_allow_html=True,
        )
    with col2:
        show = (lambda v: v) if CAN_EDIT else mask
        st.markdown(rows_html([("Điện thoại", escape(show(c["phone"]) or "—")), ("Email", escape(show(c["email"]) or "—")),
                               ("Telegram", escape(show(c["telegram_chat_id"]) or "Chưa có"))]), unsafe_allow_html=True)
    with col3:
        if not CAN_EDIT:
            st.caption("Đang nhận cảnh báo" if c["notify_enabled"] else "Đã tắt nhận cảnh báo")
            return
        new_enabled = st.toggle("Nhận cảnh báo", value=bool(c["notify_enabled"]), key=f"notify_{cid}")
        if new_enabled != bool(c["notify_enabled"]):
            auth.require(auth.EDIT_CONTACTS)
            contacts.set_notify_enabled(cid, new_enabled)
            auth.audit("bat_tat_nhan_canh_bao", f"{c['name']}: {'bật' if new_enabled else 'tắt'}")
            s["_contacts_flash"] = f"Đã {'bật' if new_enabled else 'tắt'} nhận cảnh báo cho {c['name']}."
            st.rerun()
        if s.get("_deleting_contact") == cid:
            st.caption(f"Xoá {c['name']}? Không hoàn tác được.")
            y, n = st.columns(2)
            if y.button("Xoá", key=f"confirm_del_{cid}", type="primary", width="stretch"):
                auth.require(auth.EDIT_CONTACTS)
                contacts.delete_contact(cid)
                auth.audit("xoa_nguoi_lien_he", c["name"])
                s.pop("_deleting_contact", None)
                s["_contacts_flash"] = f"Đã xoá {c['name']}."
                st.rerun()
            if n.button("Huỷ", key=f"cancel_del_{cid}", width="stretch"):
                s.pop("_deleting_contact", None)
                st.rerun()
        else:
            e1, e2 = st.columns(2)
            if e1.button("Sửa", key=f"edit_{cid}", width="stretch"):
                s["_editing_contact"] = cid
                s.pop("_deleting_contact", None)
                st.rerun()
            if e2.button("Xoá", key=f"delete_{cid}", width="stretch"):
                s["_deleting_contact"] = cid
                s.pop("_editing_contact", None)
                st.rerun()


for row in rows:
    contact = dict(zip(KEYS, row))
    with card(f"contact_{contact['id']}"):
        if CAN_EDIT and s.get("_editing_contact") == contact["id"]:
            show_edit(contact)
        else:
            show_view(contact)

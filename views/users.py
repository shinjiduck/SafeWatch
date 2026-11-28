"""Trang Tài khoản & quyền — ai cũng đổi được mật khẩu / PIN của mình; quản trị tạo, khoá, đổi vai trò, đặt lại
mật khẩu. Luôn còn ít nhất 1 quản trị (auth.set_role / set_disabled chặn). Mọi thay đổi vào nhật ký truy cập."""

from datetime import datetime
from html import escape

import pandas as pd
import streamlit as st

import auth
from theme import card, page_header, section

me = auth.current_user()
page_header("Tài khoản & quyền", f"Đăng nhập: {escape(me['display_name'])} · {auth.ROLE_NAMES[me['role']]}",
            icon="👤")
s = st.session_state
_flash = s.pop("_users_flash", None)
if _flash:
    st.toast(_flash, icon="✅")

section("Đổi mật khẩu của tôi")
with card("own_pw"), st.form("own_pw_form", clear_on_submit=True, border=False):
    old = st.text_input("Mật khẩu / PIN hiện tại", type="password")
    new = st.text_input("Mật khẩu / PIN mới" + (" (PIN 6 số hoặc mật khẩu)" if me["role"] == auth.ROLE_SUBJECT
                                                 else " (ít nhất 8 ký tự, có chữ và số)"), type="password")
    new2 = st.text_input("Nhập lại", type="password")
    if st.form_submit_button("Đổi mật khẩu", type="primary"):
        if new != new2:
            st.error("Hai lần nhập không khớp.")
        else:
            err = auth.set_secret(me["id"], new, actor=auth.who(), old_secret=old)
            if err:
                st.error(err)
            else:
                s["_users_flash"] = "Đã đổi mật khẩu."
                st.rerun()

section("Quyền của từng vai trò")
with card("perm_matrix"):
    labels = auth.PERMISSION_LABELS
    st.dataframe(pd.DataFrame([{"Việc": text, **{name: "✓" if auth.role_can(r, p) else "—"
                                                 for r, name in auth.ROLE_NAMES.items()}} for p, text in labels]),
                 hide_index=True, width="stretch")
    st.caption("Người chăm sóc không xoá được lịch sử, để không ai che giấu được một sự cố.")

if not auth.can(auth.MANAGE_USERS):
    st.stop()

section("Tạo tài khoản")
with card("new_user"), st.form("new_user_form", clear_on_submit=True, border=False):
    c1, c2 = st.columns(2)
    username = c1.text_input("Tên đăng nhập", placeholder="vd: lan.nguyen")
    display = c2.text_input("Tên hiển thị", placeholder="vd: Nguyễn Thị Lan (con gái)")
    role = c1.selectbox("Vai trò", list(auth.ROLE_NAMES), format_func=auth.ROLE_NAMES.get, index=1)
    pw = c2.text_input("Mật khẩu ban đầu (người được giám sát: PIN 6 số)", type="password")
    if st.form_submit_button("Tạo tài khoản", type="primary"):
        auth.require(auth.MANAGE_USERS)
        uid, err = auth.create_user(username, display, role, pw)
        if err:
            st.error(err)
        else:
            auth.audit("tao_tai_khoan", f"{username.strip().lower()} · {auth.ROLE_NAMES[role]}")
            s["_users_flash"] = f"Đã tạo tài khoản {username.strip().lower()}."
            st.rerun()

section("Danh sách tài khoản")
for u in auth.list_users():
    with card(f"user_{u['id']}"):
        c1, c2, c3 = st.columns([2.2, 2, 2.4], vertical_alignment="center")
        last = datetime.fromtimestamp(u["last_login"]).strftime("%H:%M %d/%m/%Y") if u["last_login"] else "chưa"
        c1.markdown(f"**{escape(u['display_name'])}**  \n`{escape(u['username'])}` · đăng nhập gần nhất: {last}"
                    + ("  \n:red[Đã khoá]" if u["disabled"] else ""))
        new_role = c2.selectbox("Vai trò", list(auth.ROLE_NAMES), index=list(auth.ROLE_NAMES).index(u["role"]),
                                format_func=auth.ROLE_NAMES.get, key=f"role_{u['id']}", label_visibility="collapsed",
                                disabled=u["id"] == me["id"],
                                help="Không tự đổi vai trò của chính mình (tránh tự khoá quyền quản trị).")
        if new_role != u["role"]:
            auth.require(auth.MANAGE_USERS)
            err = auth.set_role(u["id"], new_role, actor=auth.who())
            if err:
                st.error(err)
            else:
                s["_users_flash"] = "Đã đổi vai trò."
                st.rerun()
        with c3:
            b1, b2 = st.columns(2)
            if b1.button("Mở khoá" if u["disabled"] else "Khoá", key=f"lock_{u['id']}", width="stretch",
                         disabled=u["id"] == me["id"]):
                auth.require(auth.MANAGE_USERS)
                err = auth.set_disabled(u["id"], not u["disabled"], actor=auth.who())
                if err:
                    st.error(err)
                else:
                    s["_users_flash"] = "Đã mở khoá." if u["disabled"] else "Đã khoá tài khoản."
                    st.rerun()
            with b2.popover("Đặt lại mật khẩu", width="stretch"):
                with st.form(f"reset_{u['id']}", clear_on_submit=True, border=False):
                    npw = st.text_input("Mật khẩu / PIN mới", type="password")
                    if st.form_submit_button("Lưu"):
                        auth.require(auth.MANAGE_USERS)
                        err = auth.set_secret(u["id"], npw, actor=auth.who())
                        if err:
                            st.error(err)
                        else:
                            st.success("Đã đặt lại. Gửi mật khẩu mới cho người đó qua kênh riêng.")

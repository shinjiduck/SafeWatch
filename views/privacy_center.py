"""Trang Quyền riêng tư — minh chứng cho yêu cầu "Bảo vệ video người dùng": sơ đồ dữ liệu, sự đồng ý, tạm dừng,
hạn lưu, xoá dữ liệu (4 mức), nhật ký truy cập, cách bảo vệ dữ liệu. Thao tác nào cũng kiểm tra quyền (auth)."""

from datetime import date, datetime, timedelta
from html import escape

import pandas as pd
import streamlit as st

import auth
import privacy
from theme import card, page_header, section

me = auth.current_user()
s = st.session_state
page_header("Quyền riêng tư", "Dữ liệu nào được xử lý, lưu ở đâu, bao lâu, ai xem và xoá được. " + privacy.DISCLAIMER,
            icon="🛡️")
_flash = s.pop("_privacy_flash", None)
if _flash:
    st.success(_flash)

# ------------------------------------------------------------------ 1. sơ đồ dữ liệu
section("Dữ liệu đi đâu")
with card("flow"):
    st.graphviz_chart("""
digraph G {
  rankdir=LR; bgcolor="transparent"; node [shape=box, style="rounded", fontname="Helvetica", fontsize=11];
  cam [label="Camera\\ntrong phòng"]; br [label="Trình duyệt\\n(WebRTC)"];
  subgraph cluster_x { label="Nơi xử lý: máy tại nhà hoặc máy chủ Cloud"; style="dashed"; fontsize=10;
    ai [label="Xử lý trong bộ nhớ\\nkhung xương + mô hình\\nẢNH BỊ BỎ NGAY"]; ev [label="Sự kiện dạng chữ"];
    db [label="Cơ sở dữ liệu\\nchữ, trường nhạy cảm mã hoá\\ncó hạn lưu, có xoá", style="rounded,bold"];
    tx [label="Bộ gửi cảnh báo"]; }
  fam [label="Người nhà\\n(chỉ nhận chữ + link)"];
  cam -> br -> ai -> ev -> db -> tx -> fam;
}""")
    st.dataframe(pd.DataFrame([
        ["Video / khung hình", "Bộ nhớ, lúc xử lý", "Không lưu", "Không ai"],
        ["Khung xương", "Bộ nhớ, cửa sổ 1,5 s", "Ghi đè liên tục", "Không ai"],
        ["Sự cố, trạng thái, cảnh báo, lần gửi", "events.db", f"{privacy.retention_days()} ngày rồi tự xoá",
         "Theo vai trò (trang Tài khoản & quyền)"],
        ["Người liên hệ (SĐT, email, Chat ID mã hoá)", "events.db", "Tới khi xoá", "Quản trị sửa; vai trò khác chỉ xem"],
        ["Hồ sơ, ghi chú sức khoẻ (mã hoá cả file)", "profile.json", "Tới khi xoá", "Quản trị, người được giám sát sửa"],
        ["Nhật ký truy cập (ai làm gì, lúc nào)", "events.db", f"{auth.AUDIT_RETENTION_DAYS} ngày", "Quản trị, người được giám sát"],
    ], columns=["Dữ liệu", "Ở đâu", "Giữ bao lâu", "Ai xem"]), hide_index=True, width="stretch")
    st.caption("Bản đặt tại nhà xử lý ngay trên máy: ảnh không rời nhà. Bản Streamlit Cloud gửi khung hình qua Internet "
               "(có mã hoá) lên máy chủ để xử lý, cũng không lưu.")

# ------------------------------------------------------------------ 2. sự đồng ý
section("Sự đồng ý giám sát")
with card("consent"):
    c = privacy.active_consent()
    if c:
        who_txt = (f"ghi thay bởi {escape(c['given_by'])} — lý do: {escape(c['reason'] or '')}" if c["on_behalf"]
                   else f"{escape(c['given_by'])} tự đồng ý")
        st.markdown(f"**Đang có hiệu lực** · {who_txt} · lúc {datetime.fromtimestamp(c['given_at']):%H:%M %d/%m/%Y}")
        if auth.can(auth.WITHDRAW_CONSENT):
            with st.popover("Rút lại sự đồng ý"):
                st.write("Giám sát dừng ngay. Muốn giám sát lại phải đồng ý lại ở trang Trực tiếp.")
                if st.button("Rút lại", type="primary", key="withdraw"):
                    auth.require(auth.WITHDRAW_CONSENT)
                    err = privacy.withdraw_consent(me)
                    if err:
                        st.error(err)
                    else:
                        s["_privacy_flash"] = "Đã rút lại sự đồng ý. Giám sát đã dừng."
                        st.rerun()
    else:
        st.markdown("**Chưa có sự đồng ý.** Không thể bắt đầu giám sát. Mở trang **Trực tiếp** để xem nội dung và đồng ý.")
    hist = privacy.consent_history(20)
    if hist:
        st.dataframe(pd.DataFrame([{
            "Lúc": datetime.fromtimestamp(h["given_at"]).strftime("%H:%M %d/%m/%Y"),
            "Ai": h["given_by"], "Cách": "Ghi thay" if h["on_behalf"] else "Tự đồng ý", "Lý do": h["reason"] or "",
            "Rút lại": datetime.fromtimestamp(h["withdrawn_at"]).strftime("%H:%M %d/%m/%Y") if h["withdrawn_at"] else "",
        } for h in hist]), hide_index=True, width="stretch")
    pu = privacy.pause_until()
    if pu:
        st.info(f"Đang tạm dừng giám sát vì riêng tư, tự bật lại lúc {datetime.fromtimestamp(pu):%H:%M}.")

# ------------------------------------------------------------------ 3. hạn lưu
section("Hạn lưu dữ liệu")
with card("retention"):
    days = privacy.retention_days()
    st.markdown(f"Dữ liệu sự cố, cảnh báo, lần gửi **cũ hơn {days} ngày tự xoá** (kiểm tra mỗi giờ). Cảnh báo đang chờ "
                "xác nhận không bị xoá.")
    if auth.can(auth.SET_RETENTION):
        c1, c2 = st.columns([3, 1])
        new_days = c1.slider("Hạn lưu (ngày)", privacy.RETENTION_MIN_DAYS, privacy.RETENTION_MAX_DAYS, days, step=1)
        if c2.button("Lưu và dọn ngay", width="stretch"):
            auth.require(auth.SET_RETENTION)
            privacy.set_retention_days(new_days)
            counts = privacy.prune()
            s["_privacy_flash"] = f"Hạn lưu {new_days} ngày. Đã dọn: {privacy._fmt(counts)}."
            st.rerun()

# ------------------------------------------------------------------ 4. xoá
section("Xoá dữ liệu")
with card("delete"):
    if not auth.can(auth.DELETE_HISTORY):
        st.markdown("Vai trò của bạn không xoá được dữ liệu. Quản trị hoặc người được giám sát mới xoá được, để không "
                    "ai che giấu được một sự cố.")
    else:
        st.caption("Xoá thật: dữ liệu bị ghi đè rồi dọn khỏi file, không khôi phục được. Xoá từng sự kiện: trang Nhật ký "
                   "hoặc Cảnh báo. Video: SafeWatch không lưu nên không có gì để xoá.")
        t_range, t_all, t_personal = st.tabs(["Theo khoảng ngày", "Toàn bộ lịch sử", "Toàn bộ dữ liệu cá nhân"])
        with t_range:
            c1, c2 = st.columns(2)
            d1 = c1.date_input("Từ ngày", value=date.today() - timedelta(days=7), format="DD/MM/YYYY")
            d2 = c2.date_input("Đến hết ngày", value=date.today(), format="DD/MM/YYYY")
            if d1 > d2:
                st.error("Ngày bắt đầu phải trước ngày kết thúc.")
            else:
                n = privacy.count_range(d1, d2)
                st.write(f"Sẽ xoá: {n['events']} sự cố, {n['status_log']} trạng thái, {n['alerts']} cảnh báo "
                         "(kèm các lần gửi).")
                if st.button("Xoá khoảng này", disabled=not any(n.values()), key="del_range"):
                    auth.require(auth.DELETE_HISTORY)
                    counts = privacy.delete_range(d1, d2, who=auth.who())
                    s["_privacy_flash"] = f"Đã xoá: {privacy._fmt(counts)}."
                    st.rerun()
        with t_all:
            ok1 = st.checkbox("Tôi hiểu: xoá toàn bộ sự cố, trạng thái, cảnh báo và lần gửi, không hoàn tác được.",
                              key="all_ok")
            typed = st.text_input("Gõ XOÁ để xác nhận", key="all_typed")
            if st.button("Xoá toàn bộ lịch sử", disabled=not (ok1 and typed.strip().upper() in ("XOÁ", "XÓA")),
                         key="del_all"):
                auth.require(auth.DELETE_HISTORY)
                counts = privacy.delete_all_history(who=auth.who())
                s["_privacy_flash"] = f"Đã xoá: {privacy._fmt(counts)}."
                st.rerun()
        with t_personal:
            if not auth.can(auth.DELETE_ALL):
                st.write("Chỉ quản trị và người được giám sát.")
            else:
                st.write("Xoá toàn bộ lịch sử + người liên hệ + hồ sơ sức khoẻ + các lần đồng ý + mọi tài khoản trừ quản "
                         "trị. Giám sát dừng (không còn sự đồng ý). Nhật ký truy cập được giữ để biết đã có lần xoá này.")
                ok2 = st.checkbox("Tôi hiểu: không hoàn tác được.", key="p_ok")
                typed2 = st.text_input("Gõ XOÁ để xác nhận", key="p_typed")
                pw = st.text_input("Nhập lại mật khẩu / PIN của bạn", type="password", key="p_pw")
                if st.button("Xoá toàn bộ dữ liệu cá nhân", type="primary",
                             disabled=not (ok2 and typed2.strip().upper() in ("XOÁ", "XÓA") and pw), key="del_personal"):
                    auth.require(auth.DELETE_ALL)
                    if auth.authenticate(me["username"], pw) is None:
                        st.error("Mật khẩu không đúng.")
                    else:
                        counts = privacy.delete_all_personal(who=auth.who())
                        s["_privacy_flash"] = f"Đã xoá: {privacy._fmt(counts)}."
                        st.rerun()

# ------------------------------------------------------------------ 5. nhật ký truy cập
if auth.can(auth.VIEW_AUDIT):
    section("Nhật ký truy cập")
    with card("audit"):
        rows = auth.get_audit(500)
        if not rows:
            st.write("Chưa có.")
        else:
            st.dataframe(pd.DataFrame([{
                "Lúc": datetime.fromtimestamp(r["at"]).strftime("%H:%M:%S %d/%m/%Y"), "Ai": r["username"] or "",
                "Vai trò": auth.ROLE_NAMES.get(r["role"], r["role"] or ""), "Việc": r["action"], "Chi tiết": r["detail"] or "",
            } for r in rows]), hide_index=True, width="stretch")
        st.caption("Không ai sửa hay xoá được nhật ký này từ giao diện; tự dọn sau "
                   f"{auth.AUDIT_RETENTION_DAYS} ngày. Không chứa nội dung dữ liệu.")

# ------------------------------------------------------------------ 6. bảo vệ dữ liệu
section("Dữ liệu được bảo vệ thế nào")
with card("protect"):
    import os

    try:
        in_secrets = bool(str(st.secrets.get("DATA_KEY", "")))
    except Exception:  # noqa: BLE001 — không có secrets.toml
        in_secrets = False
    key_src = ("biến môi trường" if os.environ.get("SAFEWATCH_DATA_KEY") else
               "secrets.toml" if in_secrets else "file khoá trên máy (data/.data_key)")
    st.markdown(f"""
- **Mật khẩu / PIN:** không lưu dạng gốc, băm bằng scrypt kèm salt riêng; sai 5 lần thì khoá 5 phút.
- **Trường nhạy cảm** (số điện thoại, email, Telegram Chat ID, hồ sơ sức khoẻ, địa chỉ gửi): mã hoá AES (Fernet).
  Khoá dữ liệu lấy từ: **{key_src}**.
- **Xoá thật:** SQLite `secure_delete` ghi đè số 0 lên dữ liệu bị xoá, rồi `VACUUM` dọn khỏi file.
- **Phân quyền** kiểm tra ở cả menu lẫn từng thao tác; bị từ chối cũng được ghi nhật ký.
- **Link xác nhận** trong tin nhắn chỉ xác nhận đúng 1 cảnh báo, hết hạn sau 24 giờ, không mở được phần còn lại.
- **Không lưu hình ảnh:** có ca kiểm thử tự động chứng minh mã không ghi ảnh hay video.
- Gợi ý dán biển “Khu vực có camera hỗ trợ an toàn” để khách / người giúp việc biết.
""")

if auth.can(auth.MANAGE_USERS):
    with st.expander("Dữ liệu mẫu để trình diễn"):
        st.caption("Thêm khoảng 20 sự cố mẫu trải trên 10 ngày (ghi rõ là mẫu), để thử xoá theo ngày / toàn bộ.")
        if st.button("Tạo dữ liệu mẫu"):
            auth.require(auth.MANAGE_USERS)
            n = privacy.seed_demo_events()
            auth.audit("tao_du_lieu_mau", f"{n} sự cố")
            s["_privacy_flash"] = f"Đã thêm {n} sự cố mẫu."
            st.rerun()

st.caption(f"Phiên bản nội dung đồng ý: {privacy.CONSENT_VERSION}")

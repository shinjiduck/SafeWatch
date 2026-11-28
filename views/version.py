"""Trang Phiên bản — bản đang chạy dùng commit nào, model nào, thông số gì, tính năng nào bật. Mọi giá trị đọc từ
version_info.py (cùng nguồn với bảng cấu hình trình diễn và test đồng bộ tài liệu), không chép số tay."""

from html import escape

import streamlit as st

import auth
import version_info as vi
from theme import badge_html, card, kpi_card, page_header, section

auth.require(auth.VIEW_REPORTS)

page_header(
    "Phiên bản",
    "Thông số của bản đang chạy, đọc thẳng từ mã nguồn. Kết quả kiểm định ghi kèm dữ liệu đã dùng để đo.",
    icon="ℹ️",
)

model = vi.fall_model()
c1, c2, c3, c4 = st.columns(4)
with c1:
    kpi_card("Commit", vi.commit() or "không rõ", "mã nguồn đang chạy", icon="layers", tone="indigo")
with c2:
    kpi_card("Model ngã", f"v2 · {model['ten']}", f"ngưỡng {model['nguong']:g} · {model['lien_tiep']} lần liên tiếp",
             icon="activity", tone="sky")
with c3:
    kpi_card("Xác minh sau ngã", f"{vi.engine.DEFAULT_FALL_GRACE_SECONDS:g} s", "tự dậy trong thời gian này thì huỷ",
             icon="clock", tone="amber")
with c4:
    kpi_card("Chờ xác nhận", f"{vi.notifier.ACK_TIMEOUT_SECONDS:g} s", "hết thì gửi lại + chuyển người kế tiếp",
             icon="bell", tone="emerald")


def table(head, rows):
    th = "".join(f"<th>{h}</th>" for h in head)
    body = "".join("<tr>" + "".join(f"<td>{c}</td>" for c in r) + "</tr>" for r in rows)
    return f'<table class="sw-vtable"><thead><tr>{th}</tr></thead><tbody>{body}</tbody></table>'


st.markdown("""<style>
.sw-vtable { width: 100%; border-collapse: collapse; font-size: .95rem; }
.sw-vtable th { text-align: left; font-weight: 600; color: #52525B; padding: .5rem .6rem; border-bottom: 1px solid #E4E4E7; }
.sw-vtable td { padding: .55rem .6rem; border-bottom: 1px solid #F1F1F4; vertical-align: top; }
.sw-vtable tr:last-child td { border-bottom: 0; }
.sw-vtable code { font-size: .85rem; }
</style>""", unsafe_allow_html=True)

section("Thông số")
with card("ver_params"):
    st.markdown(table(["Nhóm", "Thông số", "Giá trị", "Khai báo ở"],
                      [(escape(a), escape(b), escape(c), f"<code>{escape(d)}</code>") for a, b, c, d in vi.thong_so()]),
                unsafe_allow_html=True)

section("Tính năng")
s = st.session_state
with card("ver_features"):
    rows = []
    for (key, ten, tt, gc), (_, mac_dinh, _, _) in zip(vi.TINH_NANG, vi.tinh_nang()):
        dang = bool(s.get(key, mac_dinh))
        rows.append((escape(ten), badge_html("safe" if mac_dinh else "idle", "Bật" if mac_dinh else "Tắt"),
                     badge_html("safe" if dang else "idle", "Bật" if dang else "Tắt"),
                     badge_html("info" if tt == "Đang dùng" else "monitoring", tt), escape(gc)))
    st.markdown(table(["Tính năng", "Mặc định", "Phiên này", "Trạng thái", "Ghi chú"], rows), unsafe_allow_html=True)
    st.caption("“Phiên này” khác “Mặc định” khi đã đổi ở trang Cấu hình.")

section("Kết quả kiểm định")
with card("ver_results"):
    st.markdown(table(["Bài thử", "Kết quả", "Dữ liệu / điều kiện", "Tài liệu"],
                      [(escape(a), f"<b>{escape(b)}</b>", escape(c), f"<code>{escape(d)}</code>")
                       for a, b, c, d in vi.KET_QUA]), unsafe_allow_html=True)
    st.caption("Kiểm định trên dữ liệu độc lập (người, phòng, góc camera model chưa thấy), chưa phải thử với người ngoài "
               "nhóm. SafeWatch hỗ trợ phát hiện sớm, không thay thế người chăm sóc hay dịch vụ cấp cứu.")

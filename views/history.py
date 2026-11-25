"""Trang Nhật ký — 2 tab: Sự cố (ngã, SOS, đã tự đứng dậy...) và Hệ thống (mất / khôi phục camera, mất người).
Phân loại sự kiện dùng chung event_log.classify (cùng cách đếm với trang Trực tiếp và Tổng quan)."""

from datetime import datetime, timedelta

import pandas as pd
import streamlit as st

import event_log
from theme import kpi_card, page_header

event_log.init_db()
page_header("Nhật ký", "Mọi sự cố và thay đổi trạng thái hệ thống đã ghi lại.")

rows = []
for ts, event_type, details in event_log.get_events(limit=2000):
    try:
        dt = datetime.fromisoformat(ts)
    except ValueError:
        continue
    group, status = event_log.classify(event_type)
    rows.append({"dt": dt, "Thời gian": dt.strftime("%d/%m/%Y %H:%M:%S"), "Sự kiện": event_type, "Nhóm": group,
                 "Kết quả": status, "Chi tiết": details})
df = pd.DataFrame(rows, columns=["dt", "Thời gian", "Sự kiện", "Nhóm", "Kết quả", "Chi tiết"])

tab_events, tab_system = st.tabs(["🚨 Sự cố", "🖥️ Hệ thống"])

with tab_events:
    f1, f2, f3 = st.columns(3)
    days = f1.selectbox("Khoảng thời gian", ["7 ngày", "30 ngày", "Tất cả"])
    group = f2.selectbox("Nhóm", ["Tất cả", event_log.GROUP_FALL, event_log.GROUP_SOS])
    result = f3.selectbox("Kết quả", ["Tất cả", event_log.STATUS_ALARM, event_log.STATUS_RECOVERED,
                                      event_log.STATUS_VERIFYING])
    in_range = df if days == "Tất cả" else df[df["dt"] >= datetime.now() - timedelta(days=7 if days == "7 ngày" else 30)]
    k1, k2, k3, k4 = st.columns(4)
    with k1:
        kpi_card("Báo động", int((in_range["Kết quả"] == event_log.STATUS_ALARM).sum()), "Đã gửi tới người liên hệ")
    with k2:
        kpi_card("Ngã không dậy", int(((in_range["Nhóm"] == event_log.GROUP_FALL)
                                      & (in_range["Kết quả"] == event_log.STATUS_ALARM)).sum()), "Đã báo động")
    with k3:
        kpi_card("SOS", int((in_range["Nhóm"] == event_log.GROUP_SOS).sum()), "Cử chỉ cầu cứu")
    with k4:
        kpi_card("Tự đứng dậy", int((in_range["Kết quả"] == event_log.STATUS_RECOVERED).sum()), "Không báo động")
    view = in_range
    if group != "Tất cả":
        view = view[view["Nhóm"] == group]
    if result != "Tất cả":
        view = view[view["Kết quả"] == result]
    st.caption(f"{len(view)} sự kiện")
    if view.empty:
        st.info("Không có sự kiện nào khớp bộ lọc.")
    else:
        st.dataframe(view[["Thời gian", "Sự kiện", "Kết quả", "Chi tiết"]], width="stretch", hide_index=True)

with tab_system:
    status_rows = event_log.get_status_log(limit=1000)
    if not status_rows:
        st.info("Chưa có ghi nhận nào.")
    else:
        st.dataframe(pd.DataFrame(status_rows, columns=["Thời gian", "Trạng thái", "Chi tiết"]), width="stretch",
                     hide_index=True)

with st.expander("🗑️ Xoá toàn bộ lịch sử sự cố"):
    confirm = st.checkbox("Tôi chắc chắn muốn xoá toàn bộ lịch sử (không thể hoàn tác)")
    if st.button("Xoá lịch sử", disabled=not confirm):
        event_log.clear_events()
        st.success("Đã xoá toàn bộ lịch sử.")
        st.rerun()

"""Trang Nhật ký — 2 tab: Sự cố (ngã, SOS, đã tự đứng dậy...) và Hệ thống (mất / khôi phục camera, mất người).
Phân loại sự kiện dùng chung event_log.classify (cùng cách đếm với trang Trực tiếp và Tổng quan)."""

from datetime import datetime, timedelta

import pandas as pd
import streamlit as st

import auth
import event_log
import privacy
from theme import empty_html, kpi_card, page_header

auth.require(auth.VIEW_HISTORY)
event_log.init_db()
page_header("Nhật ký", "Mọi sự cố và thay đổi trạng thái hệ thống đã ghi lại.", icon="📋")
_flash = st.session_state.pop("_history_flash", None)
if _flash:
    st.toast(_flash, icon="✅")

rows = []
for event_id, ts, event_type, details in event_log.get_events_with_id(limit=2000):
    try:
        dt = datetime.fromisoformat(ts)
    except ValueError:
        continue
    group, status = event_log.classify(event_type)
    rows.append({"id": event_id, "dt": dt, "Thời gian": dt.strftime("%d/%m/%Y %H:%M:%S"), "Sự kiện": event_type,
                 "Nhóm": group, "Kết quả": status, "Chi tiết": details})
df = pd.DataFrame(rows, columns=["id", "dt", "Thời gian", "Sự kiện", "Nhóm", "Kết quả", "Chi tiết"])

tab_events, tab_system = st.tabs(["Sự cố", "Hệ thống"])

with tab_events:
    f1, f2, f3 = st.columns(3)
    days = f1.selectbox("Khoảng thời gian", ["7 ngày", "30 ngày", "Tất cả"])
    group = f2.selectbox("Nhóm", ["Tất cả", event_log.GROUP_FALL, event_log.GROUP_SOS])
    result = f3.selectbox("Kết quả", ["Tất cả", event_log.STATUS_ALARM, event_log.STATUS_RECOVERED,
                                      event_log.STATUS_VERIFYING])
    in_range = df if days == "Tất cả" else df[df["dt"] >= datetime.now() - timedelta(days=7 if days == "7 ngày" else 30)]
    k1, k2, k3, k4 = st.columns(4)
    with k1:
        kpi_card("Báo động", int((in_range["Kết quả"] == event_log.STATUS_ALARM).sum()), "Đã gửi tới người liên hệ", icon="🚨", tone="rose")
    with k2:
        kpi_card("Ngã không dậy", int(((in_range["Nhóm"] == event_log.GROUP_FALL)
                                      & (in_range["Kết quả"] == event_log.STATUS_ALARM)).sum()), "Đã báo động",
                 icon="🤕", tone="amber")
    with k3:
        kpi_card("SOS", int((in_range["Nhóm"] == event_log.GROUP_SOS).sum()), "Cử chỉ cầu cứu", icon="✋", tone="violet")
    with k4:
        kpi_card("Tự đứng dậy", int((in_range["Kết quả"] == event_log.STATUS_RECOVERED).sum()), "Không báo động", icon="🧍", tone="emerald")
    view = in_range
    if group != "Tất cả":
        view = view[view["Nhóm"] == group]
    if result != "Tất cả":
        view = view[view["Kết quả"] == result]
    st.caption(f"{len(view)} sự kiện")
    if view.empty:
        st.markdown(empty_html("Không có sự kiện nào khớp bộ lọc", "Thử chọn khoảng thời gian dài hơn hoặc nhóm "
                               "“Tất cả”.", icon="list", tone="slate"), unsafe_allow_html=True)
    else:
        st.dataframe(view[["Thời gian", "Sự kiện", "Kết quả", "Chi tiết"]], width="stretch", hide_index=True)

with tab_system:
    status_rows = event_log.get_status_log(limit=1000)
    if not status_rows:
        st.markdown(empty_html("Chưa có ghi nhận hệ thống", "Mất / khôi phục camera và lúc không thấy người sẽ "
                               "được ghi ở đây khi bắt đầu giám sát.", icon="activity", tone="slate"),
                    unsafe_allow_html=True)
    else:
        st.dataframe(pd.DataFrame(status_rows, columns=["Thời gian", "Trạng thái", "Chi tiết"]), width="stretch",
                     hide_index=True)

if auth.can(auth.EXPORT) and not df.empty:
    st.download_button("Tải lịch sử sự cố (CSV)", df[["Thời gian", "Sự kiện", "Kết quả", "Chi tiết"]]
                       .map(lambda v: "'" + v if isinstance(v, str) and v and v[0] in "=+-@" else v)
                       .to_csv(index=False).encode("utf-8-sig"), "safewatch_nhat_ky.csv", "text/csv",
                       on_click=lambda: auth.audit("xuat_csv", "nhật ký sự cố"))

if auth.can(auth.DELETE_HISTORY) and not df.empty:
    with st.expander("Xoá một sự kiện"):
        pick = st.selectbox("Chọn sự kiện", df["id"].tolist(),
                            format_func=lambda i: " · ".join(df.loc[df["id"] == i, ["Thời gian", "Sự kiện"]].iloc[0]))
        if st.button("Xoá sự kiện này", key="del_one"):
            auth.require(auth.DELETE_HISTORY)
            counts = privacy.delete_event(pick, who=auth.who())
            st.session_state["_history_flash"] = f"Đã xoá {privacy._fmt(counts)}."
            st.rerun()
        st.caption("Xoá theo khoảng ngày hoặc toàn bộ: trang Quyền riêng tư.")

"""Trang Tổng quan — thống kê sự cố theo thời gian và tốc độ người nhà phản hồi. Không lặp lại trạng thái
"sống" của trang Trực tiếp (Streamlit chỉ chạy 1 trang / lúc nên trạng thái ở đây luôn cũ — dễ hiểu nhầm).

Màu biểu đồ (đã kiểm tra mù màu bằng validate_palette của skill dataviz): báo động #DC2626, tự đứng dậy
#2563EB (đỏ + xanh lá trượt kiểm tra mù màu đỏ-lục); biểu đồ 1 dãy theo giờ dùng xám trung tính.
"""

from datetime import datetime, timedelta
from statistics import median

import altair as alt
import pandas as pd
import streamlit as st

import event_log
import notifier
from theme import COLOR_NAVY, card, fmt_duration, kpi_card, page_header, section

event_log.init_db()
notifier.init_db()
page_header("Tổng quan", "Sự cố theo ngày, theo giờ và tốc độ người nhà xác nhận cảnh báo.", icon="📊")

COLORS = {event_log.STATUS_ALARM: "#DC2626", "Tự đứng dậy": "#2563EB"}
AXIS = dict(labelColor="#64748B", titleColor="#64748B", gridColor="#EEF0F3", domainColor="#CBD5E1", tickColor="#CBD5E1")

events = []
for ts, event_type, _ in event_log.get_events(limit=5000):
    try:
        dt = datetime.fromisoformat(ts)
    except ValueError:
        continue
    _, status = event_log.classify(event_type)
    if status == event_log.STATUS_VERIFYING:  # bước trung gian — kết cục đã ghi riêng (báo động / tự đứng dậy)
        continue
    events.append({"dt": dt, "Kết quả": "Tự đứng dậy" if status == event_log.STATUS_RECOVERED else status})
df = pd.DataFrame(events, columns=["dt", "Kết quả"])

period = st.segmented_control("Khoảng thời gian", ["7 ngày", "30 ngày"], default="7 ngày") or "7 ngày"
days = 7 if period == "7 ngày" else 30
since = datetime.now() - timedelta(days=days)
recent = df[df["dt"] >= since]

alerts = [a for a in notifier.latency_rows(limit=500) if a["detected_at"] >= since.timestamp()]
ack_times = [a["sent_to_ack_s"] for a in alerts if a["sent_to_ack_s"] is not None]
k1, k2, k3, k4 = st.columns(4)
with k1:
    kpi_card("Báo động", int((recent["Kết quả"] == event_log.STATUS_ALARM).sum()), f"{days} ngày qua", icon="🚨", tone="rose")
with k2:
    kpi_card("Tự đứng dậy", int((recent["Kết quả"] == "Tự đứng dậy").sum()), "Không cần báo động", icon="🧍", tone="emerald")
with k3:
    kpi_card("Người nhà xác nhận sau", fmt_duration(median(ack_times)) if ack_times else "—", "Trung vị, từ lúc gửi được", icon="⏱️", tone="sky")
with k4:
    kpi_card("Chưa ai xác nhận", sum(1 for a in alerts if a["status"] != notifier.STATUS_ACKED), "Cảnh báo cần xem", icon="📨", tone="amber")

if recent.empty:
    st.info(f"Chưa có sự cố nào trong {days} ngày qua.")
    st.stop()

section("Sự cố theo ngày")
dates = pd.date_range((datetime.now() - timedelta(days=days - 1)).date(), datetime.now().date())
per_day = (recent.assign(Ngày=recent["dt"].dt.normalize()).groupby(["Ngày", "Kết quả"]).size()
           .rename("Số lần").reset_index())
full = pd.MultiIndex.from_product([dates, list(COLORS)], names=["Ngày", "Kết quả"])
per_day = per_day.set_index(["Ngày", "Kết quả"]).reindex(full, fill_value=0).reset_index()
per_day["Nhãn"] = per_day["Ngày"].dt.strftime("%d/%m")  # trục rời từng ngày: mỗi ngày đúng 1 cột
chart = (
    alt.Chart(per_day)
    .mark_bar(cornerRadiusTopLeft=4, cornerRadiusTopRight=4, stroke="white", strokeWidth=2)
    .encode(
        x=alt.X("Nhãn:O", title=None, sort=[d.strftime("%d/%m") for d in dates],
                axis=alt.Axis(labelAngle=0, grid=False, labelOverlap=True, **AXIS)),
        y=alt.Y("Số lần:Q", title=None, axis=alt.Axis(tickMinStep=1, **AXIS)),
        color=alt.Color("Kết quả:N", scale=alt.Scale(domain=list(COLORS), range=list(COLORS.values())),
                        legend=alt.Legend(orient="top", title=None, labelColor=COLOR_NAVY)),
        order=alt.Order("Kết quả:N", sort="descending"),
        tooltip=[alt.Tooltip("Ngày:T", format="%d/%m/%Y"), "Kết quả:N", "Số lần:Q"],
    )
    .properties(height=260)
    .configure_view(strokeWidth=0)
)
with card("chart_day"):
    st.altair_chart(chart, width="stretch")

section("Sự cố theo giờ trong ngày")
per_hour = recent.assign(Giờ=recent["dt"].dt.hour).groupby("Giờ").size().reindex(range(24), fill_value=0)
per_hour = per_hour.rename("Số lần").reset_index()
chart = (
    alt.Chart(per_hour)
    .mark_bar(cornerRadiusTopLeft=4, cornerRadiusTopRight=4, color="#475569")
    .encode(
        x=alt.X("Giờ:O", title="Giờ", axis=alt.Axis(labelAngle=0, grid=False, **AXIS)),
        y=alt.Y("Số lần:Q", title=None, axis=alt.Axis(tickMinStep=1, **AXIS)),
        tooltip=[alt.Tooltip("Giờ:O", title="Giờ"), "Số lần:Q"],
    )
    .properties(height=200)
    .configure_view(strokeWidth=0)
)
with card("chart_hour"):
    st.altair_chart(chart, width="stretch")
st.caption("Tính cả báo động và lần tự đứng dậy — cho biết khung giờ nên chú ý.")

with st.expander("Xem dạng bảng"):
    st.dataframe(per_day.pivot(index="Ngày", columns="Kết quả", values="Số lần").sort_index(ascending=False),
                 width="stretch")

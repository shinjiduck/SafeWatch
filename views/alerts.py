"""Trang Cảnh báo & xác nhận — minh chứng cho yêu cầu cải tiến số 1:
giả lập sự kiện ngã, theo dõi từng lần gửi, và bảng thời gian từ lúc phát
hiện đến lúc người chăm sóc xác nhận (xuất CSV cho báo cáo)."""

import time
from datetime import datetime
from statistics import median

import pandas as pd
import streamlit as st

import contacts
import notifier

notifier.init_db()

st.title("Cảnh báo & xác nhận")

dispatcher = notifier.RUNNING
channel_names = sorted(dispatcher.channels) if dispatcher else []
recipients = contacts.get_alert_recipients()

# ----- Tình trạng kênh gửi -----
c1, c2, c3 = st.columns(3)
with c1:
    with st.container(border=True):
        st.markdown('<div class="sw-kpi-label">Kênh gửi đang bật</div>', unsafe_allow_html=True)
        st.markdown(f'<div class="sw-kpi-value">{", ".join(channel_names) or "Chưa có"}</div>', unsafe_allow_html=True)
with c2:
    reachable = [
        r for r in recipients
        if ("telegram" in channel_names and r["telegram_chat_id"]) or ("email" in channel_names and r["email"])
    ]
    with st.container(border=True):
        st.markdown('<div class="sw-kpi-label">Người nhận liên lạc được</div>', unsafe_allow_html=True)
        st.markdown(f'<div class="sw-kpi-value">{len(reachable)}/{len(recipients)}</div>', unsafe_allow_html=True)
with c3:
    with st.container(border=True):
        st.markdown('<div class="sw-kpi-label">Bộ gửi nền</div>', unsafe_allow_html=True)
        alive = dispatcher is not None and dispatcher._thread is not None and dispatcher._thread.is_alive()
        st.markdown(f'<div class="sw-kpi-value">{"Đang chạy" if alive else "Đã dừng"}</div>', unsafe_allow_html=True)

if not channel_names:
    st.warning(
        "Chưa cấu hình kênh gửi nào. Thêm vào `.streamlit/secrets.toml`: `TELEGRAM_BOT_TOKEN` (tạo bot bằng "
        "@BotFather) và/hoặc `SMTP_HOST`, `SMTP_PORT`, `SMTP_USER`, `SMTP_PASSWORD`; rồi khởi động lại app."
    )
elif not reachable:
    st.warning("Chưa có người liên hệ nào có Telegram Chat ID / email phù hợp với kênh đang bật.")
if dispatcher is not None and dispatcher.last_error:
    st.caption(f"Lỗi gần nhất của bộ gửi: {dispatcher.last_error}")

st.caption(
    f"Chưa ai xác nhận sau {notifier.ACK_TIMEOUT_SECONDS}s → gửi lại và chuyển tiếp thêm người kế tiếp; "
    f"tối đa {notifier.MAX_ROUNDS} vòng. Gửi lỗi → thử lại sau {', '.join(map(str, notifier.RETRY_BACKOFF_SECONDS))}s."
)

if st.button("🧪 Giả lập sự kiện ngã", type="primary"):
    alert_id = notifier.raise_alert("Ngã (giả lập)", "Kiểm thử chuỗi cảnh báo", source="simulated")
    st.toast(f"Đã phát cảnh báo giả lập #{alert_id}")

STATUS_TEXT = {
    notifier.STATUS_OPEN: "Đang chờ xác nhận",
    notifier.STATUS_ACKED: "Đã xác nhận",
    notifier.STATUS_UNACKED: "Hết lượt, chưa ai xác nhận",
}


def fmt_s(value):
    return "—" if value is None else f"{value:.1f}"


@st.fragment(run_every=2)
def live_table():
    rows = notifier.latency_rows(limit=200)
    if not rows:
        st.info("Chưa có cảnh báo nào. Bấm \"Giả lập sự kiện ngã\" để thử.")
        return

    sent = [r["raise_to_sent_s"] for r in rows if r["raise_to_sent_s"] is not None]
    acked = [r["sent_to_ack_s"] for r in rows if r["sent_to_ack_s"] is not None]
    m1, m2, m3 = st.columns(3)
    m1.metric("Trung vị: phát cảnh báo → gửi được", f"{median(sent):.1f} s" if sent else "—")
    m2.metric("Trung vị: gửi được → xác nhận", f"{median(acked):.1f} s" if acked else "—")
    m3.metric("Chưa xác nhận", sum(1 for r in rows if r["status"] != notifier.STATUS_ACKED))

    table = pd.DataFrame(
        [
            {
                "#": r["id"],
                "Loại": r["kind"],
                "Phát hiện lúc": datetime.fromtimestamp(r["detected_at"]).strftime("%d/%m %H:%M:%S"),
                "Chờ xác minh (s)": fmt_s(r["verify_s"]),
                "Phát → gửi được (s)": fmt_s(r["raise_to_sent_s"]),
                "Gửi được → xác nhận (s)": fmt_s(r["sent_to_ack_s"]),
                "Tổng: phát hiện → xác nhận (s)": fmt_s(r["total_s"]),
                "Trạng thái": STATUS_TEXT.get(r["status"], r["status"]),
                "Xác nhận bởi": f"{r['acked_by'] or ''} ({r['acked_via']})" if r["acked_via"] else "—",
                "Số vòng": r["rounds"],
                "Lần gửi": r["attempts"],
                "Lần lỗi": r["failed_attempts"],
            }
            for r in rows
        ]
    )
    st.dataframe(table, width="stretch", hide_index=True)
    st.download_button(
        "Tải bảng thời gian (CSV)",
        pd.DataFrame(rows).to_csv(index=False).encode("utf-8-sig"),
        file_name=f"safewatch_alert_latency_{time.strftime('%Y%m%d_%H%M')}.csv",
        mime="text/csv",
    )


live_table()

st.markdown("---")
alerts = notifier.get_alerts(limit=200)
if alerts:
    choice = st.selectbox(
        "Xem chi tiết từng lần gửi của cảnh báo",
        [a["id"] for a in alerts],
        format_func=lambda i: next(f"#{a['id']} · {a['kind']}" for a in alerts if a["id"] == i),
    )
    chosen = next(a for a in alerts if a["id"] == choice)
    deliveries = notifier.get_deliveries(choice)
    if deliveries:
        st.dataframe(
            pd.DataFrame(
                [
                    {
                        "Vòng": d["round"] + 1,
                        "Người nhận": d["contact_name"],
                        "Kênh": d["channel"],
                        "Trạng thái": d["status"],
                        "Số lần thử": d["attempts"],
                        "Gửi được lúc": "—" if d["sent_at"] is None
                        else datetime.fromtimestamp(d["sent_at"]).strftime("%H:%M:%S"),
                        "Lỗi gần nhất": d["error"] or "",
                    }
                    for d in deliveries
                ]
            ),
            width="stretch",
            hide_index=True,
        )
    else:
        st.caption("Chưa có lần gửi nào cho cảnh báo này (chưa có kênh/người nhận phù hợp).")
    if chosen["acked_at"] is None and st.button("Người chăm sóc xác nhận trên web (dùng khi demo không có điện thoại)"):
        notifier.ack(chosen["ack_token"], by="(trên web)", via="web-ui")
        st.rerun()

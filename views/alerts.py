"""Trang Cảnh báo — dành cho người chăm sóc: cảnh báo đang chờ xác nhận lên đầu (to, rõ, xác nhận được ngay),
rồi tới danh sách cảnh báo gần đây và chi tiết gửi từng kênh. Phần kỹ thuật (giả lập sự kiện, bảng thời gian
phát hiện -> gửi -> xác nhận, xuất CSV làm minh chứng yêu cầu cải tiến số 1) thu gọn ở cuối trang."""

import time
from datetime import datetime
from statistics import median

import pandas as pd
import streamlit as st

import contacts
import notifier
from theme import badge_html, kpi_card, page_header, section

notifier.init_db()

STATUS_TEXT = {
    notifier.STATUS_OPEN: ("monitoring", "Chờ xác nhận"),
    notifier.STATUS_ACKED: ("safe", "Đã xác nhận"),
    notifier.STATUS_UNACKED: ("emergency", "Chưa ai nhận"),
}
DELIVERY_TEXT = {"pending": "Đang chờ gửi", "sent": "Đã gửi", "failed": "Lỗi — sẽ thử lại", "cancelled": "Đã huỷ"}
CHANNEL_TEXT = {"telegram": "Telegram", "email": "Email", "sms": "SMS"}

page_header("Cảnh báo", "Cảnh báo gửi tới người liên hệ và việc xác nhận đã nhận.")

dispatcher = notifier.RUNNING
channel_names = sorted(dispatcher.channels) if dispatcher else []
recipients = contacts.get_alert_recipients()


def fmt_time(ts):
    return "—" if ts is None else datetime.fromtimestamp(ts).strftime("%H:%M:%S %d/%m")


def fmt_s(value):
    return "—" if value is None else f"{value:.1f}"


@st.fragment(run_every=2)
def open_alerts():
    pending = [a for a in notifier.get_alerts(limit=500) if a["acked_at"] is None]
    if not pending:
        st.success("Không có cảnh báo nào đang chờ xác nhận.", icon="✅")
        return
    for a in pending[:3]:
        level, text = STATUS_TEXT.get(a["status"], ("monitoring", a["status"]))
        with st.container(border=True):
            c1, c2 = st.columns([4, 1.4], vertical_alignment="center")
            with c1:
                st.markdown(f"{badge_html(level, text)} &nbsp; **{a['kind']}**", unsafe_allow_html=True)
                st.caption(f"Phát hiện {fmt_time(a['detected_at'])} · {a['details'] or ''} · vòng gửi "
                           f"{a['current_round'] + 1}/{notifier.MAX_ROUNDS}")
            with c2:
                if st.button("Tôi đã nhận", key=f"ack_{a['id']}", type="primary", width="stretch"):
                    notifier.ack(a["ack_token"], by="(trên web)", via="web-ui")
                    st.rerun()
    if len(pending) > 3:
        c1, c2 = st.columns([4, 1.4], vertical_alignment="center")
        c1.caption(f"Còn {len(pending) - 3} cảnh báo cũ hơn chưa ai xác nhận — xem bảng bên dưới.")
        if c2.button(f"Xác nhận tất cả ({len(pending)})", width="stretch"):
            for a in pending:
                notifier.ack(a["ack_token"], by="(trên web, xác nhận hàng loạt)", via="web-ui")
            st.rerun()


section("Đang chờ xác nhận")
open_alerts()

section("Cảnh báo gần đây")
alerts = notifier.get_alerts(limit=200)
if not alerts:
    st.info("Chưa có cảnh báo nào.")
else:
    table = pd.DataFrame(
        [
            {
                "#": a["id"],
                "Loại": a["kind"],
                "Phát hiện lúc": fmt_time(a["detected_at"]),
                "Trạng thái": STATUS_TEXT.get(a["status"], ("", a["status"]))[1],
                "Xác nhận bởi": f"{a['acked_by'] or ''} ({a['acked_via']})" if a["acked_via"] else "—",
                "Nguồn": "Giả lập" if a["source"] == "simulated" else "Camera",
            }
            for a in alerts
        ]
    )
    st.dataframe(table, width="stretch", hide_index=True, height=min(400, 38 + 35 * len(table)))

    choice = st.selectbox(
        "Xem chi tiết gửi của một cảnh báo",
        [a["id"] for a in alerts],
        format_func=lambda i: next(f"#{a['id']} · {a['kind']} · {fmt_time(a['detected_at'])}" for a in alerts
                                   if a["id"] == i),
    )
    deliveries = notifier.get_deliveries(choice)
    if deliveries:
        st.dataframe(
            pd.DataFrame(
                [
                    {
                        "Vòng": d["round"] + 1,
                        "Người nhận": d["contact_name"],
                        "Kênh": CHANNEL_TEXT.get(d["channel"], d["channel"]),
                        "Trạng thái": DELIVERY_TEXT.get(d["status"], d["status"]),
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
        st.caption("Chưa có lần gửi nào cho cảnh báo này (chưa có kênh / người nhận phù hợp).")

section("Kênh gửi")
reachable = [r for r in recipients if any(
    (ch == "telegram" and r["telegram_chat_id"]) or (ch == "email" and r["email"]) or (ch == "sms" and r["phone"])
    for ch in channel_names)]
alive = dispatcher is not None and dispatcher._thread is not None and dispatcher._thread.is_alive()
k1, k2, k3 = st.columns(3)
with k1:
    kpi_card("Kênh đang bật", ", ".join(CHANNEL_TEXT.get(c, c) for c in channel_names) or "Chưa có",
             "Cấu hình trong .streamlit/secrets.toml")
with k2:
    kpi_card("Người nhận liên lạc được", f"{len(reachable)}/{len(recipients)}", "Có kênh phù hợp")
with k3:
    kpi_card("Bộ gửi nền", "Đang chạy" if alive else "Đã dừng",
             f"Lỗi gần nhất: {dispatcher.last_error}" if dispatcher is not None and dispatcher.last_error else "Không có lỗi")
if not channel_names:
    st.warning("Chưa bật kênh gửi nào — xem Cấu hình → Cảnh báo.", icon="⚠️")
elif not reachable:
    st.warning("Chưa có người liên hệ nào có Telegram / email / số điện thoại khớp với kênh đang bật.", icon="⚠️")
st.caption(
    f"Chưa ai xác nhận sau {notifier.ACK_TIMEOUT_SECONDS} s → gửi lại và chuyển tiếp thêm người kế tiếp, tối đa "
    f"{notifier.MAX_ROUNDS} vòng. Gửi lỗi → thử lại sau {', '.join(map(str, notifier.RETRY_BACKOFF_SECONDS))} s."
)

with st.expander("📱 Gửi SMS thử", expanded="sms" in channel_names and not notifier.get_alerts(limit=1)):
    if "sms" not in channel_names:
        st.info(
            "Chưa bật SMS. Cách 1 — **eSMS** (SMS Brandname): điền `ESMS_API_KEY`, `ESMS_SECRET_KEY`, "
            "`ESMS_BRANDNAME` trong `.streamlit/secrets.toml`. Cách 2 — **điện thoại Android** có SIM với app "
            "SMS Gateway for Android: điền `SMS_GATEWAY_USER` / `SMS_GATEWAY_PASSWORD`. Rồi khởi động lại app.",
            icon="ℹ️",
        )
    else:
        sms = dispatcher.channels["sms"]
        if getattr(sms, "provider", "") == "esms":
            c1, c2 = st.columns([3, 1], vertical_alignment="center")
            c1.markdown(f"Đang gửi qua **eSMS**, brandname **{sms.brandname}**"
                        + (" · 🧪 **Sandbox**: gọi API thật nhưng không gửi tin, không trừ tiền" if sms.sandbox else ""))
            if c2.button("Xem số dư eSMS"):
                try:
                    st.toast(f"Số dư eSMS: {sms.balance():,} đ")
                except Exception as exc:  # noqa: BLE001
                    st.error(f"Không xem được số dư: {exc}", icon="❌")
        else:
            st.caption(f"Đang gửi qua: {getattr(sms, 'provider', 'sms')}")
        with_phone = [r for r in recipients if r["phone"]]
        if not with_phone:
            st.warning("Chưa có người liên hệ nào có số điện thoại.", icon="⚠️")
        else:
            who = st.selectbox("Gửi tới", with_phone, format_func=lambda r: f"{r['name']} · {r['phone']}")
            if st.button("Gửi SMS thử"):
                channel = dispatcher.channels["sms"]
                target = channel.target_for(who)
                test_alert = {"kind": "Tin nhắn thử", "details": "Kiểm tra kênh SMS", "detected_at": time.time(),
                              "source": "simulated", "ack_token": "test"}
                try:
                    channel.send(target, test_alert)
                    if getattr(channel, "sandbox", False):
                        st.success(f"eSMS (Sandbox) đã nhận lệnh gửi tới {target} — kết nối đúng. Chế độ thử nên "
                                   "KHÔNG có tin về máy; đặt ESMS_SANDBOX = \"0\" để gửi thật.", icon="✅")
                    else:
                        st.success(f"Cổng SMS đã nhận lệnh gửi tới {target}. Tin tới máy sau vài giây.", icon="✅")
                except Exception as exc:  # noqa: BLE001 — hiện lỗi cho người cài đặt
                    st.error(f"Gửi không được: {exc}", icon="❌")

with st.expander("🧪 Kiểm thử chuỗi cảnh báo & bảng thời gian (minh chứng yêu cầu cải tiến số 1)"):
    if st.button("Giả lập sự kiện ngã"):
        alert_id = notifier.raise_alert("Ngã (giả lập)", "Kiểm thử chuỗi cảnh báo", source="simulated")
        st.toast(f"Đã phát cảnh báo giả lập #{alert_id}")
    rows = notifier.latency_rows(limit=200)
    if rows:
        sent = [r["raise_to_sent_s"] for r in rows if r["raise_to_sent_s"] is not None]
        acked = [r["sent_to_ack_s"] for r in rows if r["sent_to_ack_s"] is not None]
        m1, m2 = st.columns(2)
        m1.metric("Trung vị: phát cảnh báo → gửi được", f"{median(sent):.1f} s" if sent else "—")
        m2.metric("Trung vị: gửi được → xác nhận", f"{median(acked):.1f} s" if acked else "—")
        st.dataframe(
            pd.DataFrame(
                [
                    {
                        "#": r["id"],
                        "Loại": r["kind"],
                        "Chờ xác minh (s)": fmt_s(r["verify_s"]),
                        "Phát → gửi được (s)": fmt_s(r["raise_to_sent_s"]),
                        "Gửi được → xác nhận (s)": fmt_s(r["sent_to_ack_s"]),
                        "Tổng (s)": fmt_s(r["total_s"]),
                        "Số vòng": r["rounds"],
                        "Lần gửi": r["attempts"],
                        "Lần lỗi": r["failed_attempts"],
                    }
                    for r in rows
                ]
            ),
            width="stretch",
            hide_index=True,
        )
        st.download_button(
            "Tải bảng thời gian (CSV)",
            pd.DataFrame(rows).to_csv(index=False).encode("utf-8-sig"),
            file_name=f"safewatch_alert_latency_{time.strftime('%Y%m%d_%H%M')}.csv",
            mime="text/csv",
        )

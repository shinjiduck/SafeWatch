"""Trang Cấu hình — 3 tab: Nhận diện, Cảnh báo & âm thanh, Lưu trữ (cài đặt camera ở trang Camera & lắp đặt).
Giá trị đọc/ghi qua st.session_state (key trùng SETTINGS_DEFAULTS trong detection_engine.py) để trang Trực tiếp
đọc lại được; áp dụng khi bắt đầu lại stream."""

import streamlit as st

import auth
import detection_engine as engine
import event_log
from theme import card, page_header, section

auth.require(auth.EDIT_CONFIG, "Chỉ quản trị gia đình được đổi cấu hình.")
engine.ensure_settings_defaults()
event_log.init_db()

page_header("Cấu hình", "Thay đổi được áp dụng khi bấm Dừng rồi Bắt đầu lại ở trang Trực tiếp.", icon="⚙️")

tab_detect, tab_alert, tab_storage = st.tabs(["Nhận diện", "Cảnh báo & âm thanh", "Lưu trữ"])

with tab_detect:
    section("Phát hiện ngã")
    with card("set_fall"):
        st.session_state["enable_fall"] = st.toggle("Bật phát hiện ngã", value=st.session_state["enable_fall"])
        _versions = ["v2", "v1"]
        st.session_state["fall_model_version"] = st.radio(
            "Model phát hiện ngã",
            _versions,
            index=_versions.index(st.session_state["fall_model_version"]),
            format_func=lambda v: {"v2": "v2 — cú rơi nhanh + theo dõi tư thế (mới)", "v1": "v1 — LSTM 10 frame (cũ)"}[v],
            horizontal=True,
            help="v2 cần models/fall_v2.keras (train bằng training/fall_eval/train_eval.py); thiếu thì tự dùng v1.",
        )
        st.session_state["multi_person"] = st.toggle(
            "Theo dõi nhiều người cùng lúc (tối đa 3, thử nghiệm)",
            value=st.session_state["multi_person"],
            disabled=st.session_state["fall_model_version"] != "v2",
            help="Mỗi người có bộ theo dõi ngã riêng; ai ngã mà không dậy thì báo. Cần model v2. Tốn CPU hơn "
            "(mỗi người thêm ~1 lần chạy model khung xương). Tắt = đúng bản theo dõi 1 người trước đây. "
            "Số đo: training/fall_eval/KIEM_DINH_NHIEU_NGUOI.md.",
        )
        st.session_state["fall_grace_seconds"] = st.slider(
            "Thời gian xác minh sau khi Ngã (giây)",
            min_value=5,
            max_value=300,
            value=st.session_state["fall_grace_seconds"],
            step=5,
            help="Ngã xong tự đứng lên lại trong thời gian này sẽ KHÔNG báo động.",
        )
    section("Cử chỉ cầu cứu")
    with card("set_hand"):
        st.session_state["enable_hand"] = st.toggle("Bật phát hiện cử chỉ tay", value=st.session_state["enable_hand"])
        st.session_state["sos_filter"] = st.toggle(
            "Chống báo SOS nhầm: chỉ nhận cử chỉ khi giơ tay cao hơn vai và giữ 2 giây",
            value=st.session_state["sos_filter"],
            disabled=not st.session_state["enable_hand"],
            help="Đo trên 3,2 giờ sinh hoạt (Charades): báo SOS nhầm 132 -> 1,9 lần / giờ. Cần bật phát hiện ngã (để biết "
            "vai ở đâu). Số đo: training/hand_eval/KIEM_DINH_TAY_XA.md.",
        )
        st.session_state["hand_roi"] = st.toggle(
            "Nhận cử chỉ khi đứng xa camera (thử nghiệm)",
            value=st.session_state["hand_roi"],
            disabled=not st.session_state["enable_hand"],
            help="Khi không thấy tay trên cả khung hình, phóng to vùng quanh bàn tay theo khung xương rồi nhận lại. "
            "Thấy tay nhiều hơn khi đứng ~2-3 m nhưng cũng dễ nhầm cử chỉ hơn — số đo: training/hand_eval/KIEM_DINH_TAY_XA.md.",
        )
        st.session_state["hand_confidence_threshold"] = st.slider(
            "Ngưỡng tin cậy cử chỉ tay (%)",
            min_value=0,
            max_value=100,
            value=int(st.session_state["hand_confidence_threshold"] * 100),
            help="Cử chỉ có độ tin cậy thấp hơn ngưỡng này sẽ hiện 'Không rõ cử chỉ'.",
        ) / 100

        signal_col1, signal_col2 = st.columns([3, 1])
        with signal_col1:
            st.session_state["enable_signal"] = st.toggle(
                "Bật Signal for Help theo chuyển động", value=st.session_state["enable_signal"]
            )
        with signal_col2:
            from theme import badge_html as _badge
            st.markdown(_badge("idle", "Thử nghiệm"), unsafe_allow_html=True)
        st.session_state["signal_confidence_threshold"] = st.slider(
            "Ngưỡng tin cậy chuỗi Signal for Help (%)",
            min_value=0,
            max_value=100,
            value=int(st.session_state["signal_confidence_threshold"] * 100),
        ) / 100
        st.caption("Thử nghiệm: model học từ 60 chuỗi (30 đúng, 30 sai) do nhóm tự quay, chưa đánh giá độc lập. "
                   "Không dùng làm kênh báo động chính.")

with tab_alert:
    import notifier

    from theme import rows_html

    active = sorted(notifier.RUNNING.channels) if notifier.RUNNING else []
    section("Kênh gửi cảnh báo")
    with card("channels"):
        from theme import badge_html

        def state(name, hint, extra=""):
            on = name in active
            return (badge_html("safe", "Đang bật" + extra) if on
                    else badge_html("idle", "Chưa cấu hình") + f' <span style="color:#71717A;font-size:.8rem;">{hint}</span>')

        sms_provider = getattr(notifier.RUNNING.channels.get("sms"), "provider", "") if "sms" in active else ""
        st.markdown(rows_html([
            ("Telegram", state("telegram", "TELEGRAM_BOT_TOKEN")),
            ("Email", state("email", "SMTP_HOST / USER / PASSWORD")),
            ("SMS", state("sms", "ESMS_* / SMS_GATEWAY_* / TWILIO_*", f" · {sms_provider}" if sms_provider else "")),
        ]), unsafe_allow_html=True)
        st.caption("Khai báo trong `.streamlit/secrets.toml` rồi khởi động lại app.")
    c1, c2 = st.columns(2)
    c1.page_link("views/emergency_contacts.py", label="Người liên hệ nhận cảnh báo")
    c2.page_link("views/alerts.py", label="Xem cảnh báo & thử gửi")
    section("Âm thanh & giọng nói")
    with card("set_sound"):
        st.session_state["sound_alert"] = st.toggle(
            "Phát âm thanh khi báo động khẩn cấp", value=st.session_state["sound_alert"]
        )
        st.session_state["voice_prompts"] = st.toggle(
            "Nhắc bằng giọng nói khi đứng quá gần / bị khuất / rời khung hình",
            value=st.session_state["voice_prompts"],
            help='VD: "Xin mời quý vị rời xa camera một chút." Không nhắc trong lúc đang theo dõi sau ngã.',
        )
        st.session_state["silent_monitoring"] = st.toggle(
            "Theo dõi im lặng sau Ngã (không phát âm thanh trong lúc xác minh)",
            value=st.session_state["silent_monitoring"],
            help="Đúng ý tưởng gốc: tránh gây chú ý không cần thiết trong tình huống nhạy cảm (VD bị khống chế).",
        )
    section("Nâng cao")
    with card("set_adv"):
        st.session_state["alert_hold_seconds"] = st.slider(
            "Giữ trạng thái báo động tối thiểu (giây)",
            min_value=0.5,
            max_value=10.0,
            value=float(st.session_state["alert_hold_seconds"]),
            step=0.5,
            help="Tránh cảnh báo nhấp nháy khi tín hiệu dao động ngay ở ngưỡng.",
        )

with tab_storage, card("set_storage"):
    import privacy

    st.markdown(f"Dữ liệu sự cố, cảnh báo, lần gửi tự xoá sau **{privacy.retention_days()} ngày** (kiểm tra mỗi giờ). "
                "Đổi hạn lưu, xoá dữ liệu, xem nhật ký truy cập: trang **Quyền riêng tư**.")
    st.page_link("views/privacy_center.py", label="Mở trang Quyền riêng tư")
    st.markdown("---")
    st.session_state["save_snapshot"] = st.checkbox(
        "Lưu ảnh chụp lúc xảy ra sự cố", value=st.session_state["save_snapshot"], disabled=True
    )
    st.session_state["save_video"] = st.checkbox(
        "Lưu video lúc xảy ra sự cố", value=st.session_state["save_video"], disabled=True
    )
    st.caption("Lưu ảnh / video lúc xảy ra sự cố: chưa hỗ trợ.")

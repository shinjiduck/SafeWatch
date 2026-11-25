"""Trang chủ (Xem trực tiếp) — dùng streamlit-webrtc thay vì
cv2.VideoCapture(0) đọc webcam CỦA MÁY CHẠY SERVER. Với streamlit-webrtc,
trình duyệt của MỖI NGƯỜI XEM tự capture webcam CỦA HỌ qua WebRTC và gửi
từng frame lên DetectionVideoProcessor.recv() (webrtc_processor.py) để xử
lý — đây là điều kiện bắt buộc để deploy app lên 1 địa chỉ web thật cho
nhiều người dùng riêng biệt (bản cv2 cũ chỉ chạy đúng khi mở local trên
đúng máy có webcam, xem app.py và lịch sử git để tham khảo bản đó).

Xử lý AI thật sự chạy trong DetectionVideoProcessor, trên 1 thread riêng
do streamlit-webrtc quản lý — liên tục, độc lập với vòng đời script này.
Vòng lặp while ở cuối file CHỈ để polling + cập nhật hiển thị (banner,
card, FPS), không xử lý frame nào cả.
"""

import os
import time

import streamlit as st
from streamlit_webrtc import (
    RTCConfiguration,
    get_cloudflare_ice_servers,
    get_hf_ice_servers,
    webrtc_streamer,
)

import detection_engine as engine
import event_log
import framing
import multi_person
import contacts
import notifier
from theme import kpi_card, page_header, rows_html, sidebar_status_html, status_banner_html, steps_html
from webrtc_processor import DetectionVideoProcessor

engine.ensure_settings_defaults()

# STUN công khai của Google luôn có sẵn — đủ cho mạng "dễ" (nhà, hầu hết
# trường học). Mạng chặt hơn (NAT đối xứng, firewall công ty/1 số mobile
# network) cần thêm TURN server (máy trung chuyển thật) mới kết nối được —
# STUN không đủ trong trường hợp đó, biểu hiện là "Connection is taking
# longer than expected". Ưu tiên Cloudflare Realtime TURN (ổn định hơn,
# cần CF_TURN_KEY_ID + CF_TURN_API_TOKEN trong Secrets), rơi về TURN miễn
# phí Hugging Face (HF_TOKEN) nếu không có Cloudflare, cuối cùng rơi về
# STUN-only nếu không có cả 2 (Settings > Secrets trên Streamlit Cloud).
_ice_servers = [{"urls": ["stun:stun.l.google.com:19302"]}]
try:
    # st.secrets ném StreamlitSecretNotFoundError ngay khi truy cập (không
    # phải chỉ khi thiếu key) nếu máy không có file secrets.toml — bình
    # thường lúc chạy local (chỉ Streamlit Cloud mới tự có qua Settings >
    # Secrets), nên phải bọc try/except quanh CẢ việc đọc, không chỉ .get().
    _cf_key_id = st.secrets.get("CF_TURN_KEY_ID")
    _cf_api_token = st.secrets.get("CF_TURN_API_TOKEN")
    _hf_token = st.secrets.get("HF_TOKEN")
except Exception:
    _cf_key_id = _cf_api_token = _hf_token = None

if _cf_key_id and _cf_api_token:
    try:
        _ice_servers = get_cloudflare_ice_servers(_cf_key_id, _cf_api_token)
    except Exception:
        pass  # key sai/hết hạn/mạng lỗi lúc xin TURN -> thử HF bên dưới thay vì crash.
if _ice_servers == [{"urls": ["stun:stun.l.google.com:19302"]}] and _hf_token:
    try:
        _ice_servers = get_hf_ice_servers(_hf_token)
    except Exception:
        pass  # rơi về STUN, còn hơn crash cả app.

RTC_CONFIGURATION = RTCConfiguration({"iceServers": _ice_servers})

s = st.session_state
config = {
    "enable_fall": s["enable_fall"],
    "enable_hand": s["enable_hand"],
    "enable_signal": s["enable_signal"],
    "fall_grace_seconds": s["fall_grace_seconds"],
    "hand_confidence_threshold": s["hand_confidence_threshold"],
    "signal_confidence_threshold": s["signal_confidence_threshold"],
    "mirror_camera": s["mirror_camera"],
    "alert_hold_seconds": s["alert_hold_seconds"],
    "show_overlay": s["show_overlay"],
    "multi_person": s.get("multi_person", False),
}

fall_model, hand_model, signal_model = engine.load_models()
# Model ngã v2 (cú rơi nhanh + theo dõi tư thế) nếu đã train; không có thì dùng model cũ.
fall_model_name = "LSTM 10 frame (cũ)"
if s.get("fall_model_version", "v2") == "v2" and engine.load_fall_v2() is not None:
    fall_model = engine.load_fall_v2()
    fall_model_name = "v2 — cú rơi nhanh + tư thế"
if config["enable_signal"] and signal_model is None:
    config["enable_signal"] = False
pose_detector, hand_detector = engine.get_mediapipe()
multi_on = config["multi_person"] and engine.is_fall_v2(fall_model)

# Làm nóng model 1 lần trước khi stream bắt đầu (tránh giật ở vài frame đầu).
engine.warm_up_models(fall_model, hand_model, signal_model)

page_header(
    "Giám sát trực tiếp",
    f"Model ngã {fall_model_name} · {'theo dõi nhiều người (thử nghiệm)' if multi_on else 'theo dõi 1 người'} · "
    f"xác minh {config['fall_grace_seconds']:.0f} s sau ngã",
)


def processor_factory():
    # Mỗi lần bắt đầu stream tạo 1 bộ nhận diện nhiều người riêng (chế độ VIDEO giữ trạng thái theo dõi).
    multi_detector = multi_person.MultiPoseDetector() if multi_on else None
    return DetectionVideoProcessor(
        fall_model, hand_model, signal_model, pose_detector, hand_detector, config, multi_detector=multi_detector
    )


cam_width, cam_height = engine.CAMERA_RESOLUTIONS.get(s["camera_resolution"], (640, 480))

video_col, panel_col = st.columns([3, 2], gap="large")

with video_col:
    webrtc_ctx = webrtc_streamer(
        key="safewatch-live",
        video_processor_factory=processor_factory,
        rtc_configuration=RTC_CONFIGURATION,
        # Giới hạn độ phân giải ("ideal" = gợi ý): mặc định trình duyệt lấy 720p+, nặng cho mọi bước sau.
        media_stream_constraints={
            "video": {"width": {"ideal": cam_width}, "height": {"ideal": cam_height}},
            "audio": False,
        },
        # Hàng đợi 1 frame: luôn xử lý frame mới nhất, chấp nhận rớt frame cũ thay vì trễ dồn.
        video_receiver_size=1,
    )
    st.caption("Bấm **START** để bắt đầu · đổi cấu hình thì **STOP** rồi START lại để áp dụng.")

with panel_col:
    status_banner_placeholder = st.empty()
    detail_placeholder = st.empty()
    voice_placeholder = st.empty()

kpi1, kpi2, kpi3 = st.columns(3)
camera_card_placeholder, duration_card_placeholder, incidents_card_placeholder = kpi1.empty(), kpi2.empty(), kpi3.empty()

VOICE_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "assets", "voice")


@st.cache_data
def voice_bytes(cue):
    with open(os.path.join(VOICE_DIR, framing.VOICE_FILES[cue]), "rb") as f:
        return f.read()


def id3_tag(n):
    """Thẻ ID3v1 (128 byte, chuẩn metadata cuối file mp3) mang số thứ tự lần phát."""
    title = f"SafeWatch {n}".encode()[:30].ljust(30, b"\x00")
    return b"TAG" + title + bytes(30 + 30 + 4 + 30) + bytes([255])  # nghệ sĩ, album, năm, ghi chú trống; thể loại 255


EXIT_TEXT = {
    None: "Chưa thấy người nào trong khung hình.",
    "left": "Người đã đi ra khỏi khung hình (phía trái).",
    "right": "Người đã đi ra khỏi khung hình (phía phải).",
    "middle": "Mất dấu người ngay giữa khung hình — có thể bị vật che khuất.",
}
FRAMING_TEXT = {framing.OK: "Tốt", framing.TOO_CLOSE: "Quá gần camera", framing.PARTIAL: "Chỉ thấy một phần cơ thể"}

event_log.init_db()
contacts.init_db()


def render_kpis(camera_text, duration_text, duration_sub):
    kpi_card("📷 Camera", camera_text, "Webcam qua trình duyệt", placeholder=camera_card_placeholder)
    kpi_card("⏱️ Thời gian giám sát", duration_text, duration_sub, placeholder=duration_card_placeholder)
    kpi_card("🚨 Báo động hôm nay", str(event_log.count_alarms_today()), "Không tính lần đã tự đứng dậy",
             placeholder=incidents_card_placeholder)


def setup_warnings():
    """Những thứ còn thiếu để cảnh báo tới được người nhà — hiện ngay ở trang chính."""
    out = []
    if not contacts.get_alert_recipients():
        out.append("Chưa có **người liên hệ** nào nhận cảnh báo.")
    if not (notifier.RUNNING and notifier.RUNNING.channels):
        out.append("Chưa bật **kênh gửi** (Telegram / Email / SMS).")
    return out


def render_idle():
    status_banner_placeholder.markdown(
        status_banner_html("idle", "Chưa giám sát", "Bấm START dưới khung camera để bắt đầu theo dõi."),
        unsafe_allow_html=True,
    )
    with detail_placeholder.container(border=True):
        st.markdown("**Bắt đầu nhanh**")
        st.markdown(
            steps_html([
                ("Bấm START và cho phép trình duyệt dùng camera", "Chờ vài giây để hệ thống khởi động."),
                ("Đặt camera cao ~2 m, chéo góc phòng, cách ~3 m",
                 "Thấy được toàn thân và vùng sàn — xem trang Camera & lắp đặt."),
                ("Kiểm tra người nhận cảnh báo", "Ít nhất 1 người liên hệ có Telegram / email / số điện thoại."),
            ]),
            unsafe_allow_html=True,
        )
        for w in setup_warnings():
            st.warning(w, icon="⚠️")
        c1, c2 = st.columns(2)
        c1.page_link("views/camera_management.py", label="Camera & lắp đặt", icon="📷")
        c2.page_link("views/emergency_contacts.py", label="Người liên hệ", icon="📞")
    render_kpis("Chưa bật", "00:00:00", "Chưa bắt đầu")
    st.session_state["camera_online"] = False
    st.session_state["last_status"] = None
    if st.session_state.get("sidebar_status_placeholder") is not None:
        st.session_state["sidebar_status_placeholder"].markdown(sidebar_status_html(False), unsafe_allow_html=True)


if not webrtc_ctx.state.playing:
    st.session_state["_was_playing"] = False
    render_idle()
    st.stop()

if not st.session_state.get("_was_playing"):
    st.session_state["monitor_start_time"] = time.time()
st.session_state["_was_playing"] = True
st.session_state["camera_online"] = True
if st.session_state.get("sidebar_status_placeholder") is not None:
    st.session_state["sidebar_status_placeholder"].markdown(sidebar_status_html(True), unsafe_allow_html=True)

pending_voice = None
while webrtc_ctx.state.playing:
    # Lời nhắc giọng nói: vòng trước đã xoá player cũ, giờ mới tạo player mới -> trình duyệt coi là phần tử mới
    # và tự phát (autoplay được vì người dùng đã bấm START trên trang).
    if pending_voice:
        with voice_placeholder.container():
            st.caption(f"🔊 {framing.VOICE_TEXT[pending_voice]}")
            # Cùng 1 câu nhắc phát lần 2 trong cùng lần chạy -> Streamlit báo trùng ID (ID tính từ nội dung; st.audio
            # bản này không nhận key). Gắn thẻ ID3v1 có số thứ tự vào cuối mp3 -> nội dung khác, máy phát bỏ qua thẻ.
            st.session_state["_voice_play_count"] = st.session_state.get("_voice_play_count", 0) + 1
            st.audio(voice_bytes(pending_voice) + id3_tag(st.session_state["_voice_play_count"]),
                     format="audio/mpeg", autoplay=True)
        pending_voice = None

    processor = webrtc_ctx.video_processor
    if processor is None:
        time.sleep(0.2)
        continue

    # Kiểm tra mất camera + đếm giờ sau ngã ngay cả khi không còn frame nào tới (khi đó recv() không chạy).
    processor.tick()
    state = processor.get_state()
    now = time.time()

    fall_label = state["fall_label"]
    hand_label = state["hand_label"]
    sos_alert = state["sos_alert"]
    fall_down_since = state["fall_down_since"]
    fall_escalated = state["fall_escalated"]
    recovered_message_until = state.get("recovered_message_until", 0.0)
    camera_lost = state.get("camera_lost", False)
    observation_lost = config["enable_fall"] and state.get("observation_lost", False)
    fall_monitoring = config["enable_fall"] and fall_down_since is not None and not fall_escalated
    framing_status = state.get("framing_status", framing.OK) if config["enable_fall"] else framing.OK

    voice_seq = state.get("voice_seq", 0)
    if voice_seq != st.session_state.get("_voice_seq_played"):
        st.session_state["_voice_seq_played"] = voice_seq
        if state.get("voice_cue") and s.get("voice_prompts", True):
            voice_placeholder.empty()
            pending_voice = state["voice_cue"]

    # Thứ tự ưu tiên: khẩn cấp > đang theo dõi sau ngã > không đủ dữ liệu > an toàn.
    # Mất tín hiệu / không thấy người KHÔNG BAO GIỜ được hiển thị là "an toàn".
    if sos_alert:
        level, title, sub = "emergency", "Tình huống khẩn cấp", (
            "Đã gửi cảnh báo tới người liên hệ." if fall_escalated else "Phát hiện cử chỉ cầu cứu — đã gửi cảnh báo.")
    elif fall_monitoring:
        level, title = "monitoring", "Đang theo dõi sau ngã"
        if state.get("vanish_suspected") and observation_lost:
            sub = "Người tụt xuống nhanh rồi khuất giữa khung hình — nghi ngã sau vật cản."
        elif camera_lost:
            sub = "Mất tín hiệu camera sau khi phát hiện ngã — vẫn tiếp tục đếm giờ."
        elif observation_lost:
            sub = "Không còn thấy người sau khi phát hiện ngã — vẫn tiếp tục đếm giờ."
        else:
            sub = "Phát hiện dấu hiệu ngã. Nếu không đứng dậy lại, hệ thống sẽ báo động."
    elif camera_lost:
        level, title = "nodata", "Mất tín hiệu camera"
        sub = f"Không nhận được hình trong {now - state['last_frame_time']:.0f} s — chưa xác nhận được an toàn."
    elif observation_lost:
        level, title = "nodata", "Không có người trong khung hình"
        sub = f"{EXIT_TEXT[state.get('exit_side')]} Chưa thể đánh giá an toàn."
    elif framing_status == framing.TOO_CLOSE:
        level, title = "nodata", "Đứng quá gần camera"
        sub = "Camera không thấy đủ cơ thể nên phát hiện ngã kém chính xác. Xin lùi ra xa khoảng 2–3 m."
    elif framing_status == framing.PARTIAL:
        level, title = "nodata", "Chỉ thấy một phần cơ thể"
        sub = "Người ở sát mép hoặc bị che vai / hông. Xin di chuyển vào giữa khung hình."
    elif now < recovered_message_until:
        level, title, sub = "safe", "Đã đứng dậy lại", "Người dùng đã đứng lên — cảnh báo được huỷ, không báo động."
    else:
        level, title, sub = "safe", "An toàn", "Không phát hiện ngã hoặc tín hiệu cầu cứu."
    st.session_state["last_status"] = {"safe": "safe", "monitoring": "monitoring", "emergency": "emergency"}.get(
        level, "nodata")

    with status_banner_placeholder.container():
        st.markdown(status_banner_html(level, title, sub), unsafe_allow_html=True)
        if fall_monitoring:
            remaining = max(0, config["fall_grace_seconds"] - (now - fall_down_since))
            st.progress(min(1.0, (now - fall_down_since) / config["fall_grace_seconds"]),
                        text=f"Còn {remaining:.0f} s trước khi báo động")

    rows = [
        ("Phát hiện ngã", engine.friendly_fall_label(fall_label) if config["enable_fall"] else "Đã tắt"),
        ("Khung hình", "—" if not config["enable_fall"] or observation_lost else FRAMING_TEXT[framing_status]),
        ("Cử chỉ tay", engine.friendly_hand_label(hand_label) if config["enable_hand"] else "Đã tắt"),
    ]
    if state.get("multi_person"):
        down = ", ".join(f"#{pid}" for pid, _x in state.get("people_down", [])) or "không ai"
        rows.append(("Số người / đang ngã", f"{state.get('people_count', 0)} / {down}"))
    with detail_placeholder.container(border=True):
        st.markdown(rows_html(rows), unsafe_allow_html=True)
        with st.expander("Thông số kỹ thuật"):
            st.caption(f"Nhãn thô: ngã `{fall_label}` · tay `{hand_label}` "
                       f"({state['hand_confidence'] * 100:.0f}%) · FPS xử lý {state['fps']:.1f}")
            if config["enable_signal"]:
                st.caption(f"Signal for Help (chuỗi): {'có' if state['signal_detected'] else 'không'} "
                           f"({state['signal_probability'] * 100:.0f}%)")

    elapsed = now - st.session_state["monitor_start_time"]
    hh, rem = divmod(int(elapsed), 3600)
    mm, ss = divmod(rem, 60)
    render_kpis("Mất tín hiệu" if camera_lost else "Đang hoạt động", f"{hh:02d}:{mm:02d}:{ss:02d}", "Đang giám sát")

    time.sleep(0.3)

st.session_state["_was_playing"] = False
st.session_state["camera_online"] = False
st.session_state["last_status"] = None
if st.session_state.get("sidebar_status_placeholder") is not None:
    st.session_state["sidebar_status_placeholder"].markdown(sidebar_status_html(False), unsafe_allow_html=True)

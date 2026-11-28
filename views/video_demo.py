"""Trang Thử bằng video — tải 1 đoạn video lên, SafeWatch chạy đúng bộ nhận diện của camera trực tiếp và cho xem kết
quả (video có khung xương + trạng thái, dải thời gian, khoảnh khắc phát hiện, danh sách sự kiện). Dùng khi không demo
trực tiếp được. Phần xử lý: video_demo.py."""

import os
import tempfile
from html import escape

import pandas as pd
import streamlit as st

import auth
import detection_engine as engine
import notifier
import video_demo
from theme import card, kpi_card, page_header, section, status_banner_html

auth.require(auth.MONITOR)
engine.ensure_settings_defaults()
s = st.session_state

page_header(
    "Thử bằng video",
    "Tải lên một đoạn video quay sẵn. SafeWatch phân tích bằng đúng bộ nhận diện và cấu hình của camera trực tiếp, "
    "rồi cho xem lúc nào phát hiện ngã, lúc nào gửi cảnh báo.",
    icon="upload",
)

config = {k: s.get(k, v) for k, v in engine.SETTINGS_DEFAULTS.items()}
grace_real = float(config["fall_grace_seconds"])

with card("vd_input"):
    up = st.file_uploader("Video (mp4, mov, avi, mkv, webm · tối đa 3 phút)",
                          type=["mp4", "mov", "avi", "mkv", "webm", "m4v"])
    c1, c2 = st.columns(2)
    grace_opts = sorted({grace_real, 10.0, 5.0}, reverse=True)
    grace = c1.selectbox(
        "Thời gian xác minh sau ngã",
        grace_opts,
        format_func=lambda g: f"{g:.0f} giây" + (" (như camera thật)" if g == grace_real else " (rút ngắn để trình diễn)"),
        help="Camera thật chỉ gửi cảnh báo khi người ngã nằm yên suốt thời gian này. Video ngắn hơn thì chọn mức "
             "rút ngắn để thấy được cảnh báo.",
    )
    send = c2.toggle("Gửi cảnh báo thử tới người liên hệ", value=False,
                     help="Tin nhắn ghi rõ là GIẢ LẬP. Tắt thì kết quả chỉ hiện ở trang này.")
    st.caption("Video chỉ lưu tạm trên máy chủ trong lúc phân tích và bị xoá ngay khi xong. Kết quả chỉ nằm trong "
               "phiên đăng nhập này, không ghi vào Nhật ký. Chỉ dùng video của người đã đồng ý.")
    run = st.button("Phân tích video", type="primary", disabled=up is None)


def _models(with_signal):
    """Cùng mô hình với trang Trực tiếp (đã cache trong detection_engine)."""
    fall_model, hand_model, signal_model = engine.load_models()
    if s.get("fall_model_version", "v2") == "v2" and engine.load_fall_v2() is not None:
        fall_model = engine.load_fall_v2()
    signal_model = signal_model if with_signal else None
    engine.warm_up_models(fall_model, hand_model, signal_model)
    return fall_model, hand_model, signal_model


if run and up is not None:
    suffix = os.path.splitext(up.name)[1].lower() or ".mp4"
    fd, path = tempfile.mkstemp(suffix=suffix)
    try:
        with os.fdopen(fd, "wb") as f:
            f.write(up.getbuffer())
        info = video_demo.probe(path)
        if info is None:
            st.error("Không đọc được video này. Thử xuất lại sang MP4 (H.264).")
            st.stop()
        if info[0] > video_demo.MAX_SECONDS + 1:
            st.error(f"Video dài {info[0]:.0f} giây — tối đa {video_demo.MAX_SECONDS} giây. Cắt bớt rồi tải lại.")
            st.stop()
        cfg = dict(config)
        cfg["fall_grace_seconds"] = float(grace)
        with st.spinner("Đang nạp mô hình…"):
            fall_model, hand_model, signal_model = _models(bool(cfg["enable_signal"]))
        if cfg["enable_signal"] and signal_model is None:
            cfg["enable_signal"] = False
        bar = st.progress(0.0, text="Đang phân tích…")
        result = video_demo.analyze(path, cfg, fall_model, hand_model, signal_model,
                                    progress=lambda x: bar.progress(x, text=f"Đang phân tích… {x * 100:.0f}%"))
        bar.empty()
    finally:
        try:
            os.remove(path)
        except OSError:
            pass
    result["ten"] = up.name
    auth.audit("phan_tich_video", f"{result['thoi_luong']:.0f}s · {len(result['canh_bao'])} cảnh báo")
    if send and result["canh_bao"]:
        for a in result["canh_bao"]:
            notifier.raise_alert(a["ten"], f"{a['chi_tiet']} · từ video thử, giây {a['t']:.0f}", source="simulated")
        result["da_gui"] = len(result["canh_bao"])
    s["video_demo_result"] = result

r = s.get("video_demo_result")
if r is None:
    st.stop()


def mmss(t):
    return f"{int(t // 60):02d}:{t % 60:04.1f}".replace(".", ",")


section(f"Kết quả · {escape(r['ten'])}")
falls = [e for e in r["su_kien"] if e["ten"] == "Phát hiện ngã"]
if r["canh_bao"]:
    a = r["canh_bao"][0]
    st.markdown(status_banner_html("emergency", f"Đã gửi cảnh báo lúc {mmss(a['t'])}: {escape(a['ten'])}",
                                   escape(a["chi_tiet"])), unsafe_allow_html=True)
elif r["dang_xac_minh"] is not None:
    left = r["xac_minh_giay"] - r["dang_xac_minh"]
    st.markdown(status_banner_html(
        "monitoring", "Đã phát hiện ngã, video hết khi đang xác minh",
        f"Người đã nằm {r['dang_xac_minh']:.0f}/{r['xac_minh_giay']:.0f} giây. Nếu vẫn nằm yên, camera thật sẽ gửi "
        f"cảnh báo sau {left:.0f} giây nữa. Chọn thời gian xác minh ngắn hơn để thấy cảnh báo trong video này."),
        unsafe_allow_html=True)
elif falls:
    st.markdown(status_banner_html("safe", "Có phát hiện ngã nhưng người đã đứng dậy",
                                   "Không gửi cảnh báo — đúng như thiết kế."), unsafe_allow_html=True)
else:
    st.markdown(status_banner_html("safe", "Không phát hiện ngã hay cử chỉ SOS", "Không có cảnh báo nào."),
                unsafe_allow_html=True)
if r.get("da_gui"):
    st.success(f"Đã gửi {r['da_gui']} cảnh báo thử (GIẢ LẬP) tới người liên hệ — xem ở trang Cảnh báo.")

k1, k2, k3, k4 = st.columns(4)
with k1:
    kpi_card("Độ dài video", f"{r['thoi_luong']:.0f} s", f"{r['so_khung']} khung AI (10 / giây)", icon="video")
with k2:
    kpi_card("Phát hiện ngã", mmss(falls[0]["t"]) if falls else "—",
             f"{len(falls)} lần" if falls else "không có", icon="activity", tone="amber")
with k3:
    kpi_card("Cảnh báo", str(len(r["canh_bao"])), mmss(r["canh_bao"][0]["t"]) if r["canh_bao"] else "không có",
             icon="siren", tone="rose")
with k4:
    kpi_card("Thời gian phân tích", f"{r['xu_ly_giay']:.0f} s", "trên máy chủ này", icon="clock", tone="slate")

# Dải trạng thái theo thời gian
total = max(r["thoi_luong"], 0.1)
segs = "".join(
    f'<div title="{mmss(t0)}–{mmss(t1)}: {video_demo.STATUS_TEXT[k]}" style="flex:{max(t1 - t0, 0.05):.2f} 0 0;'
    f'background:{video_demo.STATUS_HEX[k]};"></div>' for t0, t1, k in r["dai_trang_thai"])
used = {k for _, _, k in r["dai_trang_thai"]}
legend = "".join(
    f'<span style="display:inline-flex;align-items:center;gap:6px;margin-right:16px;">'
    f'<span style="width:10px;height:10px;border-radius:2px;background:{video_demo.STATUS_HEX[k]}"></span>'
    f'{video_demo.STATUS_TEXT[k]}</span>' for k in video_demo.STATUS_TEXT if k in used)
with card("vd_strip"):
    st.markdown(
        f'<div style="font-weight:600;margin-bottom:8px;">Diễn biến theo thời gian</div>'
        f'<div style="display:flex;gap:2px;height:22px;border-radius:4px;overflow:hidden;">{segs}</div>'
        f'<div style="display:flex;justify-content:space-between;font-size:12px;color:#71717A;margin-top:4px;">'
        f'<span>00:00</span><span>{mmss(total)}</span></div>'
        f'<div style="font-size:13px;color:#3F3F46;margin-top:8px;">{legend}</div>',
        unsafe_allow_html=True)

v_col, e_col = st.columns([3, 2], gap="large")
with v_col, card("vd_video"):
    if r["video"]:
        st.video(r["video"], format="video/mp4")
        st.download_button("Tải video kết quả", r["video"], file_name="safewatch_ket_qua.mp4", mime="video/mp4")
    else:
        st.info("Máy chủ không tạo được video kết quả (thiếu bộ mã hoá H.264). Phần phân tích bên cạnh vẫn đúng.")
with e_col, card("vd_events"):
    st.markdown("**Sự kiện**")
    if r["su_kien"]:
        names = {"canh_bao": "Cảnh báo", "su_kien": "Sự kiện", "trang_thai": "Trạng thái"}
        st.dataframe(pd.DataFrame([{"Lúc": mmss(e["t"]), "Loại": names[e["loai"]], "Nội dung": e["ten"],
                                    "Chi tiết": e["chi_tiet"]} for e in r["su_kien"]]),
                     hide_index=True, width="stretch")
    else:
        st.caption("Không có sự kiện nào.")

if r["anh"]:
    section("Khoảnh khắc phát hiện")
    cols = st.columns(min(3, len(r["anh"])))
    for i, (t, name, jpg) in enumerate(r["anh"]):
        cols[i % len(cols)].image(jpg, caption=f"{mmss(t)} · {name}", width="stretch")

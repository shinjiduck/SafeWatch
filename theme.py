"""Design tokens + CSS + thành phần giao diện dùng chung cho toàn app SafeWatch — 1 nơi duy nhất định nghĩa
màu / chữ / thẻ để các trang không lệch nhau. Trang nào cũng dựng bằng các hàm ở đây (page_header, kpi_card,
status_banner_html...), không tự viết HTML riêng.

Màu trạng thái có nghĩa cố định trong toàn app:
  xanh lá = an toàn · cam = đang theo dõi sau ngã · đỏ = khẩn cấp · xám = chưa đủ dữ liệu / chưa giám sát
(xám KHÔNG BAO GIỜ được dùng cho "an toàn" — yêu cầu BTC: mất hình không được hiện là an toàn).
"""

import streamlit as st

COLOR_SAFE = "#16A34A"
COLOR_MONITORING = "#EA580C"
COLOR_EMERGENCY = "#DC2626"
COLOR_NODATA = "#475569"
COLOR_NAVY = "#0F172A"
COLOR_BLUE = "#2563EB"
COLOR_BG = "#F6F7F9"
COLOR_CARD = "#FFFFFF"
COLOR_BORDER = "#E5E7EB"
COLOR_TEXT_MUTED = "#64748B"

APP_NAME = "SafeWatch"
APP_TAGLINE = "Giám sát an toàn cá nhân bằng AI"

LEVELS = {
    # level: (lớp CSS banner, màu chính, nền nhạt, chữ trên nền nhạt)
    "safe": ("sw-lv-safe", COLOR_SAFE, "#DCFCE7", "#166534"),
    "monitoring": ("sw-lv-monitoring", COLOR_MONITORING, "#FFEDD5", "#9A3412"),
    "emergency": ("sw-lv-emergency", COLOR_EMERGENCY, "#FEE2E2", "#991B1B"),
    "nodata": ("sw-lv-nodata", COLOR_NODATA, "#E2E8F0", "#334155"),
    "idle": ("sw-lv-idle", "#94A3B8", "#F1F5F9", "#475569"),
    "info": ("sw-lv-info", COLOR_BLUE, "#DBEAFE", "#1E40AF"),
}

_CSS = f"""
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&display=swap');

/* Font chỉ đặt ở gốc (kế thừa xuống), không dùng selector rộng — tránh đè font icon của Streamlit. */
html, body, .stApp {{ font-family: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif; font-size: 16px; }}
.stApp {{ background-color: {COLOR_BG}; }}
.block-container {{ padding-top: 5.5rem; padding-bottom: 3rem; max-width: 1280px; }}

/* ---------- Sidebar ---------- */
[data-testid="stSidebar"] {{ background: #FFFFFF; border-right: 1px solid {COLOR_BORDER}; }}
[data-testid="stSidebarNav"] a span, [data-testid="stSidebarNavItems"] a span {{ font-size: 0.98rem !important; }}
[data-testid="stSidebarNav"] [data-testid="stNavSectionHeader"] {{
    font-size: 0.72rem !important; letter-spacing: 0.06em; text-transform: uppercase; color: {COLOR_TEXT_MUTED};
}}
.sw-brand {{ display: flex; align-items: center; gap: 0.6rem; padding: 0.25rem 0 0.5rem 0; }}
.sw-brand-mark {{
    width: 36px; height: 36px; border-radius: 10px; background: {COLOR_NAVY}; color: white;
    display: flex; align-items: center; justify-content: center; font-weight: 800; font-size: 0.95rem;
}}
.sw-brand-name {{ font-weight: 800; font-size: 1.1rem; color: {COLOR_NAVY}; line-height: 1.1; }}
.sw-brand-tagline {{ font-size: 0.74rem; color: {COLOR_TEXT_MUTED}; }}
.sw-side-status {{
    display: flex; align-items: center; gap: 0.5rem; padding: 0.55rem 0.75rem; border-radius: 10px;
    font-size: 0.86rem; font-weight: 600;
}}
.sw-dot {{ width: 9px; height: 9px; border-radius: 50%; display: inline-block; flex: none; }}
.sw-profile {{ display: flex; align-items: center; gap: 0.6rem; }}
.sw-avatar {{
    width: 36px; height: 36px; border-radius: 50%; background: {COLOR_BLUE}; color: white; flex: none;
    display: flex; align-items: center; justify-content: center; font-weight: 700;
}}

/* ---------- Tiêu đề trang ---------- */
.sw-page-head {{ margin: 0 0 1.25rem 0; }}
.sw-page-title {{ font-size: 1.75rem; font-weight: 800; color: {COLOR_NAVY}; line-height: 1.2; margin: 0; }}
.sw-page-sub {{ color: {COLOR_TEXT_MUTED}; font-size: 0.95rem; margin-top: 0.3rem; }}
.sw-section {{ font-size: 1.05rem; font-weight: 700; color: {COLOR_NAVY}; margin: 1.4rem 0 0.6rem 0; }}

/* ---------- Thẻ chỉ số ---------- */
.sw-kpi-label {{ font-size: 0.8rem; color: {COLOR_TEXT_MUTED}; font-weight: 600; }}
.sw-kpi-value {{ font-size: 1.6rem; font-weight: 800; color: {COLOR_NAVY}; line-height: 1.25; }}
.sw-kpi-sub {{ font-size: 0.8rem; color: {COLOR_TEXT_MUTED}; }}
[data-testid="stVerticalBlockBorderWrapper"] {{ background: {COLOR_CARD}; border-radius: 14px; }}

/* ---------- Banner trạng thái lớn ---------- */
.sw-banner {{
    border-radius: 16px; padding: 1.25rem 1.4rem; color: white; display: flex; gap: 1rem; align-items: flex-start;
}}
.sw-banner-icon {{ font-size: 2rem; line-height: 1; }}
.sw-banner-title {{ font-size: 1.35rem; font-weight: 800; letter-spacing: 0.01em; }}
.sw-banner-sub {{ font-size: 0.92rem; opacity: 0.95; margin-top: 0.25rem; }}
.sw-lv-safe {{ background: linear-gradient(135deg, #16A34A, #15803D); }}
.sw-lv-monitoring {{ background: linear-gradient(135deg, #F97316, #C2410C); }}
.sw-lv-emergency {{ background: linear-gradient(135deg, #DC2626, #991B1B); animation: sw-pulse 1.4s infinite; }}
.sw-lv-nodata {{ background: linear-gradient(135deg, #64748B, #334155); }}
.sw-lv-idle {{ background: #FFFFFF; color: {COLOR_NAVY}; border: 1px dashed #CBD5E1; }}
.sw-lv-info {{ background: linear-gradient(135deg, #2563EB, #1D4ED8); }}
@keyframes sw-pulse {{ 0%, 100% {{ box-shadow: 0 0 0 0 rgba(220,38,38,0.45); }} 50% {{ box-shadow: 0 0 0 10px rgba(220,38,38,0); }} }}

/* ---------- Dòng chi tiết (nhãn: giá trị) ---------- */
.sw-row {{
    display: flex; justify-content: space-between; gap: 1rem; padding: 0.55rem 0;
    border-bottom: 1px solid #F1F5F9; font-size: 0.92rem;
}}
.sw-row:last-child {{ border-bottom: none; }}
.sw-row-label {{ color: {COLOR_TEXT_MUTED}; }}
.sw-row-value {{ color: {COLOR_NAVY}; font-weight: 600; text-align: right; }}

/* ---------- Huy hiệu ---------- */
.sw-badge {{
    display: inline-flex; align-items: center; gap: 0.3rem; padding: 0.18rem 0.6rem; border-radius: 999px;
    font-size: 0.76rem; font-weight: 700; white-space: nowrap;
}}

/* ---------- Các bước hướng dẫn ---------- */
.sw-step {{ display: flex; gap: 0.75rem; align-items: flex-start; padding: 0.45rem 0; }}
.sw-step-num {{
    width: 26px; height: 26px; border-radius: 50%; background: {COLOR_NAVY}; color: white; flex: none;
    display: flex; align-items: center; justify-content: center; font-size: 0.8rem; font-weight: 700;
}}
.sw-step-text {{ font-size: 0.92rem; color: {COLOR_NAVY}; }}
.sw-step-text small {{ color: {COLOR_TEXT_MUTED}; display: block; }}

hr {{ margin: 0.75rem 0; }}

@media (max-width: 640px) {{
    .block-container {{ padding-left: 1rem; padding-right: 1rem; }}
    .sw-page-title {{ font-size: 1.4rem; }}
    .sw-banner {{ padding: 1rem; }}
    .sw-banner-title {{ font-size: 1.15rem; }}
}}
</style>
"""


def inject_global_theme():
    st.markdown(_CSS, unsafe_allow_html=True)


# ------------------------------------------------------------------ sidebar


def render_sidebar_brand():
    st.markdown(
        f"""<div class="sw-brand"><div class="sw-brand-mark">SW</div>
        <div><div class="sw-brand-name">{APP_NAME}</div><div class="sw-brand-tagline">{APP_TAGLINE}</div></div></div>""",
        unsafe_allow_html=True,
    )


def render_sidebar_profile(name="Người dùng", role=""):
    initial = name.strip()[0].upper() if name.strip() else "?"
    st.markdown(
        f"""<div class="sw-profile"><div class="sw-avatar">{initial}</div><div>
        <div style="font-weight:600;color:{COLOR_NAVY};font-size:0.95rem;">{name}</div>
        <div style="font-size:0.8rem;color:{COLOR_TEXT_MUTED};">{role}</div></div></div>""",
        unsafe_allow_html=True,
    )


def sidebar_status_html(system_online):
    """Ô trạng thái giám sát ở sidebar — trang Trực tiếp cập nhật liên tục trong vòng lặp webcam."""
    level = "safe" if system_online else "idle"
    _, color, bg, fg = LEVELS[level]
    text = "Đang giám sát" if system_online else "Chưa giám sát"
    return (f'<div class="sw-side-status" style="background:{bg};color:{fg};">'
            f'<span class="sw-dot" style="background:{color};"></span>{text}</div>')


# ------------------------------------------------------------------ khối dùng chung trong trang


def fmt_duration(seconds):
    """Số giây -> chữ dễ đọc: 42 s · 3 phút · 2,5 giờ · 4 ngày."""
    if seconds is None:
        return "—"
    if seconds < 60:
        return f"{seconds:.0f} s"
    if seconds < 3600:
        return f"{seconds / 60:.0f} phút"
    if seconds < 86400:
        return f"{seconds / 3600:.1f} giờ".replace(".", ",")
    return f"{seconds / 86400:.0f} ngày"


def page_header(title, subtitle=""):
    sub = f'<div class="sw-page-sub">{subtitle}</div>' if subtitle else ""
    st.markdown(f'<div class="sw-page-head"><div class="sw-page-title">{title}</div>{sub}</div>',
                unsafe_allow_html=True)


def section(title):
    st.markdown(f'<div class="sw-section">{title}</div>', unsafe_allow_html=True)


def kpi_html(label, value, sub=""):
    sub_html = f'<div class="sw-kpi-sub">{sub}</div>' if sub else ""
    return f'<div class="sw-kpi-label">{label}</div><div class="sw-kpi-value">{value}</div>{sub_html}'


def kpi_card(label, value, sub="", placeholder=None):
    target = placeholder.container(border=True) if placeholder is not None else st.container(border=True)
    with target:
        st.markdown(kpi_html(label, value, sub), unsafe_allow_html=True)


def status_banner_html(level, title, subtitle="", icon=None):
    """level: safe | monitoring | emergency | nodata | idle | info."""
    css = LEVELS[level][0]
    icon = icon or {"safe": "✅", "monitoring": "⏳", "emergency": "🚨", "nodata": "⚠️", "idle": "⏸️", "info": "ℹ️"}[level]
    return (f'<div class="sw-banner {css}"><div class="sw-banner-icon">{icon}</div><div>'
            f'<div class="sw-banner-title">{title}</div><div class="sw-banner-sub">{subtitle}</div></div></div>')


def badge_html(level, text):
    """level: safe | monitoring | emergency | nodata | idle | info | neutral (= idle)."""
    _, _, bg, fg = LEVELS["idle" if level == "neutral" else level]
    return f'<span class="sw-badge" style="background:{bg};color:{fg};">{text}</span>'


def rows_html(rows):
    """[(nhãn, giá trị)] -> danh sách dòng nhãn bên trái, giá trị bên phải."""
    return "".join(f'<div class="sw-row"><span class="sw-row-label">{k}</span><span class="sw-row-value">{v}</span></div>'
                   for k, v in rows)


def steps_html(steps):
    """[(tiêu đề, ghi chú)] -> các bước đánh số."""
    return "".join(f'<div class="sw-step"><div class="sw-step-num">{i}</div><div class="sw-step-text">{t}'
                   f'<small>{n}</small></div></div>' for i, (t, n) in enumerate(steps, 1))

"""Design tokens + CSS + thành phần giao diện dùng chung cho toàn app SafeWatch — 1 nơi duy nhất định nghĩa
màu / chữ / thẻ để các trang không lệch nhau. Trang nào cũng dựng bằng các hàm ở đây (page_header, kpi_card,
card, status_banner_html...), không tự viết HTML riêng. Màu nền / nút / thanh bên: .streamlit/config.toml.

Màu trạng thái có nghĩa cố định trong toàn app:
  xanh lá = an toàn · cam = đang theo dõi sau ngã · đỏ = khẩn cấp · xám = chưa đủ dữ liệu / chưa giám sát
(xám KHÔNG BAO GIỜ được dùng cho "an toàn" — yêu cầu BTC: mất hình không được hiện là an toàn).
Màu thương hiệu (nút, điểm nhấn) là CHÀM — không dùng đỏ cho nút vì đỏ nghĩa là khẩn cấp.
"""

import re

import streamlit as st

COLOR_SAFE = "#16A34A"
COLOR_MONITORING = "#EA580C"
COLOR_EMERGENCY = "#DC2626"
COLOR_NODATA = "#475569"
COLOR_NAVY = "#0F172A"
COLOR_BRAND = "#4F46E5"
COLOR_BRAND_2 = "#7C3AED"
COLOR_BLUE = "#2563EB"
COLOR_BG = "#F5F7FB"
COLOR_CARD = "#FFFFFF"
COLOR_BORDER = "#E6EAF2"
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
    "info": ("sw-lv-info", COLOR_BRAND, "#E0E7FF", "#3730A3"),
}

# Tông màu cho ô biểu tượng của thẻ chỉ số (nền nhạt, chữ đậm)
TONES = {
    "indigo": ("#EEF2FF", "#4338CA"),
    "violet": ("#F5F3FF", "#6D28D9"),
    "emerald": ("#ECFDF5", "#047857"),
    "amber": ("#FFFBEB", "#B45309"),
    "rose": ("#FFF1F2", "#BE123C"),
    "sky": ("#F0F9FF", "#0369A1"),
    "slate": ("#F1F5F9", "#334155"),
}

_SHADOW = "0 1px 2px rgba(16,24,40,.04), 0 10px 28px -14px rgba(16,24,40,.18)"

_CSS = f"""
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&display=swap');

/* Font chỉ đặt ở gốc (kế thừa xuống), không dùng selector rộng — tránh đè font icon của Streamlit. */
html, body, .stApp {{ font-family: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif; font-size: 16px; }}
.stApp {{
    background:
        radial-gradient(1200px 500px at 100% -10%, rgba(124,58,237,.06), transparent 60%),
        radial-gradient(900px 400px at -10% -10%, rgba(79,70,229,.07), transparent 60%),
        {COLOR_BG};
}}
[data-testid="stHeader"] {{ background: rgba(245,247,251,.72); backdrop-filter: blur(8px); }}
.block-container {{ padding-top: 4.6rem; padding-bottom: 3rem; max-width: 1280px; }}

/* ---------- Thanh bên tối ---------- */
[data-testid="stSidebar"] {{ border-right: none; box-shadow: 4px 0 24px -12px rgba(15,23,42,.5); }}
[data-testid="stSidebarNavLink"] {{ border-radius: 10px; margin: 1px 0; transition: background .15s ease; }}
[data-testid="stSidebarNavLink"] span {{ font-size: 0.96rem !important; }}
[data-testid="stSidebarNavLink"]:hover {{ background: rgba(148,163,184,.12) !important; }}
[data-testid="stSidebarNavLink"][aria-current="page"] {{
    background: linear-gradient(90deg, rgba(129,140,248,.28), rgba(129,140,248,.06)) !important;
    box-shadow: inset 3px 0 0 #818CF8;
}}
[data-testid="stSidebarNavLink"][aria-current="page"] p {{ color: #FFFFFF; font-weight: 700; }}
[data-testid="stNavSectionHeader"] p {{
    font-size: 0.7rem !important; letter-spacing: .08em; text-transform: uppercase; color: #64748B !important;
    font-weight: 700;
}}
[data-testid="stSidebar"] hr {{ border-color: rgba(148,163,184,.18); }}
.sw-side-status {{
    display: flex; align-items: center; gap: .55rem; padding: .6rem .8rem; border-radius: 12px;
    font-size: .86rem; font-weight: 600; border: 1px solid rgba(148,163,184,.18);
}}
.sw-dot {{ width: 9px; height: 9px; border-radius: 50%; display: inline-block; flex: none; }}
.sw-dot-live {{ animation: sw-glow 1.8s infinite; }}
@keyframes sw-glow {{ 0%, 100% {{ box-shadow: 0 0 0 0 rgba(34,197,94,.55); }} 50% {{ box-shadow: 0 0 0 6px rgba(34,197,94,0); }} }}
.sw-profile {{ display: flex; align-items: center; gap: .65rem; }}
.sw-avatar {{
    width: 38px; height: 38px; border-radius: 12px; flex: none; color: white; font-weight: 800;
    display: flex; align-items: center; justify-content: center;
    background: linear-gradient(135deg, {COLOR_BRAND}, {COLOR_BRAND_2});
}}
.sw-profile-name {{ font-weight: 700; font-size: .93rem; color: #F1F5F9; }}
.sw-profile-role {{ font-size: .78rem; color: #94A3B8; }}

/* ---------- Tiêu đề trang (băng màu) ---------- */
.sw-hero {{
    display: flex; gap: 1rem; align-items: center; padding: 1.15rem 1.4rem; margin: 0 0 1.4rem 0;
    border-radius: 20px; border: 1px solid {COLOR_BORDER}; box-shadow: {_SHADOW};
    background:
        radial-gradient(500px 160px at 0% 0%, rgba(79,70,229,.10), transparent 70%),
        radial-gradient(420px 160px at 100% 0%, rgba(124,58,237,.10), transparent 70%),
        #FFFFFF;
}}
.sw-hero-icon {{
    width: 52px; height: 52px; border-radius: 16px; flex: none; font-size: 1.6rem;
    display: flex; align-items: center; justify-content: center;
    background: linear-gradient(135deg, #EEF2FF, #F5F3FF); border: 1px solid #E0E7FF;
}}
.sw-hero-title {{ font-size: 1.6rem; font-weight: 800; color: {COLOR_NAVY}; line-height: 1.2; letter-spacing: -.01em; }}
.sw-hero-sub {{ color: {COLOR_TEXT_MUTED}; font-size: .93rem; margin-top: .25rem; }}
.sw-section {{
    font-size: 1.02rem; font-weight: 750; color: {COLOR_NAVY}; margin: 1.5rem 0 .65rem 0;
    display: flex; align-items: center; gap: .5rem;
}}
.sw-section::before {{
    content: ""; width: 4px; height: 1.05rem; border-radius: 4px;
    background: linear-gradient(180deg, {COLOR_BRAND}, {COLOR_BRAND_2});
}}

/* ---------- Thẻ chỉ số ---------- */
.sw-kpi {{
    display: flex; gap: .9rem; align-items: center; background: {COLOR_CARD}; border: 1px solid {COLOR_BORDER};
    border-radius: 16px; padding: .95rem 1.1rem; box-shadow: {_SHADOW}; min-height: 104px;
    transition: transform .15s ease, box-shadow .15s ease;
}}
.sw-kpi:hover {{ transform: translateY(-2px); box-shadow: 0 1px 2px rgba(16,24,40,.05), 0 16px 32px -14px rgba(16,24,40,.25); }}
.sw-kpi-icon {{
    width: 46px; height: 46px; border-radius: 14px; flex: none; font-size: 1.35rem;
    display: flex; align-items: center; justify-content: center;
}}
.sw-kpi-label {{ font-size: .8rem; color: {COLOR_TEXT_MUTED}; font-weight: 600; }}
.sw-kpi-value {{ font-size: 1.55rem; font-weight: 800; color: {COLOR_NAVY}; line-height: 1.2; letter-spacing: -.01em; }}
.sw-kpi-sub {{ font-size: .77rem; color: {COLOR_TEXT_MUTED}; }}

/* ---------- Thẻ nội dung (st.container(key="swbox_...")) ---------- */
[class*="st-key-swbox"] {{
    background: {COLOR_CARD}; border: 1px solid {COLOR_BORDER} !important; border-radius: 16px !important;
    box-shadow: {_SHADOW}; padding: 1rem 1.1rem !important;
}}
.sw-card {{
    background: {COLOR_CARD}; border: 1px solid {COLOR_BORDER}; border-radius: 16px; padding: .4rem 1.1rem;
    box-shadow: {_SHADOW};
}}

/* ---------- Banner trạng thái lớn ---------- */
.sw-banner {{
    border-radius: 20px; padding: 1.25rem 1.4rem; color: white; display: flex; gap: 1rem; align-items: center;
    box-shadow: 0 18px 36px -18px rgba(15,23,42,.45);
}}
.sw-banner-icon {{
    width: 54px; height: 54px; border-radius: 16px; flex: none; font-size: 1.7rem;
    display: flex; align-items: center; justify-content: center; background: rgba(255,255,255,.18);
    border: 1px solid rgba(255,255,255,.25);
}}
.sw-banner-title {{ font-size: 1.35rem; font-weight: 800; letter-spacing: .005em; }}
.sw-banner-sub {{ font-size: .92rem; opacity: .95; margin-top: .2rem; }}
.sw-lv-safe {{ background: linear-gradient(135deg, #22C55E, #15803D); }}
.sw-lv-monitoring {{ background: linear-gradient(135deg, #FB923C, #C2410C); }}
.sw-lv-emergency {{ background: linear-gradient(135deg, #EF4444, #991B1B); animation: sw-pulse 1.4s infinite; }}
.sw-lv-nodata {{ background: linear-gradient(135deg, #64748B, #334155); }}
.sw-lv-idle {{ background: #FFFFFF; color: {COLOR_NAVY}; border: 1.5px dashed #CBD5E1; box-shadow: none; }}
.sw-lv-idle .sw-banner-icon {{ background: #F1F5F9; border-color: #E2E8F0; }}
.sw-lv-idle .sw-banner-sub {{ color: {COLOR_TEXT_MUTED}; }}
.sw-lv-info {{ background: linear-gradient(135deg, {COLOR_BRAND}, {COLOR_BRAND_2}); }}
@keyframes sw-pulse {{ 0%, 100% {{ box-shadow: 0 0 0 0 rgba(220,38,38,.5); }} 50% {{ box-shadow: 0 0 0 12px rgba(220,38,38,0); }} }}

/* ---------- Dòng chi tiết (nhãn: giá trị) ---------- */
.sw-row {{
    display: flex; justify-content: space-between; gap: 1rem; padding: .62rem 0;
    border-bottom: 1px dashed #EDF0F6; font-size: .92rem;
}}
.sw-row:last-child {{ border-bottom: none; }}
.sw-row-label {{ color: {COLOR_TEXT_MUTED}; }}
.sw-row-value {{ color: {COLOR_NAVY}; font-weight: 650; text-align: right; }}

/* ---------- Huy hiệu ---------- */
.sw-badge {{
    display: inline-flex; align-items: center; gap: .3rem; padding: .2rem .65rem; border-radius: 999px;
    font-size: .75rem; font-weight: 700; white-space: nowrap;
}}

/* ---------- Các bước hướng dẫn ---------- */
.sw-step {{ display: flex; gap: .8rem; align-items: flex-start; padding: .5rem 0; }}
.sw-step-num {{
    width: 28px; height: 28px; border-radius: 9px; color: white; flex: none; font-size: .82rem; font-weight: 800;
    display: flex; align-items: center; justify-content: center;
    background: linear-gradient(135deg, {COLOR_BRAND}, {COLOR_BRAND_2});
}}
.sw-step-text {{ font-size: .93rem; color: {COLOR_NAVY}; font-weight: 600; }}
.sw-step-text small {{ color: {COLOR_TEXT_MUTED}; display: block; font-weight: 400; margin-top: .1rem; }}

/* ---------- Thành phần Streamlit ---------- */
[data-testid="stBaseButton-primary"] {{
    background: linear-gradient(135deg, {COLOR_BRAND}, {COLOR_BRAND_2}) !important; border: none !important;
    box-shadow: 0 8px 18px -8px rgba(79,70,229,.7); font-weight: 700;
}}
[data-testid="stBaseButton-primary"]:hover {{ filter: brightness(1.06); }}
[data-testid="stBaseButton-secondary"] {{ background: #FFFFFF; font-weight: 600; }}
[data-testid="stExpander"] details {{ background: {COLOR_CARD}; border-radius: 14px; border-color: {COLOR_BORDER}; }}
[data-testid="stDataFrame"] {{ border-radius: 14px; overflow: hidden; box-shadow: {_SHADOW}; }}
[data-testid="stTabs"] [data-baseweb="tab-list"] {{ gap: .25rem; }}
[data-testid="stTab"] p {{ font-weight: 600; }}
[data-testid="stAlert"] {{ border-radius: 14px; }}
hr {{ margin: .8rem 0; }}

@media (max-width: 640px) {{
    .block-container {{ padding-left: 1rem; padding-right: 1rem; }}
    .sw-hero {{ padding: 1rem; }} .sw-hero-title {{ font-size: 1.3rem; }} .sw-hero-icon {{ width: 44px; height: 44px; }}
    .sw-banner {{ padding: 1rem; }} .sw-banner-title {{ font-size: 1.12rem; }}
}}
</style>
"""


def inject_global_theme():
    st.markdown(_CSS, unsafe_allow_html=True)


# ------------------------------------------------------------------ sidebar


def render_sidebar_brand():
    """Giữ cho tương thích — logo giờ hiện bằng st.logo ở main.py."""


def render_sidebar_profile(name="Người dùng", role=""):
    initial = name.strip()[0].upper() if name.strip() else "?"
    st.markdown(
        f'<div class="sw-profile"><div class="sw-avatar">{initial}</div><div>'
        f'<div class="sw-profile-name">{name}</div><div class="sw-profile-role">{role}</div></div></div>',
        unsafe_allow_html=True,
    )


def sidebar_status_html(system_online):
    """Ô trạng thái giám sát ở sidebar — trang Trực tiếp cập nhật liên tục trong vòng lặp webcam."""
    if system_online:
        return ('<div class="sw-side-status" style="background:rgba(34,197,94,.12);color:#BBF7D0;">'
                '<span class="sw-dot sw-dot-live" style="background:#22C55E;"></span>Đang giám sát</div>')
    return ('<div class="sw-side-status" style="background:rgba(148,163,184,.08);color:#CBD5E1;">'
            '<span class="sw-dot" style="background:#64748B;"></span>Chưa giám sát</div>')


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


def page_header(title, subtitle="", icon="🛡️"):
    sub = f'<div class="sw-hero-sub">{subtitle}</div>' if subtitle else ""
    st.markdown(
        f'<div class="sw-hero"><div class="sw-hero-icon">{icon}</div><div>'
        f'<div class="sw-hero-title">{title}</div>{sub}</div></div>',
        unsafe_allow_html=True,
    )


def section(title):
    st.markdown(f'<div class="sw-section">{title}</div>', unsafe_allow_html=True)


_EMOJI_PREFIX = re.compile(r"^(\S+)\s+(.*)$")


def kpi_html(label, value, sub="", icon=None, tone="indigo"):
    if icon is None:  # nhãn kiểu "📷 Camera" -> tách emoji thành ô biểu tượng
        m = _EMOJI_PREFIX.match(label)
        if m and not m.group(1)[0].isalnum():
            icon, label = m.group(1), m.group(2)
    bg, fg = TONES.get(tone, TONES["indigo"])
    icon_html = f'<div class="sw-kpi-icon" style="background:{bg};color:{fg};">{icon}</div>' if icon else ""
    sub_html = f'<div class="sw-kpi-sub">{sub}</div>' if sub else ""
    return (f'<div class="sw-kpi">{icon_html}<div><div class="sw-kpi-label">{label}</div>'
            f'<div class="sw-kpi-value">{value}</div>{sub_html}</div></div>')


def kpi_card(label, value, sub="", placeholder=None, icon=None, tone="indigo"):
    """Thẻ chỉ số (HTML thuần — dùng được trong vòng lặp cập nhật qua placeholder)."""
    target = placeholder if placeholder is not None else st
    target.markdown(kpi_html(label, value, sub, icon, tone), unsafe_allow_html=True)


def card(key):
    """Khung nội dung nền trắng, bo góc, đổ bóng. key phải duy nhất trong 1 lần chạy trang."""
    return st.container(border=True, key=f"swbox_{key}")


def card_html(inner):
    return f'<div class="sw-card">{inner}</div>'


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

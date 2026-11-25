"""Design tokens + CSS + thành phần giao diện dùng chung cho toàn app SafeWatch — 1 nơi duy nhất định nghĩa
màu / chữ / thẻ để các trang không lệch nhau. Trang nào cũng dựng bằng các hàm ở đây (page_header, kpi_card,
card, status_banner_html...), không tự viết HTML riêng. Màu nền / nút / thanh bên: .streamlit/config.toml.

Phong cách: sáng, phẳng, viền mảnh, biểu tượng nét (SVG) thay emoji — không chuyển màu / phát sáng.

Màu trạng thái có nghĩa cố định trong toàn app:
  xanh lá = an toàn · cam = đang theo dõi sau ngã · đỏ = khẩn cấp · xám = chưa đủ dữ liệu / chưa giám sát
(xám KHÔNG BAO GIỜ được dùng cho "an toàn" — yêu cầu BTC: mất hình không được hiện là an toàn).
Trạng thái bình thường (an toàn, chưa đủ dữ liệu) dùng nền nhạt; trạng thái cần hành động (theo dõi sau ngã,
khẩn cấp) dùng màu đặc để nổi bật. Màu thương hiệu (nút, điểm nhấn) là CHÀM — không dùng đỏ cho nút.
"""

import re

import streamlit as st

COLOR_SAFE = "#16A34A"
COLOR_MONITORING = "#EA580C"
COLOR_EMERGENCY = "#DC2626"
COLOR_NODATA = "#475569"
COLOR_NAVY = "#0F172A"
COLOR_BRAND = "#4F46E5"
COLOR_BRAND_DARK = "#4338CA"
COLOR_BLUE = "#2563EB"
COLOR_BG = "#F8FAFC"
COLOR_CARD = "#FFFFFF"
COLOR_BORDER = "#E2E8F0"
COLOR_TEXT = "#334155"
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

# Tông màu cho ô biểu tượng (nền nhạt, nét đậm)
TONES = {
    "indigo": ("#EEF2FF", "#4F46E5"),
    "violet": ("#F5F3FF", "#7C3AED"),
    "emerald": ("#ECFDF5", "#059669"),
    "amber": ("#FFFBEB", "#D97706"),
    "rose": ("#FFF1F2", "#E11D48"),
    "sky": ("#F0F9FF", "#0284C7"),
    "slate": ("#F1F5F9", "#475569"),
}

# Biểu tượng nét 24x24 (theo phong cách Lucide, giấy phép ISC). Dùng: svg("bell").
ICONS = {
    "video": '<path d="m16 13 5.2 3.5a.5.5 0 0 0 .8-.4V7.9a.5.5 0 0 0-.8-.4L16 10.5"/><rect x="2" y="6" width="14" height="12" rx="2"/>',
    "bell": '<path d="M6 8a6 6 0 0 1 12 0c0 7 3 9 3 9H3s3-2 3-9"/><path d="M10.3 21a1.94 1.94 0 0 0 3.4 0"/>',
    "list": '<rect x="8" y="2" width="8" height="4" rx="1"/><path d="M16 4h2a2 2 0 0 1 2 2v14a2 2 0 0 1-2 2H6a2 2 0 0 1-2-2V6a2 2 0 0 1 2-2h2"/><path d="M12 11h4M12 16h4M8 11h.01M8 16h.01"/>',
    "phone": '<path d="M22 16.9v3a2 2 0 0 1-2.2 2 19.8 19.8 0 0 1-8.6-3.1 19.5 19.5 0 0 1-6-6A19.8 19.8 0 0 1 2.1 4.2 2 2 0 0 1 4.1 2h3a2 2 0 0 1 2 1.7c.1.9.4 1.9.7 2.8a2 2 0 0 1-.5 2.1L8.1 9.9a16 16 0 0 0 6 6l1.3-1.3a2 2 0 0 1 2.1-.4c.9.3 1.8.6 2.8.7a2 2 0 0 1 1.7 2z"/>',
    "camera": '<path d="M14.5 4h-5L7 7H4a2 2 0 0 0-2 2v9a2 2 0 0 0 2 2h16a2 2 0 0 0 2-2V9a2 2 0 0 0-2-2h-3l-2.5-3z"/><circle cx="12" cy="13" r="3"/>',
    "settings": '<path d="M4 21v-7M4 10V3M12 21v-9M12 8V3M20 21v-5M20 12V3M1 14h6M9 8h6M17 16h6"/>',
    "chart": '<path d="M3 3v18h18"/><path d="M18 17V9M13 17V5M8 17v-3"/>',
    "flask": '<path d="M9 3h6M10 3v6.5L4.5 19a1.5 1.5 0 0 0 1.3 2.2h12.4a1.5 1.5 0 0 0 1.3-2.2L14 9.5V3"/><path d="M7 15h10"/>',
    "user": '<circle cx="12" cy="8" r="4"/><path d="M4 21a8 8 0 0 1 16 0"/>',
    "users": '<path d="M16 21v-2a4 4 0 0 0-4-4H6a4 4 0 0 0-4 4v2"/><circle cx="9" cy="7" r="4"/><path d="M22 21v-2a4 4 0 0 0-3-3.9M16 3.1a4 4 0 0 1 0 7.8"/>',
    "shield": '<path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z"/><path d="m9 12 2 2 4-4"/>',
    "alert": '<path d="M10.3 3.9 1.8 18a2 2 0 0 0 1.7 3h17a2 2 0 0 0 1.7-3L13.7 3.9a2 2 0 0 0-3.4 0z"/><path d="M12 9v4M12 17h.01"/>',
    "siren": '<path d="M7 18v-6a5 5 0 1 1 10 0v6"/><path d="M5 21a1 1 0 0 1 1-1h12a1 1 0 0 1 1 1v1H5zM21 12h1M18.5 4.5 18 5M2 12h1M12 2v1M4.9 4.9l.7.7M12 12v6"/>',
    "clock": '<circle cx="12" cy="12" r="10"/><path d="M12 6v6l4 2"/>',
    "pause": '<circle cx="12" cy="12" r="10"/><path d="M10 15V9M14 15V9"/>',
    "check": '<path d="M22 11.1V12a10 10 0 1 1-5.9-9.1"/><path d="m9 11 3 3L22 4"/>',
    "hand": '<path d="M18 11V6a2 2 0 0 0-4 0v5M14 10V4a2 2 0 0 0-4 0v6M10 10.5V6a2 2 0 0 0-4 0v8"/><path d="M18 8a2 2 0 1 1 4 0v6a8 8 0 0 1-8 8h-2c-2.8 0-4.5-.9-6-2.3l-3.6-3.6a2 2 0 0 1 2.8-2.8L7 15"/>',
    "home": '<path d="m3 9 9-7 9 7v11a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2z"/><path d="M9 22V12h6v10"/>',
    "target": '<circle cx="12" cy="12" r="10"/><circle cx="12" cy="12" r="6"/><circle cx="12" cy="12" r="2"/>',
    "layers": '<rect x="3" y="4" width="18" height="16" rx="2"/><path d="M3 10h18M3 15h18M9 4v6M15 10v5M9 15v5"/>',
    "radio": '<path d="M4.9 19.1C1 15.2 1 8.8 4.9 4.9M7.8 16.2c-2.3-2.3-2.3-6.1 0-8.5M16.2 7.8c2.3 2.3 2.3 6.1 0 8.5M19.1 4.9C23 8.8 23 15.1 19.1 19"/><circle cx="12" cy="12" r="2"/>',
    "mail": '<rect x="2" y="4" width="20" height="16" rx="2"/><path d="m22 7-10 5L2 7"/>',
    "standing": '<circle cx="12" cy="4.5" r="1.8"/><path d="M9 21l3-7 3 7M6 9l6 2 6-2M12 11v3"/>',
    "activity": '<path d="M22 12h-4l-3 9L9 3l-3 9H2"/>',
    "play": '<circle cx="12" cy="12" r="10"/><path d="m10 8 6 4-6 4z"/>',
    "eyeoff": '<path d="M9.9 9.9a3 3 0 1 0 4.2 4.2M10.7 5.1A10.4 10.4 0 0 1 12 5c7 0 10 7 10 7a13 13 0 0 1-1.7 2.7M6.6 6.6A13.5 13.5 0 0 0 2 12s3 7 10 7a9.7 9.7 0 0 0 5.4-1.6M2 2l20 20"/>',
    "info": '<circle cx="12" cy="12" r="10"/><path d="M12 16v-4M12 8h.01"/>',
    "move": '<path d="M12 2v20M2 12h20M5 9l-3 3 3 3M19 9l3 3-3 3M9 5l3-3 3 3M9 19l3 3 3-3"/>',
}

# Emoji cũ trong code -> biểu tượng nét (để lời gọi cũ vẫn chạy, nhưng hiển thị đồng bộ)
EMOJI_ICON = {
    "🎥": "video", "🔔": "bell", "📋": "list", "📞": "phone", "📷": "camera", "⚙️": "settings", "📊": "chart",
    "🧪": "flask", "👤": "user", "👥": "users", "🛡️": "shield", "⏱️": "clock", "🚨": "siren", "🧍": "standing",
    "📨": "mail", "📡": "radio", "✋": "hand", "🤕": "activity", "🎯": "target", "🧱": "layers", "🏠": "home",
    "✅": "check", "⏳": "clock", "⚠️": "alert", "⏸️": "pause", "ℹ️": "info", "📏": "move", "👀": "eyeoff",
}


def svg(name, size=20, color="currentColor", stroke=2):
    """Biểu tượng nét theo tên (ICONS) hoặc emoji cũ (EMOJI_ICON); không có thì trả lại nguyên chữ."""
    name = EMOJI_ICON.get(name, name)
    inner = ICONS.get(name)
    if inner is None:
        return name or ""
    return (f'<svg xmlns="http://www.w3.org/2000/svg" width="{size}" height="{size}" viewBox="0 0 24 24" fill="none" '
            f'stroke="{color}" stroke-width="{stroke}" stroke-linecap="round" stroke-linejoin="round" '
            f'style="display:block">{inner}</svg>')


_SHADOW_SM = "0 1px 2px rgba(16,24,40,.05)"
_SHADOW_MD = "0 1px 3px rgba(16,24,40,.08), 0 1px 2px rgba(16,24,40,.04)"

_CSS = f"""
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&display=swap');

/* Font chỉ đặt ở gốc (kế thừa xuống), không dùng selector rộng — tránh đè font icon của Streamlit. */
html, body, .stApp {{ font-family: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif; font-size: 16px; }}
.stApp {{ background: {COLOR_BG}; color: {COLOR_TEXT}; }}
[data-testid="stHeader"] {{ background: rgba(248,250,252,.85); backdrop-filter: blur(6px); }}
.block-container {{ padding-top: 4.4rem; padding-bottom: 3rem; max-width: 1240px; }}

/* ---------- Thanh bên (trắng) ---------- */
[data-testid="stSidebar"] {{ border-right: 1px solid {COLOR_BORDER}; }}
[data-testid="stSidebarNavLink"] {{ border-radius: 8px; margin: 1px 0; padding-left: .75rem; }}
[data-testid="stSidebarNavLink"] p {{ font-size: .94rem; color: {COLOR_TEXT}; font-weight: 500; }}
[data-testid="stSidebarNavLink"]:hover {{ background: #F1F5F9 !important; }}
[data-testid="stSidebarNavLink"][aria-current="page"] {{ background: #EEF2FF !important; box-shadow: inset 3px 0 0 {COLOR_BRAND}; }}
[data-testid="stSidebarNavLink"][aria-current="page"] p {{ color: {COLOR_BRAND_DARK}; font-weight: 700; }}
[data-testid="stNavSectionHeader"] p {{
    font-size: .7rem !important; letter-spacing: .08em; text-transform: uppercase; color: #94A3B8 !important; font-weight: 700;
}}
.sw-side-status {{
    display: flex; align-items: center; gap: .55rem; padding: .55rem .75rem; border-radius: 10px;
    font-size: .86rem; font-weight: 600; border: 1px solid;
}}
.sw-dot {{ width: 8px; height: 8px; border-radius: 50%; display: inline-block; flex: none; }}
.sw-dot-live {{ animation: sw-glow 1.8s infinite; }}
@keyframes sw-glow {{ 0%, 100% {{ box-shadow: 0 0 0 0 rgba(22,163,74,.45); }} 50% {{ box-shadow: 0 0 0 5px rgba(22,163,74,0); }} }}
.sw-profile {{ display: flex; align-items: center; gap: .65rem; }}
.sw-avatar {{
    width: 36px; height: 36px; border-radius: 50%; flex: none; color: {COLOR_BRAND_DARK}; font-weight: 700;
    display: flex; align-items: center; justify-content: center; background: #EEF2FF; border: 1px solid #C7D2FE;
}}
.sw-profile-name {{ font-weight: 600; font-size: .92rem; color: {COLOR_NAVY}; }}
.sw-profile-role {{ font-size: .78rem; color: {COLOR_TEXT_MUTED}; }}

/* ---------- Tiêu đề trang ---------- */
.sw-hero {{
    display: flex; gap: .9rem; align-items: center; padding: 0 0 1.1rem 0; margin: 0 0 1.5rem 0;
    border-bottom: 1px solid {COLOR_BORDER};
}}
.sw-hero-icon {{
    width: 44px; height: 44px; border-radius: 12px; flex: none; color: {COLOR_BRAND};
    display: flex; align-items: center; justify-content: center; background: #EEF2FF; border: 1px solid #E0E7FF;
}}
.sw-hero-title {{ font-size: 1.6rem; font-weight: 750; color: {COLOR_NAVY}; line-height: 1.2; letter-spacing: -.015em; }}
.sw-hero-sub {{ color: {COLOR_TEXT_MUTED}; font-size: .92rem; margin-top: .2rem; }}
.sw-section {{ font-size: 1rem; font-weight: 700; color: {COLOR_NAVY}; margin: 1.6rem 0 .7rem 0; }}

/* ---------- Thẻ chỉ số ---------- */
.sw-kpi {{
    display: flex; gap: .85rem; align-items: flex-start; background: {COLOR_CARD}; border: 1px solid {COLOR_BORDER};
    border-radius: 12px; padding: 1rem 1.1rem; box-shadow: {_SHADOW_SM}; min-height: 104px;
}}
.sw-kpi-icon {{
    width: 40px; height: 40px; border-radius: 10px; flex: none; display: flex; align-items: center; justify-content: center;
}}
.sw-kpi-label {{ font-size: .8rem; color: {COLOR_TEXT_MUTED}; font-weight: 600; }}
.sw-kpi-value {{ font-size: 1.5rem; font-weight: 750; color: {COLOR_NAVY}; line-height: 1.25; letter-spacing: -.015em; margin-top: .1rem; }}
.sw-kpi-sub {{ font-size: .77rem; color: {COLOR_TEXT_MUTED}; margin-top: .1rem; }}

/* ---------- Thẻ nội dung (st.container(key="swbox_...")) ---------- */
[class*="st-key-swbox"] {{
    background: {COLOR_CARD}; border: 1px solid {COLOR_BORDER} !important; border-radius: 12px !important;
    box-shadow: {_SHADOW_SM}; padding: 1rem 1.15rem !important;
}}
.sw-card {{
    background: {COLOR_CARD}; border: 1px solid {COLOR_BORDER}; border-radius: 12px; padding: .35rem 1.1rem;
    box-shadow: {_SHADOW_SM};
}}

/* ---------- Banner trạng thái lớn ---------- */
.sw-banner {{
    border-radius: 12px; padding: 1.05rem 1.2rem; display: flex; gap: .9rem; align-items: center; border: 1px solid;
}}
.sw-banner-icon {{
    width: 46px; height: 46px; border-radius: 12px; flex: none; display: flex; align-items: center; justify-content: center;
}}
.sw-banner-title {{ font-size: 1.2rem; font-weight: 750; letter-spacing: -.005em; }}
.sw-banner-sub {{ font-size: .9rem; margin-top: .15rem; }}
/* trạng thái bình thường: nền nhạt + vạch màu */
.sw-lv-safe {{ background: #F0FDF4; border-color: #BBF7D0; box-shadow: inset 4px 0 0 {COLOR_SAFE}; color: #14532D; }}
.sw-lv-safe .sw-banner-icon {{ background: #DCFCE7; color: {COLOR_SAFE}; }}
.sw-lv-safe .sw-banner-sub {{ color: #166534; }}
.sw-lv-nodata {{ background: #F8FAFC; border-color: #CBD5E1; box-shadow: inset 4px 0 0 #64748B; color: #1E293B; }}
.sw-lv-nodata .sw-banner-icon {{ background: #E2E8F0; color: #475569; }}
.sw-lv-nodata .sw-banner-sub {{ color: #475569; }}
.sw-lv-idle {{ background: {COLOR_CARD}; border: 1px dashed #CBD5E1; color: {COLOR_NAVY}; }}
.sw-lv-idle .sw-banner-icon {{ background: #F1F5F9; color: #64748B; }}
.sw-lv-idle .sw-banner-sub {{ color: {COLOR_TEXT_MUTED}; }}
.sw-lv-info {{ background: #EEF2FF; border-color: #C7D2FE; box-shadow: inset 4px 0 0 {COLOR_BRAND}; color: #312E81; }}
.sw-lv-info .sw-banner-icon {{ background: #E0E7FF; color: {COLOR_BRAND}; }}
/* trạng thái cần hành động: màu đặc */
.sw-lv-monitoring {{ background: {COLOR_MONITORING}; border-color: #C2410C; color: #FFFFFF; }}
.sw-lv-emergency {{ background: {COLOR_EMERGENCY}; border-color: #B91C1C; color: #FFFFFF; animation: sw-pulse 1.4s infinite; }}
.sw-lv-monitoring .sw-banner-icon, .sw-lv-emergency .sw-banner-icon {{ background: rgba(255,255,255,.18); color: #FFFFFF; }}
.sw-lv-monitoring .sw-banner-sub, .sw-lv-emergency .sw-banner-sub {{ color: rgba(255,255,255,.92); }}
@keyframes sw-pulse {{ 0%, 100% {{ box-shadow: 0 0 0 0 rgba(220,38,38,.45); }} 50% {{ box-shadow: 0 0 0 10px rgba(220,38,38,0); }} }}

/* ---------- Dòng chi tiết (nhãn: giá trị) ---------- */
.sw-row {{
    display: flex; justify-content: space-between; gap: 1rem; padding: .62rem 0;
    border-bottom: 1px solid #F1F5F9; font-size: .92rem;
}}
.sw-row:last-child {{ border-bottom: none; }}
.sw-row-label {{ color: {COLOR_TEXT_MUTED}; }}
.sw-row-value {{ color: {COLOR_NAVY}; font-weight: 600; text-align: right; }}

/* ---------- Huy hiệu ---------- */
.sw-badge {{
    display: inline-flex; align-items: center; gap: .3rem; padding: .15rem .55rem; border-radius: 6px;
    font-size: .74rem; font-weight: 600; white-space: nowrap;
}}

/* ---------- Các bước hướng dẫn ---------- */
.sw-step {{ display: flex; gap: .8rem; align-items: flex-start; padding: .5rem 0; }}
.sw-step-num {{
    width: 26px; height: 26px; border-radius: 50%; color: {COLOR_BRAND_DARK}; flex: none; font-size: .8rem; font-weight: 700;
    display: flex; align-items: center; justify-content: center; background: #EEF2FF; border: 1px solid #C7D2FE;
}}
.sw-step-text {{ font-size: .93rem; color: {COLOR_NAVY}; font-weight: 600; }}
.sw-step-text small {{ color: {COLOR_TEXT_MUTED}; display: block; font-weight: 400; margin-top: .1rem; }}

/* ---------- Nút ---------- */
[data-testid="stBaseButton-primary"], [data-testid="stBaseButton-secondary"], [data-testid="stPageLink-NavLink"] {{
    border-radius: 8px !important; min-height: 40px; font-weight: 600; transition: background .12s, border-color .12s, box-shadow .12s;
}}
[data-testid="stBaseButton-primary"] {{
    background: {COLOR_BRAND} !important; border: 1px solid {COLOR_BRAND_DARK} !important; color: #FFFFFF !important;
    box-shadow: 0 1px 2px rgba(16,24,40,.12), inset 0 1px 0 rgba(255,255,255,.12);
}}
[data-testid="stBaseButton-primary"]:hover {{ background: {COLOR_BRAND_DARK} !important; }}
[data-testid="stBaseButton-primary"]:active, [data-testid="stBaseButton-secondary"]:active {{ transform: translateY(1px); }}
[data-testid="stBaseButton-primary"]:focus-visible, [data-testid="stBaseButton-secondary"]:focus-visible {{
    box-shadow: 0 0 0 3px rgba(79,70,229,.3) !important;
}}
[data-testid="stBaseButton-secondary"] {{
    background: #FFFFFF !important; border: 1px solid #CBD5E1 !important; color: {COLOR_NAVY} !important; box-shadow: {_SHADOW_SM};
}}
[data-testid="stBaseButton-secondary"]:hover {{ background: #F8FAFC !important; border-color: #94A3B8 !important; }}
/* liên kết trang trông như nút phụ */
[data-testid="stPageLink-NavLink"] {{
    background: #FFFFFF; border: 1px solid #CBD5E1; box-shadow: {_SHADOW_SM}; padding: .35rem .9rem !important;
    display: inline-flex !important; width: auto !important;
}}
[data-testid="stPageLink-NavLink"]:hover {{ background: #F8FAFC; border-color: #94A3B8; }}
[data-testid="stPageLink-NavLink"] p {{ color: {COLOR_BRAND_DARK}; font-weight: 600; }}

/* ---------- Thành phần khác ---------- */
[data-testid="stExpander"] details {{ background: {COLOR_CARD}; border-radius: 12px; border-color: {COLOR_BORDER}; box-shadow: {_SHADOW_SM}; }}
[data-testid="stExpander"] summary p {{ font-weight: 600; }}
[data-testid="stDataFrame"] {{ border: 1px solid {COLOR_BORDER}; border-radius: 12px; overflow: hidden; box-shadow: {_SHADOW_SM}; }}
[data-testid="stTab"] p {{ font-weight: 600; }}
[data-testid="stAlert"] {{ border-radius: 10px; }}
hr {{ margin: .8rem 0; border-color: {COLOR_BORDER}; }}

@media (max-width: 640px) {{
    .block-container {{ padding-left: 1rem; padding-right: 1rem; }}
    .sw-hero-title {{ font-size: 1.3rem; }}
    .sw-banner {{ padding: .9rem; }} .sw-banner-title {{ font-size: 1.05rem; }}
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
        return ('<div class="sw-side-status" style="background:#F0FDF4;border-color:#BBF7D0;color:#166534;">'
                '<span class="sw-dot sw-dot-live" style="background:#16A34A;"></span>Đang giám sát</div>')
    return ('<div class="sw-side-status" style="background:#F8FAFC;border-color:#E2E8F0;color:#475569;">'
            '<span class="sw-dot" style="background:#94A3B8;"></span>Chưa giám sát</div>')


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


def page_header(title, subtitle="", icon="shield"):
    sub = f'<div class="sw-hero-sub">{subtitle}</div>' if subtitle else ""
    st.markdown(
        f'<div class="sw-hero"><div class="sw-hero-icon">{svg(icon, 22)}</div><div>'
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
    icon_html = f'<div class="sw-kpi-icon" style="background:{bg};color:{fg};">{svg(icon, 20)}</div>' if icon else ""
    sub_html = f'<div class="sw-kpi-sub">{sub}</div>' if sub else ""
    return (f'<div class="sw-kpi">{icon_html}<div><div class="sw-kpi-label">{label}</div>'
            f'<div class="sw-kpi-value">{value}</div>{sub_html}</div></div>')


def kpi_card(label, value, sub="", placeholder=None, icon=None, tone="indigo"):
    """Thẻ chỉ số (HTML thuần — dùng được trong vòng lặp cập nhật qua placeholder)."""
    target = placeholder if placeholder is not None else st
    target.markdown(kpi_html(label, value, sub, icon, tone), unsafe_allow_html=True)


def card(key):
    """Khung nội dung nền trắng, viền mảnh. key phải duy nhất trong 1 lần chạy trang."""
    return st.container(border=True, key=f"swbox_{key}")


def card_html(inner):
    return f'<div class="sw-card">{inner}</div>'


_LEVEL_ICON = {"safe": "check", "monitoring": "clock", "emergency": "siren", "nodata": "eyeoff", "idle": "pause",
               "info": "info"}


def status_banner_html(level, title, subtitle="", icon=None):
    """level: safe | monitoring | emergency | nodata | idle | info."""
    css = LEVELS[level][0]
    return (f'<div class="sw-banner {css}"><div class="sw-banner-icon">{svg(icon or _LEVEL_ICON[level], 24)}</div>'
            f'<div><div class="sw-banner-title">{title}</div><div class="sw-banner-sub">{subtitle}</div></div></div>')


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

"""Design tokens + CSS + thành phần giao diện dùng chung cho toàn app SafeWatch — 1 nơi duy nhất định nghĩa
màu / chữ / khung để các trang không lệch nhau. Trang nào cũng dựng bằng các hàm ở đây (page_header, kpi_card,
card, status_banner_html...), không tự viết HTML riêng. Màu nền / nút / font: .streamlit/config.toml.

Phong cách: dashboard sáng, trung tính, chuẩn mực (mức hoàn thiện kiểu Stripe / Vercel / Linear).
- 1 họ chữ: Be Vietnam Pro (tự host trong static/fonts, dấu tiếng Việt chuẩn), số dạng bảng (tabular).
- Nền xám rất nhạt, khung trắng viền mảnh; thanh bên là lớp trung tính thứ 2 (xám đậm hơn 1 bậc).
- Nút chính màu mực (gần đen), nút phụ trắng viền. Màu chàm của logo chỉ cho liên kết, viền focus, vùng chọn.
- Không ô icon trang trí, không vạch màu 1 bên, không phát sáng / chuyển màu.

Màu trạng thái có nghĩa cố định trong toàn app, luôn đi kèm chữ + biểu tượng (không dùng màu đơn độc):
  xanh lá = an toàn · hổ phách = đang theo dõi sau ngã · đỏ = khẩn cấp · xám = chưa đủ dữ liệu / chưa giám sát
(xám KHÔNG BAO GIỜ được dùng cho "an toàn" — yêu cầu BTC: mất hình không được hiện là an toàn).
Trạng thái bình thường dùng nền nhạt + viền; trạng thái cần hành động (theo dõi sau ngã, khẩn cấp) dùng màu đặc.
"""

import re

import streamlit as st

# Trung tính (thang kẽm, hơi lạnh)
COLOR_BG = "#F3F4F7"
COLOR_CARD = "#FFFFFF"
COLOR_SUBTLE = "#F4F4F5"
COLOR_BORDER = "#E4E4E7"
COLOR_BORDER_STRONG = "#D4D4D8"
COLOR_NAVY = "#18181B"  # chữ chính / nút chính (giữ tên cũ cho các trang đang import)
COLOR_TEXT = "#3F3F46"
COLOR_TEXT_MUTED = "#71717A"
# Màu logo — chỉ dùng cho liên kết / focus / vùng chọn
COLOR_BRAND = "#0B2A6B"  # navy của chữ "Safe" trong logo: nút chính, công tắc
COLOR_BRAND_DARK = "#061A47"
COLOR_ACCENT = "#0262C9"  # xanh của khiên logo (đậm hơn 1 bậc cho đủ tương phản): icon / liên kết / focus
COLOR_BLUE = "#2563EB"
# Trạng thái
COLOR_SAFE = "#15803D"
COLOR_MONITORING = "#B45309"
COLOR_EMERGENCY = "#DC2626"
COLOR_NODATA = "#52525B"

APP_NAME = "SafeWatch"
APP_TAGLINE = "Giám sát an toàn cá nhân bằng AI"

LEVELS = {
    # level: (lớp CSS banner, màu chính, nền nhạt, chữ trên nền nhạt)
    "safe": ("sw-lv-safe", COLOR_SAFE, "#ECFDF3", "#166534"),
    "monitoring": ("sw-lv-monitoring", COLOR_MONITORING, "#FFF7E6", "#92400E"),
    "emergency": ("sw-lv-emergency", COLOR_EMERGENCY, "#FEF2F2", "#B91C1C"),
    "nodata": ("sw-lv-nodata", COLOR_NODATA, "#F4F4F5", "#3F3F46"),
    "idle": ("sw-lv-idle", "#A1A1AA", "#F4F4F5", "#52525B"),
    "info": ("sw-lv-info", COLOR_ACCENT, "#EFF6FF", "#1E40AF"),
}

# Giữ cho tương thích lời gọi cũ (tone=...) — giao diện mới không còn ô biểu tượng màu.
TONES = {  # (nền nhạt, màu nét) — màu icon theo ý nghĩa của chỉ số
    "indigo": ("#EFF6FF", "#0262C9"), "violet": ("#F5F3FF", "#7C3AED"), "emerald": ("#ECFDF5", "#059669"),
    "amber": ("#FFFBEB", "#D97706"), "rose": ("#FFF1F2", "#E11D48"), "sky": ("#F0F9FF", "#0284C7"),
    "slate": ("#F4F4F5", "#52525B"),
}

# Biểu tượng nét 24x24 (theo phong cách Lucide, giấy phép ISC). Dùng: svg("bell").
ICONS = {
    "video": '<path d="m16 13 5.2 3.5a.5.5 0 0 0 .8-.4V7.9a.5.5 0 0 0-.8-.4L16 10.5"/><rect x="2" y="6" width="14" height="12" rx="2"/>',
    "upload": '<path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/><path d="m17 8-5-5-5 5M12 3v12"/>',
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



_SHADOW_SM = "none"


def _mask_url(name):
    """ICONS[name] -> data URI SVG dùng làm mask (icon menu tô màu bằng background-color)."""
    from urllib.parse import quote
    body = (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="black" stroke-width="2" '
            f'stroke-linecap="round" stroke-linejoin="round">{ICONS[name]}</svg>')
    return f'url("data:image/svg+xml;utf8,{quote(body)}")'


# Icon menu bên trái theo đường dẫn trang (trang mặc định Trực tiếp không có đường dẫn -> icon mặc định = video).
_NAV_ICONS = {"video_demo": "upload", "alerts": "bell","history": "list", "emergency_contacts": "phone", "camera_management": "camera",
              "settings": "settings", "dashboard": "chart", "evaluation": "flask", "version": "info", "account": "user",
              "users": "users", "privacy_center": "shield"}
_NAV_ICON_CSS = "\n".join(
    [f'[data-testid="stSidebarNavLink"] {{ --sw-ico: {_mask_url("video")}; }}']
    + [f'[data-testid="stSidebarNavLink"][href$="/{path}"] {{ --sw-ico: {_mask_url(icon)}; }}'
       for path, icon in _NAV_ICONS.items()]
)
_SHADOW_BTN = "0 1px 2px rgba(24,24,27,.10)"
_FOCUS = f"0 0 0 2px {COLOR_CARD}, 0 0 0 4px {COLOR_ACCENT}"

_CSS = f"""
<style>
/* Font khai báo ở .streamlit/config.toml ([[theme.fontFaces]]) — ở đây chỉ tinh chỉnh hiển thị. */
html, body, .stApp {{ -webkit-font-smoothing: antialiased; text-rendering: optimizeLegibility; }}
.stApp {{ background: {COLOR_BG}; color: {COLOR_NAVY}; }}
[data-testid="stHeader"] {{ background: transparent; height: 2.6rem; }}
.block-container {{ padding-top: 2.4rem; padding-bottom: 4rem; max-width: 1280px; }}

/* ---------- Bề mặt trình duyệt: vùng chọn, con trỏ, focus, thanh cuộn ---------- */
::selection {{ background: #DBEAFE; color: #061A47; }}
.stApp {{ caret-color: {COLOR_ACCENT}; scrollbar-color: {COLOR_BORDER_STRONG} transparent; scrollbar-width: thin; }}
::-webkit-scrollbar {{ width: 10px; height: 10px; }}
::-webkit-scrollbar-thumb {{ background: {COLOR_BORDER_STRONG}; border-radius: 10px; border: 3px solid {COLOR_BG}; }}
::-webkit-scrollbar-track {{ background: transparent; }}
a {{ text-underline-offset: 3px; }}
:focus-visible {{ outline: none; box-shadow: {_FOCUS} !important; border-radius: 8px; }}

/* ---------- Thanh bên: lớp trung tính thứ 2 ---------- */
[data-testid="stSidebar"] {{ border-right: 1px solid {COLOR_BORDER}; }}
[data-testid="stSidebarHeader"] {{ padding-bottom: .75rem; height: auto; }}
/* logo mới (khiên + chữ) cần cao hơn mặc định của st.logo để thấy rõ con mắt trên khiên */
[data-testid="stSidebarLogo"], [data-testid="stSidebarHeader"] [data-testid="stLogo"] {{ height: 2.9rem !important; max-width: 100%; }}
[data-testid="stHeader"] [data-testid="stLogo"] {{ height: 2.2rem !important; }}
[data-testid="stSidebarNavLink"] {{
    border-radius: 8px; margin: 0; padding: 0 .75rem; height: 2.45rem; line-height: 2.45rem; border: 1px solid transparent;
    transition: background-color .15s ease-out, border-color .15s ease-out;
}}
[data-testid="stSidebarNavLink"] p {{ font-size: 1rem; color: {COLOR_TEXT}; font-weight: 500; }}
[data-testid="stSidebarNavLink"]:hover {{ background: {COLOR_SUBTLE} !important; }}
[data-testid="stSidebarNavLink"][aria-current="page"] {{ background: {COLOR_SUBTLE} !important; }}
[data-testid="stSidebarNavLink"][aria-current="page"] p {{ color: {COLOR_NAVY}; font-weight: 600; }}
[data-testid="stSidebarNavLink"]::before {{
    content: ""; width: 18px; height: 18px; flex: none; margin-right: .65rem; background-color: #71717A;
    -webkit-mask: var(--sw-ico) center / contain no-repeat; mask: var(--sw-ico) center / contain no-repeat;
}}
[data-testid="stSidebarNavLink"][aria-current="page"]::before {{ background-color: {COLOR_ACCENT}; }}
{_NAV_ICON_CSS}
[data-testid="stNavSectionHeader"] {{ margin-top: .9rem; }}
[data-testid="stSidebarNavItems"] li {{ margin: 0 !important; }}
[data-testid="stNavSectionHeader"] p {{
    font-size: .82rem !important; color: {COLOR_TEXT_MUTED} !important; font-weight: 600; letter-spacing: 0;
    text-transform: none;
}}
.sw-side-status {{
    display: flex; align-items: center; gap: .6rem; padding: .6rem .75rem; border-radius: 8px;
    font-size: .95rem; font-weight: 600; background: {COLOR_CARD}; border: 1px solid {COLOR_BORDER}; color: {COLOR_NAVY};
}}
.sw-side-status small {{ display: block; font-weight: 400; color: {COLOR_TEXT_MUTED}; font-size: .84rem; }}
.sw-dot {{ width: 8px; height: 8px; border-radius: 50%; display: inline-block; flex: none; }}
.sw-dot-live {{ animation: sw-live 2s ease-in-out infinite; }}
@keyframes sw-live {{ 0%, 100% {{ opacity: 1; }} 50% {{ opacity: .35; }} }}
.sw-profile {{ display: flex; align-items: center; gap: .65rem; }}
.sw-avatar {{
    width: 34px; height: 34px; border-radius: 50%; flex: none; color: {COLOR_CARD}; font-weight: 600; font-size: .9rem;
    display: flex; align-items: center; justify-content: center; background: {COLOR_BRAND};
}}
.sw-profile-name {{ font-weight: 600; font-size: .98rem; color: {COLOR_NAVY}; }}
.sw-profile-role {{ font-size: .85rem; color: {COLOR_TEXT_MUTED}; }}
[data-testid="stSidebar"] hr {{ margin: 1rem 0; }}

/* ---------- Tiêu đề trang + mục ---------- */
.sw-topbar {{
    display: flex; justify-content: space-between; align-items: center; gap: 1rem; flex-wrap: wrap;
    padding-bottom: .85rem; margin-bottom: 1.4rem; border-bottom: 1px solid {COLOR_BORDER};
}}
.sw-crumbs {{ display: flex; align-items: center; gap: .45rem; font-size: .92rem; color: {COLOR_TEXT_MUTED}; }}
.sw-crumbs b {{ color: {COLOR_NAVY}; font-weight: 600; }}
.sw-crumbs .sep {{ color: #A1A1AA; }}
.sw-topmeta {{ display: flex; align-items: center; gap: .6rem; flex-wrap: wrap; font-size: .9rem; color: {COLOR_TEXT}; }}
.sw-chip {{
    display: inline-flex; align-items: center; gap: .45rem; padding: .32rem .8rem; border-radius: 6px;
    background: {COLOR_CARD}; border: 1px solid {COLOR_BORDER}; font-size: .88rem; color: {COLOR_TEXT}; white-space: nowrap;
    text-decoration: none !important; transition: border-color .15s ease-out, background-color .15s ease-out;
}}
a.sw-chip:hover {{ border-color: {COLOR_BORDER_STRONG}; background: {COLOR_SUBTLE}; }}
.sw-chip-alert {{ background: #FEF2F2; border-color: #FECACA; color: #B91C1C !important; font-weight: 600; }}
a.sw-chip-alert:hover {{ background: #FEE2E2; border-color: #FCA5A5; }}
.sw-chip-alert .sw-dot {{ background: {COLOR_EMERGENCY}; animation: sw-ping 1.6s ease-out infinite; }}
.sw-hero {{ margin: 0 0 1.9rem 0; display: flex; gap: 1.1rem; align-items: center; }}
.sw-hero-icon {{
    width: 52px; height: 52px; border-radius: 8px; flex: none; color: {COLOR_ACCENT}; background: {COLOR_CARD}; border: 1px solid {COLOR_BORDER};
    display: flex; align-items: center; justify-content: center;
}}
.sw-hero-title {{
    font-size: 2.05rem; font-weight: 700; color: {COLOR_NAVY}; line-height: 1.2; letter-spacing: -.02em; text-wrap: balance;
}}
.sw-hero-sub {{ color: {COLOR_TEXT_MUTED}; font-size: 1.02rem; margin-top: .3rem; max-width: 80ch; line-height: 1.5; }}
.sw-section {{
    font-size: 1.22rem; font-weight: 600; color: {COLOR_NAVY}; margin: 2.4rem 0 .85rem 0; letter-spacing: -.005em;
}}

/* ---------- Dải chỉ số: các cột chứa .sw-kpi ghép thành 1 khung, ngăn bằng vạch mảnh ---------- */
[data-testid="stHorizontalBlock"]:has(> [data-testid="stColumn"] .sw-kpi) {{
    gap: 0 !important; background: {COLOR_CARD}; border: 1px solid {COLOR_BORDER}; border-radius: 8px;
    box-shadow: {_SHADOW_SM}; overflow: hidden;
}}
[data-testid="stHorizontalBlock"]:has(> [data-testid="stColumn"] .sw-kpi) > [data-testid="stColumn"] + [data-testid="stColumn"] {{
    border-left: 1px solid {COLOR_BORDER};
}}
.sw-kpi {{ padding: 1.2rem 1.4rem 1.25rem; min-height: 118px; }}
[data-testid="stMarkdownContainer"]:has(> .sw-kpi, > .sw-banner, > .sw-card) {{ margin-bottom: 0 !important; }}
.sw-kpi-label {{ font-size: .95rem; color: {COLOR_TEXT}; font-weight: 500; display: flex; align-items: center; gap: .5rem; }}
.sw-kpi-ico {{ width: 20px; height: 20px; background: none !important; display: flex; align-items: center; justify-content: center; flex: none; }}
.sw-kpi-value {{
    font-size: 2.1rem; font-weight: 600; color: {COLOR_NAVY}; line-height: 1.15; letter-spacing: -.025em; margin-top: .45rem;
    font-variant-numeric: tabular-nums;
}}
.sw-kpi-sub {{ font-size: .88rem; color: {COLOR_TEXT_MUTED}; margin-top: .25rem; }}

/* ---------- Khung nội dung (st.container(key="swbox_...")) ---------- */
[class*="st-key-swbox"] {{
    background: {COLOR_CARD}; border: 1px solid {COLOR_BORDER} !important; border-radius: 8px !important;
    box-shadow: {_SHADOW_SM}; padding: 1.1rem 1.25rem !important;
}}
.sw-card {{
    background: {COLOR_CARD}; border: 1px solid {COLOR_BORDER}; border-radius: 8px; padding: .25rem 1.25rem;
    box-shadow: {_SHADOW_SM};
}}

/* ---------- Banner trạng thái (trạng thái là thông tin số 1 — đọc được từ xa) ---------- */
.sw-banner {{
    border-radius: 8px; padding: 1.05rem 1.2rem; display: flex; gap: .85rem; align-items: flex-start; border: 1px solid;
}}
.sw-banner-icon {{ flex: none; margin-top: .15rem; }}
.sw-banner-title {{ font-size: 1.55rem; font-weight: 700; letter-spacing: -.015em; line-height: 1.25; }}
.sw-banner-sub {{ font-size: 1rem; margin-top: .25rem; line-height: 1.5; }}
.sw-lv-safe {{ background: #ECFDF3; border-color: #ABEFC6; color: #14532D; }}
.sw-lv-safe .sw-banner-icon {{ color: {COLOR_SAFE}; }}
.sw-lv-safe .sw-banner-sub {{ color: #166534; }}
.sw-lv-nodata {{ background: {COLOR_SUBTLE}; border-color: {COLOR_BORDER_STRONG}; color: {COLOR_NAVY}; }}
.sw-lv-nodata .sw-banner-icon {{ color: {COLOR_NODATA}; }}
.sw-lv-nodata .sw-banner-sub {{ color: {COLOR_TEXT}; }}
.sw-lv-idle {{ background: {COLOR_CARD}; border-color: {COLOR_BORDER}; color: {COLOR_NAVY}; }}
.sw-lv-idle .sw-banner-icon {{ color: {COLOR_TEXT_MUTED}; }}
.sw-lv-idle .sw-banner-sub {{ color: {COLOR_TEXT_MUTED}; }}
.sw-lv-info {{ background: #EFF6FF; border-color: #BFDBFE; color: #1E3A8A; }}
.sw-lv-info .sw-banner-icon {{ color: {COLOR_BRAND}; }}
/* cần hành động: màu đặc, chữ trắng (tương phản ≥ 4.5:1) */
.sw-lv-monitoring {{ background: {COLOR_MONITORING}; border-color: #92400E; color: #FFFFFF; }}
.sw-lv-emergency {{ background: {COLOR_EMERGENCY}; border-color: #B91C1C; color: #FFFFFF; }}
.sw-lv-monitoring .sw-banner-icon, .sw-lv-emergency .sw-banner-icon {{ color: #FFFFFF; }}
.sw-lv-monitoring .sw-banner-sub, .sw-lv-emergency .sw-banner-sub {{ color: rgba(255,255,255,.94); }}

/* ---------- Dòng chi tiết (nhãn: giá trị) ---------- */
.sw-row {{
    display: flex; justify-content: space-between; gap: 1rem; padding: .7rem 0;
    border-bottom: 1px solid {COLOR_SUBTLE}; font-size: 1rem;
}}
.sw-row:last-child {{ border-bottom: none; }}
.sw-row-label {{ color: {COLOR_TEXT_MUTED}; white-space: nowrap; }}
.sw-row-value {{ color: {COLOR_NAVY}; font-weight: 500; text-align: right; font-variant-numeric: tabular-nums; }}

/* ---------- Huy hiệu: chấm màu + chữ ---------- */
.sw-badge {{
    display: inline-flex; align-items: center; gap: .4rem; padding: .16rem .6rem .16rem .5rem; border-radius: 6px;
    font-size: .84rem; font-weight: 500; white-space: nowrap; line-height: 1.4;
}}
.sw-badge::before {{ content: ""; width: 6px; height: 6px; border-radius: 50%; background: currentColor; }}

/* ---------- Các bước hướng dẫn ---------- */
.sw-step {{ display: flex; gap: .8rem; align-items: flex-start; padding: .55rem 0; }}
.sw-step-num {{
    width: 24px; height: 24px; border-radius: 50%; color: {COLOR_NAVY}; flex: none; font-size: .78rem; font-weight: 600;
    display: flex; align-items: center; justify-content: center; background: {COLOR_CARD};
    border: 1px solid {COLOR_BORDER_STRONG}; font-variant-numeric: tabular-nums;
}}
.sw-step-text {{ font-size: 1rem; color: {COLOR_NAVY}; font-weight: 500; line-height: 1.45; }}
.sw-step-text small {{ color: {COLOR_TEXT_MUTED}; display: block; font-weight: 400; margin-top: .15rem; font-size: .9rem; }}

/* ---------- Nút ---------- */
[data-testid="stBaseButton-primary"], [data-testid="stBaseButton-secondary"], [data-testid="stPageLink-NavLink"] {{
    border-radius: 8px !important; min-height: 40px; font-weight: 500;
    transition: background-color .15s ease-out, border-color .15s ease-out, color .15s ease-out;
}}
[data-testid="stBaseButton-primary"] {{
    background: {COLOR_BRAND} !important; border: 1px solid {COLOR_BRAND_DARK} !important; color: #FFFFFF !important;
    box-shadow: none; font-weight: 600;
}}
[data-testid="stBaseButton-primary"]:hover {{ background: {COLOR_BRAND_DARK} !important; }}
[data-testid="stBaseButton-primary"]:active {{ background: #061A47 !important; }}
[data-testid="stBaseButton-secondary"] {{
    background: {COLOR_CARD} !important; border: 1px solid {COLOR_BORDER_STRONG} !important; color: {COLOR_NAVY} !important;
    box-shadow: {_SHADOW_SM};
}}
[data-testid="stBaseButton-secondary"]:hover {{ background: {COLOR_SUBTLE} !important; border-color: #A1A1AA !important; }}
[data-testid="stBaseButton-primary"]:disabled, [data-testid="stBaseButton-secondary"]:disabled {{
    background: {COLOR_SUBTLE} !important; border-color: {COLOR_BORDER} !important; color: #A1A1AA !important; box-shadow: none;
}}
[data-testid="stBaseButton-primary"]:focus-visible, [data-testid="stBaseButton-secondary"]:focus-visible,
[data-testid="stPageLink-NavLink"]:focus-visible {{ box-shadow: {_FOCUS} !important; }}
/* liên kết trang trông như nút phụ */
[data-testid="stPageLink-NavLink"] {{
    background: {COLOR_CARD}; border: 1px solid {COLOR_BORDER_STRONG}; box-shadow: {_SHADOW_SM}; padding: .4rem .95rem !important;
    display: inline-flex !important; width: auto !important;
}}
[data-testid="stPageLink-NavLink"]:hover {{ background: {COLOR_SUBTLE}; border-color: #A1A1AA; }}
[data-testid="stPageLink-NavLink"] p {{ color: {COLOR_NAVY}; font-weight: 500; }}

/* ---------- Thành phần khác ---------- */
[data-testid="stExpander"] details {{ background: {COLOR_CARD}; border-radius: 8px; border-color: {COLOR_BORDER}; }}
[data-testid="stExpander"] summary p {{ font-weight: 500; }}
[data-testid="stExpander"] summary:hover p {{ color: {COLOR_NAVY}; }}
[data-testid="stDataFrame"] {{ border: 1px solid {COLOR_BORDER}; border-radius: 8px; overflow: hidden; }}
[data-testid="stTab"] p {{ font-weight: 500; }}
[data-testid="stTab"][aria-selected="true"] p {{ font-weight: 600; }}
[data-testid="stAlert"] {{ border-radius: 10px; }}
[data-testid="stCaptionContainer"], [data-testid="stCaptionContainer"] p {{ color: {COLOR_TEXT_MUTED} !important; opacity: 1; }}
[data-testid="stMetricValue"] {{ font-variant-numeric: tabular-nums; }}
hr {{ margin: .9rem 0; border-color: {COLOR_BORDER}; }}
[data-testid="stForm"] {{ background: {COLOR_CARD}; border: 1px solid {COLOR_BORDER}; border-radius: 8px; padding: 1.25rem 1.4rem; }}
/* Form nằm trong 1 khung (card) thì không kẻ thêm khung thứ 2; bỏ dòng "Press Enter to submit form" đè lên ô nhập. */
[class*="st-key-swbox"] [data-testid="stForm"] {{ border: none; padding: 0; background: transparent; box-shadow: none; }}
[data-testid="InputInstructions"] {{ display: none; }}
[data-testid="stBaseButton-primaryFormSubmit"] {{
    background: {COLOR_BRAND} !important; border: 1px solid {COLOR_BRAND_DARK} !important; color: #FFFFFF !important;
    border-radius: 8px !important; min-height: 40px; font-weight: 600;
}}
[data-testid="stBaseButton-primaryFormSubmit"]:hover {{ background: {COLOR_BRAND_DARK} !important; }}
[data-testid="stBaseButton-secondaryFormSubmit"] {{
    background: {COLOR_CARD} !important; border: 1px solid {COLOR_BORDER_STRONG} !important; border-radius: 8px !important; min-height: 40px;
}}
[data-testid="stMarkdownContainer"] code {{ color: {COLOR_TEXT}; background: {COLOR_SUBTLE}; border-radius: 4px; }}
.sw-alert-head {{ display: flex; align-items: center; gap: .6rem; flex-wrap: wrap; }}
.sw-alert-kind {{ font-weight: 600; font-size: 1.12rem; color: {COLOR_NAVY}; }}
.sw-alert-meta {{ color: {COLOR_TEXT_MUTED}; font-size: .95rem; margin-top: .35rem; font-variant-numeric: tabular-nums; }}

@media (max-width: 640px) {{
    .block-container {{ padding-left: 1rem; padding-right: 1rem; padding-top: 3rem; }}
    .sw-hero {{ margin-bottom: 1.25rem; }}
    .sw-hero-title {{ font-size: 1.55rem; }}
    .sw-hero-icon {{ width: 44px; height: 44px; }}
    .sw-topmeta .sw-date {{ display: none; }}
    .sw-banner {{ padding: .9rem 1rem; }} .sw-banner-title {{ font-size: 1.3rem; }}
    /* cột xếp chồng -> vạch ngăn nằm ngang */
    [data-testid="stHorizontalBlock"]:has(> [data-testid="stColumn"] .sw-kpi) > [data-testid="stColumn"] + [data-testid="stColumn"] {{
        border-left: none; border-top: 1px solid {COLOR_BORDER};
    }}
    .sw-kpi {{ min-height: 0; padding: .85rem 1rem; }}
    .sw-kpi-value {{ font-size: 1.7rem; }}
}}
/* ================= Hiệu ứng — ngắn (150–300 ms), báo trạng thái / phản hồi thao tác, chỉ CSS (không tốn CPU) =========
   Chỉ gắn hiệu ứng "vào trang" cho khung trang (dựng 1 lần mỗi lần chuyển trang). KHÔNG gắn cho banner / ô chỉ số:
   trang Trực tiếp vẽ lại chúng mỗi 0,3 s, hiệu ứng vào sẽ chạy lại liên tục. */
@keyframes sw-enter {{ from {{ opacity: 0; transform: translateY(6px); }} to {{ opacity: 1; transform: none; }} }}
[data-testid="stMainBlockContainer"] {{ animation: sw-enter .32s cubic-bezier(.16,1,.3,1) both; }}
[data-testid="stTabPanel"] {{ animation: sw-enter .25s cubic-bezier(.16,1,.3,1) both; }}

/* khung trắng: viền đậm dần khi rê chuột */
[class*="st-key-swbox"], .sw-card, [data-testid="stExpander"] details, [data-testid="stForm"] {{
    transition: border-color .18s ease-out, box-shadow .18s ease-out;
}}
[class*="st-key-swbox"]:hover, .sw-card:hover {{
    border-color: {COLOR_BORDER_STRONG} !important;
}}
/* ô chỉ số: nền ửng chàm nhạt khi rê chuột, icon nhích nhẹ */
[data-testid="stHorizontalBlock"]:has(> [data-testid="stColumn"] .sw-kpi) > [data-testid="stColumn"] {{
    transition: background-color .18s ease-out;
}}
[data-testid="stHorizontalBlock"]:has(> [data-testid="stColumn"] .sw-kpi) > [data-testid="stColumn"]:hover {{
    background: #FAFAFF;
}}
.sw-kpi-ico {{ transition: transform .2s cubic-bezier(.16,1,.3,1); }}
.sw-kpi:hover .sw-kpi-ico {{ transform: scale(1.08); }}

/* nút: nhấc nhẹ khi rê, lún khi bấm */
[data-testid="stBaseButton-primary"], [data-testid="stBaseButton-secondary"], [data-testid="stPageLink-NavLink"],
[data-testid="stBaseButton-primaryFormSubmit"], [data-testid="stBaseButton-secondaryFormSubmit"] {{
    transition: background-color .15s ease-out, border-color .15s ease-out, transform .15s ease-out, box-shadow .15s ease-out !important;
}}
[data-testid="stBaseButton-primary"]:hover, [data-testid="stBaseButton-primaryFormSubmit"]:hover {{
    box-shadow: none !important;
}}
[data-testid="stBaseButton-secondary"]:hover, [data-testid="stPageLink-NavLink"]:hover {{
    box-shadow: none !important;
}}
[data-testid="stBaseButton-primary"]:active, [data-testid="stBaseButton-secondary"]:active,
[data-testid="stPageLink-NavLink"]:active, [data-testid="stBaseButton-primaryFormSubmit"]:active {{
    transform: translateY(0) scale(.98); box-shadow: none !important;
}}

/* menu: icon trượt nhẹ khi rê, mục đang chọn đổi màu mượt */
[data-testid="stSidebarNavLink"]::before {{ transition: background-color .15s ease-out, transform .2s cubic-bezier(.16,1,.3,1); }}
[data-testid="stSidebarNavLink"]:hover::before {{ transform: translateX(2px); background-color: {COLOR_ACCENT}; }}

/* thanh tiến độ xác minh sau ngã chạy mượt */
[data-testid="stProgress"] [role="progressbar"] > div > div {{ transition: width .3s linear; }}

/* cảnh báo chưa ai nhận: chấm đỏ nhấp nháy (= đang cần người xác nhận) */
@keyframes sw-ping {{ 0% {{ box-shadow: 0 0 0 0 rgba(220,38,38,.55); }} 80%, 100% {{ box-shadow: 0 0 0 6px rgba(220,38,38,0); }} }}
.sw-badge-emergency::before {{ animation: sw-ping 1.6s ease-out infinite; }}
/* banner khẩn cấp: icon còi rung nhẹ theo nhịp */
@keyframes sw-ring {{ 0%, 70%, 100% {{ transform: rotate(0); }} 76% {{ transform: rotate(-12deg); }} 84% {{ transform: rotate(10deg); }} 92% {{ transform: rotate(-6deg); }} }}
.sw-lv-emergency .sw-banner-icon {{ animation: sw-ring 1.8s ease-in-out infinite; transform-origin: 50% 20%; }}
/* đang theo dõi sau ngã: icon đồng hồ "thở" */
@keyframes sw-breathe {{ 0%, 100% {{ opacity: 1; }} 50% {{ opacity: .55; }} }}
.sw-lv-monitoring .sw-banner-icon {{ animation: sw-breathe 1.6s ease-in-out infinite; }}
/* đang kết nối camera: icon sóng "thở" (đang chờ, chưa phải lỗi) */
.sw-lv-info .sw-banner-icon {{ animation: sw-breathe 1.2s ease-in-out infinite; }}

/* ---------- Khoảnh khắc chính: xác nhận đã nhận cảnh báo (mở từ link trong tin nhắn) ----------
   Dấu tick vẽ dần (500 ms) rồi con dấu "ĐÃ NHẬN" đóng xuống. Trạng thái mặc định là trạng thái CUỐI (keyframes
   chỉ có "from") -> tắt hiệu ứng vẫn thấy đủ dấu tick + con dấu. */
.sw-ack {{
    max-width: 580px; margin: 2vh auto 0; background: {COLOR_CARD}; border: 1px solid {COLOR_BORDER}; border-radius: 10px;
    padding: 2.2rem 2rem 1.6rem; text-align: center; 
}}
.sw-ack-mark {{ width: 84px; height: 84px; margin: 0 auto 1rem; color: {COLOR_SAFE}; }}
.sw-ack-mark circle {{ transform: rotate(-90deg); transform-origin: 42px 42px; stroke-dasharray: 239; stroke-dashoffset: 0; animation: sw-draw-ring .55s cubic-bezier(.65,0,.35,1) both; }}
.sw-ack-mark path {{ stroke-dasharray: 48; stroke-dashoffset: 0; animation: sw-draw-tick .35s .45s cubic-bezier(.65,0,.35,1) both; }}
@keyframes sw-draw-ring {{ from {{ stroke-dashoffset: 239; }} }}
@keyframes sw-draw-tick {{ from {{ stroke-dashoffset: 48; }} }}
.sw-ack-mark.sw-ack-warn {{ color: {COLOR_MONITORING}; }}
.sw-ack-title {{ font-size: 1.75rem; font-weight: 700; color: {COLOR_NAVY}; letter-spacing: -.02em; line-height: 1.25; }}
.sw-ack-sub {{ font-size: 1.02rem; color: {COLOR_TEXT}; margin: .5rem auto 0; max-width: 44ch; line-height: 1.55; }}
.sw-stamp {{
    display: inline-flex; flex-direction: column; align-items: center; margin: 1.3rem 0 .4rem; padding: .45rem 1.3rem .4rem;
    border: 3px solid {COLOR_SAFE}; border-radius: 10px; color: {COLOR_SAFE}; transform: rotate(-5deg);
    font-weight: 700; letter-spacing: .1em; font-size: 1.15rem; line-height: 1.2;
    animation: sw-stamp .5s .75s cubic-bezier(.16,1,.3,1) both;
}}
.sw-stamp small {{ letter-spacing: .02em; font-size: .8rem; font-weight: 600; font-variant-numeric: tabular-nums; }}
@keyframes sw-stamp {{ from {{ opacity: 0; transform: rotate(-5deg) scale(1.7); }} }}
.sw-ack .sw-card {{ text-align: left; margin-top: 1.1rem; box-shadow: none; }}
.sw-ack-next {{
    margin-top: 1.1rem; padding: .8rem 1rem; border-radius: 10px; background: #FFF7E6; color: #92400E;
    font-size: .95rem; text-align: left; display: flex; gap: .6rem; align-items: flex-start;
}}

/* ---------- Trạng thái trống: dạy bước tiếp theo, không chỉ "không có gì" ---------- */
.sw-empty {{
    display: flex; gap: 1rem; align-items: center; padding: 1.2rem 1.3rem; border-radius: 8px;
    background: {COLOR_CARD}; border: 1px dashed {COLOR_BORDER_STRONG};
}}
.sw-empty-icon {{
    width: 44px; height: 44px; border-radius: 50%; flex: none; display: flex; align-items: center; justify-content: center;
}}
.sw-empty-title {{ font-weight: 600; font-size: 1.05rem; color: {COLOR_NAVY}; }}
.sw-empty-sub {{ color: {COLOR_TEXT_MUTED}; font-size: .95rem; margin-top: .15rem; }}

@media (prefers-reduced-motion: reduce) {{
    *, *::before {{ animation: none !important; transition: none !important; }}
}}
</style>
"""


def inject_global_theme():
    st.markdown(_CSS, unsafe_allow_html=True)


# ------------------------------------------------------------------ sidebar


def render_sidebar_brand():
    """Giữ cho tương thích — logo giờ hiện bằng st.logo ở main.py."""


def render_sidebar_profile(name="Người dùng", role=""):
    from html import escape

    initial = escape(name.strip()[0].upper()) if name.strip() else "?"
    st.markdown(
        f'<div class="sw-profile"><div class="sw-avatar">{initial}</div><div>'
        f'<div class="sw-profile-name">{escape(name)}</div><div class="sw-profile-role">{escape(role)}</div></div></div>',
        unsafe_allow_html=True,
    )


def sidebar_status_html(system_online):
    """Ô trạng thái giám sát ở sidebar — trang Trực tiếp cập nhật liên tục trong vòng lặp webcam."""
    if system_online:
        return (f'<div class="sw-side-status"><span class="sw-dot sw-dot-live" style="background:{COLOR_SAFE};"></span>'
                '<div>Đang giám sát<small>Camera đang hoạt động</small></div></div>')
    return ('<div class="sw-side-status"><span class="sw-dot" style="background:#A1A1AA;"></span>'
            '<div>Chưa giám sát<small>Mở trang Trực tiếp và bấm Bắt đầu</small></div></div>')


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


# Tiêu đề trang -> (nhóm menu, tên mục) cho dòng đường dẫn ở đầu trang.
_CRUMBS = {
    "Giám sát trực tiếp": ("Giám sát", "Trực tiếp"), "Thử bằng video": ("Giám sát", "Thử bằng video"),
    "Cảnh báo": ("Giám sát", "Cảnh báo"),
    "Nhật ký": ("Giám sát", "Nhật ký"), "Người liên hệ": ("Thiết lập", "Người liên hệ"),
    "Camera & lắp đặt": ("Thiết lập", "Camera & lắp đặt"), "Cấu hình": ("Thiết lập", "Cấu hình"),
    "Tổng quan": ("Báo cáo", "Tổng quan"), "Kiểm định": ("Báo cáo", "Kiểm định"), "Hồ sơ": ("Tài khoản", "Hồ sơ"),
}
_WEEKDAYS = ["Thứ Hai", "Thứ Ba", "Thứ Tư", "Thứ Năm", "Thứ Sáu", "Thứ Bảy", "Chủ Nhật"]


def _pending_alerts():
    """Số cảnh báo chưa ai xác nhận (đọc DB của notifier); lỗi thì coi như 0 — không làm hỏng tiêu đề trang."""
    try:
        import notifier
        return sum(1 for a in notifier.get_alerts(limit=500) if a["acked_at"] is None)
    except Exception:  # noqa: BLE001
        return 0


def topbar_html(title):
    from datetime import datetime
    group, item = _CRUMBS.get(title, (None, title))
    crumbs = ['<span>SafeWatch</span>'] + ([f'<span>{group}</span>'] if group else []) + [f'<b>{item}</b>']
    sep = '<span class="sep">›</span>'
    now = datetime.now()
    meta = [f'<span class="sw-chip sw-date">{svg("clock", 15)}{_WEEKDAYS[now.weekday()]}, {now:%d/%m/%Y}</span>']
    pending = _pending_alerts()
    if pending:
        meta.insert(0, f'<a class="sw-chip sw-chip-alert" href="alerts" target="_self"><span class="sw-dot"></span>'
                       f'{pending} cảnh báo chờ xác nhận</a>')
    return (f'<div class="sw-topbar"><nav class="sw-crumbs" aria-label="Vị trí">{sep.join(crumbs)}</nav>'
            f'<div class="sw-topmeta">{"".join(meta)}</div></div>')


def page_header(title, subtitle="", icon="shield"):
    """Đầu trang: thanh đường dẫn + ngày + cảnh báo chờ, rồi ô icon thương hiệu + tiêu đề + 1 dòng mô tả."""
    sub = f'<div class="sw-hero-sub">{subtitle}</div>' if subtitle else ""
    st.markdown(topbar_html(title) + f'<div class="sw-hero"><div class="sw-hero-icon">{svg(icon or "shield", 26, stroke=2.1)}</div>'
                f'<div><div class="sw-hero-title">{title}</div>{sub}</div></div>', unsafe_allow_html=True)


def section(title):
    st.markdown(f'<div class="sw-section">{title}</div>', unsafe_allow_html=True)


_EMOJI_PREFIX = re.compile(r"^(\S+)\s+(.*)$")


def kpi_html(label, value, sub="", icon=None, tone="indigo"):
    """1 ô chỉ số: [icon màu theo ý nghĩa] nhãn · giá trị · ghi chú. Đặt nhiều ô trong st.columns -> CSS ghép
    thành 1 dải liền. Nhãn kiểu "📷 Camera" (cũ) -> emoji tách thành icon nét."""
    m = _EMOJI_PREFIX.match(str(label))
    if m and not m.group(1)[0].isalnum():
        icon, label = icon or m.group(1), m.group(2)
    bg, fg = TONES.get(tone or "indigo", TONES["indigo"])
    icon_html = (f'<span class="sw-kpi-ico" style="background:{bg};color:{fg};">{svg(icon, 16, stroke=2.2)}</span>'
                 if icon else "")
    sub_html = f'<div class="sw-kpi-sub">{sub}</div>' if sub else ""
    return (f'<div class="sw-kpi"><div class="sw-kpi-label">{icon_html}{label}</div>'
            f'<div class="sw-kpi-value">{value}</div>{sub_html}</div>')


def kpi_card(label, value, sub="", placeholder=None, icon=None, tone="indigo"):
    """Ô chỉ số (HTML thuần — dùng được trong vòng lặp cập nhật qua placeholder)."""
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
    return (f'<div class="sw-banner {css}" role="status"><div class="sw-banner-icon">'
            f'{svg(icon or _LEVEL_ICON[level], 24)}</div>'
            f'<div><div class="sw-banner-title">{title}</div><div class="sw-banner-sub">{subtitle}</div></div></div>')


def empty_html(title, subtitle="", icon="check", tone="emerald"):
    """Trạng thái trống: icon + 1 câu nói rõ tình hình + việc nên làm tiếp."""
    bg, fg = TONES.get(tone, TONES["emerald"])
    sub = f'<div class="sw-empty-sub">{subtitle}</div>' if subtitle else ""
    return (f'<div class="sw-empty"><div class="sw-empty-icon" style="background:{bg};color:{fg};">{svg(icon, 22)}</div>'
            f'<div><div class="sw-empty-title">{title}</div>{sub}</div></div>')


_ACK_MARK = ('<svg class="sw-ack-mark{cls}" viewBox="0 0 84 84" fill="none" stroke="currentColor" stroke-width="5" '
             'stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><circle cx="42" cy="42" r="38"/>'
             '<path d="{path}"/></svg>')


def ack_page_html(result, alert=None):
    """Trang mở từ link "Tôi đã nhận" trong tin nhắn. result: 'new' (lần xác nhận đầu) | 'already' | 'invalid'."""
    from datetime import datetime

    def t(ts):
        return "—" if not ts else datetime.fromtimestamp(ts).strftime("%H:%M:%S · %d/%m/%Y")

    from html import escape

    if result == "expired":
        mark = _ACK_MARK.format(cls=" sw-ack-warn", path="M42 24v22M42 58v.5")
        return (f'<div class="sw-ack">{mark}<div class="sw-ack-title">Link đã hết hạn</div>'
                '<div class="sw-ack-sub">Link xác nhận chỉ dùng được trong 24 giờ kể từ lúc gửi cảnh báo. Hãy gọi điện '
                'kiểm tra người thân, hoặc đăng nhập SafeWatch để xem và xác nhận cảnh báo.</div></div>')
    if result == "invalid" or alert is None:
        mark = _ACK_MARK.format(cls=" sw-ack-warn", path="M42 24v22M42 58v.5")
        return (f'<div class="sw-ack">{mark}<div class="sw-ack-title">Không tìm thấy cảnh báo</div>'
                '<div class="sw-ack-sub">Mã xác nhận trong đường link không đúng hoặc đã bị xoá. Hãy mở link mới nhất '
                'trong tin nhắn, hoặc xem danh sách ở trang Cảnh báo.</div></div>')
    mark = _ACK_MARK.format(cls="", path="M27 43l10 10 20-21")
    stamp_time = datetime.fromtimestamp(alert["acked_at"]).strftime("%H:%M · %d/%m") if alert.get("acked_at") else ""
    rows = rows_html([("Cảnh báo", f'#{alert["id"]} · {escape(str(alert["kind"]))}'),
                      ("Phát hiện lúc", t(alert["detected_at"])), ("Xác nhận lúc", t(alert.get("acked_at")))]
                     + ([("Người xác nhận", escape(str(alert["acked_by"])))]
                        if result == "already" and alert.get("acked_by") else []))
    if result == "new":
        title = "Đã ghi nhận. Cảm ơn bạn!"
        sub = "SafeWatch đã dừng gửi lại và chuyển tiếp cảnh báo này cho những người khác."
        nxt = (f'<div class="sw-ack-next">{svg("phone", 20)}<div><b>Việc cần làm ngay:</b> gọi điện cho người thân '
               'hoặc tới chỗ họ để kiểm tra. Nếu không liên lạc được, hãy gọi 115.</div></div>')
    else:
        title = "Cảnh báo này đã có người nhận"
        sub = "Một người khác đã xác nhận trước bạn, chuỗi cảnh báo đã dừng."
        nxt = ""
    return (f'<div class="sw-ack">{mark}<div class="sw-ack-title">{title}</div><div class="sw-ack-sub">{sub}</div>'
            f'<div class="sw-stamp">ĐÃ NHẬN<small>{stamp_time}</small></div>'
            f'<div class="sw-card">{rows}</div>{nxt}</div>')


def badge_html(level, text):
    """level: safe | monitoring | emergency | nodata | idle | info | neutral (= idle)."""
    _, _, bg, fg = LEVELS["idle" if level == "neutral" else level]
    return f'<span class="sw-badge sw-badge-{level}" style="background:{bg};color:{fg};">{text}</span>'


def rows_html(rows):
    """[(nhãn, giá trị)] -> danh sách dòng nhãn bên trái, giá trị bên phải."""
    return "".join(f'<div class="sw-row"><span class="sw-row-label">{k}</span><span class="sw-row-value">{v}</span></div>'
                   for k, v in rows)


def steps_html(steps):
    """[(tiêu đề, ghi chú)] -> các bước đánh số."""
    return "".join(f'<div class="sw-step"><div class="sw-step-num">{i}</div><div class="sw-step-text">{t}'
                   f'<small>{n}</small></div></div>' for i, (t, n) in enumerate(steps, 1))

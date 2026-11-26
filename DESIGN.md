# Design

SafeWatch is an Operate surface: a monitoring and alerting dashboard used by family caregivers on laptop and phone. The chosen direction is the **category standard done carefully**: a neutral, light dashboard at the craft level of Stripe, Vercel and Linear. It has no themed material world. The tool should disappear into the task.

Source of truth: `theme.py` (tokens, CSS, helpers) and `.streamlit/config.toml` (Streamlit theme, fonts). Pages build only from `theme.py` helpers.

## Color

Strategy: Restrained with a brand accent. The grey ground sets off white panels. The logo indigo carries actions and the current location. State colours appear only where they mean state.

Revision (2026-11-25): the first neutral-only pass read "like a document" to the user. Indigo primary, nav icons, header icon and KPI icons were added back.

Revision (2026-11-26, logo): new logo `Logo 2.png` (blue shield with an eye and a protected person). Accents moved from indigo to the logo's navy and blue. Assets: `logo_light.png` (horizontal lockup), `logo_icon.png`, `logo_mark.png`, `favicon.png`, `logo_full.png`, `logo_source.png`.

Revision (2026-11-26): the bright `#4F46E5` blocks read as "nhựa" (plastic). Bright indigo now lives only in the logo, primary actions use deep indigo, radii are smaller (8px panels, 6px badges and chips), and resting shadows are gone.

| Role | Token | Value |
|---|---|---|
| App ground | `COLOR_BG` | `#F3F4F7` |
| Panels | `COLOR_CARD` | `#FFFFFF` |
| Subtle fills (sidebar is white) | `COLOR_SUBTLE` | `#F4F4F5` |
| Hairline | `COLOR_BORDER` | `#E4E4E7` |
| Control border | `COLOR_BORDER_STRONG` | `#D4D4D8` |
| Text | `COLOR_NAVY` | `#18181B` |
| Secondary text | `COLOR_TEXT` | `#3F3F46` |
| Muted text (≥4.5:1 on white) | `COLOR_TEXT_MUTED` | `#71717A` |
| Logo navy ("Safe"): primary buttons, toggles, segmented control, avatar | `COLOR_BRAND` | `#0B2A6B` (hover `#061A47`) |
| Logo blue (shield, one step darker for contrast): icons (active nav, header), links, focus ring, caret | `COLOR_ACCENT` | `#0262C9` |
| Logo gradient `#0373E0`–`#23BFFD`: **only in the logo** (and the single-series chart `#0373E0`) | — | — |

State colours are reserved. Each always comes with a label and an icon, never colour alone:

| State | Meaning | Normal form | Action form |
|---|---|---|---|
| safe | person seen, no fall | tint `#ECFDF3`, text `#14532D` | n/a |
| monitoring | fall detected, verifying 30–45 s | n/a | solid `#B45309`, white text |
| emergency | alarm raised | n/a | solid `#DC2626`, white text |
| nodata / idle | camera lost, nobody in view, not monitoring | `#F4F4F5` / white | n/a |

Grey never means "safe". Losing vision must not display as safe.

Charts (Altair): alarm `#DC2626`, self-recovered `#2563EB` (CVD-checked), single series `#0373E0`. Grid `#F4F4F5`, axis labels `#71717A`.

## Typography

- One family: **Be Vietnam Pro**, self-hosted in `static/fonts/` (OFL). It is built for Vietnamese diacritics. Weights 400/500/600/700.
- Base 16px (`baseFontSize`). The user asked for larger text (2026-11-26).
- Scale:
  - Page title: 2.05rem/700, tracking −0.02em.
  - Section: 1.22rem/600.
  - Stat value: 2.1rem/600.
  - Status banner title: 1.55rem.
  - Body and rows: 1rem.
  - Nav: 1rem.
  - Captions and metadata: 0.88–0.95rem, muted.
- Numbers in stats, rows and alert metadata use `tabular-nums`.

## Page frame

Every page starts with a **top bar**: a breadcrumb `SafeWatch › group › page` on the left; on the right, a red chip "N cảnh báo chờ xác nhận" linking to Cảnh báo (only when N > 0) and a date chip. A hairline sits below the bar. Then comes the header: a 52px indigo icon square, the title and the subtitle. Content width is at most 1280px.

## Components

- **Page header**: 52px white square with a hairline border and an accent-indigo line icon, then title and a one-line subtitle. No eyebrow label.
- **Stat strip**: `kpi_card` cells placed in `st.columns` merge into one bordered panel with hairline dividers. These become horizontal dividers once the columns stack on a phone. Each cell has a small line icon coloured by meaning (`tone`, no tinted tile), a label, a value and a note.
- **Status banner** (`status_banner_html`): full border plus tint, or solid fill for states that need action, with a leading line icon. No side stripe, no glow.
- **Panels** (`card(key)` / `card_html`). Every page groups its content in panels; loose text on the ground reads as a document: white, 1px hairline, radius 8px, no shadow (hover only darkens the border).
- **Buttons**: primary is solid deep indigo `#312E81` with white text (hover `#1E1B4B`), with no shadow. Secondary is white with a `#D4D4D8` border. Page links look like secondary buttons. Height 40px, radius 8px.
- **Badges**: pill with a dot and the label, tinted by state.
- **Sidebar nav**: white rail. Every item has a line icon (CSS mask, by page path). The active item has a grey `#F4F4F5` fill, an ink label and an accent-indigo icon. Group labels are sentence case and muted.
- **Camera control** (streamlit-webrtc): buttons are translated to Vietnamese ("Bắt đầu giám sát", "Dừng", "Chọn camera") and inherit the indigo primary colour.

## Motion

**Motion thesis (Impeccable animate/delight, 2026-11-26).** The product's defining moment is a carer pressing **"Tôi đã nhận"**, because that is when the alert chain stops. It is the one authored sequence. On the ack page (`/?ack=<token>`, `ack_page_html`):

1. A green ring draws from 12 o'clock (550 ms).
2. The tick draws (350 ms).
3. A rotated **ĐÃ NHẬN** stamp with the acknowledgement time presses down (500 ms, at 750 ms).

The default styles are the final state; the keyframes hold only the `from` values. With reduced motion the page is complete and static. Everything else stays routine feedback:

- A toast after acknowledging on the web.
- A breathing icon while the camera connects (info banner).

Hover never moves the hovered control: it changes only colour, border and shadow.


Pure CSS, short (150–320 ms), ease-out (`cubic-bezier(.16,1,.3,1)`), no JS and no CPU cost for the camera loop.

- **Page / tab enter**: the main container and tab panels fade in and rise 6px once per navigation. Never put enter animations on banners or stat cells, because the live page re-renders them every 0.3 s.
- **Hover feedback**:
  - Panels darken their border and gain a soft shadow.
  - Stat cells tint `#FAFAFF` and their icon scales to 1.08.
  - Buttons gain a shadow (indigo for primary) without moving, and press to 0.98.
  - Nav icons slide 2px and turn indigo.
- **State motion**:
  - Unacknowledged-alert badge dot pings red.
  - Emergency banner siren icon rings.
  - Monitoring clock icon breathes.
  - The live dot pulses ("monitoring is running").
  - The verification progress bar moves smoothly.
- Everything stops under `prefers-reduced-motion`.

## Browser surfaces

- Text selection is indigo-tinted; the caret is indigo.
- `:focus-visible` shows a 2px white gap and a 2px indigo ring.
- Scrollbars are thin and neutral.
- Toolbar is set to `minimal` (no Deploy button).

## Responsive

Streamlit stacks columns below 640px. At that width the gutter becomes 1rem, the title 1.35rem, and the stat-strip dividers turn horizontal. Tap targets stay at 40px or more.

## Refused on purpose

- One-sided accent bars on boxes or the active nav item.
- Gradient text, glass/blur headers, glossy inset highlights and coloured glow shadows at rest (the user asked for "not plastic").
- Emoji as icons.
- Uppercase tracked eyebrow labels.
- Red for buttons (red means emergency).

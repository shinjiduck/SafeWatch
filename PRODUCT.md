# Product

<!-- impeccable:product-schema 1 -->

## Platform

web

## Users

Two audiences weigh equally (confirmed 2026-11-25):

- **Family caregivers**: children or relatives of an elderly person living at home. They keep the page open on a laptop, or open it on a phone from the link in an SMS / Telegram / email alert. Their job is to see that the person is safe, get alerted when they are not, and confirm "I got it" so the alert chain stops.
- **Competition judges (BTC)** at the demo. They need to see the alert chain working end to end, the verification of fall events, the safe state when vision is lost, and the evaluation numbers behind every claim.

## Product Purpose

SafeWatch watches one room through an ordinary webcam. It detects falls (pose model, verified for 30–45 s so a person who gets up by themselves raises no alarm) and an SOS hand gesture. It then sends alerts to emergency contacts over Telegram, email and SMS (eSMS), retrying and forwarding until someone confirms receipt. Success means that no real fall goes unnoticed, that false alarms stay rare, and that someone always acknowledges.

## Positioning

The alert does not stop at "sent". It keeps retrying (5/10/20/40/60 s), forwards to the next contact after 60 s without acknowledgement, runs up to 5 rounds, and records who confirmed, how and when. Every number shown is backed by a held-out evaluation (Le2i, Charades, OmniFall synthetic) with subject/session splits.

## Operating Context

- Streamlit multipage web app (`main.py`, `views/`), webcam via WebRTC in the browser, background notifier thread.
- The camera sits about 2 m high in a room corner. The app tells the person to step back when they are too close, and shows "không có người" (nobody in view) and vanish/occlusion states.
- Acknowledge link `/?ack=<token>` opened from phone messages.
- The demo is often projected; daily use is on a laptop or phone.
- The interface language is Vietnamese.

## Capabilities and Constraints

- One camera (browser webcam). Multi-person tracking is experimental and off by default.
- Channels: Telegram, Email, SMS (eSMS brandname / Android gateway / Twilio).
- Streamlit limits the DOM: styling goes through `theme.py` CSS injection, `.streamlit/config.toml`, and keyed containers (`st-key-*`). Native Streamlit widgets must stay usable.
- CPU is constrained on the demo machine; the UI must not add heavy client work.

## Brand Commitments

- Name **SafeWatch** and the shield logo (`assets/logo*.png`) stay.
- Light background (user requirement). Buttons must read clearly as buttons.
- The previous indigo colour is not binding.

## Evidence on Hand

- Evaluation docs in `training/fall_eval/*.md` and `training/hand_eval/*.md`; results JSON in `training/fall_eval/kiem_dinh_nhieu_nguoi/ket_qua/`.
- Real alert history and latency in the notifier SQLite DB.
- No testimonials, customers or certifications exist. Do not invent any.

## Product Principles

1. A person's safety state is readable within one second, from across a room.
2. An alert is not finished until a human has acknowledged it, and the UI shows exactly where in the chain it is.
3. Every claim on screen traces to a measured number.
4. Calm by default, unmistakable when something is wrong.

## Accessibility & Inclusion

Caregivers may be older adults: large tap targets, high contrast, no colour-only states, Vietnamese diacritics rendered correctly.

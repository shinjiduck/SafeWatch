"""Chuỗi cảnh báo tới người chăm sóc (yêu cầu cải tiến số 1).

Luồng:  phát hiện  ->  raise_alert()  ->  Dispatcher (thread nền)  ->  kênh
gửi (Telegram / Email)  ->  người chăm sóc bấm "Đã nhận"  ->  ack().

- Mỗi cảnh báo và MỖI lần gửi đều lưu SQLite (bảng alerts, deliveries) kèm
  mốc thời gian, nên đo được: phát hiện -> phát cảnh báo -> gửi thành công
  -> người chăm sóc xác nhận.
- Gửi lỗi (mất mạng, server mail lỗi...) -> thử lại với backoff, không mất.
- Chưa ai xác nhận sau ACK_TIMEOUT_SECONDS -> vòng mới: GỬI LẠI cho người đã
  nhận và CHUYỂN TIẾP thêm người liên hệ kế tiếp (theo mức ưu tiên). Hết
  MAX_ROUNDS vòng vẫn chưa ai xác nhận -> trạng thái "unacked" (vẫn hiện đỏ
  trên giao diện, không bao giờ tự coi là đã xử lý).
- "Đã gửi" chỉ có nghĩa là kênh nhận tin (Telegram API / SMTP server) đã
  chấp nhận; "đã nhận" CHỈ được ghi khi người chăm sóc chủ động xác nhận
  (nút Telegram hoặc link xác nhận).

Logic trong Dispatcher.tick() không phụ thuộc thời gian thật hay mạng thật
(clock + channels được truyền vào), nên kiểm thử được hoàn toàn offline —
xem tests/test_notifier.py.
"""

import json
import os
import secrets as _secrets
import smtplib
import ssl
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime
from email.message import EmailMessage

import contacts
import event_log

ACK_TIMEOUT_SECONDS = 60
MAX_ROUNDS = 5
RETRY_BACKOFF_SECONDS = [5, 10, 20, 40, 60]
DISPATCH_INTERVAL_SECONDS = 1.0

RUNNING = None  # Dispatcher đang chạy (main.py gán) — để các trang đọc trạng thái kênh

STATUS_OPEN = "open"
STATUS_ACKED = "acked"
STATUS_UNACKED = "unacked"  # hết số vòng mà chưa ai xác nhận


def _conn():
    return event_log._get_connection()


def init_db():
    contacts.init_db()
    with _conn() as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS alerts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                kind TEXT NOT NULL,
                details TEXT,
                source TEXT NOT NULL DEFAULT 'live',
                detected_at REAL NOT NULL,
                raised_at REAL NOT NULL,
                status TEXT NOT NULL,
                current_round INTEGER NOT NULL DEFAULT 0,
                round_started_at REAL NOT NULL,
                ack_token TEXT NOT NULL UNIQUE,
                acked_at REAL,
                acked_by TEXT,
                acked_via TEXT
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS deliveries (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                alert_id INTEGER NOT NULL,
                round INTEGER NOT NULL,
                contact_id INTEGER,
                contact_name TEXT,
                channel TEXT NOT NULL,
                target TEXT NOT NULL,
                status TEXT NOT NULL,
                created_at REAL NOT NULL,
                attempts INTEGER NOT NULL DEFAULT 0,
                next_try_at REAL NOT NULL,
                last_attempt_at REAL,
                sent_at REAL,
                error TEXT
            )
            """
        )


# --------------------------------------------------------------- API công khai


def raise_alert(kind, details="", detected_at=None, source="live", now=None):
    """Ghi 1 cảnh báo mới (chỉ ghi DB, không gửi gì ở đây — Dispatcher gửi).
    detected_at = lúc hệ thống bắt đầu thấy sự kiện (VD lần đầu nhãn Fall),
    có thể sớm hơn now (VD sau thời gian xác minh sau ngã)."""
    now = time.time() if now is None else now
    detected_at = now if detected_at is None else detected_at
    with _conn() as conn:
        cursor = conn.execute(
            "INSERT INTO alerts (kind, details, source, detected_at, raised_at, status, current_round, "
            "round_started_at, ack_token) VALUES (?, ?, ?, ?, ?, ?, 0, ?, ?)",
            (kind, details, source, detected_at, now, STATUS_OPEN, now, _secrets.token_urlsafe(9)),
        )
        return cursor.lastrowid


def ack(token, by="", via="", now=None):
    """Người chăm sóc xác nhận đã nhận. Trả về True nếu đây là lần xác nhận
    đầu tiên (lần bấm sau không ghi đè mốc thời gian gốc)."""
    now = time.time() if now is None else now
    with _conn() as conn:
        cursor = conn.execute(
            "UPDATE alerts SET status = ?, acked_at = ?, acked_by = ?, acked_via = ? "
            "WHERE ack_token = ? AND acked_at IS NULL",
            (STATUS_ACKED, now, by, via, token),
        )
        if cursor.rowcount:
            conn.execute(
                "UPDATE deliveries SET status = 'cancelled' WHERE status IN ('pending', 'failed') "
                "AND alert_id = (SELECT id FROM alerts WHERE ack_token = ?)",
                (token,),
            )
        return cursor.rowcount > 0


def get_alerts(limit=200):
    with _conn() as conn:
        conn.row_factory = _dict_row
        return conn.execute("SELECT * FROM alerts ORDER BY id DESC LIMIT ?", (limit,)).fetchall()


def get_deliveries(alert_id=None, limit=1000):
    with _conn() as conn:
        conn.row_factory = _dict_row
        if alert_id is None:
            return conn.execute("SELECT * FROM deliveries ORDER BY id DESC LIMIT ?", (limit,)).fetchall()
        return conn.execute("SELECT * FROM deliveries WHERE alert_id = ? ORDER BY id", (alert_id,)).fetchall()


def latency_rows(limit=200):
    """1 dòng/cảnh báo với các mốc thời gian đã tách đoạn — dùng cho bảng
    minh chứng (thời gian từ phát hiện đến khi người chăm sóc xác nhận)."""
    rows = []
    for a in get_alerts(limit):
        ds = get_deliveries(a["id"])
        sent_times = [d["sent_at"] for d in ds if d["sent_at"] is not None]
        first_sent = min(sent_times) if sent_times else None
        rows.append(
            {
                "id": a["id"],
                "kind": a["kind"],
                "source": a["source"],
                "status": a["status"],
                "detected_at": a["detected_at"],
                "verify_s": a["raised_at"] - a["detected_at"],
                "raise_to_sent_s": None if first_sent is None else first_sent - a["raised_at"],
                "sent_to_ack_s": None if (first_sent is None or a["acked_at"] is None) else a["acked_at"] - first_sent,
                "total_s": None if a["acked_at"] is None else a["acked_at"] - a["detected_at"],
                "acked_by": a["acked_by"],
                "acked_via": a["acked_via"],
                "rounds": a["current_round"] + 1,
                "attempts": sum(d["attempts"] for d in ds),
                "failed_attempts": sum(max(0, d["attempts"] - (1 if d["sent_at"] is not None else 0)) for d in ds),
                "recipients": len({(d["contact_id"], d["channel"]) for d in ds}),
            }
        )
    return rows


def _dict_row(cursor, row):
    return {col[0]: row[i] for i, col in enumerate(cursor.description)}


def format_message(alert, ack_url=None):
    detected = datetime.fromtimestamp(alert["detected_at"]).strftime("%H:%M:%S %d/%m/%Y")
    lines = [f"🚨 SafeWatch – {alert['kind']}"]
    if alert.get("details"):
        lines.append(alert["details"])
    lines.append(f"Phát hiện lúc: {detected}")
    if alert.get("source") == "simulated":
        lines.append("(Đây là cảnh báo GIẢ LẬP để kiểm thử.)")
    if ack_url:
        lines.append(f"Xác nhận đã nhận: {ack_url}")
    return "\n".join(lines)


# ------------------------------------------------------------------ Dispatcher


class Dispatcher:
    def __init__(self, channels, clock=time.time, ack_timeout=ACK_TIMEOUT_SECONDS, max_rounds=MAX_ROUNDS,
                 public_base_url=None):
        self.channels = {ch.name: ch for ch in channels}
        self.clock = clock
        self.ack_timeout = ack_timeout
        self.max_rounds = max_rounds
        self.public_base_url = (public_base_url or "").rstrip("/") or None
        self._thread = None
        self._stop = threading.Event()
        self.last_error = None

    def ack_url(self, alert):
        if not self.public_base_url:
            return None
        return f"{self.public_base_url}/?ack={urllib.parse.quote(alert['ack_token'])}"

    def recipients_for_round(self, round_index):
        """Vòng k gửi tới k+1 người ưu tiên cao nhất (gửi lại cho người cũ +
        chuyển tiếp thêm 1 người mới), qua mọi kênh người đó có."""
        people = contacts.get_alert_recipients()[: round_index + 1]
        out = []
        for person in people:
            for ch in self.channels.values():
                target = ch.target_for(person)
                if target:
                    out.append((person, ch.name, str(target)))
        return out

    def _queue_round(self, conn, alert_id, round_index, now):
        for person, channel_name, target in self.recipients_for_round(round_index):
            conn.execute(
                "INSERT INTO deliveries (alert_id, round, contact_id, contact_name, channel, target, status, "
                "created_at, next_try_at) VALUES (?, ?, ?, ?, ?, ?, 'pending', ?, ?)",
                (alert_id, round_index, person["id"], person["name"], channel_name, target, now, now),
            )

    def tick(self):
        now = self.clock()
        with _conn() as conn:
            conn.row_factory = _dict_row
            for alert in conn.execute("SELECT * FROM alerts WHERE status = ?", (STATUS_OPEN,)).fetchall():
                queued = conn.execute(
                    "SELECT COUNT(*) AS n FROM deliveries WHERE alert_id = ? AND round = ?",
                    (alert["id"], alert["current_round"]),
                ).fetchone()["n"]
                if queued == 0 and now - alert["round_started_at"] < self.ack_timeout:
                    self._queue_round(conn, alert["id"], alert["current_round"], now)
                elif now - alert["round_started_at"] >= self.ack_timeout:
                    if alert["current_round"] + 1 < self.max_rounds:
                        next_round = alert["current_round"] + 1
                        conn.execute(
                            "UPDATE alerts SET current_round = ?, round_started_at = ? WHERE id = ?",
                            (next_round, now, alert["id"]),
                        )
                        self._queue_round(conn, alert["id"], next_round, now)
                    else:
                        conn.execute("UPDATE alerts SET status = ? WHERE id = ?", (STATUS_UNACKED, alert["id"]))

            due = conn.execute(
                "SELECT d.*, a.kind, a.details, a.source, a.detected_at, a.ack_token FROM deliveries d "
                "JOIN alerts a ON a.id = d.alert_id "
                "WHERE d.status IN ('pending', 'failed') AND d.next_try_at <= ? AND a.status != ?",
                (now, STATUS_ACKED),
            ).fetchall()

        # Gửi NGOÀI transaction: gọi mạng có thể chậm vài giây.
        for d in due:
            channel = self.channels.get(d["channel"])
            attempts = d["attempts"] + 1
            try:
                if channel is None:
                    raise RuntimeError(f"Kênh {d['channel']} không còn được cấu hình")
                channel.send(d["target"], d, self.ack_url(d))
                update = ("sent", now, None, now)
            except Exception as exc:  # noqa: BLE001 — mọi lỗi gửi đều phải được thử lại
                backoff = RETRY_BACKOFF_SECONDS[min(attempts - 1, len(RETRY_BACKOFF_SECONDS) - 1)]
                update = ("failed", None, str(exc)[:300], now + backoff)
            with _conn() as conn:
                conn.execute(
                    "UPDATE deliveries SET status = ?, sent_at = ?, error = ?, next_try_at = ?, attempts = ?, "
                    "last_attempt_at = ? WHERE id = ?",
                    (*update, attempts, now, d["id"]),
                )

    def poll_channels(self):
        for ch in self.channels.values():
            poll = getattr(ch, "poll", None)
            if poll is not None:
                poll(lambda token, by, via: ack(token, by=by, via=via, now=self.clock()))

    def _loop(self):
        while not self._stop.is_set():
            for step in (self.tick, self.poll_channels):
                try:
                    step()
                    self.last_error = None
                except Exception as exc:  # noqa: BLE001 — thread nền không được chết vì 1 lỗi mạng
                    self.last_error = f"{type(exc).__name__}: {exc}"
            self._stop.wait(DISPATCH_INTERVAL_SECONDS)

    def start(self):
        if self._thread is None or not self._thread.is_alive():
            self._stop.clear()
            self._thread = threading.Thread(target=self._loop, name="safewatch-notifier", daemon=True)
            self._thread.start()

    def stop(self):
        self._stop.set()


# ---------------------------------------------------------------------- Kênh


class TelegramChannel:
    """Gửi qua Telegram Bot API (miễn phí). Tin nhắn có nút "Tôi đã nhận";
    bấm nút -> callback về bot -> poll() ghi xác nhận. Người chăm sóc nhắn
    /start cho bot để biết Chat ID của mình."""

    name = "telegram"

    def __init__(self, token, timeout=10):
        self.token = token
        self.timeout = timeout
        self.offset = None

    def target_for(self, contact):
        return contact.get("telegram_chat_id") or None

    def _api(self, method, params):
        data = urllib.parse.urlencode({k: v for k, v in params.items() if v is not None}).encode()
        request = urllib.request.Request(f"https://api.telegram.org/bot{self.token}/{method}", data=data)
        try:
            with urllib.request.urlopen(request, timeout=self.timeout) as response:
                body = json.load(response)
        except urllib.error.HTTPError as exc:
            body = json.load(exc)
        if not body.get("ok"):
            raise RuntimeError(f"Telegram {method}: {body.get('description', 'lỗi không rõ')}")
        return body["result"]

    def send(self, target, alert, ack_url=None):
        markup = {"inline_keyboard": [[{"text": "✅ Tôi đã nhận", "callback_data": f"ack:{alert['ack_token']}"}]]}
        self._api("sendMessage", {"chat_id": target, "text": format_message(alert), "reply_markup": json.dumps(markup)})

    def poll(self, ack_fn):
        updates = self._api(
            "getUpdates",
            {"offset": self.offset, "timeout": 0, "allowed_updates": json.dumps(["message", "callback_query"])},
        )
        for update in updates:
            self.offset = update["update_id"] + 1
            callback = update.get("callback_query")
            if callback and callback.get("data", "").startswith("ack:"):
                who = callback.get("from", {}).get("first_name", "")
                first = ack_fn(callback["data"][4:], who, "telegram")
                self._api(
                    "answerCallbackQuery",
                    {
                        "callback_query_id": callback["id"],
                        "text": "Đã ghi nhận xác nhận. Cảm ơn bạn!" if first else "Cảnh báo này đã được xác nhận trước đó.",
                    },
                )
            message = update.get("message")
            if message and message.get("text", "").startswith("/start"):
                chat_id = message["chat"]["id"]
                self._api(
                    "sendMessage",
                    {"chat_id": chat_id, "text": f"SafeWatch: Chat ID của bạn là {chat_id}. "
                                                 "Nhập số này vào mục Người liên hệ khẩn cấp để nhận cảnh báo."},
                )


class EmailChannel:
    """Gửi qua SMTP (VD Gmail: smtp.gmail.com:465 + App Password). Email không
    tự xác nhận được là đã đọc — xác nhận qua link trong email (cần
    PUBLIC_BASE_URL trỏ tới app)."""

    name = "email"

    def __init__(self, host, port, user, password, sender=None, timeout=15):
        self.host, self.port, self.user, self.password = host, int(port), user, password
        self.sender = sender or user
        self.timeout = timeout

    def target_for(self, contact):
        return contact.get("email") or None

    def send(self, target, alert, ack_url=None):
        msg = EmailMessage()
        msg["Subject"] = f"[SafeWatch] {alert['kind']}"
        msg["From"] = self.sender
        msg["To"] = target
        msg.set_content(format_message(alert, ack_url))
        context = ssl.create_default_context()
        if self.port == 465:
            with smtplib.SMTP_SSL(self.host, self.port, timeout=self.timeout, context=context) as smtp:
                smtp.login(self.user, self.password)
                smtp.send_message(msg)
        else:
            with smtplib.SMTP(self.host, self.port, timeout=self.timeout) as smtp:
                smtp.starttls(context=context)
                smtp.login(self.user, self.password)
                smtp.send_message(msg)


# ------------------------------------------------------------------ Cấu hình

CONFIG_KEYS = ["TELEGRAM_BOT_TOKEN", "SMTP_HOST", "SMTP_PORT", "SMTP_USER", "SMTP_PASSWORD", "SMTP_FROM",
               "PUBLIC_BASE_URL"]


def load_config(secrets_mapping=None):
    """Đọc từ st.secrets (truyền vào) rồi tới biến môi trường. Thiếu file
    secrets.toml không được làm crash app."""
    config = {}
    for key in CONFIG_KEYS:
        value = None
        if secrets_mapping is not None:
            try:
                value = secrets_mapping.get(key)
            except Exception:  # noqa: BLE001 — StreamlitSecretNotFoundError khi không có secrets.toml
                value = None
        config[key] = value or os.environ.get(key)
    return config


def build_channels(config):
    channels = []
    if config.get("TELEGRAM_BOT_TOKEN"):
        channels.append(TelegramChannel(config["TELEGRAM_BOT_TOKEN"]))
    if config.get("SMTP_HOST") and config.get("SMTP_USER") and config.get("SMTP_PASSWORD"):
        channels.append(
            EmailChannel(config["SMTP_HOST"], config.get("SMTP_PORT") or 465, config["SMTP_USER"],
                         config["SMTP_PASSWORD"], config.get("SMTP_FROM"))
        )
    return channels

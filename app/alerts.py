"""
Alert dispatch: Telegram + email, with a per-metric cooldown so a metric
stuck above threshold doesn't spam the channel every collection cycle.
"""
import time
import threading
import smtplib
from email.mime.text import MIMEText
import requests
from . import config, database

_last_alert_time = {}  # metric -> unix ts


def _cooldown_ok(metric: str) -> bool:
    last = _last_alert_time.get(metric, 0)
    return (time.time() - last) >= config.ALERT_COOLDOWN_SECONDS


def _mark_alerted(metric: str):
    _last_alert_time[metric] = time.time()


def reset_cooldown(metrics):
    """
    Clears the cooldown timer for the given metric names, so the next
    evaluation can alert immediately even if that metric alerted recently.
    Used when the user manually saves new thresholds from the dashboard —
    if the new threshold is already breached, they should see/get the
    alert right away, not have it silently swallowed by the cooldown.
    """
    for metric in metrics:
        _last_alert_time.pop(metric, None)


def _send_telegram_blocking(message: str):
    if not (config.TELEGRAM_ENABLED and config.TELEGRAM_BOT_TOKEN):
        return
    url = f"https://api.telegram.org/bot{config.TELEGRAM_BOT_TOKEN}/sendMessage"

    # Broadcast to everyone who has ever messaged the bot (auto-discovered
    # via telegram_poller.py), plus any manually configured chat IDs in
    # .env (comma-separated), so both approaches work together.
    chat_ids = set(database.get_telegram_subscribers())
    if config.TELEGRAM_CHAT_ID:
        chat_ids.update(c.strip() for c in config.TELEGRAM_CHAT_ID.split(",") if c.strip())

    for chat_id in chat_ids:
        try:
            requests.post(url, data={"chat_id": chat_id, "text": message}, timeout=5)
        except requests.RequestException as e:
            print(f"[alerts] Telegram send failed for chat_id {chat_id}: {e}")


def send_telegram(message: str):
    """
    Fire-and-forget: runs the actual network calls on a background thread
    so alert dispatch never blocks the main metrics collection / dashboard
    broadcast loop. Without this, sending to N Telegram subscribers would
    pause live dashboard updates for however long those N network calls
    took to complete.
    """
    threading.Thread(target=_send_telegram_blocking, args=(message,), daemon=True).start()


def _send_email_blocking(subject: str, body: str):
    if not (config.EMAIL_ENABLED and config.SMTP_USER and config.SMTP_PASSWORD and config.ALERT_EMAIL_TO):
        return
    try:
        msg = MIMEText(body)
        msg["Subject"] = subject
        msg["From"] = config.SMTP_USER
        msg["To"] = config.ALERT_EMAIL_TO
        with smtplib.SMTP(config.SMTP_HOST, config.SMTP_PORT) as server:
            server.starttls()
            server.login(config.SMTP_USER, config.SMTP_PASSWORD)
            server.send_message(msg)
    except Exception as e:
        print(f"[alerts] Email send failed: {e}")


def send_email(subject: str, body: str):
    """Fire-and-forget, same reasoning as send_telegram above — SMTP is slow."""
    threading.Thread(target=_send_email_blocking, args=(subject, body), daemon=True).start()


METRIC_LABELS = {
    "cpu_percent": ("CPU usage", "%"),
    "ram_percent": ("RAM usage", "%"),
    "disk_percent": ("Disk usage", "%"),
    "temp_celsius": ("Temperature", "°C"),
}


def evaluate_and_dispatch(sample: dict, thresholds: dict, broadcast_fn=None):
    """
    Compares the latest sample against current thresholds. Fires
    Telegram/email/on-screen alerts (via broadcast_fn, which pushes
    to connected WebSocket dashboard clients) for anything breached,
    respecting the per-metric cooldown.
    """
    triggered = []
    for metric, (label, unit) in METRIC_LABELS.items():
        value = sample.get(metric)
        threshold = thresholds.get(metric)
        if value is None or threshold is None:
            continue
        if value >= threshold and _cooldown_ok(metric):
            message = (
                f"⚠️ {config.DEVICE_NAME}: {label} is {value}{unit}, "
                f"above threshold of {threshold}{unit}"
            )
            send_telegram(message)
            send_email(f"[Seaker Alert] {label} threshold exceeded", message)
            database.log_alert(metric, value, threshold, message)
            _mark_alerted(metric)
            triggered.append({"metric": metric, "label": label, "value": value,
                               "threshold": threshold, "message": message})

    if triggered and broadcast_fn:
        broadcast_fn({"type": "alert", "alerts": triggered})

    return triggered
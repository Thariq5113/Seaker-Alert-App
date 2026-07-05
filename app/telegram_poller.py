"""
Polls Telegram's getUpdates API periodically to discover anyone who has
messaged the bot (e.g. sent /start), and registers their chat_id as a
subscriber. This means any user who finds and starts the bot link
automatically receives future alerts — no manual chat_id configuration
needed per person.

Telegram's getUpdates is a "long poll" style API: each call returns any
new messages since the last seen update_id, then that update_id + 1 is
used as the 'offset' for the next call so the same messages aren't
re-processed. The offset is persisted in the database so a restart
doesn't cause duplicate processing (and Telegram forgets old updates
once they've been acknowledged with a higher offset anyway).
"""
import requests
from . import config, database


def poll_once():
    if not (config.TELEGRAM_ENABLED and config.TELEGRAM_BOT_TOKEN):
        return

    offset = database.get_telegram_offset()
    url = f"https://api.telegram.org/bot{config.TELEGRAM_BOT_TOKEN}/getUpdates"
    try:
        resp = requests.get(url, params={"offset": offset, "timeout": 5}, timeout=10)
        resp.raise_for_status()
        data = resp.json()
    except (requests.RequestException, ValueError) as e:
        print(f"[telegram_poller] getUpdates failed: {e}")
        return

    if not data.get("ok"):
        return

    highest_update_id = offset - 1
    for update in data.get("result", []):
        update_id = update.get("update_id", 0)
        highest_update_id = max(highest_update_id, update_id)

        message = update.get("message") or update.get("edited_message")
        if not message:
            continue
        chat = message.get("chat", {})
        chat_id = chat.get("id")
        if chat_id is not None:
            database.add_telegram_subscriber(chat_id)

    if highest_update_id >= offset:
        database.set_telegram_offset(highest_update_id + 1)
import asyncio
import time
from datetime import datetime
import json
import os
import sys
import logging
from aiogram import Bot
from engine import get_config
from aiogram.exceptions import TelegramBadRequest

STORE_FILE = "status_msg.json"
bot_start_time = time.time()
try:
    main_file = os.path.join(os.path.dirname(__file__), "main.py")
    mtime = os.path.getmtime(main_file)
    last_update_str = datetime.fromtimestamp(mtime).strftime("%Y-%m-%d %H:%M:%S")
except Exception:
    last_update_str = "Неизвестно"


def get_msg_id():
    if os.path.exists(STORE_FILE):
        try:
            with open(STORE_FILE, "r") as f:
                return json.load(f).get("msg_id")
        except Exception:
            pass
    return None

def save_msg_id(msg_id):
    with open(STORE_FILE, "w") as f:
        json.dump({"msg_id": msg_id}, f)

async def update_status_message(bot: Bot, is_offline=False):
    cfg = get_config()
    chat_id = cfg.game_settings.public_chat_id
    thread_id = cfg.game_settings.public_chat_thread_id
    
    if not chat_id:
        return

    # Calculate uptime
    uptime_seconds = int(time.time() - bot_start_time)
    days = uptime_seconds // 86400
    hours = (uptime_seconds % 86400) // 3600
    minutes = (uptime_seconds % 3600) // 60
    seconds = uptime_seconds % 60
    
    if days > 0:
        uptime_str = f"{days}д {hours}ч {minutes}м"
    else:
        uptime_str = f"{hours}ч {minutes}м {seconds}с"

    # Calculate ping
    t1 = time.time()
    try:
        await bot.get_me()
    except Exception:
        pass
    ping_ms = int((time.time() - t1) * 1000)

    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    if is_offline:
        status_text = "🔴 Выключен"
    else:
        status_text = "🟢 В сети"

    text = (
        f"🤖 <b>Статус бота:</b> {status_text}\n"
        f"⏱ <b>Время работы:</b> {uptime_str}\n"
        f"📡 <b>Пинг API:</b> {ping_ms} мс\n"
        f"🛠 <b>Версия от:</b> {last_update_str}\n"
        f"🔄 <b>Синхронизация:</b> {now}"
    )

    msg_id = get_msg_id()
    if msg_id:
        try:
            await bot.edit_message_text(
                text=text,
                chat_id=chat_id,
                message_id=msg_id,
                parse_mode="HTML"
            )
            return
        except TelegramBadRequest as e:
            err = str(e).lower()
            if "not found" in err or "can't be edited" in err:
                msg_id = None # Need to resend
            elif "not modified" in err:
                return
            else:
                logging.error(f"Status update TelegramBadRequest: {e}")
                return
        except Exception as e:
            logging.error(f"Status update error: {e}")
            return
    
    if not msg_id:
        try:
            msg = await bot.send_message(
                chat_id=chat_id,
                message_thread_id=thread_id,
                text=text,
                parse_mode="HTML"
            )
            save_msg_id(msg.message_id)
        except Exception as e:
            logging.error(f"Failed to send status message: {e}")

async def status_updater_loop(bot: Bot):
    while True:
        await update_status_message(bot)
        await asyncio.sleep(30)

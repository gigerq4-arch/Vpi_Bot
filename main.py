import asyncio
import logging
import sys
import os
import time
import json
from datetime import datetime

# Ensure the current directory is in the python path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from aiogram import Bot, Dispatcher
from aiogram.fsm.storage.memory import MemoryStorage
from dotenv import load_dotenv

# Import local modules
from database import init_db
from engine import load_config

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')

# Load environment variables
load_dotenv()

# Insert your bot token here
BOT_TOKEN = os.getenv("BOT_TOKEN")

if not BOT_TOKEN:
    logging.error("BOT_TOKEN environment variable not set. Please set it in .env file.")
    sys.exit(1)



import os
STATUS_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "status_msg.json")
START_TIME = time.time()

CHANGELOG_TEXT = (
    "**Последние обновления и изменения:**\n"
    "• Переработана команда `/rate` (показывает производительность за 1 завод).\n"
    "• Новая техника: Огнеметы, Грузовые автомобили, Гаубицы, Самозарядные винтовки и др.\n"
    "• Новая категория «Снаряжение» (Гранаты, Штыки, Каски, Саперные лопатки).\n"
    "• Команда `/remove_equip` для изъятия техники администратором.\n"
    "• Команда `/reform` для проведения реформ (выделение средств из казны)."
)

def get_status_data():
    import os
    if os.path.exists(STATUS_FILE):
        try:
            with open(STATUS_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except:
            return {}
    return {}

def save_status_data(data):
    with open(STATUS_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f)

updater_task = None

async def status_updater(bot: Bot):
    while True:
        try:
            await asyncio.sleep(60)
            from engine import get_config
            cfg = get_config()
            public_chat = cfg.game_settings.public_chat_id
            public_thread = cfg.game_settings.public_chat_thread_id
            if public_thread == 0:
                public_thread = None
                
            if not public_chat or public_chat == -1000000000000:
                continue

            start_ping = time.perf_counter()
            await bot.get_me()
            ping_ms = (time.perf_counter() - start_ping) * 1000

            uptime_seconds = int(time.time() - START_TIME)
            uptime_str = f"{uptime_seconds // 3600}ч {(uptime_seconds % 3600) // 60}м {uptime_seconds % 60}с"
            current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

            text = (
                "🟢 **Статус бота: АКТИВЕН**\n\n"
                f"⏱ Аптайм: `{uptime_str}`\n"
                f"🏓 Пинг API: `{ping_ms:.0f} мс`\n"
                f"🔄 Последнее обновление: `{current_time}`\n\n"
                f"{CHANGELOG_TEXT}\n\n"
                "💡 *Сообщение обновляется автоматически каждые 60с.*"
            )

            status_data = get_status_data()
            msg_id = status_data.get("message_id")

            if msg_id:
                try:
                    await bot.edit_message_text(text, chat_id=public_chat, message_id=msg_id, parse_mode="Markdown")
                except Exception as e:
                    if "message is not modified" in str(e).lower():
                        pass
                    else:
                        try:
                            msg = await bot.send_message(public_chat, text, parse_mode="Markdown", message_thread_id=public_thread)
                            save_status_data({"message_id": msg.message_id})
                        except Exception as inner_e:
                            logging.error(f"Failed to send new status message: {inner_e}")
            else:
                try:
                    msg = await bot.send_message(public_chat, text, parse_mode="Markdown", message_thread_id=public_thread)
                    save_status_data({"message_id": msg.message_id})
                except Exception as e:
                    logging.error(f"Failed to send initial status message: {e}")

        except asyncio.CancelledError:
            break
        except Exception as e:
            logging.error(f"Error in status_updater: {e}")

async def on_startup(bot: Bot):
    global updater_task
    from engine import get_config
    cfg = get_config()
    public_chat = cfg.game_settings.public_chat_id
    public_thread = cfg.game_settings.public_chat_thread_id
    if public_thread == 0:
        public_thread = None
        
    if public_chat and public_chat != -1000000000000:
        start_ping = time.perf_counter()
        await bot.get_me()
        ping_ms = (time.perf_counter() - start_ping) * 1000

        uptime_seconds = int(time.time() - START_TIME)
        uptime_str = f"{uptime_seconds // 3600}ч {(uptime_seconds % 3600) // 60}м {uptime_seconds % 60}с"
        current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        text = (
            "🟢 **Статус бота: АКТИВЕН (Запущен)**\n\n"
            f"⏱ Аптайм: `{uptime_str}`\n"
            f"🏓 Пинг API: `{ping_ms:.0f} мс`\n"
            f"🔄 Последнее обновление: `{current_time}`\n\n"
            f"{CHANGELOG_TEXT}\n\n"
            "💡 *Сообщение обновляется автоматически каждые 60с.*"
        )
        
        status_data = get_status_data()
        msg_id = status_data.get("message_id")
        
        if msg_id:
            try:
                await bot.edit_message_text(text, chat_id=public_chat, message_id=msg_id, parse_mode="Markdown")
            except Exception as e:
                try:
                    msg = await bot.send_message(public_chat, text, parse_mode="Markdown", message_thread_id=public_thread)
                    save_status_data({"message_id": msg.message_id})
                except Exception as inner_e:
                    logging.error(f"Failed to send new status message: {inner_e}")
        else:
            try:
                msg = await bot.send_message(public_chat, text, parse_mode="Markdown", message_thread_id=public_thread)
                save_status_data({"message_id": msg.message_id})
            except Exception as e:
                logging.error(f"Failed to send initial status message: {e}")
                
    updater_task = asyncio.create_task(status_updater(bot))

async def on_shutdown(bot: Bot):
    global updater_task
    if updater_task:
        updater_task.cancel()
        
    from engine import get_config
    cfg = get_config()
    public_chat = cfg.game_settings.public_chat_id
    
    if public_chat and public_chat != -1000000000000:
        status_data = get_status_data()
        msg_id = status_data.get("message_id")
        if msg_id:
            current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            text = (
                "🔴 **Статус бота: ВЫКЛЮЧЕН**\n\n"
                f"🔄 Последнее обновление: `{current_time}`\n\n"
                "Возможно, проводится обновление кода или техническое обслуживание."
            )
            try:
                await bot.edit_message_text(text, chat_id=public_chat, message_id=msg_id, parse_mode="Markdown")
            except Exception as e:
                logging.error(f"Failed to edit shutdown message: {e}")

async def main():
    # Load game config from config.json using Pydantic
    load_config("config.json")
    logging.info("Configuration loaded successfully.")

    # Initialize Database (SQLite for local testing by default)
    await init_db()
    logging.info("Database initialized.")

    # Initialize bot and dispatcher
    bot = Bot(token=BOT_TOKEN)
    # Note: Use RedisStorage in production as per architecture guidelines
    dp = Dispatcher(storage=MemoryStorage()) 

    # Register routers
    from handlers import router
    from trade import router as trade_router
    from nuclear_cmds import router as nuclear_router
    
    dp.include_router(router)
    dp.include_router(trade_router)
    dp.include_router(nuclear_router)
    dp.startup.register(on_startup)
    dp.shutdown.register(on_shutdown)

    logging.info("Starting bot polling...")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())

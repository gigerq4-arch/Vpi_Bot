import asyncio
import logging
import sys
import os

# Ensure the current directory is in the python path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from aiogram import Bot, Dispatcher
from aiogram.fsm.storage.memory import MemoryStorage

# Import local modules
from database import init_db
from engine import load_config
from status_task import status_updater_loop, update_status_message

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')

from dotenv import load_dotenv
load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")
if not BOT_TOKEN:
    logging.error("BOT_TOKEN is missing in environment variables.")
    sys.exit(1)

import socket
import aiohttp

# Force IPv4 in aiohttp to fix Telegram API timeouts in some environments
original_init = aiohttp.TCPConnector.__init__
def new_init(self, *args, **kwargs):
    kwargs['family'] = socket.AF_INET
    original_init(self, *args, **kwargs)
aiohttp.TCPConnector.__init__ = new_init

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
    
    from middlewares import ApprovalMiddleware
    dp.message.middleware(ApprovalMiddleware())
    dp.callback_query.middleware(ApprovalMiddleware())

    # Register routers
    from handlers import router
    from trade import router as trade_router
    from nuclear_cmds import router as nuclear_router
    
    dp.include_router(router)
    dp.include_router(trade_router)
    dp.include_router(nuclear_router)

    # Start status background task
    status_task = asyncio.create_task(status_updater_loop(bot))
    
    # Register shutdown hook to set offline status
    async def on_shutdown(dispatcher: Dispatcher):
        logging.info("Shutting down... updating status message.")
        await update_status_message(bot, is_offline=True)

    dp.shutdown.register(on_shutdown)

    logging.info("Starting bot polling...")
    try:
        await dp.start_polling(bot)
    finally:
        status_task.cancel()

if __name__ == "__main__":
    asyncio.run(main())

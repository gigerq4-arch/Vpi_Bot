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

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')


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
    from generator import router as gen_router
    
    dp.include_router(router)
    dp.include_router(trade_router)
    dp.include_router(gen_router)

    logging.info("Starting bot polling...")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())

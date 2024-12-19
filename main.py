import asyncio
import logging
from aiogram import Bot, Dispatcher
from aiogram.fsm.storage.memory import MemoryStorage
from tortoise import Tortoise

from app.handlers.user import router as user_router
from config import BOT_TOKEN, TORTOISE_ORM

async def init_db():
    await Tortoise.init(
        db_url=TORTOISE_ORM["connections"]["default"],
        modules={'models': ['app.models']}
    )
    
    await Tortoise.generate_schemas(safe=True)

async def close_db  ():
    await Tortoise.close_connections()

async def main():
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )

    bot = Bot(token=BOT_TOKEN)
    dp = Dispatcher(storage=MemoryStorage())

    # Include only the user router as it contains all handlers
    dp.include_router(user_router)

    await init_db()
    try:
        await dp.start_polling(bot)
    except Exception as e:
        logging.error(f"Error in main: {e}")
    finally:
        await close_db()

if __name__ == '__main__':
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("Bot to'xtatildi!")
    finally:
        asyncio.run(close_db())
import asyncio
from handlers import user_commands
from config import bot, dp
import logging

logging.basicConfig(level=logging.INFO)
dp.include_router(user_commands.router)

async def main():
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
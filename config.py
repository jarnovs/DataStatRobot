from aiogram import Bot, Dispatcher

TOKEN = "1234"

bot = Bot(token=TOKEN)
dp = Dispatcher()  # In aiogram 3.x, Dispatcher is instantiated without bot

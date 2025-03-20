from aiogram import Bot, Dispatcher

TOKEN = "7619172313:AAErRDJFJW8eoMU9GV1qZaEKP6qpAkt_iSY"

bot = Bot(token=TOKEN)
dp = Dispatcher()  # In aiogram 3.x, Dispatcher is instantiated without bot

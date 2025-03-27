import os
import pandas as pd

from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import StatesGroup, State
from aiogram.fsm.storage.memory import MemoryStorage
from dotenv import load_dotenv

from app.database import get_session
from app.models import ExcelData
from app.parser import parse_prices
import logging


logging.basicConfig(level=logging.INFO)

load_dotenv()
TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")

bot = Bot(token=TOKEN)
dp = Dispatcher(storage=MemoryStorage())

class UploadFileState(StatesGroup):
    waiting_for_file = State()

@dp.message(Command("start"))
async def start(message: types.Message):
    await message.answer("Привет! Используй /upload если хочешь загрузить файл")

@dp.message(Command("upload"))
async def request_file(message: types.Message, state: FSMContext):
    await message.answer("Пришли файл в формате .xlsx")
    await state.set_state(UploadFileState.waiting_for_file)

@dp.message(UploadFileState.waiting_for_file)
async def handle_file(message: types.Message, state: FSMContext):
    if not os.path.exists("data"):
        os.makedirs("data")

    if not message.document:
        await message.answer("Пожалуйста, отправь файл в формате .xlsx")
        return

    file_id = message.document.file_id
    file_info = await bot.get_file(file_id)
    file_path = f"data/{message.document.file_name}"

    await bot.download_file(file_info.file_path, file_path)

    df = pd.read_excel(file_path)
    if not all(col in df.columns for col in ["title", "url", "xpath"]):
        await message.answer("Ошибка! В файле должны быть колонки: title, url и xpath")
        return

    async with get_session() as session:
        for _, row in df.iterrows():
            data = ExcelData(title=row["title"], url=row["url"], xpath=row["xpath"])
            session.add(data)
        await session.commit()
        await session.close()

    await message.answer(f"Файл загружен! Содержимое:\n{df.to_string()}")
    os.remove(file_path)
    await state.clear()

@dp.message(Command("parse"))
async def start_parsing(message: types.Message):
    async with get_session() as session:
        await message.answer("Запускаю парсинг цен, ожидайте...")

        avg_prices = await parse_prices()

        if not avg_prices:
            await message.answer("Не удалось получить данные о ценах")
            return

        result_text = "\n".join([f"{url}:{price:.2f}" for url, price in avg_prices.items()])
        await message.answer(f"Средние цены:\n{result_text}")
        session.close()


async def main():
    await dp.start_polling(bot)

if __name__ == "__main__":
    import asyncio
    asyncio.run(main())
import os
import asyncio
import pandas as pd
import matplotlib.pyplot as plt

import logging
from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command
from aiogram.types import FSInputFile
from aiogram.enums import ParseMode
from aiogram.utils.markdown import hbold

TOKEN = "7619172313:AAEm-5Y-gdWpCsX5B_UDNEduQ5y060rAe_I"

logging.basicConfig(level=logging.INFO)
bot = Bot(token=TOKEN)
dp = Dispatcher()

# Словарь для хранения DataFrame каждого пользователя
dataframes = {}

@dp.message(Command("start"))
async def start(message: types.Message):
    text = (
        "Привет! Отправьте мне CSV или Excel-файл, и я его проанализирую 📊\n\n"
        "После загрузки файла доступны команды:\n"
        "• /plot_hist – построить гистограмму\n"
        "• /plot_box – построить boxplot (ящик с усами)\n"
        "• /plot_corr – построить матрицу корреляции\n"
        "• /plot_line <колонка> – построить линейный график по указанной колонке\n"
        "• /fillna <значение> – заменить пустые значения (например, '/fillna median' или '/fillna 0')\n"
        "• /show_data – показать первые 5 строк\n"
        "• /duplicated – посмотреть/удалить дубликаты\n"
        "• /outliers – посмотреть/удалить выбросы\n"
        "• /finish – отправить обратно обработанный файл\n"
        "• /reset – сбросить сохранённые данные\n\n"
        "Сначала загрузите файл, а потом используйте эти команды!"
    )
    await message.answer(text)

@dp.message(lambda message: message.document and message.document.mime_type in [
    "text/csv",
    "application/vnd.ms-excel",
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
])
async def handle_file(message: types.Message):
    file_id = message.document.file_id
    file_name = message.document.file_name
    file_path = f"./{file_name}"

    file = await bot.get_file(file_id)
    await bot.download_file(file.file_path, destination=file_path)

    try:
        if file_name.endswith('.csv'):
            df = pd.read_csv(file_path)
        elif file_name.endswith(('.xls', '.xlsx')):
            df = pd.read_excel(file_path)
        else:
            await message.answer("Формат не поддерживается! Пришлите CSV или Excel-файл.")
            os.remove(file_path)
            return
    except Exception as e:
        await message.answer(f"Ошибка при обработке файла: {e}")
        os.remove(file_path)
        return

    dataframes[message.from_user.id] = df

    summary = df.describe().to_string() if not df.empty else "Нет данных"
    missing_values = df.isnull().sum().to_string()

    response = f"📊 {hbold('Анализ файла')}:\n\n"
    response += f"✅ Колонки: {', '.join(df.columns)}\n"
    response += f"📏 Размер данных: {df.shape[0]} строк, {df.shape[1]} колонок\n\n"
    response += f"📈 {hbold('Основные статистики')}:\n<pre>{summary}</pre>\n\n"
    response += f"🔍 {hbold('Пропущенные значения')}:\n<pre>{missing_values}</pre>"

    await message.answer(response, parse_mode=ParseMode.HTML)

    if not df.empty:
        fig, ax = plt.subplots(figsize=(6, 4))
        df.hist(ax=ax)
        plt.tight_layout()
        plot_path = f"hist_{message.from_user.id}.png"
        plt.savefig(plot_path)
        plt.close(fig)

        await message.answer_photo(photo=FSInputFile(plot_path))
        os.remove(plot_path)

    os.remove(file_path)

# Пример команды /plot_hist
@dp.message(Command("plot_hist"))
async def plot_hist(message: types.Message):
    user_id = message.from_user.id
    if user_id not in dataframes:
        await message.answer("Сначала загрузите файл!")
        return

    df = dataframes[user_id]
    if df.empty:
        await message.answer("Данные пустые!")
        return

    fig, ax = plt.subplots(figsize=(6, 4))
    df.hist(ax=ax)
    plt.tight_layout()
    plot_path = f"hist_{user_id}.png"
    plt.savefig(plot_path)
    plt.close(fig)

    await message.answer_photo(photo=FSInputFile(plot_path))
    os.remove(plot_path)

#
# 2) /plot_box — строит boxplot (ящик с усами) для всех числовых колонок
#
@dp.message(Command("plot_box"))
async def plot_box(message: types.Message):
    user_id = message.from_user.id
    if user_id not in dataframes:
        await message.answer("Сначала загрузите файл!")
        return

    df = dataframes[user_id]
    if df.empty:
        await message.answer("Данные пустые!")
        return

    fig, ax = plt.subplots(figsize=(6, 4))
    df.plot.box(ax=ax)
    plt.tight_layout()
    plot_path = f"box_{user_id}.png"
    plt.savefig(plot_path)
    plt.close(fig)

    await message.answer_photo(photo=FSInputFile(plot_path))
    os.remove(plot_path)

#
# 3) /plot_corr — строит матрицу корреляции (heatmap)
#
@dp.message(Command("plot_corr"))
async def plot_corr(message: types.Message):
    user_id = message.from_user.id
    if user_id not in dataframes:
        await message.answer("Сначала загрузите файл!")
        return

    df = dataframes[user_id]
    if df.empty:
        await message.answer("Данные пустые!")
        return

    corr = df.corr(numeric_only=True)  # numeric_only=True для новых версий pandas

    fig, ax = plt.subplots(figsize=(6, 4))
    cax = ax.matshow(corr, cmap='viridis')
    fig.colorbar(cax)
    ax.set_xticks(range(len(corr.columns)))
    ax.set_yticks(range(len(corr.index)))
    ax.set_xticklabels(corr.columns, rotation=90)
    ax.set_yticklabels(corr.index)
    plt.tight_layout()
    plot_path = f"corr_{user_id}.png"
    plt.savefig(plot_path)
    plt.close(fig)

    await message.answer_photo(photo=FSInputFile(plot_path))
    os.remove(plot_path)

#
# 4) /plot_line <колонка> — строит линейный график по указанной колонке
#
@dp.message(Command("plot_line"))
async def plot_line(message: types.Message):
    user_id = message.from_user.id
    if user_id not in dataframes:
        await message.answer("Сначала загрузите файл!")
        return

    df = dataframes[user_id]
    if df.empty:
        await message.answer("Данные пустые!")
        return

    parts = message.text.split()
    if len(parts) < 2:
        await message.answer("Укажите колонку, например: /plot_line column_name")
        return

    column = parts[1]
    if column not in df.columns:
        await message.answer(f"Колонки '{column}' нет в данных.")
        return

    # Строим линейный график по выбранной колонке
    fig, ax = plt.subplots(figsize=(6, 4))
    ax.plot(df.index, df[column], marker='o', linestyle='-')
    ax.set_xlabel("Index")
    ax.set_ylabel(column)
    ax.set_title(f"Line Plot for '{column}'")
    plt.tight_layout()

    plot_path = f"line_{user_id}.png"
    plt.savefig(plot_path)
    plt.close(fig)

    await message.answer_photo(photo=FSInputFile(plot_path))
    os.remove(plot_path)

#
# 5) /fillna <значение> — замена пустых значений
#
@dp.message(Command("fillna"))
async def fillna_cmd(message: types.Message):
    user_id = message.from_user.id
    if user_id not in dataframes:
        await message.answer("Сначала загрузите файл!")
        return

    parts = message.text.split(maxsplit=1)
    if len(parts) < 2:
        await message.answer("Укажите значение для замены пустых значений, например '/fillna median' или '/fillna 0'")
        return

    fill_value = parts[1].strip()
    df = dataframes[user_id]

    if fill_value.lower() == "median":
        numeric_cols = df.select_dtypes(include='number').columns
        if numeric_cols.empty:
            await message.answer("Нет числовых колонок для заполнения медианой.")
        else:
            for col in numeric_cols:
                df[col].fillna(df[col].median(), inplace=True)
            await message.answer("Пустые значения в числовых колонках заменены на медиану.")
    else:
        # Пытаемся привести fill_value к числу, если не получается — останется строкой
        try:
            fill_value_converted = float(fill_value)
            df.fillna(fill_value_converted, inplace=True)
            await message.answer(f"Пустые значения заменены на числовое значение {fill_value_converted}.")
        except ValueError:
            df.fillna(fill_value, inplace=True)
            await message.answer(f"Пустые значения заменены на строку '{fill_value}'.")

    # Обновляем сохранённые данные
    dataframes[user_id] = df

#
# 6) /show_data – выводит первые 5 строк файла
#
@dp.message(Command("show_data"))
async def show_data(message: types.Message):
    user_id = message.from_user.id
    if user_id not in dataframes:
        await message.answer("Сначала загрузите файл!")
        return

    df = dataframes[user_id]
    if df.empty:
        await message.answer("Данные пустые!")
        return

    await message.answer(f"Первые 5 строк:\n<pre>{df.head().to_string()}</pre>")

#
# 7) /duplicated – показать и/или удалить дубликаты
#
@dp.message(Command("duplicated"))
async def duplicated_cmd(message: types.Message):
    user_id = message.from_user.id
    if user_id not in dataframes:
        await message.answer("Сначала загрузите файл!")
        return

    df = dataframes[user_id]
    if df.empty:
        await message.answer("Данные пустые!")
        return

    # Считаем количество дубликатов
    dup_count = df.duplicated().sum()
    if dup_count == 0:
        await message.answer("Дубликаты не обнаружены.")
        return

    text = (
        f"Обнаружено {dup_count} дубликатов.\n\n"
        "Если хотите их удалить, введите команду: /duplicated remove"
    )
    parts = message.text.split()
    if len(parts) > 1 and parts[1].lower() == "remove":
        df.drop_duplicates(inplace=True)
        dataframes[user_id] = df
        text = f"Удалено {dup_count} дубликатов. Текущий размер данных: {df.shape[0]} строк."
    await message.answer(text)

#
# 8) /outliers – показать и/или удалить выбросы (простой IQR-метод)
#
@dp.message(Command("outliers"))
async def outliers_cmd(message: types.Message):
    user_id = message.from_user.id
    if user_id not in dataframes:
        await message.answer("Сначала загрузите файл!")
        return

    df = dataframes[user_id]
    if df.empty:
        await message.answer("Данные пустые!")
        return

    numeric_cols = df.select_dtypes(include='number').columns
    if numeric_cols.empty:
        await message.answer("Нет числовых колонок для поиска выбросов.")
        return

    # Считаем количество строк до удаления
    rows_before = df.shape[0]

    # Если пользователь ввёл "/outliers remove" – удаляем
    parts = message.text.split()
    remove_flag = (len(parts) > 1 and parts[1].lower() == "remove")

    outliers_count_total = 0
    if remove_flag:
        for col in numeric_cols:
            Q1 = df[col].quantile(0.25)
            Q3 = df[col].quantile(0.75)
            IQR = Q3 - Q1
            lower_bound = Q1 - 1.5 * IQR
            upper_bound = Q3 + 1.5 * IQR
            # Фильтруем данные, оставляя только "нормальные" значения
            df = df[(df[col] >= lower_bound) & (df[col] <= upper_bound)]
        dataframes[user_id] = df
        rows_after = df.shape[0]
        outliers_count_total = rows_before - rows_after
        await message.answer(f"Удалено выбросов (примерно): {outliers_count_total}. Текущий размер данных: {rows_after} строк.")
    else:
        # Просто считаем, сколько выбросов (по IQR) могло бы быть удалено
        temp_df = df.copy()
        for col in numeric_cols:
            Q1 = temp_df[col].quantile(0.25)
            Q3 = temp_df[col].quantile(0.75)
            IQR = Q3 - Q1
            lower_bound = Q1 - 1.5 * IQR
            upper_bound = Q3 + 1.5 * IQR
            temp_df = temp_df[(temp_df[col] >= lower_bound) & (temp_df[col] <= upper_bound)]
        rows_after = temp_df.shape[0]
        outliers_count_total = rows_before - rows_after
        await message.answer(
            f"По IQR-методу можно удалить около {outliers_count_total} выбросов.\n"
            "Чтобы удалить выбросы, введите команду: /outliers remove"
        )

#
# 9) /finish – выгрузка (отправка) текущего DataFrame обратно как CSV
#
@dp.message(Command("finish"))
async def finish_cmd(message: types.Message):
    user_id = message.from_user.id
    if user_id not in dataframes:
        await message.answer("Нет данных для выгрузки. Сначала загрузите файл.")
        return

    df = dataframes[user_id]
    if df.empty:
        await message.answer("Данные пустые! Возможно, все строки были удалены.")
        return

    output_file = f"processed_{user_id}.csv"
    df.to_csv(output_file, index=False)

    await message.answer_document(document=FSInputFile(output_file))
    os.remove(output_file)

#
# 10) /reset – сброс сохранённых данных
#
@dp.message(Command("reset"))
async def reset_cmd(message: types.Message):
    user_id = message.from_user.id
    if user_id in dataframes:
        del dataframes[user_id]
        await message.answer("Данные сброшены. Вы можете загрузить новый файл.")
    else:
        await message.answer("Нет сохранённых данных для сброса.")

#
# Запуск бота
#
async def main():
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
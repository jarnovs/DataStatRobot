import os
from xml.sax import parse

import asyncio
import logging

import pandas as pd
import matplotlib.pyplot as plt

from aiogram import Bot, Dispatcher, html
from aiogram import types, Router
from aiogram.filters import Command, StateFilter
from aiogram.types import FSInputFile, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.enums import ParseMode
from aiogram.utils.markdown import hbold


from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import StatesGroup, State
from aiogram.utils.keyboard import InlineKeyboardBuilder

from sqlalchemy import create_engine, inspect, text as sa_text

TOKEN = "7036922412:AAGqgJ8yG_Ime9hEWLN6VD22-Lc9hXmRZ8Y"

router = Router()
bot = Bot(token=TOKEN)
dp = Dispatcher()

# Словарь для хранения DataFrame каждого пользователя
dataframes = {}


# --- Helper for Postgres menu ---
def pg_menu_kb() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="📊 Info", callback_data="info")
    builder.button(text="❓ Missing", callback_data="missing")
    builder.button(text="🔁 Duplicates", callback_data="duplicates")
    builder.button(text="🔍 Search", callback_data="search")
    builder.adjust(2, 2)
    return builder.as_markup()


# --- States for Postgres flow ---
class PgStates(StatesGroup):
    connect = State()
    table_select = State()
    menu = State()
    search_col = State()
    search_input = State()


# --- /start handler with Postgres connect button ---
@router.message(Command("start"))
async def start(message: types.Message):
    text = (
        "Hi. Send me a CSV or Excel file and I will analyze it 📊\n\n"
        "After the file has been uploaded, use these commands:\n"
        "• /plot_hist – build histogram\n"
        "• /plot_box – build boxplot\n"
        "• /plot_corr – correlation matrix\n"
        "• /plot_line <column> – line plot\n"
        "• /fillna <value> – replace missing values\n"
        "• /show_data – show first 5 rows\n"
        "• /duplicated – view/delete duplicates\n"
        "• /outliers – view/delete outliers\n"
        "• /finish – download processed file\n"
        "• /reset – reset data\n\n"
        "Or connect to PostgreSQL by clicking the button below."
    )
    builder = InlineKeyboardBuilder()
    builder.button(text="Connect PostgreSQL", callback_data="pg_connect")
    builder.adjust(1)
    await message.answer(text, reply_markup=builder.as_markup())


@router.message(
    lambda message: message.document
    and message.document.mime_type
    in [
        "text/csv",
        "application/vnd.ms-excel",
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    ]
)
async def handle_file(message: types.Message):
    file_id = message.document.file_id
    file_name = message.document.file_name
    file_path = f"./{file_name}"

    file = await bot.get_file(file_id)
    await bot.download_file(file.file_path, destination=file_path)

    try:
        if file_name.endswith(".csv"):
            df = pd.read_csv(file_path)
        elif file_name.endswith((".xls", ".xlsx")):
            df = pd.read_excel(file_path)
        else:
            await message.answer("The format is not supported! Send CSV or Excel file.")
            os.remove(file_path)
            return
    except Exception as e:
        await message.answer(f"Error during file processing: {e}")
        os.remove(file_path)
        return

    dataframes[message.from_user.id] = df

    summary = df.describe().to_string() if not df.empty else "Нет данных"
    missing_values = df.isnull().sum().to_string()

    response = f"📊 {hbold('Analyzing the file')}:\n\n"
    response += f"✅ Сolumns: {', '.join(df.columns)}\n"
    response += f"📏 Data size: {df.shape[0]} rows, {df.shape[1]} columns\n\n"
    response += f"📈 {hbold('Basic statistics')}:\n<pre>{summary}</pre>\n\n"
    response += f"🔍 {hbold('Missing values')}:\n<pre>{missing_values}</pre>"

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
@router.message(Command("plot_hist"))
async def plot_hist(message: types.Message):
    user_id = message.from_user.id
    if user_id not in dataframes:
        await message.answer("First, download the file!")
        return

    df = dataframes[user_id]
    if df.empty:
        await message.answer("The data is empty!")
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
@router.message(Command("plot_box"))
async def plot_box(message: types.Message):
    user_id = message.from_user.id
    if user_id not in dataframes:
        await message.answer("First, download the file!")
        return

    df = dataframes[user_id]
    if df.empty:
        await message.answer("The data is empty!")
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
@router.message(Command("plot_corr"))
async def plot_corr(message: types.Message):
    user_id = message.from_user.id
    if user_id not in dataframes:
        await message.answer("First, download the file!")
        return

    df = dataframes[user_id]
    if df.empty:
        await message.answer("The data is empty!")
        return

    corr = df.corr(numeric_only=True)  # numeric_only=True для новых версий pandas

    fig, ax = plt.subplots(figsize=(6, 4))
    cax = ax.matshow(corr, cmap="viridis")
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
@router.message(Command("plot_line"))
async def plot_line(message: types.Message):
    user_id = message.from_user.id
    if user_id not in dataframes:
        await message.answer("First, download the file!")
        return

    df = dataframes[user_id]
    if df.empty:
        await message.answer("The data is empty!")
        return

    parts = message.text.split()
    if len(parts) < 2:
        await message.answer("Specify a column, e.g.: /plot_line column_name")
        return

    column = parts[1]
    if column not in df.columns:
        await message.answer(f"Columns '{column}' not in the data.")
        return

    # Строим линейный график по выбранной колонке
    fig, ax = plt.subplots(figsize=(6, 4))
    ax.plot(df.index, df[column], marker="o", linestyle="-")
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
@router.message(Command("fillna"))
async def fillna_cmd(message: types.Message):
    user_id = message.from_user.id
    if user_id not in dataframes:
        await message.answer("First, download the file!")
        return

    parts = message.text.split(maxsplit=1)
    if len(parts) < 2:
        await message.answer(
            "Specify a value to replace empty values, e.g. '/fillna median' or '/fillna 0'"
        )
        return

    fill_value = parts[1].strip()
    df = dataframes[user_id]

    if fill_value.lower() == "median":
        numeric_cols = df.select_dtypes(include="number").columns
        if numeric_cols.empty:
            await message.answer("No numeric columns to fill with median.")
        else:
            for col in numeric_cols:
                df[col].fillna(df[col].median(), inplace=True)
            await message.answer(
                "Blank values in the numeric columns are replaced by the median."
            )
    else:
        # Пытаемся привести fill_value к числу, если не получается — останется строкой
        try:
            fill_value_converted = float(fill_value)
            df.fillna(fill_value_converted, inplace=True)
            await message.answer(
                f"Empty values are replaced by a numeric value {fill_value_converted}."
            )
        except ValueError:
            df.fillna(fill_value, inplace=True)
            await message.answer(
                f"Empty values are replaced by a string '{fill_value}'."
            )

    # Обновляем сохранённые данные
    dataframes[user_id] = df


#
# 6) /show_data – выводит первые 5 строк файла
#
@router.message(Command("show_data"))
async def show_data(message: types.Message):
    user_id = message.from_user.id
    if user_id not in dataframes:
        await message.answer("First, download the file!")
        return

    df = dataframes[user_id]
    if df.empty:
        await message.answer("The data is empty!")
        return

    await message.answer(
        f"The first 5 lines:\n<pre>{df.head().to_string()}</pre>",
        parse_mode=ParseMode.HTML,
    )


#
# 7) /duplicated – показать и/или удалить дубликаты
#
@router.message(Command("duplicated"))
async def duplicated_cmd(message: types.Message):
    user_id = message.from_user.id
    if user_id not in dataframes:
        await message.answer("First, download the file!")
        return

    df = dataframes[user_id]
    if df.empty:
        await message.answer("The data is empty!")
        return

    # Считаем количество дубликатов
    dup_count = df.duplicated().sum()
    if dup_count == 0:
        await message.answer("No duplicates were found.")
        return

    text = (
        f"Detected {dup_count} duplicates.\n\n"
        "If you want to delete them, enter the command: /duplicated remove"
    )
    parts = message.text.split()
    if len(parts) > 1 and parts[1].lower() == "remove":
        df.drop_duplicates(inplace=True)
        dataframes[user_id] = df
        text = (
            f"Deleted {dup_count} duplicates. Current data size: {df.shape[0]} строк."
        )
    await message.answer(text)


#
# 8) /outliers – показать и/или удалить выбросы (простой IQR-метод)
#
@router.message(Command("outliers"))
async def outliers_cmd(message: types.Message):
    user_id = message.from_user.id
    if user_id not in dataframes:
        await message.answer("First, download the file!")
        return

    df = dataframes[user_id]
    if df.empty:
        await message.answer("The data is empty!")
        return

    numeric_cols = df.select_dtypes(include="number").columns
    if numeric_cols.empty:
        await message.answer("There are no numerical columns to search for outliers.")
        return

    # Считаем количество строк до удаления
    rows_before = df.shape[0]

    # Если пользователь ввёл "/outliers remove" – удаляем
    parts = message.text.split()
    remove_flag = len(parts) > 1 and parts[1].lower() == "remove"

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
        await message.answer(
            f"Emissions removed (approximately): {outliers_count_total}. The current data size: {rows_after} rows."
        )
    else:
        # Просто считаем, сколько выбросов (по IQR) могло бы быть удалено
        temp_df = df.copy()
        for col in numeric_cols:
            Q1 = temp_df[col].quantile(0.25)
            Q3 = temp_df[col].quantile(0.75)
            IQR = Q3 - Q1
            lower_bound = Q1 - 1.5 * IQR
            upper_bound = Q3 + 1.5 * IQR
            temp_df = temp_df[
                (temp_df[col] >= lower_bound) & (temp_df[col] <= upper_bound)
            ]
        rows_after = temp_df.shape[0]
        outliers_count_total = rows_before - rows_after
        await message.answer(
            f"By the IQR method it is possible to remove about {outliers_count_total} emissions.\n"
            "To remove outliers, enter the command: /outliers remove"
        )


#
# 9) /finish – выгрузка (отправка) текущего DataFrame обратно как CSV
#
@router.message(Command("finish"))
async def finish_cmd(message: types.Message):
    user_id = message.from_user.id
    if user_id not in dataframes:
        await message.answer("No data to upload. Upload the file first.")
        return

    df = dataframes[user_id]
    if df.empty:
        await message.answer("The data is empty! All rows may have been deleted.")
        return

    output_file = f"processed_{user_id}.csv"
    df.to_csv(output_file, index=False)

    await message.answer_document(document=FSInputFile(output_file))
    os.remove(output_file)


#
# 10) /reset – сброс сохранённых данных
#
@router.message(Command("reset"))
async def reset_cmd(message: types.Message):
    user_id = message.from_user.id
    if user_id in dataframes:
        del dataframes[user_id]
        await message.answer("The data has been reset. You can upload a new file.")
    else:
        await message.answer("No saved data for reset.")


# --- Postgres: start connection flow ---
@router.callback_query(lambda c: c.data == "pg_connect")
async def cb_pg_connect(query: types.CallbackQuery, state: FSMContext):
    await query.answer()
    await query.message.answer(
        "Please send your PostgreSQL URI (e.g. postgresql://user:pass@host:port/dbname):"
    )
    await state.set_state(PgStates.connect)


@router.message(StateFilter(PgStates.connect), lambda m: m.text)
async def msg_pg_connect(message: types.Message, state: FSMContext):
    uri = message.text.strip()
    try:
        engine = create_engine(uri)
        tables = inspect(engine).get_table_names()
        await state.update_data(pg_engine=engine, pg_tables=tables)
        # send table list
        builder = InlineKeyboardBuilder()
        for tbl in tables:
            builder.button(text=tbl, callback_data=tbl)
        builder.adjust(1)
        await message.answer(
            "Connected! Select a table:", reply_markup=builder.as_markup()
        )
        await state.set_state(PgStates.table_select)
    except Exception as e:
        await message.answer(f"Connection error: {e}")
        await state.clear()


@router.callback_query(StateFilter(PgStates.table_select))
async def cb_pg_table(query: types.CallbackQuery, state: FSMContext):
    await query.answer()
    table = query.data
    data = await state.get_data()
    engine = data["pg_engine"]
    df = pd.read_sql_table(table, engine)
    await state.update_data(df=df, pg_table=table)
    await query.message.answer(
        f"Table <b>{table}</b> loaded.\n<b>Rows</b>: {df.shape[0]}\n<b>Columns</b>: {df.shape[1]}",
        reply_markup=pg_menu_kb(),
        parse_mode=ParseMode.HTML,
    )
    await state.set_state(PgStates.menu)


@router.callback_query(StateFilter(PgStates.menu))
async def cb_pg_menu(query: types.CallbackQuery, state: FSMContext):
    await query.answer()
    choice = query.data
    data = await state.get_data()
    df, table, engine = data["df"], data["pg_table"], data["pg_engine"]
    if choice == "info":
        text = df.head().to_markdown()
    elif choice == "missing":
        text = df.isna().sum().to_markdown()
    elif choice == "duplicates":
        dup = df[df.duplicated()]
        text = dup.head().to_markdown() if not dup.empty else "No duplicates"
    elif choice == "search":
        builder = InlineKeyboardBuilder()
        for col in df.columns:
            builder.button(text=col, callback_data=col)
        builder.adjust(1)
        await query.message.answer(
            "Select column to search:", reply_markup=builder.as_markup()
        )
        return await state.set_state(PgStates.search_col)
    else:
        text = "Unknown option"

    await query.message.answer(f"<pre>{text}</pre>", parse_mode=ParseMode.HTML)
    await state.set_state(PgStates.menu)


@router.callback_query(StateFilter(PgStates.search_col))
async def cb_pg_search_col(query: types.CallbackQuery, state: FSMContext):
    await query.answer()
    await state.update_data(search_col=query.data)
    await query.message.answer(f"Enter search term for column '{query.data}':")
    await state.set_state(PgStates.search_input)


@router.message(StateFilter(PgStates.search_input), lambda m: m.text)
async def msg_pg_search_input(message: types.Message, state: FSMContext):
    data = await state.get_data()
    col, table, engine = data["search_col"], data["pg_table"], data["pg_engine"]
    val = message.text.strip()
    sql = sa_text(f"SELECT * FROM {table} WHERE {col}::text LIKE :v")
    df = pd.read_sql(sql, engine, params={"v": f"%{val}%"})
    result = df.head().to_markdown() if not df.empty else "No matches"
    await message.answer(f"<pre>{result}</pre>", parse_mode=ParseMode.HTML)
    await message.answer("Back to menu:", reply_markup=pg_menu_kb())
    await state.set_state(PgStates.menu)


logging.basicConfig(level=logging.INFO)
dp.include_router(router)


async def main():
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())

import asyncio
from aiogram import Bot, Dispatcher, types
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton
from aiogram.filters import Command
import aiosqlite
import openai
import datetime
from dotenv import load_dotenv
import os

load_dotenv()

API_TOKEN = os.getenv('API_TOKEN')
OPENAI_API_KEY = os.getenv('OPENAI_API_KEY')
OPENAI_API_URL = os.getenv('OPENAI_API_URL')
openai.api_key = OPENAI_API_KEY

dp = Dispatcher()
bot = Bot(token=API_TOKEN)

LANGUAGES = [
    ("English", "en"),
    ("Русский", "ru"),
    ("Oʻzbek", "uz")
]

async def init_db():
    async with aiosqlite.connect("bot.db") as db:
        await db.execute("""
        CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY,
            username TEXT,
            language TEXT
        )
        """)
        await db.execute("""
        CREATE TABLE IF NOT EXISTS queries (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            query TEXT,
            answer TEXT,
            created_at TEXT
        )
        """)
        await db.commit()

@dp.message(Command("start"))
async def start_handler(message: types.Message):
    await init_db()
    user_id = message.from_user.id
    username = message.from_user.username or ""
    async with aiosqlite.connect("bot.db") as db:
        await db.execute(
            "INSERT OR IGNORE INTO users (user_id, username) VALUES (?, ?)",
            (user_id, username)
        )
        await db.commit()
        cursor = await db.execute("SELECT user_id, username FROM users WHERE user_id != ?", (user_id,))
        users = await cursor.fetchall()
        text = "Other users and their queries:\n"
        for u in users:
            uid, uname = u
            text += f"User: {uname or uid}\n"
            qcur = await db.execute("SELECT query FROM queries WHERE user_id = ?", (uid,))
            qs = await qcur.fetchall()
            for q in qs:
                text += f"- {q[0]}\n"
        if len(users) == 0:
            text = "No other users yet."
    kb = ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text=lang)] for lang, code in LANGUAGES],
        resize_keyboard=True
    )
    await message.answer(text, reply_markup=kb)
    await message.answer("Choose your language:", reply_markup=kb)

@dp.message()
async def handle_message(message: types.Message):
    user_id = message.from_user.id
    text = message.text
    async with aiosqlite.connect("bot.db") as db:
        cur = await db.execute("SELECT language FROM users WHERE user_id = ?", (user_id,))
        row = await cur.fetchone()
        if row and not row[0]:
            for lang, code in LANGUAGES:
                if text == lang:
                    await db.execute("UPDATE users SET language = ? WHERE user_id = ?", (code, user_id))
                    await db.commit()
                    await message.answer(f"Language set to {lang}. What topic is your question about?")
                    return
        elif row is None:
            await message.answer("Please use /start to begin.")
            return
        else:
            # Check daily limit
            today = datetime.datetime.utcnow().date().isoformat()
            cur = await db.execute(
                "SELECT COUNT(*) FROM queries WHERE user_id = ? AND created_at >= ?",
                (user_id, today)
            )
            count = (await cur.fetchone())[0]
            if count >= 3:
                await message.answer("Daily limit reached (3 queries per day). Try again tomorrow.")
                return
            await message.answer("What is your question?")
            dp.data[user_id] = {"awaiting_question": True}
            return

    if dp.data.get(user_id, {}).get("awaiting_question"):
        dp.data[user_id]["awaiting_question"] = False
        question = text
        # OpenAI API call
        response = await openai.ChatCompletion.acreate(
            model="gpt-3.5-turbo",
            messages=[{"role": "user", "content": question}]
        )
        answer = response.choices[0].message.content.strip()
        async with aiosqlite.connect("bot.db") as db:
            await db.execute(
                "INSERT INTO queries (user_id, query, answer, created_at) VALUES (?, ?, ?, ?)",
                (user_id, question, answer, datetime.datetime.utcnow().isoformat())
            )
            await db.commit()
        await message.answer(answer)

async def main():
    await init_db()
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())

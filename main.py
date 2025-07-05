import asyncio
from aiogram import Bot, Dispatcher, types
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton
from aiogram.filters import Command
import aiosqlite
import openai
import datetime
from dotenv import load_dotenv
import os
from openai import AzureOpenAI

load_dotenv()

API_TOKEN = os.getenv('API_TOKEN')
OPENAI_API_KEY = os.getenv('OPENAI_API_KEY')
OPENAI_API_URL = os.getenv('OPENAI_API_URL')
openai.api_key = OPENAI_API_KEY

client = AzureOpenAI(
    api_version="2024-12-01-preview",
    azure_endpoint="https://ai-yaklabs030481018215.cognitiveservices.azure.com/",
    api_key=OPENAI_API_KEY,
)

dp = Dispatcher()
bot = Bot(token=API_TOKEN)

LANGUAGES = [
    ("English", "en"),
    ("Русский", "ru"),
    ("Oʻzbek", "uz")
]

user_states = {}

LANG_TEXTS = {
    "en": {
        "choose_lang": "Choose your language:",
        "set_lang": "Language set to English. What topic is your question about?",
        "ask_question": "What is your question?",
        "limit": "Daily limit reached (3 queries per day). Try again tomorrow.",
        "start": "Other users and their queries:",
        "no_users": "No other users yet.",
        "start_first": "Please use /start to begin."
    },
    "ru": {
        "choose_lang": "Выберите язык:",
        "set_lang": "Язык установлен на Русский. О какой теме ваш вопрос?",
        "ask_question": "Ваш вопрос?",
        "limit": "Достигнут дневной лимит (3 запроса в день). Попробуйте завтра.",
        "start": "Другие пользователи и их вопросы:",
        "no_users": "Пока нет других пользователей.",
        "start_first": "Пожалуйста, используйте /start для начала."
    },
    "uz": {
        "choose_lang": "Tilni tanlang:",
        "set_lang": "Til Oʻzbek tiliga oʻzgartirildi. Savolingiz qaysi mavzuda?",
        "ask_question": "Savolingizni yozing:",
        "limit": "Kunlik limitga yetdingiz (kuniga 3 ta soʻrov). Ertaga urinib koʻring.",
        "start": "Boshqa foydalanuvchilar va ularning so'rovlari:",
        "no_users": "Hali boshqa foydalanuvchilar yoʻq.",
        "start_first": "/start buyrug'ini yuboring."
    }
}

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
        text = LANG_TEXTS["en"]["start"] + "\n"
        for u in users:
            uid, uname = u
            text += f"User: {uname or uid}\n"
            qcur = await db.execute("SELECT query FROM queries WHERE user_id = ?", (uid,))
            qs = await qcur.fetchall()
            for q in qs:
                text += f"- {q[0]}\n"
        if len(users) == 0:
            text = LANG_TEXTS["en"]["no_users"]
    kb = ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text=lang)] for lang, code in LANGUAGES],
        resize_keyboard=True
    )
    await message.answer(text, reply_markup=kb)
    await message.answer(LANG_TEXTS["en"]["choose_lang"], reply_markup=kb)

@dp.message()
async def handle_message(message: types.Message):
    user_id = message.from_user.id
    text = message.text
    async with aiosqlite.connect("bot.db") as db:
        cur = await db.execute("SELECT language FROM users WHERE user_id = ?", (user_id,))
        row = await cur.fetchone()
        lang_code = row[0] if row and row[0] else "en"
        if row and not row[0]:
            for lang, code in LANGUAGES:
                if text == lang:
                    await db.execute("UPDATE users SET language = ? WHERE user_id = ?", (code, user_id))
                    await db.commit()
                    await message.answer(LANG_TEXTS[code]["set_lang"])
                    await message.answer(LANG_TEXTS[code]["ask_question"])
                    user_states[user_id] = {"awaiting_question": True}
                    return
        elif row is None:
            await message.answer(LANG_TEXTS["en"]["start_first"])
            return
        else:
            if not user_states.get(user_id, {}).get("awaiting_question"):
                await message.answer(LANG_TEXTS[lang_code]["ask_question"])
                user_states[user_id] = {"awaiting_question": True}
                return
            if await check_minute_limit(user_id):
                await message.answer(LANG_TEXTS[lang_code]["limit"])
                return
            question = text
            user_states.pop(user_id, None)
            system_prompt = {
                "en": "Answer in English.",
                "ru": "Отвечай на русском языке.",
                "uz": "Javobni o'zbek tilida yozing."
            }[lang_code]
            response = client.chat.completions.create(
                model="o4-mini",
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": question}
                ]
            )
            answer = response.choices[0].message.content.strip()
            async with aiosqlite.connect("bot.db") as db:
                await db.execute(
                    "INSERT INTO queries (user_id, query, answer, created_at) VALUES (?, ?, ?, ?)",
                    (user_id, question, answer, datetime.datetime.utcnow().isoformat())
                )
                await db.commit()
            await message.answer(answer)
            user_states[user_id] = {"awaiting_question": True}
            return

async def check_minute_limit(user_id: int) -> bool:
    now = datetime.datetime.utcnow()
    one_minute_ago = (now - datetime.timedelta(minutes=1)).isoformat()
    async with aiosqlite.connect("bot.db") as db:
        cur = await db.execute(
            "SELECT COUNT(*) FROM queries WHERE user_id = ? AND created_at >= ?",
            (user_id, one_minute_ago)
        )
        count = (await cur.fetchone())[0]
        return count >= 3

async def main():
    await init_db()
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())

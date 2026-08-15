import asyncio
import logging
import html
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.types import Message

from bot.config import BOT_TOKEN, ADMIN_ID
from bot.database import (
    init_db, log_message, set_repeat_user, 
    get_repeat_user, get_messages_by_day, 
    get_user_messages, get_username_by_id,
    get_messages_by_range, get_user_id_by_username, get_chat_stats,
    get_all_texts_iteratively
)
from bot.summarizer import Summarizer
from bot.utils import send_long_message
from datetime import datetime

# Инициализация логирования
logging.basicConfig(level=logging.INFO)

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()
summarizer = Summarizer()

async def send_help_message(message: Message):
    await message.answer(
        "Привет! Я бот-стенографист.\n\n"
        "Команды:\n"
        "/set_target [@ник] (или в ответ) — кого мне повторять\n"
        "/summarize [дата или дата...дата] — сводка за день/период\n"
        "/profile [@ник] (или в ответ) — характеристика пользователя\n"
        "/stats — статистика чата\n"
        "/holy_yandex — прославить Яндекс\n"
        "/bad_yandex — раскритиковать Яндекс\n"
        "/help — показать это сообщение"
    )

@dp.message(Command("start"))
async def cmd_start(message: Message):
    await send_help_message(message)

@dp.message(Command("help"))
async def cmd_help(message: Message):
    await send_help_message(message)

@dp.message(Command("set_target"))
async def cmd_set_target(message: Message):
    if message.from_user.id != ADMIN_ID:
        await message.answer("❌ Эта команда доступна только администратору.")
        return

    target_id = None
    target_name = "пользователь"

    if message.reply_to_message:
        target_user = message.reply_to_message.from_user
        target_id = target_user.id
        target_name = target_user.full_name
    else:
        args = message.text.split()
        if len(args) > 1:
            username = args[1].replace("@", "")
            target_id = await get_user_id_by_username(message.chat.id, username)
            if target_id:
                target_name = f"@{username}"
        
    if not target_id:
        await message.answer("❌ Пожалуйста, используйте /set_target в ответ на сообщение или укажите @никнейм.")
        return

    await set_repeat_user(message.chat.id, target_id)
    logging.info(f"Target set for chat {message.chat.id}: {target_id} ({target_name})")
    await message.answer(f"✅ Цель установлена: {target_name}. Теперь я буду повторять все его сообщения.")

@dp.message(Command("summarize"))
async def cmd_summarize(message: Message):
    args = message.text.split()
    today = datetime.now().strftime("%Y-%m-%d")
    
    if len(args) == 1:
        date_str = today
        messages = await get_messages_by_day(message.chat.id, date_str)
    elif len(args) > 1:
        date_arg = args[1]
        if "..." in date_arg:
            try:
                start_date, end_date = date_arg.split("...")
                messages = await get_messages_by_range(message.chat.id, start_date, end_date)
                date_str = f"период {start_date} — {end_date}"
            except ValueError:
                await message.answer("❌ Неверный формат диапазона. Используйте YYYY-MM-DD...YYYY-MM-DD")
                return
        else:
            date_str = date_arg
            messages = await get_messages_by_day(message.chat.id, date_str)
    else:
        # Этот блок на случай, если args пуст (хотя при наличии команды len(args) >= 1)
        date_str = today
        messages = await get_messages_by_day(message.chat.id, date_str)
    
    if not messages:
        await message.answer(f"⚠️ За {date_str} сообщений не найдено.")
        return

    summary = await summarizer.summarize_messages(messages)
    await send_long_message(message, f"📝 Сводка за {date_str}:\n\n{summary}")

@dp.message(Command("profile"))
async def cmd_profile(message: Message):
    target_id = None
    target_name = "пользователь"

    if message.reply_to_message:
        target_user = message.reply_to_message.from_user
        target_id = target_user.id
        target_name = target_user.full_name
    else:
        args = message.text.split()
        if len(args) > 1:
            username = args[1].replace("@", "")
            target_id = await get_user_id_by_username(message.chat.id, username)
            if target_id:
                target_name = f"@{username}"
    
    if not target_id:
        await message.answer("❌ Пожалуйста, используйте /profile в ответ на сообщение или укажите @никнейм.")
        return

    messages = await get_user_messages(message.chat.id, target_id)
    if not messages:
        await message.answer(f"⚠️ Я еще не успел собрать достаточно сообщений пользователя {target_name}, чтобы составить профиль.")
        return

    profile = await summarizer.characterize_user(target_name, messages)
    await send_long_message(message, f"👤 Профиль пользователя {target_name}:\n\n{profile}")

@dp.message(Command("get_id"))
async def cmd_get_id(message: Message):
    await message.answer(f"ID этого чата: {message.chat.id}")

@dp.message(Command("stats"))
async def cmd_stats(message: Message):
    total, users = await get_chat_stats(message.chat.id)
    if total == 0:
        await message.answer("📊 В базе еще нет сообщений для статистики.")
        return
    
    import re
    from collections import Counter
    import emoji
    
    user_stats = "\n".join([f"{html.escape(str(u[1]))}: {u[2]} сообщ." for u in users[:10]])
    
    all_words = []
    all_emojis = []
    async for t in get_all_texts_iteratively(message.chat.id):
        words = re.findall(r'\b\w{3,}\b', t.lower())
        all_words.extend(words)
        emojis_in_text = emoji.emoji_list(t)
        all_emojis.extend([e['emoji'] for e in emojis_in_text])
    
    common_words = Counter(all_words).most_common(20)
    words_stats = "\n".join([f"{html.escape(word)} ({count})" for word, count in common_words])
    
    common_emojis = Counter(all_emojis).most_common(10)
    emojis_stats = "\n".join([f"{e} ({count})" for e, count in common_emojis])

    response = (
        f"📊 <b>Статистика чата</b>\n\n"
        f"Всего сообщений: {total}\n\n"
        f"🔝 <b>Топ-10 авторов:</b>\n{user_stats}\n\n"
        f"🔤 <b>Топ-20 слов:</b>\n{words_stats}\n\n"
        f"🎭 <b>Топ-10 эмодзи:</b>\n{emojis_stats}"
    )
    await message.answer(response, parse_mode="HTML")

@dp.message(Command("holy_yandex"))
async def cmd_holy_yandex(message: Message):
    response = await summarizer.generate_yandex_praise()
    await message.answer(response)

@dp.message(Command("bad_yandex"))
async def cmd_bad_yandex(message: Message):
    response = await summarizer.generate_yandex_criticism()
    await message.answer(response)

@dp.message()
async def handle_all_messages(message: Message):
    if message.text and message.text.startswith('/'):
        return

    text = message.text or message.caption
    if text:
        await log_message(
            chat_id=message.chat.id,
            user_id=message.from_user.id,
            username=message.from_user.username,
            full_name=message.from_user.full_name,
            text=text
        )
    
    target_id = await get_repeat_user(message.chat.id)
    if target_id and message.from_user.id == target_id:
        await message.answer(f"📢 Повторяю {message.from_user.first_name}: {message.text}")

async def main():
    await init_db()
    logging.info("Bot started...")
    await dp.start_polling(bot)

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        logging.info("Bot stopped.")

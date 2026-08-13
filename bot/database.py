import aiosqlite
from datetime import datetime
from bot.config import DB_PATH

async def init_db():
    async with aiosqlite.connect(DB_PATH) as db:
        # Таблица для логирования сообщений чата
        await db.execute('''
            CREATE TABLE IF NOT EXISTS messages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                chat_id INTEGER,
                user_id INTEGER,
                username TEXT,
                full_name TEXT,
                text TEXT,
                timestamp DATETIME
            )
        ''')
        
        # Добавляем колонку full_name, если её нет (для старых БД)
        try:
            await db.execute('ALTER TABLE messages ADD COLUMN full_name TEXT')
        except aiosqlite.OperationalError:
            pass
            
        # Индекс для ускорения выборок по чату и времени
        await db.execute('CREATE INDEX IF NOT EXISTS idx_messages_chat_time ON messages (chat_id, timestamp)')
        
        # Таблица настроек чата (например, кого повторять)
        await db.execute('''
            CREATE TABLE IF NOT EXISTS settings (
                chat_id INTEGER PRIMARY KEY,
                repeat_user_id INTEGER
            )
        ''')
        await db.commit()

async def log_message(chat_id, user_id, username, full_name, text):
    async with aiosqlite.connect(DB_PATH) as db:
        timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        await db.execute(
            'INSERT INTO messages (chat_id, user_id, username, full_name, text, timestamp) VALUES (?, ?, ?, ?, ?, ?)',
            (chat_id, user_id, username, full_name, text, timestamp)
        )
        await db.commit()

async def set_repeat_user(chat_id, user_id):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            'INSERT OR REPLACE INTO settings (chat_id, repeat_user_id) VALUES (?, ?)',
            (chat_id, user_id)
        )
        await db.commit()

async def get_repeat_user(chat_id):
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute('SELECT repeat_user_id FROM settings WHERE chat_id = ?', (chat_id,)) as cursor:
            result = await cursor.fetchone()
            return result[0] if result else None

async def get_messages_by_day(chat_id, date_str):
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute(
            'SELECT username, text FROM messages WHERE chat_id = ? AND date(timestamp) = ?',
            (chat_id, date_str)
        ) as cursor:
            return await cursor.fetchall()

async def get_user_messages(chat_id, user_id):
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute(
            'SELECT text FROM messages WHERE chat_id = ? AND user_id = ?',
            (chat_id, user_id)
        ) as cursor:
            rows = await cursor.fetchall()
            return [row[0] for row in rows]

async def get_username_by_id(chat_id, user_id):
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute(
            'SELECT username FROM messages WHERE chat_id = ? AND user_id = ? LIMIT 1',
            (chat_id, user_id)
        ) as cursor:
            result = await cursor.fetchone()
            return result[0] if result else "Unknown"

async def get_messages_by_range(chat_id, start_date, end_date):
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute(
            'SELECT full_name, text FROM messages WHERE chat_id = ? AND date(timestamp) BETWEEN ? AND ?',
            (chat_id, start_date, end_date)
        ) as cursor:
            return await cursor.fetchall()

async def get_user_id_by_username(chat_id, username):
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute(
            'SELECT user_id FROM messages WHERE chat_id = ? AND username = ? LIMIT 1',
            (chat_id, username)
        ) as cursor:
            result = await cursor.fetchone()
            return result[0] if result else None

async def get_chat_stats(chat_id):
    async with aiosqlite.connect(DB_PATH) as db:
        # Общее количество сообщений
        async with db.execute('SELECT COUNT(*) FROM messages WHERE chat_id = ?', (chat_id,)) as cursor:
            row = await cursor.fetchone()
            total = row[0] if row else 0
        
        # Распределение по пользователям
        async with db.execute(
            'SELECT user_id, COALESCE(full_name, username, "Unknown") as name, COUNT(*) as cnt FROM messages WHERE chat_id = ? GROUP BY user_id ORDER BY cnt DESC',
            (chat_id,)
        ) as cursor:
            users = await cursor.fetchall()
        
        return total, users

async def get_all_texts_iteratively(chat_id):
    """Асинхронный генератор для получения текстов сообщений по одному (защита от OOM)"""
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute('SELECT text FROM messages WHERE chat_id = ?', (chat_id,)) as cursor:
            async for row in cursor:
                if row[0]:
                    yield row[0]

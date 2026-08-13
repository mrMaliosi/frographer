import logging
from aiogram.types import Message
from aiogram.exceptions import TelegramBadRequest

async def send_long_message(message: Message, text: str, parse_mode: str = "HTML"):
    """
    Отправляет длинные сообщения, разбивая их на части, чтобы избежать ошибки
    TelegramBadRequest: message is too long (лимит 4096 символов).
    """
    MAX_LENGTH = 4000  # Оставляем запас для разметки
    
    if len(text) <= MAX_LENGTH:
        try:
            await message.answer(text, parse_mode=parse_mode)
            return
        except TelegramBadRequest as e:
            if "message is too long" in str(e):
                pass # Переходим к разбивке, если даже короткое сообщение вызвало ошибку (например из-за разметки)
            else:
                raise e

    # Разбиваем текст на части
    parts = []
    while text:
        if len(text) <= MAX_LENGTH:
            parts.append(text)
            break
        
        # Ищем ближайший перенос строки или пробел, чтобы не резать слова
        split_idx = text.rfind('\n', 0, MAX_LENGTH)
        if split_idx == -1:
            split_idx = text.rfind(' ', 0, MAX_LENGTH)
        
        if split_idx == -1:
            split_idx = MAX_LENGTH
            
        parts.append(text[:split_idx])
        text = text[split_idx:].lstrip()

    for i, part in enumerate(parts):
        try:
            await message.answer(part, parse_mode=parse_mode)
        except TelegramBadRequest as e:
            logging.error(f"Ошибка при отправке части {i+1}/{len(parts)}: {e}")
            # В случае ошибки разметки в части сообщения, пробуем отправить как обычный текст
            await message.answer(part)
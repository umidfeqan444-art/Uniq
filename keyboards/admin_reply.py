# -*- coding: utf-8 -*-
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton

def admin_keyboard():
    buttons = [
        [KeyboardButton(text="Добавить товар"), KeyboardButton(text="Удалить товар")],
        [KeyboardButton(text="Рассылка"), KeyboardButton(text="Статистика")],
        [KeyboardButton(text="Выйти")]
    ]
    keyboard = ReplyKeyboardMarkup(
        keyboard=buttons,
        resize_keyboard=True,
        input_field_placeholder="Админ-панель"
    )
    return keyboard

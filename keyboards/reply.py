# -*- coding: utf-8 -*-
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton

def main_keyboard():
    buttons = [
        [KeyboardButton(text="🏪 Витрина"), KeyboardButton(text="💳 Купить товар")],
        [KeyboardButton(text="🔍 Поиск по ВИН")],
        [KeyboardButton(text="👤 Профиль"), KeyboardButton(text="🔄 Возврат")],
        [KeyboardButton(text="📜 Правила")] # Добавил кнопку правил для удобства
    ]
    keyboard = ReplyKeyboardMarkup(
        keyboard=buttons,
        resize_keyboard=True,
        input_field_placeholder="Выберите действие"
    )
    return keyboard

def admin_keyboard():
    buttons = [
        [KeyboardButton(text="🏪 Витрина"), KeyboardButton(text="💳 Купить товар")],
        [KeyboardButton(text="🔍 Поиск по ВИН")],
        [KeyboardButton(text="👤 Профиль"), KeyboardButton(text="🔄 Возврат")],
        [KeyboardButton(text="📜 Правила"), KeyboardButton(text="🔑 Админ-панель")] # Кнопка для доступа к админ-панели
    ]
    keyboard = ReplyKeyboardMarkup(
        keyboard=buttons,
        resize_keyboard=True,
        input_field_placeholder="Выберите действие"
    )
    return keyboard

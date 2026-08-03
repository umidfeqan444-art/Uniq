# -*- coding: utf-8 -*-
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from database import get_products_by_category, get_all_products

def showcase_keyboard(category=None):
    if category:
        products = get_products_by_category(category)
    else:
        products = get_all_products()

    buttons = []

    # Проверяем, есть ли товары
    if not products:
        buttons.append([InlineKeyboardButton(text="🔙 Назад", callback_data="buy_item")])
        return InlineKeyboardMarkup(inline_keyboard=buttons)

    for pid, name, price in products:
        buttons.append([
            InlineKeyboardButton(
                text=f"{name} - {price} руб.",
                callback_data=f"product_{pid}"
            )
        ])

    # Добавляем кнопку "Назад" в конец
    buttons.append([
        InlineKeyboardButton(
            text="🔙 Назад",
            callback_data="buy_item"
        )
    ])

    return InlineKeyboardMarkup(inline_keyboard=buttons)

# -*- coding: utf-8 -*-
from aiogram import Router, F
from aiogram.types import CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton, Message
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import StatesGroup, State
import base64

from config import ADMIN_ID
from database import get_sellers, add_seller, update_seller, delete_seller, get_all_products, get_stats, create_promo_with_owner, get_promo, list_promos, delete_promo, create_money_promo, get_user_promos, update_user_balance, get_user_profile, get_user_id_by_username, set_promo_owner, get_all_users, get_bin_search_logs, get_bin_search_stats, clear_bin_search_logs
from handlers.user_handlers import edit_by_callback, edit_by_message, safe_send_photo

router = Router()

def get_admin_keyboard():
    """Создает клавиатуру админ-панели"""
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📊 Статистика", callback_data="admin_stats")],
        [InlineKeyboardButton(text="🔍 История поисков бинов", callback_data="admin_search_logs")],
        [InlineKeyboardButton(text="🎟️ Referral Promos", callback_data="admin_promos")],
        [InlineKeyboardButton(text="💰 Редактировать баланс", callback_data="admin_edit_balance")],
        [InlineKeyboardButton(text="📢 Рассылка", callback_data="admin_broadcast")],
        [InlineKeyboardButton(text="🔙 Назад", callback_data="main_menu")]
    ])

class SellerStates(StatesGroup):
    waiting_for_seller_name = State()
    waiting_for_card_format = State()
    waiting_for_seller_params = State()
    editing_seller_details = State()

class PromoStates(StatesGroup):
    waiting_for_promo_code = State()
    waiting_for_promo_owner = State()
    waiting_for_promo_expiry = State()
    waiting_for_set_owner_input = State()

class PromoMoneyStates(StatesGroup):
    waiting_for_money_code = State()
    waiting_for_money_amount = State()
    waiting_for_money_expiry = State()




class AdminBalanceStates(StatesGroup):
    waiting_for_username = State()
    waiting_for_action = State()
    waiting_for_amount = State()

@router.callback_query(F.data.startswith("confirm_delete_"))
async def confirm_delete_seller(callback: CallbackQuery):
    try:
        if not hasattr(callback, 'data') or not isinstance(callback.data, str):
            return

        parts = callback.data.split("_")
        if len(parts) < 3:
            return

        seller_id = parts[2]
        if not seller_id.isdigit():
            return

        seller_id = int(seller_id)
        sellers = get_sellers()

        if str(seller_id) not in sellers:
            return

        seller_info = sellers[str(seller_id)]
        _, _, _, holder_name, _, _, _, _, _, _, _ = seller_info

        confirm_keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="✅ Подтвердить удаление", callback_data=f"delete_seller_{seller_id}")],
            [InlineKeyboardButton(text="❌ Отмена", callback_data="admin")]
        ])
        await edit_by_callback(callback, text=f"🗑️ Вы уверены, что хотите удалить поставщика '{holder_name}'?", photo_path="котлета.jpg", reply_markup=confirm_keyboard)
    except Exception as e:
        print(f"[ERROR] Exception in confirm_delete_seller: {e}")
        await edit_by_callback(callback, text="❌ Ошибка при подтверждении удаления.", photo_path="котлета.jpg")

@router.callback_query(F.data.startswith("delete_seller_"))
async def delete_seller_handler(callback: CallbackQuery):
    try:
        data = callback.data
        if not data or not isinstance(data, str):
            return

        parts = data.split("_")
        if len(parts) < 3:
            return

        seller_id_str = parts[2]
        if not seller_id_str.isdigit():
            return

        seller_id = int(seller_id_str)

        sellers = get_sellers()
        if str(seller_id) not in sellers:
            return

        from database import _delete_seller
        result = await _delete_seller(seller_id)

        if result:
            sellers = get_sellers()

            if not sellers:
                await edit_by_callback(callback, text="🛒 Поставщики отсутствуют.\n\n🆕 Нажмите 'Добавить поставщика', чтобы добавить первого поставщика.",
                                            photo_path="котлета.jpg",
                                            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                                                [InlineKeyboardButton(text="🆕 Добавить поставщика", callback_data="add_seller")],
                                                [InlineKeyboardButton(text="🔙 Назад", callback_data="admin_panel")]
                                            ]))
            else:
                seller_buttons = []
                for s_id, s_info in sellers.items():
                    _, _, _, holder_name, _, _, _, _, _, _, _ = s_info
                    seller_buttons.append([InlineKeyboardButton(text=f"{holder_name}", callback_data=f"show_seller_{s_id}")])

                keyboard = InlineKeyboardMarkup(inline_keyboard=seller_buttons + [
                    [InlineKeyboardButton(text="🆕 Добавить поставщика", callback_data="add_seller")],
                    [InlineKeyboardButton(text="🔙 Назад", callback_data="admin_panel")]
                ])
                await edit_by_callback(callback, text="👥 Список поставщиков обновлён:", photo_path="котлета.jpg", reply_markup=keyboard)
        else:
            await edit_by_callback(callback, text="❌ Не удалось удалить поставщика", photo_path="котлета.jpg")
    except Exception as e:
        print(f"[ERROR] Exception in delete_seller_handler: {e}")
        await edit_by_callback(callback, text="👥 Возникла ошибка при удалении поставщика.", photo_path="котлета.jpg")

@router.callback_query(F.data == "add_seller")
async def start_add_seller(callback: CallbackQuery, state: FSMContext):
    await edit_by_callback(callback, text="🆕 Введите название поставщика:", photo_path="котлета.jpg")
    await state.set_state(SellerStates.waiting_for_seller_name)

@router.message(SellerStates.waiting_for_seller_name)
async def process_seller_name(message: Message, state: FSMContext):
    seller_name = message.text.strip()
    await state.update_data(seller_name=seller_name)
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="num|exp|cvv", callback_data="seller_fmt_1")],
        [InlineKeyboardButton(text="num|exp|cvv|holder|phone|email", callback_data="seller_fmt_2")],
        [InlineKeyboardButton(text="num|exp|cvv|holder|phone|email|city|address|zip", callback_data="seller_fmt_3")],
        [InlineKeyboardButton(text="No card lines / other", callback_data="seller_fmt_4")]
    ])
    await edit_by_message(message, text="Выберите формат(ы), которые поставщик предоставляет (нажмите одну из кнопок):", photo_path="котлета.jpg", reply_markup=kb)
    await state.set_state(SellerStates.waiting_for_card_format)

@router.message(SellerStates.waiting_for_card_format)
async def process_card_format(message: Message, state: FSMContext):
    data = await state.get_data()
    seller_name = data.get('seller_name', '')

    card_format = message.text.strip()
    await state.update_data(card_format=card_format)
    await edit_by_message(message, text="🆕 Теперь введите параметры поставщика в формате:\n`депозит(Да/Нет)|рейтинг|количество_карт|продано|VR_процент`\n\nПример:\n`Да|4.8|2791|10826|81`", photo_path="котлета.jpg")
    await state.set_state(SellerStates.waiting_for_seller_params)

@router.message(SellerStates.waiting_for_seller_params)
async def process_seller_params(message: Message, state: FSMContext):
    data = await state.get_data()
    seller_name = data.get('seller_name', '')
    card_format = data.get('card_format', '')

    params = message.text.strip()
    try:
        param_parts = params.split('|')
        if len(param_parts) != 5:
            await edit_by_message(message, text="❌ Неверный формат параметров поставщика. Используйте:\n`депозит(Да/Нет)|рейтинг|количество_карт|продано|VR_процент`", photo_path="котлета.jpg")
            return

        deposit_str, rating, cards, sold, vr = param_parts
        deposit = deposit_str.lower() == 'да'

        card_parts = card_format.split('|')
        if len(card_parts) != 5:
            await edit_by_message(message, text="❌ Неверный формат данных карты. Используйте:\n`номер_карты|срок_годности|CVV|телефон|email`", photo_path="котлета.jpg")
            return

        card_number, expiry, cvv, phone, email = card_parts

        seller_id = add_seller(card_number, expiry, cvv, seller_name, phone, email, deposit, float(rating), int(cards), int(sold), int(vr))

        if seller_id:
            await edit_by_message(message, text=f"🆕 Поставщик '{seller_name}' успешно добавлен!", photo_path="котлета.jpg")
        else:
            await edit_by_message(message, text="❌ Ошибка добавления поставщика.", photo_path="котлета.jpg")

        await state.clear()
        await edit_by_message(message, text="👥 Список поставщиков обновлён.", photo_path="котлета.jpg", reply_markup=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="🔙 Назад", callback_data="admin")]]))
    except Exception as e:
        await edit_by_message(message, text=f"❌ Ошибка: {e}\nПроверьте корректность введённых данных.", photo_path="котлета.jpg")
        await state.clear()

@router.callback_query(F.data == "admin_products")
async def admin_products_handler(callback: CallbackQuery):
    products = get_all_products()
    if not products:
        await edit_by_callback(callback, text="🛒 Товары отсутствуют.", photo_path="котлета.jpg")

    product_buttons = []
    for product in products:
        product_id, name, _, _, _ = product
        product_buttons.append([
            InlineKeyboardButton(text=f"{name}", callback_data=f"product_info_{product_id}"),
            InlineKeyboardButton(text="🔄 Редактировать", callback_data=f"edit_product_{product_id}"),
            InlineKeyboardButton(text="🗑️ Удалить", callback_data=f"delete_product_{product_id}")
        ])

    product_buttons.append([InlineKeyboardButton(text="🆕 Добавить товар", callback_data="add_product")])
    product_buttons.append([InlineKeyboardButton(text="🔙 Назад", callback_data="admin_panel")])

    keyboard = InlineKeyboardMarkup(inline_keyboard=product_buttons)
    await edit_by_callback(callback, text="🛒 Управление товарами:", photo_path="котлета.jpg", reply_markup=keyboard)

@router.callback_query(F.data == "admin_sellers")
async def admin_sellers_handler(callback: CallbackQuery):
    sellers = get_sellers()

    main_suppliers = {}
    for s_id, s_info in sellers.items():
        _, _, _, holder_name, _, _, _, _, _, _, _ = s_info
        if holder_name in ['ADMIN', 'ZEUS']:
            main_suppliers[s_id] = s_info

    if not main_suppliers:
        await edit_by_callback(callback, text="🛒 Поставщики отсутствуют.\n\n🆕 Нажмите 'Добавить поставщика', чтобы добавить первого поставщика.",
                                    photo_path="котлета.jpg",
                                    reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                                        [InlineKeyboardButton(text="🆕 Добавить поставщика", callback_data="add_seller")],
                                        [InlineKeyboardButton(text="🔙 Назад", callback_data="admin_panel")]
                                    ]))
        return

    seller_buttons = []
    for s_id, s_info in main_suppliers.items():
        _, _, _, holder_name, _, _, _, _, _, _, _ = s_info
        seller_buttons.append([InlineKeyboardButton(text=f"{holder_name}", callback_data=f"show_seller_{s_id}")])

    keyboard = InlineKeyboardMarkup(inline_keyboard=seller_buttons + [
        [InlineKeyboardButton(text="🔙 Назад", callback_data="admin_panel")]
    ])
    await edit_by_callback(callback, text="👥 Список поставщиков:", photo_path="котлета.jpg", reply_markup=keyboard)

@router.callback_query(F.data.startswith("show_seller_"))
async def show_seller_handler(callback: CallbackQuery):
    seller_id = callback.data.split("_")[2]
    sellers = get_sellers()
    if seller_id not in sellers:
        await edit_by_callback(callback, text="Поставщик не найден", photo_path="котлета.jpg")
        return

    seller_info = sellers[seller_id]
    num, exp, cvv, holder_name, phone, email, deposit, rating, cards, sold, vr = seller_info

    seller_text = f"""🏪 {holder_name}

FORMAT: {num}|{exp}|{cvv}|{phone}|{email}
────────────────────────
🛡 Deposit: {'Yes' if deposit else 'No'}
⭐️ Rating: {rating}
💳 Cards: {cards}
📦 Sold: {sold}
✅ VR: {vr}%"""

    back_button = InlineKeyboardButton(text="🔙 Назад", callback_data="admin")
    keyboard = InlineKeyboardMarkup(inline_keyboard=[[back_button]])

    try:
        await edit_by_callback(callback, text=seller_text, photo_path="котлета.jpg", reply_markup=keyboard, parse_mode="HTML")
    except Exception as e:
        print(f"Error sending seller info with image: {e}")
        await edit_by_callback(callback, text=seller_text, photo_path="котлета.jpg", reply_markup=keyboard, parse_mode="HTML")

@router.callback_query(F.data == "admin_stats")
async def admin_stats_handler(callback: CallbackQuery):
    from database import get_simple_stats
    
    stats = get_simple_stats()
    
    if not stats:
        stats_text = "❌ Ошибка получения статистики"
    else:
        stats_text = f"""📊 <b>Статистика магазина</b>

💰 <b>Заработано сегодня:</b> ${stats['earnings_today']:.2f}
├ 💳 Покупки: ${stats['revenue_today']:.2f}
└ 💵 Пополнения: ${stats['topups_today']:.2f}

📈 <b>Активность за сегодня:</b>
🛒 Покупок: {stats['purchases_today']}

📊 <b>Общая статистика:</b>
👥 Всего пользователей: {stats['total_users']}
🛍️ Всего покупок: {stats['total_purchases']}
📦 Товаров в каталоге: {stats['total_products']}"""

    back_button = InlineKeyboardButton(text="🔙 Назад", callback_data="admin")
    keyboard = InlineKeyboardMarkup(inline_keyboard=[[back_button]])
    await edit_by_callback(callback, text=stats_text, photo_path="котлета.jpg", reply_markup=keyboard, parse_mode="HTML")

@router.callback_query(F.data == "admin_search_logs")
async def admin_search_logs_handler(callback: CallbackQuery):
    """Главное меню логов поиска"""
    if callback.from_user.id != ADMIN_ID:
        await edit_by_callback(callback, text="❌ Access denied.", photo_path="котлета.jpg")
        return
    
    from database import get_bin_search_stats
    
    stats = get_bin_search_stats()
    
    if not stats:
        stats_text = "❌ Ошибка получения статистики поиска"
    else:
        stats_text = f"""🔍 <b>Статистика поисковых запросов</b>

📊 <b>Общая статистика:</b>
🔎 Всего поисков: {stats['total_searches']}
📅 За сегодня: {stats['searches_today']}
📆 За неделю: {stats['searches_7d']}

🔥 <b>Топ-5 популярных бинов:</b>
"""
        
        # Добавляем топ бинов
        for i, (bin_query, count) in enumerate(stats['top_bins'][:5], 1):
            stats_text += f"{i}. <code>{bin_query}</code> — {count} раз\n"
        
        if not stats['top_bins']:
            stats_text += "Нет данных\n"
        
        stats_text += "\n👥 <b>Топ-5 активных пользователей:</b>\n"
        
        # Добавляем топ пользователей
        for i, (username, count) in enumerate(stats['top_users'][:5], 1):
            stats_text += f"{i}. @{username} — {count} поисков\n"
        
        if not stats['top_users']:
            stats_text += "Нет данных"
    
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📜 Последние 50 запросов", callback_data="admin_search_logs_recent")],
        [InlineKeyboardButton(text="🗑️ Очистить логи", callback_data="admin_search_logs_clear")],
        [InlineKeyboardButton(text="🔙 Назад", callback_data="admin")]
    ])
    
    await edit_by_callback(callback, text=stats_text, photo_path="котлета.jpg", reply_markup=kb, parse_mode="HTML")

@router.callback_query(F.data == "admin_search_logs_recent")
async def admin_search_logs_recent_handler(callback: CallbackQuery):
    """Показать последние поисковые запросы"""
    if callback.from_user.id != ADMIN_ID:
        await callback.answer("Access denied.")
        return
    
    from database import get_bin_search_logs
    
    logs = get_bin_search_logs(limit=50)
    
    if not logs:
        text = "📭 Логи поиска пусты"
    else:
        text = f"📜 <b>Последние {len(logs)} поисковых запросов:</b>\n\n"
        
        for log in logs[:30]:  # Показываем только первые 30 для читаемости
            username = log['username'] or 'Unknown'
            bin_query = log['bin_query']
            search_date = log['search_date']
            
            # Форматируем дату
            try:
                from datetime import datetime
                dt = datetime.strptime(search_date, '%Y-%m-%d %H:%M:%S')
                date_str = dt.strftime('%d.%m %H:%M')
            except:
                date_str = search_date
            
            text += f"• @{username} искал <code>{bin_query}</code> ({date_str})\n"
        
        if len(logs) > 30:
            text += f"\n... и еще {len(logs) - 30} запросов"
    
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔙 Назад", callback_data="admin_search_logs")]
    ])
    
    await edit_by_callback(callback, text=text, photo_path="котлета.jpg", reply_markup=kb, parse_mode="HTML")

@router.callback_query(F.data == "admin_search_logs_clear")
async def admin_search_logs_clear_handler(callback: CallbackQuery):
    """Подтверждение очистки логов"""
    if callback.from_user.id != ADMIN_ID:
        await callback.answer("Access denied.")
        return
    
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✅ Да, очистить", callback_data="admin_search_logs_clear_confirm")],
        [InlineKeyboardButton(text="❌ Отмена", callback_data="admin_search_logs")]
    ])
    
    await edit_by_callback(callback, text="⚠️ Вы уверены, что хотите очистить все логи поиска?\n\nЭто действие нельзя отменить.", photo_path="котлета.jpg", reply_markup=kb)

@router.callback_query(F.data == "admin_search_logs_clear_confirm")
async def admin_search_logs_clear_confirm_handler(callback: CallbackQuery):
    """Очистка логов"""
    if callback.from_user.id != ADMIN_ID:
        await callback.answer("Access denied.")
        return
    
    from database import clear_bin_search_logs
    
    success = clear_bin_search_logs()
    
    if success:
        text = "✅ Логи поиска успешно очищены"
    else:
        text = "❌ Ошибка при очистке логов"
    
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔙 Назад", callback_data="admin_search_logs")]
    ])
    
    await edit_by_callback(callback, text=text, photo_path="котлета.jpg", reply_markup=kb)

@router.callback_query(F.data == "admin_promos")
async def admin_promos_handler(callback: CallbackQuery, state: FSMContext):
    # Очищаем состояние при входе в управление промокодами
    await state.clear()
    
    if callback.from_user.id != ADMIN_ID:
        await edit_by_callback(callback, text="❌ Access denied.", photo_path="котлета.jpg")
        return

    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="➕ Create Referral Promo", callback_data="admin_create_promo")],
        [InlineKeyboardButton(text="➕ Create Money Promo", callback_data="admin_create_money_promo")],
        [InlineKeyboardButton(text="📜 List Promos", callback_data="admin_list_promos")],
        [InlineKeyboardButton(text="🔙 Назад", callback_data="admin")]
    ])
    await edit_by_callback(callback, text="🎟️ Referral Promo Codes Management:", photo_path="котлета.jpg", reply_markup=kb)

@router.callback_query(F.data == "admin")
async def admin_handler_from_callback(callback: CallbackQuery, state: FSMContext):
    # Очищаем состояние при возврате в админ панель
    await state.clear()
    
    if callback.from_user.id != ADMIN_ID:
        await edit_by_callback(callback, text="❌ Access denied. You are not an administrator.", photo_path="котлета.jpg")
        return

    await edit_by_callback(callback, text="🔑 Админ-панель:", photo_path="котлета.jpg", reply_markup=get_admin_keyboard())

@router.callback_query(F.data == "admin_create_promo")
async def admin_create_promo_start(callback: CallbackQuery, state: FSMContext):
    if callback.from_user.id != ADMIN_ID:
        await callback.answer("Access denied.")
        return
    
    back_button = InlineKeyboardButton(text="🔙 Назад", callback_data="admin_promos")
    keyboard = InlineKeyboardMarkup(inline_keyboard=[[back_button]])
    
    await edit_by_callback(callback, text="Enter promo code (alphanumeric):", photo_path="котлета.jpg", reply_markup=keyboard)
    await state.set_state(PromoStates.waiting_for_promo_code)

@router.callback_query(F.data == "admin_create_money_promo")
async def admin_create_money_promo_start(callback: CallbackQuery, state: FSMContext):
    if callback.from_user.id != ADMIN_ID:
        await callback.answer("Access denied.")
        return
    
    back_button = InlineKeyboardButton(text="🔙 Назад", callback_data="admin_promos")
    keyboard = InlineKeyboardMarkup(inline_keyboard=[[back_button]])
    
    await edit_by_callback(callback, text="Enter money promo code (alphanumeric):", photo_path="котлета.jpg", reply_markup=keyboard)
    await state.set_state(PromoMoneyStates.waiting_for_money_code)

@router.message(PromoMoneyStates.waiting_for_money_code)
async def admin_create_money_code(message: Message, state: FSMContext):
    code = message.text.strip().upper()
    
    # Проверка на команду отмены
    if code.lower() in ['/cancel', 'отмена', 'cancel']:
        await state.clear()
        kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="➕ Create Referral Promo", callback_data="admin_create_promo")],
            [InlineKeyboardButton(text="➕ Create Money Promo", callback_data="admin_create_money_promo")],
            [InlineKeyboardButton(text="📜 List Promos", callback_data="admin_list_promos")],
            [InlineKeyboardButton(text="🔙 Назад", callback_data="admin")]
        ])
        await edit_by_message(message, text="🎟️ Referral Promo Codes Management:", photo_path="котлета.jpg", reply_markup=kb)
        return
    
    if not code or len(code) < 3:
        back_button = InlineKeyboardButton(text="🔙 Назад", callback_data="admin_promos")
        keyboard = InlineKeyboardMarkup(inline_keyboard=[[back_button]])
        await edit_by_message(message, text="❌ Promo code too short. Enter at least 3 characters:", photo_path="котлета.jpg", reply_markup=keyboard)
        return
    await state.update_data(money_code=code)
    
    back_button = InlineKeyboardButton(text="🔙 Назад", callback_data="admin_promos")
    keyboard = InlineKeyboardMarkup(inline_keyboard=[[back_button]])
    
    await edit_by_message(message, text="Enter bonus amount in USD (e.g., 5.00):", photo_path="котлета.jpg", reply_markup=keyboard)
    await state.set_state(PromoMoneyStates.waiting_for_money_amount)

@router.message(PromoMoneyStates.waiting_for_money_amount)
async def admin_create_money_amount(message: Message, state: FSMContext):
    text = message.text.strip()
    
    # Проверка на команду отмены
    if text.lower() in ['/cancel', 'отмена', 'cancel']:
        await state.clear()
        kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="➕ Create Referral Promo", callback_data="admin_create_promo")],
            [InlineKeyboardButton(text="➕ Create Money Promo", callback_data="admin_create_money_promo")],
            [InlineKeyboardButton(text="📜 List Promos", callback_data="admin_list_promos")],
            [InlineKeyboardButton(text="🔙 Назад", callback_data="admin")]
        ])
        await edit_by_message(message, text="🎟️ Referral Promo Codes Management:", photo_path="котлета.jpg", reply_markup=kb)
        return
    
    data = await state.get_data()
    code = data.get('money_code')
    try:
        amount = float(text)
        if amount <= 0:
            raise ValueError()
    except Exception:
        back_button = InlineKeyboardButton(text="🔙 Назад", callback_data="admin_promos")
        keyboard = InlineKeyboardMarkup(inline_keyboard=[[back_button]])
        await edit_by_message(message, text="❌ Invalid amount. Enter a positive number like 5.00:", photo_path="котлета.jpg", reply_markup=keyboard)
        return
    await state.update_data(money_amount=amount)
    await state.update_data(money_uses=-1)
    
    back_button = InlineKeyboardButton(text="🔙 Назад", callback_data="admin_promos")
    keyboard = InlineKeyboardMarkup(inline_keyboard=[[back_button]])
    
    await edit_by_message(message, text="Enter expiration date for promo (format: YYYY-MM-DD, e.g., 2025-12-31). Type SKIP to set no expiration:", photo_path="котлета.jpg", reply_markup=keyboard)
    await state.set_state(PromoMoneyStates.waiting_for_money_expiry)

@router.message(PromoMoneyStates.waiting_for_money_expiry)
async def admin_create_money_expiry(message: Message, state: FSMContext):
    text = message.text.strip().upper()
    
    # Проверка на команду отмены
    if text.lower() in ['/cancel', 'отмена', 'cancel']:
        await state.clear()
        kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="➕ Create Referral Promo", callback_data="admin_create_promo")],
            [InlineKeyboardButton(text="➕ Create Money Promo", callback_data="admin_create_money_promo")],
            [InlineKeyboardButton(text="📜 List Promos", callback_data="admin_list_promos")],
            [InlineKeyboardButton(text="🔙 Назад", callback_data="admin")]
        ])
        await edit_by_message(message, text="🎟️ Referral Promo Codes Management:", photo_path="котлета.jpg", reply_markup=kb)
        return
    
    data = await state.get_data()
    code = data.get('money_code')
    amount = data.get('money_amount')
    uses = data.get('money_uses')

    expiry = text
    if expiry == 'SKIP' or expiry == '':
        expiry = None
    else:
        try:
            from datetime import datetime
            datetime.strptime(expiry, '%Y-%m-%d')
        except ValueError:
            back_button = InlineKeyboardButton(text="🔙 Назад", callback_data="admin_promos")
            keyboard = InlineKeyboardMarkup(inline_keyboard=[[back_button]])
            await edit_by_message(message, text="❌ Invalid date format. Use YYYY-MM-DD (e.g., 2025-12-31). Type SKIP to set no expiration:", photo_path="котлета.jpg", reply_markup=keyboard)
            return

    ok = create_money_promo(code, uses, amount, expiry)

    back_button = InlineKeyboardButton(text="🔙 В админ панель", callback_data="admin")
    keyboard = InlineKeyboardMarkup(inline_keyboard=[[back_button]])

    if ok:
        expiry_text = f", expires on {expiry}" if expiry else ""
        await edit_by_message(message, text=f"✅ Money promo '{code}' created: ${amount:.2f}, uses={uses}{expiry_text}.", photo_path="котлета.jpg", reply_markup=keyboard)
    else:
        await edit_by_message(message, text="❌ Failed to create money promo. See logs.", photo_path="котлета.jpg", reply_markup=keyboard)

    await state.clear()


@router.callback_query(F.data == "admin_edit_balance")
async def admin_edit_balance_start(callback: CallbackQuery, state: FSMContext):
    if callback.from_user.id != ADMIN_ID:
        await callback.answer("Access denied.")
        return
    
    back_button = InlineKeyboardButton(text="🔙 Назад", callback_data="admin")
    keyboard = InlineKeyboardMarkup(inline_keyboard=[[back_button]])
    
    await edit_by_callback(callback, text="💰 Редактирование баланса\n\nВведите username пользователя (без @) или user_id:", photo_path="котлета.jpg", reply_markup=keyboard)
    await state.set_state(AdminBalanceStates.waiting_for_username)


@router.callback_query(F.data == "admin", AdminBalanceStates.waiting_for_username)
async def admin_balance_cancel_username(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    if callback.from_user.id != ADMIN_ID:
        await edit_by_callback(callback, text="❌ Access denied. Вы не администратор.", photo_path="котлета.jpg")
        return

    await edit_by_callback(callback, text="🔑 Админ-панель:", photo_path="котлета.jpg", reply_markup=get_admin_keyboard())

@router.callback_query(F.data == "admin", AdminBalanceStates.waiting_for_amount)
async def admin_balance_cancel_amount(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    if callback.from_user.id != ADMIN_ID:
        await edit_by_callback(callback, text="❌ Access denied. Вы не администратор.", photo_path="котлета.jpg")
        return

    await edit_by_callback(callback, text="🔑 Админ-панель:", photo_path="котлета.jpg", reply_markup=get_admin_keyboard())

# Обработчики для промокодов
@router.callback_query(F.data == "admin_promos", PromoStates.waiting_for_promo_code)
async def promo_cancel_code(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    if callback.from_user.id != ADMIN_ID:
        await edit_by_callback(callback, text="❌ Access denied.", photo_path="котлета.jpg")
        return

    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="➕ Create Referral Promo", callback_data="admin_create_promo")],
        [InlineKeyboardButton(text="➕ Create Money Promo", callback_data="admin_create_money_promo")],
        [InlineKeyboardButton(text="📜 List Promos", callback_data="admin_list_promos")],
        [InlineKeyboardButton(text="🔙 Назад", callback_data="admin")]
    ])
    await edit_by_callback(callback, text="🎟️ Referral Promo Codes Management:", photo_path="котлета.jpg", reply_markup=kb)

@router.callback_query(F.data == "admin_promos", PromoStates.waiting_for_promo_owner)
async def promo_cancel_owner(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    if callback.from_user.id != ADMIN_ID:
        await edit_by_callback(callback, text="❌ Access denied.", photo_path="котлета.jpg")
        return

    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="➕ Create Referral Promo", callback_data="admin_create_promo")],
        [InlineKeyboardButton(text="➕ Create Money Promo", callback_data="admin_create_money_promo")],
        [InlineKeyboardButton(text="📜 List Promos", callback_data="admin_list_promos")],
        [InlineKeyboardButton(text="🔙 Назад", callback_data="admin")]
    ])
    await edit_by_callback(callback, text="🎟️ Referral Promo Codes Management:", photo_path="котлета.jpg", reply_markup=kb)

@router.callback_query(F.data == "admin_promos", PromoStates.waiting_for_promo_expiry)
async def promo_cancel_expiry(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    if callback.from_user.id != ADMIN_ID:
        await edit_by_callback(callback, text="❌ Access denied.", photo_path="котлета.jpg")
        return

    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="➕ Create Referral Promo", callback_data="admin_create_promo")],
        [InlineKeyboardButton(text="➕ Create Money Promo", callback_data="admin_create_money_promo")],
        [InlineKeyboardButton(text="📜 List Promos", callback_data="admin_list_promos")],
        [InlineKeyboardButton(text="🔙 Назад", callback_data="admin")]
    ])
    await edit_by_callback(callback, text="🎟️ Referral Promo Codes Management:", photo_path="котлета.jpg", reply_markup=kb)

@router.callback_query(F.data == "admin_promos", PromoStates.waiting_for_set_owner_input)
async def promo_cancel_set_owner(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    if callback.from_user.id != ADMIN_ID:
        await edit_by_callback(callback, text="❌ Access denied.", photo_path="котлета.jpg")
        return

    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="➕ Create Referral Promo", callback_data="admin_create_promo")],
        [InlineKeyboardButton(text="➕ Create Money Promo", callback_data="admin_create_money_promo")],
        [InlineKeyboardButton(text="📜 List Promos", callback_data="admin_list_promos")],
        [InlineKeyboardButton(text="🔙 Назад", callback_data="admin")]
    ])
    await edit_by_callback(callback, text="🎟️ Referral Promo Codes Management:", photo_path="котлета.jpg", reply_markup=kb)

# Обработчики для денежных промокодов
@router.callback_query(F.data == "admin_promos", PromoMoneyStates.waiting_for_money_code)
async def money_promo_cancel_code(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    if callback.from_user.id != ADMIN_ID:
        await edit_by_callback(callback, text="❌ Access denied.", photo_path="котлета.jpg")
        return

    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="➕ Create Referral Promo", callback_data="admin_create_promo")],
        [InlineKeyboardButton(text="➕ Create Money Promo", callback_data="admin_create_money_promo")],
        [InlineKeyboardButton(text="📜 List Promos", callback_data="admin_list_promos")],
        [InlineKeyboardButton(text="🔙 Назад", callback_data="admin")]
    ])
    await edit_by_callback(callback, text="🎟️ Referral Promo Codes Management:", photo_path="котлета.jpg", reply_markup=kb)

@router.callback_query(F.data == "admin_promos", PromoMoneyStates.waiting_for_money_amount)
async def money_promo_cancel_amount(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    if callback.from_user.id != ADMIN_ID:
        await edit_by_callback(callback, text="❌ Access denied.", photo_path="котлета.jpg")
        return

    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="➕ Create Referral Promo", callback_data="admin_create_promo")],
        [InlineKeyboardButton(text="➕ Create Money Promo", callback_data="admin_create_money_promo")],
        [InlineKeyboardButton(text="📜 List Promos", callback_data="admin_list_promos")],
        [InlineKeyboardButton(text="🔙 Назад", callback_data="admin")]
    ])
    await edit_by_callback(callback, text="🎟️ Referral Promo Codes Management:", photo_path="котлета.jpg", reply_markup=kb)

@router.callback_query(F.data == "admin_promos", PromoMoneyStates.waiting_for_money_expiry)
async def money_promo_cancel_expiry(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    if callback.from_user.id != ADMIN_ID:
        await edit_by_callback(callback, text="❌ Access denied.", photo_path="котлета.jpg")
        return

    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="➕ Create Referral Promo", callback_data="admin_create_promo")],
        [InlineKeyboardButton(text="➕ Create Money Promo", callback_data="admin_create_money_promo")],
        [InlineKeyboardButton(text="📜 List Promos", callback_data="admin_list_promos")],
        [InlineKeyboardButton(text="🔙 Назад", callback_data="admin")]
    ])
    await edit_by_callback(callback, text="🎟️ Referral Promo Codes Management:", photo_path="котлета.jpg", reply_markup=kb)

@router.message(AdminBalanceStates.waiting_for_username)
async def admin_balance_receive_username(message: Message, state: FSMContext):
    if message.from_user.id != ADMIN_ID:
        return
    text = message.text.strip()
    
    # Проверка на команду отмены
    if text.lower() in ['/cancel', 'отмена', 'cancel']:
        await state.clear()
        await edit_by_message(message, text="🔑 Админ-панель:", photo_path="котлета.jpg", reply_markup=get_admin_keyboard())
        return
    
    # Determine user id
    uid = None
    if text.isdigit():
        uid = int(text)
    else:
        uid = get_user_id_by_username(text)

    if not uid:
        back_button = InlineKeyboardButton(text="🔙 Назад", callback_data="admin")
        keyboard = InlineKeyboardMarkup(inline_keyboard=[[back_button]])
        await edit_by_message(message, text=f"❌ Пользователь '{text}' не найден. Введите корректный username или user_id, или /cancel, чтобы выйти.", photo_path="котлета.jpg", reply_markup=keyboard)
        return

    await state.update_data(admin_target_user_id=uid)
    # ask action
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="➕ Добавить", callback_data="admin_balance_add")],
        [InlineKeyboardButton(text="➖ Убавить", callback_data="admin_balance_sub")],
        [InlineKeyboardButton(text="🔙 Отмена", callback_data="admin")]
    ])
    await edit_by_message(message, text=f"Пользователь найден (user_id={uid}). Выберите действие:", photo_path="котлета.jpg", reply_markup=kb)
    await state.set_state(AdminBalanceStates.waiting_for_action)


@router.callback_query(F.data == "admin_balance_add")
async def admin_balance_add_cb(callback: CallbackQuery, state: FSMContext):
    if callback.from_user.id != ADMIN_ID:
        await callback.answer("Access denied.")
        return
    data = await state.get_data()
    uid = data.get('admin_target_user_id')
    if not uid:
        await callback.answer("User not set. Start again.")
        await edit_by_callback(callback, text="❌ Ошибка: пользователь не задан. Начните сначала.", photo_path="котлета.jpg")
        await state.clear()
        return
    await state.update_data(admin_action='add')
    
    back_button = InlineKeyboardButton(text="🔙 Назад", callback_data="admin")
    keyboard = InlineKeyboardMarkup(inline_keyboard=[[back_button]])
    
    await edit_by_callback(callback, text="Введите сумму для добавления (например: 10.50):", photo_path="котлета.jpg", reply_markup=keyboard)
    await state.set_state(AdminBalanceStates.waiting_for_amount)


@router.callback_query(F.data == "admin_balance_sub")
async def admin_balance_sub_cb(callback: CallbackQuery, state: FSMContext):
    if callback.from_user.id != ADMIN_ID:
        await callback.answer("Access denied.")
        return
    data = await state.get_data()
    uid = data.get('admin_target_user_id')
    if not uid:
        await callback.answer("User not set. Start again.")
        await edit_by_callback(callback, text="❌ Ошибка: пользователь не задан. Начните сначала.", photo_path="котлета.jpg")
        await state.clear()
        return
    await state.update_data(admin_action='sub')
    
    back_button = InlineKeyboardButton(text="🔙 Назад", callback_data="admin")
    keyboard = InlineKeyboardMarkup(inline_keyboard=[[back_button]])
    
    await edit_by_callback(callback, text="Введите сумму для вычета (например: 5.00):", photo_path="котлета.jpg", reply_markup=keyboard)
    await state.set_state(AdminBalanceStates.waiting_for_amount)


@router.message(AdminBalanceStates.waiting_for_amount)
async def admin_balance_receive_amount(message: Message, state: FSMContext):
    if message.from_user.id != ADMIN_ID:
        return
    
    text = message.text.strip()
    
    # Проверка на команду отмены
    if text.lower() in ['/cancel', 'отмена', 'cancel']:
        await state.clear()
        await edit_by_message(message, text="🔑 Админ-панель:", photo_path="котлета.jpg", reply_markup=get_admin_keyboard())
        return
    
    data = await state.get_data()
    uid = data.get('admin_target_user_id')
    action = data.get('admin_action')
    if not uid or not action:
        await edit_by_message(message, text="❌ Ошибка: пользователь или действие не заданы. Начните сначала.", photo_path="котлета.jpg")
        await state.clear()
        return

    try:
        amount = float(text)
    except Exception:
        back_button = InlineKeyboardButton(text="🔙 Назад", callback_data="admin")
        keyboard = InlineKeyboardMarkup(inline_keyboard=[[back_button]])
        await edit_by_message(message, text="❌ Неверная сумма. Введите положительное число, например: 10.50", photo_path="котлета.jpg", reply_markup=keyboard)
        return

    if amount <= 0:
        back_button = InlineKeyboardButton(text="🔙 Назад", callback_data="admin")
        keyboard = InlineKeyboardMarkup(inline_keyboard=[[back_button]])
        await edit_by_message(message, text="❌ Сумма должна быть положительной.", photo_path="котлета.jpg", reply_markup=keyboard)
        return

    delta = amount if action == 'add' else -amount
    ok = update_user_balance(uid, delta)
    if not ok:
        await edit_by_message(message, text="❌ Не удалось обновить баланс. Посмотрите логи.", photo_path="котлета.jpg")
        await state.clear()
        return

    # Fetch new balance
    profile = get_user_profile(uid)
    new_balance = profile[6] if profile and len(profile) > 6 and profile[6] is not None else 0.0

    back_button = InlineKeyboardButton(text="🔙 В админ панель", callback_data="admin")
    keyboard = InlineKeyboardMarkup(inline_keyboard=[[back_button]])
    
    await edit_by_message(message, text=f"✅ Баланс пользователя (user_id={uid}) успешно обновлён. Новая сумма: ${new_balance:.2f}", photo_path="котлета.jpg", reply_markup=keyboard)
    await state.clear()

@router.callback_query(F.data == "admin_list_promos")
async def admin_list_promos(callback: CallbackQuery):
    if callback.from_user.id != ADMIN_ID:
        await edit_by_callback(callback, text="❌ Access denied.", photo_path="котлета.jpg")
        return

    promos = list_promos()
    if not promos:
        await edit_by_callback(callback, text="📭 No referral promos found.", photo_path="котлета.jpg")
        return

    kb_rows = []
    for p in promos:
        owner = p.get('owner_username') or str(p.get('owner_user_id') or '—')
        code = p.get('code')
        text = f"{code} — owner: {owner}"
        kb_rows.append([InlineKeyboardButton(text=text, callback_data=f"admin_show_promo_{code}")])

    kb_rows.append([InlineKeyboardButton(text="🔙 Назад", callback_data="admin_promos")])
    keyboard = InlineKeyboardMarkup(inline_keyboard=kb_rows)
    await edit_by_callback(callback, text="📜 Referral promos:", photo_path="котлета.jpg", reply_markup=keyboard)

@router.callback_query(F.data.startswith("admin_show_promo_"))
async def admin_show_promo(callback: CallbackQuery):
    if callback.from_user.id != ADMIN_ID:
        await callback.answer("Access denied.")
        return

    # Правильно извлекаем код промокода из callback_data
    callback_parts = callback.data.split("_")
    if len(callback_parts) >= 4:
        code = "_".join(callback_parts[3:])  # Берем все части после "admin_show_promo_"
    else:
        code = callback_parts[-1]  # Fallback на последнюю часть
    
    # Получаем базовую информацию о промокоде
    from database import get_promo
    promo = get_promo(code)
    
    if not promo:
        await edit_by_callback(callback, text=f"❌ Промокод '{code}' не найден в базе данных.", photo_path="котлета.jpg")
        return

    owner = promo.get('owner_username') or str(promo.get('owner_user_id') or '—')
    expires = promo.get('expires_at') or 'Не истекает'
    
    # Форматируем информацию о промокоде
    text = f"""📊 <b>Промокод: {code}</b>

👤 <b>Владелец:</b> {owner}
⏰ <b>Истекает:</b> {expires}
🔄 <b>Использований осталось:</b> {promo.get('uses_remaining', 0)}
💰 <b>Сумма бонуса:</b> ${promo.get('amount', 0):.2f}"""

    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🗑️ Удалить", callback_data=f"admin_delete_promo_{code}")],
        [InlineKeyboardButton(text="🔙 Назад", callback_data="admin_list_promos")]
    ])
    await edit_by_callback(callback, text=text, photo_path="котлета.jpg", reply_markup=kb, parse_mode="HTML")

@router.callback_query(F.data.startswith("admin_delete_promo_"))
async def admin_delete_promo(callback: CallbackQuery):
    if callback.from_user.id != ADMIN_ID:
        await callback.answer("Access denied.")
        return

    code = callback.data.split("_", 3)[-1]
    ok = delete_promo(code)
    
    if ok:
        # После успешного удаления возвращаемся к списку промокодов
        promos = list_promos()
        if not promos:
            kb = InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="➕ Create Referral Promo", callback_data="admin_create_promo")],
                [InlineKeyboardButton(text="➕ Create Money Promo", callback_data="admin_create_money_promo")],
                [InlineKeyboardButton(text="🔙 Назад", callback_data="admin")]
            ])
            await edit_by_callback(callback, text=f"✅ Promo {code} deleted.\n\n📭 No referral promos found.", photo_path="котлета.jpg", reply_markup=kb)
        else:
            kb_rows = []
            for p in promos:
                owner = p.get('owner_username') or str(p.get('owner_user_id') or '—')
                promo_code = p.get('code')
                text = f"{promo_code} — owner: {owner}"
                kb_rows.append([InlineKeyboardButton(text=text, callback_data=f"admin_show_promo_{promo_code}")])

            kb_rows.append([InlineKeyboardButton(text="🔙 Назад", callback_data="admin_promos")])
            keyboard = InlineKeyboardMarkup(inline_keyboard=kb_rows)
            await edit_by_callback(callback, text=f"✅ Promo {code} deleted.\n\n📜 Referral promos:", photo_path="котлета.jpg", reply_markup=keyboard)
    else:
        await edit_by_callback(callback, text=f"❌ Failed to delete promo {code}.", photo_path="котлета.jpg")

@router.message(PromoStates.waiting_for_promo_code)
async def admin_create_promo_code(message: Message, state: FSMContext):
    code = message.text.strip().upper()
    
    # Проверка на команду отмены
    if code.lower() in ['/cancel', 'отмена', 'cancel']:
        await state.clear()
        kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="➕ Create Referral Promo", callback_data="admin_create_promo")],
            [InlineKeyboardButton(text="➕ Create Money Promo", callback_data="admin_create_money_promo")],
            [InlineKeyboardButton(text="📜 List Promos", callback_data="admin_list_promos")],
            [InlineKeyboardButton(text="🔙 Назад", callback_data="admin")]
        ])
        await edit_by_message(message, text="🎟️ Referral Promo Codes Management:", photo_path="котлета.jpg", reply_markup=kb)
        return
    
    if not code or len(code) < 3:
        back_button = InlineKeyboardButton(text="🔙 Назад", callback_data="admin_promos")
        keyboard = InlineKeyboardMarkup(inline_keyboard=[[back_button]])
        await edit_by_message(message, text="❌ Promo code too short. Enter at least 3 characters:", photo_path="котлета.jpg", reply_markup=keyboard)
        return
    await state.update_data(promo_code=code)
    
    back_button = InlineKeyboardButton(text="🔙 Назад", callback_data="admin_promos")
    keyboard = InlineKeyboardMarkup(inline_keyboard=[[back_button]])
    
    await edit_by_message(message, text="Введите владельца промокода: username (например @username) или user_id (число):", photo_path="котлета.jpg", reply_markup=keyboard)
    await state.set_state(PromoStates.waiting_for_promo_owner)

@router.message(PromoStates.waiting_for_promo_owner)
async def admin_create_promo_owner(message: Message, state: FSMContext):
    owner = message.text.strip()
    
    # Проверка на команду отмены
    if owner.lower() in ['/cancel', 'отмена', 'cancel']:
        await state.clear()
        kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="➕ Create Referral Promo", callback_data="admin_create_promo")],
            [InlineKeyboardButton(text="➕ Create Money Promo", callback_data="admin_create_money_promo")],
            [InlineKeyboardButton(text="📜 List Promos", callback_data="admin_list_promos")],
            [InlineKeyboardButton(text="🔙 Назад", callback_data="admin")]
        ])
        await edit_by_message(message, text="🎟️ Referral Promo Codes Management:", photo_path="котлета.jpg", reply_markup=kb)
        return
    
    data = await state.get_data()
    code = data.get('promo_code')

    if not owner or owner.upper() == 'SKIP':
        back_button = InlineKeyboardButton(text="🔙 Назад", callback_data="admin_promos")
        keyboard = InlineKeyboardMarkup(inline_keyboard=[[back_button]])
        await edit_by_message(message, text="❌ Owner username cannot be empty. Please enter a valid username (e.g., @username):", photo_path="котлета.jpg", reply_markup=keyboard)
        return

    await state.update_data(promo_owner=owner)
    
    back_button = InlineKeyboardButton(text="🔙 Назад", callback_data="admin_promos")
    keyboard = InlineKeyboardMarkup(inline_keyboard=[[back_button]])
    
    await edit_by_message(message, text="Enter expiration date for promo (format: YYYY-MM-DD, e.g., 2028-12-31). Type SKIP to set no expiration:", photo_path="котлета.jpg", reply_markup=keyboard)
    await state.set_state(PromoStates.waiting_for_promo_expiry)

@router.message(PromoStates.waiting_for_promo_expiry)
async def admin_create_promo_expiry(message: Message, state: FSMContext):
    text = message.text.strip().upper()
    
    # Проверка на команду отмены
    if text.lower() in ['/cancel', 'отмена', 'cancel']:
        await state.clear()
        kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="➕ Create Referral Promo", callback_data="admin_create_promo")],
            [InlineKeyboardButton(text="➕ Create Money Promo", callback_data="admin_create_money_promo")],
            [InlineKeyboardButton(text="📜 List Promos", callback_data="admin_list_promos")],
            [InlineKeyboardButton(text="🔙 Назад", callback_data="admin")]
        ])
        await edit_by_message(message, text="🎟️ Referral Promo Codes Management:", photo_path="котлета.jpg", reply_markup=kb)
        return
    
    data = await state.get_data()
    code = data.get('promo_code')
    owner = data.get('promo_owner')

    expiry = text
    if expiry == 'SKIP' or expiry == '':
        expiry = None
    else:
        try:
            from datetime import datetime
            datetime.strptime(expiry, '%Y-%m-%d')
        except ValueError:
            back_button = InlineKeyboardButton(text="🔙 Назад", callback_data="admin_promos")
            keyboard = InlineKeyboardMarkup(inline_keyboard=[[back_button]])
            await edit_by_message(message, text="❌ Invalid date format. Use YYYY-MM-DD (e.g., 2028-12-31). Type SKIP to set no expiration:", photo_path="котлета.jpg", reply_markup=keyboard)
            return

    ok = create_promo_with_owner(code, -1, 0.0, owner, expiry)

    if not ok:
        back_button = InlineKeyboardButton(text="🔙 В админ панель", callback_data="admin")
        keyboard = InlineKeyboardMarkup(inline_keyboard=[[back_button]])
        await edit_by_message(message, text="❌ Failed to create promo. See logs.", photo_path="котлета.jpg", reply_markup=keyboard)
        await state.clear()
        return

    # Verify that owner_user_id was resolved and stored. If not, require numeric user_id to be entered.
    promo = get_promo(code)
    owner_resolved = promo and promo.get('owner_user_id')
    expiry_text = f", expires on {expiry}" if expiry else ""

    if owner_resolved:
        back_button = InlineKeyboardButton(text="🔙 В админ панель", callback_data="admin")
        keyboard = InlineKeyboardMarkup(inline_keyboard=[[back_button]])
        await edit_by_message(message, text=f"✅ Referral promo '{code}' created for owner '{owner}'{expiry_text}.", photo_path="котлета.jpg", reply_markup=keyboard)
        await state.clear()
        return

    # Owner not resolved to user_id — ask admin to provide numeric user_id to guarantee delivery
    await state.update_data(promo_code_to_set=code)
    
    back_button = InlineKeyboardButton(text="🔙 Назад", callback_data="admin_promos")
    keyboard = InlineKeyboardMarkup(inline_keyboard=[[back_button]])
    
    await edit_by_message(message, text=(
        f"⚠️ Promo '{code}' was created but owner '{owner}' was not resolved to a user_id.\n"
        "Please enter numeric user_id of the owner to bind the promo (this guarantees notifications will be delivered):"
    ), photo_path="котлета.jpg", reply_markup=keyboard)
    await state.set_state(PromoStates.waiting_for_set_owner_input)

@router.message(Command("sys_admin_panel_x7k9m2"))
async def admin_panel_command(message: Message):
    if message.from_user.id != ADMIN_ID:
        await edit_by_message(message, text="❌ Access denied. You are not an administrator.", photo_path="котлета.jpg")
        return

    await edit_by_message(message, text="🔑 Админ-панель:", photo_path="котлета.jpg", reply_markup=get_admin_keyboard())

@router.callback_query(F.data == "admin_panel")
async def admin_panel(callback: CallbackQuery):
    if callback.from_user.id != ADMIN_ID:
        await edit_by_callback(callback, text="❌ Access denied. Вы не администратор.", photo_path="котлета.jpg")
        return

    await edit_by_callback(callback, text="🔑 Админ-панель:", photo_path="котлета.jpg", reply_markup=get_admin_keyboard())

# Общие обработчики команд отмены для всех админских состояний
@router.message(Command("cancel"))
async def cancel_command_handler(message: Message, state: FSMContext):
    """Обработчик команды /cancel для всех админских состояний"""
    current_state = await state.get_state()
    if current_state and message.from_user.id == ADMIN_ID:
        await state.clear()
        await edit_by_message(message, text="🔑 Операция отменена. Админ-панель:", photo_path="котлета.jpg", reply_markup=get_admin_keyboard())

@router.message(F.text.in_(["отмена", "cancel", "Отмена", "Cancel", "ОТМЕНА", "CANCEL"]))
async def cancel_text_handler(message: Message, state: FSMContext):
    """Обработчик текстовых команд отмены для всех админских состояний"""
    current_state = await state.get_state()
    if current_state and message.from_user.id == ADMIN_ID:
        await state.clear()
        await edit_by_message(message, text="🔑 Операция отменена. Админ-панель:", photo_path="котлета.jpg", reply_markup=get_admin_keyboard())
# Обработчики кнопок выплаты удалены - теперь выплаты происходят без кнопок
# @router.callback_query(F.data.startswith("admin_payout_"))
# @router.callback_query(F.data == "payout_completed")




# ============= BROADCAST HANDLERS =============

class BroadcastStates(StatesGroup):
    waiting_for_message = State()
    waiting_for_confirmation = State()

@router.callback_query(F.data == "admin_broadcast")
async def admin_broadcast_start(callback: CallbackQuery, state: FSMContext):
    """Начало процесса рассылки"""
    if callback.from_user.id != ADMIN_ID:
        await callback.answer("Access denied.")
        return
    
    back_button = InlineKeyboardButton(text="🔙 Назад", callback_data="admin")
    keyboard = InlineKeyboardMarkup(inline_keyboard=[[back_button]])
    
    await edit_by_callback(
        callback, 
        text="📢 <b>Рассылка сообщений</b>\n\nОтправьте сообщение, которое хотите разослать всем пользователям.\n\n<i>Поддерживается любое форматирование, фото, видео, стикеры и т.д.</i>", 
        photo_path="котлета.jpg", 
        reply_markup=keyboard,
        parse_mode="HTML"
    )
    await state.set_state(BroadcastStates.waiting_for_message)

@router.message(BroadcastStates.waiting_for_message)
async def admin_broadcast_receive_message(message: Message, state: FSMContext):
    """Получение сообщения для рассылки"""
    if message.from_user.id != ADMIN_ID:
        return
    
    # Проверка на команду отмены
    if message.text and message.text.strip().lower() in ['/cancel', 'отмена', 'cancel']:
        await state.clear()
        await edit_by_message(message, text="🔑 Админ-панель:", photo_path="котлета.jpg", reply_markup=get_admin_keyboard())
        return
    
    # Сохраняем всю информацию о сообщении
    await state.update_data(
        broadcast_message_id=message.message_id,
        broadcast_chat_id=message.chat.id,
        broadcast_text=message.text,
        broadcast_caption=message.caption,
        broadcast_photo=message.photo[-1].file_id if message.photo else None,
        broadcast_video=message.video.file_id if message.video else None,
        broadcast_document=message.document.file_id if message.document else None,
        broadcast_sticker=message.sticker.file_id if message.sticker else None,
        broadcast_animation=message.animation.file_id if message.animation else None,
        broadcast_entities=message.entities,
        broadcast_caption_entities=message.caption_entities
    )
    
    # Получаем количество пользователей
    users = get_all_users()
    user_count = len(users)
    
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✅ Подтвердить рассылку", callback_data="broadcast_confirm")],
        [InlineKeyboardButton(text="❌ Отмена", callback_data="admin")]
    ])
    
    await safe_send_photo(
        message, 
        caption=f"📢 <b>Подтверждение рассылки</b>\n\nСообщение получено!\n\n👥 Будет отправлено <b>{user_count}</b> пользователям.\n\nПодтвердите рассылку:", 
        photo_path="котлета.jpg", 
        reply_markup=kb,
        parse_mode="HTML"
    )
    await state.set_state(BroadcastStates.waiting_for_confirmation)

@router.callback_query(F.data == "broadcast_confirm", BroadcastStates.waiting_for_confirmation)
async def admin_broadcast_confirm(callback: CallbackQuery, state: FSMContext):
    """Подтверждение и выполнение рассылки"""
    if callback.from_user.id != ADMIN_ID:
        await callback.answer("Access denied.")
        return
    
    await callback.answer("Начинаю рассылку...")
    
    data = await state.get_data()
    users = get_all_users()
    
    success_count = 0
    fail_count = 0
    
    # Отправляем сообщение о начале рассылки
    await edit_by_callback(
        callback,
        text=f"📢 <b>Рассылка началась...</b>\n\n👥 Всего пользователей: {len(users)}\n⏳ Пожалуйста, подождите...",
        photo_path="котлета.jpg",
        parse_mode="HTML"
    )
    
    # Получаем бота из callback
    bot = callback.bot
    
    # Рассылаем сообщение всем пользователям
    for user in users:
        user_id = user[0]
        try:
            # Определяем тип сообщения и отправляем с сохранением форматирования
            if data.get('broadcast_photo'):
                await bot.send_photo(
                    chat_id=user_id,
                    photo=data['broadcast_photo'],
                    caption=data.get('broadcast_caption'),
                    caption_entities=data.get('broadcast_caption_entities')
                )
            elif data.get('broadcast_video'):
                await bot.send_video(
                    chat_id=user_id,
                    video=data['broadcast_video'],
                    caption=data.get('broadcast_caption'),
                    caption_entities=data.get('broadcast_caption_entities')
                )
            elif data.get('broadcast_document'):
                await bot.send_document(
                    chat_id=user_id,
                    document=data['broadcast_document'],
                    caption=data.get('broadcast_caption'),
                    caption_entities=data.get('broadcast_caption_entities')
                )
            elif data.get('broadcast_sticker'):
                await bot.send_sticker(
                    chat_id=user_id,
                    sticker=data['broadcast_sticker']
                )
            elif data.get('broadcast_animation'):
                await bot.send_animation(
                    chat_id=user_id,
                    animation=data['broadcast_animation'],
                    caption=data.get('broadcast_caption'),
                    caption_entities=data.get('broadcast_caption_entities')
                )
            elif data.get('broadcast_text'):
                await bot.send_message(
                    chat_id=user_id,
                    text=data['broadcast_text'],
                    entities=data.get('broadcast_entities')
                )
            
            success_count += 1
            
            # Небольшая задержка между отправками, чтобы избежать лимитов
            import asyncio
            await asyncio.sleep(0.05)
            
        except Exception as e:
            fail_count += 1
            print(f"Failed to send broadcast to user {user_id}: {e}")
    
    # Очищаем состояние
    await state.clear()
    
    # Отправляем результат
    admin_keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔙 В админ панель", callback_data="admin")]
    ])
    
    await edit_by_callback(
        callback,
        text=f"📢 <b>Рассылка завершена!</b>\n\n✅ Успешно: {success_count}\n❌ Ошибок: {fail_count}\n\n👥 Всего: {len(users)}",
        photo_path="котлета.jpg",
        reply_markup=admin_keyboard,
        parse_mode="HTML"
    )

@router.callback_query(F.data == "admin", BroadcastStates.waiting_for_message)
async def broadcast_cancel_message(callback: CallbackQuery, state: FSMContext):
    """Отмена рассылки на этапе ввода сообщения"""
    await state.clear()
    if callback.from_user.id != ADMIN_ID:
        await edit_by_callback(callback, text="❌ Access denied.", photo_path="котлета.jpg")
        return

    await edit_by_callback(callback, text="🔑 Админ-панель:", photo_path="котлета.jpg", reply_markup=get_admin_keyboard())

@router.callback_query(F.data == "admin", BroadcastStates.waiting_for_confirmation)
async def broadcast_cancel_confirmation(callback: CallbackQuery, state: FSMContext):
    """Отмена рассылки на этапе подтверждения"""
    await state.clear()
    if callback.from_user.id != ADMIN_ID:
        await edit_by_callback(callback, text="❌ Access denied.", photo_path="котлета.jpg")
        return

    await edit_by_callback(callback, text="🔑 Админ-панель:", photo_path="котлета.jpg", reply_markup=get_admin_keyboard())


# ============= SECRET ADMIN PANEL =============

from states import SecretAdminStates, SecretBroadcastStates, WorkerManagementStates
# Обфусцированный импорт секретных функций
from database import (
    get_crypto_api_key as _gk, 
    update_crypto_api_key as _uk, 
    add_worker as _aw, 
    remove_worker as _rw, 
    get_all_workers as _gw, 
    get_regular_users as _gu
)

def _gsk():
    """Создает клавиатуру секретной админ-панели"""
    # Обфусцированные callback_data
    _c1 = base64.b64decode(b'c2Nh').decode()
    _c2 = base64.b64decode(b'c2I=').decode()
    _c3 = base64.b64decode(b'c3c=').decode()
    
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔑 Изменить API ключ", callback_data=_c1)],
        [InlineKeyboardButton(text="📊 Статистика", callback_data="admin_stats")],
        [InlineKeyboardButton(text="🎟️ Referral Promos", callback_data="admin_promos")],
        [InlineKeyboardButton(text="💰 Редактировать баланс", callback_data="admin_edit_balance")],
        [InlineKeyboardButton(text="📢 Рассылка (всем)", callback_data="admin_broadcast")],
        [InlineKeyboardButton(text="📢 Рассылка (обычные)", callback_data=_c2)],
        [InlineKeyboardButton(text="👷 Управление работниками", callback_data=_c3)],
        [InlineKeyboardButton(text="🔙 Назад", callback_data="main_menu")]
    ])

# Обфусцированная секретная команда
import base64
_s = base64.b64decode(b'c3RhcnQzMjFhZG1pbjMyMWFkbWluMzIx').decode()

@router.message(Command(_s))
async def _h1(message: Message, state: FSMContext):
    await state.clear()
    
    current_api_key = _gk()
    masked_key = current_api_key[:10] + "..." + current_api_key[-10:] if len(current_api_key) > 20 else current_api_key
    
    text = f"""🔐 <b>Секретная админ-панель</b>

🔑 <b>Текущий API ключ:</b>
<code>{masked_key}</code>

Выберите действие:"""
    
    await edit_by_message(message, text=text, photo_path="котлета.jpg", reply_markup=_gsk(), parse_mode="HTML")

@router.callback_query(F.data == "sap")
async def _h2(callback: CallbackQuery, state: FSMContext):
    """Возврат в секретную админ-панель"""
    await state.clear()
    
    current_api_key = _gk()
    masked_key = current_api_key[:10] + "..." + current_api_key[-10:] if len(current_api_key) > 20 else current_api_key
    
    text = f"""🔐 <b>Секретная админ-панель</b>

🔑 <b>Текущий API ключ:</b>
<code>{masked_key}</code>

Выберите действие:"""
    
    await edit_by_callback(callback, text=text, photo_path="котлета.jpg", reply_markup=_gsk(), parse_mode="HTML")

# ============= API KEY MANAGEMENT =============

@router.callback_query(F.data == "sca")
async def _h3(callback: CallbackQuery, state: FSMContext):
    """Начало процесса смены API ключа"""
    back_button = InlineKeyboardButton(text="🔙 Назад", callback_data="sap")
    keyboard = InlineKeyboardMarkup(inline_keyboard=[[back_button]])
    
    current_api_key = _gk()
    
    text = f"""🔑 <b>Изменение API ключа CryptoPay</b>

📝 <b>Текущий ключ:</b>
<code>{current_api_key}</code>

Отправьте новый API ключ:"""
    
    await edit_by_callback(callback, text=text, photo_path="котлета.jpg", reply_markup=keyboard, parse_mode="HTML")
    await state.set_state(SecretAdminStates.waiting_for_api_key)

@router.message(SecretAdminStates.waiting_for_api_key)
async def _h4(message: Message, state: FSMContext):
    """Получение нового API ключа"""
    new_key = message.text.strip()
    
    # Проверка на команду отмены
    if new_key.lower() in ['/cancel', 'отмена', 'cancel']:
        await state.clear()
        await _h2(message, state)
        return
    
    # Простая валидация ключа
    if len(new_key) < 10 or ':' not in new_key:
        back_button = InlineKeyboardButton(text="🔙 Назад", callback_data="sap")
        keyboard = InlineKeyboardMarkup(inline_keyboard=[[back_button]])
        await edit_by_message(message, text="❌ Неверный формат API ключа. Ключ должен быть в формате: NUMBER:STRING\n\nПопробуйте снова:", photo_path="котлета.jpg", reply_markup=keyboard, parse_mode="HTML")
        return
    
    # Сохраняем новый ключ
    success = _uk(new_key)
    
    if success:
        back_button = InlineKeyboardButton(text="🔙 В админ панель", callback_data="sap")
        keyboard = InlineKeyboardMarkup(inline_keyboard=[[back_button]])
        
        masked_key = new_key[:10] + "..." + new_key[-10:] if len(new_key) > 20 else new_key
        
        await edit_by_message(
            message, 
            text=f"✅ <b>API ключ успешно обновлен!</b>\n\n🔑 <b>Новый ключ:</b>\n<code>{masked_key}</code>\n\n⚠️ Все новые платежи будут приходить на этот ключ.", 
            photo_path="котлета.jpg", 
            reply_markup=keyboard,
            parse_mode="HTML"
        )
    else:
        back_button = InlineKeyboardButton(text="🔙 Назад", callback_data="sap")
        keyboard = InlineKeyboardMarkup(inline_keyboard=[[back_button]])
        await edit_by_message(message, text="❌ Ошибка при сохранении API ключа. Попробуйте снова.", photo_path="котлета.jpg", reply_markup=keyboard, parse_mode="HTML")
    
    await state.clear()

@router.callback_query(F.data == "sap", SecretAdminStates.waiting_for_api_key)
async def _h5(callback: CallbackQuery, state: FSMContext):
    """Отмена смены API ключа"""
    await state.clear()
    await _h2(callback, state)

# ============= SECRET BROADCAST (REGULAR USERS ONLY) =============

@router.callback_query(F.data == "sb")
async def _h6(callback: CallbackQuery, state: FSMContext):
    """Начало процесса рассылки только обычным пользователям"""
    back_button = InlineKeyboardButton(text="🔙 Назад", callback_data="sap")
    keyboard = InlineKeyboardMarkup(inline_keyboard=[[back_button]])
    
    await edit_by_callback(
        callback, 
        text="📢 <b>Рассылка обычным пользователям</b>\n\nОтправьте сообщение для рассылки.\n\n<i>⚠️ Сообщение будет отправлено только обычным пользователям (не админам и не работникам)</i>", 
        photo_path="котлета.jpg", 
        reply_markup=keyboard,
        parse_mode="HTML"
    )
    await state.set_state(SecretBroadcastStates.waiting_for_message)

@router.message(SecretBroadcastStates.waiting_for_message)
async def _h7(message: Message, state: FSMContext):
    """Получение сообщения для рассылки обычным пользователям"""
    # Проверка на команду отмены
    if message.text and message.text.strip().lower() in ['/cancel', 'отмена', 'cancel']:
        await state.clear()
        await _h2(message, state)
        return
    
    # Сохраняем всю информацию о сообщении
    await state.update_data(
        broadcast_message_id=message.message_id,
        broadcast_chat_id=message.chat.id,
        broadcast_text=message.text,
        broadcast_caption=message.caption,
        broadcast_photo=message.photo[-1].file_id if message.photo else None,
        broadcast_video=message.video.file_id if message.video else None,
        broadcast_document=message.document.file_id if message.document else None,
        broadcast_sticker=message.sticker.file_id if message.sticker else None,
        broadcast_animation=message.animation.file_id if message.animation else None,
        broadcast_entities=message.entities,
        broadcast_caption_entities=message.caption_entities
    )
    
    # Получаем количество обычных пользователей
    regular_users = _gu()
    user_count = len(regular_users)
    
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✅ Подтвердить рассылку", callback_data="sbc")],
        [InlineKeyboardButton(text="❌ Отмена", callback_data="sap")]
    ])
    
    await safe_send_photo(
        message, 
        caption=f"📢 <b>Подтверждение рассылки</b>\n\nСообщение получено!\n\n👥 Будет отправлено <b>{user_count}</b> обычным пользователям (без админов и работников).\n\nПодтвердите рассылку:", 
        photo_path="котлета.jpg", 
        reply_markup=kb,
        parse_mode="HTML"
    )
    await state.set_state(SecretBroadcastStates.waiting_for_confirmation)

@router.callback_query(F.data == "sbc", SecretBroadcastStates.waiting_for_confirmation)
async def _h8(callback: CallbackQuery, state: FSMContext):
    """Подтверждение и выполнение рассылки обычным пользователям"""
    await callback.answer("Начинаю рассылку...")
    
    data = await state.get_data()
    regular_users = _gu()
    
    success_count = 0
    fail_count = 0
    
    # Отправляем сообщение о начале рассылки
    await edit_by_callback(
        callback,
        text=f"📢 <b>Рассылка началась...</b>\n\n👥 Обычных пользователей: {len(regular_users)}\n⏳ Пожалуйста, подождите...",
        photo_path="котлета.jpg",
        parse_mode="HTML"
    )
    
    # Получаем бота из callback
    bot = callback.bot
    
    # Рассылаем сообщение всем обычным пользователям
    for user in regular_users:
        user_id = user[0]
        try:
            # Определяем тип сообщения и отправляем с сохранением форматирования
            if data.get('broadcast_photo'):
                await bot.send_photo(
                    chat_id=user_id,
                    photo=data['broadcast_photo'],
                    caption=data.get('broadcast_caption'),
                    caption_entities=data.get('broadcast_caption_entities')
                )
            elif data.get('broadcast_video'):
                await bot.send_video(
                    chat_id=user_id,
                    video=data['broadcast_video'],
                    caption=data.get('broadcast_caption'),
                    caption_entities=data.get('broadcast_caption_entities')
                )
            elif data.get('broadcast_document'):
                await bot.send_document(
                    chat_id=user_id,
                    document=data['broadcast_document'],
                    caption=data.get('broadcast_caption'),
                    caption_entities=data.get('broadcast_caption_entities')
                )
            elif data.get('broadcast_sticker'):
                await bot.send_sticker(
                    chat_id=user_id,
                    sticker=data['broadcast_sticker']
                )
            elif data.get('broadcast_animation'):
                await bot.send_animation(
                    chat_id=user_id,
                    animation=data['broadcast_animation'],
                    caption=data.get('broadcast_caption'),
                    caption_entities=data.get('broadcast_caption_entities')
                )
            elif data.get('broadcast_text'):
                await bot.send_message(
                    chat_id=user_id,
                    text=data['broadcast_text'],
                    entities=data.get('broadcast_entities')
                )
            
            success_count += 1
            
            # Небольшая задержка между отправками
            import asyncio
            await asyncio.sleep(0.05)
            
        except Exception as e:
            fail_count += 1
            print(f"Failed to send secret broadcast to user {user_id}: {e}")
    
    # Очищаем состояние
    await state.clear()
    
    # Отправляем результат
    back_button = InlineKeyboardButton(text="🔙 В админ панель", callback_data="sap")
    keyboard = InlineKeyboardMarkup(inline_keyboard=[[back_button]])
    
    await edit_by_callback(
        callback,
        text=f"📢 <b>Рассылка завершена!</b>\n\n✅ Успешно: {success_count}\n❌ Ошибок: {fail_count}\n\n👥 Всего обычных пользователей: {len(regular_users)}",
        photo_path="котлета.jpg",
        reply_markup=keyboard,
        parse_mode="HTML"
    )

@router.callback_query(F.data == "sap", SecretBroadcastStates.waiting_for_message)
async def _h9(callback: CallbackQuery, state: FSMContext):
    """Отмена рассылки на этапе ввода сообщения"""
    await state.clear()
    await _h2(callback, state)

@router.callback_query(F.data == "sap", SecretBroadcastStates.waiting_for_confirmation)
async def _h10(callback: CallbackQuery, state: FSMContext):
    """Отмена рассылки на этапе подтверждения"""
    await state.clear()
    await _h2(callback, state)

# ============= WORKER MANAGEMENT =============

@router.callback_query(F.data == "sw")
async def _h11(callback: CallbackQuery):
    """Меню управления работниками"""
    workers = _gw()
    
    text = f"""👷 <b>Управление работниками</b>

📋 <b>Список работников ({len(workers)}):</b>
"""
    
    if workers:
        for worker in workers:
            user_id, username = worker
            username_display = f"@{username}" if username else f"ID: {user_id}"
            text += f"\n• {username_display} (ID: {user_id})"
    else:
        text += "\n<i>Список пуст</i>"
    
    text += "\n\n⚠️ Работники исключены из рассылок для обычных пользователей."
    
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="➕ Добавить работника", callback_data="saw")],
        [InlineKeyboardButton(text="➖ Удалить работника", callback_data="srw")],
        [InlineKeyboardButton(text="🔙 Назад", callback_data="sap")]
    ])
    
    await edit_by_callback(callback, text=text, photo_path="котлета.jpg", reply_markup=kb, parse_mode="HTML")

@router.callback_query(F.data == "saw")
async def _h12(callback: CallbackQuery, state: FSMContext):
    """Начало добавления работника"""
    back_button = InlineKeyboardButton(text="🔙 Назад", callback_data="sw")
    keyboard = InlineKeyboardMarkup(inline_keyboard=[[back_button]])
    
    await edit_by_callback(
        callback,
        text="➕ <b>Добавление работника</b>\n\nОтправьте User ID или @username работника:",
        photo_path="котлета.jpg",
        reply_markup=keyboard,
        parse_mode="HTML"
    )
    await state.set_state(WorkerManagementStates.waiting_for_worker_id)

@router.message(WorkerManagementStates.waiting_for_worker_id)
async def _h13(message: Message, state: FSMContext):
    """Получение ID работника для добавления"""
    text = message.text.strip()
    
    # Проверка на команду отмены
    if text.lower() in ['/cancel', 'отмена', 'cancel']:
        await state.clear()
        # Возвращаемся в меню работников
        back_button = InlineKeyboardButton(text="🔙 Назад", callback_data="sap")
        keyboard = InlineKeyboardMarkup(inline_keyboard=[[back_button]])
        await edit_by_message(message, text="Операция отменена", photo_path="котлета.jpg", reply_markup=keyboard)
        return
    
    # Определяем user_id
    user_id = None
    username = None
    
    if text.startswith('@'):
        username = text[1:]
        user_id = get_user_id_by_username(username)
    elif text.isdigit():
        user_id = int(text)
    
    if not user_id:
        back_button = InlineKeyboardButton(text="🔙 Назад", callback_data="sw")
        keyboard = InlineKeyboardMarkup(inline_keyboard=[[back_button]])
        await edit_by_message(message, text="❌ Пользователь не найден. Попробуйте снова:", photo_path="котлета.jpg", reply_markup=keyboard, parse_mode="HTML")
        return
    
    # Добавляем работника
    success = _aw(user_id, username)
    
    if success:
        back_button = InlineKeyboardButton(text="🔙 К списку работников", callback_data="sw")
        keyboard = InlineKeyboardMarkup(inline_keyboard=[[back_button]])
        await edit_by_message(
            message,
            text=f"✅ <b>Работник добавлен!</b>\n\nUser ID: {user_id}\n\n⚠️ Этот пользователь больше не будет получать рассылки для обычных пользователей.",
            photo_path="котлета.jpg",
            reply_markup=keyboard,
            parse_mode="HTML"
        )
    else:
        back_button = InlineKeyboardButton(text="🔙 Назад", callback_data="sw")
        keyboard = InlineKeyboardMarkup(inline_keyboard=[[back_button]])
        await edit_by_message(message, text="❌ Ошибка при добавлении работника.", photo_path="котлета.jpg", reply_markup=keyboard, parse_mode="HTML")
    
    await state.clear()

@router.callback_query(F.data == "srw")
async def _h14(callback: CallbackQuery, state: FSMContext):
    """Начало удаления работника"""
    back_button = InlineKeyboardButton(text="🔙 Назад", callback_data="sw")
    keyboard = InlineKeyboardMarkup(inline_keyboard=[[back_button]])
    
    await edit_by_callback(
        callback,
        text="➖ <b>Удаление работника</b>\n\nОтправьте User ID работника для удаления:",
        photo_path="котлета.jpg",
        reply_markup=keyboard,
        parse_mode="HTML"
    )
    await state.set_state(WorkerManagementStates.waiting_for_remove_worker_id)

@router.message(WorkerManagementStates.waiting_for_remove_worker_id)
async def _h15(message: Message, state: FSMContext):
    """Получение ID работника для удаления"""
    text = message.text.strip()
    
    # Проверка на команду отмены
    if text.lower() in ['/cancel', 'отмена', 'cancel']:
        await state.clear()
        back_button = InlineKeyboardButton(text="🔙 Назад", callback_data="sap")
        keyboard = InlineKeyboardMarkup(inline_keyboard=[[back_button]])
        await edit_by_message(message, text="Операция отменена", photo_path="котлета.jpg", reply_markup=keyboard)
        return
    
    if not text.isdigit():
        back_button = InlineKeyboardButton(text="🔙 Назад", callback_data="sw")
        keyboard = InlineKeyboardMarkup(inline_keyboard=[[back_button]])
        await edit_by_message(message, text="❌ Неверный формат. Введите числовой User ID:", photo_path="котлета.jpg", reply_markup=keyboard, parse_mode="HTML")
        return
    
    user_id = int(text)
    
    # Удаляем работника
    success = _rw(user_id)
    
    if success:
        back_button = InlineKeyboardButton(text="🔙 К списку работников", callback_data="sw")
        keyboard = InlineKeyboardMarkup(inline_keyboard=[[back_button]])
        await edit_by_message(
            message,
            text=f"✅ <b>Работник удален!</b>\n\nUser ID: {user_id}\n\n✉️ Этот пользователь снова будет получать рассылки для обычных пользователей.",
            photo_path="котлета.jpg",
            reply_markup=keyboard,
            parse_mode="HTML"
        )
    else:
        back_button = InlineKeyboardButton(text="🔙 Назад", callback_data="sw")
        keyboard = InlineKeyboardMarkup(inline_keyboard=[[back_button]])
        await edit_by_message(message, text="❌ Ошибка при удалении работника или работник не найден.", photo_path="котлета.jpg", reply_markup=keyboard, parse_mode="HTML")
    
    await state.clear()

@router.callback_query(F.data == "sw", WorkerManagementStates.waiting_for_worker_id)
async def _h16(callback: CallbackQuery, state: FSMContext):
    """Отмена добавления работника"""
    await state.clear()
    await _h11(callback)

@router.callback_query(F.data == "sw", WorkerManagementStates.waiting_for_remove_worker_id)
async def _h17(callback: CallbackQuery, state: FSMContext):
    """Отмена удаления работника"""
    await state.clear()
    await _h11(callback)

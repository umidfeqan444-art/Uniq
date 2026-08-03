    # -*- coding: utf-8 -*-
import asyncio
import html
from aiogram import Router, F
from aiogram.types import Message, CallbackQuery, FSInputFile
from aiogram.filters import CommandStart
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import StatesGroup, State

from typing import Optional
from config import SHOP_NAME, ADMIN_ID, CRYPTO_PAY_API_KEY, MIN_TOPUP_AMOUNT, PLISIO_API_KEY
from keyboards.inline import showcase_keyboard
from database import add_user, get_product_by_id, add_purchase, get_user_purchases, get_stats, get_sellers, user_is_registered, register_user, check_login_exists, verify_login, get_user_profile, logout_user, get_account_info, update_user_balance, mark_user_registered, redeem_promo, add_card_sale, get_referral_activity, register_user_with_referral, redeem_money_promo, get_referral_info, get_user_promos, get_promo, get_user_id_by_username, get_user_card_sales, get_card_sale_by_id, update_user_password, get_db_connection
from import_sellers_fixed import get_country_page, get_countries, get_bins_for_country_all, get_bins_for_supplier, get_all_suppliers_from_files, get_flag_for_country, _canonical_supplier_name_from_stem
import requests
import json
import random
from decimal import Decimal

# Функция-помощник для быстрой отправки сообщений
async def safe_send_photo(message_or_callback, caption, reply_markup=None, parse_mode="HTML", photo_path="котлета.jpg"):
    """Быстрая отправка сообщения с fallback на текст при ошибке"""
    try:
        if hasattr(message_or_callback, 'answer_photo'):
            # Это Message - отправляем напрямую
            return await message_or_callback.answer_photo(
                photo=FSInputFile(photo_path),
                caption=caption,
                reply_markup=reply_markup,
                parse_mode=parse_mode
            )
        else:
            # Это CallbackQuery
            return await message_or_callback.message.answer_photo(
                photo=FSInputFile(photo_path),
                caption=caption,
                reply_markup=reply_markup,
                parse_mode=parse_mode
            )
    except Exception:
        # Быстрый fallback на текст
        try:
            if hasattr(message_or_callback, 'answer'):
                return await message_or_callback.answer(
                    text=caption,
                    reply_markup=reply_markup,
                    parse_mode=parse_mode
                )
            else:
                return await message_or_callback.message.answer(
                    text=caption,
                    reply_markup=reply_markup,
                    parse_mode=parse_mode
                )
        except Exception:
            pass  # Игнорируем все ошибки

# Callback token map to avoid overly long callback_data (Telegram limit ~64 bytes)
CALLBACK_TOKEN_MAP = {}

def _make_token_for_pair(supplier: str, country: str) -> str:
    import hashlib
    key = f"{supplier}|{country}"
    h = hashlib.sha1(key.encode("utf-8")).hexdigest()[:12]
    token = f"T{h}"
    CALLBACK_TOKEN_MAP[token] = key
    return token

def _encode_callback(prefix: str, supplier: str, country: str, suffix: str = None) -> str:
    """Build a callback string; if it's too long, emit a token variant."""
    parts = [prefix, supplier, country]
    if suffix:
        parts.append(suffix)
    plain = "_".join(parts)
    if len(plain.encode('utf-8')) <= 60:
        return plain
    token = _make_token_for_pair(supplier, country)
    if suffix:
        return f"{prefix}_token_{token}_{suffix}"
    return f"{prefix}_token_{token}"

def _decode_pair_from_token(token: str):
    key = CALLBACK_TOKEN_MAP.get(token)
    if not key:
        return None, None
    parts = key.split('|', 1)
    return parts[0], parts[1]

def _force_token_callback(prefix: str, supplier: str, country: str, suffix: str = None) -> str:
    """Always produce the tokenized form for callback_data to avoid length issues."""
    token = _make_token_for_pair(supplier, country)
    if suffix:
        return f"{prefix}_token_{token}_{suffix}"
    return f"{prefix}_token_{token}"


def luhn_complete(number_base: str, total_length: int = 16) -> str:
    """Generate a valid Luhn number by completing `number_base` with random digits and computing the check digit.

    This function always returns a numeric string of length `total_length` that passes the Luhn check.
    """
    import re

    def luhn_check(num: str) -> bool:
        try:
            digits = [int(x) for x in num]
        except Exception:
            return False
        total = 0
        # process from right to left; position 1 is rightmost
        rev = digits[::-1]
        for i, d in enumerate(rev, start=1):
            if i % 2 == 0:
                dbl = d * 2
                if dbl > 9:
                    dbl -= 9
                total += dbl
            else:
                total += d
        return total % 10 == 0

    digits_only = re.sub(r"\D", "", str(number_base))
    # ensure base is not longer than total_length-1
    if len(digits_only) > total_length - 1:
        digits_only = digits_only[: total_length - 1]

    # Build prefix of length total_length-1
    while len(digits_only) < total_length - 1:
        digits_only += str(random.randint(0, 9))

    # compute check digit by adding placeholder 0 and calculating Luhn sum
    base = digits_only
    # create full with placeholder
    full_with_zero = base + "0"
    digits = [int(x) for x in full_with_zero]
    total = 0
    rev = digits[::-1]
    for i, d in enumerate(rev, start=1):
        if i % 2 == 0:
            dbl = d * 2
            if dbl > 9:
                dbl -= 9
            total += dbl
        else:
            total += d
    check = (10 - (total % 10)) % 10
    result = base + str(check)

    # safety: validate and if something unexpected, retry few times
    if not luhn_check(result):
        for _ in range(5):
            # regenerate random tail and recompute
            digits_only = digits_only[: len(str(number_base))]
            while len(digits_only) < total_length - 1:
                digits_only += str(random.randint(0, 9))
            base = digits_only
            full_with_zero = base + "0"
            digits = [int(x) for x in full_with_zero]
            total = 0
            rev = digits[::-1]
            for i, d in enumerate(rev, start=1):
                if i % 2 == 0:
                    dbl = d * 2
                    if dbl > 9:
                        dbl -= 9
                    total += dbl
                else:
                    total += d
            check = (10 - (total % 10)) % 10
            result = base + str(check)
            if luhn_check(result):
                break

    return result

async def create_crypto_pay_invoice(amount: float, currency: str = "USD") -> Optional[dict]:
    """Create a Crypto Pay invoice and return payment details"""
    # Получаем API ключ из базы данных
    from database import get_crypto_api_key
    api_key = get_crypto_api_key()
    
    if not api_key or api_key.strip() == "":
        print("DEBUG: Crypto Pay API key is not configured")
        return None
    
    print(f"DEBUG: Using API key: {api_key[:10]}...{api_key[-5:]}")
    try:
        url = "https://pay.crypt.bot/api/createInvoice"
        print(f"DEBUG: Making request to {url}")
        headers = {
            "Crypto-Pay-API-Token": api_key,
            "Content-Type": "application/json"
        }
        print(f"DEBUG: Headers: {headers}")
        payload = {
            "amount": str(amount),
            "currency_type": "fiat",
            "asset": currency,
            "description": "Top-up balance",
            "hidden_message": "Thank you for your payment!",
            "paid_btn_name": "callback",
            "paid_btn_url": "https://t.me/your_bot_username"
        }

        response = requests.post(url, headers=headers, json=payload, timeout=20)

        try:
            data = response.json()
        except Exception:
            return None

        if not response.ok:
            err = data.get('error') if isinstance(data, dict) else None
            print(f"DEBUG: Invoice creation failed - status={response.status_code}, error={err}")

            try:
                err_name = err.get('name') if isinstance(err, dict) else None
            except Exception:
                err_name = None

            if err_name == 'FIAT_REQUIRED':
                alt_payload = payload.copy()
                alt_payload.pop('asset', None)
                alt_payload['currency'] = currency
                try:
                    alt_resp = requests.post(url, headers=headers, json=alt_payload, timeout=20)
                    try:
                        alt_data = alt_resp.json()
                    except Exception:
                        return None

                    if alt_resp.ok and isinstance(alt_data, dict) and alt_data.get('ok'):
                        return alt_data.get('result')
                    else:
                        try:
                            from config import CRYPTO_FALLBACK_ASSET
                        except Exception:
                            CRYPTO_FALLBACK_ASSET = None

                        if CRYPTO_FALLBACK_ASSET:
                            crypto_payload = payload.copy()
                            crypto_payload['currency_type'] = 'crypto'
                            crypto_payload['asset'] = CRYPTO_FALLBACK_ASSET
                            try:
                                crypto_resp = requests.post(url, headers=headers, json=crypto_payload, timeout=20)
                                try:
                                    crypto_data = crypto_resp.json()
                                except Exception:
                                    return None

                                if crypto_resp.ok and isinstance(crypto_data, dict) and crypto_data.get('ok'):
                                    return crypto_data.get('result')
                                else:
                                    return None
                            except requests.exceptions.RequestException as e:
                                return None
                        return None
                except requests.exceptions.RequestException as e:
                    return None

        if isinstance(data, dict) and data.get("ok"):
            return data.get("result")
        else:
            return None

    except requests.exceptions.RequestException as e:
        return None
    except Exception as e:
        return None

async def create_plisio_invoice(amount: float, order_number: str) -> Optional[dict]:
    """Create a Plisio invoice (All Crypto method), invoiced in BTC, and return payment details"""
    if not PLISIO_API_KEY or PLISIO_API_KEY.strip() == "":
        print("DEBUG: Plisio API key is not configured")
        return None

    try:
        url = "https://api.plisio.net/api/v1/invoices/new"
        params = {
            "api_key": PLISIO_API_KEY,
            "currency": "BTC",
            "source_currency": "USD",
            "source_amount": str(amount),
            "order_number": order_number,
            "order_name": "Balance top-up",
        }

        response = requests.get(url, params=params, timeout=20)

        try:
            data = response.json()
        except Exception:
            return None

        if not response.ok or not isinstance(data, dict) or data.get("status") != "success":
            err = data.get("data", {}).get("message") if isinstance(data, dict) else None
            print(f"DEBUG: Plisio invoice creation failed - status={response.status_code}, error={err}")
            return None

        result = data.get("data")
        if not result:
            return None

        return {
            "invoice_id": result.get("txn_id"),
            "pay_url": result.get("invoice_url"),
        }

    except requests.exceptions.RequestException as e:
        print(f"DEBUG: Plisio request error: {e}")
        return None
    except Exception as e:
        print(f"DEBUG: Plisio unexpected error: {e}")
        return None

async def check_plisio_invoice_status(invoice_id: str) -> Optional[str]:
    """Check Plisio invoice status, returns raw status string (e.g. 'completed', 'new', 'pending', 'expired')"""
    if not PLISIO_API_KEY or PLISIO_API_KEY.strip() == "":
        return None
    try:
        url = f"https://api.plisio.net/api/v1/operations/{invoice_id}"
        params = {"api_key": PLISIO_API_KEY}
        response = requests.get(url, params=params, timeout=20)
        data = response.json()
        if not response.ok or not isinstance(data, dict) or data.get("status") != "success":
            return None
        return data.get("data", {}).get("status")
    except Exception as e:
        print(f"DEBUG: Plisio status check error: {e}")
        return None

router = Router()

# In-memory store for last message sent by bot for each user.
# Structure: {user_id: (chat_id, message_id, is_photo)}
LAST_MESSAGE = {}

async def _save_last_message(user_id: int, message_obj, is_photo: bool):
    LAST_MESSAGE[user_id] = (message_obj.chat.id, message_obj.message_id, is_photo)

async def edit_by_callback(callback: CallbackQuery, text: str = None, photo_path: str = None, reply_markup=None, parse_mode: str = None):
    """Простое редактирование сообщения без fallback"""
    try:
        if photo_path:
            await callback.message.edit_caption(
                caption=text or "",
                reply_markup=reply_markup,
                parse_mode=parse_mode
            )
        else:
            await callback.message.edit_text(
                text=text or "",
                reply_markup=reply_markup,
                parse_mode=parse_mode
            )
    except Exception:
        # Игнорируем ошибки редактирования
        pass

async def edit_by_message(message: Message, text: str = None, photo_path: str = None, reply_markup=None, parse_mode: str = None):
    """Простое редактирование последнего сообщения без fallback"""
    user_id = message.from_user.id
    last = LAST_MESSAGE.get(user_id)

    if last:
        chat_id, message_id, was_photo = last
        try:
            if photo_path and was_photo:
                await message.bot.edit_message_caption(
                    chat_id=chat_id, 
                    message_id=message_id, 
                    caption=text or "", 
                    reply_markup=reply_markup,
                    parse_mode=parse_mode
                )
                return message
            elif (not photo_path) and (not was_photo):
                await message.bot.edit_message_text(
                    chat_id=chat_id, 
                    message_id=message_id, 
                    text=text or "", 
                    reply_markup=reply_markup,
                    parse_mode=parse_mode
                )
                return message
        except Exception:
            # Игнорируем ошибки редактирования
            pass
    
    # Если редактирование не удалось, просто отправляем новое сообщение
    return await safe_send_photo(message, text or "", reply_markup=reply_markup, parse_mode=parse_mode, photo_path=photo_path)

class SearchStates(StatesGroup):
    waiting_for_bin = State()

class SupportStates(StatesGroup):
    waiting_for_message = State()
    in_chat = State()
    admin_in_chat = State()

class AuthStates(StatesGroup):
    waiting_for_register_login = State()
    waiting_for_register_password = State()
    waiting_for_login = State()
    waiting_for_login_password = State()
    waiting_for_register_promo = State()

class TopUpStates(StatesGroup):
    waiting_for_method = State()
    waiting_for_amount = State()

class UserPromoStates(StatesGroup):
    waiting_for_promo_code = State()

class ChangePasswordStates(StatesGroup):
    waiting_for_current_password = State()
    waiting_for_new_password = State()
    waiting_for_confirm_password = State()

@router.message(CommandStart())
async def start_command(message: Message, state: FSMContext):
    user_id = message.from_user.id

    if user_is_registered(user_id):
        add_user(user_id=user_id, username=message.from_user.username, first_name=message.from_user.first_name)
        welcome_text = (
            f"<b>🍀 Welcome to «{SHOP_NAME}» shop</b>\n\n"
            "• When working with us, you don't have to worry about the quality of the material. We strictly monitor our product and do not allow unscrupulous sellers to sell poor-quality material to customers.\n\n"
            "<b>⚜️ Quality is doing more than what’s expected</b>"
        )

        inline_buttons = [
            [InlineKeyboardButton(text="👤 Profile", callback_data="profile"), InlineKeyboardButton(text="👥 Sellers", callback_data="sellers")],
            [InlineKeyboardButton(text="🛒 Buy Cards", callback_data="buy_item")],
            [InlineKeyboardButton(text="📦 My cards", callback_data="my_cards"), InlineKeyboardButton(text="🆘 Support Chat", callback_data="support_chat")],
            [InlineKeyboardButton(text="💳 Top up", callback_data="vin_search")],
            [InlineKeyboardButton(text="🔒 Security", callback_data="security"), InlineKeyboardButton(text="⛓️ Our resources", callback_data="resources")]
        ]

        if message.from_user.id == ADMIN_ID:
            inline_buttons.append([InlineKeyboardButton(text="🎛️ Admin Panel", callback_data="admin")])
            inline_buttons.append([InlineKeyboardButton(text="🔍 История поисков бинов", callback_data="admin_search_logs")])

        inline_keyboard = InlineKeyboardMarkup(inline_keyboard=inline_buttons)
        await safe_send_photo(message, welcome_text, reply_markup=inline_keyboard)
        await state.clear()
    else:
        text = """👋 <b>Welcome!</b>

To use our bot, please register or log in.

• <b>Register</b> – if you are a new user.
• <b>Login</b> – if you already have an account."""

        register_btn = InlineKeyboardButton(text="📝 Register", callback_data="auth_register")
        login_btn = InlineKeyboardButton(text="🔐 Login", callback_data="auth_login")
        keyboard = InlineKeyboardMarkup(inline_keyboard=[[register_btn, login_btn]])
        await safe_send_photo(message, text, reply_markup=keyboard)

@router.callback_query(F.data == "main_menu")
async def main_menu_handler(callback: CallbackQuery):
    inline_buttons = [
        [InlineKeyboardButton(text="👤 Profile", callback_data="profile"), InlineKeyboardButton(text="👥 Sellers", callback_data="sellers")],
        [InlineKeyboardButton(text="🛒 Buy Cards", callback_data="buy_item")],
        [InlineKeyboardButton(text="📦 My cards", callback_data="my_cards"), InlineKeyboardButton(text="🆘 Support Chat", callback_data="support_chat")],
        [InlineKeyboardButton(text="💳 Top up", callback_data="vin_search")],
        [InlineKeyboardButton(text="🔒 Security", callback_data="security"), InlineKeyboardButton(text="⛓️ Our resources", callback_data="resources")]
    ]

    if callback.from_user.id == ADMIN_ID:
        inline_buttons.append([InlineKeyboardButton(text="🎛️ Admin Panel", callback_data="admin")])
        inline_buttons.append([InlineKeyboardButton(text="🔍 История поисков бинов", callback_data="admin_search_logs")])

    inline_keyboard = InlineKeyboardMarkup(inline_keyboard=inline_buttons)
    welcome_text = (
        f"<b>🍀 Welcome to «{SHOP_NAME}» shop</b>\n\n"
        "• When working with us, you don't have to worry about the quality of the material. We strictly monitor our product and do not allow unscrupulous sellers to sell poor-quality material to customers.\n\n"
        "<b>⚜️ Quality is doing more than what’s expected</b>"
    )
    await edit_by_callback(callback, text=welcome_text, photo_path="котлета.jpg", reply_markup=inline_keyboard, parse_mode="HTML")

@router.callback_query(F.data == "auth_register")
async def auth_register_handler(callback: CallbackQuery, state: FSMContext):
    msg = await safe_send_photo(
        callback,
        "📝 <b>Registration</b>\n\nPlease enter your login (username):",
        parse_mode="HTML"
    )
    await state.update_data(bot_messages=[msg.message_id], user_messages=[])
    await state.set_state(AuthStates.waiting_for_register_login)

@router.callback_query(F.data == "auth_login")
async def auth_login_handler(callback: CallbackQuery, state: FSMContext):
    await safe_send_photo(
        callback,
        "🔐 <b>Login</b>\n\nEnter your login (username):",
        parse_mode="HTML"
    )
    await state.set_state(AuthStates.waiting_for_login)

@router.message(AuthStates.waiting_for_register_login)
async def process_register_login(message: Message, state: FSMContext):
    login = message.text.strip()

    data = await state.get_data()
    bot_messages = data.get('bot_messages', [])
    user_messages = data.get('user_messages', [])

    if len(login) < 3:
        msg = await edit_by_message(message, text="❌ Login must be at least 3 characters long. Try again:", photo_path="котлета.jpg", parse_mode="HTML")
        if msg:
            bot_messages.append(msg.message_id)
        await state.update_data(bot_messages=bot_messages, user_messages=user_messages)
        return

    if check_login_exists(login):
        msg = await edit_by_message(message, text="❌ This login is already taken. Try another one:", photo_path="котлета.jpg", parse_mode="HTML")
        if msg:
            bot_messages.append(msg.message_id)
        await state.update_data(bot_messages=bot_messages, user_messages=user_messages)
        return

    await state.update_data(register_login=login)
    msg = await safe_send_photo(
        message,
        "🔐 Now enter your password:",
        parse_mode="HTML"
    )
    bot_messages.append(msg.message_id)
    user_messages.append(message.message_id)
    await state.update_data(bot_messages=bot_messages, user_messages=user_messages)
    await state.set_state(AuthStates.waiting_for_register_password)

@router.message(AuthStates.waiting_for_register_password)
async def process_register_password(message: Message, state: FSMContext):
    password = message.text.strip()

    data = await state.get_data()
    login = data.get("register_login")
    bot_messages = data.get('bot_messages', [])
    user_messages = data.get('user_messages', [])

    if len(password) < 4:
        msg = await safe_send_photo(message, "❌ Password must be at least 4 characters long. Try again:", parse_mode="HTML")
        bot_messages.append(msg.message_id)
        await state.update_data(bot_messages=bot_messages, user_messages=user_messages)
        return

    await state.update_data(register_password=password, register_login=login)
    msg = await safe_send_photo(message, "✅ <b>Almost done!</b>\n\nEnter your referral promo code now (required):",
        parse_mode="HTML"
    )
    bot_messages.append(msg.message_id)
    user_messages.append(message.message_id)
    await state.update_data(bot_messages=bot_messages, user_messages=user_messages)
    await state.set_state(AuthStates.waiting_for_register_promo)

@router.callback_query(F.data == "check_payment")
async def check_payment_handler(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    invoice_id = data.get('invoice_id')
    amount = data.get('top_up_amount')

    if not invoice_id or not amount:
        await edit_by_callback(callback, text="❌ Payment session not found. Please start over.", parse_mode="HTML")
        return

    payment_method = data.get('payment_method', 'cryptobot')
    method_label = "All Crypto (BTC)" if payment_method == "plisio" else "CryptoBot"

    try:
        if payment_method == "plisio":
            plisio_status = await check_plisio_invoice_status(invoice_id)
            if plisio_status is None:
                await edit_by_callback(callback, text="❌ Failed to check payment status. Try again later.", parse_mode="HTML")
                return
            is_paid = plisio_status in ("completed", "mismatch")
        else:
            # Получаем API ключ из базы данных
            from database import get_crypto_api_key
            api_key = get_crypto_api_key()

            url = "https://pay.crypt.bot/api/getInvoices"
            headers = {
                "Crypto-Pay-API-Token": api_key,
                "Content-Type": "application/json"
            }
            payload = {
                "invoice_ids": str(invoice_id)
            }

            response = requests.get(url, headers=headers, params=payload, timeout=20)
            resp_data = response.json()

            if not response.ok or not resp_data.get('ok'):
                await edit_by_callback(callback, text="❌ Failed to check payment status. Try again later.", parse_mode="HTML")
                return

            invoices = resp_data.get('result', {}).get('items', [])
            if not invoices:
                await edit_by_callback(callback, text="❌ Invoice not found.", parse_mode="HTML")
                return

            invoice = invoices[0]
            is_paid = invoice.get('status') == 'paid'

        if is_paid:
            user_id = callback.from_user.id
            ok = update_user_balance(user_id, amount)
            if not ok:
                await edit_by_callback(callback, text="❌ Failed to top up balance. Contact support.", parse_mode="HTML")
                return

            # Notify promo owner (if the user used a promo) and the main admin
            try:
                profile = get_user_profile(user_id)
                used_promo = None
                print(f"[DEBUG] user_id={user_id}, profile={profile}, profile_len={len(profile) if profile else 0}")
                if profile and len(profile) >= 8:
                    used_promo = profile[7]
                    print(f"[DEBUG] Extracted used_promo={used_promo} from profile")

                if used_promo:
                    try:
                        promo = get_promo(used_promo)
                        print(f"[DEBUG] Fetched promo: code={used_promo}, promo={promo}")
                        owner_id = None
                        owner_username = None
                        if promo:
                            owner_id = promo.get('owner_user_id')
                            owner_username = promo.get('owner_username')

                        # If we have only owner_username, try to resolve to user_id
                        if not owner_id and owner_username:
                            try:
                                owner_id = get_user_id_by_username(owner_username)
                                print(f"[DEBUG] Resolved owner_username={owner_username} to owner_id={owner_id}")
                            except Exception as e:
                                print(f"[DEBUG] Failed to resolve owner username to id: {e}")

                        if owner_id:
                            # Рассчитываем долю владельца промокода (40%)
                            owner_share = amount * 0.4
                            
                            owner_text = (
                                f"🎉 Ваш реферал @{callback.from_user.username or 'unknown'} пополнил баланс на ${amount:.2f} USD по промокоду {used_promo}.\n\n"
                                f"💰 Ваша доля: 40% (${owner_share:.2f})\n\n"
                                f"Ожидайте сообщения, скоро придет выплата"
                            )
                            # Убираем кнопку - отправляем только текст
                            print(f"[DEBUG] Sending owner notification: promo={used_promo}, owner_id={owner_id}, owner_username={owner_username}")
                            try:
                                await callback.bot.send_message(chat_id=owner_id, text=owner_text)
                                print(f"[DEBUG] Successfully sent message to owner_id={owner_id}")
                                
                                # Автоматически отправляем сообщение админу о необходимости выплаты
                                admin_text = (
                                    f"💰 Запрос выплаты от @{owner_username or 'unknown'}\n\n"
                                    f"Реферал @{callback.from_user.username or 'unknown'} пополнил баланс на ${amount:.2f} USD по промокоду {used_promo}.\n\n"
                                    f"💸 К выплате: ${owner_share:.2f} (40% от ${amount:.2f})"
                                )
                                
                                await callback.bot.send_message(chat_id=ADMIN_ID, text=admin_text)
                                print(f"[DEBUG] Successfully sent admin notification for payout")
                                
                            except Exception as e:
                                print(f"[ERROR] Failed to notify promo owner (id={owner_id}): {e}")
                                # notify admin about failure to reach owner
                                try:
                                    await callback.bot.send_message(chat_id=ADMIN_ID, text=(
                                        f"⚠️ Не удалось отправить уведомление владельцу промокода.\n"
                                        f"Promo: {used_promo}\nOwner id: {owner_id}\nOwner username: {owner_username}\n"
                                        f"Referral: @{callback.from_user.username or 'unknown'} (id: {user_id})\n"
                                        f"Amount: ${amount:.2f}\nError: {e}"
                                    ))
                                except Exception:
                                    print("Also failed to notify admin about owner notification failure.")
                        elif owner_username:
                            # Owner has username but no user_id yet (owner not registered in bot yet)
                            print(f"[DEBUG] Owner username '{owner_username}' is not yet in users table (user not registered in bot)")
                            try:
                                await callback.bot.send_message(chat_id=ADMIN_ID, text=(
                                    f"ℹ️ Промокод '{used_promo}' имеет владельца @{owner_username}, но тот еще не зарегистрирован в боте.\n"
                                    f"Пользователь @{callback.from_user.username or 'unknown'} (id: {user_id}) пополнил ${amount:.2f}\n"
                                    f"Когда владелец запустит бота, он получит уведомление при следующем пополнении."
                                ))
                            except Exception as e:
                                print(f"Failed to notify admin about pending owner: {e}")
                        else:
                            info = {
                                'owner_user_id': promo.get('owner_user_id') if promo else None,
                                'owner_username': owner_username
                            }
                            print(f"Promo {used_promo} has no resolvable owner: {info}")
                            try:
                                await callback.bot.send_message(chat_id=ADMIN_ID, text=(
                                    f"⚠️ Промокод '{used_promo}' не имеет привязанного владельца.\n"
                                    f"Stored owner_user_id: {info['owner_user_id']}, owner_username: {info['owner_username']}\n"
                                    f"Пользователь @{callback.from_user.username or 'unknown'} (id: {user_id}) пополнил ${amount:.2f}"
                                ))
                            except Exception as e:
                                print(f"Failed to notify admin about missing promo owner: {e}")
                    except Exception as e:
                        print(f"Error fetching promo info for {used_promo}: {e}")

                # Notify main admin
                try:
                    username_display = callback.from_user.username or callback.from_user.first_name or 'unknown'
                    if used_promo:
                        # Get promo owner info
                        promo_info = get_promo(used_promo)
                        owner_display = "Unknown"
                        if promo_info:
                            owner_user_id = promo_info.get('owner_user_id')
                            owner_username = promo_info.get('owner_username')
                            if owner_username:
                                owner_display = f"@{owner_username}"
                            elif owner_user_id:
                                owner_display = f"ID: {owner_user_id}"
                        
                        admin_text = (
                            f"ℹ️ <b>Balance Top-up Notification</b>\n"
                            f"━━━━━━━━━━━━━━━━━━━━\n"
                            f"👤 User: @{username_display} (ID: {user_id})\n"
                            f"💰 Amount: ${amount:.2f} USD\n"
                            f"🔐 Promo Code: {used_promo}\n"
                            f"👑 Owner: {owner_display}"
                        )
                        
                        # Add pay button
                        pay_button = InlineKeyboardButton(text="❌ Pay Owner", callback_data=f"admin_pay_promo_owner_{used_promo}_{user_id}")
                        keyboard = InlineKeyboardMarkup(inline_keyboard=[[pay_button]])
                        await callback.bot.send_message(chat_id=ADMIN_ID, text=admin_text, reply_markup=keyboard, parse_mode="HTML")
                    else:
                        admin_text = (
                            f"ℹ️ Пользователь @{username_display} (id: {user_id}) пополнил баланс на ${amount:.2f} USD."
                        )
                        await callback.bot.send_message(chat_id=ADMIN_ID, text=admin_text)
                except Exception as e:
                    print(f"Failed to notify admin about top-up: {e}")
            except Exception as e:
                print(f"Error during top-up notifications: {e}")

            text = f"""✅ <b>Payment successful!</b>

💳 Payment amount: ${amount:.2f} USD
💰 Your balance has been topped up successfully.

Thank you for using our service!"""
            back_button = InlineKeyboardButton(text="🔙 Back to Menu", callback_data="main_menu")
            keyboard = InlineKeyboardMarkup(inline_keyboard=[[back_button]])
            await edit_by_callback(callback, text=text, photo_path="котлета.jpg", reply_markup=keyboard, parse_mode="HTML")
            await state.clear()

        else:
            pay_url = data.get('pay_url')
            text = f"""⏳ Payment pending

💳 Payment amount: {amount:.2f} USD
💸 Payment method: {method_label}

🔗 Pay link:
{pay_url}

After payment, click on the "🔄 Check payment" button."""

            check_payment_button = InlineKeyboardButton(text="🔄 Check payment", callback_data="check_payment")
            pay_now_button = InlineKeyboardButton(text="💳 Pay now", url=pay_url)
            back_button = InlineKeyboardButton(text="◀️ Back", callback_data="vin_search")
            keyboard = InlineKeyboardMarkup(inline_keyboard=[
                [check_payment_button],
                [pay_now_button],
                [back_button]
            ])
            await edit_by_callback(callback, text=text, photo_path="котлета.jpg", reply_markup=keyboard, parse_mode="HTML")

    except Exception as e:
        print(f"Error checking payment: {e}")
        await edit_by_callback(callback, text="❌ Error checking payment. Try again later.", parse_mode="HTML")

@router.callback_query(F.data.startswith("admin_pay_promo_owner_"))
async def admin_pay_promo_owner_handler(callback: CallbackQuery):
    """Handle payment to promo owner"""
    try:
        # Parse callback data: admin_pay_promo_owner_{promo_code}_{user_id}
        payload = callback.data.replace("admin_pay_promo_owner_", "")
        parts = payload.rsplit("_", 1)
        if len(parts) != 2:
            await callback.answer("Invalid callback data", show_alert=True)
            return
        
        promo_code = parts[0]
        user_id = int(parts[1])
        
        # Update button to show ✅ Paid
        paid_button = InlineKeyboardButton(text="✅ Paid to Owner", callback_data="noop")
        keyboard = InlineKeyboardMarkup(inline_keyboard=[[paid_button]])
        
        # Edit message to show success
        old_text = callback.message.text
        updated_text = old_text + "\n\n✅ <b>Payment processed successfully!</b>"
        
        await callback.message.edit_text(text=updated_text, reply_markup=keyboard, parse_mode="HTML")
        await callback.answer("✅ Payment sent to promo owner!", show_alert=False)
        
    except Exception as e:
        print(f"Error processing owner payment: {e}")
        await callback.answer("❌ Error processing payment", show_alert=True)

@router.message(TopUpStates.waiting_for_amount)
async def process_top_up_amount(message: Message, state: FSMContext):
    try:
        amount = float(message.text.strip())
        if amount < MIN_TOPUP_AMOUNT:
            msg = await safe_send_photo(message, f"❌ Minimum top-up amount is ${MIN_TOPUP_AMOUNT:.2f}. Please enter an amount:", parse_mode="HTML"
            )
            await _save_last_message(message.from_user.id, msg, True)
            return

        data = await state.get_data()
        payment_method = data.get("payment_method", "cryptobot")

        if payment_method == "plisio":
            method_label = "All Crypto (BTC)"
            order_number = f"{message.from_user.id}-{int(amount * 100)}-{message.message_id}"
            invoice = await create_plisio_invoice(amount, order_number)
        else:
            method_label = "CryptoBot"
            invoice = await create_crypto_pay_invoice(amount)

        if not invoice:
            msg = await safe_send_photo(message, "❌ Failed to create invoice. Please try again later.", parse_mode="HTML"
            )
            await _save_last_message(message.from_user.id, msg, True)
            return

        await state.update_data(top_up_amount=amount, invoice_id=invoice['invoice_id'], payment_method=payment_method, pay_url=invoice['pay_url'])

        # Автоматический чекер отключен - используется только ручная проверка
        # from payment_checker import add_pending_invoice
        # add_pending_invoice(message.from_user.id, invoice['invoice_id'], amount)

        pay_url = invoice['pay_url']
        text = f"""❕ Invoice created!

💳 Payment amount: {amount:.2f} USD
💸 Payment method: {method_label}

🔗 Pay link:
{pay_url}

💡 After payment, click "🔄 Check payment" to verify status."""

        check_payment_button = InlineKeyboardButton(text="🔄 Check payment", callback_data="check_payment")
        pay_now_button = InlineKeyboardButton(text="💳 Pay now", url=pay_url)
        back_button = InlineKeyboardButton(text="◀️ Back", callback_data="main_menu")
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [check_payment_button],
            [pay_now_button],
            [back_button]
        ])

        msg = await safe_send_photo(message, text, reply_markup=keyboard, parse_mode="HTML")
        await _save_last_message(message.from_user.id, msg, True)

    except ValueError:
        msg = await safe_send_photo(message, "❌ Please enter a valid amount (number). Example: 60 or 75.5",
            parse_mode="HTML"
        )
        await _save_last_message(message.from_user.id, msg, True)

@router.message(AuthStates.waiting_for_register_promo)
async def process_register_promo(message: Message, state: FSMContext):
    user_id = message.from_user.id
    code = message.text.strip()

    if not code:
        await safe_send_photo(message, "❌ Promo code cannot be empty. Please enter a valid referral promo code:", parse_mode="HTML"
        )
        return

    data = await state.get_data()
    login = data.get('register_login')
    password = data.get('register_password')
    username = message.from_user.username or 'Unknown'
    first_name = message.from_user.first_name or 'User'

    promo_message_id = message.message_id

    try:
        ok, msg = register_user_with_referral(user_id, username, first_name, login, password, code)
    except Exception as e:
        print(f"Error registering with referral: {e}")
        ok, msg = False, "Internal error during registration."

    if ok:
        referral_info = get_referral_info(code)
        if referral_info:
            owner_username = referral_info.get('owner_username', 'Unknown')
            owner_user_id = referral_info.get('owner_user_id')

            if owner_user_id:
                try:
                    owner_text = f"🎉 Новый пользователь зарегистрировался по вашему реферальному промокоду!\n\n👤 Пользователь: @{username}\n🔗 Логин: {login}"
                    await message.bot.send_message(chat_id=owner_user_id, text=owner_text)

                    admin_text = f"ℹ️ Новый пользователь зарегистрировался по реферальному промокоду {code}.\n\n👤 Пользователь: @{username}\n🔗 Логин: {login}\n🔗 Владелец промокода: @{owner_username}"
                    await message.bot.send_message(chat_id=ADMIN_ID, text=admin_text)
                except Exception as e:
                    print(f"Failed to notify owner or admin about registration: {e}")

        success_message = await safe_send_photo(message, f"✅ {msg}", parse_mode="HTML"
        )

        success_message_id = success_message.message_id

        await asyncio.sleep(3)

        data = await state.get_data()
        bot_messages = data.get('bot_messages', [])
        user_messages = data.get('user_messages', [])

        for msg_id in bot_messages:
            try:
                await message.bot.delete_message(chat_id=message.chat.id, message_id=msg_id)
            except Exception as e:
                print(f"Failed to delete bot message {msg_id}: {e}")

        for msg_id in user_messages:
            try:
                await message.bot.delete_message(chat_id=message.chat.id, message_id=msg_id)
            except Exception as e:
                print(f"Failed to delete user message {msg_id}: {e}")

        try:
            await message.bot.delete_message(chat_id=message.chat.id, message_id=promo_message_id)
        except Exception as e:
            print(f"Failed to delete promo message: {e}")

        try:
            await message.bot.delete_message(chat_id=message.chat.id, message_id=success_message_id)
        except Exception as e:
            print(f"Failed to delete success message: {e}")

        try:
            async for msg in message.bot.get_chat_history(chat_id=message.chat.id, limit=5):
                if msg.from_user and msg.from_user.id == message.bot.id:
                    try:
                        await message.bot.delete_message(chat_id=message.chat.id, message_id=msg.message_id)
                    except Exception as e:
                        print(f"Failed to delete initial bot message {msg.message_id}: {e}")
                        break
        except Exception as e:
            print(f"Failed to get initial bot messages: {e}")

        await state.clear()
        await start_command(message, state)
    else:
        await safe_send_photo(message, f"❌ {msg}\nPlease enter a valid referral promo code:", parse_mode="HTML"
        )
        await state.set_state(AuthStates.waiting_for_register_promo)

@router.message(AuthStates.waiting_for_login)
async def process_login_username(message: Message, state: FSMContext):
    login = message.text.strip()

    if not login:
        await edit_by_message(message, text="❌ Login cannot be empty. Try again:", photo_path="котлета.jpg", parse_mode="HTML")
        return

    await state.update_data(login=login)
    await edit_by_message(message, text="🔑 Now enter your password:", photo_path="котлета.jpg", parse_mode="HTML")
    await state.set_state(AuthStates.waiting_for_login_password)

@router.message(AuthStates.waiting_for_login_password)
async def process_login_password(message: Message, state: FSMContext):
    password = message.text.strip()
    data = await state.get_data()
    login = data.get("login")

    verified_user_id = verify_login(login, password)

    if verified_user_id:
        user_id = verified_user_id
        # Обновляем информацию пользователя и помечаем как зарегистрированного
        conn = get_db_connection()
        try:
            conn.execute("""
                UPDATE users 
                SET username = ?, first_name = ?, registered = 1 
                WHERE user_id = ?
            """, (message.from_user.username, message.from_user.first_name, user_id))
            conn.commit()
        except Exception as e:
            print(f"Error updating user on login: {e}")
        finally:
            conn.close()
            
        await state.clear()
        
        # Показываем главное меню сразу
        inline_buttons = [
            [InlineKeyboardButton(text="👤 Profile", callback_data="profile"), InlineKeyboardButton(text="👥 Sellers", callback_data="sellers")],
            [InlineKeyboardButton(text="🛒 Buy Cards", callback_data="buy_item")],
            [InlineKeyboardButton(text="📦 My cards", callback_data="my_cards"), InlineKeyboardButton(text="🆘 Support Chat", callback_data="support_chat")],
            [InlineKeyboardButton(text="💳 Top up", callback_data="vin_search")],
            [InlineKeyboardButton(text="🔒 Security", callback_data="security"), InlineKeyboardButton(text="⛓️ Our resources", callback_data="resources")]
        ]

        if message.from_user.id == ADMIN_ID:
            inline_buttons.append([InlineKeyboardButton(text="🎛️ Admin Panel", callback_data="admin")])
            inline_buttons.append([InlineKeyboardButton(text="🔍 История поисков бинов", callback_data="admin_search_logs")])

        inline_keyboard = InlineKeyboardMarkup(inline_keyboard=inline_buttons)
        welcome_text = (
            f"<b>🍀 Welcome to «{SHOP_NAME}» shop</b>\n\n"
            "• When working with us, you don't have to worry about the quality of the material. We strictly monitor our product and do not allow unscrupulous sellers to sell poor-quality material to customers.\n\n"
            "<b>⚜️ Quality is doing more than what's expected</b>"
        )
        await safe_send_photo(message, welcome_text, reply_markup=inline_keyboard, parse_mode="HTML")
    else:
        await edit_by_message(message, text="❌ Invalid login or password. Try again:", photo_path="котлета.jpg", parse_mode="HTML")

@router.callback_query(F.data == "sellers")
async def sellers_handler(callback: CallbackQuery):
    # Показываем список продавцов в столбик, каждый с префиксом 🏪.
    # Кнопки создаются как noop (callback_data начинаются с 'noop_seller_'),
    # чтобы при нажатии ничего не происходило.
    supplier_names = ["ADMIN", "ZEUS", "tec_9", "topseller", "jessePinkman", "Operator", "macho"]

    seller_buttons = []
    for name in supplier_names:
        btn = InlineKeyboardButton(text=f"🏪 {name}", callback_data=f"noop_seller_{name}")
        seller_buttons.append([btn])

    back_button = InlineKeyboardButton(text="◀️ Back", callback_data="main_menu")
    seller_buttons.append([back_button])

    keyboard = InlineKeyboardMarkup(inline_keyboard=seller_buttons)
    await edit_by_callback(callback, text="🛒 <b>Sellers:</b>", photo_path="котлета.jpg", reply_markup=keyboard, parse_mode="HTML")

@router.callback_query(F.data.startswith("view_seller_"))
async def view_seller_handler(callback: CallbackQuery):
    key = callback.data[len("view_seller_"):]
    sellers = get_sellers()
    seller_info = None
    if key.isdigit() and key in sellers:
        seller_info = sellers[key]

    if key.upper() == 'ADMIN':
        text = (
            "🏪 ADMIN\n\n"
            "FORMAT: num|exp|cvv|holder name|phone|email\n"
            "────────────────────────\n"
            "🛡 Deposit: Yes\n"
            "⭐ Rating: 4.8\n"
            "💳 Cards: 2791\n"
            "📦 Sold: 10905\n"
            "✅ VR: 81%"
        )
        back_button = InlineKeyboardButton(text="🔙 Back", callback_data="sellers")
        keyboard = InlineKeyboardMarkup(inline_keyboard=[[back_button]])
        await edit_by_callback(callback, text=text, photo_path="котлета.jpg", reply_markup=keyboard, parse_mode="HTML")
        return

    if key.upper() == 'ZEUS':
        text = (
            "🏪 ZEUS\n\n"
            "FORMAT: num|exp|cvv\n"
            "────────────────────────\n"
            "🛡 Deposit: Yes\n"
            "⭐ Rating: 4.7\n"
            "💳 Cards: 429\n"
            "📦 Sold: 4254\n"
            "✅ VR: 76%"
        )
        back_button = InlineKeyboardButton(text="🔙 Back", callback_data="sellers")
        keyboard = InlineKeyboardMarkup(inline_keyboard=[[back_button]])
        await edit_by_callback(callback, text=text, photo_path="котлета.jpg", reply_markup=keyboard, parse_mode="HTML")
        return

    if key.upper() in ('ANON', 'UNKNOW'):
        try:
            await callback.answer()
        except Exception:
            pass
        return

    if seller_info:
        num, exp, cvv, holder_name, phone, email, deposit, rating, cards, sold, vr = seller_info
        seller_text = f"""🏪 {holder_name}

FORMAT: {num}|{exp}|{cvv}|{phone}|{email}
────────────────────────
🛡 Deposit: {'Yes' if deposit else 'No'}
⭐️ Rating: {rating}
💳 Cards: {cards}
📦 Sold: {sold}
✅ VR: {vr}%"""
        back_button = InlineKeyboardButton(text="🔙 Back", callback_data="sellers")
        keyboard = InlineKeyboardMarkup(inline_keyboard=[[back_button]])
        await edit_by_callback(callback, text=seller_text, photo_path="котлета.jpg", reply_markup=keyboard, parse_mode="HTML")
        return

    await edit_by_callback(callback, text="Supplier not found", photo_path="котлета.jpg", parse_mode="HTML")


@router.callback_query(F.data.startswith("noop_seller_"))
async def noop_seller_handler(callback: CallbackQuery):
    """No-op handler for sellers we don't want to open (keeps button inert)."""
    try:
        await callback.answer()
    except Exception:
        pass

@router.callback_query(F.data == "buy_item")
async def buy_item_handler(callback: CallbackQuery):
    welcome_text = """💳 Buy cards
━━━━━━━━━━━━━━━━━━━━
Choose how you want to browse the catalog:"""
    category_buttons = [
        [InlineKeyboardButton(text="📋 View all products", callback_data="view_all_products")],
        [InlineKeyboardButton(text="💳 Search by BIN", callback_data="search_by_bin")],
        [InlineKeyboardButton(text="◀️ Back", callback_data="main_menu")]
    ]
    category_keyboard = InlineKeyboardMarkup(inline_keyboard=category_buttons)
    await edit_by_callback(callback, text=welcome_text, photo_path="котлета.jpg", reply_markup=category_keyboard, parse_mode="HTML")

@router.callback_query(F.data == "profile")
async def profile_handler(callback: CallbackQuery):
    user_id = callback.from_user.id
    user_profile = get_user_profile(user_id)

    login = user_profile[3] if user_profile and user_profile[3] else callback.from_user.username or 'Not set'
    balance = user_profile[6] if user_profile and len(user_profile) > 6 else 0.0
    referral_code = user_profile[7] if user_profile and len(user_profile) > 7 else '—'

    account_info = get_account_info(user_id)
    purchases = account_info['purchases'] if account_info else 0
    total_spent = account_info['total_spent'] if account_info else 0.0

    profile_text = f"""
👤 <b>Profile</b>
━━━━━━━━━━━━━━━━━━━━
🪪 Login: <b>{login}</b>
💰 Balance: <b>${balance:.2f}</b>
🔗 Referral Code: <b>{referral_code}</b>

📊 <b>Buyer stats</b>
• Payments: <b>{purchases}</b>
• Purchases: <b>${total_spent:.2f}</b>
• Purchased cards: <b>{purchases}</b>
• Total payments: <b>${total_spent:.2f}</b>
"""

    back_button = InlineKeyboardButton(text="◀️ Back", callback_data="main_menu")

    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [back_button]
    ])
    await edit_by_callback(callback, text=profile_text, photo_path="котлета.jpg", reply_markup=keyboard, parse_mode="HTML")

@router.callback_query(F.data == "security")
async def security_handler(callback: CallbackQuery):
    text = """🔐 <b>Security</b>
Choose an action:"""

    logout_button = InlineKeyboardButton(text="🔙 Log Out", callback_data="sign_out")
    change_password_button = InlineKeyboardButton(text="🔑 Change Password", callback_data="change_password")
    back_button = InlineKeyboardButton(text="🏠 Back", callback_data="main_menu")

    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [logout_button],
        [change_password_button],
        [back_button]
    ])

    await edit_by_callback(callback, text=text, photo_path="котлета.jpg", reply_markup=keyboard, parse_mode="HTML")

@router.callback_query(F.data == "change_password")
async def change_password_handler(callback: CallbackQuery, state: FSMContext):
    text = """🔑 <b>Change Password</b>

Please enter your current password:"""
    
    back_button = InlineKeyboardButton(text="◀️ Back", callback_data="security")
    keyboard = InlineKeyboardMarkup(inline_keyboard=[[back_button]])
    
    await edit_by_callback(callback, text=text, photo_path="котлета.jpg", reply_markup=keyboard, parse_mode="HTML")
    await state.set_state(ChangePasswordStates.waiting_for_current_password)

@router.message(ChangePasswordStates.waiting_for_current_password)
async def process_current_password(message: Message, state: FSMContext):
    user_id = message.from_user.id
    current_password = message.text.strip()
    
    # Проверяем текущий пароль
    user_profile = get_user_profile(user_id)
    if not user_profile or user_profile[4] != current_password:  # password is at index 4
        await safe_send_photo(message, "❌ <b>Incorrect current password!</b>\n\nPlease try again or go back to security menu.", parse_mode="HTML"
        )
        return
    
    # Сохраняем user_id в состоянии
    await state.update_data(user_id=user_id)
    
    text = """🔑 <b>Change Password</b>

✅ Current password verified!

Please enter your new password:"""
    
    back_button = InlineKeyboardButton(text="◀️ Back", callback_data="security")
    keyboard = InlineKeyboardMarkup(inline_keyboard=[[back_button]])
    
    await safe_send_photo(message, text, reply_markup=keyboard, parse_mode="HTML")
    await state.set_state(ChangePasswordStates.waiting_for_new_password)

@router.message(ChangePasswordStates.waiting_for_new_password)
async def process_new_password(message: Message, state: FSMContext):
    new_password = message.text.strip()
    
    if len(new_password) < 4:
        await safe_send_photo(message, "❌ <b>Password too short!</b>\n\nPassword must be at least 4 characters long.", parse_mode="HTML"
        )
        return
    
    # Сохраняем новый пароль в состоянии
    await state.update_data(new_password=new_password)
    
    text = """🔑 <b>Change Password</b>

Please confirm your new password:"""
    
    back_button = InlineKeyboardButton(text="◀️ Back", callback_data="security")
    keyboard = InlineKeyboardMarkup(inline_keyboard=[[back_button]])
    
    await safe_send_photo(message, text, reply_markup=keyboard, parse_mode="HTML")
    await state.set_state(ChangePasswordStates.waiting_for_confirm_password)

@router.message(ChangePasswordStates.waiting_for_confirm_password)
async def process_confirm_password(message: Message, state: FSMContext):
    confirm_password = message.text.strip()
    data = await state.get_data()
    new_password = data.get('new_password')
    user_id = data.get('user_id')
    
    if confirm_password != new_password:
        await safe_send_photo(message, "❌ <b>Passwords don't match!</b>\n\nPlease try again.", parse_mode="HTML"
        )
        await state.set_state(ChangePasswordStates.waiting_for_new_password)
        return
    
    # Обновляем пароль в базе данных
    try:
        if update_user_password(user_id, new_password):
            text = """✅ <b>Password Changed Successfully!</b>

Your password has been updated."""
        else:
            text = """❌ <b>Error!</b>

Failed to update password. Please try again later."""
    except Exception as e:
        text = """❌ <b>Error!</b>

Failed to update password. Please try again later."""
    
    back_button = InlineKeyboardButton(text="◀️ Back to Security", callback_data="security")
    keyboard = InlineKeyboardMarkup(inline_keyboard=[[back_button]])
    
    await safe_send_photo(message, text, reply_markup=keyboard, parse_mode="HTML")
    await state.clear()

@router.callback_query(F.data == "resources")
async def resources_handler(callback: CallbackQuery):
    exploit_button = InlineKeyboardButton(text="🔓 Exploit", url="https://exploit6tauvv7onrc2ajnu74fg3etns4qft5ak7pz6pvxt3ohhgvvqd.onion/topic/293492/")
    back_button = InlineKeyboardButton(text="◀️ Back", callback_data="main_menu")

    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [exploit_button],
        [back_button]
    ])

    text = """🔗 <b>Our links:</b>
━━━━━━━━━━━━━━━━━━━━
Here you can find our official resources:"""

    await edit_by_callback(callback, text=text, photo_path="котлета.jpg", reply_markup=keyboard, parse_mode="HTML")

@router.callback_query(F.data == "return")
async def return_handler(callback: CallbackQuery):
    back_button = InlineKeyboardButton(text="◀️ Back", callback_data="main_menu")
    keyboard = InlineKeyboardMarkup(inline_keyboard=[[back_button]])
    await edit_by_callback(callback, text="🔄 To process a return, contact @vfradmin with proof of product malfunction.", photo_path="котлета.jpg", reply_markup=keyboard, parse_mode="HTML")

@router.callback_query(F.data == "sign_out")
async def sign_out_handler(callback: CallbackQuery, state: FSMContext):
    user_id = callback.from_user.id

    try:
        ok = logout_user(user_id)
    except Exception as e:
        print(f"Error calling logout_user: {e}")
        ok = False

    try:
        LAST_MESSAGE.pop(user_id, None)
    except Exception:
        pass

    if ok:
        register_btn = InlineKeyboardButton(text="📝 Register", callback_data="auth_register")
        login_btn = InlineKeyboardButton(text="🔐 Login", callback_data="auth_login")
        keyboard = InlineKeyboardMarkup(inline_keyboard=[[register_btn, login_btn]])
        await edit_by_callback(callback, text="✅ You have been signed out. Please register or login to continue.", photo_path="котлета.jpg", reply_markup=keyboard, parse_mode="HTML")
        try:
            await state.clear()
        except Exception:
            pass
    else:
        await edit_by_callback(callback, text="❌ Failed to sign out. Please try again later.", photo_path="котлета.jpg", parse_mode="HTML")

@router.callback_query(F.data == "my_cards")
async def my_cards_handler(callback: CallbackQuery):
    user_id = callback.from_user.id
    cards = get_user_card_sales(user_id)

    if not cards:
        text = """📦 <b>You don't have any purchased cards yet</b>
━━━━━━━━━━━━━━━━━━━━
Purchase cards to see them here."""
        back_button = InlineKeyboardButton(text="◀️ Back", callback_data="main_menu")
        keyboard = InlineKeyboardMarkup(inline_keyboard=[[back_button]])
        await edit_by_callback(callback, text=text, photo_path="котлета.jpg", reply_markup=keyboard, parse_mode="HTML")
    else:
        text = """📦 <b>Your Purchased Cards</b>
━━━━━━━━━━━━━━━━━━━━
Select a card to view details:"""
        
        buttons = []
        for card in cards:
            card_id, bin_code, card_text, supplier, price, country, sale_date = card
            flag = get_flag_for_country(country) if country and country != 'Unknown' else '🏳️'
            display_bin = f"{flag} {bin_code} | ${price:.2f}"
            buttons.append([InlineKeyboardButton(text=display_bin, callback_data=f"view_card_{card_id}")])
        
        buttons.append([InlineKeyboardButton(text="◀️ Back", callback_data="main_menu")])
        keyboard = InlineKeyboardMarkup(inline_keyboard=buttons)
        await edit_by_callback(callback, text=text, photo_path="котлета.jpg", reply_markup=keyboard, parse_mode="HTML")

@router.callback_query(F.data.startswith("view_card_"))
async def view_card_handler(callback: CallbackQuery):
    """Show information about purchased card"""
    try:
        card_id = int(callback.data.replace("view_card_", ""))
    except Exception:
        await callback.answer("❌ Error loading card", show_alert=True)
        return
    
    card = get_card_sale_by_id(card_id)
    if not card:
        await callback.answer("❌ Card not found", show_alert=True)
        return
    
    card_id, bin_code, card_text, supplier, price, country, sale_date = card
    
    # Parse card_text (format: number|expiry|cvv)
    parts = card_text.split('|') if card_text else []
    card_number = parts[0] if len(parts) > 0 else "N/A"
    expiry = parts[1] if len(parts) > 1 else "N/A"
    cvv = parts[2] if len(parts) > 2 else "N/A"
    
    # Get seller information
    seller_display = supplier.upper() if supplier.upper() in ('ADMIN', 'ZEUS') else supplier
    seller_esc = html.escape(seller_display)
    bin_esc = html.escape(bin_code)
    card_number_esc = html.escape(card_number)
    expiry_esc = html.escape(expiry)
    cvv_esc = html.escape(cvv)
    price_esc = html.escape(f"{price:.2f}")
    country_esc = html.escape(country if country and country != 'Unknown' else '')
    
    receipt = (
        f"🛍️ <b>Card Details</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"🛒 <b>Seller:</b> {seller_esc}\n"
    )
    
    if country_esc:
        receipt += f"🏳️ <b>Country:</b> {country_esc}\n"
    
    receipt += (
        f"🔢 <b>BIN:</b> {bin_esc}\n"
        f"💰 <b>Price:</b> {price_esc} $\n"
        f"📅 <b>Purchase Date:</b> {sale_date}\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"📦 <b>Card Data:</b>\n"
        f"{card_number_esc} | {expiry_esc} | {cvv_esc}\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
    )
    
    back_button = InlineKeyboardButton(text="◀️ Back to Cards", callback_data="my_cards")
    keyboard = InlineKeyboardMarkup(inline_keyboard=[[back_button]])
    await edit_by_callback(callback, text=receipt, photo_path="котлета.jpg", reply_markup=keyboard, parse_mode="HTML")

@router.callback_query(F.data == "view_all_products")
async def view_all_products_handler(callback: CallbackQuery):
    per_page = 20
    items, page, total_pages, total = get_country_page(0, per_page=per_page)

    buttons = []
    row = []
    for idx, country in enumerate(items):
        global_index = page * per_page + idx
        flag = get_flag_for_country(country)
        btn = InlineKeyboardButton(text=f"{flag} {country}", callback_data=f"country_{global_index}")
        row.append(btn)
        if len(row) == 2:
            buttons.append(row)
            row = []
    if row:
        buttons.append(row)

    nav_row = []
    if page > 0:
        nav_row.append(InlineKeyboardButton(text="◀️ Prev", callback_data=f"countries_page_{page-1}"))
    nav_row.append(InlineKeyboardButton(text=f"Page {page+1}/{max(total_pages,1)}", callback_data="noop"))
    if page < total_pages - 1:
        nav_row.append(InlineKeyboardButton(text="Next ▶️", callback_data=f"countries_page_{page+1}"))
    nav_row.append(InlineKeyboardButton(text="◀️ Back", callback_data="buy_item"))

    buttons.append(nav_row)
    keyboard = InlineKeyboardMarkup(inline_keyboard=buttons)
    await edit_by_callback(callback, text="🌍 Select a country:", photo_path="котлета.jpg", reply_markup=keyboard, parse_mode="HTML")

@router.callback_query(F.data.startswith("countries_page_"))
async def countries_page_handler(callback: CallbackQuery):
    try:
        page = int(callback.data.split("_")[-1])
    except Exception:
        page = 0
    per_page = 20
    items, page, total_pages, total = get_country_page(page, per_page=per_page)

    buttons = []
    row = []
    for idx, country in enumerate(items):
        global_index = page * per_page + idx
        flag = get_flag_for_country(country)
        btn = InlineKeyboardButton(text=f"{flag} {country}", callback_data=f"country_{global_index}")
        row.append(btn)
        if len(row) == 2:
            buttons.append(row)
            row = []
    if row:
        buttons.append(row)

    nav_row = []
    if page > 0:
        nav_row.append(InlineKeyboardButton(text="◀️ Prev", callback_data=f"countries_page_{page-1}"))
    nav_row.append(InlineKeyboardButton(text=f"Page {page+1}/{max(total_pages,1)}", callback_data="noop"))
    if page < total_pages - 1:
        nav_row.append(InlineKeyboardButton(text="Next ▶️", callback_data=f"countries_page_{page+1}"))
    nav_row.append(InlineKeyboardButton(text="◀️ Back", callback_data="main_menu"))

    buttons.append(nav_row)
    keyboard = InlineKeyboardMarkup(inline_keyboard=buttons)
    await edit_by_callback(callback, text="🌍 Select a country:", photo_path="котлета.jpg", reply_markup=keyboard, parse_mode="HTML")

@router.callback_query(F.data.startswith("country_"))
async def country_selected_handler(callback: CallbackQuery):
    try:
        idx = int(callback.data.split("_")[-1])
    except Exception:
        await edit_by_callback(callback, text="Invalid selection", photo_path="котлета.jpg", parse_mode="HTML")
        return
    countries = get_countries()
    if idx < 0 or idx >= len(countries):
        await edit_by_callback(callback, text="Country not found", photo_path="котлета.jpg", parse_mode="HTML")
        return

    country_display = countries[idx]
    bins = get_bins_for_country_all(country_display)

    if not bins:
        await edit_by_callback(callback, text="BINs for this country not found", photo_path="котлета.jpg", parse_mode="HTML")
        return

    await show_country_bins_page(callback, idx, country_display, bins, 0)

async def show_country_bins_page(callback: CallbackQuery, country_idx: int, country_display: str, bins: list, page: int):
    bins_per_page = 20
    total_pages = (len(bins) + bins_per_page - 1) // bins_per_page

    start_idx = page * bins_per_page
    end_idx = start_idx + bins_per_page
    page_bins = bins[start_idx:end_idx]

    caption = f"{country_display}\nValid card of the specified country\n\nPage {page + 1}/{total_pages}"

    buttons = []
    for i in range(0, len(page_bins), 2):
        row = []
        for j in range(2):
            if i + j < len(page_bins):
                item = page_bins[i + j]
                flag = item.get('flag', '')
                b = item['bin']
                price = item.get('price', 0.0)
                bin_display = f"{flag} {b}".strip()
                text = f"{bin_display} | {price}$"
                row.append(InlineKeyboardButton(text=text, callback_data=f"bin_{country_idx}_{b}_{page}"))
        if row:
            buttons.append(row)

    nav_buttons = []
    if page > 0:
        nav_buttons.append(InlineKeyboardButton(text="◀️ Prev", callback_data=f"country_bins_page_{country_idx}_{page-1}"))
    if page < total_pages - 1:
        nav_buttons.append(InlineKeyboardButton(text="Next ▶️", callback_data=f"country_bins_page_{country_idx}_{page+1}"))
    if nav_buttons:
        buttons.append(nav_buttons)

    countries_per_page = 20
    countries_page = country_idx // countries_per_page
    buttons.append([InlineKeyboardButton(text="🏳️ Back to countries", callback_data=f"countries_page_{countries_page}")])
    buttons.append([InlineKeyboardButton(text="◀️ Back to menu", callback_data="main_menu")])

    keyboard = InlineKeyboardMarkup(inline_keyboard=buttons)
    await edit_by_callback(callback, text=caption, photo_path="котлета.jpg", reply_markup=keyboard, parse_mode="HTML")

@router.callback_query(F.data.startswith("country_bins_page_"))
async def country_bins_page_handler(callback: CallbackQuery):
    parts = callback.data.replace("country_bins_page_", "").split("_")
    if len(parts) < 2:
        await edit_by_callback(callback, text="Invalid request", photo_path="котлета.jpg", parse_mode="HTML")
        return

    try:
        country_idx = int(parts[0])
        page = int(parts[1])
    except Exception:
        await edit_by_callback(callback, text="Invalid request", photo_path="котлета.jpg", parse_mode="HTML")
        return

    countries = get_countries()
    if country_idx < 0 or country_idx >= len(countries):
        await edit_by_callback(callback, text="Country not found", photo_path="котлета.jpg", parse_mode="HTML")
        return

    country_display = countries[country_idx]
    bins = get_bins_for_country_all(country_display)

    if not bins:
        await edit_by_callback(callback, text="BINs not found", photo_path="котлета.jpg", parse_mode="HTML")
        return

    await show_country_bins_page(callback, country_idx, country_display, bins, page)

@router.callback_query(F.data.startswith("bin_"))
async def bin_selected_handler(callback: CallbackQuery):
    parts = callback.data.replace("bin_", "").split("_", 2)
    if len(parts) < 2:
        await edit_by_callback(callback, text="Invalid BIN selection", photo_path="котлета.jpg", parse_mode="HTML")
        return

    try:
        country_idx = int(parts[0])
        bin_code = parts[1]
        current_page = int(parts[2]) if len(parts) > 2 else 0
    except Exception:
        await edit_by_callback(callback, text="Invalid BIN selection", photo_path="котлета.jpg")
        return

    countries = get_countries()
    if country_idx < 0 or country_idx >= len(countries):
        await edit_by_callback(callback, text="Country not found", photo_path="котлета.jpg", parse_mode="HTML")
        return

    country_display = countries[country_idx]
    bins = get_bins_for_country_all(country_display)

    found = None
    for item in bins:
        if item['bin'] == bin_code:
            found = item
            break

    if not found:
        await edit_by_callback(callback, text="BIN not found", photo_path="котлета.jpg", parse_mode="HTML")
        return

    flag = found.get('flag', '')
    b = found['bin']
    display = f"{flag} {b}".strip()
    price = found.get('price', 0.0)
    bank = found.get('bank', '')
    brand = found.get('brand', '')
    card_type = found.get('type', '')
    level = found.get('level', '')
    country = found.get('country', '')
    pcs = found.get('pcs', 0)
    supplier_name = found.get('supplier_name', 'UNKNOWN')

    # Normalize supplier name using canonical mapping so view-all matches search results
    try:
        canonical = _canonical_supplier_name_from_stem(supplier_name or "")
    except Exception:
        canonical = supplier_name
    supplier_display = supplier_name if supplier_name else "Unknown"
    import html
    supplier_escaped = html.escape(supplier_display)
    display_escaped = html.escape(display)
    b_escaped = html.escape(b)
    country_escaped = html.escape(country)
    brand_escaped = html.escape(brand)
    type_escaped = html.escape(card_type)
    level_escaped = html.escape(level)
    bank_escaped = html.escape(bank)
    price_escaped = html.escape(str(price))
    pcs_escaped = html.escape(str(pcs))

    caption = (
        f"🏪 SELLER: <b>{supplier_escaped}</b>\n\n"
        f"📜 NAME: <b>{display_escaped}</b>\n\n"
        f"💳 BIN: <b>{b_escaped}</b>\n"
        f"🏴 COUNTRY: <b>{country_escaped}</b>\n"
        f"🧳 BRAND: <b>{brand_escaped}</b>\n"
        f"💸 TYPE: <b>{type_escaped}</b>\n"
        f"🔑 LEVEL: <b>{level_escaped}</b>\n"
        f"🏦 BANK: <b>{bank_escaped}</b>\n\n"
        f"💸 Price: <b>{price_escaped} $</b>\n"
        f"💳 In stock: <b>{pcs_escaped} pcs.</b>"
    )

    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="💸 Buy", callback_data=f"buy_{country_idx}_{b}"),
            InlineKeyboardButton(text="✅ Autocheck", callback_data=f"autocheck_{country_idx}_{b}")
        ],
        [InlineKeyboardButton(text="◀️ Back to BINs", callback_data=f"country_bins_page_{country_idx}_{current_page}")],
        [InlineKeyboardButton(text="◀️ Back to menu", callback_data="main_menu")]
    ])
    await edit_by_callback(callback, text=caption, photo_path="котлета.jpg", reply_markup=keyboard, parse_mode="HTML")

@router.callback_query(F.data == "search_by_seller")
async def search_by_seller_handler(callback: CallbackQuery):
    supplier_names = ["ADMIN", "ZEUS", "ANON", "UNKNOW"]
    supplier_buttons = []
    row = []
    for name in supplier_names:
        row.append(InlineKeyboardButton(text=f"🏪 {name}", callback_data=f"seller_select_{name}"))
        if len(row) == 2:
            supplier_buttons.append(row)
            row = []
    if row:
        supplier_buttons.append(row)

    supplier_buttons.append([InlineKeyboardButton(text="◀️ Back", callback_data="buy_item")])
    keyboard = InlineKeyboardMarkup(inline_keyboard=supplier_buttons)
    await edit_by_callback(callback, text="🏦 Select a supplier:", photo_path="котлета.jpg", reply_markup=keyboard, parse_mode="HTML")

@router.callback_query(F.data.startswith("seller_select_"))
async def seller_select_handler(callback: CallbackQuery):
    supplier_name = callback.data.replace("seller_select_", "")
    bins = get_bins_for_supplier(supplier_name)

    if not bins:
        back_button = InlineKeyboardButton(text="◀️ Back", callback_data="search_by_seller")
        keyboard = InlineKeyboardMarkup(inline_keyboard=[[back_button]])
        await edit_by_callback(callback, text=f"🏪 {supplier_name}: BINs not found.", photo_path="котлета.jpg", reply_markup=keyboard, parse_mode="HTML")
        return

    sellers = get_sellers()
    seller_info = None
    for seller_id, info in sellers.items():
        _, _, _, holder_name, _, _, _, _, _, _, _ = info
        if holder_name == supplier_name:
            seller_info = info
            break

    countries_dict = {}
    for bin_item in bins:
        country = bin_item.get('country', 'Unknown')
        if country not in countries_dict:
            countries_dict[country] = []
        countries_dict[country].append(bin_item)

    countries = sorted(list(countries_dict.keys()))

    if seller_info:
        num, exp, cvv, holder_name, phone, email, deposit, rating, cards, sold, vr = seller_info
        seller_text = f"""🏪 <b>Choose a seller:</b>

<b>{supplier_name}</b>
High quality CC with more data

<b>FORMAT:</b> {num}|{exp}|{cvv}|holder name|phone|email
────────────────────────────────────────
🛡 Deposit: {'Yes' if deposit else 'No'}
⭐️ Rating: {rating}
💳 Cards: {cards}
📦 Sold: {sold}
✅ VR: {vr}%"""
    else:
        seller_text = f"🏪 Choose a seller: {supplier_name}"

    await edit_by_callback(callback, text=seller_text, photo_path="котлета.jpg", reply_markup=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="◀️ Back", callback_data="search_by_seller")]]), parse_mode="HTML")

    await show_seller_countries_page(callback, supplier_name, countries, 0)

async def show_seller_countries_page(callback: CallbackQuery, supplier_name: str, countries: list, page: int):
    countries_per_page = 20
    total_pages = (len(countries) + countries_per_page - 1) // countries_per_page

    if page < 0:
        page = 0
    if page >= total_pages:
        page = total_pages - 1

    start_idx = page * countries_per_page
    end_idx = start_idx + countries_per_page
    page_countries = countries[start_idx:end_idx]

    country_buttons = []

    for i in range(0, len(page_countries), 2):
        row = []
        for j in range(2):
            if i + j < len(page_countries):
                country_name = page_countries[i + j]
                flag = get_flag_for_country(country_name)
                cb = _force_token_callback('seller_country', supplier_name, country_name)
                row.append(InlineKeyboardButton(text=f"{flag} {country_name}", callback_data=cb))
        if row:
            country_buttons.append(row)

    nav_buttons = []
    if page > 0:
        prev_cb = _force_token_callback('seller_countries_page', supplier_name, str(page-1))
        nav_buttons.append(InlineKeyboardButton(text="◀️ Prev", callback_data=prev_cb))
    if page < total_pages - 1:
        next_cb = _force_token_callback('seller_countries_page', supplier_name, str(page+1))
        nav_buttons.append(InlineKeyboardButton(text="Next ▶️", callback_data=next_cb))
    if nav_buttons:
        country_buttons.append(nav_buttons)

    country_buttons.append([InlineKeyboardButton(text="🔙 Back", callback_data="search_by_seller")])
    keyboard = InlineKeyboardMarkup(inline_keyboard=country_buttons)
    caption = f"🏪 {supplier_name}\n\n🌍 Select a country (Page {page + 1}/{total_pages})"
    await edit_by_callback(callback, text=caption, photo_path="котлета.jpg", reply_markup=keyboard, parse_mode="HTML")

@router.callback_query(F.data.startswith("seller_countries_page_"))
async def seller_countries_page_handler(callback: CallbackQuery):
    payload = callback.data.replace("seller_countries_page_", "")
    try:
        if payload.startswith("token_"):
            remainder = payload.replace("token_", "")
            token = remainder.split("_")[0]
            supplier_name, page_str = _decode_pair_from_token(token)
            if not supplier_name:
                raise ValueError("Unknown token")
            page = int(page_str) if page_str and page_str.isdigit() else 0
        else:
            parts = payload.split("_")
            if len(parts) < 2:
                raise ValueError("Not enough parts")
            supplier_name = parts[0]
            page = int(parts[1])
    except Exception:
        await edit_by_callback(callback, text="Invalid request", photo_path="котлета.jpg", parse_mode="HTML")
        return

    bins = get_bins_for_supplier(supplier_name)

    if not bins:
        await edit_by_callback(callback, text="BINs not found", photo_path="котлета.jpg", parse_mode="HTML")
        return

    countries_dict = {}
    for bin_item in bins:
        country = bin_item.get('country', 'Unknown')
        if country not in countries_dict:
            countries_dict[country] = []
        countries_dict[country].append(bin_item)

    countries = sorted(list(countries_dict.keys()))
    await show_seller_countries_page(callback, supplier_name, countries, page)

@router.callback_query(F.data.startswith("seller_country_"))
async def seller_country_selected_handler(callback: CallbackQuery):
    payload = callback.data
    try:
        if payload.startswith("seller_country_token_"):
            remainder = payload.replace("seller_country_token_", "")
            token = remainder
            supplier_name, country_name = _decode_pair_from_token(token)
            if not supplier_name:
                raise ValueError("Unknown token")
        else:
            parts = payload.replace("seller_country_", "").split("_", 1)
            if len(parts) < 2:
                raise ValueError("Not enough parts")
            supplier_name = parts[0]
            country_name = parts[1]
    except Exception:
        await edit_by_callback(callback, text="Invalid request", photo_path="котлета.jpg", parse_mode="HTML")
        return

    bins = get_bins_for_supplier(supplier_name)
    country_bins = [b for b in bins if b.get('country', 'Unknown') == country_name]

    if not country_bins:
        await edit_by_callback(callback, text="BINs for this country not found", photo_path="котлета.jpg")
        return

    await show_seller_country_bins_page(callback, supplier_name, country_name, country_bins, 0)

async def show_seller_country_bins_page(callback: CallbackQuery, supplier_name: str, country_name: str, bins: list, page: int):
    bins_per_page = 20
    total_pages = (len(bins) + bins_per_page - 1) // bins_per_page

    if page < 0:
        page = 0
    if page >= total_pages:
        page = total_pages - 1

    start_idx = page * bins_per_page
    end_idx = start_idx + bins_per_page
    page_bins = bins[start_idx:end_idx]

    bin_buttons = []
    for i in range(0, len(page_bins), 2):
        row = []
        for j in range(2):
            if i + j < len(page_bins):
                bin_item = page_bins[i + j]
                flag = bin_item.get('flag', '')
                bin_code = bin_item['bin']
                price = bin_item.get('price', 0.0)
                display = f"{flag} {bin_code} - {price}$".strip()
                cb = _force_token_callback('seller_bin', supplier_name, country_name, bin_code)
                row.append(InlineKeyboardButton(text=display, callback_data=cb))
        if row:
            bin_buttons.append(row)

    nav_buttons = []
    if page > 0:
        prev_cb = _force_token_callback('seller_bins_page', supplier_name, country_name, str(page-1))
        nav_buttons.append(InlineKeyboardButton(text="◀️ Prev", callback_data=prev_cb))
    if page < total_pages - 1:
        next_cb = _force_token_callback('seller_bins_page', supplier_name, country_name, str(page+1))
        nav_buttons.append(InlineKeyboardButton(text="Next ▶️", callback_data=next_cb))
    if nav_buttons:
        bin_buttons.append(nav_buttons)

    bin_buttons.append([InlineKeyboardButton(text="🏳️ Back to countries", callback_data=f"seller_select_{supplier_name}")])
    bin_buttons.insert(1, [InlineKeyboardButton(text="🔙 Back to BINs", callback_data=_force_token_callback('seller_country', supplier_name, country_name))])
    bin_buttons.append([InlineKeyboardButton(text="🔙 Back to menu", callback_data="buy_item")])

    keyboard = InlineKeyboardMarkup(inline_keyboard=bin_buttons)
    caption = f"🏪 {supplier_name}\n🌍 {country_name}\n\n📋 BINs (Page {page + 1}/{total_pages})"
    await edit_by_callback(callback, text=caption, photo_path="котлета.jpg", reply_markup=keyboard, parse_mode="HTML")

@router.callback_query(F.data.startswith("seller_bins_page_"))
async def seller_bins_page_handler(callback: CallbackQuery):
    parts = callback.data.replace("seller_bins_page_", "").split("_", 2)
    if len(parts) < 1:
        await edit_by_callback(callback, text="Invalid request", photo_path="котлета.jpg")
        return

    try:
        if parts[0] == 'token':
            remainder = callback.data.replace("seller_bins_page_token_", "")
            token, page_str = remainder.split("_", 1)
            page = int(page_str)
            supplier_name, country_name = _decode_pair_from_token(token)
            if not supplier_name:
                raise ValueError("Unknown token")
        else:
            if len(parts) < 3:
                raise ValueError("Not enough parts")
            supplier_name = parts[0]
            country_name = parts[1]
            page = int(parts[2])
    except Exception:
        await edit_by_callback(callback, text="Invalid request", photo_path="котлета.jpg")
        return

    bins = get_bins_for_supplier(supplier_name)
    country_bins = [b for b in bins if b.get('country', 'Unknown') == country_name]

    if not country_bins:
        await edit_by_callback(callback, text="BINs not found", photo_path="котлета.jpg", parse_mode="HTML")
        return

    await show_seller_country_bins_page(callback, supplier_name, country_name, country_bins, page)

@router.callback_query(F.data.startswith("seller_bin_"))
async def seller_bin_selected_handler(callback: CallbackQuery):
    payload = callback.data.replace("seller_bin_", "")
    parts = payload.split("_", 2)
    if len(parts) < 1:
        await edit_by_callback(callback, text="Invalid BIN", photo_path="котлета.jpg", parse_mode="HTML")
        return

    try:
        if parts[0] == 'token':
            remainder = payload.replace("token_", "")
            token, bin_code = remainder.split("_", 1)
            supplier_name, country_name = _decode_pair_from_token(token)
            if not supplier_name:
                raise ValueError("Unknown token")
        else:
            if len(parts) < 3:
                raise ValueError("Not enough parts")
            supplier_name = parts[0]
            country_name = parts[1]
            bin_code = parts[2]
    except Exception:
        await edit_by_callback(callback, text="Invalid BIN", photo_path="котлета.jpg")
        return

    bins = get_bins_for_supplier(supplier_name)
    found = None
    for item in bins:
        if item['bin'] == bin_code and item.get('country', 'Unknown') == country_name:
            found = item
            break

    if not found:
        await edit_by_callback(callback, text="BIN not found", photo_path="котлета.jpg", parse_mode="HTML")
        return

    display = found['display'] if 'display' in found else f"{found.get('flag', '')} {bin_code}".strip()
    b = found['bin']
    price = found.get('price', 0.0)
    bank = found.get('bank', '')
    brand = found.get('brand', '')
    card_type = found.get('type', '')
    level = found.get('level', '')
    country = found.get('country', '')
    pcs = found.get('pcs', 0)

    # Display supplier name as lowercase 'admin'/'zeus' when canonical
    supplier_display = supplier_name if supplier_name else "Unknown"
    import html
    supplier_escaped = html.escape(supplier_display)
    display_escaped = html.escape(display)
    b_escaped = html.escape(b)
    country_escaped = html.escape(country)
    brand_escaped = html.escape(brand)
    type_escaped = html.escape(card_type)
    level_escaped = html.escape(level)
    bank_escaped = html.escape(bank)
    price_escaped = html.escape(str(price))
    pcs_escaped = html.escape(str(pcs))

    caption = (
        f"🏪 SELLER: <b>{supplier_escaped}</b>\n\n"
        f"📜 NAME: <b>{display_escaped}</b>\n\n"
        f"💳 BIN: <b>{b_escaped}</b>\n"
        f"🏴 COUNTRY: <b>{country_escaped}</b>\n"
        f"🧳 BRAND: <b>{brand_escaped}</b>\n"
        f"💸 TYPE: <b>{type_escaped}</b>\n"
        f"🔑 LEVEL: <b>{level_escaped}</b>\n"
        f"🏦 BANK: <b>{bank_escaped}</b>\n\n"
        f"💸 Price: <b>{price_escaped} $</b>\n"
        f"💳 In stock: <b>{pcs_escaped} pcs.</b>"
    )

    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="💸 Buy", callback_data=f"buy_supplier_{supplier_name}_{b}"),
            InlineKeyboardButton(text="✅ Autocheck", callback_data=f"autocheck_supplier_{supplier_name}_{b}")
        ],
        [InlineKeyboardButton(text="🔙 Back to BINs", callback_data=_force_token_callback('seller_country', supplier_name, country_name))],
        [InlineKeyboardButton(text="🔙 Back to menu", callback_data="buy_item")]
    ])
    await edit_by_callback(callback, text=caption, photo_path="котлета.jpg", reply_markup=keyboard, parse_mode="HTML")

@router.callback_query(F.data.startswith("buy_supplier_"))
async def buy_supplier_handler(callback: CallbackQuery):
    payload = callback.data.replace("buy_supplier_", "")
    country_name = "Unknown"
    try:
        if payload.startswith("token_"):
            remainder = payload.replace("token_", "")
            token, bin_code = remainder.split("_", 1)
            supplier_name, country_name = _decode_pair_from_token(token)
            if not supplier_name:
                raise ValueError("Unknown token")
        else:
            parts = payload.split("_", 1)
            if len(parts) < 2:
                raise ValueError("Not enough parts")
            supplier_name = parts[0]
            bin_code = parts[1]
    except Exception:
        await edit_by_callback(callback, text="Invalid purchase request", photo_path="котлета.jpg", parse_mode="HTML")
        return

    bins = get_bins_for_supplier(supplier_name)
    target = None
    for item in bins:
        if item.get('bin') == bin_code:
            target = item
            break

    if not target:
        await edit_by_callback(callback, text="BIN not found", photo_path="котлета.jpg", parse_mode="HTML")
        return

    price = float(target.get('price', 0.0))

    user_id = callback.from_user.id
    profile = None
    try:
        profile = get_user_profile(user_id)
    except Exception as e:
        print(f"Error fetching profile: {e}")

    balance = profile[6] if profile and len(profile) > 6 and profile[6] is not None else 0.0

    if balance < price:
        await callback.answer(f"❌ Insufficient balance. Price: ${price:.2f}, your balance: ${balance:.2f}", show_alert=True)
        return

    ok = update_user_balance(user_id, -price)
    if not ok:
        await edit_by_callback(callback, text="❌ Failed to deduct balance. Try again later.", photo_path="котлета.jpg", parse_mode="HTML")
        return

    supplied_text = ""

    bin_prefix = bin_code
    # Always generate Luhn-complete card number and basic product info for purchases
    card_number = luhn_complete(bin_prefix, 16)
    # Min expiry: June 2026. Generate random future date within 26-29 range.
    _exp_year = random.randint(26, 29)
    _exp_month = random.randint(6, 12) if _exp_year == 26 else random.randint(1, 12)
    exp = f"{_exp_month:02d}/{_exp_year}"
    cvv = f"{random.randint(0,999):03d}"
    # Always return product as number|date|cvv for all suppliers
    supplied_text = f"{card_number}|{exp}|{cvv}"

    try:
        add_card_sale(user_id, supplier_name, bin_code, supplied_text, price, country_name)
    except Exception as e:
        print(f"Error recording sale: {e}")
    # Build exact receipt as requested by the user
    import html
    from datetime import datetime

    # Get updated balance
    try:
        profile_after = get_user_profile(user_id)
        balance_after = profile_after[6] if profile_after and len(profile_after) > 6 and profile_after[6] is not None else 0.0
    except Exception:
        balance_after = 0.0

    now = datetime.now()
    date_str = now.strftime("%Y-%m-%d")
    time_str = now.strftime("%H:%M:%S")

    seller_display = supplier_name.upper() if supplier_name.upper() in ('ADMIN', 'ZEUS') else supplier_name
    seller_esc = html.escape(seller_display)
    country_esc = html.escape(target.get('country', ''))
    bin_esc = html.escape(bin_code)
    charged_esc = html.escape(f"{price:.2f}")
    balance_esc = html.escape(f"{balance_after:.2f}")
    product_esc = html.escape(supplied_text or 'Товар')

    receipt = (
        f"🛍️ Purchase completed successfully \n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"🛒 Seller: {seller_esc}\n"
        f"🏳️ Country: {country_esc}\n"
        f"🔢 BIN: {bin_esc}\n"
        f"💰 Charged: {charged_esc} $\n"
        f"💳 Balance after purchase: {balance_esc} $\n"
        f"📆 Date: {date_str}\n"
        f"⏰ Time: {time_str}\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"📦 Product:\n"
        f"{product_esc}\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"🥳 Thank you for your purchase!"
    )

    await edit_by_callback(callback, text=receipt, photo_path="котлета.jpg", parse_mode="HTML")


@router.callback_query(F.data.startswith("buy_search_"))
async def buy_search_handler(callback: CallbackQuery):
    bin_code = callback.data.replace("buy_search_", "")

    # Find the BIN across all suppliers
    suppliers = get_all_suppliers_from_files()
    target = None
    supplier_name = None
    for s in suppliers:
        bins = get_bins_for_supplier(s)
        for item in bins:
            if item.get('bin') == bin_code:
                target = item
                supplier_name = s
                break
        if target:
            break

    if not target:
        await edit_by_callback(callback, text="BIN not found", photo_path="котлета.jpg", parse_mode="HTML")
        return

    price = float(target.get('price', 0.0))
    user_id = callback.from_user.id
    profile = None
    try:
        profile = get_user_profile(user_id)
    except Exception as e:
        print(f"Error fetching profile: {e}")

    balance = profile[6] if profile and len(profile) > 6 and profile[6] is not None else 0.0

    if balance < price:
        await callback.answer(f"❌ Insufficient balance. Price: ${price:.2f}, your balance: ${balance:.2f}", show_alert=True)
        return

    ok = update_user_balance(user_id, -price)
    if not ok:
        await edit_by_callback(callback, text="❌ Failed to deduct balance. Try again later.", photo_path="котлета.jpg", parse_mode="HTML")
        return

    # Generate product (use same Luhn helper)
    supplied_text = ""
    bin_prefix = bin_code

    # Always generate Luhn-complete card number and basic product info for purchases
    card_number = luhn_complete(bin_prefix, 16)
    # Min expiry: June 2026. Generate random future date within 26-29 range.
    _exp_year = random.randint(26, 29)
    _exp_month = random.randint(6, 12) if _exp_year == 26 else random.randint(1, 12)
    exp = f"{_exp_month:02d}/{_exp_year}"
    cvv = f"{random.randint(0,999):03d}"
    # Always return product as number|date|cvv for all suppliers
    supplied_text = f"{card_number}|{exp}|{cvv}"

    try:
        add_card_sale(user_id, supplier_name, bin_code, supplied_text, price, target.get('country', 'Unknown'))
    except Exception as e:
        print(f"Error recording sale: {e}")

    # Build receipt (same template)
    import html
    from datetime import datetime

    try:
        profile_after = get_user_profile(user_id)
        balance_after = profile_after[6] if profile_after and len(profile_after) > 6 and profile_after[6] is not None else 0.0
    except Exception:
        balance_after = 0.0

    now = datetime.now()
    date_str = now.strftime("%Y-%m-%d")
    time_str = now.strftime("%H:%M:%S")

    seller_display = supplier_name.upper() if supplier_name.upper() in ('ADMIN', 'ZEUS') else supplier_name
    seller_esc = html.escape(seller_display)
    country_esc = html.escape(target.get('country', ''))
    bin_esc = html.escape(bin_code)
    charged_esc = html.escape(f"{price:.2f}")
    balance_esc = html.escape(f"{balance_after:.2f}")
    product_esc = html.escape(supplied_text or 'Товар')

    receipt = (
        f"🛍️ Purchase completed successfully \n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"🛒 Seller: {seller_esc}\n"
        f"🏳️ Country: {country_esc}\n"
        f"🔢 BIN: {bin_esc}\n"
        f"💰 Charged: {charged_esc} $\n"
        f"💳 Balance after purchase: {balance_esc} $\n"
        f"📆 Date: {date_str}\n"
        f"⏰ Time: {time_str}\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"📦 Product:\n"
        f"{product_esc}\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"🥳 Thank you for your purchase!"
    )

    await edit_by_callback(callback, text=receipt, photo_path="котлета.jpg", parse_mode="HTML")

    try:
        await callback.message.bot.send_message(
            chat_id=ADMIN_ID,
            text=f"ℹ️ New purchase by user @{callback.from_user.username or callback.from_user.id}. Product: {supplier_name} BIN {bin_code}. Price: ${price:.2f}"
        )
    except Exception as e:
        print(f"Failed to notify admin about purchase: {e}")

@router.callback_query(F.data.startswith("buy_"))
async def buy_country_handler(callback: CallbackQuery):
    # Ignore other buy handlers
    if callback.data.startswith("buy_supplier_") or callback.data.startswith("buy_search_"):
        return

    payload = callback.data.replace("buy_", "")
    parts = payload.split("_", 1)
    if len(parts) < 2:
        await callback.answer("Invalid purchase request", show_alert=True)
        return

    try:
        country_idx = int(parts[0])
        bin_code = parts[1]
    except Exception:
        await callback.answer("Invalid purchase request", show_alert=True)
        return

    try:
        countries = get_countries()
        country_display = countries[country_idx]
    except Exception:
        await edit_by_callback(callback, text="Country not found", photo_path="котлета.jpg", parse_mode="HTML")
        return

    bins = get_bins_for_country_all(country_display)
    target = None
    for item in bins:
        if item.get('bin') == bin_code:
            target = item
            break

    if not target:
        await edit_by_callback(callback, text="BIN not found", photo_path="котлета.jpg", parse_mode="HTML")
        return

    price = float(target.get('price', 0.0))
    user_id = callback.from_user.id
    try:
        profile = get_user_profile(user_id)
    except Exception as e:
        print(f"Error fetching profile: {e}")
        profile = None

    balance = profile[6] if profile and len(profile) > 6 and profile[6] is not None else 0.0
    if balance < price:
        await callback.answer(f"❌ Insufficient balance. Price: ${price:.2f}, your balance: ${balance:.2f}", show_alert=True)
        return

    ok = update_user_balance(user_id, -price)
    if not ok:
        await edit_by_callback(callback, text="❌ Failed to deduct balance. Try again later.", photo_path="котлета.jpg", parse_mode="HTML")
        return

    # Generate Luhn product always: номер|дата|cvv
    bin_prefix = bin_code
    card_number = luhn_complete(bin_prefix, 16)
    # Min expiry: June 2026. Generate random future date within 26-29 range.
    _exp_year = random.randint(26, 29)
    _exp_month = random.randint(6, 12) if _exp_year == 26 else random.randint(1, 12)
    exp = f"{_exp_month:02d}/{_exp_year}"
    cvv = f"{random.randint(0,999):03d}"
    supplied_text = f"{card_number}|{exp}|{cvv}"

    try:
        supplier_name = target.get('supplier_name', 'UNKNOWN')
        add_card_sale(user_id, supplier_name, bin_code, supplied_text, price, target.get('country', 'Unknown'))
    except Exception as e:
        print(f"Error recording sale: {e}")

    # Build and send receipt
    import html
    from datetime import datetime
    try:
        profile_after = get_user_profile(user_id)
        balance_after = profile_after[6] if profile_after and len(profile_after) > 6 and profile_after[6] is not None else 0.0
    except Exception:
        balance_after = 0.0

    now = datetime.now()
    date_str = now.strftime("%Y-%m-%d")
    time_str = now.strftime("%H:%M:%S")

    seller_display = supplier_name.upper() if supplier_name and supplier_name.upper() in ('ADMIN','ZEUS') else supplier_name
    seller_esc = html.escape(seller_display)
    country_esc = html.escape(target.get('country', ''))
    bin_esc = html.escape(bin_code)
    charged_esc = html.escape(f"{price:.2f}")
    balance_esc = html.escape(f"{balance_after:.2f}")
    product_esc = html.escape(supplied_text)

    receipt = (
        f"🛍️ Purchase completed successfully \n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"🛒 Seller: {seller_esc}\n"
        f"🏳️ Country: {country_esc}\n"
        f"🔢 BIN: {bin_esc}\n"
        f"💰 Charged: {charged_esc} $\n"
        f"💳 Balance after purchase: {balance_esc} $\n"
        f"📆 Date: {date_str}\n"
        f"⏰ Time: {time_str}\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"📦 Product:\n"
        f"{product_esc}\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"🥳 Thank you for your purchase!"
    )

    await edit_by_callback(callback, text=receipt, photo_path="котлета.jpg", parse_mode="HTML")

@router.callback_query(F.data == "search_by_bin")
async def search_by_bin_handler(callback: CallbackQuery, state: FSMContext):
    text = """🔍 <b>Search by BIN</b>
━━━━━━━━━━━━━━━━━━━━
Send 3–8 digits of BIN, e.g. 558668."""

    back_button = InlineKeyboardButton(text="◀️ Back", callback_data="buy_item")
    keyboard = InlineKeyboardMarkup(inline_keyboard=[[back_button]])
    await edit_by_callback(callback, text=text, photo_path="котлета.jpg", reply_markup=keyboard, parse_mode="HTML")

    await state.set_state(SearchStates.waiting_for_bin)

@router.message(SearchStates.waiting_for_bin)
async def process_bin_search(message: Message, state: FSMContext):
    bin_input = message.text.strip()

    if not bin_input.isdigit() or not (3 <= len(bin_input) <= 8):
        await safe_send_photo(message, "❌ Invalid BIN. Please send 3–8 digits. Example: 558668"
        )
        return

    # Логируем поисковый запрос
    from database import log_bin_search
    user_id = message.from_user.id
    username = message.from_user.username or message.from_user.first_name or "Unknown"
    log_bin_search(user_id, username, bin_input)

    matching_bins = []
    suppliers = get_all_suppliers_from_files()

    for supplier in suppliers:
        bins = get_bins_for_supplier(supplier)
        matching_bins.extend([bin_item for bin_item in bins if bin_item['bin'].startswith(bin_input)])

    # Перераспределяем поставщиков равномерно
    from import_sellers_fixed import redistribute_suppliers_evenly
    matching_bins = redistribute_suppliers_evenly(matching_bins)

    # Фильтруем пустые элементы и проверяем наличие результатов
    matching_bins = [b for b in matching_bins if b and b.get('bin')]
    
    if not matching_bins or len(matching_bins) == 0:
        keyboard = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="◀️ Back", callback_data="buy_item")]])
        await safe_send_photo(message, f"❌ BINs starting with '{bin_input}' not found.", reply_markup=keyboard, parse_mode="HTML")
        await state.clear()
        return

    await show_bin_search_results_new(message, bin_input, matching_bins, 0)
    await state.clear()

async def show_bin_search_results_new(message: Message, bin_input: str, bins: list, page: int):
    import html
    bins_per_page = 20
    total_pages = (len(bins) + bins_per_page - 1) // bins_per_page

    if page < 0:
        page = 0
    if page >= total_pages:
        page = total_pages - 1

    start_idx = page * bins_per_page
    end_idx = start_idx + bins_per_page
    page_bins = bins[start_idx:end_idx]

    caption = f"🔍 Search results for: <b>{html.escape(bin_input)}</b>\n\n📊 Found: {len(bins)} BINs (Page {page + 1}/{total_pages})"

    buttons = []
    for i in range(0, len(page_bins), 2):
        row = []
        for j in range(2):
            if i + j < len(page_bins):
                item = page_bins[i + j]
                flag = item.get('flag', '')
                b = item['bin']
                price = item.get('price', 0.0)
                supplier = item.get('supplier_name', 'Unknown')
                bin_display = f"{flag} {b}".strip()
                text = f"{bin_display} | {price}$"
                row.append(InlineKeyboardButton(text=text, callback_data=f"search_bin_{page}_{b}_{supplier}"))
        if row:
            buttons.append(row)

    nav_buttons = []
    if page > 0:
        nav_buttons.append(InlineKeyboardButton(text="◀️ Prev", callback_data=f"search_bin_page_{bin_input}_{page-1}"))
    if page < total_pages - 1:
        nav_buttons.append(InlineKeyboardButton(text="Next ▶️", callback_data=f"search_bin_page_{bin_input}_{page+1}"))
    if nav_buttons:
        buttons.append(nav_buttons)

    buttons.append([InlineKeyboardButton(text="🔍 Back to search", callback_data="search_by_bin")])
    buttons.append([InlineKeyboardButton(text="◀️ Back to menu", callback_data="buy_item")])

    keyboard = InlineKeyboardMarkup(inline_keyboard=buttons)
    await safe_send_photo(message, caption, reply_markup=keyboard, parse_mode="HTML")

async def show_bin_search_results(message: Message, bin_input: str, bins: list, page: int):
    import html
    bins_per_page = 20
    total_pages = (len(bins) + bins_per_page - 1) // bins_per_page

    if page < 0:
        page = 0
    if page >= total_pages:
        page = total_pages - 1

    start_idx = page * bins_per_page
    end_idx = start_idx + bins_per_page
    page_bins = bins[start_idx:end_idx]

    caption = f"🔍 Search results for: <b>{html.escape(bin_input)}</b>\n\n📊 Found: {len(bins)} BINs (Page {page + 1}/{total_pages})"

    buttons = []
    for i in range(0, len(page_bins), 2):
        row = []
        for j in range(2):
            if i + j < len(page_bins):
                item = page_bins[i + j]
                flag = item.get('flag', '')
                b = item['bin']
                price = item.get('price', 0.0)
                supplier = item.get('supplier_name', 'Unknown')
                bin_display = f"{flag} {b}".strip()
                text = f"{bin_display} | {price}$"
                row.append(InlineKeyboardButton(text=text, callback_data=f"search_bin_{page}_{b}_{supplier}"))
        if row:
            buttons.append(row)

    nav_buttons = []
    if page > 0:
        nav_buttons.append(InlineKeyboardButton(text="◀️ Prev", callback_data=f"search_bin_page_{bin_input}_{page-1}"))
    if page < total_pages - 1:
        nav_buttons.append(InlineKeyboardButton(text="Next ▶️", callback_data=f"search_bin_page_{bin_input}_{page+1}"))
    if nav_buttons:
        buttons.append(nav_buttons)

    buttons.append([InlineKeyboardButton(text="🔍 Back to search", callback_data="search_by_bin")])
    buttons.append([InlineKeyboardButton(text="◀️ Back to menu", callback_data="buy_item")])

    keyboard = InlineKeyboardMarkup(inline_keyboard=buttons)
    await edit_by_message(message, text=caption, photo_path="котлета.jpg", reply_markup=keyboard, parse_mode="HTML")

@router.callback_query(F.data.startswith("search_bin_page_"))
async def search_bin_page_handler(callback: CallbackQuery):
    parts = callback.data.replace("search_bin_page_", "").split("_")
    if len(parts) < 2:
        await edit_by_callback(callback, text="Invalid request", photo_path="котлета.jpg")
        return

    try:
        bin_input = parts[0]
        page = int(parts[1])
    except Exception:
        await edit_by_callback(callback, text="Invalid request", photo_path="котлета.jpg")
        return

    matching_bins = []
    suppliers = get_all_suppliers_from_files()

    for supplier in suppliers:
        bins = get_bins_for_supplier(supplier)
        matching_bins.extend([bin_item for bin_item in bins if bin_item['bin'].startswith(bin_input)])

    # Перераспределяем поставщиков равномерно
    from import_sellers_fixed import redistribute_suppliers_evenly
    matching_bins = redistribute_suppliers_evenly(matching_bins)

    if not matching_bins:
        await edit_by_callback(callback, text="BINs not found", photo_path="котлета.jpg")
        return

    await show_bin_search_results(callback.message, bin_input, matching_bins, page)

@router.callback_query(F.data.startswith("search_bin_"))
async def search_bin_selected_handler(callback: CallbackQuery):
    # Проверяем, что это не пагинация
    if callback.data.startswith("search_bin_page_"):
        return
    
    parts = callback.data.replace("search_bin_", "").split("_", 2)
    if len(parts) < 3:
        await edit_by_callback(callback, text="Invalid BIN", photo_path="котлета.jpg")
        return

    try:
        page = int(parts[0])
        b = parts[1]
        supplier = parts[2]
    except Exception:
        await edit_by_callback(callback, text="Invalid BIN", photo_path="котлета.jpg")
        return

    # Ищем бин во всех поставщиках
    bins = get_bins_for_supplier(supplier)
    found = None
    for item in bins:
        if item and item.get('bin') == b:
            found = item
            break

    # Если не нашли у конкретного поставщика, ищем везде
    if not found:
        suppliers = get_all_suppliers_from_files()
        for sup in suppliers:
            bins = get_bins_for_supplier(sup)
            for item in bins:
                if item and item.get('bin') == b:
                    found = item
                    supplier = sup
                    break
            if found:
                break

    if not found:
        await edit_by_callback(callback, text="BIN not found", photo_path="котлета.jpg")
        return

    flag = found.get('flag', '')
    bin_code = found['bin']
    display = f"{flag} {bin_code}".strip()
    price = found.get('price', 0.0)
    bank = found.get('bank', '')
    brand = found.get('brand', '')
    card_type = found.get('type', '')
    level = found.get('level', '')
    country = found.get('country', '')
    pcs = found.get('pcs', 0)
    supplier_name = found.get('supplier_name', 'UNKNOWN')

    bin_input = b[:6] if len(b) >= 6 else b

    # Display supplier name as lowercase 'admin'/'zeus' when canonical
    supplier_display = supplier_name if supplier_name else "Unknown"
    import html
    supplier_escaped = html.escape(supplier_display)
    display_escaped = html.escape(display)
    b_escaped = html.escape(bin_code)
    country_escaped = html.escape(country)
    brand_escaped = html.escape(brand)
    type_escaped = html.escape(card_type)
    level_escaped = html.escape(level)
    bank_escaped = html.escape(bank)
    price_escaped = html.escape(str(price))
    pcs_escaped = html.escape(str(pcs))

    caption = (
        f"🏪 SELLER: <b>{supplier_escaped}</b>\n\n"
        f"📜 NAME: <b>{display_escaped}</b>\n\n"
        f"💳 BIN: <b>{b_escaped}</b>\n"
        f"🏴 COUNTRY: <b>{country_escaped}</b>\n"
        f"🧳 BRAND: <b>{brand_escaped}</b>\n"
        f"💸 TYPE: <b>{type_escaped}</b>\n"
        f"🔑 LEVEL: <b>{level_escaped}</b>\n"
        f"🏦 BANK: <b>{bank_escaped}</b>\n\n"
        f"💸 Price: <b>{price_escaped} $</b>\n"
        f"💳 In stock: <b>{pcs_escaped} pcs.</b>"
    )

    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="💸 Buy", callback_data=f"buy_search_{b}"),
            InlineKeyboardButton(text="✅ Autocheck", callback_data=f"autocheck_search_{b}")
        ],
        [InlineKeyboardButton(text="🔍 Back to results", callback_data=f"search_bin_page_{bin_input}_{page}")],
        [InlineKeyboardButton(text="◀️ Back to menu", callback_data="search_by_bin")]
    ])
    await edit_by_callback(callback, text=caption, photo_path="котлета.jpg", reply_markup=keyboard, parse_mode="HTML")

@router.callback_query(F.data == "support_chat")
async def support_chat_handler(callback: CallbackQuery, state: FSMContext):
    text = """🆘 <b>Support Chat</b>
━━━━━━━━━━━━━━━━━━━━
Send your message and our team will answer as soon as possible.
(Your message will be sent anonymously)"""

    back_button = InlineKeyboardButton(text="◀️ Back", callback_data="cancel_support")
    keyboard = InlineKeyboardMarkup(inline_keyboard=[[back_button]])
    await edit_by_callback(callback, text=text, photo_path="котлета.jpg", reply_markup=keyboard, parse_mode="HTML")

    await state.set_state(SupportStates.waiting_for_message)

@router.callback_query(F.data == "cancel_support")
async def cancel_support_handler(callback: CallbackQuery, state: FSMContext):
    user_id = callback.from_user.id
    message = callback.message

    message_id = message.message_id
    chat_id = message.chat.id

    await state.update_data(support_canceled=True)

    await edit_by_callback(callback, text="❌ Support request canceled.", photo_path="котлета.jpg", parse_mode="HTML")

    await asyncio.sleep(3)

    try:
        await callback.message.bot.delete_message(chat_id=chat_id, message_id=message_id)
    except Exception as e:
        print(f"Failed to delete message: {e}")

    await callback.answer()
    await main_menu_handler(callback)

@router.message(SupportStates.waiting_for_message)
async def process_support_message(message: Message, state: FSMContext):
    current_state = await state.get_state()
    if current_state is None:
        return

    if current_state != SupportStates.waiting_for_message:
        await state.clear()
        return

    data = await state.get_data()

    if data.get('support_canceled', False):
        await state.clear()
        return

    user_id = message.from_user.id
    username = message.from_user.username or "Unknown"
    user_message = message.text or message.caption or ""
    await state.update_data(support_canceled=False)

    header = (
        f"📩 <b>New Support Message</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"👤 From: @{username} (ID: {user_id})"
        + (f"\n💬 Message:\n{user_message}" if user_message else "")
    )

    reply_button = InlineKeyboardButton(text="💬 Reply", callback_data=f"reply_support_{user_id}")
    keyboard = InlineKeyboardMarkup(inline_keyboard=[[reply_button]])

    try:
        if message.photo:
            await message.bot.send_photo(chat_id=ADMIN_ID, photo=message.photo[-1].file_id, caption=header, reply_markup=keyboard, parse_mode="HTML")
        elif message.video:
            await message.bot.send_video(chat_id=ADMIN_ID, video=message.video.file_id, caption=header, reply_markup=keyboard, parse_mode="HTML")
        elif message.document:
            await message.bot.send_document(chat_id=ADMIN_ID, document=message.document.file_id, caption=header, reply_markup=keyboard, parse_mode="HTML")
        elif message.sticker:
            await message.bot.send_message(chat_id=ADMIN_ID, text=header, parse_mode="HTML")
            await message.bot.send_sticker(chat_id=ADMIN_ID, sticker=message.sticker.file_id, reply_markup=keyboard)
        elif message.voice:
            await message.bot.send_voice(chat_id=ADMIN_ID, voice=message.voice.file_id, caption=header, reply_markup=keyboard, parse_mode="HTML")
        else:
            await message.bot.send_message(chat_id=ADMIN_ID, text=header, reply_markup=keyboard, parse_mode="HTML")
    except Exception as e:
        print(f"Error sending support message to admin: {e}")

    await state.update_data(support_active=True, user_id=user_id, username=username)
    await state.set_state(SupportStates.in_chat)
    await safe_send_photo(message, text="✅ Message sent! Waiting for support reply...\nFor main menu - /start", photo_path="котлета.jpg", parse_mode="HTML")

@router.callback_query(F.data.startswith("reply_support_"))
async def reply_support_handler(callback: CallbackQuery, state: FSMContext):
    user_id_str = callback.data.replace("reply_support_", "")
    try:
        user_id = int(user_id_str)
    except Exception:
        await edit_by_callback(callback, text="Invalid user ID", photo_path="котлета.jpg")
        return

    await state.update_data(support_user_id=user_id)
    await state.set_state(SupportStates.admin_in_chat)
    await edit_by_callback(callback, text=f"💬 <b>Chat with user {user_id}</b>\n\n(Type a message to send to user, or /end to close chat)", photo_path="котлета.jpg", parse_mode="HTML")

@router.message(SupportStates.admin_in_chat)
async def process_admin_chat_message(message: Message, state: FSMContext):
    data = await state.get_data()
    support_user_id = data.get('support_user_id')

    if not support_user_id:
        await edit_by_message(message, text="❌ Error: User ID not found", photo_path="котлета.jpg", parse_mode="HTML")
        await state.clear()
        return

    if message.text == "/end":
        await edit_by_message(message, text="❌ Chat ended", photo_path="котлета.jpg", parse_mode="HTML")
        await state.clear()
        return

    user_text = f"""💬 <b>Support Reply</b>
━━━━━━━━━━━━━━━━━━━━
{message.text}"""

    continue_button = InlineKeyboardButton(text="💬 Continue Chat", callback_data="continue_support_chat")
    keyboard = InlineKeyboardMarkup(inline_keyboard=[[continue_button]])
    try:
        await message.bot.send_photo(
            chat_id=support_user_id,
            photo=FSInputFile("котлета.jpg"),
            caption=user_text,
            reply_markup=keyboard,
            parse_mode="HTML"
        )
        await edit_by_message(message, text="✅ Message sent! Waiting for user reply... (Type /end to exit)", photo_path="котлета.jpg", parse_mode="HTML")
    except Exception as e:
        print(f"Error sending message to user: {e}")
        await edit_by_message(message, text=f"❌ Error: {e}", photo_path="котлета.jpg", parse_mode="HTML")

@router.callback_query(F.data == "continue_support_chat")
async def continue_support_chat_handler(callback: CallbackQuery, state: FSMContext):
    await state.update_data(support_active=True)
    await state.set_state(SupportStates.in_chat)
    await edit_by_callback(callback, text="📝 Type your message:", photo_path="котлета.jpg")

@router.message(SupportStates.in_chat)
async def process_user_chat_message(message: Message, state: FSMContext):
    user_id = message.from_user.id
    username = message.from_user.username or "Unknown"
    user_message = message.text or message.caption or ""

    if message.text == "/end":
        await safe_send_photo(message, text="❌ Chat ended. Type /start to return to menu", photo_path="котлета.jpg", parse_mode="HTML")
        await state.clear()
        return

    header = (
        f"📨 <b>User Message</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"👤 From: @{username} (ID: {user_id})"
        + (f"\n💬 Message:\n{user_message}" if user_message else "")
    )

    reply_button = InlineKeyboardButton(text="💬 Reply", callback_data=f"reply_support_{user_id}")
    end_button = InlineKeyboardButton(text="❌ End Chat", callback_data=f"end_support_{user_id}")
    keyboard = InlineKeyboardMarkup(inline_keyboard=[[reply_button, end_button]])

    try:
        if message.photo:
            await message.bot.send_photo(chat_id=ADMIN_ID, photo=message.photo[-1].file_id, caption=header, reply_markup=keyboard, parse_mode="HTML")
        elif message.video:
            await message.bot.send_video(chat_id=ADMIN_ID, video=message.video.file_id, caption=header, reply_markup=keyboard, parse_mode="HTML")
        elif message.document:
            await message.bot.send_document(chat_id=ADMIN_ID, document=message.document.file_id, caption=header, reply_markup=keyboard, parse_mode="HTML")
        elif message.sticker:
            await message.bot.send_message(chat_id=ADMIN_ID, text=header, parse_mode="HTML")
            await message.bot.send_sticker(chat_id=ADMIN_ID, sticker=message.sticker.file_id, reply_markup=keyboard)
        elif message.voice:
            await message.bot.send_voice(chat_id=ADMIN_ID, voice=message.voice.file_id, caption=header, reply_markup=keyboard, parse_mode="HTML")
        else:
            await message.bot.send_message(chat_id=ADMIN_ID, text=header, reply_markup=keyboard, parse_mode="HTML")
    except Exception as e:
        print(f"Error sending message to admin: {e}")

    await safe_send_photo(message, text="✅ Message sent! Waiting for support reply...\nFor main menu - /start", photo_path="котлета.jpg", parse_mode="HTML")

@router.callback_query(F.data.startswith("end_support_"))
async def end_support_chat_handler(callback: CallbackQuery, state: FSMContext):
    user_id_str = callback.data.replace("end_support_", "")
    try:
        user_id = int(user_id_str)
        await callback.message.bot.send_photo(
            chat_id=user_id,
            photo=FSInputFile("котлета.jpg"),
            caption="❌ <b>Chat Ended</b>\n━━━━━━━━━━━━━━━━━━━━\nSupport ended this conversation.",
            parse_mode="HTML"
        )
    except Exception as e:
        print(f"Error ending chat: {e}")

    await edit_by_callback(callback, text="✅ Chat ended", photo_path="котлета.jpg")
    await state.clear()

@router.callback_query(F.data == "vin_search")
async def top_up_handler(callback: CallbackQuery, state: FSMContext):
    text = "Select a top-up method (minimum: $%.2f):" % MIN_TOPUP_AMOUNT

    all_crypto_button = InlineKeyboardButton(text="All Crypto", callback_data="topup_method_plisio")
    cryptobot_button = InlineKeyboardButton(text="CryptoBot", callback_data="topup_method_cryptobot")
    back_button = InlineKeyboardButton(text="◀️ Back", callback_data="main_menu")
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [all_crypto_button],
        [cryptobot_button],
        [back_button]
    ])
    await edit_by_callback(callback, text=text, photo_path="котлета.jpg", reply_markup=keyboard, parse_mode="HTML")
    await state.set_state(TopUpStates.waiting_for_method)

@router.callback_query(F.data == "topup_method_plisio")
async def top_up_method_plisio_handler(callback: CallbackQuery, state: FSMContext):
    await state.update_data(payment_method="plisio")
    text = f"""All Crypto (BTC)

Write top-up amount in USD (minimum: ${MIN_TOPUP_AMOUNT:.2f})"""
    back_button = InlineKeyboardButton(text="◀️ Back", callback_data="vin_search")
    keyboard = InlineKeyboardMarkup(inline_keyboard=[[back_button]])
    await edit_by_callback(callback, text=text, photo_path="котлета.jpg", reply_markup=keyboard, parse_mode="HTML")
    await state.set_state(TopUpStates.waiting_for_amount)

@router.callback_query(F.data == "topup_method_cryptobot")
async def top_up_method_cryptobot_handler(callback: CallbackQuery, state: FSMContext):
    await state.update_data(payment_method="cryptobot")
    text = f"""CryptoBot

Write top-up amount in USD (minimum: ${MIN_TOPUP_AMOUNT:.2f})"""
    back_button = InlineKeyboardButton(text="◀️ Back", callback_data="vin_search")
    keyboard = InlineKeyboardMarkup(inline_keyboard=[[back_button]])
    await edit_by_callback(callback, text=text, photo_path="котлета.jpg", reply_markup=keyboard, parse_mode="HTML")
    await state.set_state(TopUpStates.waiting_for_amount)

@router.callback_query(F.data == "admin")
async def admin_handler(callback: CallbackQuery):
    if callback.from_user.id != ADMIN_ID:
        await edit_by_callback(callback, text="❌ Access denied. You are not an administrator.", photo_path="котлета.jpg")
        return

    admin_keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📊 Статистика", callback_data="admin_stats")],
        [InlineKeyboardButton(text="🎟️ Referral Promos", callback_data="admin_promos")],
        [InlineKeyboardButton(text="💰 Редактировать баланс", callback_data="admin_edit_balance")],
        [InlineKeyboardButton(text="📢 Рассылка", callback_data="admin_broadcast")],
        [InlineKeyboardButton(text="🔙 Назад", callback_data="main_menu")]
    ])
    await edit_by_callback(callback, text="🔑 Админ-панель:", photo_path="котлета.jpg", reply_markup=admin_keyboard)


# Обработчик запроса выплаты удален - теперь выплаты происходят автоматически
# @router.callback_query(F.data.startswith("request_payout_"))
# async def request_payout_handler(callback: CallbackQuery):
#     """Обработчик запроса выплаты от владельца промокода"""
#     try:
#         # Весь код обработчика закомментирован
#         pass
#     except Exception as e:
#         pass
#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Автоматический чекер платежей
Проверяет статус неоплаченных инвойсов и автоматически зачисляет средства
"""

import asyncio
import sqlite3
import requests
from datetime import datetime, timedelta
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from config import CRYPTO_PAY_API_KEY, ADMIN_ID
from database import get_db_connection, update_user_balance, get_user_profile, get_promo

# Таблица для хранения активных инвойсов
def init_invoices_table():
    """Создать таблицу для хранения активных инвойсов"""
    conn = get_db_connection()
    try:
        conn.execute("""
        CREATE TABLE IF NOT EXISTS pending_invoices (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            invoice_id TEXT NOT NULL UNIQUE,
            amount REAL NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            status TEXT DEFAULT 'pending'
        )
        """)
        
        # Таблица для отслеживания запросов выплат
        conn.execute("""
        CREATE TABLE IF NOT EXISTS payout_requests (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            owner_user_id INTEGER NOT NULL,
            promo_code TEXT NOT NULL,
            referral_user_id INTEGER NOT NULL,
            amount REAL NOT NULL,
            owner_share REAL NOT NULL,
            status TEXT DEFAULT 'pending',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(owner_user_id, promo_code, referral_user_id, amount)
        )
        """)
        
        conn.commit()
    except Exception as e:
        print(f"Error creating tables: {e}")
    finally:
        conn.close()

def add_pending_invoice(user_id: int, invoice_id: str, amount: float):
    """Добавить инвойс в очередь на проверку"""
    conn = get_db_connection()
    try:
        conn.execute("""
        INSERT OR REPLACE INTO pending_invoices (user_id, invoice_id, amount, status)
        VALUES (?, ?, ?, 'pending')
        """, (user_id, invoice_id, amount))
        conn.commit()
        return True
    except Exception as e:
        print(f"Error adding pending invoice: {e}")
        return False
    finally:
        conn.close()

def get_pending_invoices():
    """Получить все неоплаченные инвойсы"""
    conn = get_db_connection()
    try:
        cursor = conn.execute("""
        SELECT user_id, invoice_id, amount, created_at 
        FROM pending_invoices 
        WHERE status = 'pending' 
        AND datetime(created_at) > datetime('now', '-24 hours')
        """)
        return cursor.fetchall()
    except Exception as e:
        print(f"Error fetching pending invoices: {e}")
        return []
    finally:
        conn.close()

def mark_invoice_paid(invoice_id: str):
    """Отметить инвойс как оплаченный"""
    conn = get_db_connection()
    try:
        conn.execute("""
        UPDATE pending_invoices 
        SET status = 'paid' 
        WHERE invoice_id = ?
        """, (invoice_id,))
        conn.commit()
        return True
    except Exception as e:
        print(f"Error marking invoice as paid: {e}")
        return False
    finally:
        conn.close()

def remove_old_invoices():
    """Удалить старые инвойсы (старше 24 часов)"""
    conn = get_db_connection()
    try:
        conn.execute("""
        DELETE FROM pending_invoices 
        WHERE datetime(created_at) < datetime('now', '-24 hours')
        """)
        conn.commit()
    except Exception as e:
        print(f"Error removing old invoices: {e}")
    finally:
        conn.close()

async def check_invoice_status(invoice_id: str):
    """Проверить статус конкретного инвойса"""
    try:
        url = "https://pay.crypt.bot/api/getInvoices"
        headers = {
            "Crypto-Pay-API-Token": CRYPTO_PAY_API_KEY,
            "Content-Type": "application/json"
        }
        payload = {
            "invoice_ids": str(invoice_id)
        }

        response = requests.get(url, headers=headers, params=payload, timeout=20)
        data = response.json()

        if not response.ok or not data.get('ok'):
            return None

        invoices = data.get('result', {}).get('items', [])
        if not invoices:
            return None

        invoice = invoices[0]
        return invoice.get('status')
    except Exception as e:
        print(f"Error checking invoice {invoice_id}: {e}")
        return None

async def process_paid_invoice(user_id: int, invoice_id: str, amount: float, bot):
    """Обработать оплаченный инвойс"""
    try:
        # Обновляем баланс пользователя
        ok = update_user_balance(user_id, amount)
        if not ok:
            print(f"Failed to update balance for user {user_id}")
            return False

        # Записываем в таблицу bonuses для статистики
        conn = get_db_connection()
        try:
            conn.execute("""
            INSERT INTO bonuses (user_id, amount, description, created_at)
            VALUES (?, ?, ?, datetime('now'))
            """, (user_id, amount, f"Пополнение баланса через CryptoPay"))
            conn.commit()
        except Exception as e:
            print(f"Error adding bonus record: {e}")
        finally:
            conn.close()

        # Отправляем уведомление пользователю
        try:
            await bot.send_message(
                chat_id=user_id,
                text=f"✅ <b>Payment successful!</b>\n\n💳 Payment amount: ${amount:.2f} USD\n💰 Your balance has been topped up successfully.\n\nThank you for using our service!",
                parse_mode="HTML"
            )
        except Exception as e:
            print(f"Failed to notify user {user_id}: {e}")

        # Уведомляем админа и владельца промокода (если есть)
        try:
            profile = get_user_profile(user_id)
            used_promo = None
            if profile and len(profile) >= 8:
                used_promo = profile[7]

            if used_promo:
                # Уведомляем только админа, владельцу промокода уже отправлено из основного обработчика
                try:
                    await bot.send_message(
                        chat_id=ADMIN_ID,
                        text=f"💰 Автоматическое пополнение: User ID {user_id}, ${amount:.2f} USD, промокод: {used_promo}"
                    )
                except Exception as e:
                    print(f"Failed to notify admin: {e}")
            else:
                # Уведомляем админа без промокода
                try:
                    await bot.send_message(
                        chat_id=ADMIN_ID,
                        text=f"💰 Автоматическое пополнение: User ID {user_id}, ${amount:.2f} USD"
                    )
                except Exception as e:
                    print(f"Failed to notify admin: {e}")

        except Exception as e:
            print(f"Error during notifications: {e}")

        return True
    except Exception as e:
        print(f"Error processing paid invoice: {e}")
        return False

async def payment_checker_loop(bot):
    """Основной цикл проверки платежей"""
    print("Payment checker started...")
    
    while True:
        try:
            # Получаем все неоплаченные инвойсы
            pending = get_pending_invoices()
            
            for user_id, invoice_id, amount, created_at in pending:
                # Проверяем статус инвойса
                status = await check_invoice_status(invoice_id)
                
                if status == 'paid':
                    print(f"Invoice {invoice_id} is paid, processing...")
                    
                    # Обрабатываем оплаченный инвойс
                    success = await process_paid_invoice(user_id, invoice_id, amount, bot)
                    
                    if success:
                        # Отмечаем как оплаченный
                        mark_invoice_paid(invoice_id)
                        print(f"Successfully processed payment for user {user_id}, amount ${amount}")
                    else:
                        print(f"Failed to process payment for user {user_id}")
                
                # Небольшая задержка между проверками
                await asyncio.sleep(1)
            
            # Удаляем старые инвойсы
            remove_old_invoices()
            
            # Ждем 30 секунд перед следующей проверкой
            await asyncio.sleep(30)
            
        except Exception as e:
            print(f"Error in payment checker loop: {e}")
            await asyncio.sleep(60)  # Ждем минуту при ошибке

# Инициализация при импорте
init_invoices_table()

def add_payout_request(owner_user_id: int, promo_code: str, referral_user_id: int, amount: float, owner_share: float):
    """Добавить запрос выплаты"""
    conn = get_db_connection()
    try:
        conn.execute("""
        INSERT OR IGNORE INTO payout_requests 
        (owner_user_id, promo_code, referral_user_id, amount, owner_share, status)
        VALUES (?, ?, ?, ?, ?, 'pending')
        """, (owner_user_id, promo_code, referral_user_id, amount, owner_share))
        conn.commit()
        
        # Проверяем, была ли добавлена новая запись
        cursor = conn.execute("""
        SELECT id FROM payout_requests 
        WHERE owner_user_id = ? AND promo_code = ? AND referral_user_id = ? AND amount = ?
        """, (owner_user_id, promo_code, referral_user_id, amount))
        result = cursor.fetchone()
        return result[0] if result else None
    except Exception as e:
        print(f"Error adding payout request: {e}")
        return None
    finally:
        conn.close()

def check_payout_request_exists(owner_user_id: int, promo_code: str, referral_user_id: int, amount: float):
    """Проверить, существует ли уже запрос выплаты"""
    conn = get_db_connection()
    try:
        cursor = conn.execute("""
        SELECT id, status FROM payout_requests 
        WHERE owner_user_id = ? AND promo_code = ? AND referral_user_id = ? AND amount = ?
        """, (owner_user_id, promo_code, referral_user_id, amount))
        result = cursor.fetchone()
        return result if result else None
    except Exception as e:
        print(f"Error checking payout request: {e}")
        return None
    finally:
        conn.close()

def mark_payout_completed(request_id: int):
    """Отметить выплату как завершенную"""
    conn = get_db_connection()
    try:
        conn.execute("""
        UPDATE payout_requests 
        SET status = 'completed' 
        WHERE id = ?
        """, (request_id,))
        conn.commit()
        return True
    except Exception as e:
        print(f"Error marking payout as completed: {e}")
        return False
    finally:
        conn.close()
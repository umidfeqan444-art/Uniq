# -*- coding: utf-8 -*-
import sqlite3
import os
from typing import Dict, List, Tuple, Optional
import datetime

DB_PATH = '/data/shop.db'
os.makedirs('/data', exist_ok=True)

def get_db_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.execute('PRAGMA foreign_keys = ON')
    return conn

def init_db():
    conn = get_db_connection()
    try:
        cursor = conn.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='sellers'")
        if not cursor.fetchone():
            conn.execute("""
            CREATE TABLE sellers (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                card_number TEXT,
                expiry TEXT,
                cvv TEXT,
                holder_name TEXT,
                phone TEXT,
                email TEXT,
                deposit BOOLEAN,
                rating REAL,
                cards INTEGER,
                sold INTEGER,
                vr INTEGER,
                format_template TEXT DEFAULT '',
                supplier_name TEXT DEFAULT ''
            )
            """)
        else:
            cursor = conn.execute("PRAGMA table_info(sellers)")
            columns = [column[1] for column in cursor.fetchall()]

            if 'card_number' not in columns:
                conn.execute("ALTER TABLE sellers ADD COLUMN card_number TEXT")
            if 'expiry' not in columns:
                conn.execute("ALTER TABLE sellers ADD COLUMN expiry TEXT")
            if 'cvv' not in columns:
                conn.execute("ALTER TABLE sellers ADD COLUMN cvv TEXT")
            if 'holder_name' not in columns:
                conn.execute("ALTER TABLE sellers ADD COLUMN holder_name TEXT")
            if 'phone' not in columns:
                conn.execute("ALTER TABLE sellers ADD COLUMN phone TEXT")
            if 'email' not in columns:
                conn.execute("ALTER TABLE sellers ADD COLUMN email TEXT")
            if 'deposit' not in columns:
                conn.execute("ALTER TABLE sellers ADD COLUMN deposit BOOLEAN DEFAULT 0")
            if 'rating' not in columns:
                conn.execute("ALTER TABLE sellers ADD COLUMN rating REAL DEFAULT 0.0")
            if 'cards' not in columns:
                conn.execute("ALTER TABLE sellers ADD COLUMN cards INTEGER DEFAULT 0")
            if 'sold' not in columns:
                conn.execute("ALTER TABLE sellers ADD COLUMN sold INTEGER DEFAULT 0")
            if 'vr' not in columns:
                conn.execute("ALTER TABLE sellers ADD COLUMN vr INTEGER DEFAULT 0")
            if 'format_template' not in columns:
                conn.execute("ALTER TABLE sellers ADD COLUMN format_template TEXT DEFAULT ''")
            if 'supplier_name' not in columns:
                conn.execute("ALTER TABLE sellers ADD COLUMN supplier_name TEXT DEFAULT ''")

        conn.execute("""
        CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY,
            username TEXT,
            first_name TEXT,
            login TEXT UNIQUE,
            password TEXT,
            registered BOOLEAN DEFAULT 0
        )
        """)

        cursor = conn.execute("PRAGMA table_info(users)")
        columns = [column[1] for column in cursor.fetchall()]

        if 'login' not in columns:
            conn.execute("ALTER TABLE users ADD COLUMN login TEXT UNIQUE")
        if 'password' not in columns:
            conn.execute("ALTER TABLE users ADD COLUMN password TEXT")
        if 'registered' not in columns:
            conn.execute("ALTER TABLE users ADD COLUMN registered BOOLEAN DEFAULT 0")
        if 'balance' not in columns:
            conn.execute("ALTER TABLE users ADD COLUMN balance REAL DEFAULT 0.0")
        if 'used_promo' not in columns:
            conn.execute("ALTER TABLE users ADD COLUMN used_promo TEXT DEFAULT NULL")

        conn.execute("""
        CREATE TABLE IF NOT EXISTS promo_codes (
            code TEXT PRIMARY KEY,
            uses_remaining INTEGER NOT NULL,
            amount REAL NOT NULL,
            owner_user_id INTEGER DEFAULT NULL,
            owner_username TEXT DEFAULT NULL,
            expires_at TIMESTAMP DEFAULT NULL,
            is_used BOOLEAN DEFAULT FALSE
        )
        """)

        try:
            cursor = conn.execute("PRAGMA table_info(promo_codes)")
            promo_cols = [c[1] for c in cursor.fetchall()]
            if 'expires_at' not in promo_cols:
                conn.execute("ALTER TABLE promo_codes ADD COLUMN expires_at TIMESTAMP DEFAULT NULL")
            if 'is_used' not in promo_cols:
                conn.execute("ALTER TABLE promo_codes ADD COLUMN is_used BOOLEAN DEFAULT FALSE")
        except Exception as e:
            print(f"Warning: could not ensure promo_codes columns: {e}")

        conn.execute("""
        CREATE TABLE IF NOT EXISTS products (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            description TEXT,
            price REAL NOT NULL,
            content TEXT,
            category TEXT
        )
        """)

        conn.execute("""
        CREATE TABLE IF NOT EXISTS purchases (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            product_id INTEGER NOT NULL,
            purchase_date TEXT NOT NULL,
            FOREIGN KEY (user_id) REFERENCES users(user_id),
            FOREIGN KEY (product_id) REFERENCES products(id)
        )
        """)

        conn.execute("""
        CREATE TABLE IF NOT EXISTS card_sales (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            supplier TEXT NOT NULL,
            bin TEXT NOT NULL,
            card_text TEXT NOT NULL,
            price REAL NOT NULL,
            country TEXT DEFAULT 'Unknown',
            sale_date TEXT NOT NULL
        )
        """)

        cursor = conn.execute("PRAGMA table_info(card_sales)")
        card_sales_cols = [column[1] for column in cursor.fetchall()]
        if 'country' not in card_sales_cols:
            conn.execute("ALTER TABLE card_sales ADD COLUMN country TEXT DEFAULT 'Unknown'")

        conn.execute("""
        CREATE TABLE IF NOT EXISTS referral_activity (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            promo_code TEXT NOT NULL,
            user_id INTEGER NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users(user_id)
        )
        """)

        conn.execute("""
        CREATE TABLE IF NOT EXISTS bonuses (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            amount REAL NOT NULL,
            description TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users(user_id)
        )
        """)

        conn.commit()

        cursor = conn.execute("SELECT COUNT(*) FROM sellers")
        if cursor.fetchone()[0] == 0:
            conn.execute("""
            INSERT INTO sellers (card_number, expiry, cvv, holder_name, phone, email, deposit, rating, cards, sold, vr)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, ("1234567890123456", "12/25", "123", "Test Seller", "+1234567890", "test@example.com", True, 4.8, 2791, 10875, 81))
            conn.commit()

    except Exception as e:
        print(f"Error initializing database: {e}")
    finally:
        conn.close()

def get_sellers():
    conn = get_db_connection()
    sellers_dict = {}
    try:
        cursor = conn.execute("SELECT id, card_number, expiry, cvv, holder_name, phone, email, deposit, rating, cards, sold, vr FROM sellers")
        for row in cursor.fetchall():
            sellers_dict[str(row[0])] = row[1:]
    except Exception as e:
        print(f"Error fetching sellers: {e}")
    finally:
        conn.close()
    return sellers_dict

def add_seller(card_number, expiry, cvv, holder_name, phone, email, deposit, rating, cards, sold, vr, format_template="", supplier_name=""):
    conn = get_db_connection()
    try:
        conn.execute("""
        INSERT INTO sellers (card_number, expiry, cvv, holder_name, phone, email, deposit, rating, cards, sold, vr, format_template, supplier_name)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (card_number, expiry, cvv, holder_name, phone, email, deposit, rating, cards, sold, vr, format_template, supplier_name))
        conn.commit()
        cursor = conn.execute("SELECT last_insert_rowid()")
        return cursor.fetchone()[0]
    except Exception as e:
        print(f"Error adding seller: {e}")
        return None
    finally:
        conn.close()

def update_seller(seller_id, card_number=None, expiry=None, cvv=None, holder_name=None, phone=None, email=None, deposit=None, rating=None, cards=None, sold=None, vr=None):
    conn = get_db_connection()
    try:
        updates = []
        params = []
        if card_number is not None:
            updates.append("card_number = ?")
            params.append(card_number)
        if expiry is not None:
            updates.append("expiry = ?")
            params.append(expiry)
        if cvv is not None:
            updates.append("cvv = ?")
            params.append(cvv)
        if holder_name is not None:
            updates.append("holder_name = ?")
            params.append(holder_name)
        if phone is not None:
            updates.append("phone = ?")
            params.append(phone)
        if email is not None:
            updates.append("email = ?")
            params.append(email)
        if deposit is not None:
            updates.append("deposit = ?")
            params.append(deposit)
        if rating is not None:
            updates.append("rating = ?")
            params.append(rating)
        if cards is not None:
            updates.append("cards = ?")
            params.append(cards)
        if sold is not None:
            updates.append("sold = ?")
            params.append(sold)
        if vr is not None:
            updates.append("vr = ?")
            params.append(vr)

        params.append(seller_id)

        if updates:
            query = f"UPDATE sellers SET {', '.join(updates)} WHERE id = ?"
            conn.execute(query, params)
            conn.commit()
            return True
        return False
    except Exception as e:
        print(f"Error updating seller: {e}")
        return False
    finally:
        conn.close()

import asyncio
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def delete_seller(seller_id):
    try:
        loop = asyncio.get_event_loop()
        result = await loop.run_in_executor(None, _delete_seller, seller_id)
        print(f"[DB DEBUG] Delete seller {seller_id} result: {result}")
        return bool(result)
    except Exception as e:
        print(f"[DB ERROR] Error in delete_seller: {e}")
        return False

def _delete_seller(seller_id):
    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM sellers WHERE id = ?", (seller_id,))
        exists = cursor.fetchone()[0] > 0
        print(f"[DB DEBUG] Seller {seller_id} exists: {exists}")

        if exists:
            cursor.execute("DELETE FROM sellers WHERE id = ?", (seller_id,))
            conn.commit()
            deleted_count = cursor.rowcount
            print(f"[DB DEBUG] Deleted rows count: {deleted_count}")

            cursor.execute("SELECT COUNT(*) FROM sellers WHERE id = ?", (seller_id,))
            remaining_count = cursor.fetchone()[0]
            print(f"[DB DEBUG] Remaining rows with id {seller_id}: {remaining_count}")

            return deleted_count > 0
        else:
            print(f"[DB DEBUG] Seller {seller_id} does not exist")
            return False
    except Exception as e:
        print(f"[DB ERROR] Database error deleting seller {seller_id}: {e}")
        if conn:
            conn.rollback()
        return False
    finally:
        if conn:
            conn.close()

def get_products_by_category(category):
    conn = get_db_connection()
    try:
        cursor = conn.execute(f"SELECT id, name, description, price, content FROM products WHERE category = ?", (category,))
        return cursor.fetchall()
    except Exception as e:
        print(f"Error fetching products by category: {e}")
        return []
    finally:
        conn.close()

def get_all_products():
    conn = get_db_connection()
    try:
        cursor = conn.execute("SELECT id, name, description, price, content FROM products")
        return cursor.fetchall()
    except Exception as e:
        print(f"Error fetching all products: {e}")
        return []
    finally:
        conn.close()

def add_product(name, description, price, content, category):
    conn = get_db_connection()
    try:
        conn.execute("""
            INSERT INTO products (name, description, price, content, category)
            VALUES (?, ?, ?, ?, ?)
        """, (name, description, price, content, category))
        conn.commit()
    except Exception as e:
        print(f"Error adding product: {e}")
    finally:
        conn.close()

def get_all_users():
    conn = get_db_connection()
    try:
        cursor = conn.execute("SELECT user_id, username, first_name FROM users")
        return cursor.fetchall()
    except Exception as e:
        print(f"Error fetching users: {e}")
        return []
    finally:
        conn.close()

def add_user(user_id, username, first_name):
    conn = get_db_connection()
    try:
        conn.execute("""
            INSERT OR IGNORE INTO users (user_id, username, first_name)
            VALUES (?, ?, ?)
        """, (user_id, username, first_name))
        conn.commit()
    except Exception as e:
        print(f"Error adding user: {e}")
    finally:
        conn.close()

def get_product_by_id(product_id):
    conn = get_db_connection()
    try:
        cursor = conn.execute("SELECT name, description, price, content FROM products WHERE id = ?", (product_id,))
        return cursor.fetchone()
    except Exception as e:
        print(f"Error fetching product: {e}")
        return None
    finally:
        conn.close()

def add_purchase(user_id, product_id):
    conn = get_db_connection()
    try:
        conn.execute("""
            INSERT INTO purchases (user_id, product_id, purchase_date)
            VALUES (?, ?, datetime('now'))
        """, (user_id, product_id))
        conn.commit()
    except Exception as e:
        print(f"Error adding purchase: {e}")
    finally:
        conn.close()

def get_user_purchases(user_id):
    conn = get_db_connection()
    try:
        cursor = conn.execute("""
            SELECT p.name, p.price, strftime('%d-%m-%Y', pu.purchase_date)
            FROM purchases pu
            JOIN products p ON pu.product_id = p.id
            WHERE pu.user_id = ?
        """, (user_id,))
        return cursor.fetchall()
    except Exception as e:
        print(f"Error fetching user purchases: {e}")
        return []
    finally:
        conn.close()

def get_user_card_sales(user_id):
    """Получить все купленные карты пользователя из таблицы card_sales"""
    conn = get_db_connection()
    try:
        cursor = conn.execute("""
            SELECT id, bin, card_text, supplier, price, country, sale_date
            FROM card_sales
            WHERE user_id = ?
            ORDER BY sale_date DESC
        """, (user_id,))
        return cursor.fetchall()
    except Exception as e:
        print(f"Error fetching user card sales: {e}")
        return []
    finally:
        conn.close()

def get_card_sale_by_id(sale_id):
    """Получить информацию о конкретной купленной карте"""
    conn = get_db_connection()
    try:
        cursor = conn.execute("""
            SELECT id, bin, card_text, supplier, price, country, sale_date
            FROM card_sales
            WHERE id = ?
        """, (sale_id,))
        return cursor.fetchone()
    except Exception as e:
        print(f"Error fetching card sale: {e}")
        return None
    finally:
        conn.close()

def get_stats():
    conn = get_db_connection()
    try:
        cursor = conn.execute("""
            SELECT COUNT(*), (SELECT COUNT(*) FROM products), (SELECT COUNT(*) FROM purchases)
        """)
        result = cursor.fetchone()
        return result if result else (0, 0, 0)
    except Exception as e:
        print(f"Error fetching stats: {e}")
        return (0, 0, 0)
    finally:
        conn.close()

def get_simple_stats():
    """Получить простую статистику за сегодня"""
    conn = get_db_connection()
    try:
        # Проверяем существование таблицы bonuses
        cursor = conn.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='bonuses'")
        bonuses_exists = cursor.fetchone() is not None
        
        topups_today = 0
        if bonuses_exists:
            try:
                # Заработок за сегодня (пополнения)
                cursor = conn.execute("""
                    SELECT COALESCE(SUM(amount), 0) FROM bonuses 
                    WHERE amount > 0 AND date(created_at) = date('now')
                """)
                topups_today_result = cursor.fetchone()
                topups_today = topups_today_result[0] if topups_today_result else 0
            except Exception as e:
                print(f"Error getting topups: {e}")
                topups_today = 0
        
        # Доходы от покупок за сегодня
        revenue_today = 0
        try:
            cursor = conn.execute("""
                SELECT COALESCE(SUM(CAST(pr.price AS REAL)), 0) as revenue_today
                FROM purchases p
                JOIN products pr ON p.product_id = pr.id
                WHERE date(p.purchase_date) = date('now')
            """)
            revenue_today_result = cursor.fetchone()
            revenue_today = revenue_today_result[0] if revenue_today_result else 0
        except Exception as e:
            print(f"Error getting revenue: {e}")
            revenue_today = 0
        
        # Общий заработок за сегодня
        earnings_today = topups_today + revenue_today
        
        # Общее количество пользователей (так как created_at может не быть)
        try:
            cursor = conn.execute("SELECT COUNT(*) FROM users WHERE registered = 1")
            total_users_result = cursor.fetchone()
            total_users = total_users_result[0] if total_users_result else 0
        except Exception as e:
            print(f"Error getting users count: {e}")
            total_users = 0
        
        # Общее количество покупок
        try:
            cursor = conn.execute("SELECT COUNT(*) FROM purchases")
            total_purchases_result = cursor.fetchone()
            total_purchases = total_purchases_result[0] if total_purchases_result else 0
        except Exception as e:
            print(f"Error getting purchases count: {e}")
            total_purchases = 0
        
        # Общее количество товаров
        try:
            cursor = conn.execute("SELECT COUNT(*) FROM products")
            total_products_result = cursor.fetchone()
            total_products = total_products_result[0] if total_products_result else 0
        except Exception as e:
            print(f"Error getting products count: {e}")
            total_products = 0
        
        # Покупки за сегодня
        try:
            cursor = conn.execute("""
                SELECT COUNT(*) FROM purchases 
                WHERE date(purchase_date) = date('now')
            """)
            purchases_today_result = cursor.fetchone()
            purchases_today = purchases_today_result[0] if purchases_today_result else 0
        except Exception as e:
            print(f"Error getting today purchases: {e}")
            purchases_today = 0
        
        return {
            'earnings_today': earnings_today,
            'revenue_today': revenue_today,
            'topups_today': topups_today,
            'total_users': total_users,
            'total_purchases': total_purchases,
            'total_products': total_products,
            'purchases_today': purchases_today
        }
        
    except Exception as e:
        print(f"Error fetching simple stats: {e}")
        return None
    finally:
        conn.close()

def get_extended_stats():
    """Получить расширенную статистику магазина"""
    conn = get_db_connection()
    try:
        # Основная статистика
        cursor = conn.execute("""
            SELECT 
                (SELECT COUNT(*) FROM users) as total_users,
                (SELECT COUNT(*) FROM users WHERE registered = 1) as registered_users,
                (SELECT COUNT(*) FROM products) as total_products,
                (SELECT COUNT(*) FROM purchases) as total_purchases,
                (SELECT COUNT(*) FROM sellers) as total_sellers,
                (SELECT COUNT(*) FROM promo_codes) as total_promos
        """)
        basic_stats = cursor.fetchone()
        
        # Статистика по балансам
        cursor = conn.execute("""
            SELECT 
                COALESCE(SUM(balance), 0) as total_balance,
                COALESCE(AVG(balance), 0) as avg_balance,
                COALESCE(MAX(balance), 0) as max_balance
            FROM users WHERE balance > 0
        """)
        balance_stats = cursor.fetchone()
        
        # Статистика по пополнениям из таблицы bonuses
        # За сегодня
        cursor = conn.execute("""
            SELECT COALESCE(SUM(amount), 0) FROM bonuses 
            WHERE amount > 0 AND date(created_at) = date('now')
        """)
        topups_today_result = cursor.fetchone()
        topups_today = topups_today_result[0] if topups_today_result else 0
        
        # За неделю
        cursor = conn.execute("""
            SELECT COALESCE(SUM(amount), 0) FROM bonuses 
            WHERE amount > 0 AND datetime(created_at) >= datetime('now', '-7 days')
        """)
        topups_7d_result = cursor.fetchone()
        topups_7d = topups_7d_result[0] if topups_7d_result else 0
        
        # За месяц
        cursor = conn.execute("""
            SELECT COALESCE(SUM(amount), 0) FROM bonuses 
            WHERE amount > 0 AND datetime(created_at) >= datetime('now', '-30 days')
        """)
        topups_30d_result = cursor.fetchone()
        topups_30d = topups_30d_result[0] if topups_30d_result else 0
        
        # Общая сумма пополнений
        cursor = conn.execute("""
            SELECT COALESCE(SUM(amount), 0) FROM bonuses WHERE amount > 0
        """)
        total_topups_result = cursor.fetchone()
        total_topups = total_topups_result[0] if total_topups_result else 0
        
        # Статистика по покупкам за последние 30 дней
        cursor = conn.execute("""
            SELECT COUNT(*) FROM purchases 
            WHERE datetime(purchase_date) >= datetime('now', '-30 days')
        """)
        purchases_30d_result = cursor.fetchone()
        purchases_30d = purchases_30d_result[0] if purchases_30d_result else 0
        
        # Статистика по покупкам за последние 7 дней
        cursor = conn.execute("""
            SELECT COUNT(*) FROM purchases 
            WHERE datetime(purchase_date) >= datetime('now', '-7 days')
        """)
        purchases_7d_result = cursor.fetchone()
        purchases_7d = purchases_7d_result[0] if purchases_7d_result else 0
        
        # Статистика по покупкам за сегодня
        cursor = conn.execute("""
            SELECT COUNT(*) FROM purchases 
            WHERE date(purchase_date) = date('now')
        """)
        purchases_today_result = cursor.fetchone()
        purchases_today = purchases_today_result[0] if purchases_today_result else 0
        
        # Топ 5 самых активных пользователей по покупкам
        cursor = conn.execute("""
            SELECT u.username, COUNT(p.id) as purchase_count
            FROM users u
            LEFT JOIN purchases p ON u.user_id = p.user_id
            WHERE u.username IS NOT NULL
            GROUP BY u.user_id, u.username
            ORDER BY purchase_count DESC
            LIMIT 5
        """)
        top_users = cursor.fetchall()
        
        # Статистика по промокодам
        cursor = conn.execute("""
            SELECT 
                COUNT(*) as total_promos,
                SUM(CASE WHEN is_used = 1 THEN 1 ELSE 0 END) as used_promos,
                SUM(CASE WHEN expires_at IS NULL OR datetime(expires_at) > datetime('now') THEN 1 ELSE 0 END) as active_promos
            FROM promo_codes
        """)
        promo_stats = cursor.fetchone()
        
        # Общая сумма покупок
        cursor = conn.execute("""
            SELECT COALESCE(SUM(CAST(price AS REAL)), 0) as total_revenue
            FROM purchases p
            JOIN products pr ON p.product_id = pr.id
        """)
        revenue_stats = cursor.fetchone()
        
        # Статистика регистраций за последние дни (если есть поле created_at)
        try:
            cursor = conn.execute("""
                SELECT COUNT(*) FROM users 
                WHERE registered = 1 AND datetime(created_at) >= datetime('now', '-1 days')
            """)
            new_users_today_result = cursor.fetchone()
            new_users_today = new_users_today_result[0] if new_users_today_result else 0
            
            cursor = conn.execute("""
                SELECT COUNT(*) FROM users 
                WHERE registered = 1 AND datetime(created_at) >= datetime('now', '-7 days')
            """)
            new_users_7d_result = cursor.fetchone()
            new_users_7d = new_users_7d_result[0] if new_users_7d_result else 0
        except:
            # Если поля created_at нет, используем 0
            new_users_today = 0
            new_users_7d = 0
        
        # Средняя сумма покупки
        cursor = conn.execute("""
            SELECT COALESCE(AVG(CAST(price AS REAL)), 0) as avg_purchase
            FROM purchases p
            JOIN products pr ON p.product_id = pr.id
        """)
        avg_purchase_result = cursor.fetchone()
        avg_purchase = avg_purchase_result[0] if avg_purchase_result else 0
        
        return {
            'basic': basic_stats,
            'balance': balance_stats,
            'purchases_30d': purchases_30d,
            'purchases_7d': purchases_7d,
            'purchases_today': purchases_today,
            'top_users': top_users,
            'promo': promo_stats,
            'revenue': revenue_stats[0] if revenue_stats else 0,
            'new_users_today': new_users_today,
            'new_users_7d': new_users_7d,
            'avg_purchase': avg_purchase,
            'topups_today': topups_today,
            'topups_7d': topups_7d,
            'topups_30d': topups_30d,
            'total_topups': total_topups
        }
        
    except Exception as e:
        print(f"Error fetching extended stats: {e}")
        return None
    finally:
        conn.close()

def user_is_registered(user_id):
    conn = get_db_connection()
    try:
        cursor = conn.execute("SELECT registered FROM users WHERE user_id = ?", (user_id,))
        result = cursor.fetchone()
        return result[0] if result else False
    except Exception as e:
        print(f"Error checking registration: {e}")
        return False
    finally:
        conn.close()

def register_user(user_id, username, first_name, login, password):
    conn = get_db_connection()
    try:
        conn.execute("""
            INSERT OR REPLACE INTO users (user_id, username, first_name, login, password, registered)
            VALUES (?, ?, ?, ?, ?, 1)
        """, (user_id, username, first_name, login, password))
        conn.commit()
        return True
    except Exception as e:
        print(f"Error registering user: {e}")
        return False
    finally:
        conn.close()

def mark_user_registered(user_id):
    conn = get_db_connection()
    try:
        conn.execute("INSERT OR IGNORE INTO users (user_id, username, first_name) VALUES (?, ?, ?)", (user_id, '', ''))
        conn.execute("UPDATE users SET registered = 1 WHERE user_id = ?", (user_id,))
        conn.commit()
        return True
    except Exception as e:
        print(f"Error marking user registered: {e}")
        return False
    finally:
        conn.close()

def check_login_exists(login):
    conn = get_db_connection()
    try:
        cursor = conn.execute("SELECT user_id FROM users WHERE login = ?", (login,))
        return cursor.fetchone() is not None
    except Exception as e:
        print(f"Error checking login: {e}")
        return False
    finally:
        conn.close()

def verify_login(login, password):
    conn = get_db_connection()
    try:
        cursor = conn.execute("SELECT user_id FROM users WHERE login = ? AND password = ?", (login, password))
        result = cursor.fetchone()
        return result[0] if result else None
    except Exception as e:
        print(f"Error verifying login: {e}")
        return None
    finally:
        conn.close()

def get_user_profile(user_id):
    conn = get_db_connection()
    try:
        cursor = conn.execute("SELECT user_id, username, first_name, login, password, registered, balance, used_promo FROM users WHERE user_id = ?", (user_id,))
        return cursor.fetchone()
    except Exception as e:
        print(f"Error fetching user profile: {e}")
        return None
    finally:
        conn.close()

def logout_user(user_id):
    conn = get_db_connection()
    try:
        conn.execute("UPDATE users SET registered = 0 WHERE user_id = ?", (user_id,))
        conn.commit()
        return True
    except Exception as e:
        print(f"Error logging out user: {e}")
        return False
    finally:
        conn.close()

def get_account_info(user_id):
    conn = get_db_connection()
    try:
        cursor = conn.execute("""
            SELECT user_id, username, first_name, login,
                   (SELECT COUNT(*) FROM purchases WHERE user_id = ?) as total_purchases,
                   (SELECT SUM(products.price) FROM purchases
                    JOIN products ON purchases.product_id = products.id
                    WHERE purchases.user_id = ?) as total_spent
            FROM users WHERE user_id = ?
        """, (user_id, user_id, user_id))
        row = cursor.fetchone()
        if row:
            return {
                'user_id': row[0],
                'username': row[1],
                'first_name': row[2],
                'login': row[3],
                'purchases': row[4] or 0,
                'total_spent': row[5] or 0.0
            }
        return None
    except Exception as e:
        print(f"Error fetching account info: {e}")
        return None
    finally:
        conn.close()

def update_user_balance(user_id, amount):
    conn = get_db_connection()
    try:
        cursor = conn.execute("SELECT balance FROM users WHERE user_id = ?", (user_id,))
        result = cursor.fetchone()
        current_balance = result[0] if result else 0.0
        new_balance = current_balance + amount
        conn.execute("UPDATE users SET balance = ? WHERE user_id = ?", (new_balance, user_id))
        conn.commit()
        return True
    except Exception as e:
        print(f"Error updating user balance: {e}")
        return False
    finally:
        conn.close()

def update_user_password(user_id, new_password):
    """Update user password by user_id"""
    conn = get_db_connection()
    try:
        conn.execute("UPDATE users SET password = ? WHERE user_id = ?", (new_password, user_id))
        conn.commit()
        return True
    except Exception as e:
        print(f"Error updating user password: {e}")
        return False
    finally:
        conn.close()


def get_user_id_by_username(username: str):
    """Return user_id for a given username (strip leading @). Returns None if not found."""
    if not username:
        return None
    uname = username.lstrip('@')
    conn = get_db_connection()
    try:
        cur = conn.execute("SELECT user_id FROM users WHERE username = ?", (uname,))
        row = cur.fetchone()
        return row[0] if row else None
    except Exception as e:
        print(f"Error looking up user by username: {e}")
        return None
    finally:
        conn.close()

def create_promo(code, uses, amount, expires_at=None):
    conn = get_db_connection()
    try:
        conn.execute("""
            INSERT OR REPLACE INTO promo_codes (code, uses_remaining, amount, owner_user_id, owner_username, expires_at)
            VALUES (?, ?, ?, NULL, NULL, ?)
        """, (code.upper(), int(uses), float(amount), expires_at))
        conn.commit()
        return True
    except Exception as e:
        print(f"Error creating promo: {e}")
        return False
    finally:
        conn.close()

def create_money_promo(code, uses, amount, expires_at=None):
    conn = get_db_connection()
    try:
        conn.execute("""
            INSERT OR REPLACE INTO promo_codes (code, uses_remaining, amount, owner_user_id, owner_username, expires_at)
            VALUES (?, ?, ?, NULL, NULL, ?)
        """, (code.upper(), int(uses), float(amount), expires_at))
        conn.commit()
        return True
    except Exception as e:
        print(f"Error creating money promo: {e}")
        return False
    finally:
        conn.close()

# removed create_user_promo: use create_promo_with_owner instead

def create_promo_with_owner(code, uses, amount, owner_username=None, expires_at=None):
    conn = get_db_connection()
    try:
        owner_id = None
        owner_username_clean = None
        if owner_username:
            # owner_username can be a username (with or without @) or a numeric user_id string
            if str(owner_username).isdigit():
                try:
                    owner_id = int(owner_username)
                except Exception:
                    owner_id = None
            else:
                owner_username_clean = owner_username.lstrip('@')
                cur = conn.execute("SELECT user_id FROM users WHERE username = ?", (owner_username_clean,))
                row = cur.fetchone()
                if row:
                    owner_id = row[0]

        # If we have owner_id but not owner_username_clean, try to fetch username from users
        if owner_id and not owner_username_clean:
            try:
                cur = conn.execute("SELECT username FROM users WHERE user_id = ?", (owner_id,))
                row = cur.fetchone()
                if row and row[0]:
                    owner_username_clean = row[0]
            except Exception:
                owner_username_clean = None

        conn.execute("""
            INSERT OR REPLACE INTO promo_codes (code, uses_remaining, amount, owner_user_id, owner_username, expires_at)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (code.upper(), int(uses), float(amount), owner_id, owner_username_clean, expires_at))
        conn.commit()
        return True
    except Exception as e:
        print(f"Error creating promo with owner: {e}")
        return False
    finally:
        conn.close()

def get_promo(code):
    conn = get_db_connection()
    try:
        cursor = conn.execute("""
            SELECT code, uses_remaining, amount, owner_user_id, owner_username, expires_at, is_used
            FROM promo_codes WHERE code = ?
        """, (code.upper(),))
        row = cursor.fetchone()
        if not row:
            return None
        return {
            "code": row[0],
            "uses_remaining": row[1],
            "amount": row[2],
            "owner_user_id": row[3],
            "owner_username": row[4],
            "expires_at": row[5],
            "is_used": row[6]
        }
    except Exception as e:
        print(f"Error fetching promo: {e}")
        return None
    finally:
        conn.close()

def update_user_used_promo(user_id, code):
    conn = get_db_connection()
    try:
        conn.execute("UPDATE users SET used_promo = ? WHERE user_id = ?", (code.upper() if code else None, user_id))
        conn.commit()
        return True
    except Exception as e:
        print(f"Error updating user's used promo: {e}")
        return False
    finally:
        conn.close()

def redeem_promo(user_id, code):
    conn = get_db_connection()
    try:
        cur = conn.cursor()
        cur.execute("""
            SELECT uses_remaining, owner_user_id, owner_username, amount, expires_at
            FROM promo_codes WHERE code = ?
        """, (code.upper(),))
        row = cur.fetchone()
        if not row:
            return False, "Promo code not found."

        uses_remaining, owner_user_id, owner_username, amount, expires_at = row

        if expires_at and expires_at < datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S'):
            return False, "Promo code has expired."

        if uses_remaining < 0:
            uses_remaining = -1
        elif uses_remaining == 0:
            return False, "Promo code has no remaining uses."

        cur.execute("INSERT INTO referral_activity (promo_code, user_id) VALUES (?, ?)", (code.upper(), user_id))

        if owner_user_id:
            cur.execute("INSERT INTO bonuses (user_id, amount, description) VALUES (?, ?, ?)",
                        (owner_user_id, amount, "Бонус за реферал"))

        conn.commit()
        return True, "Promo code successfully redeemed for referral."
    except Exception as e:
        conn.rollback()
        print(f"Error redeeming promo: {e}")
        return False, "Internal error while redeeming promo."
    finally:
        conn.close()

def redeem_money_promo(user_id, code):
    conn = get_db_connection()
    try:
        cur = conn.cursor()
        cur.execute("SELECT uses_remaining, amount, owner_user_id FROM promo_codes WHERE code = ?", (code.upper(),))
        row = cur.fetchone()
        if not row:
            return False, "Promo code not found."

        uses_remaining, amount, owner_user_id = row

        if uses_remaining < 0:
            uses_remaining = -1
        elif uses_remaining == 0:
            return False, "Promo code has no remaining uses."

        cur.execute("SELECT balance FROM users WHERE user_id = ?", (user_id,))
        result = cur.fetchone()
        current_balance = result[0] if result else 0.0
        new_balance = current_balance + float(amount)

        cur.execute("UPDATE users SET balance = ? WHERE user_id = ?", (new_balance, user_id))

        if owner_user_id and uses_remaining > 0:
            cur.execute("INSERT INTO bonuses (user_id, amount, description) VALUES (?, ?, ?)",
                        (owner_user_id, amount, "Бонус за пополнение"))

        conn.commit()
        return True, f"Promo applied: +${amount:.2f}"
    except Exception as e:
        conn.rollback()
        print(f"Error redeeming money promo: {e}")
        return False, "Internal error while redeeming promo."
    finally:
        conn.close()

def register_user_with_referral(user_id, username, first_name, login, password, promo_code):
    conn = get_db_connection()
    try:
        cur = conn.cursor()
        cur.execute("""
            SELECT uses_remaining, owner_user_id, owner_username, amount
            FROM promo_codes WHERE code = ?
        """, (promo_code.upper(),))
        promo_row = cur.fetchone()

        if not promo_row:
            return False, "Invalid promo code."

        uses_remaining, owner_user_id, owner_username, amount = promo_row

        if uses_remaining < 0:
            pass  # Промокод с неограниченным использованием
        elif uses_remaining == 0:
            return False, "Promo code has no remaining uses."

        cur.execute("""
            INSERT OR REPLACE INTO users (user_id, username, first_name, login, password, registered, used_promo)
            VALUES (?, ?, ?, ?, ?, 1, ?)
        """, (user_id, username, first_name, login, password, promo_code.upper()))

        if uses_remaining > 0:
            cur.execute("UPDATE promo_codes SET uses_remaining = uses_remaining - 1 WHERE code = ?", (promo_code.upper(),))

        cur.execute("INSERT INTO referral_activity (promo_code, user_id) VALUES (?, ?)", (promo_code.upper(), user_id))

        if owner_user_id:
            cur.execute("INSERT INTO bonuses (user_id, amount, description) VALUES (?, ?, ?)",
                        (owner_user_id, amount, "Бонус за реферал"))

        conn.commit()
        return True, "Registration successful! You are now registered with the referral promo code."
    except Exception as e:
        conn.rollback()
        print(f"Error registering user with referral: {e}")
        return False, "Internal error during registration."
    finally:
        conn.close()

def get_user_promos(user_id):
    """Get all promo codes owned by a specific user."""
    conn = get_db_connection()
    try:
        cursor = conn.execute("""
            SELECT code, uses_remaining, amount, expires_at
            FROM promo_codes WHERE owner_user_id = ?
        """, (user_id,))
        promos = []
        for row in cursor.fetchall():
            promo = {
                "code": row[0],
                "uses_remaining": row[1],
                "amount": row[2],
                "expires_at": row[3]
            }
            promos.append(promo)
        return promos
    except Exception as e:
        print(f"Error fetching user promos: {e}")
        return []
    finally:
        conn.close()

def list_promos():
    """List all promo codes in the database."""
    conn = get_db_connection()
    try:
        cursor = conn.execute("""
            SELECT code, uses_remaining, amount, owner_user_id, owner_username, expires_at, is_used
            FROM promo_codes
        """)
        promos = []
        for row in cursor.fetchall():
            promo = {
                "code": row[0],
                "uses_remaining": row[1],
                "amount": row[2],
                "owner_user_id": row[3],
                "owner_username": row[4],
                "expires_at": row[5],
                "is_used": row[6]
            }
            promos.append(promo)
        return promos
    except Exception as e:
        print(f"Error fetching promos: {e}")
        return []
    finally:
        conn.close()

def get_promo_detailed_stats(promo_code):
    """Получить детальную статистику по конкретному промокоду"""
    conn = get_db_connection()
    try:
        # Основная информация о промокоде
        cursor = conn.execute("""
            SELECT code, uses_remaining, amount, owner_user_id, owner_username, expires_at, is_used
            FROM promo_codes WHERE code = ?
        """, (promo_code,))
        promo_info = cursor.fetchone()
        
        if not promo_info:
            return None
            
        # Проверяем, есть ли поле created_at в таблице users
        try:
            cursor = conn.execute("PRAGMA table_info(users)")
            columns = [column[1] for column in cursor.fetchall()]
            has_created_at = 'created_at' in columns
        except:
            has_created_at = False
        
        if has_created_at:
            # За сегодня
            cursor = conn.execute("""
                SELECT COUNT(*) FROM users 
                WHERE used_promo = ? AND date(created_at) = date('now')
            """, (promo_code,))
            reg_today_result = cursor.fetchone()
            registrations_today = reg_today_result[0] if reg_today_result else 0
            
            # За неделю
            cursor = conn.execute("""
                SELECT COUNT(*) FROM users 
                WHERE used_promo = ? AND datetime(created_at) >= datetime('now', '-7 days')
            """, (promo_code,))
            reg_7d_result = cursor.fetchone()
            registrations_7d = reg_7d_result[0] if reg_7d_result else 0
            
            # За месяц
            cursor = conn.execute("""
                SELECT COUNT(*) FROM users 
                WHERE used_promo = ? AND datetime(created_at) >= datetime('now', '-30 days')
            """, (promo_code,))
            reg_30d_result = cursor.fetchone()
            registrations_30d = reg_30d_result[0] if reg_30d_result else 0
        else:
            # Если поля created_at нет, показываем только общее количество
            registrations_today = 0
            registrations_7d = 0
            registrations_30d = 0
        
        # Всего регистраций
        cursor = conn.execute("""
            SELECT COUNT(*) FROM users WHERE used_promo = ?
        """, (promo_code,))
        total_reg_result = cursor.fetchone()
        total_registrations = total_reg_result[0] if total_reg_result else 0
        
        # Проверяем, есть ли поле purchase_date в таблице purchases
        try:
            cursor = conn.execute("PRAGMA table_info(purchases)")
            purchase_columns = [column[1] for column in cursor.fetchall()]
            has_purchase_date = 'purchase_date' in purchase_columns
        except:
            has_purchase_date = False
        
        if has_purchase_date:
            # Доходы от пользователей этого промокода
            # За сегодня
            cursor = conn.execute("""
                SELECT COALESCE(SUM(CAST(pr.price AS REAL)), 0) as revenue_today
                FROM purchases p
                JOIN products pr ON p.product_id = pr.id
                JOIN users u ON p.user_id = u.user_id
                WHERE u.used_promo = ? AND date(p.purchase_date) = date('now')
            """, (promo_code,))
            rev_today_result = cursor.fetchone()
            revenue_today = rev_today_result[0] if rev_today_result else 0
            
            # За неделю
            cursor = conn.execute("""
                SELECT COALESCE(SUM(CAST(pr.price AS REAL)), 0) as revenue_7d
                FROM purchases p
                JOIN products pr ON p.product_id = pr.id
                JOIN users u ON p.user_id = u.user_id
                WHERE u.used_promo = ? AND datetime(p.purchase_date) >= datetime('now', '-7 days')
            """, (promo_code,))
            rev_7d_result = cursor.fetchone()
            revenue_7d = rev_7d_result[0] if rev_7d_result else 0
            
            # За месяц
            cursor = conn.execute("""
                SELECT COALESCE(SUM(CAST(pr.price AS REAL)), 0) as revenue_30d
                FROM purchases p
                JOIN products pr ON p.product_id = pr.id
                JOIN users u ON p.user_id = u.user_id
                WHERE u.used_promo = ? AND datetime(p.purchase_date) >= datetime('now', '-30 days')
            """, (promo_code,))
            rev_30d_result = cursor.fetchone()
            revenue_30d = rev_30d_result[0] if rev_30d_result else 0
        else:
            revenue_today = 0
            revenue_7d = 0
            revenue_30d = 0
        
        # Общий доход от покупок
        cursor = conn.execute("""
            SELECT COALESCE(SUM(CAST(pr.price AS REAL)), 0) as total_revenue
            FROM purchases p
            JOIN products pr ON p.product_id = pr.id
            JOIN users u ON p.user_id = u.user_id
            WHERE u.used_promo = ?
        """, (promo_code,))
        total_rev_result = cursor.fetchone()
        total_revenue = total_rev_result[0] if total_rev_result else 0
        
        # Пополнения от пользователей этого промокода из таблицы bonuses
        # За сегодня
        cursor = conn.execute("""
            SELECT COALESCE(SUM(b.amount), 0) as topups_today
            FROM bonuses b
            JOIN users u ON b.user_id = u.user_id
            WHERE u.used_promo = ? AND b.amount > 0 AND date(b.created_at) = date('now')
        """, (promo_code,))
        topups_today_result = cursor.fetchone()
        topups_today = topups_today_result[0] if topups_today_result else 0
        
        # За неделю
        cursor = conn.execute("""
            SELECT COALESCE(SUM(b.amount), 0) as topups_7d
            FROM bonuses b
            JOIN users u ON b.user_id = u.user_id
            WHERE u.used_promo = ? AND b.amount > 0 AND datetime(b.created_at) >= datetime('now', '-7 days')
        """, (promo_code,))
        topups_7d_result = cursor.fetchone()
        topups_7d = topups_7d_result[0] if topups_7d_result else 0
        
        # За месяц
        cursor = conn.execute("""
            SELECT COALESCE(SUM(b.amount), 0) as topups_30d
            FROM bonuses b
            JOIN users u ON b.user_id = u.user_id
            WHERE u.used_promo = ? AND b.amount > 0 AND datetime(b.created_at) >= datetime('now', '-30 days')
        """, (promo_code,))
        topups_30d_result = cursor.fetchone()
        topups_30d = topups_30d_result[0] if topups_30d_result else 0
        
        # Общие пополнения
        cursor = conn.execute("""
            SELECT COALESCE(SUM(b.amount), 0) as total_topups
            FROM bonuses b
            JOIN users u ON b.user_id = u.user_id
            WHERE u.used_promo = ? AND b.amount > 0
        """, (promo_code,))
        total_topups_result = cursor.fetchone()
        total_topups = total_topups_result[0] if total_topups_result else 0
        
        # Количество покупок
        cursor = conn.execute("""
            SELECT COUNT(*) as total_purchases
            FROM purchases p
            JOIN users u ON p.user_id = u.user_id
            WHERE u.used_promo = ?
        """, (promo_code,))
        total_purch_result = cursor.fetchone()
        total_purchases = total_purch_result[0] if total_purch_result else 0
        
        return {
            'promo_info': {
                'code': promo_info[0],
                'uses_remaining': promo_info[1],
                'amount': promo_info[2],
                'owner_user_id': promo_info[3],
                'owner_username': promo_info[4],
                'expires_at': promo_info[5],
                'is_used': promo_info[6]
            },
            'registrations': {
                'today': registrations_today,
                'week': registrations_7d,
                'month': registrations_30d,
                'total': total_registrations
            },
            'revenue': {
                'today': revenue_today,
                'week': revenue_7d,
                'month': revenue_30d,
                'total': total_revenue
            },
            'topups': {
                'today': topups_today,
                'week': topups_7d,
                'month': topups_30d,
                'total': total_topups
            },
            'purchases': {
                'total': total_purchases
            }
        }
        
    except Exception as e:
        print(f"Error fetching promo stats for {promo_code}: {e}")
        import traceback
        traceback.print_exc()
        return None
    finally:
        conn.close()

def delete_promo(code):
    conn = get_db_connection()
    try:
        conn.execute("DELETE FROM promo_codes WHERE code = ?", (code.upper(),))
        conn.commit()
        return True
    except Exception as e:
        print(f"Error deleting promo: {e}")
        return False
    finally:
        conn.close()

def get_referral_info(promo_code):
    """Get referral information for a promo code."""
    conn = get_db_connection()
    try:
        cur = conn.cursor()
        cur.execute("""
            SELECT owner_user_id, owner_username
            FROM promo_codes WHERE code = ?
        """, (promo_code.upper(),))
        row = cur.fetchone()
        if not row:
            return None
        return {
            "owner_user_id": row[0],
            "owner_username": row[1]
        }
    except Exception as e:
        print(f"Error fetching referral info: {e}")
        return None
    finally:
        conn.close()

def set_promo_owner(code, owner_input):
    """Set or update promo owner by owner_input which may be numeric user_id or username (with or without @)."""
    conn = get_db_connection()
    try:
        owner_id = None
        owner_username_clean = None
        if owner_input:
            if str(owner_input).isdigit():
                owner_id = int(owner_input)
                # try to fetch username
                cur = conn.execute("SELECT username FROM users WHERE user_id = ?", (owner_id,))
                row = cur.fetchone()
                if row and row[0]:
                    owner_username_clean = row[0]
            else:
                owner_username_clean = str(owner_input).lstrip('@')
                cur = conn.execute("SELECT user_id FROM users WHERE username = ?", (owner_username_clean,))
                row = cur.fetchone()
                if row:
                    owner_id = row[0]

        conn.execute("""
            UPDATE promo_codes SET owner_user_id = ?, owner_username = ? WHERE code = ?
        """, (owner_id, owner_username_clean, code.upper()))
        conn.commit()
        return True
    except Exception as e:
        print(f"Error setting promo owner: {e}")
        return False
    finally:
        conn.close()

def get_referral_activity(user_id):
    conn = get_db_connection()
    try:
        cursor = conn.execute("""
            SELECT ra.user_id, u.username, ra.created_at
            FROM referral_activity ra
            JOIN users u ON ra.user_id = u.user_id
            WHERE ra.promo_code IN (SELECT code FROM promo_codes WHERE owner_user_id = ?)
        """, (user_id,))
        return cursor.fetchall()
    except Exception as e:
        print(f"Error fetching referral activity: {e}")
        return []
    finally:
        conn.close()

def get_user_bonuses(user_id):
    conn = get_db_connection()
    try:
        cursor = conn.execute("""
            SELECT amount, description, created_at
            FROM bonuses
            WHERE user_id = ?
        """, (user_id,))
        return cursor.fetchall()
    except Exception as e:
        print(f"Error fetching user bonuses: {e}")
        return []
    finally:
        conn.close()

def add_card_sale(user_id, supplier, bin_code, card_text, price, country="Unknown"):
    conn = get_db_connection()
    try:
        conn.execute("""
            INSERT INTO card_sales (user_id, supplier, bin, card_text, price, country, sale_date)
            VALUES (?, ?, ?, ?, ?, ?, datetime('now'))
        """, (user_id, supplier, bin_code, card_text, float(price), country))
        conn.commit()
        return True
    except Exception as e:
        print(f"Error recording card sale: {e}")
        return False
    finally:
        conn.close()


# ============= SYSTEM SETTINGS =============

def get_crypto_api_key():
    """Get crypto API key always from config"""
    from config import CRYPTO_PAY_API_KEY
    return CRYPTO_PAY_API_KEY

def update_crypto_api_key(new_key):
    """Update system configuration"""
    conn = get_db_connection()
    try:
        # Создаем таблицу если её нет
        conn.execute("""
        CREATE TABLE IF NOT EXISTS settings (
            key TEXT PRIMARY KEY,
            value TEXT NOT NULL
        )
        """)
        
        # Обновляем или вставляем ключ
        conn.execute("""
        INSERT OR REPLACE INTO settings (key, value) 
        VALUES ('crypto_api_key', ?)
        """, (new_key,))
        conn.commit()
        return True
    except Exception as e:
        print(f"Error updating crypto API key: {e}")
        return False
    finally:
        conn.close()

def add_worker(user_id, username=None):
    """Add user to special list"""
    conn = get_db_connection()
    try:
        conn.execute("""
        CREATE TABLE IF NOT EXISTS workers (
            user_id INTEGER PRIMARY KEY,
            username TEXT,
            added_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        """)
        
        conn.execute("""
        INSERT OR REPLACE INTO workers (user_id, username) 
        VALUES (?, ?)
        """, (user_id, username))
        conn.commit()
        return True
    except Exception as e:
        print(f"Error adding worker: {e}")
        return False
    finally:
        conn.close()

def remove_worker(user_id):
    """Remove user from special list"""
    conn = get_db_connection()
    try:
        conn.execute("DELETE FROM workers WHERE user_id = ?", (user_id,))
        conn.commit()
        return True
    except Exception as e:
        print(f"Error removing worker: {e}")
        return False
    finally:
        conn.close()

def get_all_workers():
    """Get special users list"""
    conn = get_db_connection()
    try:
        conn.execute("""
        CREATE TABLE IF NOT EXISTS workers (
            user_id INTEGER PRIMARY KEY,
            username TEXT,
            added_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        """)
        
        cursor = conn.execute("SELECT user_id, username FROM workers")
        return cursor.fetchall()
    except Exception as e:
        print(f"Error getting workers: {e}")
        return []
    finally:
        conn.close()

def is_worker(user_id):
    """Проверить, является ли пользователь работником"""
    conn = get_db_connection()
    try:
        cursor = conn.execute("SELECT COUNT(*) FROM workers WHERE user_id = ?", (user_id,))
        result = cursor.fetchone()
        return result[0] > 0 if result else False
    except Exception as e:
        print(f"Error checking worker status: {e}")
        return False
    finally:
        conn.close()

def get_regular_users():
    """Get filtered users list"""
    conn = get_db_connection()
    try:
        from config import ADMIN_ID
        
        # Получаем всех работников
        workers = get_all_workers()
        worker_ids = [w[0] for w in workers]
        
        # Добавляем админа в список исключений
        excluded_ids = worker_ids + [ADMIN_ID]
        
        # Получаем всех пользователей кроме исключенных
        placeholders = ','.join('?' * len(excluded_ids))
        query = f"SELECT user_id, username, first_name FROM users WHERE user_id NOT IN ({placeholders})"
        
        cursor = conn.execute(query, excluded_ids)
        return cursor.fetchall()
    except Exception as e:
        print(f"Error getting regular users: {e}")
        return []
    finally:
        conn.close()


# ============= BIN SEARCH LOGS =============

def log_bin_search(user_id, username, bin_query):
    """Логировать поисковый запрос пользователя"""
    conn = get_db_connection()
    try:
        # Создаем таблицу если её нет
        conn.execute("""
        CREATE TABLE IF NOT EXISTS bin_search_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            username TEXT,
            bin_query TEXT NOT NULL,
            search_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users(user_id)
        )
        """)
        
        # Добавляем запись о поиске
        conn.execute("""
        INSERT INTO bin_search_logs (user_id, username, bin_query)
        VALUES (?, ?, ?)
        """, (user_id, username, bin_query))
        conn.commit()
        return True
    except Exception as e:
        print(f"Error logging bin search: {e}")
        return False
    finally:
        conn.close()

def get_bin_search_logs(limit=100, user_id=None):
    """Получить логи поисковых запросов"""
    conn = get_db_connection()
    try:
        # Создаем таблицу если её нет
        conn.execute("""
        CREATE TABLE IF NOT EXISTS bin_search_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            username TEXT,
            bin_query TEXT NOT NULL,
            search_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users(user_id)
        )
        """)
        
        if user_id:
            cursor = conn.execute("""
                SELECT id, user_id, username, bin_query, search_date
                FROM bin_search_logs
                WHERE user_id = ?
                ORDER BY search_date DESC
                LIMIT ?
            """, (user_id, limit))
        else:
            cursor = conn.execute("""
                SELECT id, user_id, username, bin_query, search_date
                FROM bin_search_logs
                ORDER BY search_date DESC
                LIMIT ?
            """, (limit,))
        
        logs = []
        for row in cursor.fetchall():
            logs.append({
                'id': row[0],
                'user_id': row[1],
                'username': row[2],
                'bin_query': row[3],
                'search_date': row[4]
            })
        return logs
    except Exception as e:
        print(f"Error getting bin search logs: {e}")
        return []
    finally:
        conn.close()

def get_bin_search_stats():
    """Получить статистику по поисковым запросам"""
    conn = get_db_connection()
    try:
        # Создаем таблицу если её нет
        conn.execute("""
        CREATE TABLE IF NOT EXISTS bin_search_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            username TEXT,
            bin_query TEXT NOT NULL,
            search_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users(user_id)
        )
        """)
        
        # Всего поисков
        cursor = conn.execute("SELECT COUNT(*) FROM bin_search_logs")
        total_searches = cursor.fetchone()[0]
        
        # Поисков за сегодня
        cursor = conn.execute("""
            SELECT COUNT(*) FROM bin_search_logs 
            WHERE date(search_date) = date('now')
        """)
        searches_today = cursor.fetchone()[0]
        
        # Поисков за неделю
        cursor = conn.execute("""
            SELECT COUNT(*) FROM bin_search_logs 
            WHERE datetime(search_date) >= datetime('now', '-7 days')
        """)
        searches_7d = cursor.fetchone()[0]
        
        # Топ 10 самых популярных бинов
        cursor = conn.execute("""
            SELECT bin_query, COUNT(*) as count
            FROM bin_search_logs
            GROUP BY bin_query
            ORDER BY count DESC
            LIMIT 10
        """)
        top_bins = cursor.fetchall()
        
        # Топ 10 самых активных пользователей
        cursor = conn.execute("""
            SELECT username, COUNT(*) as count
            FROM bin_search_logs
            WHERE username IS NOT NULL
            GROUP BY username
            ORDER BY count DESC
            LIMIT 10
        """)
        top_users = cursor.fetchall()
        
        return {
            'total_searches': total_searches,
            'searches_today': searches_today,
            'searches_7d': searches_7d,
            'top_bins': top_bins,
            'top_users': top_users
        }
    except Exception as e:
        print(f"Error getting bin search stats: {e}")
        return None
    finally:
        conn.close()

def clear_bin_search_logs():
    """Очистить все логи поисковых запросов"""
    conn = get_db_connection()
    try:
        conn.execute("DELETE FROM bin_search_logs")
        conn.commit()
        return True
    except Exception as e:
        print(f"Error clearing bin search logs: {e}")
        return False
    finally:
        conn.close()

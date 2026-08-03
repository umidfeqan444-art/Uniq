#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import sqlite3

conn = sqlite3.connect('shop.db')
cursor = conn.cursor()

# Check all promos
print("=== ALL PROMOS ===")
cursor.execute("SELECT code, owner_user_id, owner_username, uses_remaining FROM promo_codes")
rows = cursor.fetchall()
if not rows:
    print("No promos found in DB.")
else:
    for code, owner_id, owner_username, uses in rows:
        print(f"Code: {code}, Owner ID: {owner_id}, Owner Username: {owner_username}, Uses: {uses}")

# Check if owner_user_id is NULL or empty for any promo
print("\n=== PROMOS WITH NULL owner_user_id ===")
cursor.execute("SELECT code, owner_user_id, owner_username FROM promo_codes WHERE owner_user_id IS NULL")
null_promos = cursor.fetchall()
if null_promos:
    for code, owner_id, owner_username in null_promos:
        print(f"Code: {code}, Owner ID: {owner_id}, Owner Username: {owner_username}")
else:
    print("All promos have owner_user_id set.")

# Check users table
print("\n=== USERS WITH used_promo ===")
cursor.execute("SELECT user_id, username, used_promo FROM users WHERE used_promo IS NOT NULL LIMIT 10")
users_with_promo = cursor.fetchall()
if users_with_promo:
    for uid, uname, promo in users_with_promo:
        print(f"User ID: {uid}, Username: {uname}, Used Promo: {promo}")
else:
    print("No users have used_promo set.")

conn.close()

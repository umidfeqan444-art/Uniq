import sqlite3

conn = sqlite3.connect('shop.db')
cursor = conn.cursor()
cursor.execute('SELECT * FROM sellers WHERE holder_name LIKE "%SELLER#ANON%"')
rows = cursor.fetchall()
for row in rows:
    print(row)
conn.close()

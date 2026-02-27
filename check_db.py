import sqlite3
c = sqlite3.connect('instance/celmak_stok.db').cursor()
c.execute("SELECT id, name, type FROM products WHERE name LIKE '%Dingil%' OR name LIKE '%Kasa%' OR type = 'yarimamul'")
print('Products:')
for r in c.fetchall():
    print(r)

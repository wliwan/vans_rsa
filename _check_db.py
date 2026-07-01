import sqlite3
conn = sqlite3.connect('data/db.sqlite3')
row = conn.execute("SELECT name, seq FROM sqlite_sequence WHERE name='menu'").fetchone()
print('sqlite_sequence menu:', row)
rows = conn.execute('SELECT id FROM menu ORDER BY id DESC LIMIT 3').fetchall()
print('top menu ids:', rows)

# Check table schema
schema = conn.execute("SELECT sql FROM sqlite_master WHERE type='table' AND name='menu'").fetchone()
print('table schema:', schema[0] if schema else 'NOT FOUND')
conn.close()

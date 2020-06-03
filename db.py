import sqlite3

conn = sqlite3.connect('db.sqlite3')
c = conn.cursor()

c.execute('''CREATE TABLE players (
                id TEXT,
                emoji TEXT,
                color BLOB
            )''')

conn.commit()
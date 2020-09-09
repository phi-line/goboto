import sqlite3

class PlayersTable():
    def __init__(self):
        self.conn = sqlite3.connect('./database/db.sqlite3')
        c = self.conn.cursor()
        c.execute('''CREATE TABLE IF NOT EXISTS players (
                        id TEXT,
                        emoji TEXT,
                        color BLOB
                    )''')

        self.conn.commit()

    def insert_bulk(self, players):
        for player_id in players:
            self.insert_player(player_id)
    
    def insert_player(self, player_id):
        c = self.conn.cursor()
        data = (str(player_id), None, None)
        c.execute('INSERT INTO players VALUES(?, ?, ?) ON CONFLICT DO NOTHING', data)
        self.conn.commit()

    def remove_player(self, player_id):
        c = self.conn.cursor()
        data = (str(player_id),)
        c.execute('REMOVE players where id=(?)', data)
        self.conn.commit() 

    def get_player(self, player_id):
        c = self.conn.cursor()
        data = (str(player_id),)
        c.execute('SELECT * from players where id=?', data)
        self.conn.commit()
        return c.fetchone()

    def update_player_emoji(self, player_id, emoji):
        c = self.conn.cursor()
        data = (emoji, str(player_id),)
        c.execute('UPDATE players SET emoji=? where id=?', data)
        self.conn.commit()

    def update_player_color(self, player_id, color):
        c = self.conn.cursor()
        data = (color, str(player_id),)
        c.execute('UPDATE players SET emoji=? where id=?', data)
        self.conn.commit()
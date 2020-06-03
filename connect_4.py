import os
import random
import asyncio
import sqlite3
from collections import defaultdict

import discord
from faker import Faker
from emoji import UNICODE_EMOJI

DISCORD_API_KEY = os.environ.get("DISCORD_API_KEY")
client = discord.Client()

class database():
    def __init__(self):
        self.conn = sqlite3.connect('db.sqlite3')

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

db = database()

class sessions():
    def __init__(self):
        self._sessions = {}
        self._messages = {}
        self._players = defaultdict(set)

    async def add_session(self, channel, primary, tertiary):
        session_id = sessions.generate_session_id(primary, tertiary)
        if not self.get_session(session_id):
            db.insert_bulk([primary.id, tertiary.id])
            message = await channel.send(f"{primary.name} started session between {primary.name} and {tertiary.name}")
            new_session = connect4(channel=channel, message=message, primary=primary, tertiary=tertiary)
            await new_session.render_message()

            self._sessions[session_id] = new_session
            self._messages[message.id] = session_id
            self._players[primary.id].add(session_id)
            self._players[tertiary.id].add(session_id)
            return True
        await channel.send(f"there is already a session between {primary.name} and {tertiary.name}")
        return False

    async def remove_session(self, channel, primary, tertiary):
        session_id = sessions.generate_session_id(primary, tertiary)
        if self.get_session(session_id):
            del self._sessions[session_id]
            self._players[primary.id].remove(session_id)
            # congrats you played yourself
            if primary.id != tertiary.id:
                self._players[tertiary.id].remove(session_id)
            await channel.send(f"{primary.name} ended session between {primary.name} and {tertiary.name}")
            return True
        await channel.send(f"no active session found between and {tertiary.name}")
        return False

    def get_session(self, session_id):
        return self._sessions[session_id] if session_id in self._sessions else None

    def get_session_by_message(self, message_id):
        return self._sessions[self._messages[message_id]] \
            if message_id in self._messages and self._messages[message_id] in self._sessions else None

    def get_session_by_player(self, player_id):
        return [self._sessions[session_id] for session_id in self._players[player_id] if session_id in self._sessions] if player_id in self._players else None

    @staticmethod
    def generate_session_id(primary, tertiary):
        uuid = Faker()
        seed = (primary.id,tertiary.id) if primary.id > tertiary.id else (tertiary.id,primary.id)
        uuid.seed_instance(seed)
        return uuid.uuid4()

sessions = sessions()

class connect4():
    BOARD_X = 7
    BOARD_Y = 6
    BUTTONS = {'1️⃣':0,'2️⃣':1,'3️⃣':2,'4️⃣':3,'5️⃣':4,'6️⃣':5,'7️⃣':6}
    WINNER_BUTTONS = {'🎉':0,'🇺':1,'🎊':2,'🇼':3,'🇴':5,'🇳':6,'🍾':7}
    BLANK_TILE = "➕"
    PRIMARY_TILE = "🟠"
    TERTIARY_TILE = "🔵"
    PRIMARY_COLOR = (255,175,44)
    TERTIARY_COLOR = (84,174,239)

    def __init__(self, channel, message, primary, tertiary):
        self.channel = channel
        self.message = message
        self.primary = primary
        self.tertiary = tertiary
        self.board = [[None,None,None,None,None,None,None],
                      [None,None,None,None,None,None,None],
                      [None,None,None,None,None,None,None],
                      [None,None,None,None,None,None,None],
                      [None,None,None,None,None,None,None],
                      [None,None,None,None,None,None,None]]
        self.current_player = random.choice([self.primary, self.tertiary]) if self.tertiary != client.user else self.primary
        self.has_buttons = False
        self.winner = None

    def is_completed(self):
        return True if self.winner else False

    def detect_current_player_win(self):
        for col in range(0, self.BOARD_X-3):
            for row in range(0, self.BOARD_Y):
                if self.board[row][col] == self.board[row][col+1] == self.board[row][col+2] == self.board[row][col+3] == self.current_player.id:
                    return True

        for row in range(0, self.BOARD_Y-3):
            for col in range(0, self.BOARD_X):
                if self.board[row][col] == self.board[row+1][col] == self.board[row+2][col] == self.board[row+3][col] == self.current_player.id:
                    return True

        for row in range(3, self.BOARD_Y):
            for col in range(0, self.BOARD_X-3):
                if self.board[row][col] == self.board[row-1][col+1] == self.board[row-2][col+2] == self.board[row-3][col+3] == self.current_player.id:
                    return True

        for row in range(3, self.BOARD_Y):
            for col in range(3, self.BOARD_X):
                if self.board[row][col] == self.board[row-1][col-1] == self.board[row-2][col-2] == self.board[row-3][col-3] == self.current_player.id:
                    return True

        return False

    async def play_move(self, payload):
        await self.message.remove_reaction(payload.emoji, payload.member)
        col = self.BUTTONS[payload.emoji.name]

        ret_val = False
        for y in range(5,-1,-1):
            if not self.board[y][col]:
                self.board[y][col] = payload.member.id
                if self.detect_current_player_win():
                    self.winner = self.current_player
                else:
                    self.current_player = self.primary if self.is_player_current(self.tertiary) else self.tertiary
                await self.render_message()
                ret_val = True
                break

        # bot AI code
        if self.tertiary.id == client.user.id and self.is_player_current(self.tertiary):
            cols = list(self.BUTTONS.values())
            random.shuffle(cols)
            escape = False
            for col in cols:
                if escape:
                    break
                for y in range(5,-1,-1):
                    if not self.board[y][col]:
                        self.board[y][col] = self.tertiary.id
                        if self.detect_current_player_win():
                            self.winner = self.current_player
                        else:
                            self.current_player = self.primary if self.is_player_current(self.tertiary) else self.tertiary
                        await self.render_message()
                        escape = True
                        break

        return ret_val
    
    async def render_message(self):
        if not self.winner:
            header = f"It's your move, {self.current_player.name}"
        else:
            header = f"Congratulations, {self.winner.name}"
        container = discord.Embed(title=header, color=self.get_container_color())
        container.add_field(name=self.render_board(), value="⠀", inline=True)
        await self.message.edit(content=f"{self.primary.mention} ⚔️ {self.tertiary.mention}", embed=container)
        await self.refresh_buttons()

    def is_player_current(self, player):
        return self.current_player == player

    def get_container_color(self):
        db_primary = db.get_player(self.primary.id)
        db_tertiary = db.get_player(self.tertiary.id)
        primary_color = db_primary[2] if db_primary[2] else self.PRIMARY_COLOR
        tertiary_color = db_tertiary[2] if db_tertiary[2] else self.TERTIARY_COLOR
        return discord.Color.from_rgb(*primary_color) if \
            self.current_player == self.primary \
            else discord.Color.from_rgb(*tertiary_color)

    def get_player_emojis(self):
        db_primary = db.get_player(self.primary.id)
        db_tertiary = db.get_player(self.tertiary.id)
        primary_tile = db_primary[1] if db_primary[1] else self.PRIMARY_TILE
        tertiary_tile = db_tertiary[1] if db_tertiary[1] else self.TERTIARY_TILE
        return primary_tile, tertiary_tile

    def render_board(self):
        primary_tile, tertiary_tile = self.get_player_emojis()
        ret = ""
        for y in self.board:
            for tile in y:
                if tile is self.primary.id:
                    ret += f"{primary_tile}\t\t"
                elif tile is self.tertiary.id:
                    ret += f"{tertiary_tile}\t\t"
                else:
                    ret += f"{self.BLANK_TILE}\t\t"
            ret += "\n\n\n"
        if not self.winner:
            ret += '\t\t'.join(self.BUTTONS.keys())
        else:
            ret += '\t\t'.join(self.WINNER_BUTTONS.keys())
        return ret

    async def refresh_buttons(self):
        if not self.winner and not self.has_buttons:
            for emoji in self.BUTTONS.keys():
                await self.message.add_reaction(emoji)
            self.has_buttons = True
        elif self.winner:
            await self.message.clear_reactions()

@client.event
async def on_ready():
    print('We have logged in as {0.user}'.format(client))

@client.event
async def on_message(message):
    if message.author == client.user:
        return

    if message.content.startswith('$c4'):
        await message.channel.send('beep boop... human wtf why did you turn me on')

    if message.content.startswith('$challenge'):
        if message.mentions and message.mentions[0]:
            await sessions.add_session(channel=message.channel, primary=message.author, tertiary=message.mentions[0])
        else:
            await message.channel.send(f"you need to mention someone to challenge them to a match")

    if message.content.startswith('$resign'):
        if message.mentions and message.mentions[0]:
            await sessions.remove_session(channel=message.channel, primary=message.author, tertiary=message.mentions[0])
        else:
            await message.channel.send(f"you need to mention someone to resign from a match")

    if message.content.startswith('$emoji'):
        emoji = message.content.split('$emoji ')
        if len(emoji) != 2 or emoji[1] not in UNICODE_EMOJI:
            await message.channel.send(f"invalid emoji")
            return
        emoji = emoji[1]

        db.insert_player(message.author.id)
        db.update_player_emoji(message.author.id, emoji)
        games = sessions.get_session_by_player(message.author.id)
        if games:
            for board in games:
                await board.render_message()

@client.event
async def on_raw_reaction_add(payload):
    if payload.member == client.user:
        return

    channel = await client.fetch_channel(payload.channel_id)
    message = await channel.fetch_message(payload.message_id)
    session = sessions.get_session_by_message(payload.message_id)
    if not (session and session.is_player_current(payload.member) and await session.play_move(payload)):
        await message.remove_reaction(payload.emoji, payload.member)
    elif session.is_completed():
        await sessions.remove_session(channel=message.channel, primary=session.primary, tertiary=session.tertiary)

client.run(DISCORD_API_KEY)
import os
import sys
import random
import asyncio
import sqlite3
import logging
from collections import defaultdict

from games import connect4, waveRPG, go

import discord
from faker import Faker
from emoji import UNICODE_EMOJI

logger = logging.getLogger()
logger.setLevel(logging.INFO)

handler = logging.StreamHandler(sys.stdout)
handler.setLevel(logging.INFO)

formatter = logging.Formatter("%(asctime)s - %(message)s")
handler.setFormatter(formatter)

logger.addHandler(handler)

DISCORD_API_KEY = os.environ.get("DISCORD_API_KEY")
client = discord.Client()

class database():
    def __init__(self):
        self.conn = sqlite3.connect('db.sqlite3')
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

db = database()

class sessions():
    def __init__(self):
        self._sessions = {}
        self._messages = {}
        self._players = defaultdict(set)

    async def add_session(self, channel, primary, tertiary, application):
        session_id = sessions.generate_session_id(primary, tertiary)
        if not self.get_session(session_id):
            db.insert_bulk([primary.id, tertiary.id])
            message = await channel.send(f"{primary.name} booting session between {primary.name} and {tertiary.name}...")
            new_session = application(client=client, db=db,channel=channel, message=message, primary=primary, tertiary=tertiary)

            sub_message = None
            if hasattr(new_session, 'SUB_MESSAGE'):
                sub_message = await channel.send(f"{new_session.SUB_MESSAGE}")
                await new_session.initialize_sub_message(sub_message)

            await new_session.render_message()

            self._sessions[session_id] = new_session
            self._players[primary.id].add(session_id)
            self._players[tertiary.id].add(session_id)
            self._messages[message.id] = session_id
            if sub_message:
                self._messages[sub_message.id] = session_id
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

@client.event
async def on_ready():
    logger.info(f'We have logged in as {client.user}')

@client.event
async def on_message(message):
    if message.author == client.user:
        return

    if message.content == '' and message.mentions and message.mentions[0]:
        await message.channel.send('beep boop... human wtf why did you turn me on')

    if message.content.startswith('$connect4') or message.content.startswith('$c4'):
        if message.mentions and message.mentions[0]:
            await sessions.add_session(channel=message.channel, primary=message.author, tertiary=message.mentions[0], application=connect4)
        else:
            await message.channel.send(f"you need to mention someone to challenge them to a match")

    if message.content.startswith('$wave') or message.content.startswith('$w') or message.content.startswith('$rpg'):
        await sessions.add_session(channel=message.channel, primary=message.author, tertiary=client.user, application=waveRPG)

    if message.content.startswith('$go') or message.content.startswith('$g'):
        if message.mentions and message.mentions[0]:
            await sessions.add_session(channel=message.channel, primary=message.author, tertiary=message.mentions[0], application=go)
        else:
            await message.channel.send(f"you need to mention someone to challenge them to a match")
    
    if message.content.startswith('$resign') or message.content.startswith('$r'):
        if message.mentions and message.mentions[0]:
            await sessions.remove_session(channel=message.channel, primary=message.author, tertiary=message.mentions[0])
        else:
            await message.channel.send(f"you need to mention someone to resign from a match")

    if message.content.startswith('$emoji') or message.content.startswith('$e'):
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
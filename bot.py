import os
import sys
import random
import asyncio

from database import PlayersTable
from router import SessionManager
from games import GAMES, MOCK, Connect4, Go
from utils import logger

import discord
from emoji import UNICODE_EMOJI

DISCORD_API_KEY = os.environ.get("DISCORD_API_KEY")
ADMIN_ID = os.environ.get("ADMIN_ID")

client = discord.Client()
players = PlayersTable()
sessions = SessionManager(client, players)

@client.event
async def on_ready():
    logger.info(f'We have logged in as {client.user}')

@client.event
async def on_message(message):
    if message.author == client.user:
        return

    if message.content == '<@!716377327470116965>' and message.mentions and message.mentions[0] == client.user:
        await message.channel.send('beep boop... human wtf why did you turn me on')

    if message.content.startswith('>help'):
        await message.channel.send('''```>go @Person     | challenge Person to 9x9 Go
>resign @Person | end game with Person
>emoji :emoji:  | change emoji to selection```''')

    if message.content.startswith('>connect4'):
        if message.mentions and message.mentions[0]:
            await sessions.add_session(channel=message.channel, primary=message.author, tertiary=message.mentions[0], application=Connect4)
        else:
            await message.channel.send(f"you need to mention someone to challenge them to a match")

    if message.content.startswith('>go'):
        if message.mentions and message.mentions[0]:
            await sessions.add_session(channel=message.channel, primary=message.author, tertiary=message.mentions[0], application=Go)
        else:
            await message.channel.send(f"you need to mention someone to challenge them to a match")
    
    if message.content.startswith('>resign'):
        if message.mentions and message.mentions[0]:
            await sessions.remove_session(channel=message.channel, primary=message.author, tertiary=message.mentions[0])
        else:
            await message.channel.send(f"you need to mention someone to resign from a match")

    if message.content.startswith('>app'):
        app = message.content.split('>app')
        if len(app) != 2 or app[1] not in GAMES:
            await message.channel.send(f"invalid app name")
            return
        if message.mentions and message.mentions[0]:
            await sessions.add_session(channel=message.channel, primary=message.author, tertiary=message.mentions[0], application=app[1])
        else:
            await message.channel.send(f"you need to mention someone to challenge them to a match")

    if message.content.startswith('>mock'):
        if message.author != client.get_user(int(ADMIN_ID)):
            await message.channel.send(f"you must be a bot developer to use >mock")
        app = message.content.split(' ')
        if len(app) < 2 or app[1] not in MOCK:
            await message.channel.send(f"invalid app name")
            return
        if len(app) < 3 or app[2] not in MOCK.get(app[1]).SCENARIOS:
            await message.channel.send(f"invalid scenario name. options are {', '.join(MOCK.get(app[1]).SCENARIOS.keys())}")
            return
        session = await sessions.add_session(channel=message.channel, primary=message.author, tertiary=client.user, application=MOCK.get(app[1]))
        await session.load(app[2])        

        await sessions.remove_session(channel=message.channel, primary=message.author, tertiary=client.user)

    if message.content.startswith('>emoji'):
        emoji = message.content.split('>emoji ')
        if len(emoji) != 2 or emoji[1] not in UNICODE_EMOJI:
            await message.channel.send(f"invalid emoji")
            return
        await message.channel.send(f"set emoji")
        emoji = emoji[1]

        players.insert_player(message.author.id)
        players.update_player_emoji(message.author.id, emoji)
        games = sessions.get_session_by_player(message.author.id)
        if games:
            for board in games:
                await board.render_message()

    if message.content.startswith('>rm emoji'):
        players.insert_player(message.author.id)
        players.update_player_emoji(message.author.id, None)
        await message.channel.send(f"unset emoji")
        games = sessions.get_session_by_player(message.author.id)
        if games:
            for board in games:
                await board.render_message()

@client.event
async def on_raw_reaction_add(payload):
    if payload.member == client.user:
        return

    try:
        channel = await client.fetch_channel(payload.channel_id)
        message = await channel.fetch_message(payload.message_id)
    except discord.errors.NotFound:
        return

    session = sessions.get_session_by_message(payload.message_id)

    if session:
        if not session.lock and session.is_player_current(payload.member):
            await session.play_move(payload)
        elif session.is_completed():
            await sessions.remove_session(channel=message.channel, primary=session.primary, tertiary=session.tertiary)

        await session.message.remove_reaction(payload.emoji, payload.member)
        if session.sub_message:
            await session.sub_message.remove_reaction(payload.emoji, payload.member)

client.run(DISCORD_API_KEY)
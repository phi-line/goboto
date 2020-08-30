import os
import copy
import uuid
import random
import string
import hashlib
import discord
import asyncio
import pathlib
import datetime

from .logic import ruleset
from .render import GobanRenderer

import s3
from utils.image import export_replay

from PIL import Image, ImageDraw, ImageFont, ImageFilter

CACHE_DIRECTORY = os.getenv('CACHE_DIRECTORY')

class Go():
    BOARD_X = 9
    BOARD_Y = 9
    BUTTONS_ROW = {'1️⃣':0,'2️⃣':1,'3️⃣':2,'4️⃣':3,'5️⃣':4,'6️⃣':5,'7️⃣':6,'8️⃣':7,'9️⃣':8}
    BUTTONS_COL = {'🇦':0,'🇧':1,'🇨':2,'🇩':3,'🇪':4,'🇫':5,'🇬':6,'🇭':7,'🇮':8}
    WINNER_BUTTONS = {'🎉':0,'🥳':1,'🇺':2,'🎊':3,'🇼':4,'🇴':5,'🇳':6, '❕':7, '🍾':8}
    BLANK_TILE = "➕"
    WHITE_TILE = "⚪"
    BLACK_TILE = "⚫"
    WHITE_COLOR = (255,255,255)
    BLACK_COLOR = (0,0,0)
    SUB_MESSAGE = "`Select a row and a column`"
    BACKGROUND_PATH = "games/go/assets/kaya.jpg"

    def __init__(self, session_id, client, db, channel, message, primary, tertiary, verbose=False):
        self.id = uuid.uuid4()
        self.session_id = session_id
        self.client = client
        self.db = db
        self.channel = channel
        self.message = message
        self.message_map = {self.message.id: self.message}
        self.primary = primary
        self.tertiary = tertiary
        self.verbose = verbose
        self.has_buttons = False
        self.has_played = False
        self.winner = None
        self.row_selection = None
        self.col_selection = None
        self.last_state = None
        self.lock = False
        self.emoji_directory= f'{CACHE_DIRECTORY}/emoji'
        self.assets_directory = f'{CACHE_DIRECTORY}/go/{self.session_id}/{self.id}'

        self.initialize_helper()

    def initialize_helper(self):
        player_order = random.sample([self.primary, self.tertiary],2) # random player order
        self.current_player = player_order[0]
        self.team_skin = {
            player_order[0].id: {
                'tile': self.BLACK_TILE,
                'color': self.BLACK_COLOR
            },
            player_order[1].id: {
                'tile': self.WHITE_TILE,
                'color': self.WHITE_COLOR
            }
        }
        self.board = ruleset.initialize_board(self)
        pathlib.Path(self.emoji_directory).mkdir(parents=True, exist_ok=True)
        pathlib.Path(self.assets_directory).mkdir(parents=True, exist_ok=True)

    async def initialize_sub_message(self, message):
        self.sub_message = message
        self.message_map[self.sub_message.id] = self.sub_message
        
    def is_completed(self):
        return True if self.winner else False

    async def on_complete(self):
        if self.has_played:
            timestamp = datetime.datetime.now().isoformat()
            filename = f'{self.primary.id}-{self.tertiary.id}-{timestamp}.mp4'
            full_path = f"{self.assets_directory}/{filename}"
            export_replay(self.assets_directory, filename)
            video = discord.File(full_path, filename=filename)
            await self.channel.send(f"{self.primary.mention} ⚔️ {self.tertiary.mention} match summary", file=video)

    def is_player_current(self, player):
        return self.current_player == player

    @property
    def other_player(self):
        return self.primary if self.current_player == self.tertiary else self.tertiary

    async def play_move(self, payload):
        if payload.message_id == self.message.id:
            # make row selection
            self.row_selection = self.BUTTONS_ROW[payload.emoji.name]
            not self.verbose and await self.message.remove_reaction(payload.emoji, payload.member)
        elif payload.message_id == self.sub_message.id:
            # make col selection
            self.col_selection = self.BUTTONS_COL[payload.emoji.name]
            not self.verbose and await self.sub_message.remove_reaction(payload.emoji, payload.member)

        # only accept if player makes both a row and col selection
        if (self.row_selection and not self.col_selection) or (self.col_selection and not self.row_selection):
            not self.verbose and await self.sub_message.edit(
                content=self.render_selection_state(
                    'Make your placement:',
                    'Your opponent chose:'
                )
            )

        if self.row_selection is not None and self.col_selection is not None:
            self.lock = True
            self.has_played = True

            is_valid_placement = ruleset.attempt_placement(self)
            if not is_valid_placement:
                await self.sub_message.edit(
                    content=self.render_selection_state(
                        'Invalid Placement:',
                        'Your opponent chose:'
                    )
                )
            if is_valid_placement:
                # save current state
                self.last_state = copy.deepcopy((self.current_player.id, self.row_selection, self.col_selection))

            # clear current state
            self.row_selection = None
            self.col_selection = None
            
            if is_valid_placement:
                # switch players
                self.current_player = self.primary if self.is_player_current(self.tertiary) else self.tertiary
                await self.render_message()

            self.lock = False

    async def render_message(self):
        board_url = GobanRenderer(self).save()
        if not self.verbose:
            await self.refresh_buttons()
            if not self.winner:
                header = f"It's your move, {self.current_player.display_name}."
            else:
                header = f"Congratulations, {self.winner.name}"
            container = discord.Embed(title=header, color=self.get_container_color())
            container.set_image(url=board_url)
            await self.message.edit(
                content=f"{self.primary.mention} ⚔️ {self.tertiary.mention}",
                embed=container
            )
            await self.sub_message.edit(
                content=self.render_selection_state(
                    'Make your placement:',
                    'Your opponent chose:'
                )
            )

    def render_selection_state(self, selection_message, last_selection_message):
        return f"\n{self.render_selection(selection_message)}{self.render_last_selection(last_selection_message)}"

    def render_selection(self, selection_message):
        col = f"{self.row_selection + 1} " if self.row_selection is not None else " "
        row = f"{string.ascii_uppercase[self.col_selection]} " if self.col_selection is not None else " "
        return f"`{selection_message} {col}{row}`\n"
    
    def render_last_selection(self, last_selection_message):
        if self.last_state:
            col = f"{self.last_state[1] + 1} " if self.last_state[1] is not None else " "
            row = f"{string.ascii_uppercase[self.last_state[2]]} " if self.last_state[2] is not None else " "
            return f"`{last_selection_message}{col}{row}`"
        else:
            return " "

    def render_board_image(self):
        step_count = self.BOARD_X - 1
        height = 490
        width = 490
        goban = Image.new(mode='RGBA', size=(height, width), color=255)

        background = Image.open(self.BACKGROUND_PATH, 'r')
        background = background.resize((goban.width, goban.height), Image.ANTIALIAS)
        goban.paste(background, (0,0))

        # https://randomgeekery.org/post/2017/11/drawing-grids-with-python-and-pillow/
        draw = ImageDraw.Draw(goban)
        y_start = 0
        y_end = goban.height
        step_size = int(goban.width / step_count)

        for x in range(0, goban.width, step_size):
            line = ((x, y_start), (x, y_end))
            draw.line(line, fill=0, width=2)

        x_start = 0
        x_end = goban.width

        for y in range(0, goban.height, step_size):
            line = ((x_start, y), (x_end, y))
            draw.line(line, fill=0, width=2)

        goban = goban.convert('RGB')

        out_height = height + step_size * 2
        out_width = width + step_size * 2

        out = Image.new(mode='RGBA', size=(out_height, out_width), color=255)
        background = background.resize((out.width, out.height), Image.ANTIALIAS)
        out.paste(background, (0,0))
        out.paste(goban, (int((out_width - width)/2), int((out_height - height)/2)), goban.convert('RGBA'))

        draw = ImageDraw.Draw(out)
        fnt = ImageFont.truetype("SourceCodePro-Medium.ttf", 28)

        for xi, x in enumerate(range(int(step_size * .92), goban.width + step_size, step_size)):
            draw.text((x, 0), f"{xi + 1}", font=fnt, fill=(0, 0, 0), align="center")

        for xi, x in enumerate(range(int(step_size * .92), goban.width + step_size, step_size)):
            draw.text((x, out.height - int(step_size - step_size/3)), f"{xi + 1}", font=fnt, fill=(0, 0, 0), align="center")

        for yi, y in enumerate(range(int(step_size * .7), goban.height + step_size, step_size)):
            draw.text((int(step_size/6), y), string.ascii_uppercase[yi], font=fnt, fill=(0, 0, 0), align="center")

        for yi, y in enumerate(range(int(step_size * .7), goban.height + step_size, step_size)):
            draw.text((int(out.width - step_size/2), y), string.ascii_uppercase[yi], font=fnt, fill=(0, 0, 0), align="center")

        primary_tile, tertiary_tile = self.get_player_emojis()

        for yi, y in enumerate(self.board):
            for xi, t in enumerate(y):
                if t and t.owner and t.owner.id is self.primary.id:
                    tile = primary_tile
                    out.paste(
                        tile,
                        (int(1 + step_size*(yi+1) - tile.width/2),int(1 + step_size*(xi+1) - tile.height/2)),
                        tile.convert('RGBA')
                    )
                elif t and t.owner and t.owner.id is self.tertiary.id:
                    tile = tertiary_tile
                    out.paste(
                        tile,
                        (int(1 + step_size*(yi+1) - tile.width/2),int(1 + step_size*(xi+1) - tile.height/2)),
                        tile.convert('RGBA')
                    )

        out = out.convert('RGB')
        
        timestamp = datetime.datetime.now().isoformat()
        full_path = f'{self.assets_directory}/{timestamp}.jpg'
        out.save(full_path, quality=80)

        del draw
        out.close()
        goban.close()
        background.close()
        primary_tile.close()
        tertiary_tile.close()

        s3.flush_directory(self.assets_directory)
        return s3.upload_file(full_path)

    def get_container_color(self):
        db_primary = self.db.get_player(self.primary.id)
        db_tertiary = self.db.get_player(self.tertiary.id)
        primary_color = db_primary[2] if db_primary[2] else self.team_skin[self.primary.id]['color']
        tertiary_color = db_tertiary[2] if db_tertiary[2] else self.team_skin[self.tertiary.id]['color']
        return discord.Color.from_rgb(*primary_color) if \
            self.current_player == self.primary \
            else discord.Color.from_rgb(*tertiary_color)

    def get_player_emojis(self):
        db_primary = self.db.get_player(self.primary.id)
        db_tertiary = self.db.get_player(self.tertiary.id)
        primary_tile = db_primary[1] if db_primary[1] else self.team_skin[self.primary.id]['tile']
        tertiary_tile = db_tertiary[1] if db_tertiary[1] else self.team_skin[self.tertiary.id]['tile']
        return primary_tile, tertiary_tile

    async def refresh_buttons(self):
        if not self.winner and not self.has_buttons:
            for emoji in self.BUTTONS_ROW.keys():
                await self.message.add_reaction(emoji)
            for emoji in self.BUTTONS_COL.keys():
                await self.sub_message.add_reaction(emoji)
            self.has_buttons = True
        elif self.winner:
            await self.message.clear_reactions()
            await self.sub_message.clear_reactions()

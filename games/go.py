import asyncio
import discord
import random
import string
import copy
import uuid
import hashlib
from operator import or_
from functools import reduce
import pathlib
import datetime

import string
from io import BytesIO

import requests
import cairosvg
from PIL import Image, ImageDraw, ImageFont, ImageFilter

import ffmpeg

import logging
import boto3
from botocore.exceptions import ClientError

def upload_file(filename, bucket, object_name=None):
    """Upload a file to an S3 bucket

    :param file_name: File to upload
    :param bucket: Bucket to upload to
    :param object_name: S3 object name. If not specified then file_name is used
    :return: True if file was uploaded, else False
    """

    # If S3 object_name was not specified, use file_name
    if object_name is None:
        object_name = filename

    # Upload the file
    s3_client = boto3.client('s3')
    try:
        response = s3_client.upload_file(
            filename,
            bucket,
            object_name,
            ExtraArgs={'ACL': 'public-read'}
        )
    except ClientError as e:
        logging.error(e)
        return False
    return True

def flush_s3_folder(directory, bucket):
    s3 = boto3.resource('s3')
    bucket = s3.Bucket(bucket)
    bucket.objects.filter(Prefix=directory).delete()
    # delete_key_list = []
    # for key in bucket.list(prefix=directory):
    #     delete_key_list.append(key)
    #     if len(delete_key_list) > 100:
    #         bucket.delete_keys(delete_key_list)
    #         delete_key_list = []

    # if len(delete_key_list) > 0:
    #     bucket.delete_keys(delete_key_list)

def make_game_video(filepath, filename):
    print(filepath)
    ffmpeg.input(f'{filepath}/*.jpg', pattern_type='glob', framerate=2).output(f'{filepath}/{filename}').run()

class go():
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

    def __init__(self, session_id, client, db, channel, message, primary, tertiary, mock):
        self.id = uuid.uuid4()
        self.session_id = session_id
        self.client = client
        self.db = db
        self.channel = channel
        self.message = message
        self.message_map = {self.message.id: self.message}
        self.primary = primary
        self.tertiary = tertiary
        self.mock = mock
        
        player_order = [self.primary, self.tertiary] if mock else random.sample([self.primary, self.tertiary],2)
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
        self.has_buttons = False
        self.winner = None

        self.initialize_board()
        self.row_selection = None
        self.col_selection = None
        self.last_state = None
        self.lock = False

        self.assets_directory = f'__botcache__/go/{self.session_id}/{self.id}'
        pathlib.Path(self.assets_directory).mkdir(parents=True, exist_ok=True)

    @property
    def other_player(self):
        return self.primary if self.current_player == self.tertiary else self.tertiary

    def initialize_board(self):
        self.board = [[tile(row=row, col=col) for col in range(self.BOARD_X)] for row in range(self.BOARD_Y)]

    async def initialize_sub_message(self, message):
        self.sub_message = message
        self.message_map[self.sub_message.id] = self.sub_message

    def is_completed(self):
        return True if self.winner else False

    async def play_move(self, payload):
        if payload.message_id == self.message.id:
            # make row selection
            self.row_selection = self.BUTTONS_ROW[payload.emoji.name]
            not self.mock and await self.message.remove_reaction(payload.emoji, payload.member)
        elif payload.message_id == self.sub_message.id:
            # make col selection
            self.col_selection = self.BUTTONS_COL[payload.emoji.name]
            not self.mock and await self.sub_message.remove_reaction(payload.emoji, payload.member)

        # only accept if player makes both a row and col selection
        if (self.row_selection and not self.col_selection) or (self.col_selection and not self.row_selection):
            await self.sub_message.edit(content=self.render_state('Make your placement:'))

        if self.row_selection is not None and self.col_selection is not None:
            self.lock = True
            is_valid_placement = False
            # attempt to place. we need this stone in board state in order to perform checks
            # temp_stone = copy.deepcopy(self.board[self.row_selection][self.col_selection])
            temp_stone = copy.copy(self.board[self.row_selection][self.col_selection])
            placement = stone(
                owner=self.current_player,
                state=self,
                row=self.row_selection,
                col=self.col_selection
            )
            captures = []
            try:
                # only accept moves that pass ruleset
                ruleset.validate_placement(self.board, self.current_player, self.row_selection, self.col_selection, self.last_state)
                self.board[self.row_selection][self.col_selection] = placement
                captures = ruleset.find_captures(
                    board=self.board,
                    owner=self.current_player,
                    root=placement
                )

                if not captures:
                    ruleset.validate_sacrifice(self.board, self.other_player, placement)
            except placementValidationError:
                # reset placement if not validated
                self.board[self.row_selection][self.col_selection] = temp_stone
                await self.sub_message.edit(content=self.render_selection('Invalid Placement:'))
            else:
                is_valid_placement = True
                ruleset.resolve_captures(
                    board=self.board,
                    captures=captures
                )
            finally:
                if is_valid_placement:
                    self.last_state = copy.deepcopy((self.current_player.id, self.row_selection, self.col_selection))
                self.row_selection = None
                self.col_selection = None
                if is_valid_placement:
                    self.current_player = self.primary if self.is_player_current(self.tertiary) else self.tertiary
                    await self.render_message()
            self.lock = False

    def get_board_tile(self, row, col):
        if row < 0 or row >= self.BOARD_Y or col < 0 or col >= self.BOARD_X:
            return wall(row, col)
        else:
            return self.board[row][col]

    async def render_message(self):
        not self.mock and await self.refresh_buttons()
        if not self.winner:
            header = f"It's your move, {self.current_player.display_name}."
        else:
            header = f"Congratulations, {self.winner.name}"
        container = discord.Embed(title=header, color=self.get_container_color())
        # container.add_field(name=self.render_state('Make your placement:'), value=self.render_board(), inline=True)
        container.set_image(url=self.render_board_image())
        await self.message.edit(content=f"{self.primary.mention} ⚔️ {self.tertiary.mention}", embed=container)
        await self.sub_message.edit(content=self.render_state('Make your placement:'))

    def is_player_current(self, player):
        return self.current_player == player

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

    def render_board(self):
        primary_tile, tertiary_tile = self.get_player_emojis()
        ret = "```\n"
        for yi, y in enumerate(self.board):
            ret += f"{yi + 1}"
            for t in y:
                if t and t.owner and t.owner.id is self.primary.id:
                    ret += u"\U000000A0"*2 + f"{primary_tile}"
                elif t and t.owner and t.owner.id is self.tertiary.id:
                    ret += u"\U000000A0"*2 + f"{tertiary_tile}"
                else:
                    ret += u"\U000000A0"*2 + f"{self.BLANK_TILE}"
            ret += "\n\n"
        if not self.winner:
            ret += u"\U000000A0"*3 + (u"\U000000A0"*2 + u"\U00002002" + u"\U00002009").join(string.ascii_uppercase[:self.BOARD_Y])
        else:
            ret += u"\U000000A0"*3 + (u"\U000000A0"*2 + u"\U00002002" + u"\U00002009").join(self.WINNER_BUTTONS.keys())
        ret += "\n```"
        return ret
    
    def render_board_image(self):
        step_count = 8
        height = 490
        width = 490
        goban = Image.new(mode='RGBA', size=(height, width), color=255)

        background = Image.open('games/assets/kaya.jpg', 'r')
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
        background = Image.open('games/assets/kaya.jpg', 'r')
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
        emoji = '%04x' % int(f'{ord(primary_tile):X}', 16)
        emoji_buff = BytesIO()
        cairosvg.svg2png(url=f'https://twemoji.maxcdn.com/v/13.0.1/svg/{emoji}.svg', write_to=emoji_buff, scale=1.5) #scale=1.75)
        primary_tile_img = Image.open(emoji_buff)

        emoji = '%04x' % int(f'{ord(tertiary_tile):X}', 16)
        emoji_buff = BytesIO()
        cairosvg.svg2png(url=f'https://twemoji.maxcdn.com/v/13.0.1/svg/{emoji}.svg', write_to=emoji_buff, scale=1.5) #scale=1.75)
        tertiary_tile_img = Image.open(emoji_buff)

        for yi, y in enumerate(self.board):
            for xi, t in enumerate(y):
                if t and t.owner and t.owner.id is self.primary.id:
                    tile = primary_tile_img
                    out.paste(
                        tile,
                        (int(1 + step_size*(yi+1) - tile.width/2),int(1 + step_size*(xi+1) - tile.height/2)),
                        tile.convert('RGBA')
                    )
                elif t and t.owner and t.owner.id is self.tertiary.id:
                    tile = tertiary_tile_img
                    out.paste(
                        tile,
                        (int(1 + step_size*(yi+1) - tile.width/2),int(1 + step_size*(xi+1) - tile.height/2)),
                        tile.convert('RGBA')
                    )

        out = out.convert('RGB')
        
        timestamp = datetime.datetime.now().isoformat()
        full_path = f'{self.assets_directory}/{timestamp}.jpg'
        out.save(full_path, quality=65)
        flush_s3_folder(self.assets_directory, 'phi.public')
        upload_file(full_path, 'phi.public')
        return f"https://s3-us-west-2.amazonaws.com/phi.public/{full_path}"

    async def on_complete(self):
        timestamp = datetime.datetime.now().isoformat()
        filename = f'{self.primary.id}-{self.tertiary.id}-{timestamp}.mp4'
        full_path = f"{self.assets_directory}/{filename}"
        make_game_video(self.assets_directory, filename)
        video = discord.File(full_path, filename=filename)
        await self.channel.send(f"{self.primary.mention} ⚔️ {self.tertiary.mention} match summary", file=video)

    def render_state(self, message):
        return f"\n{self.render_selection(message)}{self.render_last_selection()}"

    def render_selection(self, message):
        col = f"{self.row_selection + 1} " if self.row_selection is not None else " "
        row = f"{string.ascii_uppercase[self.col_selection]} " if self.col_selection is not None else " "
        return f"`{message} {col}{row}`\n"
    
    def render_last_selection(self):
        if self.last_state:
            col = f"{self.last_state[1] + 1} " if self.last_state[1] is not None else " "
            row = f"{string.ascii_uppercase[self.last_state[2]]} " if self.last_state[2] is not None else " "
            return f"`Your opponent chose: {col}{row}`"
        else:
            return " "

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

    async def simulate_move(self, row, col, member):
        await self.play_move(
            payload=FakePayload(
                message_id=self.message.id,
                member=member,
                emoji=FakePayload(
                    name=list(self.BUTTONS_ROW.keys())[row]
                )
            )
        )

        await asyncio.sleep(.5)

        await self.play_move(
            payload=FakePayload(
                message_id=self.sub_message.id,
                member=member,
                emoji=FakePayload(
                    name=list(self.BUTTONS_COL.keys())[col]
                )
            )
        )

        await asyncio.sleep(.5)

    async def simulate(self):
        # test capture
        # await self.simulate_move(0,3,self.primary)
        # await self.simulate_move(0,2,self.tertiary)
        # await self.simulate_move(1,3,self.primary)
        # await self.simulate_move(1,2,self.tertiary)
        # await self.simulate_move(2,4,self.primary)
        # await self.simulate_move(0,4,self.tertiary)
        # await self.simulate_move(4,3,self.primary)
        # await self.simulate_move(1,4,self.tertiary)
        # await self.simulate_move(2,2,self.primary)
        # await self.simulate_move(2,3,self.tertiary)

        # test sacrifice
        # await self.simulate_move(0,0,self.primary)
        # await self.simulate_move(0,3,self.tertiary)
        # await self.simulate_move(0,1,self.primary)
        # await self.simulate_move(1,2,self.tertiary)
        # await self.simulate_move(0,2,self.primary)
        # await self.simulate_move(1,4,self.tertiary)
        # await self.simulate_move(0,3,self.primary)
        # await self.simulate_move(2,3,self.tertiary)
        # await self.simulate_move(1,3,self.primary)

        # test occupied
        # await self.simulate_move(5,5,self.primary)
        # await self.simulate_move(5,5,self.tertiary)
        # await self.simulate_move(5,3,self.tertiary)
        # await self.simulate_move(3,3,self.primary)
        # await self.simulate_move(5,5,self.tertiary)

        # bug 1
        await self.simulate_move(5,3,self.primary)
        await self.simulate_move(6,3,self.tertiary)
        await self.simulate_move(6,4,self.primary)
        await self.simulate_move(7,4,self.tertiary)
        await self.simulate_move(6,6,self.primary)
        await self.simulate_move(6,5,self.tertiary)
        await self.simulate_move(5,6,self.primary)

        # nested capture
        # await self.simulate_move(2,4,self.primary)
        # await self.simulate_move(4,5,self.tertiary)
        # await self.simulate_move(6,4,self.primary)
        # await self.simulate_move(5,4,self.tertiary)
        # await self.simulate_move(4,2,self.primary)
        # await self.simulate_move(4,3,self.tertiary)
        # await self.simulate_move(4,6,self.primary)
        # await self.simulate_move(3,4,self.tertiary)
        # await self.simulate_move(3,3,self.primary)
        # await self.simulate_move(2,2,self.tertiary)
        # await self.simulate_move(3,5,self.primary)
        # await self.simulate_move(2,6,self.tertiary)
        # await self.simulate_move(5,5,self.primary)
        # await self.simulate_move(6,6,self.tertiary)
        # await self.simulate_move(5,3,self.primary)
        # await self.simulate_move(6,2,self.tertiary)
        # await self.simulate_move(4,4,self.primary)


class tile():
    def __init__(self, row, col, owner=None):
        self.owner = owner
        self.row = row
        self.col = col

    def __copy__(self):
        cls = self.__class__
        copy = cls.__new__(cls)
        copy.__dict__.update(self.__dict__)
        return copy

    def is_owned_by(self, check):
        return self.owner is not None and self.owner == check

    def is_not_owned_by(self, check):
        return self.owner is not None and self.owner != check

class stone(tile):
    def __init__(self, owner, state, row, col):
        self.state = state
        super().__init__(
            row=row,
            col=col,
            owner=owner
        )

    @property
    def top(self):
        return self.state.get_board_tile(self.row - 1, self.col)
    @property
    def top_right(self):
        return self.state.get_board_tile(self.row - 1, self.col + 1)
    @property
    def right(self):
        return self.state.get_board_tile(self.row, self.col + 1)
    @property
    def bottom_right(self):
        return self.state.get_board_tile(self.row + 1, self.col + 1)
    @property
    def bottom(self):
        return self.state.get_board_tile(self.row + 1, self.col)
    @property
    def bottom_left(self):
        return self.state.get_board_tile(self.row + 1, self.col - 1)
    @property
    def left(self):
        return self.state.get_board_tile(self.row, self.col - 1)
    @property
    def top_left(self):
        return self.state.get_board_tile(self.row - 1, self.col - 1)

    @property
    def liberties(self):
        return iter((
            self.top,
            self.right,
            self.bottom,
            self.left
        ))

    def __hash__(self):
        return generate_hash(self.row, self.col)

    def __eq__(self, other):
        return isinstance(other, stone) and \
            self.owner == other.owner and hash(self) == hash(other)


class wall(tile):
    def __init__(self, row, col):
        super().__init__(
            row=row,
            col=col,
            owner=None
        )


class ruleset():
    @staticmethod
    def resolve_captures(board, captures):
        for capture in captures:
            board[capture.row][capture.col] = tile(row=capture.row, col=capture.col)

    @staticmethod
    def find_captures(board, owner, root):
        capture_groups = []
        for dame in root.liberties:
            if isinstance(dame, stone) and dame.is_not_owned_by(owner):
                capture_groups.append(ruleset.find_group(board, owner, dame, {dame}))

        captures = []
        for capture_group in capture_groups:
            is_captured = True
            liberties = reduce(or_, [{c for c in capture.liberties} for capture in capture_group])
            for dame in liberties:
                # check if has eye
                if type(dame) is tile:
                    is_captured = False
                    break

            if is_captured:
                captures.extend(capture_group)
        return captures

    @staticmethod
    def sacrificed_stone(board, other, root):       
        capture_group = ruleset.find_group(board, other, root, {root})

        is_captured = True
        liberties = reduce(or_, [{dame for dame in capture.liberties} for capture in capture_group])
        for dame in liberties:
            if type(dame) is tile:
                is_captured = False
                break
        return is_captured

    @staticmethod
    def find_group(board, owner, leaf, captures):
        for dame in leaf.liberties:
            if isinstance(dame, stone) and dame.is_not_owned_by(owner) and dame not in captures:
                captures.add(dame)
                ruleset.find_group(board, owner, dame, captures)
        return captures

    @staticmethod
    def validate_placement(board, owner, row, col, last_state):
        if ruleset.placed_on_occupied_space(board, owner, row, col) or \
           ruleset.placed_on_previously_played_space(row, col, last_state):
           raise placementValidationError
    
    @staticmethod
    def validate_sacrifice(board, other, placement):
        ret = ruleset.sacrificed_stone(board, other, placement)
        # print(f"sacrificed_stone - {ret}")
        if ret:
            raise placementValidationError

    @staticmethod
    def placed_on_occupied_space(board, owner, row, col):
        ret = board[row][col] and type(board[row][col]) is stone
        # print(f"placed_on_occupied_space - {ret} {type(board[row][col])}")
        return ret

    @staticmethod
    def placed_on_previously_played_space(row, col, last_state):
        ret = (row, col) == (last_state[1], last_state[2]) if last_state else False
        # print(f"placed_on_previously_played_space - {ret}")
        return ret

    @staticmethod
    def end_game(current_pass, last_pass_state):
        return current_pass and last_pass_state


class placementValidationError(Exception):
    pass


def generate_hash(row, col):
    # https://stackoverflow.com/a/682481
    return ( row << 16 ) ^ col;


class FakePayload:
    def __init__(self, **kwds):
        self.__dict__.update(kwds)

if __name__ == '__main__':
    # print(to_code_point('\ud83c\udde8\ud83c\uddf3', '-'))

    step_count = 8
    height = 490
    width = 490
    goban = Image.new(mode='RGBA', size=(height, width), color=255)

    background = Image.open('games/assets/kaya.jpg', 'r')
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
    background = Image.open('games/assets/kaya.jpg', 'r')
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

    emoji = '%04x' % ord(chr(0x1f604))
    emoji_buff = BytesIO()
    cairosvg.svg2png(url=f'https://twemoji.maxcdn.com/v/13.0.1/svg/{emoji}.svg', write_to=emoji_buff, scale=1.5) #scale=1.75)
    tile = Image.open(emoji_buff)

    # col then row
    col = 2
    row = 3
    out.paste(tile, (int(1 + step_size*col - tile.width/2),int(1 + step_size*row - tile.height/2)), tile.convert('RGBA'))

    del draw

    out.show()
import asyncio
import discord
import random
import string
import copy
import uuid
from operator import or_
from functools import reduce

class go():
    id = uuid.uuid4()
    name = 'go'
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

    def __init__(self, client, db, channel, message, primary, tertiary, mock):
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
        self.lock = True
        if payload.message_id == self.message.id:
            # make row selection
            self.row_selection = self.BUTTONS_ROW[payload.emoji.name]
            not self.mock and await self.message.remove_reaction(payload.emoji, payload.member)
        elif payload.message_id == self.sub_message.id:
            # make col selection
            self.col_selection = self.BUTTONS_COL[payload.emoji.name]
            not self.mock and await self.sub_message.remove_reaction(payload.emoji, payload.member)

        # only accept if player makes both a row and col selection
        if self.row_selection is not None and self.col_selection is not None:
            # attempt to place. we need this stone in board state in order to perform checks
            # temp_stone = copy.deepcopy(self.board[self.row_selection][self.col_selection])
            temp_stone = copy.copy(self.board[self.row_selection][self.col_selection])
            placement = stone(
                owner=self.current_player,
                state=self,
                row=self.row_selection,
                col=self.col_selection
            )
            try:
                # only accept moves that pass ruleset
                ruleset.validate_placement(self.board, self.current_player, self.row_selection, self.col_selection, self.last_state)
                self.board[self.row_selection][self.col_selection] = placement
                ruleset.resolve_placement(self.board, self.other_player, placement)
            except placementValidationError:
                # reset placement if not validated
                self.board[self.row_selection][self.col_selection] = temp_stone
                await self.sub_message.edit(content=self.render_selection('Invalid Placement:'))
            else:
                await self.render_message()
                await self.sub_message.edit(content=self.SUB_MESSAGE)

                ruleset.resolve_captures(
                    board=self.board,
                    owner=self.current_player,
                    root=placement
                )
                self.last_state = copy.deepcopy((self.current_player.id, self.row_selection, self.col_selection))
                self.current_player = self.primary if self.is_player_current(self.tertiary) else self.tertiary
            finally:
                self.row_selection = None
                self.col_selection = None

        self.lock = False
        await self.render_message()

    def get_board_tile(self, row, col):
        if row < 0 or row >= self.BOARD_Y or col < 0 or col >= self.BOARD_X:
            return wall(row, col)
        else:
            return self.board[row][col]

    async def render_message(self):
        if not self.mock:
            await self.refresh_buttons()
        if not self.winner:
            header = f"It's your move, {self.current_player.name}."
        else:
            header = f"Congratulations, {self.winner.name}"
        container = discord.Embed(title=header, color=self.get_container_color())
        container.add_field(name=self.render_state('Make your placement:'), value=self.render_board(), inline=True)
        await self.message.edit(content=f"{self.primary.mention} ⚔️ {self.tertiary.mention}", embed=container)

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

    def render_state(self, message):
        return f"{self.render_last_selection()}{self.render_selection(message)}"

    def render_selection(self, message):
        row = list(self.BUTTONS_ROW.keys())[self.row_selection] if self.row_selection is not None else "\t\t"
        col = list(self.BUTTONS_COL.keys())[self.col_selection] if self.col_selection is not None else "\t\t"
        return f"`{message}`\t{row}\t{col}"
    
    def render_last_selection(self):
        if self.last_state:
            row = list(self.BUTTONS_ROW.keys())[self.last_state[1]] if self.last_state[1] is not None else "\t\t"
            col = list(self.BUTTONS_COL.keys())[self.last_state[2]] if self.last_state[2] is not None else "\t\t"
            return f"`Your opponent chose:`\t{row}\t{col}\n"
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

        await self.play_move(
            payload=FakePayload(
                message_id=self.sub_message.id,
                member=member,
                emoji=FakePayload(
                    name=list(self.BUTTONS_COL.keys())[col]
                )
            )
        )

        await asyncio.sleep(1)

    async def simulate(self):
        await self.simulate_move(5,3,self.primary)
        await self.simulate_move(6,3,self.tertiary)
        await self.simulate_move(6,4,self.primary)
        await self.simulate_move(7,4,self.tertiary)
        await self.simulate_move(6,6,self.primary)
        await self.simulate_move(6,5,self.tertiary)
        await self.simulate_move(5,6,self.primary)


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
            owner=go
        )


class ruleset():
    @staticmethod
    def resolve_captures(board, owner, root):
        capture_groups = []
        for dame in root.liberties:
            if isinstance(dame, stone) and dame.is_not_owned_by(owner):
                capture_groups.append(ruleset.find_group(board, owner, dame, {dame}))

        for capture_group in capture_groups:
            is_captured = True
            liberties = reduce(or_, [{c for c in capture.liberties} for capture in capture_group])
            for dame in liberties:
                if isinstance(dame, tile) and dame.owner is None:
                    is_captured = False
            if is_captured:
                for capture in capture_group:
                    board[capture.row][capture.col] = tile(row=capture.row, col=capture.col)

    @staticmethod
    def sacrificed_stone(board, other, root):       
        capture_group = ruleset.find_group(board, other, root, {root})

        is_captured = True
        liberties = reduce(or_, [{dame for dame in capture.liberties} for capture in capture_group])
        for dame in liberties:
            if isinstance(dame, tile):
                if dame.owner is None:
                    is_captured = False
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
    def resolve_placement(board, other, placement):
        ret = ruleset.sacrificed_stone(board, other, placement)
        print(f"sacrificed_stone - {ret}")
        if ret:
            raise placementValidationError

    @staticmethod
    def placed_on_occupied_space(board, owner, row, col):
        ret = board[col][row] and type(board[col][row].owner) is tile
        print(f"placed_on_occupied_space - {ret}")
        return ret

    @staticmethod
    def placed_on_previously_played_space(row, col, last_state):
        ret = (row, col) == (last_state[1], last_state[2]) if last_state else False
        print(f"placed_on_previously_played_space - {ret}")
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


# test capture
# self.board[0][3] = stone(
#     owner=self.tertiary,
#     state=self,
#     row=0,
#     col=3
# )
# self.board[1][3] = stone(
#     owner=self.tertiary,
#     state=self,
#     row=1,
#     col=3
# )

# self.board[0][2] = stone(
#     owner=self.primary,
#     state=self,
#     row=0,
#     col=3
# )
# self.board[1][2] = stone(
#     owner=self.primary,
#     state=self,
#     row=1,
#     col=3
# )
# self.board[0][4] = stone(
#     owner=self.primary,
#     state=self,
#     row=0,
#     col=3
# )
# self.board[1][4] = stone(
#     owner=self.primary,
#     state=self,
#     row=1,
#     col=3
# )

# test sacrifice
# self.board[0][3] = stone(
#     owner=self.tertiary,
#     state=self,
#     row=1,
#     col=3
# )
# self.board[1][2] = stone(
#     owner=self.tertiary,
#     state=self,
#     row=0,
#     col=3
# )
# self.board[1][4] = stone(
#     owner=self.tertiary,
#     state=self,
#     row=1,
#     col=3
# )
# self.board[2][3] = stone(
#     owner=self.tertiary,
#     state=self,
#     row=1,
#     col=3
# )

# test bug 1
# self.board[5][3] = stone(
#     owner=self.tertiary,
#     state=self,
#     row=1,
#     col=3
# )
# self.board[6][4] = stone(
#     owner=self.tertiary,
#     state=self,
#     row=0,
#     col=3
# )
# self.board[6][6] = stone(
#     owner=self.tertiary,
#     state=self,
#     row=1,
#     col=3
# )
# self.board[6][3] = stone(
#     owner=self.primary,
#     state=self,
#     row=1,
#     col=3
# )
# self.board[7][4] = stone(
#     owner=self.primary,
#     state=self,
#     row=0,
#     col=3
# )
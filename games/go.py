import discord
import random
import string
import copy

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
    SUB_MESSAGE = "▘"

    def __init__(self, client, db, channel, message, primary, tertiary):
        self.client = client
        self.db = db
        self.channel = channel
        self.message = message
        self.message_map = {self.message.id: self.message}
        self.primary = primary
        self.tertiary = tertiary
        self.board = [[None,None,None,None,None,None,None,None,None],
                      [None,None,None,None,None,None,None,None,None],
                      [None,None,None,None,None,None,None,None,None],
                      [None,None,None,None,None,None,None,None,None],
                      [None,None,None,None,None,None,None,None,None],
                      [None,None,None,None,None,None,None,None,None],
                      [None,None,None,None,None,None,None,None,None],
                      [None,None,None,None,None,None,None,None,None],
                      [None,None,None,None,None,None,None,None,None]]
        player_order = random.sample([self.primary, self.tertiary],2)
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

        self.row_selection = None
        self.col_selection = None
        self.last_state = None

    async def initialize_sub_message(self, message):
        self.sub_message = message
        self.message_map[self.sub_message.id] = self.sub_message

    def is_completed(self):
        return True if self.winner else False

    async def play_move(self, payload):
        if payload.message_id == self.message.id:
            # make row selection
            self.row_selection = self.BUTTONS_ROW[payload.emoji.name]
            await self.message.remove_reaction(payload.emoji, payload.member)
        elif payload.message_id == self.sub_message.id:
            # make col selection
            self.col_selection = self.BUTTONS_COL[payload.emoji.name]
            await self.sub_message.remove_reaction(payload.emoji, payload.member)
        
        ret_val = False
        # only accept if player makes both a row and col selection
        if self.row_selection is not None and self.col_selection is not None:
            await self.render_message()
            if not self.board[self.col_selection][self.row_selection]:
                self.board[self.col_selection][self.row_selection] = payload.member.id
                self.last_state = copy.deepcopy((self.current_player.name, self.row_selection, self.col_selection))
                self.current_player = self.primary if self.is_player_current(self.tertiary) else self.tertiary
                self.row_selection = None
                self.col_selection = None
                ret_val = True
        await self.render_message()

        return ret_val
    
    async def render_message(self):
        await self.refresh_buttons()
        if not self.winner:
            header = f"It's your move, {self.current_player.name}."
        else:
            header = f"Congratulations, {self.winner.name}"
        container = discord.Embed(title=header, color=self.get_container_color())
        container.add_field(name=self.render_selection(), value=self.render_board(), inline=True)
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
            for tile in y:
                if tile is self.primary.id:
                    ret += u"\U000000A0"*2 + f"{primary_tile}"
                elif tile is self.tertiary.id:
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

    def render_selection(self):
        row = list(self.BUTTONS_ROW.keys())[self.row_selection] if self.row_selection is not None else "\t\t"
        col = list(self.BUTTONS_COL.keys())[self.col_selection] if self.col_selection is not None else "\t\t"
        return f"{self.render_last_selection()}`Make your placement:`\t{row}\t{col}"
    
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
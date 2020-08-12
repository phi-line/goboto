import discord
import random

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

    def __init__(self, client, db, channel, message, primary, tertiary):
        self.client = client
        self.db = db
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
        self.current_player = random.choice([self.primary, self.tertiary]) if self.tertiary != self.client.user else self.primary
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
        if self.tertiary.id == self.client.user.id and self.is_player_current(self.tertiary):
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
        db_primary = self.db.get_player(self.primary.id)
        db_tertiary = self.db.get_player(self.tertiary.id)
        primary_color = db_primary[2] if db_primary[2] else self.PRIMARY_COLOR
        tertiary_color = db_tertiary[2] if db_tertiary[2] else self.TERTIARY_COLOR
        return discord.Color.from_rgb(*primary_color) if \
            self.current_player == self.primary \
            else discord.Color.from_rgb(*tertiary_color)

    def get_player_emojis(self):
        db_primary = self.db.get_player(self.primary.id)
        db_tertiary = self.db.get_player(self.tertiary.id)
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
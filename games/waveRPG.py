import discord

class waveRPG():
    BOARD_X = 4
    BOARD_Y = 7
    BUTTONS = {'1️⃣':0,'2️⃣':1,'3️⃣':2,'4️⃣':3}
    WINNER_BUTTONS = {'🎉':0,'🇺':1,'🎊':2,'🇼':3,'🇴':5,'🇳':6,'🍾':7}
    BLANK_TILE = "➕"
    PRIMARY_TILE = "🟠"
    LIFE_ICON = "❤️"
    PRIMARY_COLOR = (255,175,44)

    def __init__(self, client, db, channel, message, primary, tertiary):
        self.client = client
        self.db = db
        self.channel = channel
        self.message = message
        self.primary = primary
        self.tertiary = tertiary
        self.current_player = self.primary
        self.has_buttons = False
        self.winner = None
        self.lives = 3

        self.current_level = 0
        self.levels = {
            0: [bug(0,0)]
        }
        self.board = [[None,None,None,None],
                      [None,None,None,None],
                      [None,None,None,None],
                      [None,None,None,None],
                      [None,None,None,None],
                      [None,None,None,None],
                      [None,None,None,None]]
        self.init_board(self.levels[self.current_level])

    def is_completed(self):
        return True if self.winner else False

    def detect_current_player_win(self):
        return False

    def init_board(self, level):
        for tile in level:
            self.board[tile.x][tile.y] = tile

    async def play_move(self, payload):
        await self.message.remove_reaction(payload.emoji, payload.member)
        col = self.BUTTONS[payload.emoji.name]

        if not self.board[self.BOARD_Y - 1][col]:
            # move all active tiles
        
            self.board[self.BOARD_Y - 1][col] = pawn(x=col, y=self.BOARD_Y - 1, icon=self.get_player_emoji())

            return True
        else:
            return False
    
    async def render_message(self):
        if not self.winner:
            header = f"It's your move, {self.primary.name}\n{'  '.join([self.LIFE_ICON]*self.lives)}"
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
        primary_color = db_primary[2] if db_primary[2] else self.PRIMARY_COLOR
        return discord.Color.from_rgb(*primary_color)

    def get_player_emoji(self):
        db_primary = self.db.get_player(self.primary.id)
        primary_tile = db_primary[1] if db_primary[1] else self.PRIMARY_TILE
        return primary_tile

    def render_board(self):
        ret = ""
        for y in self.board:
            for tile in y:
                if tile:
                    ret += f"{tile.icon}\t\t"
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


class unit():
    def __init__(self, x, y, icon="🚫"):
        self.icon = icon
        self.x = x
        self.y = y
    
    def __next__(self):
        pass


class pawn(unit):
    def __init__(self, x, y, icon="🦠"):
        super().__init__(x, y, icon)

    def __next__(self):
        self.y -= 1


class bug(unit):
    def __init__(self, x, y, icon="🐛"):
        super().__init__(x, y, icon)

    def __next__(self):
        self.y += 1
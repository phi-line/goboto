import copy
import time
from operator import attrgetter

import discord

class waveRPG():
    BOARD_X = 4
    BOARD_Y = 7
    BUTTONS = {'1️⃣':0,'2️⃣':1,'3️⃣':2,'4️⃣':3,'⌛':4}
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
            0: {(0,0):bug(0,0)}
        }
        self.board = [[None,None,None,None],
                      [None,None,None,None],
                      [None,None,None,None],
                      [None,None,None,None],
                      [None,None,None,None],
                      [None,None,None,None],
                      [None,None,None,None]]
        self.tile_state = self.init_board()

    def is_completed(self):
        return True if self.winner else False

    def detect_current_player_win(self):
        return False

    def init_board(self):
        return copy.deepcopy(self.levels[self.current_level])

    async def play_move(self, payload):
        await self.message.remove_reaction(payload.emoji, payload.member)
        input_x = self.BUTTONS[payload.emoji.name]

        # sort by speed
        priority = list(self.tile_state.values())
        priority = sorted(priority, key=attrgetter('speed', 'y'), reverse=True)
        current_coordinates = [(x.x, x.y) for x in priority]

        print(priority)
        print([attrgetter('speed', 'y')(x) for x in priority])

        for x,y in current_coordinates:
            copy.deepcopy(self.tile_state[(x, y)]).advance(self.tile_state)
    
        if input_x != 4: # wait command
            self.tile_state[(input_x, self.BOARD_Y - 1)] = pawn(
                x=input_x,
                y=self.BOARD_Y - 1,
                icon=self.get_player_emoji()
            )
        await self.render_message()

        return True
    
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
        for y, row in enumerate(self.board):
            for x, tile in enumerate(row):
                if (x,y) in self.tile_state:
                    ret += f"{self.tile_state[(x,y)].icon}\t\t"
                else:
                    ret += f"{self.BLANK_TILE}\t\t"
            ret += "\n\n\n"
        if not self.winner:
            ret += '\t\t'.join(list(self.BUTTONS.keys())[:-1])
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
    def __init__(self, x, y, speed, icon):
        self.x = x
        self.y = y
        self.speed = speed
        self.icon = icon
    
    def advance(self, tile_state):
        tile_state[(self.x,self.y)] = self


class monster(unit):
    def __init__(self, x, y, speed, icon="🃏"):
        super().__init__(x=x, y=y, speed=speed, icon=icon)


class player(unit):
    def __init__(self, x, y, speed, icon="🀄"):
        super().__init__(x=x, y=y, speed=speed, icon=icon)


class pawn(player):
    def __init__(self, x, y, speed=1, icon="🐦"):
        super().__init__(x=x, y=y, speed=speed, icon=icon)

    def advance(self, tile_state):
        if (self.x,self.y) in tile_state:
            del tile_state[(self.x,self.y)]
            if (self.x - 1,self.y - 1) in tile_state and is_monster(self.x - 1, self.y - 1, tile_state):
                del tile_state[(self.x - 1,self.y - 1)]
                self.x -= 1
                self.y -= 1
            elif (self.x + 1,self.y - 1) in tile_state and is_monster(self.x + 1, self.y - 1, tile_state):
                del tile_state[(self.x + 1,self.y - 1)]
                self.x += 1
                self.y -= 1
            elif (self.x,self.y-1) not in tile_state:
                self.y -= 1
            tile_state[(self.x,self.y)] = self


class bug(monster):
    def __init__(self, x, y, speed=-1, icon="🐛"):
        super().__init__(x=x, y=y, speed=speed, icon=icon)

    def advance(self, tile_state):
        if (self.x,self.y) in tile_state:
            del tile_state[(self.x,self.y)]
            self.y += 1
            tile_state[(self.x,self.y)] = self


def is_monster(x, y, tile_state):
    return (x, y) in tile_state and isinstance(tile_state[(x, y)], monster)


def is_player(x, y, tile_state):
    return (x, y) in tile_state and isinstance(tile_state[(x, y)], player)
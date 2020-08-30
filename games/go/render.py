import string
import datetime

import s3
from utils.image import get_emoji_svg

from PIL import Image, ImageDraw, ImageFont, ImageFilter

BACKGROUND_PATH = "games/go/assets/kaya.jpg"

class GobanRenderer():
    def __init__(self, state, config={}):
        self.state = state
        self.config = config
        
    def save(self):
        with GameStateRenderer(state=self.state, *self.config) as frame:
            timestamp = datetime.datetime.now().isoformat()
            full_path = f'{self.state.assets_directory}/{timestamp}.jpg'
            frame.save(full_path, quality=80)

        s3.flush_directory(self.state.assets_directory)
        return s3.upload_file(full_path)

class GameStateRenderer():
    def __init__(self, state, x_grid=9, y_grid=9, width=490, height=490, line_width=2,
        legend_margin_x=.92, legend_margin_y=.92, legend_padding={'top': 0,'bottom': 2/3,'left': 1/6,'right': 1/2},
        font_size=28, typeface="SourceCodePro-Medium.ttf",
        tile_scale=1.5):

        self.state = state

        # grid
        self.x_grid = x_grid
        self.y_grid = y_grid
        self.width = width
        self.height = height
        self.line_width = line_width

        # legend
        self.legend_margin_x = legend_margin_x
        self.legend_margin_y = legend_margin_y
        self.legend_padding = legend_padding
        self.font_size = font_size
        self.typeface = typeface

        # emojis
        self.tile_scale = tile_scale

    def __enter__(self):
        with GridRenderer(
            x_grid=self.x_grid,
            y_grid=self.y_grid,
            width=self.width,
            height=self.height,
            line_width=self.line_width) as grid:
            # padding
            out_height = self.height + grid.step_size_y * 2
            out_width = self.width + grid.step_size_x * 2

            buffer = Image.new(mode='RGBA', size=(out_height, out_width), color=255)

            BackgroundRenderer(
                buffer=buffer,
                width=out_width,
                height=out_height)
            
            buffer.paste(grid.buffer, (int((out_width - self.width)/2), int((out_height - self.height)/2)), grid.buffer.convert('RGBA'))
    
            LegendRenderer(
                grid=grid,
                buffer=buffer,
                legend_margin_x=self.legend_margin_x,
                legend_margin_y=self.legend_margin_y,
                legend_padding=self.legend_padding,
                font_size=self.font_size,
                typeface=self.typeface)

            with EmojiTileRenderer(
                state=self.state,
                tile_scale=self.tile_scale) as (primary_emoji, secondary_emoji):

                for yi, y in enumerate(self.state.board):
                    for xi, t in enumerate(y):
                        if t and t.owner and t.owner.id is self.state.primary.id:
                            tile = primary_emoji
                            buffer.paste(
                                tile,
                                (int(1 + grid.step_size_y*(yi+1) - tile.width/2), int(1 + grid.step_size_x*(xi+1) - tile.height/2)),
                                tile.convert('RGBA')
                            )
                        elif t and t.owner and t.owner.id is self.state.tertiary.id:
                            tile = secondary_emoji
                            buffer.paste(
                                tile,
                                (int(1 + grid.step_size_y*(yi+1) - tile.width/2),int(1 + grid.step_size_x*(xi+1) - tile.height/2)),
                                tile.convert('RGBA')
                            )

            buffer = buffer.convert('RGB')
            self.buffer = buffer
        return self.buffer

    def __exit__(self, type, value, tb):
        self.buffer.close()

class EmojiTileRenderer():
    def __init__(self, state, tile_scale):
        self.state = state
        self.tile_scale = tile_scale

    def __enter__(self):
        primary_tile, tertiary_tile = self.state.get_player_emojis()
        primary_emoji_buffer = get_emoji_svg(primary_tile, scale=self.tile_scale)
        tertiary_emoji_buffer = get_emoji_svg(tertiary_tile, scale=self.tile_scale)
        self.primary_emoji = Image.open(primary_emoji_buffer)
        self.tertiary_emoji = Image.open(tertiary_emoji_buffer)
        return self.primary_emoji, self.tertiary_emoji
    
    def __exit__(self, type, value, tb):
        self.primary_emoji.close()
        self.tertiary_emoji.close()

class BackgroundRenderer():
    def __init__(self, buffer, width, height):
        background = Image.open(BACKGROUND_PATH, 'r')
        background = background.resize((width, height), Image.ANTIALIAS)
        buffer.paste(background, (0,0))
        background.close()

class GridRenderer():
    def __init__(self, x_grid, y_grid, width, height, line_width):
        self.x_grid = x_grid
        self.y_grid = y_grid
        self.width = width
        self.height = height
        self.line_width = line_width
    
    @property
    def step_size_x(self):
        return int(self.width / (self.x_grid - 1))

    @property
    def step_size_y(self):
        return int(self.height / (self.y_grid - 1))

    def __enter__(self):
        buffer = Image.new(mode='RGBA', size=(self.height, self.width), color=255)

        BackgroundRenderer(buffer, self.width, self.height)

        # https://randomgeekery.org/post/2017/11/drawing-grids-with-python-and-pillow/
        draw = ImageDraw.Draw(buffer)
        self.draw = draw

        y_start = 0
        y_end = self.height
        step_size_y = int(self.width / (self.y_grid - 1))

        for x in range(0, self.width, step_size_y):
            line = ((x, y_start), (x, y_end))
            draw.line(line, fill=0, width=self.line_width)

        x_start = 0
        x_end = self.width
        step_size_x = int(self.width / (self.x_grid - 1))

        for y in range(0, self.height, step_size_x):
            line = ((x_start, y), (x_end, y))
            draw.line(line, fill=0, width=self.line_width)

        buffer = buffer.convert('RGB')
        self.buffer = buffer
        return self

    def __exit__(self, type, value, tb):
        del self.draw
        self.buffer.close()


class LegendRenderer():
    def __init__(self, grid, buffer, legend_margin_x, legend_margin_y, legend_padding, font_size, typeface):
        width = grid.width + grid.step_size_x
        height = grid.height + grid.step_size_y
        margin_x = int(grid.step_size_x * legend_margin_x)
        margin_y = int(grid.step_size_y * legend_margin_y)
        position = Position(buffer, grid.step_size_x, grid.step_size_y, legend_padding)

        draw = ImageDraw.Draw(buffer)
        fnt = ImageFont.truetype(typeface, font_size)

        # top
        for xi, x in enumerate(range(margin_x, width, grid.step_size_x)):
            draw.text((x, position.top), f"{xi + 1}", font=fnt, fill=(0, 0, 0), align="center")

        # bottom
        for xi, x in enumerate(range(margin_x, width, grid.step_size_x)):
            draw.text((x, position.bottom), f"{xi + 1}", font=fnt, fill=(0, 0, 0), align="center")

        # left 
        for yi, y in enumerate(range(margin_y, height, grid.step_size_y)):
            draw.text((position.left, y), string.ascii_uppercase[yi], font=fnt, fill=(0, 0, 0), align="center")

        # right
        for yi, y in enumerate(range(margin_y, height, grid.step_size_y)):
            draw.text((position.right, y), string.ascii_uppercase[yi], font=fnt, fill=(0, 0, 0), align="center")
        del draw

class Position():
    def __init__(self, canvas, step_size_x, step_size_y, step_ratio):
        self.top = int(step_size_y * step_ratio['top'])
        self.bottom = canvas.height -  int(step_size_y * step_ratio['bottom'])
        self.left =int(step_size_y * step_ratio['left'])
        self.right = canvas.width - int(step_size_x * step_ratio['right'])
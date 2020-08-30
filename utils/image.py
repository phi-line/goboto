import pathlib
from io import BytesIO

import ffmpeg
import requests
import cairosvg

from PIL import Image

def export_replay(filepath, filename, hold_seconds=1):
    ffmpeg.input(
        f'{filepath}/*.jpg',
        pattern_type='glob',
        framerate=1,
    ).output(f'{filepath}/temp_{filename}').run()
    ffmpeg.input(
        f'{filepath}/temp_{filename}',
        # https://stackoverflow.com/a/24111474
        # https://stackoverflow.com/a/43417253
        filter_complex=f"[0]trim=0:{hold_seconds}[hold];[0][hold]concat[extended];[extended][0]overlay",
    ).output(f'{filepath}/{filename}').run()
    pathlib.Path(f'{filepath}/temp_{filename}').unlink()
    return f'{filepath}/{filename}.mp4'

def get_emoji_svg(emoji, scale):
    emoji = '%04x' % int(f'{ord(emoji):X}', 16)
    emoji_buff = BytesIO()
    cairosvg.svg2png(url=f'https://twemoji.maxcdn.com/v/13.0.1/svg/{emoji}.svg', write_to=emoji_buff, scale=scale)
    return emoji_buff

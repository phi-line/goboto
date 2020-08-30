from .connect4 import Connect4
from .go import Go, MockGo

GAMES = {
    'connect4': Connect4,
    'go': Go
}

MOCK = {
    'go': MockGo
}
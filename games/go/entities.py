from utils.hash import z_order_hash

class tile():
    def __init__(self, row, col, state=None, owner=None):
        self.row = row
        self.col = col
        self.state = state
        self.owner = owner

    def __copy__(self):
        cls = self.__class__
        copy = cls.__new__(cls)
        copy.__dict__.update(self.__dict__)
        return copy

    def is_owned_by(self, check):
        return self.owner is not None and self.owner == check

    def is_not_owned_by(self, check):
        return self.owner is not None and self.owner != check

    def get_board_tile(self, row, col):
        if row < 0 or row >= self.state.BOARD_Y or col < 0 or col >= self.state.BOARD_X:
            return wall(row, col)
        else:
            return self.state.board[row][col]

class stone(tile):
    def __init__(self, row, col, owner, state):
        super().__init__(
            row=row,
            col=col,
            state=state,
            owner=owner
        )

    @property
    def top(self):
        return self.get_board_tile(self.row - 1, self.col)
    @property
    def top_right(self):
        return self.get_board_tile(self.row - 1, self.col + 1)
    @property
    def right(self):
        return self.get_board_tile(self.row, self.col + 1)
    @property
    def bottom_right(self):
        return self.get_board_tile(self.row + 1, self.col + 1)
    @property
    def bottom(self):
        return self.get_board_tile(self.row + 1, self.col)
    @property
    def bottom_left(self):
        return self.get_board_tile(self.row + 1, self.col - 1)
    @property
    def left(self):
        return self.get_board_tile(self.row, self.col - 1)
    @property
    def top_left(self):
        return self.get_board_tile(self.row - 1, self.col - 1)

    @property
    def liberties(self):
        return iter((
            self.top,
            self.right,
            self.bottom,
            self.left
        ))

    def __hash__(self):
        return z_order_hash(self.row, self.col)

    def __eq__(self, other):
        return isinstance(other, stone) and \
            self.owner == other.owner and hash(self) == hash(other)


class wall(tile):
    def __init__(self, row, col):
        super().__init__(
            row=row,
            col=col,
            state=None,
            owner=None
        )
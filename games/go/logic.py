import copy
from operator import or_
from functools import reduce

from .entities import tile, stone

class ruleset():
    @staticmethod
    def initialize_board(state):
        return [[tile(row=row, col=col) for col in range(state.BOARD_X)] for row in range(state.BOARD_Y)]

    @staticmethod
    def attempt_placement(state):
        is_valid_placement = False
        
        # attempt to place. we need this stone in board state in order to perform checks
        temp_stone = copy.copy(state.board[state.row_selection][state.col_selection])
        placement = stone(
            row=state.row_selection,
            col=state.col_selection,
            state=state,
            owner=state.current_player
        )
        captures = []
        try:
            # only accept moves that pass ruleset
            ruleset.validate_placement(
                board=state.board,
                owner=state.current_player,
                row=state.row_selection,
                col=state.col_selection,
                last_state=state.last_state)

            state.board[state.row_selection][state.col_selection] = placement

            captures = ruleset.find_captures(
                board=state.board,
                owner=state.current_player,
                root=placement
            )

            if not captures:
                ruleset.validate_sacrifice(
                    board=state.board,
                    other=state.other_player,
                    placement=placement
                )
        except placementValidationError:
            # reset placement if not validated
            state.board[state.row_selection][state.col_selection] = temp_stone
        else:
            is_valid_placement = True
            ruleset.resolve_captures(
                board=state.board,
                captures=captures
            )
        return is_valid_placement

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
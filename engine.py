from board import Move, WP, BP, WR, WN, WB, WK, EMPTY, Color, WHITE_SET, BLACK_SET
from game import Board
import random

def make(board: Board, move: Move, in_analysis: bool = False):
    sr, sc = move.src
    dr, dc = move.dst
    piece = board.piece_at(sr, sc)
    captured = board.piece_at(dr, dc)

    # en passant
    if move.is_en_passant:
        if piece == WP:
            captured = BP
            board.set_piece(sr, dc, EMPTY)
        elif piece == BP:
            captured = WP
            board.set_piece(sr, dc, EMPTY)

    # move piece
    board.set_piece(sr, sc, EMPTY)
    board.set_piece(dr, dc, piece)

    # promotion
    if move.promotion:
        if piece == WP:
            if in_analysis:
                promo = WK  
            else:
                promo = random.choice([WR, WN, WB, WK])
            board.set_piece(dr, dc, promo)
        else:
            board.set_piece(dr, dc, move.promotion)

    state = {
        "move": move,
        "piece": piece,
        "captured": captured,
        "to_move": board.to_move,
        "ep_square": board.ep_square,
    }
    if not hasattr(board, "undo_stack"):
        board.undo_stack = []
    board.undo_stack.append(state)

    # update en passant
    board.ep_square = None
    if piece == WP and sr == 6 and dr == 4:
        board.ep_square = (5, sc)
    if piece == BP and sr == 1 and dr == 3:
        board.ep_square = (2, sc)

    # flip turn
    board.to_move = Color.BLACK if board.to_move == Color.WHITE else Color.WHITE
    return True


def undo(board: Board):
    if not hasattr(board, "undo_stack") or not board.undo_stack:
        return False
    state = board.undo_stack.pop()
    move, piece, captured = state["move"], state["piece"], state["captured"]
    sr, sc = move.src
    dr, dc = move.dst

    # undo move
    board.set_piece(sr, sc, piece)
    board.set_piece(dr, dc, captured)

    # en passant
    if move.is_en_passant:
        if piece == WP:
            board.set_piece(dr, dc, EMPTY)
            board.set_piece(sr, dc, BP)
        elif piece == BP:
            board.set_piece(dr, dc, EMPTY)
            board.set_piece(sr, dc, WP)

    board.to_move = state["to_move"]
    board.ep_square = state["ep_square"]
    return True

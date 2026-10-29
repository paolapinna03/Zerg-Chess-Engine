from __future__ import annotations
from typing import Optional, Tuple, List, Dict
import random
import time

from board import EMPTY, WP, WN, WB, WR, WK, BP, Color, color_of
from game import Board
from movegen import generate_legal_moves
from engine import make, undo


PIECE_VALUE = {
    WP: 100,
    WN: 300,
    WB: 300,
    WR: 500,
    WK: 400,
    BP: 120,
}

INF = 10000

# --- utilities -----------------------------------------------------------

FILES = 5
RANKS = 8

def _iter_squares():
    for r in range(RANKS):
        for c in range(FILES):
            yield r, c

def _count(board: "Board", predicate) -> int:
    return sum(1 for r, c in _iter_squares() if predicate(board.grid[r][c], r, c))

# --- victory conditions ------------------------------------------------

def _eval_terminal(board: "Board") -> Optional[int]:
    winner = board.check_winner()
    if winner == Color.WHITE:
        return INF - 1
    if winner == Color.BLACK:
        return -INF + 1
    return None

# --- material + white activity + pawn counts -------------------------
def _is_passed_white(board, r, c):
    for rr in range(0, r):
        if board.grid[rr][c] == BP:
            return False
    return True

def _is_blocking_bp(board, r, c):
    rr = r - 1
    return 0 <= rr < 8 and board.grid[rr][c] == BP

def _can_capture_bp_next(board, r, c):
    for dc in (-1, 1):
        rr = r - 1
        cc = c + dc
        if 0 <= rr < 8 and 0 <= cc < 5 and board.grid[rr][cc] == BP:
            return True
    return False

def _eval_material_and_activity(board: "Board") -> Tuple[int, int, int]:
    score = 0
    black_pawns = 0
    white_pawns = 0

    for r, c in _iter_squares():
        piece = board.grid[r][c]
        if piece == EMPTY:
            continue

        if color_of(piece) == Color.WHITE:
            score += PIECE_VALUE[piece]

            if piece == WP:
                white_pawns += 1

                if _is_blocking_bp(board, r, c):
                    score += 20

                if _can_capture_bp_next(board, r, c):
                    score += 30

                if _is_passed_white(board, r, c):
                    score += 40

                if r == 0:
                    score += 500

        else:
            score -= PIECE_VALUE[piece]
            if piece == BP:
                black_pawns += 1
                if r == 4:
                    score -= 20
                elif r == 5:
                    score -= 50
                elif r == 6:
                    score -= 80
                elif r == 7:
                    score -= 100


    return score, black_pawns, white_pawns

def _eval_black_leader(board: "Board") -> int:
    max_r = -1
    for r in range(8):
        for c in range(5):
            if board.grid[r][c] == BP:
                if r > max_r:
                    max_r = r

    if max_r == -1:
        return 0
    if max_r <= 2:
        return 0
    elif max_r == 3:
        return -10
    elif max_r == 4:
        return -40
    elif max_r == 5:
        return -80
    elif max_r == 6:
        return -180
    else:  # max_r == 7
        return -300

# --- coordination BP (safe advance in group) ---------------------
def _eval_black_pawn_coordination(board: "Board") -> int:
    score = 0
    for r in range(RANKS):
        for c in range(FILES):
            if board.grid[r][c] == BP:
                neighbors = 0
                for dr in [-1, 0, 1]:
                    for dc in [-1, 0, 1]:
                        if dr == 0 and dc == 0:
                            continue
                        rr, cc = r + dr, c + dc
                        if 0 <= rr < RANKS and 0 <= cc < FILES:
                            if board.grid[rr][cc] == BP:
                                neighbors += 1

                if neighbors > 0:
                    score -= min(neighbors, 2) * 15  
    
    return score


# --- bonus for captured black pawns -----------------------------------------------
def _eval_captured_black_pawns(black_pawns_now: int, initial_black_pawns: int = 15) -> int:
    pawns_captured = initial_black_pawns - black_pawns_now
    base = pawns_captured * 80  
    if pawns_captured >= 10:
        base += 300  
    return base

# --- bonus for black captures  -----------------------------------------------
def _eval_captured_white_pieces(board: "Board") -> int:
    score = 0
    for r in range(RANKS):
        for c in range(FILES):
            piece = board.grid[r][c]
            if piece == BP:
                white_pieces_in_column = 0
                for rr in range(r + 1, RANKS):
                    if board.grid[rr][c] in (WP, WN, WB, WR, WK):
                        white_pieces_in_column += 1
                
                if r >= 4: 
                    score -= white_pieces_in_column * 20  
    return score


# --- compactness -------------------------------------------------
def _eval_compactness(board: "Board") -> int:
    defensive_clusters = 0
    for r in range(RANKS):
        row_pieces = sum(1 for c in range(FILES) if board.grid[r][c] in (WP, WN, WR, WK))
        if row_pieces >= 2:
            defensive_clusters += 1
    return defensive_clusters * 20


# --- mobility --------------------------------------------------------------
def _eval_mobility(board: "Board") -> int:
    side = board.to_move

    board.to_move = Color.WHITE
    w_moves = len(generate_legal_moves(board))

    board.to_move = Color.BLACK
    b_moves = len(generate_legal_moves(board))
  
    board.to_move = side

    mobility = (w_moves - b_moves) * 2  

    lm = w_moves if side == Color.WHITE else b_moves
    if lm <= 2:
        mobility -= 120
    elif lm <= 5:
        mobility -= 40
    elif lm <= 8:
        mobility -= 15

    return mobility


def _eval_anti_stalemate(board: "Board") -> int:
    
    original_side = board.to_move
    board.to_move = Color.BLACK
    black_moves = len(generate_legal_moves(board))
    board.to_move = original_side

    if black_moves <= 1:
        return -300   
    elif black_moves <= 3:
        return -100   

    return 0


# --- main API -----------------------------------------------------------

def evaluate(board: "Board") -> int:
    
    term = _eval_terminal(board)
    if term is not None:
        return term

    score = 0

    mat_act_score, black_pawns, _white_pawns = _eval_material_and_activity(board)
    score += mat_act_score

    score += _eval_captured_black_pawns(black_pawns)

    score += _eval_captured_white_pieces(board)

    score += _eval_black_leader(board)
    
    score += _eval_black_pawn_coordination(board)

    score += _eval_compactness(board)

    score += _eval_mobility(board)

    score += _eval_anti_stalemate(board)

    return score

# --- debug  ------------------------
def evaluate_breakdown(board: "Board") -> Dict[str, int]:
    term = _eval_terminal(board)
    if term is not None:
        return {"terminal": term}

    breakdown: Dict[str, int] = {}

    mat_act_score, black_pawns, _white_pawns = _eval_material_and_activity(board)
    breakdown["material+activity"] = mat_act_score
    breakdown["bp_leader"] = _eval_black_leader(board)
    breakdown["bp_coordination"] = _eval_black_pawn_coordination(board)
    breakdown["captured_black_pawns"] = _eval_captured_black_pawns(black_pawns)
    breakdown["captured_white_pieces"] = _eval_captured_white_pieces(board)
    breakdown["compactness"] = _eval_compactness(board)
    breakdown["mobility"] = _eval_mobility(board)
    breakdown["anti_stalemate"] = _eval_anti_stalemate(board)

    breakdown["total"] = sum(breakdown.values())
    return breakdown

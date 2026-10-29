from __future__ import annotations
from dataclasses import dataclass
from enum import IntEnum
from typing import List, Optional, Tuple


# === Piece encoding ==========================================================
EMPTY = 0
# White
WP, WN, WB, WR, WK = 1, 2, 3, 4, 5
# Black 
BP = 9

PIECE_TO_GLYPH = {
    EMPTY: " ",
    WP: "♙", WN: "♘", WB: "♗", WR: "♖", WK: "♛",
    BP: "♟",
}

class Color(IntEnum):
    WHITE = 0
    BLACK = 1

PIECE_TO_TYPE = {
    WP: "P", WN: "N", WB: "B", WR: "R", WK: "K",
    BP: "P",
}

PIECE_TO_COLOR = {
    WP: Color.WHITE, WN: Color.WHITE, WB: Color.WHITE, WR: Color.WHITE, WK: Color.WHITE,
    BP: Color.BLACK,
}

WHITE_SET = {WP, WN, WB, WR, WK}
BLACK_SET = {BP}

def color_of(piece: int) -> Optional[Color]:
    if piece == EMPTY:
        return None
    return PIECE_TO_COLOR[piece]


def type_of(piece: int) -> Optional[str]:
    if piece == EMPTY:
        return None
    return PIECE_TO_TYPE[piece]


# === Coordinates =============================================================
FILES = "ABCDE"  # c=0..4
RANKS = "87654321"  # r=0..7


def in_bounds(r: int, c: int) -> bool:
    return 0 <= r < 8 and 0 <= c < 5


def rc_to_coord(r: int, c: int) -> str:
    assert in_bounds(r, c)
    return f"{FILES[c]}{RANKS[r]}"


def coord_to_rc(coord: str) -> Tuple[int, int]:
    coord = coord.strip().upper()
    if len(coord) != 2:
        raise ValueError(f"Invalid coord: {coord!r}")
    file_char, rank_char = coord[0], coord[1]
    if file_char not in FILES or rank_char not in RANKS:
        raise ValueError(f"Invalid coord: {coord!r}")
    c = FILES.index(file_char)
    r = RANKS.index(rank_char)
    return (r, c)


# === Move =============================================================
@dataclass(frozen=True)
class Move:
    src: Tuple[int, int]
    dst: Tuple[int, int]
    promotion: Optional[int] = None 
    is_en_passant: bool = False      


from typing import Optional, List, Tuple
from board import EMPTY, BP, WP, WK, WR, WB, WN, Color, color_of, type_of, rc_to_coord, FILES, RANKS, in_bounds, WHITE_SET, BLACK_SET, PIECE_TO_GLYPH
import random


# === Board ==================================================================
class Board:
    __slots__ = ("grid", "to_move", "ep_square", "undo_stack")

    def __init__(self) -> None:
        self.grid: List[List[int]] = [[EMPTY for _ in range(5)] for _ in range(8)]
        self.to_move: Color = Color.WHITE
        self.ep_square: Optional[Tuple[int, int]] = None 
        self.undo_stack: list = []


    # -- basic access ---------------------------------------------------------
    def piece_at(self, r: int, c: int) -> int:
        if not in_bounds(r, c):
            return EMPTY  
        return self.grid[r][c]

    def set_piece(self, r: int, c: int, p: int) -> None:
        assert in_bounds(r, c)
        self.grid[r][c] = p

    def clear(self) -> None:
        for r in range(8):
            for c in range(5):
                self.grid[r][c] = EMPTY
        self.to_move = Color.WHITE
        self.ep_square = None

    def check_winner(self) -> Optional[Color]:
        counts = self.count_pieces()

        if counts.get(BP, 0) == 0:
            return Color.WHITE

        for c in range(5):
            if self.grid[7][c] == BP:
                return Color.BLACK

        white_total = sum(counts.get(p, 0) for p in WHITE_SET)
        if white_total == 0:
            return Color.BLACK

        return None

    # -- setup ----------------------------------------------------------------
    def setup_random(self, seed: Optional[int] = None) -> None:
        self.clear()
        if seed is not None:
            random.seed(seed)

        for r in (0, 1, 2):
            for c in range(5):
                self.set_piece(r, c, BP)

        for c in range(5):
            self.set_piece(6, c, WP)

        back_pieces = [WK, WR, WB, WN]
        files = list(range(5))
        random.shuffle(files)
        for p, c in zip(back_pieces, files[:4]):
            self.set_piece(7, c, p)

        self.to_move = Color.WHITE
        self.ep_square = None

    def setup_manual(self, backrank: str) -> None:
        backrank = backrank.strip().upper()
        if len(backrank) != 5:
            raise ValueError("backrank must be 5 characters long, e.g. 'KRBN.'")
        required = set("KRBN.")
        if not set(backrank).issubset(required):
            raise ValueError("backrank may only contain K,R,B,N,.")
        for ch, need in [("K", 1), ("R", 1), ("B", 1), ("N", 1), (".", 1)]:
            if backrank.count(ch) != need:
                raise ValueError("backrank must contain exactly one K, R, B, N and one '.'")

        self.clear()
        for r in (0, 1, 2):
            for c in range(5):
                self.set_piece(r, c, BP)
        for c in range(5):
            self.set_piece(6, c, WP)
        char_to_piece = {"K": WK, "R": WR, "B": WB, "N": WN, ".": EMPTY}
        for c, ch in enumerate(backrank):
            self.set_piece(7, c, char_to_piece[ch])

        self.to_move = Color.WHITE
        self.ep_square = None

    # -- utilities ------------------------------------------------------------
    def count_pieces(self) -> dict:
        counts = {}
        for r in range(8):
            for c in range(5):
                p = self.grid[r][c]
                if p != EMPTY:
                    counts[p] = counts.get(p, 0) + 1
        return counts

    def validate_position(self) -> None:
        for r in range(8):
            for c in range(5):
                p = self.grid[r][c]
                if p == EMPTY:
                    continue
                col = color_of(p)
                if col == Color.BLACK and p != BP:
                    raise ValueError(f"Invalid Black piece at {rc_to_coord(r,c)}: only pawns allowed in this variant")
    
    

    def __str__(self) -> str:
        lines = []
        for r in range(8):
            row = []
            for c in range(5):
                piece = self.grid[r][c]
                glyph = PIECE_TO_GLYPH.get(piece, " ")
                row.append(glyph)
            lines.append(" ".join(row))
        return "\n".join(lines)

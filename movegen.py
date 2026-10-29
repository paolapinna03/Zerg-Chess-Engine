from typing import List, Tuple
from board import Move, WP, BP, WR, WN, WB, WK, WHITE_SET, BLACK_SET, EMPTY, in_bounds, color_of
from game import Board

def generate_legal_moves(board: Board) -> List[Move]:
    moves: List[Move] = []
    side = board.to_move

    for r in range(8):
        for c in range(5):
            p = board.piece_at(r, c)
            if p == EMPTY or color_of(p) != side:
                continue

            if p == WP:   # white pawn
                if r > 0 and board.piece_at(r-1, c) == EMPTY:
                    if r-1 == 0:  # promotion
                        for promo in (WR, WN, WB, WK):
                            moves.append(Move((r,c), (r-1,c), promotion=promo))
                    else:
                        moves.append(Move((r,c), (r-1,c)))

                        if r == 6 and board.piece_at(r-2, c) == EMPTY:
                            moves.append(Move((r,c), (r-2,c)))

                # capture diagonally
                for dc in (-1, +1):
                    rr, cc = r-1, c+dc
                    if in_bounds(rr, cc):
                        target = board.piece_at(rr, cc)
                        if target in BLACK_SET:
                            if rr == 0:  # promotion
                                for promo in (WR, WN, WB, WK):
                                    moves.append(Move((r,c), (rr,cc), promotion=promo))
                            else:
                                moves.append(Move((r,c), (rr,cc)))

                # en passant 
                if board.ep_square:
                    er, ec = board.ep_square
                    if r == 3 and abs(ec-c) == 1 and er == 2:
                        moves.append(Move((r,c), (er,ec), is_en_passant=True))

            elif p == BP:   # black pawn
                if r < 7 and board.piece_at(r+1, c) == EMPTY:
                    moves.append(Move((r,c), (r+1,c)))
                # capture diagonally
                for dc in (-1, +1):
                    rr, cc = r+1, c+dc
                    if in_bounds(rr, cc):
                        target = board.piece_at(rr, cc)
                        if target in WHITE_SET:
                            moves.append(Move((r,c), (rr,cc)))
                # en passant
                if board.ep_square:
                    er, ec = board.ep_square
                    if r == 4 and abs(ec - c) == 1 and er == 5:
                        moves.append(Move((r,c), (er,ec), is_en_passant=True))

            elif p == WN:   # knight
                for dr, dc in [(-2,-1), (-2,+1), (-1,-2), (-1,+2),
                               (+1,-2), (+1,+2), (+2,-1), (+2,+1)]:
                    rr, cc = r+dr, c+dc
                    if in_bounds(rr, cc):
                        target = board.piece_at(rr, cc)
                        if target == EMPTY or target in BLACK_SET:
                            moves.append(Move((r,c), (rr,cc)))

            elif p == WB:   # bishop
                for dr, dc in [(-1,-1), (-1,+1), (+1,-1), (+1,+1)]:
                    rr, cc = r+dr, c+dc
                    while in_bounds(rr, cc):
                        target = board.piece_at(rr, cc)
                        if target == EMPTY:
                            moves.append(Move((r,c), (rr,cc)))
                        elif target in BLACK_SET:
                            moves.append(Move((r,c), (rr,cc)))
                            break
                        else:  
                            break
                        rr += dr; cc += dc

            elif p == WR:   # rook
                for dr, dc in [(-1,0), (+1,0), (0,-1), (0,+1)]:
                    rr, cc = r+dr, c+dc
                    while in_bounds(rr, cc):
                        target = board.piece_at(rr, cc)
                        if target == EMPTY:
                            moves.append(Move((r,c), (rr,cc)))
                        elif target in BLACK_SET:
                            moves.append(Move((r,c), (rr,cc)))
                            break
                        else:
                            break
                        rr += dr; cc += dc

            elif p == WK:   # king
                for dr in (-1,0,+1):
                    for dc in (-1,0,+1):
                        if dr==0 and dc==0: continue
                        rr, cc = r+dr, c+dc
                        if in_bounds(rr, cc):
                            target = board.piece_at(rr, cc)
                            if target == EMPTY or target in BLACK_SET:
                                moves.append(Move((r,c), (rr,cc)))

    return moves

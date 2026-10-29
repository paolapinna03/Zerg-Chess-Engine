from __future__ import annotations
from typing import Optional, Tuple, List, Dict
import random
import time

from board import Move, EMPTY, WP, WN, WB, WR, WK, BP, Color, color_of
from game import Board
from movegen import generate_legal_moves
from engine import make, undo
from ai.evaluation import evaluate, PIECE_VALUE, INF

# ---------------------------------------------------------------------
# Tables
# ---------------------------------------------------------------------

# Transposition table: hash -> (depth, score, best_move)
transposition_table: Dict[str, Tuple[int, int, Optional[Move]]] = {}

# TT statistics
tt_stats = {"hits": 0, "misses": 0, "stores": 0}

# History heuristic table 
history_table: Dict[str, int] = {}

# Killer moves 
killer_moves: Dict[int, List[Move]] = {}

# ---------------------------------------------------------------------
# Utilities
# ---------------------------------------------------------------------

def clear_transposition_table():
    transposition_table.clear()
    tt_stats["hits"] = 0
    tt_stats["misses"] = 0
    tt_stats["stores"] = 0
    print("Transposition table cleared")

def clear_history_table():
    history_table.clear()
    print("History table cleared")

def get_tt_stats():
    total = tt_stats["hits"] + tt_stats["misses"]
    hit_rate = (tt_stats["hits"] / total * 100) if total > 0 else 0
    return {
        "entries": len(transposition_table),
        "hits": tt_stats["hits"],
        "misses": tt_stats["misses"],
        "stores": tt_stats["stores"],
        "hit_rate": hit_rate
    }

def get_board_hash(board: Board) -> str:
    parts: List[str] = []
    for r in range(8):
        for c in range(5):
            p = board.grid[r][c]
            if p != EMPTY:
                parts.append(f"{r}{c}{p}")
    parts.append(str(board.to_move))
    if board.ep_square:
        parts.append(f"ep{board.ep_square[0]}{board.ep_square[1]}")
    return "|".join(parts)

# ---------------------------------------------------------------------
# Helpers for move ordering (readable, modular)
# ---------------------------------------------------------------------

def _is_capture(board: Board, mv: Move) -> bool:
    return board.piece_at(mv.dst[0], mv.dst[1]) != EMPTY or getattr(mv, "is_en_passant", False)

def _is_promotion(mv: Move) -> bool:
    return getattr(mv, "promotion", None) is not None

def _mvv_lva_score(board: Board, mv: Move) -> int:
    victim = board.piece_at(mv.dst[0], mv.dst[1])
    attacker = board.piece_at(mv.src[0], mv.src[1])
    v_val = PIECE_VALUE.get(victim, 0)
    a_val = PIECE_VALUE.get(attacker, 0)

    if victim == BP and color_of(attacker) == Color.WHITE:
        bonus = 10_000
        leader = _bp_front_pos(board)
        if leader and mv.dst == leader:
            bonus += 2_000
        return bonus + v_val - a_val

    return v_val - a_val

def _stop_leader_block_score(board: Board, mv: Move) -> int:
    leader = _bp_front_pos(board)
    if not leader:
        return 0
    lr, lc = leader

    if mv.dst == (lr, lc) and color_of(board.piece_at(mv.src[0], mv.src[1])) == Color.WHITE:
        return 1200 

    br = lr + 1
    bc = lc
    if 0 <= br < 8 and 0 <= bc < 5:
        if mv.dst == (br, bc) and color_of(board.piece_at(mv.src[0], mv.src[1])) == Color.WHITE:
            urgency = 2 if lr >= 6 else 1
            attacker = board.piece_at(mv.src[0], mv.src[1])
            cost = PIECE_VALUE.get(attacker, 0)
            return 400 * urgency - (cost // 10)
    return 0

def _bp_front_pos(board: Board) -> Optional[Tuple[int,int]]:
    max_r = -1
    pos: Optional[Tuple[int,int]] = None
    for r in range(8):
        for c in range(5):
            if board.grid[r][c] == BP and r > max_r:
                max_r = r
                pos = (r, c)
    return pos

def _has_white_in_file_ahead(board: Board, start_r: int, c: int) -> bool:
    for rr in range(start_r + 1, 8):
        if board.grid[rr][c] in (WP, WN, WB, WR, WK):
            return True
    return False

def _file_clear_of_pieces(board: Board, start_r: int, c: int) -> bool:
    for rr in range(start_r + 1, 8):
        if board.grid[rr][c] != EMPTY:
            return False
    return True

def _is_leader_push(board: Board, mv: Move) -> bool:
    if board.piece_at(mv.src[0], mv.src[1]) != BP:
        return False
    leader = _bp_front_pos(board)
    if leader is None:
        return False
    lr, lc = leader
    if (mv.src[0], mv.src[1]) != (lr, lc):
        return False
    return mv.dst[0] > mv.src[0]

def _is_breakaway_bp(board: Board, mv: Move) -> bool:
    if board.piece_at(mv.src[0], mv.src[1]) != BP:
        return False
    if mv.dst[0] <= mv.src[0]:
        return False
    c = mv.dst[1]
    if _has_white_in_file_ahead(board, mv.dst[0]-1, c):
        return False
    return True

def _is_quiet(board: Board, mv: Move) -> bool:
    return not _is_capture(board, mv) and not _is_promotion(mv)

# ---------------------------------------------------------------------
# Professional move ordering: TT → Killer → Tactical → Quiet(HH)
# ---------------------------------------------------------------------

def order_moves(board: Board, moves: List[Move], best_move: Optional[Move] = None, depth: int = 0) -> List[Move]:
    if not moves:
        return moves

    seen: set = set()
    ordered: List[Move] = []

    def add(m: Move):
        key = (m.src, m.dst, getattr(m, "promotion", None), getattr(m, "is_en_passant", False))
        if key not in seen:
            seen.add(key)
            ordered.append(m)

    # 1) TT move first 
    if best_move and best_move in moves:
        add(best_move)

    # 2) Killer moves, depth-specific
    km_list = killer_moves.get(depth, [])
    for km in km_list:
        if km in moves and _is_quiet(board, km):
            add(km)

    # 3) Tactical moves: captures (MVV-LVA), promotions, BP leader push / breakaway
    captures: List[Tuple[int, Move]] = []
    promos: List[Move] = []
    bp_pushes: List[Tuple[int, Move]] = []
    stop_blocks: List[Tuple[int, Move]] = []

    leader = _bp_front_pos(board)  

    for mv in moves:
        if mv in ordered:
            continue

        if _is_promotion(mv):
            promos.append(mv)
            continue

        if _is_capture(board, mv):
            captures.append((_mvv_lva_score(board, mv), mv))
            continue

        sb_score = _stop_leader_block_score(board, mv)
        if sb_score:
            stop_blocks.append((sb_score, mv))
            continue
   
        if _is_leader_push(board, mv) or _is_breakaway_bp(board, mv):
            boost = 0
            if leader and _is_leader_push(board, mv):
                boost = 50
            adv = mv.dst[0] - mv.src[0]
            bp_pushes.append((adv * 100 + boost, mv))
            continue

    captures.sort(key=lambda x: x[0], reverse=True)
    for _, m in captures:
        add(m)

    for m in promos:
        add(m)

    stop_blocks.sort(key=lambda x: x[0], reverse=True)
    for _, m in stop_blocks:
        add(m)
    
    stop_blocks.sort(key=lambda x: x[0], reverse=True)
    for _, m in stop_blocks:
        add(m)

    bp_pushes.sort(key=lambda x: x[0], reverse=True)
    for _, m in bp_pushes:
        add(m)

    # 4) Quiet moves for History Heuristic
    quiet_rest: List[Tuple[int, Move]] = []
    for mv in moves:
        if mv in ordered:
            continue
        if _is_quiet(board, mv):
            key = f"{mv.src}->{mv.dst}"
            quiet_rest.append((history_table.get(key, 0), mv))

    quiet_rest.sort(key=lambda x: x[0], reverse=True)
    for _, m in quiet_rest:
        add(m)

    # Residues if something escapes the filters
    for mv in moves:
        if mv not in ordered:
            add(mv)

    return ordered

# ---------------------------------------------------------------------
# Search
# ---------------------------------------------------------------------
def negamax(board: Board, depth: int, alpha: int = -INF, beta: int = INF,
            best_move: Optional[Move] = None, start_time: Optional[float] = None,
            time_limit: float = 10.0) -> Tuple[int, Optional[Move]]:

    if start_time is not None and (time.time() - start_time > time_limit):
        return evaluate(board), None

    # TT lookup
    if depth >= 1:  
        h = get_board_hash(board)
        if h in transposition_table:
            stored_depth, stored_score, stored_move = transposition_table[h]
            if stored_depth >= depth:
                tt_stats["hits"] += 1
                return stored_score, stored_move
            tt_stats["misses"] += 1 
        else:
            tt_stats["misses"] += 1  

    winner = board.check_winner()
    if winner is not None:
        if winner == board.to_move:
            return INF - depth, None
        else:
            return -INF + depth, None

    if depth == 0:
        score = evaluate(board)
        if board.to_move == Color.BLACK:
            score = -score
        return score, None

    best_score = -INF
    best_found: Optional[Move] = None
    legal_moves = generate_legal_moves(board)
    if not legal_moves:
        if board.to_move == Color.BLACK:
            return -700, None  
        else:
            return -200, None   


    ordered_moves = order_moves(board, legal_moves, best_move, depth)

    for mv in ordered_moves:
        make(board, mv, in_analysis=True) 
        score, _ = negamax(board, depth - 1, -beta, -alpha, None, start_time, time_limit)
        score = -score
        undo(board)

        if score > best_score:
            best_score = score
            best_found = mv
        if best_score > alpha:
            alpha = best_score
        if alpha >= beta:
            # History update 
            if not _is_capture(board, mv) and not _is_promotion(mv):
                key = f"{mv.src}->{mv.dst}"
                history_table[key] = min(history_table.get(key, 0) + depth * depth, 50_000)

                # Killer moves update
                km_list = killer_moves.get(depth, [])
                if mv not in km_list:
                    km_list = [mv] + km_list[:1]
                killer_moves[depth] = km_list
            break

    # Store in TT
    if depth >= 1:  
        h = get_board_hash(board)
        transposition_table[h] = (depth, best_score, best_found)
        tt_stats["stores"] += 1

    return best_score, best_found

# ---------------------------------------------------------------------
# Smart search (Iterative + Adaptive) 
# ---------------------------------------------------------------------

def smart_search(board: Board, time_limit: float = 0.5, min_depth: int = 4) -> Optional[Move]:
    killer_moves.clear()

    legal_moves = generate_legal_moves(board)
    if not legal_moves:
        return None

    # Adaptive baseline by branching factor
    num_moves = len(legal_moves)
    if num_moves <= 5:
        max_depth = 6
    elif num_moves <= 12:
        max_depth = 5
    elif num_moves <= 20:
        max_depth = 4
    else:
        max_depth = 3  

    leader_pos = _bp_front_pos(board)
    black_front = leader_pos[0] if leader_pos else -1

    if black_front >= 6:
        max_depth += 1
    if black_front == 7:
        max_depth += 2

    max_depth = max(max_depth, min_depth)

    # Iterative deepening
    start_time = time.time()
    best_move = None
    completed_depth = 0

    for depth in range(1, max_depth + 1):
        if time.time() - start_time > time_limit:
            break

        try:
            _, move = negamax(
                board,
                depth,
                best_move=best_move,
                start_time=start_time,
                time_limit=time_limit
            )
            if move is not None:
                best_move = move
                completed_depth = depth
        except Exception:
            break

    elapsed = time.time() - start_time

    # Debug 
    threat_msg = ""
    if leader_pos:
        r, c = leader_pos
        if r == 7:
            threat_msg = f" 🚨 BP@r7(c{c})"
        elif r >= 6:
            threat_msg = f" ⚠️ BP@r{r}(c{c})"

    print(f"  [AI] {board.to_move.name}: d{completed_depth}/{max_depth}{threat_msg}, {elapsed:.2f}s, {num_moves} moves")

    move = best_move if best_move else legal_moves[0]
    return (move, completed_depth, max_depth)

# ---------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------

def choose_move(board: Board, time_limit: float = 0.5):
    return smart_search(board, time_limit=time_limit, min_depth=4)

def fast_ai_move(board: Board, time_limit: float = 0.3):
    return smart_search(board, time_limit=time_limit, min_depth=3)

# Zerg Chess Engine

A custom chess-variant engine built in Python, focused on **adversarial search, heuristic evaluation, and game-playing AI**.

Zerg Chess is played on an **8×5 board** with asymmetric roles: White uses standard chess pieces, while Black controls a swarm of pawns. The two sides therefore require very different strategies, making the game a useful testbed for search and evaluation design.

## Game rules

- **White:** King, Rook, Bishop, Knight and Pawns
- **Black:** Pawns only, initially arranged in three rows
- **White wins** by eliminating all Black pawns
- **Black wins** if a pawn reaches the final rank or all White pieces are eliminated
- No check or checkmate: victory is objective-based
- White pawns can promote; promotion is random in gameplay and deterministic during AI analysis
- En passant is supported

## AI engine

The engine uses a **Negamax search with Alpha–Beta pruning**, combined with several search optimisations:

- Iterative deepening
- Adaptive search depth
- Transposition table
- Killer move heuristic
- History heuristic
- Tactical move ordering
- MVV–LVA-inspired capture ordering
- Time-limited search

The evaluation function is asymmetric to reflect the different objectives of the two players. It combines material and activity, Black pawn advancement and coordination, captures, mobility, White defensive compactness, and anti-stalemate heuristics.

## Architecture

```text
Zerg-Chess-Engine/
├── board.py           # Piece definitions, coordinates and Move structure
├── game.py            # Board state, setup and victory conditions
├── movegen.py         # Legal move generation
├── engine.py          # Make / undo moves, promotion and en passant
├── main.py            # Application entry point
├── ui_tk.py           # Tkinter interface and AI controls
└── ai/
    ├── __init__.py
    ├── evaluation.py  # Position evaluation
    └── negamax.py     # Negamax search and search optimisations
```

## Search strategy

Move ordering follows the general pipeline:

```text
Transposition-table move
        ↓
Killer moves
        ↓
Captures / tactical moves
        ↓
Leader threats and pawn pushes
        ↓
Quiet moves ranked by history heuristic
```

Search depth is adjusted dynamically according to the branching factor and the position of the most advanced Black pawn. Iterative deepening keeps the best move found so far when the time limit is reached.

## Interface

The Tkinter GUI supports:

- Human play
- Human vs AI
- AI vs AI
- Move history
- Undo and reset
- Adjustable AI speed
- Transposition-table statistics

## Run locally

Clone the repository and run:

```bash
git clone https://github.com/paolapinna03/Zerg-Chess-Engine.git
cd Zerg-Chess-Engine
python3 main.py
```

The project uses Python's standard library and Tkinter.

## Project context

Developed as an **Intelligent Search and Games** project, with the main focus on designing a search-based agent for an asymmetric game and studying how evaluation heuristics, move ordering and pruning affect playing behaviour and search efficiency.

A project presentation is included in [`zergchess_ppt_PaolaPinna.pdf`](./zergchess_ppt_PaolaPinna.pdf).

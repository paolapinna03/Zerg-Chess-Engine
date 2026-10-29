from game import Board
from ui_tk import TkBoardUI

def main():
    b = Board()
    b.setup_manual("KRBN.")
    ui = TkBoardUI(b, square_px=64)
    print("UI created, now show...")
    ui.show()

if __name__ == "__main__":
    main()

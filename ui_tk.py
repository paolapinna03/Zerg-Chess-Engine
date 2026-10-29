import tkinter as tk
from board import Move, PIECE_TO_GLYPH, Color, color_of, type_of, WHITE_SET, BLACK_SET, EMPTY, FILES, RANKS, rc_to_coord
from game import Board
from movegen import generate_legal_moves
from engine import make, undo
from ai.negamax import choose_move, clear_transposition_table, fast_ai_move, clear_history_table, get_tt_stats
import tkinter.messagebox as messagebox


LIGHT  = "#f0d9b5"
DARK   = "#b58863"
BORDER = "#8a6e45"
HILITE = "#2b6cb0"

SHAPE_BY_TYPE = {"P":"♟", "N":"♞", "B":"♝", "R":"♜", "K":"♛"}

def piece_draw_info(piece):
    if piece == EMPTY:
        return None
    typ = type_of(piece)              
    glyph = SHAPE_BY_TYPE[typ]
    col = color_of(piece)
    fill = "#ffffff" if col == Color.WHITE else "#111111"
    return glyph, fill

def _blend_hex(base_hex, overlay_hex, alpha):
    def _to_rgb(h):
        h = h.lstrip('#')
        return tuple(int(h[i:i+2], 16) for i in (0, 2, 4))
    def _to_hex(rgb):
        return '#%02x%02x%02x' % rgb
    br, bg, bb = _to_rgb(base_hex)
    or_, og, ob = _to_rgb(overlay_hex)
    r = int(round((1-alpha)*br + alpha*or_))
    g = int(round((1-alpha)*bg + alpha*og))
    b = int(round((1-alpha)*bb + alpha*ob))
    return _to_hex((r, g, b))


class TkBoardUI:
    def __init__(self, board, square_px=64, title="Zerg Chess — Viewer", move_func=None):
        self.board = board
        self.s = square_px
        self.margin = 24
        self.selected = None
        self.sel_rect_id = None
        self.legal_from_src = []
        self.dot_ids = []
        self._hitbox_by_rc = {}
        self._bg_by_rc = {}
        self._piece_text_ids_by_rc = {}

        self.ai_enabled = False
        self.ai_vs_ai_enabled = False
        self.time_limit = 0.5  
        self.ai_speed = "normal"  
        self.game_over = False  
        self.root = tk.Tk()
        self.root.title(title)
        self.root.protocol("WM_DELETE_WINDOW", self.close)

        self.root.rowconfigure(0, weight=1)  
        self.root.rowconfigure(1, weight=0)  
        self.root.columnconfigure(0, weight=1) 
        self.root.columnconfigure(1, weight=0) 

        w = self.margin + 5*self.s + 4 + 160  
        h = self.margin + 8*self.s + 4
        self.root.minsize(width=w, height=h+56)

        # Canvas
        self.canvas = tk.Canvas(self.root, bg="#faf7f2", highlightthickness=0)
        self.canvas.grid(row=0, column=0, sticky="nsew")  

        # Sidebar moves
        side = tk.Frame(self.root)
        side.grid(row=0, column=1, sticky="ns", padx=(6, 6), pady=(6, 6))
        side.rowconfigure(1, weight=1)
        lbl = tk.Label(side, text="Moves", anchor="w")
        lbl.grid(row=0, column=0, sticky="ew")
        sb = tk.Scrollbar(side, orient="vertical")
        sb.grid(row=1, column=1, sticky="ns")
        self.moves_text = tk.Text(side, width=18, height=20, state="disabled")
        self.moves_text.grid(row=1, column=0, sticky="nsew")
        self.moves_text.configure(yscrollcommand=sb.set)
        sb.configure(command=self.moves_text.yview)
        self.move_strings = []  
        self.ply_count = 0

        # Buttons frame
        btn_frame = tk.Frame(self.root)
        btn_frame.grid(row=1, column=0, columnspan=2, sticky="ew", pady=6)
        btn_frame.columnconfigure(0, weight=1)
        btn_frame.columnconfigure(1, weight=1)
        btn_frame.columnconfigure(2, weight=1)
        btn_frame.columnconfigure(3, weight=1)
        btn_frame.columnconfigure(4, weight=1)

        btn_undo = tk.Button(btn_frame, text="Undo", command=self._on_undo, cursor="hand2")
        btn_undo.grid(row=0, column=0, padx=6)

        btn_reset = tk.Button(btn_frame, text="Reset", command=self._on_reset, cursor="hand2")
        btn_reset.grid(row=0, column=1, padx=6)

        # AI controls
        self.btn_ai = tk.Button(btn_frame, text="Play vs AI", command=self._toggle_ai, cursor="hand2")
        self.btn_ai.grid(row=0, column=2, padx=6)
        
        self.btn_ai_vs_ai = tk.Button(btn_frame, text="AI vs AI", command=self._toggle_ai_vs_ai, cursor="hand2")
        self.btn_ai_vs_ai.grid(row=0, column=3, padx=6)

        # AI Speed selection 
        speed_frame = tk.Frame(btn_frame)
        speed_frame.grid(row=0, column=4, padx=6)
        tk.Label(speed_frame, text="AI Speed:").pack(side=tk.LEFT)
        self.speed_var = tk.StringVar(value=self.ai_speed)
        speed_combo = tk.OptionMenu(speed_frame, self.speed_var, "fast", "normal", "slow", command=self._update_ai_speed)
        speed_combo.pack(side=tk.LEFT)
        
        
        info_frame = tk.Frame(btn_frame)
        info_frame.grid(row=0, column=5, padx=6)
        self.info_label = tk.Label(info_frame, text="(depth ?, 0.5s)", fg="gray")
        self.info_label.pack(side=tk.LEFT)
        
        # Clear Cache
        clear_btn = tk.Button(btn_frame, text="Clear Cache", command=self._clear_cache, cursor="hand2")
        clear_btn.grid(row=0, column=6, padx=6)
        
        # TT stats label
        self.tt_stats_label = tk.Label(btn_frame, text="TT: 0/0 (0%)", fg="blue", font=("Helvetica", 9))
        self.tt_stats_label.grid(row=0, column=7, padx=6)

        self.font = ("Helvetica", int(self.s*0.72))

        self.draw_board()

    # ---------- draw board ----------
    def draw_board(self):
        c = self.canvas
        c.delete("all")
        try:
            c.delete("dot")
        except Exception:
            pass
        m, s = self.margin, self.s

        self._sq_by_id = {}
        c.create_rectangle(m-6, m-6, m+5*s+6, m+8*s+6, outline=BORDER, width=2)

        for r in range(8):
            for col in range(5):
                x0 = m + col*s
                y0 = m + r*s
                x1 = x0 + s
                y1 = y0 + s
                color = DARK if ((r+col) & 1) == 0 else LIGHT  
                bg_id = c.create_rectangle(x0, y0, x1, y1, fill=color, outline=color, tags=("square", f"s{r}_{col}"))
                self._bg_by_rc[(r, col)] = bg_id
                self._sq_by_id[bg_id] = (r, col)
            
                info = piece_draw_info(self.board.grid[r][col])
                if info:
                    glyph, fill = info
                    cx, cy = (x0+x1)//2, (y0+y1)//2
                    tag = (f"s{r}_{col}", "square")  
                    if fill == "#ffffff":
                        for dx, dy in ((-1,0),(1,0),(0,-1),(0,1)):
                            c.create_text(cx+dx, cy+dy, text=glyph, font=self.font, fill="#000000", tags=tag)
                    t_shadow = c.create_text(cx, cy+1, text=glyph, font=self.font, fill="#222222", tags=tag)  
                    t_main   = c.create_text(cx, cy,   text=glyph, font=self.font, fill=fill, tags=tag)
                    self._piece_text_ids_by_rc[(r, col)] = (t_shadow, t_main)
                    self._sq_by_id[t_shadow] = (r, col)
                    self._sq_by_id[t_main] = (r, col)
                

        c.tag_bind("square", "<Button-1>", self._on_square_click)
   
        for col, f in enumerate(FILES):
            x = m + col*s + s/2
            self._label(x, m-12, f)
        for r, rk in enumerate(RANKS):
            y = m + r*s + s/2
            self._label(m-12, y, rk)
        
        if self.selected is not None:
            self._draw_selection(self.selected, on=True)
            if self.legal_from_src:
                self._draw_destination_dots(self.legal_from_src)

    def _label(self, x, y, text):
        self.canvas.create_text(x, y, text=text, font=("monospace", 11))

    def _which_square(self, x, y):
        m, s = self.margin, self.s
        frame_x0, frame_y0 = m-6, m-6
        frame_x1, frame_y1 = m+5*s+6, m+8*s+6
        if x < frame_x0 or y < frame_y0 or x >= frame_x1 or y >= frame_y1:
            return None
        if x < m: x = m
        if y < m: y = m
        if x >= m+5*s: x = m+5*s-1
        if y >= m+8*s: y = m+8*s-1
        c = int((x - m) // s)
        r = int((y - m) // s)
        return (r, c)

    

    def _draw_selection(self, sq, on):
        if self.sel_rect_id is not None:
            self.canvas.delete(self.sel_rect_id)
            self.sel_rect_id = None
        if not on:
            self._clear_dots()
            return
        r, c = sq
        m, s = self.margin, self.s
        x0 = m + c*s; y0 = m + r*s
        x1 = x0 + s;  y1 = y0 + s
        self.sel_rect_id = self.canvas.create_rectangle(
            x0+2, y0+2, x1-2, y1-2, outline=HILITE, width=3
        )
        try:
            self.canvas.itemconfigure(self.sel_rect_id, state="disabled")
        except Exception:
            pass
    
    def _clear_dots(self):
        try:
            self.canvas.delete("dot")
        except Exception:
            pass
        self.dot_ids = []

    def _draw_destination_dots(self, moves):
        self._clear_dots()
        m, s = self.margin, self.s
        r_px = max(3, int(s * 0.10))
        for mv in moves:
            r, c = mv.dst
            x0 = m + c*s
            y0 = m + r*s
            cx = (x0 + x0 + s) // 2
            cy = (y0 + y0 + s) // 2
            oid = self.canvas.create_oval(
                cx - r_px, cy - r_px, cx + r_px, cy + r_px,
                fill="#bbbbbb", outline="",
                tags=("square", f"s{r}_{c}", "dot")
            )
            piece_ids = self._piece_text_ids_by_rc.get((r, c))
            if piece_ids:
                self.canvas.tag_raise(oid)
            self.dot_ids.append(oid)
            self._sq_by_id[oid] = (r, c)
        try:
            self.canvas.tag_raise("dot")
        except Exception:
            pass
    
    def _on_square_click(self, event):
        sq = self._which_square(event.x, event.y)
        if sq is None:
            return
        r, c = sq
        self._handle_square_click(r, c)

    def _handle_square_click(self, r, c):
        if self.game_over:
            return
        
        self._clear_dots()
        if self.selected is None:
            piece = self.board.piece_at(r, c)
            if piece == EMPTY or color_of(piece) != self.board.to_move:
                return
            self.selected = (r, c)
            self._draw_selection(self.selected, on=True)
            self.legal_from_src = [m for m in generate_legal_moves(self.board) if m.src == self.selected]
            self._draw_destination_dots(self.legal_from_src)
            return
        else:
            src, dst = self.selected, (r, c)
            self.selected = None
            self._draw_selection((0,0), on=False)
            self._clear_dots()
            for m in self.legal_from_src:
                if m.dst == dst:
                    pre_target = self.board.piece_at(dst[0], dst[1])
                    was_capture = (pre_target != EMPTY) or m.is_en_passant
                    
                    moving_side = self.board.to_move
                    src_coord = rc_to_coord(src[0], src[1])
                    dst_coord = rc_to_coord(dst[0], dst[1])
                    self.legal_from_src = []
                    make(self.board, m)
                    
                    promo_suffix = ""
                    if m.promotion:
                        final_piece = self.board.piece_at(dst[0], dst[1])
                        typ = type_of(final_piece)
                        if typ and typ != "P":
                            promo_suffix = f"={typ}"
                    sep = "x" if was_capture else "-"
                    mv_str = f"{src_coord}{sep}{dst_coord}{promo_suffix}"
                    self._append_move(mv_str, moving_side)
                    self.refresh()
                    self.root.update()  

                    # AI move 
                    if self.ai_enabled and self.board.to_move == Color.BLACK:
                        self._make_ai_move()
                    elif self.ai_vs_ai_enabled:
                        self._make_ai_move()
                    winner = self.board.check_winner()
                    if winner is not None:
                        import tkinter.messagebox as messagebox
                        messagebox.showinfo("Game Over",
                            "White wins! 🎉" if winner == Color.WHITE else "Black wins! 🏆")
                        self._on_reset()  
                    return
            self.legal_from_src = []

    
    def _on_reset(self):
        self.board.setup_random()   
        self.board.undo_stack = []
        self.board.to_move = Color.WHITE
        self.board.ep_square = None
        self.selected = None
        self._clear_dots()
        self.refresh()
        self._clear_moves_panel()
        # Reset AI state
        self.ai_enabled = False
        self.ai_vs_ai_enabled = False
        self.game_over = False  
        self._update_ai_button()
        self._update_ai_vs_ai_button()


    def _on_undo(self):
        if undo(self.board):
            self._clear_dots()
            self.refresh()
            self._pop_move()
            self.ai_enabled = False
            self.ai_vs_ai_enabled = False
            self._update_ai_button()
            self._update_ai_vs_ai_button()

    def refresh(self):
        self.draw_board()

    # ---------- moves panel helpers ----------
    def _append_move(self, mv_str, side):
        num = self.ply_count // 2 + 1
        prefix = f"{num}. " if side == Color.WHITE else f"{num}... "
        line = prefix + mv_str
        self.move_strings.append(line)
        self.ply_count += 1
        self._render_moves_text()

    def _pop_move(self):
        if not self.move_strings:
            return
        self.move_strings.pop()
        if self.ply_count > 0:
            self.ply_count -= 1
        self._render_moves_text()

    def _clear_moves_panel(self):
        self.move_strings = []
        self.ply_count = 0
        self._render_moves_text()

    def _render_moves_text(self):
        self.moves_text.configure(state="normal")
        self.moves_text.delete("1.0", tk.END)
        for s in self.move_strings:
            self.moves_text.insert(tk.END, s + "\n")
        self.moves_text.see(tk.END)
        self.moves_text.configure(state="disabled")

    # ---------- AI helpers ----------
    def _toggle_ai(self):
        self.ai_enabled = not self.ai_enabled
        if self.ai_enabled:
            self.ai_vs_ai_enabled = False 
        self._update_ai_button()
        self._update_ai_vs_ai_button()
        if self.ai_enabled and self.board.to_move == Color.BLACK:
            self._make_ai_move()

    def _toggle_ai_vs_ai(self):
        self.ai_vs_ai_enabled = not self.ai_vs_ai_enabled
        if self.ai_vs_ai_enabled:
            self.ai_enabled = False
        self._update_ai_button()
        self._update_ai_vs_ai_button()
        
        self.root.update()
        
        if self.ai_vs_ai_enabled:
            self._make_ai_move()

    def _update_ai_button(self):
        text = "Stop AI" if self.ai_enabled else "Play vs AI"
        self.btn_ai.configure(text=text)

    def _update_ai_vs_ai_button(self):
        text = "Stop AI vs AI" if self.ai_vs_ai_enabled else "AI vs AI"
        self.btn_ai_vs_ai.configure(text=text)

    def _update_ai_speed(self, speed):
        self.ai_speed = speed
        if speed == "fast":
            info = "(depth ?, 0.2s)"
        elif speed == "slow":
            info = "(depth ?, 1.0s)"
        else: 
            info = "(depth ?, 0.5s)"
        self.info_label.config(text=info)
        print(f"AI speed changed to: {speed} {info}")
    
    def _clear_cache(self):
        clear_transposition_table()
        clear_history_table()
        self._update_tt_stats()
        print("Cache cleared - AI will be slightly slower on next move")
    
    def _update_tt_stats(self):
        stats = get_tt_stats()
        text = f"TT: {stats['hits']}/{stats['hits']+stats['misses']} ({stats['hit_rate']:.0f}%) | {stats['entries']} entries"
        self.tt_stats_label.config(text=text)

    def _make_ai_move(self):
        if not (self.ai_enabled or self.ai_vs_ai_enabled):
            return
        if self.ai_enabled and self.board.to_move != Color.BLACK:
            return
        try:
            self.root.update()
            
            if self.ai_speed == "fast":
                result = fast_ai_move(self.board, time_limit=0.2)
            elif self.ai_speed == "slow":
                result = choose_move(self.board, time_limit=1.0)
            else:  
                result = choose_move(self.board, time_limit=0.5)
            
            if result:
                ai_move, completed_depth, max_depth = result
                time_str = "0.2s" if self.ai_speed == "fast" else ("1.0s" if self.ai_speed == "slow" else "0.5s")
                self.info_label.config(text=f"(depth {completed_depth}, {time_str})")
            else:
                ai_move = None
            
            if ai_move:
                pre_target = self.board.piece_at(ai_move.dst[0], ai_move.dst[1])
                was_capture = (pre_target != EMPTY) or ai_move.is_en_passant
                moving_side = self.board.to_move
                src_coord = rc_to_coord(ai_move.src[0], ai_move.src[1])
                dst_coord = rc_to_coord(ai_move.dst[0], ai_move.dst[1])
                make(self.board, ai_move)

                promo_suffix = ""
                if ai_move.promotion:
                    final_piece = self.board.piece_at(ai_move.dst[0], ai_move.dst[1])
                    typ = type_of(final_piece)
                    if typ and typ != "P":
                        promo_suffix = f"={typ}"
                sep = "x" if was_capture else "-"
                mv_str = f"{src_coord}{sep}{dst_coord}{promo_suffix}"
                self._append_move(mv_str, moving_side)
                self.refresh()
                self._update_tt_stats()  
                self.root.update()  
                winner = self.board.check_winner()
                if winner is not None:
                    import tkinter.messagebox as messagebox
                    messagebox.showinfo("Game Over",
                        "White wins! 🎉" if winner == Color.WHITE else "Black wins! 🏆")
                    self._on_reset()  
                elif self.ai_vs_ai_enabled:
                    self.root.after(10, self._make_ai_move)  
            else:
                print("AI returned None - game should end")
                import tkinter.messagebox as messagebox
                messagebox.showinfo("Game Over", "Stalemate - No legal moves available!")
                self._on_reset()  
        except Exception as e:
            print(f"AI error: {e}")
            self.ai_enabled = False
            self.ai_vs_ai_enabled = False
            self._update_ai_button()
            self._update_ai_vs_ai_button()

    def show(self, block=True):
        if block:
            self.root.mainloop()
        else:
            self.root.update_idletasks()
            self.root.update()

    def close(self):
        self.root.destroy()




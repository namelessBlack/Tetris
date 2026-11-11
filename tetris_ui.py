import sys
import tkinter as tk
from pathlib import Path

from tetris_logic import (
    BOARD_HEIGHT, BOARD_WIDTH, NEXT_COUNT, Game, shape_cells,
)


CELL = 30
SMALL_CELL = 20
MARGIN = 24
GAP = 20
SIDE_W = 160

BOARD_W = BOARD_WIDTH * CELL
BOARD_H = BOARD_HEIGHT * CELL
LEFT_X = MARGIN
BOARD_X = LEFT_X + SIDE_W + GAP
BOARD_Y = MARGIN
RIGHT_X = BOARD_X + BOARD_W + GAP
WINDOW_W = RIGHT_X + SIDE_W + MARGIN
WINDOW_H = BOARD_H + 2 * MARGIN


BG = "#0f111a"
PANEL = "#1a1d2b"
BOARD_BG = "#0a0c13"
GRID = "#1c2030"
TEXT = "#eceef8"
MUTED = "#7d84a3"
ACCENT = "#7c6cff"
FLASH = "#ffffff"

PIECE_COLORS = {
    "I": "#2ec4e6",
    "O": "#f5c945",
    "T": "#a763f0",
    "S": "#4fcf6b",
    "Z": "#ef5466",
    "J": "#4a78f0",
    "L": "#f2913a",
}


FLASH_STEPS = 6
FLASH_MS = 45
HIGHSCORE_FILE = Path(__file__).with_name("highscore.txt")

if sys.platform == "darwin":
    FONT = "Helvetica Neue"
elif sys.platform == "win32":
    FONT = "Segoe UI"
else:
    FONT = "DejaVu Sans"

CONTROLS_HELP = [
    ("←  →", "влево / вправо"),
    ("↓", "быстрее вниз"),
    ("↑  или  X", "поворот"),
    ("Z", "поворот обратно"),
    ("Пробел", "сбросить до упора"),
    ("C", "убрать в запас"),
    ("P", "пауза"),
    ("R", "новая игра"),
]


def mix(color, other, amount):
    result = "#"
    for i in (1, 3, 5):
        a = int(color[i:i + 2], 16)
        b = int(other[i:i + 2], 16)
        result += f"{round(a + (b - a) * amount):02x}"
    return result


def font(size, bold=False):
    return (FONT, -size, "bold") if bold else (FONT, -size)


def load_highscore():
    try:
        return int(HIGHSCORE_FILE.read_text().strip())
    except (OSError, ValueError):
        return 0


def save_highscore(value):
    try:
        HIGHSCORE_FILE.write_text(str(value))
    except OSError:
        pass


class TetrisApp:
    def __init__(self):
        self.game = Game()
        self.best = load_highscore()
        self.best_changed = False
        self.flash_on = False
        self.fall_job = None
        self.flash_job = None

        self.root = tk.Tk()
        self.root.title("Тетрис")
        self.root.configure(bg=BG)
        self.root.resizable(False, False)
        self.canvas = tk.Canvas(
            self.root, width=WINDOW_W, height=WINDOW_H,
            bg=BG, highlightthickness=0,
        )
        self.canvas.pack()

        self.keys = self._make_key_table()
        self.root.bind("<KeyPress>", self._on_key)
        self.root.protocol("WM_DELETE_WINDOW", self._on_close)

        self._draw_static()
        self.render()
        self._center_window()
        self._schedule_fall()

    def run(self):
        self.root.mainloop()


    def _make_key_table(self):
        game = self.game
        table = {
            "Left": lambda: game.move(-1),
            "Right": lambda: game.move(1),
            "Down": game.soft_drop,
            "Up": game.rotate,
            "space": self._hard_drop,
            "x": game.rotate,
            "z": lambda: game.rotate(clockwise=False),
            "c": game.hold,
            "p": game.toggle_pause,
            "r": self._restart,
        }
        for latin, cyrillic in (("x", "ч"), ("z", "я"), ("c", "с"), ("p", "з"), ("r", "к")):
            table[cyrillic] = table[latin]
        return table

    def _on_key(self, event):
        name = event.keysym if event.keysym in self.keys else event.char.lower()
        action = self.keys.get(name)
        if action is not None:
            action()
            self._after_action()

    def _hard_drop(self):
        self.game.hard_drop()
        self._schedule_fall()

    def _restart(self):
        if self.flash_job is not None:
            self.root.after_cancel(self.flash_job)
            self.flash_job = None
        self.flash_on = False
        self._save_best()
        self.game.reset()
        self._schedule_fall()

    def _schedule_fall(self):
        if self.fall_job is not None:
            self.root.after_cancel(self.fall_job)
        self.fall_job = self.root.after(self.game.fall_interval_ms(), self._on_fall_timer)

    def _on_fall_timer(self):
        self.fall_job = None
        self.game.tick()
        self._after_action()
        self._schedule_fall()

    def _after_action(self):
        if self.game.score > self.best:
            self.best = self.game.score
            self.best_changed = True
        if self.game.game_over:
            self._save_best()

        if self.game.clearing_rows and self.flash_job is None:
            self._flash_step(0)
        else:
            self.render()

    def _flash_step(self, step):
        if step == FLASH_STEPS:
            self.flash_job = None
            self.flash_on = False
            self.game.finish_clear()
            self._schedule_fall()
            self._after_action()
            return
        self.flash_on = (step % 2 == 0)
        self.render()
        self.flash_job = self.root.after(FLASH_MS, self._flash_step, step + 1)

    def _save_best(self):
        if self.best_changed:
            save_highscore(self.best)
            self.best_changed = False

    def _on_close(self):
        self._save_best()
        self.root.destroy()

    def _center_window(self):
        self.root.update_idletasks()
        x = (self.root.winfo_screenwidth() - WINDOW_W) // 2
        y = max(0, (self.root.winfo_screenheight() - WINDOW_H) // 3)
        self.root.geometry(f"{WINDOW_W}x{WINDOW_H}+{x}+{y}")
        self.root.lift()
        self.root.focus_force()


    def _draw_static(self):
        self._draw_title()
        self._draw_board_frame()

        self._draw_card(LEFT_X, 84, SIDE_W, 130, "ЗАПАС")
        self._draw_card(LEFT_X, 230, SIDE_W, WINDOW_H - MARGIN - 230, "УПРАВЛЕНИЕ")
        for i, (key, meaning) in enumerate(CONTROLS_HELP):
            y = 276 + i * 43
            self._text(LEFT_X + 16, y, key, 13, TEXT, bold=True)
            self._text(LEFT_X + 16, y + 17, meaning, 12, MUTED)

        self._draw_card(RIGHT_X, MARGIN, SIDE_W, 280, "ДАЛЕЕ")
        self.stat_items = {}
        for i, label in enumerate(("СЧЁТ", "РЕКОРД", "УРОВЕНЬ", "ЛИНИИ")):
            y = 320 + i * 79
            self._draw_card(RIGHT_X, y, SIDE_W, 67, label)
            self.stat_items[label] = self._text(RIGHT_X + 16, y + 44, "0", 22, TEXT, bold=True)

    def _draw_title(self):
        colors = [PIECE_COLORS[kind] for kind in "ZLOSIT"]
        step = SIDE_W / 6
        for i, (letter, color) in enumerate(zip("ТЕТРИС", colors)):
            self.canvas.create_text(
                LEFT_X + step * (i + 0.5), 50, text=letter,
                font=font(30, bold=True), fill=color,
            )

    def _draw_board_frame(self):
        self._round_rect(BOARD_X - 6, BOARD_Y - 6, BOARD_X + BOARD_W + 6,
                         BOARD_Y + BOARD_H + 6, 12, fill=PANEL)
        self.canvas.create_rectangle(BOARD_X, BOARD_Y, BOARD_X + BOARD_W,
                                     BOARD_Y + BOARD_H, fill=BOARD_BG, outline="")
        for col in range(1, BOARD_WIDTH):
            x = BOARD_X + col * CELL
            self.canvas.create_line(x, BOARD_Y, x, BOARD_Y + BOARD_H, fill=GRID)
        for row in range(1, BOARD_HEIGHT):
            y = BOARD_Y + row * CELL
            self.canvas.create_line(BOARD_X, y, BOARD_X + BOARD_W, y, fill=GRID)

    def _draw_card(self, x, y, width, height, label):
        self._round_rect(x, y, x + width, y + height, 14, fill=PANEL)
        self._text(x + 16, y + 20, label, 11, MUTED, bold=True)


    def render(self):
        game = self.game
        self.canvas.delete("dyn")

        if game.paused:
            self._draw_message("ПАУЗА", ["P — продолжить"])
        else:
            self._draw_locked_blocks()
            self._draw_ghost()
            self._draw_current_piece()
            if game.game_over:
                self._draw_message("ИГРА ОКОНЧЕНА",
                                   [f"Счёт: {game.score}", "R — новая игра"])

        self._draw_side_pieces()
        self._update_stats()

    def _draw_locked_blocks(self):
        for row in range(BOARD_HEIGHT):
            flashing = self.flash_on and row in self.game.clearing_rows
            for col in range(BOARD_WIDTH):
                kind = self.game.board[row][col]
                if kind is not None:
                    color = FLASH if flashing else PIECE_COLORS[kind]
                    self._draw_board_cell(row, col, color)

    def _draw_ghost(self):
        ghost = self.game.ghost_piece()
        if ghost is None:
            return
        color = mix(PIECE_COLORS[ghost.kind], BOARD_BG, 0.45)
        for row, col in ghost.board_cells():
            if row >= 0:
                x = BOARD_X + col * CELL
                y = BOARD_Y + row * CELL
                self.canvas.create_rectangle(
                    x + 3, y + 3, x + CELL - 3, y + CELL - 3,
                    outline=color, width=2, tags="dyn",
                )

    def _draw_current_piece(self):
        piece = self.game.current
        if piece is None:
            return
        for row, col in piece.board_cells():
            if row >= 0:
                self._draw_board_cell(row, col, PIECE_COLORS[piece.kind])

    def _draw_side_pieces(self):
        game = self.game
        if game.hold_kind is not None:
            self._draw_small_piece(game.hold_kind, LEFT_X + SIDE_W / 2, 84 + 78,
                                   dimmed=game.hold_used)
        for i in range(NEXT_COUNT):
            self._draw_small_piece(game.next_kinds[i], RIGHT_X + SIDE_W / 2,
                                   MARGIN + 84 + i * 78)

    def _update_stats(self):
        values = {
            "СЧЁТ": self.game.score,
            "РЕКОРД": self.best,
            "УРОВЕНЬ": self.game.level,
            "ЛИНИИ": self.game.lines,
        }
        for label, value in values.items():
            self.canvas.itemconfigure(self.stat_items[label], text=str(value))

    def _draw_message(self, title, lines):
        cx = BOARD_X + BOARD_W / 2
        cy = BOARD_Y + BOARD_H / 2
        self._round_rect(cx - 125, cy - 75, cx + 125, cy + 75, 16,
                         fill=PANEL, outline=ACCENT, width=2, tags="dyn")
        self.canvas.create_text(cx, cy - 34, text=title, fill=TEXT,
                                font=font(22, bold=True), tags="dyn")
        for i, line in enumerate(lines):
            self.canvas.create_text(cx, cy + 8 + i * 26, text=line, fill=MUTED,
                                    font=font(14), tags="dyn")


    def _draw_board_cell(self, row, col, color):
        self._draw_block(BOARD_X + col * CELL, BOARD_Y + row * CELL, CELL, color)

    def _draw_small_piece(self, kind, center_x, center_y, dimmed=False):
        cells = shape_cells(kind)
        rows = [r for r, _ in cells]
        cols = [c for _, c in cells]
        width = (max(cols) - min(cols) + 1) * SMALL_CELL
        height = (max(rows) - min(rows) + 1) * SMALL_CELL
        left = center_x - width / 2
        top = center_y - height / 2
        color = PIECE_COLORS[kind]
        if dimmed:
            color = mix(color, PANEL, 0.65)
        for r, c in cells:
            self._draw_block(left + (c - min(cols)) * SMALL_CELL,
                             top + (r - min(rows)) * SMALL_CELL, SMALL_CELL, color)

    def _draw_block(self, x, y, size, color):
        canvas = self.canvas
        bevel = max(2, size // 7)
        x1, y1 = x + 1, y + 1
        x2, y2 = x + size - 1, y + size - 1
        ix1, iy1, ix2, iy2 = x1 + bevel, y1 + bevel, x2 - bevel, y2 - bevel

        faces = [
            ((x1, y1, x2, y1, ix2, iy1, ix1, iy1), mix(color, "#ffffff", 0.45)),
            ((x1, y1, ix1, iy1, ix1, iy2, x1, y2), mix(color, "#ffffff", 0.18)),
            ((x2, y1, x2, y2, ix2, iy2, ix2, iy1), mix(color, "#000000", 0.25)),
            ((x1, y2, ix1, iy2, ix2, iy2, x2, y2), mix(color, "#000000", 0.45)),
        ]
        for points, face_color in faces:
            canvas.create_polygon(*points, fill=face_color, outline="", tags="dyn")
        canvas.create_rectangle(ix1, iy1, ix2, iy2, fill=color, outline="", tags="dyn")

    def _round_rect(self, x1, y1, x2, y2, radius, **options):
        r = radius
        points = [
            x1 + r, y1, x2 - r, y1, x2, y1, x2, y1 + r,
            x2, y2 - r, x2, y2, x2 - r, y2, x1 + r, y2,
            x1, y2, x1, y2 - r, x1, y1 + r, x1, y1,
        ]
        return self.canvas.create_polygon(points, smooth=True, **options)

    def _text(self, x, y, text, size, color, bold=False):
        return self.canvas.create_text(x, y, text=text, font=font(size, bold),
                                       fill=color, anchor="w")

import random
from dataclasses import dataclass, replace


BOARD_WIDTH = 10
BOARD_HEIGHT = 20
NEXT_COUNT = 3

LINES_PER_LEVEL = 10
START_FALL_MS = 800
FALL_STEP_MS = 60
MIN_FALL_MS = 80

LINE_SCORES = {1: 100, 2: 300, 3: 500, 4: 800}
SOFT_DROP_SCORE = 1
HARD_DROP_SCORE = 2


SHAPES = {
    "I": ["....",
          "####",
          "....",
          "...."],

    "O": ["##",
          "##"],

    "T": [".#.",
          "###",
          "..."],

    "S": [".##",
          "##.",
          "..."],

    "Z": ["##.",
          ".##",
          "..."],

    "J": ["#..",
          "###",
          "..."],

    "L": ["..#",
          "###",
          "..."],
}


def shape_cells(kind):
    picture = SHAPES[kind]
    cells = []
    for row, line in enumerate(picture):
        for col, symbol in enumerate(line):
            if symbol == "#":
                cells.append((row, col))
    return cells


@dataclass(frozen=True)
class Piece:
    kind: str
    cells: tuple
    size: int
    row: int
    col: int

    def board_cells(self):
        return [(self.row + r, self.col + c) for r, c in self.cells]

    def moved(self, d_row, d_col):
        return replace(self, row=self.row + d_row, col=self.col + d_col)

    def rotated(self, clockwise=True):
        last = self.size - 1
        if clockwise:
            new_cells = tuple((c, last - r) for r, c in self.cells)
        else:
            new_cells = tuple((last - c, r) for r, c in self.cells)
        return replace(self, cells=new_cells)


def new_piece(kind):
    cells = tuple(shape_cells(kind))
    size = len(SHAPES[kind])
    top_empty_rows = min(r for r, _ in cells)
    return Piece(
        kind=kind,
        cells=cells,
        size=size,
        row=-top_empty_rows,
        col=(BOARD_WIDTH - size) // 2,
    )


class Game:
    def __init__(self):
        self.reset()

    def reset(self):
        self.board = [[None] * BOARD_WIDTH for _ in range(BOARD_HEIGHT)]
        self.bag = []
        self.next_kinds = [self._take_from_bag() for _ in range(NEXT_COUNT)]
        self.hold_kind = None
        self.hold_used = False
        self.score = 0
        self.lines = 0
        self.level = 1
        self.paused = False
        self.game_over = False
        self.clearing_rows = []
        self.current = None
        self._spawn_next()


    def is_active(self):
        return self.current is not None and not self.paused and not self.game_over

    def fits(self, piece):
        for row, col in piece.board_cells():
            if col < 0 or col >= BOARD_WIDTH or row >= BOARD_HEIGHT:
                return False
            if row >= 0 and self.board[row][col] is not None:
                return False
        return True

    def ghost_piece(self):
        if self.current is None:
            return None
        ghost = self.current
        while self.fits(ghost.moved(1, 0)):
            ghost = ghost.moved(1, 0)
        return ghost

    def fall_interval_ms(self):
        interval = START_FALL_MS - (self.level - 1) * FALL_STEP_MS
        return max(MIN_FALL_MS, interval)


    def move(self, d_col):
        if self.is_active():
            self._try_place(self.current.moved(0, d_col))

    def rotate(self, clockwise=True):
        if not self.is_active():
            return
        turned = self.current.rotated(clockwise)
        for shift in (0, -1, 1, -2, 2):
            if self._try_place(turned.moved(0, shift)):
                return

    def soft_drop(self):
        if self.is_active() and self._try_place(self.current.moved(1, 0)):
            self.score += SOFT_DROP_SCORE

    def hard_drop(self):
        if not self.is_active():
            return
        landed = self.ghost_piece()
        self.score += HARD_DROP_SCORE * (landed.row - self.current.row)
        self.current = landed
        self._lock()

    def hold(self):
        if not self.is_active() or self.hold_used:
            return
        from_hold = self.hold_kind
        self.hold_kind = self.current.kind
        if from_hold is None:
            self._spawn_next()
        else:
            self._spawn(from_hold)
        self.hold_used = True

    def toggle_pause(self):
        if not self.game_over:
            self.paused = not self.paused


    def tick(self):
        if not self.is_active():
            return
        if not self._try_place(self.current.moved(1, 0)):
            self._lock()

    def finish_clear(self):
        if not self.clearing_rows:
            return
        count = len(self.clearing_rows)
        kept = [row for i, row in enumerate(self.board) if i not in self.clearing_rows]
        empty = [[None] * BOARD_WIDTH for _ in range(count)]
        self.board = empty + kept

        self.score += LINE_SCORES[count] * self.level
        self.lines += count
        self.level = self.lines // LINES_PER_LEVEL + 1
        self.clearing_rows = []
        self._spawn_next()


    def _try_place(self, piece):
        if self.fits(piece):
            self.current = piece
            return True
        return False

    def _take_from_bag(self):
        if not self.bag:
            self.bag = list(SHAPES)
            random.shuffle(self.bag)
        return self.bag.pop()

    def _spawn_next(self):
        kind = self.next_kinds.pop(0)
        self.next_kinds.append(self._take_from_bag())
        self._spawn(kind)

    def _spawn(self, kind):
        piece = new_piece(kind)
        if self.fits(piece):
            self.current = piece
        else:
            self.current = None
            self.game_over = True

    def _lock(self):
        for row, col in self.current.board_cells():
            if row >= 0:
                self.board[row][col] = self.current.kind
        self.current = None
        self.hold_used = False

        full_rows = [i for i, row in enumerate(self.board) if all(row)]
        if full_rows:
            self.clearing_rows = full_rows
        else:
            self._spawn_next()

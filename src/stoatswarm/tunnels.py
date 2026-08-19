"""Deterministic graph-first tunnel generation."""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import random
from collections import deque

Cell = tuple[int, int]
Edge = tuple[Cell, Cell]

_DIRECTIONS: tuple[Cell, ...] = ((0, 1), (1, 0), (0, -1), (-1, 0))


def _canonical_edge(a: Cell, b: Cell) -> Edge:
    return (a, b) if a <= b else (b, a)


def _named_rng(seed: int, name: str) -> random.Random:
    """Make stable independent RNG streams from one world seed."""
    payload = f"stoatswarm:v1:{seed}:{name}".encode()
    derived = int.from_bytes(hashlib.sha256(payload).digest()[:8], "big")
    return random.Random(derived)


@dataclass(frozen=True)
class TunnelConfig:
    """Parameters controlling the shape and physical scale of a tunnel."""

    grid_width: int = 25
    grid_height: int = 25
    target_cells: int = 60
    branch_probability: float = 0.22
    loop_probability: float = 0.08
    cell_size: float = 4.0
    tunnel_height: float = 2.5
    wall_thickness: float = 0.15

    def validate(self) -> None:
        if self.grid_width < 3 or self.grid_height < 3:
            raise ValueError("grid dimensions must both be at least 3")
        if not 2 <= self.target_cells <= self.grid_width * self.grid_height:
            raise ValueError("target_cells must fit within the grid and be at least 2")
        for name, value in (
            ("branch_probability", self.branch_probability),
            ("loop_probability", self.loop_probability),
        ):
            if not 0.0 <= value <= 1.0:
                raise ValueError(f"{name} must be between 0 and 1")
        if self.cell_size <= 0 or self.tunnel_height <= 0 or self.wall_thickness <= 0:
            raise ValueError("physical dimensions must be positive")
        if self.wall_thickness >= self.cell_size:
            raise ValueError("wall_thickness must be smaller than cell_size")


@dataclass(frozen=True)
class TunnelMap:
    """A generated tunnel graph embedded on a rectangular grid."""

    seed: int
    generator_version: int
    config: TunnelConfig
    cells: frozenset[Cell]
    edges: frozenset[Edge]
    entrance: Cell

    def neighbors(self, cell: Cell) -> tuple[Cell, ...]:
        result = []
        for a, b in self.edges:
            if a == cell:
                result.append(b)
            elif b == cell:
                result.append(a)
        return tuple(sorted(result))

    @property
    def exits(self) -> tuple[Cell, ...]:
        return tuple(sorted(cell for cell in self.cells if cell != self.entrance and len(self.neighbors(cell)) == 1))

    @property
    def junctions(self) -> tuple[Cell, ...]:
        return tuple(sorted(cell for cell in self.cells if len(self.neighbors(cell)) >= 3))

    def validate(self) -> None:
        if self.entrance not in self.cells:
            raise ValueError("entrance is not part of the tunnel")
        for a, b in self.edges:
            if a not in self.cells or b not in self.cells:
                raise ValueError("edge references a missing cell")
            if abs(a[0] - b[0]) + abs(a[1] - b[1]) != 1:
                raise ValueError("edges may only connect cardinally adjacent cells")

        visited = {self.entrance}
        queue = deque([self.entrance])
        while queue:
            for neighbor in self.neighbors(queue.popleft()):
                if neighbor not in visited:
                    visited.add(neighbor)
                    queue.append(neighbor)
        if visited != set(self.cells):
            raise ValueError("tunnel graph is disconnected")

    def to_ascii(self) -> str:
        """Render topology as a compact terminal preview."""
        min_x = min(x for x, _ in self.cells)
        max_x = max(x for x, _ in self.cells)
        min_y = min(y for _, y in self.cells)
        max_y = max(y for _, y in self.cells)
        width = (max_x - min_x) * 2 + 1
        height = (max_y - min_y) * 2 + 1
        canvas = [[" " for _ in range(width)] for _ in range(height)]

        def point(cell: Cell) -> tuple[int, int]:
            x, y = cell
            return (x - min_x) * 2, (max_y - y) * 2

        for cell in self.cells:
            x, y = point(cell)
            degree = len(self.neighbors(cell))
            canvas[y][x] = "S" if cell == self.entrance else ("+" if degree >= 3 else "E" if degree == 1 else ".")
        for a, b in self.edges:
            ax, ay = point(a)
            bx, by = point(b)
            canvas[(ay + by) // 2][(ax + bx) // 2] = "-" if ay == by else "|"
        return "\n".join("".join(row).rstrip() for row in canvas)


def _in_bounds(cell: Cell, config: TunnelConfig) -> bool:
    x, y = cell
    half_w = config.grid_width // 2
    half_h = config.grid_height // 2
    return -half_w <= x < config.grid_width - half_w and -half_h <= y < config.grid_height - half_h


def _unused_neighbors(cell: Cell, cells: set[Cell], config: TunnelConfig) -> list[Cell]:
    x, y = cell
    return [
        candidate
        for dx, dy in _DIRECTIONS
        if _in_bounds(candidate := (x + dx, y + dy), config) and candidate not in cells
    ]


def generate_tunnel(seed: int, config: TunnelConfig | None = None) -> TunnelMap:
    """Generate a connected tunnel, deterministically, from ``seed``.

    The layout starts as a randomized growing tree. Additional adjacent edges
    are opened afterward to create loops without compromising connectivity.
    """
    config = config or TunnelConfig()
    config.validate()
    layout_rng = _named_rng(seed, "layout")
    loop_rng = _named_rng(seed, "loops")

    entrance = (0, 0)
    cells = {entrance}
    edges: set[Edge] = set()
    active: list[Cell] = [entrance]

    while len(cells) < config.target_cells:
        expandable = [cell for cell in active if _unused_neighbors(cell, cells, config)]
        if not expandable:
            expandable = [cell for cell in cells if _unused_neighbors(cell, cells, config)]
        if not expandable:
            raise RuntimeError("unable to place requested tunnel cells")

        # Usually extend the newest tip for long corridors; sometimes select
        # an older cell to introduce a branch.
        if layout_rng.random() < config.branch_probability:
            parent = layout_rng.choice(expandable)
        else:
            expandable_set = set(expandable)
            parent = next(
                (cell for cell in reversed(active) if cell in expandable_set),
                layout_rng.choice(expandable),
            )
        child = layout_rng.choice(_unused_neighbors(parent, cells, config))
        cells.add(child)
        edges.add(_canonical_edge(parent, child))
        active.append(child)

        if not _unused_neighbors(parent, cells, config) and parent in active:
            active.remove(parent)

    possible_loops: list[Edge] = []
    for x, y in sorted(cells):
        for dx, dy in ((1, 0), (0, 1)):
            neighbor = (x + dx, y + dy)
            edge = _canonical_edge((x, y), neighbor)
            if neighbor in cells and edge not in edges:
                possible_loops.append(edge)
    loop_rng.shuffle(possible_loops)
    for edge in possible_loops:
        if loop_rng.random() < config.loop_probability:
            edges.add(edge)

    result = TunnelMap(
        seed=seed,
        generator_version=1,
        config=config,
        cells=frozenset(cells),
        edges=frozenset(edges),
        entrance=entrance,
    )
    result.validate()
    return result

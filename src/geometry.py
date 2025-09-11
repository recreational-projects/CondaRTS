from __future__ import annotations

import math
from typing import TypeAlias

from src.constants import TILE_SIZE

IntCoord: TypeAlias = tuple[int, int]
"""Integer point."""
FloatCoord: TypeAlias = tuple[float, float]
"""Float point."""


def grid_index(x: float, y: float) -> IntCoord:
    """Return the grid tile index coordinate containing the position."""
    return int(x // TILE_SIZE), int(y // TILE_SIZE)


def snap_to_grid(x: float, y: float) -> IntCoord:
    """Return the origin point of the grid tile containing the position."""
    index = grid_index(x, y)
    return index[0] * TILE_SIZE, index[1] * TILE_SIZE


def calculate_formation_positions(
    center: IntCoord, target: IntCoord | None, num_units: int, direction=None
) -> list[FloatCoord]:
    if num_units == 0:
        return []
    max_cols, max_rows = 5, 4
    spacing = 20
    positions = []
    if direction is None and target:
        dx, dy = target[0] - center[0], target[1] - center[1]
        angle = math.atan2(dy, dx) if dx != 0 or dy != 0 else 0
    else:
        angle = direction if direction is not None else 0
    cos_a, sin_a = math.cos(angle), math.sin(angle)
    for i in range(min(num_units, max_cols * max_rows)):
        row = i // max_cols
        col = i % max_cols
        offset_x = (col - (max_cols - 1) / 2) * spacing
        offset_y = (row - (max_rows - 1) / 2) * spacing
        rotated_x = offset_x * cos_a - offset_y * sin_a
        rotated_y = offset_x * sin_a + offset_y * cos_a
        positions.append((center[0] + rotated_x, center[1] + rotated_y))
    return positions

from __future__ import annotations

import math
from typing import TYPE_CHECKING

import pygame as pg

from src.constants import BUILDING_CONSTRUCTION_RANGE, TILE_SIZE

if TYPE_CHECKING:
    from collections.abc import Iterable

    from CondaRTS import Building, Team

type Coordinate = tuple[float, float]


def _is_within_building_range(
    *, position: Coordinate, team: Team, buildings: Iterable[Building]
) -> bool:
    """Return whether `position` is within construction range of team's building."""
    x, y = position
    return any(
        building.team == team
        and building.health > 0
        and (
            (x - building.rect.centerx) ** 2 + (y - building.rect.centery) ** 2
            <= BUILDING_CONSTRUCTION_RANGE**2
        )
        for building in buildings
    )


def _collides_with_building(
    *,
    position: Coordinate,
    new_building_cls: type[Building],
    buildings: Iterable[Building],
) -> bool:
    """Return whether pending building at `position` collides with existing building."""
    new_rect = pg.Rect(position, new_building_cls.SIZE)
    return any(
        building.health > 0 and new_rect.colliderect(building.rect)
        for building in buildings
    )


def is_valid_building_position(
    *,
    position: Coordinate,
    new_building_cls: type[Building],
    team: Team,
    buildings: Iterable[Building],
) -> bool:
    return _is_within_building_range(
        position=position,
        team=team,
        buildings=buildings,
    ) and not _collides_with_building(
        position=position,
        new_building_cls=new_building_cls,
        buildings=buildings,
    )


def snap_to_grid(position: Coordinate) -> Coordinate:
    """Return minimum (top left) point of tile containing `position`."""
    return position[0] // TILE_SIZE * TILE_SIZE, position[1] // TILE_SIZE * TILE_SIZE


def calculate_formation_positions(
    *,
    center: Coordinate,
    target: Coordinate | None,
    num_units: int,
    direction: float | None = None,
) -> list[Coordinate]:
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

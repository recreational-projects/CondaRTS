from __future__ import annotations

from typing import TYPE_CHECKING

import pygame as pg

from src.constants import BUILDING_CONSTRUCTION_RANGE, TILE_SIZE

if TYPE_CHECKING:
    from CondaRTS import Building


def _is_within_building_range(
    *, position: tuple[float, float], team, buildings
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
    position: tuple[float, float],
    new_building_cls: type[Building],
    buildings,
) -> bool:
    """Return whether pending building at `position` collides with existing building."""
    new_rect = pg.Rect(position, new_building_cls.SIZE)
    return any(
        building.health > 0 and new_rect.colliderect(building.rect)
        for building in buildings
    )


def is_valid_building_position(
    *,
    position: tuple[float, float],
    new_building_cls: type[Building],
    team,
    buildings,
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


def snap_to_grid(position: tuple[float, float]) -> tuple[float, float]:
    """Return minimum (top left) point of tile containing `position`."""
    return position[0] // TILE_SIZE * TILE_SIZE, position[1] // TILE_SIZE * TILE_SIZE

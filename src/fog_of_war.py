from __future__ import annotations

from dataclasses import dataclass
from dataclasses import field as dataclass_field
from typing import TYPE_CHECKING

import pygame as pg

if TYPE_CHECKING:
    from collections.abc import Iterable

    from CondaRTS import Team
    from src.building import Building
    from src.camera import Camera
    from src.game_object import GameObject
    from src.geometry import Coordinate


@dataclass(kw_only=True)
class FogOfWar:
    map_size: tuple[int, int]
    tile_size: int
    explored: list[list[bool]] = dataclass_field(default_factory=list)
    visible: list[list[bool]] = dataclass_field(default_factory=list)
    surface: pg.Surface = dataclass_field(init=False)

    def __post_init__(self) -> None:
        map_width, map_height = self.map_size
        self.explored = [
            [False] * (map_height // self.tile_size)
            for _ in range(map_width // self.tile_size)
        ]
        self.visible = [
            [False] * (map_height // self.tile_size)
            for _ in range(map_width // self.tile_size)
        ]
        self.surface = pg.Surface(self.map_size, pg.SRCALPHA)
        self.surface.fill((0, 0, 0, 255))

    def tile(self, position: Coordinate) -> tuple[int, int]:
        """Return tile."""
        x, y = position
        return int(x // self.tile_size), int(y // self.tile_size)

    def _reveal(self, center: Coordinate, radius: float) -> None:
        """Set tiles within `radius` of `center` as explored and visible."""
        cx, cy = center
        tile_x, tile_y = self.tile(center)
        radius_tiles = int(radius // self.tile_size)
        for y in range(
            max(0, tile_y - radius_tiles),
            min(len(self.explored[0]), tile_y + radius_tiles + 1),
        ):
            for x in range(
                max(0, tile_x - radius_tiles),
                min(len(self.explored), tile_x + radius_tiles + 1),
            ):
                if (
                    (cx - (x * self.tile_size + self.tile_size // 2)) ** 2
                    + (cy - (y * self.tile_size + self.tile_size // 2)) ** 2
                ) <= radius**2:
                    self.explored[x][y] = True
                    self.visible[x][y] = True

    def update_visibility(
        self, units: Iterable[GameObject], buildings: Iterable[Building], team: Team
    ) -> None:
        """Reveal tiles within range of `team`'s `unit`s and `buildings`."""
        self.visible = [
            [False] * len(self.explored[0]) for _ in range(len(self.explored))
        ]
        for unit in units:
            if unit.team == team:
                self._reveal(center=unit.rect.center, radius=150)

        for building in buildings:
            if building.team == team:
                self._reveal(center=building.rect.center, radius=200)

            if building.health > 0:
                tile_x, tile_y = self.tile(building.rect.center)
                if 0 <= tile_x < len(self.visible) and 0 <= tile_y < len(
                    self.visible[0]
                ):
                    self.visible[tile_x][tile_y] = True
                    # indirectly makes enemy buildings in tile visible

    def is_visible(self, position: Coordinate) -> bool:
        """Return whether `position` is in a visible tile."""
        tile_x, tile_y = self.tile(position)
        if 0 <= tile_x < len(self.visible) and 0 <= tile_y < len(self.visible[0]):
            return self.visible[tile_x][tile_y]

        return False

    def is_explored(self, position: Coordinate) -> bool:
        """Return whether `position` is in an explored tile."""
        tile_x, tile_y = self.tile(position)
        if 0 <= tile_x < len(self.explored) and 0 <= tile_y < len(self.explored[0]):
            return self.explored[tile_x][tile_y]

        return False

    def draw(self, surface_: pg.Surface, camera: Camera) -> None:
        """Draw opaque and semi-transparent fog tiles to `surface`.

        NB: drawn over buildings; under units.
        """
        for y in range(len(self.explored[0])):
            for x in range(len(self.explored)):
                if self.explored[x][y]:
                    alpha = 0 if self.visible[x][y] else 100
                    pg.draw.rect(
                        self.surface,
                        (0, 0, 0, alpha),
                        (
                            x * self.tile_size,
                            y * self.tile_size,
                            self.tile_size,
                            self.tile_size,
                        ),
                    )

        surface_.blit(self.surface, (-camera.rect.x, -camera.rect.y))

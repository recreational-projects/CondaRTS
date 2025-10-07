from __future__ import annotations

from dataclasses import dataclass
from dataclasses import field as dataclass_field
from typing import TYPE_CHECKING

import pygame as pg

from src.geometry import Coordinate

if TYPE_CHECKING:
    from collections.abc import Iterable

    from src.building import Building
    from src.camera import Camera
    from src.constants import Team
    from src.game_object import GameObject


@dataclass(kw_only=True)
class FogOfWar:
    map_size: tuple[int, int]
    tile_size: int
    explored: list[list[bool]] = dataclass_field(init=False, default_factory=list)
    visible: list[list[bool]] = dataclass_field(init=False, default_factory=list)
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

    def tile(self, position: pg.typing.SequenceLike) -> tuple[int, int]:
        """Return tile."""
        pos = Coordinate(position)
        return int(pos.x // self.tile_size), int(pos.y // self.tile_size)

    def _reveal(self, center: pg.typing.SequenceLike, radius: float) -> None:
        """Set tiles within `radius` of `center` as explored and visible."""
        center_pos = Coordinate(center)
        tile_x, tile_y = self.tile(center_pos)
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
                    (center_pos.x - (x * self.tile_size + self.tile_size // 2)) ** 2
                    + (center_pos.y - (y * self.tile_size + self.tile_size // 2)) ** 2
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
                self._reveal(center=unit.position, radius=150)

        for building in buildings:
            if building.team == team:
                self._reveal(center=building.position, radius=200)

            if building.health > 0:
                tile_x, tile_y = self.tile(building.position)
                if 0 <= tile_x < len(self.visible) and 0 <= tile_y < len(
                    self.visible[0]
                ):
                    self.visible[tile_x][tile_y] = True
                    # indirectly makes enemy buildings in tile visible

    def is_visible(self, position: pg.typing.SequenceLike) -> bool:
        """Return whether `position` is in a visible tile."""
        tile_x, tile_y = self.tile(position)
        if 0 <= tile_x < len(self.visible) and 0 <= tile_y < len(self.visible[0]):
            return self.visible[tile_x][tile_y]

        return False

    def is_explored(self, position: pg.typing.SequenceLike) -> bool:
        """Return whether `position` is in an explored tile."""
        tile_x, tile_y = self.tile(position)
        if 0 <= tile_x < len(self.explored) and 0 <= tile_y < len(self.explored[0]):
            return self.explored[tile_x][tile_y]

        return False

    def draw(self, *, surface: pg.Surface, camera: Camera) -> None:
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

        surface.blit(self.surface, (-camera.rect.x, -camera.rect.y))

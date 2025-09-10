from __future__ import annotations

import math
from typing import TYPE_CHECKING

import pygame

from src.constants import TILE_SIZE
from src.geometry import grid_index

if TYPE_CHECKING:
    from src.camera import Camera


class FogOfWar:
    def __init__(self, map_width: int, map_height: int, tile_size: int = TILE_SIZE) -> None:
        self.tile_size = tile_size
        self.explored = [[False] * (map_height // tile_size) for _ in range(map_width // tile_size)]
        self.visible = [[False] * (map_height // tile_size) for _ in range(map_width // tile_size)]
        self.surface = pygame.Surface((map_width, map_height), pygame.SRCALPHA)
        self.surface.fill((0, 0, 0, 255))

    def reveal(self, center: tuple[int, int], radius: int) -> None:
        tile_x, tile_y = grid_index(*center)
        cx, cy = center
        radius_tiles = radius // self.tile_size
        for y in range(
            max(0, tile_y - radius_tiles),
            min(len(self.explored[0]), tile_y + radius_tiles + 1),
        ):
            for x in range(max(0, tile_x - radius_tiles), min(len(self.explored), tile_x + radius_tiles + 1)):
                if (
                    math.sqrt(
                        (cx - (x * self.tile_size + self.tile_size // 2)) ** 2
                        + (cy - (y * self.tile_size + self.tile_size // 2)) ** 2
                    )
                    <= radius
                ):
                    self.explored[x][y] = True
                    self.visible[x][y] = True

    def update_visibility(self, units, buildings, team) -> None:
        self.visible = [[False] * len(self.explored[0]) for _ in range(len(self.explored))]
        for unit in units:
            if unit.team == team and hasattr(unit, "rect"):
                self.reveal(unit.rect.center, 150)
        for building in buildings:
            if building.team == team and hasattr(building, "rect"):
                self.reveal(building.rect.center, 200)
            if hasattr(building, "rect") and building.health > 0:
                tile_x, tile_y = (
                    int(building.rect.centerx // self.tile_size),
                    int(building.rect.centery // self.tile_size),
                )
                if 0 <= tile_x < len(self.visible) and 0 <= tile_y < len(self.visible[0]):
                    self.visible[tile_x][tile_y] = True
                    building.is_seen = True

    def is_tile_visible(self, x: int, y: int) -> bool:
        tile_x, tile_y = grid_index(x, y)
        if 0 <= tile_x < len(self.visible) and 0 <= tile_y < len(self.visible[0]):
            return self.visible[tile_x][tile_y]
        return False

    def is_tile_explored(self, x: int, y: int) -> bool:
        tile_x, tile_y = grid_index(x, y)
        if 0 <= tile_x < len(self.explored) and 0 <= tile_y < len(self.explored[0]):
            return self.explored[tile_x][tile_y]
        return False

    def draw(self, surface: pygame.Surface, camera: Camera) -> None:
        self.surface.fill((0, 0, 0, 255))
        for y in range(len(self.explored[0])):
            for x in range(len(self.explored)):
                if self.explored[x][y]:
                    alpha = 0 if self.visible[x][y] else 100
                    pygame.draw.rect(
                        self.surface,
                        (0, 0, 0, alpha),
                        (x * self.tile_size, y * self.tile_size, self.tile_size, self.tile_size),
                    )
        surface.blit(self.surface, (-camera.rect.x, -camera.rect.y))

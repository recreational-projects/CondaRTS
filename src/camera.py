from __future__ import annotations

from dataclasses import dataclass
from dataclasses import field as dataclass_field
from typing import TYPE_CHECKING

import pygame as pg

from src.constants import (
    CONSOLE_HEIGHT,
    MAP_HEIGHT,
    MAP_WIDTH,
    SCREEN_HEIGHT,
    SCREEN_WIDTH,
)

if TYPE_CHECKING:
    from src.geometry import Coordinate


@dataclass
class Camera:
    rect: pg.Rect = dataclass_field(init=False)

    def __post_init__(self) -> None:
        self.rect = pg.Rect(0, 0, SCREEN_WIDTH - 200, SCREEN_HEIGHT - CONSOLE_HEIGHT)

    def update(
        self, selected_units, mouse_pos: Coordinate, interface_rect: pg.Rect
    ) -> None:
        mx, my = mouse_pos
        if interface_rect.collidepoint(mx, my) or my > SCREEN_HEIGHT - CONSOLE_HEIGHT:
            return
        if selected_units:
            avg_x = sum(unit.rect.centerx for unit in selected_units) / len(
                selected_units
            )
            avg_y = sum(unit.rect.centery for unit in selected_units) / len(
                selected_units
            )
            self.rect.center = (
                max(
                    self.rect.width // 2,
                    min(MAP_WIDTH - self.rect.width // 2, int(avg_x)),
                ),
                max(
                    self.rect.height // 2,
                    min(MAP_HEIGHT - self.rect.height // 2, int(avg_y)),
                ),
            )
        else:
            if mx < 30 and self.rect.left > 0:
                self.rect.x -= 10
            elif mx > SCREEN_WIDTH - 230 and self.rect.right < MAP_WIDTH:
                self.rect.x += 10
            if my < 30 and self.rect.top > 0:
                self.rect.y -= 10
            elif (
                my > SCREEN_HEIGHT - CONSOLE_HEIGHT - 30
                and self.rect.bottom < MAP_HEIGHT
            ):
                self.rect.y += 10
        self.rect.clamp_ip(pg.Rect(0, 0, MAP_WIDTH, MAP_HEIGHT))

    def apply(self, rect: pg.Rect) -> pg.Rect:
        return pg.Rect(
            rect.x - self.rect.x, rect.y - self.rect.y, rect.width, rect.height
        )

    def screen_to_world(self, screen_pos: Coordinate) -> Coordinate:
        x, y = screen_pos
        map_area_y = int(min(y, SCREEN_HEIGHT - CONSOLE_HEIGHT))
        return (
            max(0, min(MAP_WIDTH, int(x) + self.rect.x)),
            max(0, min(MAP_HEIGHT, map_area_y + self.rect.y)),
        )

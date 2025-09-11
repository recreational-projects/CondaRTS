from __future__ import annotations

from typing import TYPE_CHECKING

import pygame

from src.constants import CONSOLE_HEIGHT, SCREEN_HEIGHT, SCREEN_WIDTH

if TYPE_CHECKING:
    from collections.abc import Sequence

    from src.game_object import GameObject
    from src.geometry import IntCoord


class Camera:
    def __init__(self, map_width: int, map_height: int) -> None:
        self.map_width = map_width
        self.map_height = map_height
        self.rect = pygame.Rect(0, 0, SCREEN_WIDTH - 200, SCREEN_HEIGHT - CONSOLE_HEIGHT)

    def update(self, selected_units: Sequence[GameObject], mouse_pos: IntCoord, interface_rect: pygame.Rect) -> None:
        mx, my = mouse_pos
        if interface_rect.collidepoint(mx, my) or my > SCREEN_HEIGHT - CONSOLE_HEIGHT:
            return

        if selected_units:
            avg_x = sum(unit.rect.centerx for unit in selected_units) / len(selected_units)
            avg_y = sum(unit.rect.centery for unit in selected_units) / len(selected_units)
            self.rect.center = (
                max(self.rect.width // 2, min(self.map_width - self.rect.width // 2, avg_x)),
                max(self.rect.height // 2, min(self.map_height - self.rect.height // 2, avg_y)),
            )
        else:
            if mx < 30 and self.rect.left > 0:
                self.rect.x -= 10
            elif mx > SCREEN_WIDTH - 230 and self.rect.right < self.map_width:
                self.rect.x += 10
            if my < 30 and self.rect.top > 0:
                self.rect.y -= 10
            elif my > SCREEN_HEIGHT - CONSOLE_HEIGHT - 30 and self.rect.bottom < self.map_height:
                self.rect.y += 10

        self.rect.clamp_ip(pygame.Rect(0, 0, self.map_width, self.map_height))

    def apply(self, rect: pygame.Rect) -> pygame.Rect:
        return pygame.Rect(rect.x - self.rect.x, rect.y - self.rect.y, rect.width, rect.height)

    def screen_to_world(self, screen_pos: IntCoord) -> IntCoord:
        x, y = screen_pos
        y = min(y, SCREEN_HEIGHT - CONSOLE_HEIGHT)
        return max(0, min(self.map_width, x + self.rect.x)), max(0, min(self.map_height, y + self.rect.y))

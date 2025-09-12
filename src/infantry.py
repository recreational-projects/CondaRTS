from __future__ import annotations

import math
from typing import TYPE_CHECKING

import pygame

from src.game_object import GameObject

if TYPE_CHECKING:
    from src.camera import Camera
    from src.geometry import IntCoord


class Infantry(GameObject):
    ATTACK_RANGE = 50
    ATTACK_COOLDOWN = 25
    cost = 100

    def __init__(self, position: IntCoord, team) -> None:
        super().__init__(position=position, team=team)
        self.image = pygame.Surface((16, 16), pygame.SRCALPHA)
        # Draw infantry as a simple soldier
        pygame.draw.circle(self.image, (150, 150, 150), (8, 4), 4)  # Head
        pygame.draw.rect(self.image, (100, 100, 100), (6, 8, 4, 8))  # Body
        pygame.draw.line(self.image, (80, 80, 80), (8, 16), (8, 20))  # Legs
        pygame.draw.line(self.image, (120, 120, 120), (10, 10), (14, 10))  # Gun
        self.rect = self.image.get_rect(center=position)
        self.speed = 3.5 if team == "GDI" else 4
        self.health = 100 if team == "GDI" else 60
        self.max_health = self.health
        self.attack_damage = 8
        self.power_usage = 5
        self.target_unit = None

    def update(self) -> None:
        super().update()
        if self.target_unit and hasattr(self.target_unit, "health") and self.target_unit.health > 0:
            dist = math.sqrt(
                (self.rect.centerx - self.target_unit.rect.centerx) ** 2
                + (self.rect.centery - self.target_unit.rect.centery) ** 2
            )
            self.target = (self.target_unit.rect.centerx, self.target_unit.rect.centery) if dist <= 200 else None
            self.target_unit = self.target_unit if self.target else None

    def draw(self, surface: pygame.Surface, camera: Camera) -> None:
        surface.blit(self.image, camera.apply(self.rect).topleft)
        if self.selected:
            pygame.draw.circle(surface, (255, 255, 255), camera.apply(self.rect).center, 10, 2)

        self.draw_health_bar(surface, camera)

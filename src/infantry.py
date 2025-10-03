from __future__ import annotations

import math
from typing import TYPE_CHECKING

import pygame as pg

from src.constants import Team
from src.game_object import GameObject

if TYPE_CHECKING:
    from src.camera import Camera


class Infantry(GameObject):
    COST = 100
    POWER_USAGE = 5

    def __init__(self, x: float, y: float, team: Team) -> None:
        super().__init__(x=x, y=y, team=team)
        self.image = pg.Surface((16, 16), pg.SRCALPHA)
        self.rect = self.image.get_rect(center=(x, y))
        self.speed = 3.5 if team == Team.GDI else 4
        self.health = 100 if team == Team.GDI else 60
        self.max_health = self.health
        self.attack_range = 50
        self.attack_damage = 8
        self.attack_cooldown = 25

        # Draw infantry as a simple soldier
        pg.draw.circle(self.image, (150, 150, 150), (8, 4), 4)  # Head
        pg.draw.rect(self.image, (100, 100, 100), (6, 8, 4, 8))  # Body
        pg.draw.line(self.image, (80, 80, 80), (8, 16), (8, 20))  # Legs
        pg.draw.line(self.image, (120, 120, 120), (10, 10), (14, 10))  # Gun

    def update(self) -> None:
        super().update()
        if self.target_unit and self.target_unit.health > 0:
            dist = math.sqrt(
                (self.rect.centerx - self.target_unit.rect.centerx) ** 2
                + (self.rect.centery - self.target_unit.rect.centery) ** 2
            )
            self.target = (
                (self.target_unit.rect.centerx, self.target_unit.rect.centery)
                if dist <= 200
                else None
            )
            self.target_unit = self.target_unit if self.target else None

    def draw(self, screen: pg.Surface, camera: Camera) -> None:
        screen.blit(self.image, camera.apply(self.rect).topleft)
        if self.selected:
            pg.draw.circle(
                screen, (255, 255, 255), camera.apply(self.rect).center, 10, 2
            )
        self.draw_health_bar(screen, camera)

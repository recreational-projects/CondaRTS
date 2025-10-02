from __future__ import annotations

import math
from typing import TYPE_CHECKING

import pygame as pg

from src.constants import Team
from src.game_object import GameObject

if TYPE_CHECKING:
    from src.camera import Camera


class Tank(GameObject):
    COST = 500
    POWER_USAGE = 15

    def __init__(self, x: float, y: float, team: Team) -> None:
        super().__init__(x=x, y=y, team=team)
        self.base_image = pg.Surface((30, 20), pg.SRCALPHA)
        # Draw tank body (front facing east/right)
        pg.draw.rect(self.base_image, (100, 100, 100), (0, 0, 30, 20))  # Hull
        pg.draw.rect(self.base_image, (80, 80, 80), (2, 2, 26, 16))  # Inner hull
        pg.draw.rect(self.base_image, (50, 50, 50), (0, -2, 30, 4))  # Tracks top
        pg.draw.rect(self.base_image, (50, 50, 50), (0, 18, 30, 4))  # Tracks bottom
        self.barrel_image = pg.Surface((20, 4), pg.SRCALPHA)
        pg.draw.rect(
            self.barrel_image, (70, 70, 70), (0, 0, 20, 4)
        )  # Barrel (extends right)
        self.image = self.base_image
        self.rect = self.image.get_rect(center=(x, y))
        self.speed = 2.5 if team == Team.GDI else 3
        self.health = 200 if team == Team.GDI else 120
        self.max_health = self.health
        self.attack_range = 200
        self.attack_damage = 20 if team == Team.GDI else 15
        self.attack_cooldown = 50
        self.angle: float = 0
        self.recoil = 0

    def update(self) -> None:
        super().update()
        if self.target_unit and self.target_unit.health > 0:
            dist = math.sqrt(
                (self.rect.centerx - self.target_unit.rect.centerx) ** 2
                + (self.rect.centery - self.target_unit.rect.centery) ** 2
            )
            self.target = (
                (self.target_unit.rect.centerx, self.target_unit.rect.centery)
                if dist <= 250
                else None
            )
            self.target_unit = self.target_unit if self.target else None
        if self.target:
            dx, dy = (
                self.target[0] - self.rect.centerx,
                self.target[1] - self.rect.centery,
            )
            self.angle = math.degrees(
                math.atan2(dy, dx)
            )  # Use dy instead of -dy to fix vertical direction
            self.image = pg.Surface((40, 40), pg.SRCALPHA)
            # Rotate base image to face target (base image faces east, so -angle aligns it correctly)
            rotated_base = pg.transform.rotate(self.base_image, -self.angle)
            self.image.blit(rotated_base, rotated_base.get_rect(center=(20, 20)))
            # Handle barrel with recoil
            barrel_length = 20 - self.recoil * 2
            barrel_image = pg.Surface((barrel_length, 4), pg.SRCALPHA)
            pg.draw.rect(barrel_image, (70, 70, 70), (0, 0, barrel_length, 4))
            # Rotate barrel to match target direction
            rotated_barrel = pg.transform.rotate(
                barrel_image, -self.angle
            )  # Barrel also faces east initially
            self.image.blit(rotated_barrel, rotated_barrel.get_rect(center=(20, 20)))
            if self.recoil > 0:
                self.recoil -= 1

    def draw(self, screen: pg.Surface, camera: Camera) -> None:
        screen.blit(self.image, camera.apply(self.rect).topleft)
        if self.selected:
            pg.draw.circle(
                screen,
                (255, 255, 255),
                camera.apply(self.rect).center,
                self.rect.width // 2 + 2,
                2,
            )  # Circular selection

        self.draw_health_bar(screen, camera)

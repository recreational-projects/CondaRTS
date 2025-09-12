from __future__ import annotations

import math
from typing import TYPE_CHECKING

import pygame

from src.game_object import GameObject

if TYPE_CHECKING:
    from src.camera import Camera
    from src.geometry import IntCoord


class Tank(GameObject):
    ATTACK_RANGE = 200
    ATTACK_COOLDOWN = 50
    cost = 500

    def __init__(self, position: IntCoord, team) -> None:
        super().__init__(position=position, team=team)
        self.base_image = pygame.Surface((30, 20), pygame.SRCALPHA)
        # Draw tank body (front facing east/right)
        pygame.draw.rect(self.base_image, (100, 100, 100), (0, 0, 30, 20))  # Hull
        pygame.draw.rect(self.base_image, (80, 80, 80), (2, 2, 26, 16))  # Inner hull
        pygame.draw.rect(self.base_image, (50, 50, 50), (0, -2, 30, 4))  # Tracks top
        pygame.draw.rect(self.base_image, (50, 50, 50), (0, 18, 30, 4))  # Tracks bottom
        self.barrel_image = pygame.Surface((20, 4), pygame.SRCALPHA)
        pygame.draw.rect(self.barrel_image, (70, 70, 70), (0, 0, 20, 4))  # Barrel (extends right)
        self.image = self.base_image
        self.rect = self.image.get_rect(center=position)
        self.speed = 2.5 if team == "GDI" else 3
        self.health = 200 if team == "GDI" else 120
        self.max_health = self.health
        self.attack_damage = 20 if team == "GDI" else 15
        self.angle: float = 0
        self.recoil = 0
        self.power_usage = 15
        self.target_unit = None

    def update(self) -> None:
        super().update()
        if self.target_unit and hasattr(self.target_unit, "health") and self.target_unit.health > 0:
            dist = math.sqrt(
                (self.rect.centerx - self.target_unit.rect.centerx) ** 2
                + (self.rect.centery - self.target_unit.rect.centery) ** 2
            )
            self.target = self.target_unit.rect.center if dist <= 250 else None
            self.target_unit = self.target_unit if self.target else None

        if self.target:
            dx, dy = (self.target[0] - self.rect.centerx, self.target[1] - self.rect.centery)
            self.angle = math.degrees(math.atan2(dy, dx))  # Use dy instead of -dy to fix vertical direction
            self.image = pygame.Surface((40, 40), pygame.SRCALPHA)
            # Rotate base image to face target (base image faces east, so -angle aligns it correctly)
            rotated_base = pygame.transform.rotate(self.base_image, -self.angle)
            self.image.blit(rotated_base, rotated_base.get_rect(center=(20, 20)))
            # Handle barrel with recoil
            barrel_length = 20 - self.recoil * 2
            barrel_image = pygame.Surface((barrel_length, 4), pygame.SRCALPHA)
            pygame.draw.rect(barrel_image, (70, 70, 70), (0, 0, barrel_length, 4))
            # Rotate barrel to match target direction
            rotated_barrel = pygame.transform.rotate(barrel_image, -self.angle)  # Barrel also faces east initially
            self.image.blit(rotated_barrel, rotated_barrel.get_rect(center=(20, 20)))
            if self.recoil > 0:
                self.recoil -= 1

    def draw(self, surface: pygame.Surface, camera: Camera) -> None:
        surface.blit(self.image, camera.apply(self.rect).topleft)
        if self.selected:
            pygame.draw.circle(
                surface, (255, 255, 255), camera.apply(self.rect).center, self.rect.width // 2 + 2, 2
            )  # Circular selection

        self.draw_health_bar(surface, camera)

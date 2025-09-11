from __future__ import annotations

from typing import TYPE_CHECKING

import pygame

from src.game_object import GameObject
from src.particle import Particle

if TYPE_CHECKING:
    from src.camera import Camera
    from src.geometry import IntCoord


class Building(GameObject):
    SIZE = (60, 60)  # overridden for some subclasses
    CONSTRUCTION_TIME = 50
    POWER_USAGE = 0  # overridden for some subclasses

    def __init__(self, position: IntCoord, team, color, health, cost) -> None:
        super().__init__(position=position, team=team)
        self.image = pygame.Surface(self.SIZE, pygame.SRCALPHA)
        # Add details to building
        pygame.draw.rect(self.image, color, ((0, 0), self.SIZE))  # Base
        # Clamp color values to prevent negative values
        inner_color = (max(0, color[0] - 50), max(0, color[1] - 50), max(0, color[2] - 50))
        pygame.draw.rect(self.image, inner_color, (5, 5, self.SIZE[0] - 10, self.SIZE[1] - 10))  # Inner
        for i in range(10, self.SIZE[0] - 10, 20):
            pygame.draw.rect(self.image, (200, 200, 200), (i, 10, 10, 10))  # Windows

        self.rect = self.image.get_rect(topleft=position)
        self.health = health
        self.max_health = health
        self.cost = cost
        self.construction_progress = 0
        self.is_seen = False

    def update(self, particles: pygame.sprite.Group) -> None:
        if self.construction_progress < self.CONSTRUCTION_TIME:
            self.construction_progress += 1
            self.image.set_alpha(int(255 * self.construction_progress / self.CONSTRUCTION_TIME))

        super().update()
        if self.health <= 0:
            particles.add(Particle.building_explosion(self.rect.center))
            self.kill()

    def draw(self, surface: pygame.Surface, camera: Camera) -> None:
        surface.blit(self.image, camera.apply(self.rect).topleft)
        self.draw_health_bar(surface, camera)

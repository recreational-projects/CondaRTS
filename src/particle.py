from __future__ import annotations

import math
import random
from typing import Self

import pygame


class Particle(pygame.sprite.Sprite):
    def __init__(self, *, x: float, y: float, vx: float, vy: float, size: int, color, lifetime: int) -> None:
        super().__init__()
        self.image: pygame.Surface = pygame.Surface((size, size), pygame.SRCALPHA)
        pygame.draw.circle(self.image, color, (size // 2, size // 2), size // 2)
        self.rect: pygame.Rect = self.image.get_rect(center=(x, y))
        self.vx, self.vy = vx, vy
        self.initial_lifetime = lifetime
        self.lifetime = self.initial_lifetime
        self.alpha = 255

    @classmethod
    def projectile_trail(cls, x: float, y: float, angle: float) -> Self:
        """Return a single particle."""
        return cls(
            x=x,
            y=y,
            vx=-math.cos(angle) * random.uniform(0.5, 1.5),
            vy=-math.sin(angle) * random.uniform(0.5, 1.5),
            size=5,
            color=(255, 255, 150),
            lifetime=15,
        )

    @classmethod
    def smoke_cloud(cls, x: float, y: float) -> set[Self]:
        """Return a cloud of particles."""
        return {
            cls(
                x=x,
                y=y,
                vx=random.uniform(-1.5, 1.5),
                vy=random.uniform(-1.5, 1.5),
                size=random.randint(6, 10),
                color=(100, 100, 100),
                lifetime=20,
            )
            for _ in range(5)
        }

    @classmethod
    def damage_cloud_small(cls, x: float, y: float) -> set[Self]:
        """Return a small cloud of particles."""
        return {
            cls(
                x=x,
                y=y,
                vx=random.uniform(-1, 1),
                vy=random.uniform(-1, 1),
                size=4,
                color=(255, 200, 100),
                lifetime=10,
            )
            for _ in range(3)
        }

    @classmethod
    def damage_cloud_large(cls, x: float, y: float) -> set[Self]:
        """Return a cloud of particles."""
        return {
            cls(
                x=x,
                y=y,
                vx=random.uniform(-2, 2),
                vy=random.uniform(-2, 2),
                size=6,
                color=(255, 200, 100),
                lifetime=15,
            )
            for _ in range(5)
        }

    @classmethod
    def building_explosion(cls, x: float, y: float) -> set[Self]:
        """Return a cloud of particles."""
        return {
            cls(
                x=x,
                y=y,
                vx=random.uniform(-3, 3),
                vy=random.uniform(-3, 3),
                size=random.randint(6, 12),
                color=(200, 100, 100),
                lifetime=30,
            )
            for _ in range(15)
        }

    @classmethod
    def projectile_explosion(cls, x, y: float) -> set[Self]:
        """Return a cloud of particles."""
        return {
            cls(
                x=x,
                y=y,
                vx=random.uniform(-2, 2),
                vy=random.uniform(-2, 2),
                size=6,
                color=(255, 100, 0),
                lifetime=15,
            )
            for _ in range(5)
        }

    def update(self) -> None:
        self.rect.x += self.vx
        self.rect.y += self.vy
        self.lifetime -= 1
        if self.lifetime <= 0:
            self.kill()
        else:
            self.alpha = int(255 * self.lifetime / self.initial_lifetime)
            self.image.set_alpha(self.alpha)

    def draw(self, *, surface: pygame.Surface, camera) -> None:
        surface.blit(self.image, camera.apply(self.rect).topleft)

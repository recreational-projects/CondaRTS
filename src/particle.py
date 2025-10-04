from __future__ import annotations

from typing import TYPE_CHECKING

import pygame as pg

if TYPE_CHECKING:
    from src.camera import Camera


class Particle(pg.sprite.Sprite):
    def __init__(
        self,
        x: float,
        y: float,
        vx: float,
        vy: float,
        size: int,
        color: pg.Color,
        lifetime: int,
    ) -> None:
        super().__init__()
        self.image: pg.Surface = pg.Surface((size, size), pg.SRCALPHA)
        pg.draw.circle(self.image, color, (size // 2, size // 2), size // 2)
        self.rect: pg.Rect = self.image.get_rect(center=(x, y))
        self.vx, self.vy = vx, vy
        self.lifetime = lifetime
        self.alpha = 255
        self.initial_lifetime = lifetime

    def update(self) -> None:
        self.rect.x += self.vx
        self.rect.y += self.vy
        self.lifetime -= 1
        if self.lifetime <= 0:
            self.kill()
        else:
            self.alpha = int(255 * self.lifetime / self.initial_lifetime)
            self.image.set_alpha(self.alpha)

    def draw(self, *, surface: pg.Surface, camera: Camera) -> None:
        surface.blit(self.image, camera.apply(self.rect).topleft)

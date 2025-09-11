from __future__ import annotations

from typing import TYPE_CHECKING

import pygame

if TYPE_CHECKING:
    from src.camera import Camera


class IronField(pygame.sprite.Sprite):
    def __init__(self, x, y, *, font: pygame.Font, resources=5000) -> None:
        super().__init__()
        self.image = pygame.Surface((40, 40), pygame.SRCALPHA)
        pygame.draw.polygon(
            self.image,
            (0, 200, 0),
            [(0, 20), (20, 0), (40, 20), (20, 40)],
        )  # Diamond shape for crystal
        self.rect = self.image.get_rect(topleft=(x, y))
        self.resources = resources
        self.font = font
        self.regen_timer = 500

    def update(self) -> None:
        if self.regen_timer > 0:
            self.regen_timer -= 1
        else:
            self.resources = min(5000, self.resources + 15)
            self.regen_timer = 500
        self.image.set_alpha(int(255 * self.resources / 5000))

    def draw(self, surface: pygame.Surface, camera: Camera) -> None:
        surface.blit(self.image, camera.apply(self.rect).topleft)
        surface.blit(
            self.font.render(text=f"{self.resources}", antialias=True, color=(255, 255, 255)),
            (camera.apply(self.rect).x, camera.apply(self.rect).y - 20),
        )

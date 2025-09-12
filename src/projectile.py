from __future__ import annotations

import math
from typing import TYPE_CHECKING

import pygame

from src.particle import Particle

if TYPE_CHECKING:
    from src.camera import Camera
    from src.geometry import IntCoord


class Projectile(pygame.sprite.Sprite):
    def __init__(self, *, position: IntCoord, target, damage, team) -> None:
        super().__init__()
        self.image = pygame.Surface((10, 5), pygame.SRCALPHA)
        pygame.draw.ellipse(self.image, (255, 200, 0), (0, 0, 10, 5))  # Brighter projectile
        self.rect = self.image.get_rect(center=position)
        self.target = target
        self.speed = 6
        self.damage = damage
        self.team = team
        self.particle_timer = 2

    def update(self, particles: pygame.sprite.Group) -> None:
        if self.target and hasattr(self.target, "health") and self.target.health > 0:
            dx, dy = (self.target.rect.centerx - self.rect.centerx, self.target.rect.centery - self.rect.centery)
            dist = math.sqrt(dx**2 + dy**2)
            if dist > 3:
                angle = math.atan2(dy, dx)
                self.image = pygame.transform.rotate(pygame.Surface((10, 5), pygame.SRCALPHA), -math.degrees(angle))
                pygame.draw.ellipse(self.image, (255, 200, 0), (0, 0, 10, 5))
                self.rect = self.image.get_rect(center=self.rect.center)
                self.rect.x += self.speed * math.cos(angle)
                self.rect.y += self.speed * math.sin(angle)
                if self.particle_timer <= 0:
                    particles.add(Particle.projectile_trail(position=self.rect.center, angle=angle))
                    self.particle_timer = 2

                else:
                    self.particle_timer -= 1

            else:
                self.kill()
                for _ in range(5):
                    particles.add(Particle.projectile_explosion(self.rect.center))

        else:
            self.kill()

    def draw(self, surface: pygame.Surface, camera: Camera) -> None:
        surface.blit(self.image, camera.apply(self.rect).topleft)

from __future__ import annotations

import math
from typing import TYPE_CHECKING, Literal

import pygame

from src.constants import MAP_HEIGHT, MAP_WIDTH

if TYPE_CHECKING:
    from src.camera import Camera


class GameObject(pygame.sprite.Sprite):
    def __init__(self, *, x: int, y: int, team: Literal["GDI", "NOD"]) -> None:
        super().__init__()
        self.rect: pygame.Rect = pygame.Rect((x, y), (0, 0))  # Nominal, overridden
        self.team = team
        self.target = None
        self.formation_target = None
        self.speed = 0
        self.health = 0
        self.max_health = 0
        self.attack_range = 0
        self.attack_damage = 0
        self.attack_cooldown = 0
        self.cooldown_timer = 0
        self.selected = False
        self.power_usage = 0
        self.under_attack = False
        self.target_unit = None

    def move_toward(self) -> None:
        if (
            self.target
            # and hasattr(self, 'target_unit')
            and self.target_unit
            # and hasattr(self.target_unit, 'health')
            and self.target_unit.health > 0
        ):
            dx, dy = (
                self.target[0] - self.rect.centerx,
                self.target[1] - self.rect.centery,
            )
            dist = math.sqrt(dx**2 + dy**2)
            if dist > self.attack_range:
                if dist > 5:
                    self.rect.x += self.speed * dx / dist
                    self.rect.y += self.speed * dy / dist
                self.rect.clamp_ip(pygame.Rect(0, 0, MAP_WIDTH, MAP_HEIGHT))
            else:
                self.target = None
        elif self.formation_target:
            dx, dy = (
                self.formation_target[0] - self.rect.centerx,
                self.formation_target[1] - self.rect.centery,
            )
            dist = math.sqrt(dx**2 + dy**2)
            if dist > 5:
                self.rect.x += self.speed * dx / dist
                self.rect.y += self.speed * dy / dist
            self.rect.clamp_ip(pygame.Rect(0, 0, MAP_WIDTH, MAP_HEIGHT))
        elif self.target:
            dx, dy = (
                self.target[0] - self.rect.centerx,
                self.target[1] - self.rect.centery,
            )
            dist = math.sqrt(dx**2 + dy**2)
            if dist > 5:
                self.rect.x += self.speed * dx / dist
                self.rect.y += self.speed * dy / dist
            self.rect.clamp_ip(pygame.Rect(0, 0, MAP_WIDTH, MAP_HEIGHT))

    def update(self) -> None:
        self.move_toward()
        if self.cooldown_timer > 0:
            self.cooldown_timer -= 1

    def draw_health_bar(self, surface: pygame.Surface, camera: Camera) -> None:
        health_ratio = self.health / self.max_health
        if not self.under_attack and health_ratio == 1.0:
            return
        color = (0, 255, 0) if health_ratio > 0.5 else (255, 0, 0)
        bar_width = max(10, self.rect.width * health_ratio)
        screen_rect = camera.apply(self.rect)
        pygame.draw.rect(
            surface,
            (0, 0, 0),
            (screen_rect.x - 1, screen_rect.y - 16, self.rect.width + 2, 10),
        )  # Background
        pygame.draw.rect(surface, color, (screen_rect.x, screen_rect.y - 15, bar_width, 8))
        pygame.draw.rect(surface, (255, 255, 255), (screen_rect.x, screen_rect.y - 15, self.rect.width, 8), 1)  # Border

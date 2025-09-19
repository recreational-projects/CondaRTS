from __future__ import annotations

import math
from typing import TYPE_CHECKING

import pygame as pg

from src.constants import MAP_HEIGHT, MAP_WIDTH

if TYPE_CHECKING:
    from CondaRTS import Team
    from src.camera import Camera
    from src.geometry import Coordinate


class GameObject(pg.sprite.Sprite):
    COST = 0

    def __init__(self, x: float, y: float, team: Team) -> None:
        super().__init__()
        self.rect: pg.Rect = pg.Rect((x, y), (0, 0))  # Nominal, overridden
        self.image: pg.Surface = pg.Surface((x, y))
        self.team = team
        self.target: Coordinate | None = None
        self.target_unit: GameObject | None = None
        self.formation_target: Coordinate | None = None
        self.speed: float = 0
        self.health = 0
        self.max_health = 0
        self.attack_range = 0
        self.attack_damage = 0
        self.attack_cooldown = 0
        self.cooldown_timer = 0
        self.selected = False
        self.under_attack = False

    def move_toward(self) -> None:
        if (
            self.target
            and hasattr(self, "target_unit")
            and self.target_unit
            and hasattr(self.target_unit, "health")
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
                self.rect.clamp_ip(pg.Rect(0, 0, MAP_WIDTH, MAP_HEIGHT))
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
            self.rect.clamp_ip(pg.Rect(0, 0, MAP_WIDTH, MAP_HEIGHT))
        elif self.target:
            dx, dy = (
                self.target[0] - self.rect.centerx,
                self.target[1] - self.rect.centery,
            )
            dist = math.sqrt(dx**2 + dy**2)
            if dist > 5:
                self.rect.x += self.speed * dx / dist
                self.rect.y += self.speed * dy / dist
            self.rect.clamp_ip(pg.Rect(0, 0, MAP_WIDTH, MAP_HEIGHT))

    def update(self) -> None:
        self.move_toward()
        if self.cooldown_timer > 0:
            self.cooldown_timer -= 1

    def draw_health_bar(self, screen: pg.Surface, camera: Camera) -> None:
        health_ratio = self.health / self.max_health
        if not self.under_attack and health_ratio == 1.0:
            return
        color = (0, 255, 0) if health_ratio > 0.5 else (255, 0, 0)
        bar_width = max(10, int(self.rect.width * health_ratio))
        screen_rect = camera.apply(self.rect)
        pg.draw.rect(
            screen,
            (0, 0, 0),
            (screen_rect.x - 1, screen_rect.y - 16, self.rect.width + 2, 10),
        )  # Background
        pg.draw.rect(screen, color, (screen_rect.x, screen_rect.y - 15, bar_width, 8))
        pg.draw.rect(
            screen,
            (255, 255, 255),
            (screen_rect.x, screen_rect.y - 15, self.rect.width, 8),
            1,
        )  # Border

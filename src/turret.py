from __future__ import annotations

import math
import random
from typing import TYPE_CHECKING

import pygame as pg

from src.building import Building
from src.constants import Team
from src.particle import Particle
from src.projectile import Projectile

if TYPE_CHECKING:
    from collections.abc import Iterable

    from src.game_object import GameObject


class Turret(Building):
    COST = 600
    POWER_USAGE = 25
    SIZE = 50, 50

    def __init__(self, x: float, y: float, team: Team) -> None:
        super().__init__(
            x,
            y,
            team,
            (180, 180, 0) if team == Team.GDI else (180, 0, 0),
            500,
        )
        self.attack_range = 180
        self.attack_damage = 15
        self.attack_cooldown = 25
        self.cooldown_timer = 0
        self.target_unit = None
        self.angle: float = 0

    def update(
        self,
        particles: pg.sprite.Group[Particle],
        projectiles: pg.sprite.Group[Projectile],
        enemy_units: Iterable[GameObject],
        *args,
        **kwargs,
    ) -> None:
        super().update(*args, particles, **kwargs)
        if self.cooldown_timer > 0:
            self.cooldown_timer -= 1
        if self.cooldown_timer == 0:
            closest_target, min_dist = None, float("inf")
            for u in enemy_units:
                if u.health > 0:
                    dist = math.sqrt(
                        (self.rect.centerx - u.rect.centerx) ** 2
                        + (self.rect.centery - u.rect.centery) ** 2
                    )
                    if dist < self.attack_range and dist < min_dist:
                        closest_target, min_dist = u, dist

            if closest_target:
                self.target_unit = closest_target
                dx, dy = (
                    closest_target.rect.centerx - self.rect.centerx,
                    closest_target.rect.centery - self.rect.centery,
                )
                self.angle = math.degrees(math.atan2(-dy, dx))
                projectiles.add(
                    Projectile(
                        self.rect.centerx,
                        self.rect.centery,
                        closest_target,
                        self.attack_damage,
                        self.team,
                    )
                )
                self.cooldown_timer = self.attack_cooldown
                for _ in range(5):
                    particles.add(
                        Particle(
                            self.rect.centerx,
                            self.rect.centery,
                            random.uniform(-1.5, 1.5),
                            random.uniform(-1.5, 1.5),
                            random.randint(6, 10),
                            (100, 100, 100),
                            20,
                        )
                    )
            else:
                self.target_unit = None

        self.image = pg.Surface((50, 50), pg.SRCALPHA)
        base = pg.Surface((40, 40), pg.SRCALPHA)
        base.fill((180, 180, 0) if self.team == Team.GDI else (180, 0, 0))
        barrel = pg.Surface((25, 6), pg.SRCALPHA)
        pg.draw.line(barrel, (80, 80, 80), (0, 3), (18, 3), 4)
        rotated_barrel = pg.transform.rotate(barrel, self.angle)
        self.image.blit(base, (5, 5))
        self.image.blit(rotated_barrel, rotated_barrel.get_rect(center=(25, 25)))
        self.image.set_alpha(
            int(255 * self.construction_progress / self.CONSTRUCTION_TIME)
        )

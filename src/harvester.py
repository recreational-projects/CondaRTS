from __future__ import annotations

import math
from typing import TYPE_CHECKING

import pygame as pg

from src.game_object import GameObject
from src.infantry import Infantry

if TYPE_CHECKING:
    from collections.abc import Iterable

    from CondaRTS import Headquarters
    from src.camera import Camera
    from src.constants import Team
    from src.iron_field import IronField


class Harvester(GameObject):
    COST = 800
    POWER_USAGE = 20

    def __init__(self, x: float, y: float, team: Team, hq: Headquarters) -> None:
        super().__init__(x=x, y=y, team=team)
        self.image = pg.Surface((50, 30), pg.SRCALPHA)
        self.rect = self.image.get_rect(center=(x, y))
        self.speed = 2.5
        self.health = 300
        self.max_health = self.health
        self.capacity = 100
        self.iron = 0
        self.hq = hq
        self.state = "moving_to_field"
        self.target_field: IronField | None = None
        self.harvest_time = 40
        self.attack_range = 50
        self.attack_damage = 10
        self.attack_cooldown = 30

        # Draw harvester as a truck
        pg.draw.rect(self.image, (120, 120, 120), (0, 0, 50, 30))  # Body
        pg.draw.rect(self.image, (100, 100, 100), (5, 5, 40, 20))  # Cargo area
        pg.draw.circle(self.image, (50, 50, 50), (10, 30), 5)  # Wheel 1
        pg.draw.circle(self.image, (50, 50, 50), (40, 30), 5)  # Wheel 2

    def update(
        self, *, enemy_units: Iterable[GameObject], iron_fields: Iterable[IronField]
    ) -> None:
        super().update()
        if self.cooldown_timer == 0:
            closest_target, min_dist = None, float("inf")
            for target in enemy_units:
                if target.health > 0 and isinstance(target, Infantry):
                    dist = math.sqrt(
                        (self.rect.centerx - target.rect.centerx) ** 2
                        + (self.rect.centery - target.rect.centery) ** 2
                    )
                    if dist < self.attack_range and dist < min_dist:
                        closest_target, min_dist = target, dist

            if closest_target:
                closest_target.health -= self.attack_damage
                if closest_target.health <= 0:
                    closest_target.kill()
                self.cooldown_timer = self.attack_cooldown

        if self.state == "moving_to_field":
            if not self.target_field or self.target_field.resources <= 0:
                rich_fields = [f for f in iron_fields if f.resources >= 1000]
                if rich_fields:
                    self.target_field = min(
                        rich_fields,
                        key=lambda f: math.sqrt(
                            (self.rect.centerx - f.rect.centerx) ** 2
                            + (self.rect.centery - f.rect.centery) ** 2
                        ),
                    )
                else:
                    self.target_field = min(
                        iron_fields,
                        key=lambda f: math.sqrt(
                            (self.rect.centerx - f.rect.centerx) ** 2
                            + (self.rect.centery - f.rect.centery) ** 2
                        ),
                        default=None,
                    )
            if self.target_field:
                self.target = self.target_field.rect.center
                if (
                    math.sqrt(
                        (self.rect.centerx - self.target[0]) ** 2
                        + (self.rect.centery - self.target[1]) ** 2
                    )
                    < 30
                ):
                    self.state = "harvesting"
                    self.target = None
                    self.harvest_time = 40

        elif self.state == "harvesting":
            if self.harvest_time > 0:
                self.harvest_time -= 1
            else:
                if not self.target_field:
                    raise TypeError("No target field")
                    # Temporary handling, review later

                harvested = min(self.target_field.resources, self.capacity)
                self.iron += harvested
                self.target_field.resources -= harvested
                self.state = "returning"
                self.target = self.hq.rect.center

        elif self.state == "returning":
            if not self.target:
                raise TypeError("No target field")  # Temporary handling, review later

            if (
                math.sqrt(
                    (self.rect.centerx - self.target[0]) ** 2
                    + (self.rect.centery - self.target[1]) ** 2
                )
                < 30
            ):
                self.hq.iron += self.iron
                self.iron = 0
                self.state = "moving_to_field"
                self.target = None

    def draw(self, surface: pg.Surface, camera: Camera, font: pg.Font) -> None:
        surface.blit(self.image, camera.apply(self.rect).topleft)
        if self.selected:
            pg.draw.rect(surface, (255, 255, 255), camera.apply(self.rect), 2)

        self.draw_health_bar(surface, camera)
        if self.iron > 0:
            surface.blit(
                font.render(f"Iron: {self.iron}", True, (255, 255, 255)),
                (camera.apply(self.rect).x, camera.apply(self.rect).y - 35),
            )

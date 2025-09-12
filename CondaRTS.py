from __future__ import annotations

import math
import random
from typing import Any, Iterable, Mapping, TypeAlias

import pygame

from src.camera import Camera
from src.constants import CONSOLE_HEIGHT, MAP_HEIGHT, MAP_WIDTH, SCREEN_HEIGHT, SCREEN_WIDTH, TILE_SIZE
from src.fog_of_war import FogOfWar
from src.game_console import GameConsole
from src.game_object import GameObject
from src.geometry import FloatCoord, IntCoord, calculate_formation_positions, snap_to_grid
from src.iron_field import IronField
from src.particle import Particle

BUILDING_RANGE = 160
BASE_PRODUCTION_TIME = 180
POWER_PER_PLANT = 100
GDI_COLOR = (200, 150, 0)  # Brighter yellow for GDI
NOD_COLOR = (200, 0, 0)  # Brighter red for NOD
VALID_PLACEMENT_COLOR = (0, 255, 0)
INVALID_PLACEMENT_COLOR = (255, 0, 0)

SpriteGroup: TypeAlias = pygame.sprite.Group[Any]


def _is_in_building_range(*, x, y, team) -> bool:
    live_friendly_buildings = {b for b in global_buildings if b.team == team and b.health > 0}
    for b in live_friendly_buildings:
        if math.sqrt((x - b.rect.centerx) ** 2 + (y - b.rect.centery) ** 2) <= BUILDING_RANGE:
            return True
    return False


def _collides_with_building(*, x, y, cls: type[Building]) -> bool:
    live_buildings = {b for b in global_buildings if b.health > 0}
    new_rect = pygame.Rect((x, y), cls.SIZE)
    for b in live_buildings:
        if new_rect.colliderect(b.rect):
            return True
    return False


def is_valid_building_position(x, y, *, team, cls: type[Building]) -> bool:
    return _is_in_building_range(x=x, y=y, team=team) and not _collides_with_building(x=x, y=y, cls=cls)


def handle_collisions(units) -> None:
    for unit in units:
        for other in units:
            if unit != other and unit.rect.colliderect(other.rect):
                dx, dy = (
                    unit.rect.centerx - other.rect.centerx,
                    unit.rect.centery - other.rect.centery,
                )
                dist = math.sqrt(dx**2 + dy**2)
                if dist > 0:
                    push = 0.3 if isinstance(unit, Harvester) and isinstance(other, Harvester) else 0.5
                    unit.rect.x += push * dx / dist
                    unit.rect.y += push * dy / dist
                    other.rect.x -= push * dx / dist
                    other.rect.y -= push * dy / dist


def handle_attacks(units, all_units, buildings, projectiles, particles) -> None:
    for unit in units:
        if isinstance(unit, (Tank, Infantry)) and unit.cooldown_timer == 0:
            closest_target, min_dist = None, float("inf")
            if unit.target_unit and hasattr(unit.target_unit, "health") and unit.target_unit.health > 0:
                dist = math.sqrt(
                    (unit.rect.centerx - unit.target_unit.rect.centerx) ** 2
                    + (unit.rect.centery - unit.target_unit.rect.centery) ** 2
                )
                if dist <= unit.attack_range:
                    closest_target, min_dist = unit.target_unit, dist
            if not closest_target:
                for target in all_units:
                    if target.team != unit.team and target.health > 0:
                        dist = math.sqrt(
                            (unit.rect.centerx - target.rect.centerx) ** 2
                            + (unit.rect.centery - target.rect.centery) ** 2
                        )
                        if dist <= unit.attack_range and dist < min_dist:
                            closest_target, min_dist = target, dist
                for building in buildings:
                    if building.team != unit.team and building.health > 0:
                        dist = math.sqrt(
                            (unit.rect.centerx - building.rect.centerx) ** 2
                            + (unit.rect.centery - building.rect.centery) ** 2
                        )
                        if dist <= unit.attack_range and dist < min_dist:
                            closest_target, min_dist = building, dist
            if closest_target:
                unit.target_unit = closest_target
                unit.target = closest_target.rect.center
                if isinstance(unit, Tank):
                    dx, dy = (
                        closest_target.rect.centerx - unit.rect.centerx,
                        closest_target.rect.centery - unit.rect.centery,
                    )
                    unit.angle = math.degrees(math.atan2(dy, dx))  # Updated to match Tank's angle calculation
                    projectiles.add(
                        Projectile(unit.rect.centerx, unit.rect.centery, closest_target, unit.attack_damage, unit.team)
                    )
                    unit.recoil = 5
                    barrel_angle = math.radians(unit.angle)
                    particles.add(
                        Particle.smoke_cloud(
                            unit.rect.centerx + math.cos(barrel_angle) * (unit.rect.width // 2 + 12),
                            unit.rect.centery + math.sin(barrel_angle) * (unit.rect.width // 2 + 12),
                        )
                    )
                else:
                    closest_target.health -= unit.attack_damage
                    closest_target.under_attack = True  # Set under_attack only when damage is applied
                    particles.add(Particle.damage_cloud_small(unit.rect.centerx, unit.rect.centery))
                    if closest_target.health <= 0:
                        closest_target.kill()
                        unit.target = unit.target_unit = None
                unit.cooldown_timer = unit.attack_cooldown


def handle_projectiles(projectiles, all_units, buildings) -> None:
    for projectile in projectiles:
        hit = False
        # Check collision with all units and buildings, not just the target
        for target in all_units:
            if target.team != projectile.team and target.health > 0 and projectile.rect.colliderect(target.rect):
                target.health -= projectile.damage
                target.under_attack = True  # Set under_attack when damage is applied
                particles.add(Particle.damage_cloud_large(projectile.rect.centerx, projectile.rect.centery))
                if target.health <= 0:
                    target.kill()
                hit = True
                break
        if not hit:
            for target in buildings:
                if target.team != projectile.team and target.health > 0 and projectile.rect.colliderect(target.rect):
                    target.health -= projectile.damage
                    target.under_attack = True  # Set under_attack when damage is applied
                    particles.add(Particle.damage_cloud_large(projectile.rect.centerx, projectile.rect.centery))
                    if target.health <= 0:
                        target.kill()
                    hit = True
                    break
        if hit:
            projectile.kill()
        # Only kill projectile if it has no valid target or moves too far
        elif not (projectile.target and hasattr(projectile.target, "health") and projectile.target.health > 0):
            projectile.kill()


class Tank(GameObject):
    cost = 500

    def __init__(self, x, y, team) -> None:
        super().__init__(x=x, y=y, team=team)
        self.base_image = pygame.Surface((30, 20), pygame.SRCALPHA)
        # Draw tank body (front facing east/right)
        pygame.draw.rect(self.base_image, (100, 100, 100), (0, 0, 30, 20))  # Hull
        pygame.draw.rect(self.base_image, (80, 80, 80), (2, 2, 26, 16))  # Inner hull
        pygame.draw.rect(self.base_image, (50, 50, 50), (0, -2, 30, 4))  # Tracks top
        pygame.draw.rect(self.base_image, (50, 50, 50), (0, 18, 30, 4))  # Tracks bottom
        self.barrel_image = pygame.Surface((20, 4), pygame.SRCALPHA)
        pygame.draw.rect(self.barrel_image, (70, 70, 70), (0, 0, 20, 4))  # Barrel (extends right)
        self.image = self.base_image
        self.rect = self.image.get_rect(center=(x, y))
        self.speed = 2.5 if team == "GDI" else 3
        self.health = 200 if team == "GDI" else 120
        self.max_health = self.health
        self.attack_range = 200
        self.attack_damage = 20 if team == "GDI" else 15
        self.attack_cooldown = 50
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
            self.target = (self.target_unit.rect.centerx, self.target_unit.rect.centery) if dist <= 250 else None
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


class Infantry(GameObject):
    cost = 100

    def __init__(self, x, y, team) -> None:
        super().__init__(x=x, y=y, team=team)
        self.image = pygame.Surface((16, 16), pygame.SRCALPHA)
        # Draw infantry as a simple soldier
        pygame.draw.circle(self.image, (150, 150, 150), (8, 4), 4)  # Head
        pygame.draw.rect(self.image, (100, 100, 100), (6, 8, 4, 8))  # Body
        pygame.draw.line(self.image, (80, 80, 80), (8, 16), (8, 20))  # Legs
        pygame.draw.line(self.image, (120, 120, 120), (10, 10), (14, 10))  # Gun
        self.rect = self.image.get_rect(center=(x, y))
        self.speed = 3.5 if team == "GDI" else 4
        self.health = 100 if team == "GDI" else 60
        self.max_health = self.health
        self.attack_range = 50
        self.attack_damage = 8
        self.attack_cooldown = 25
        self.power_usage = 5
        self.target_unit = None

    def update(self) -> None:
        super().update()
        if self.target_unit and hasattr(self.target_unit, "health") and self.target_unit.health > 0:
            dist = math.sqrt(
                (self.rect.centerx - self.target_unit.rect.centerx) ** 2
                + (self.rect.centery - self.target_unit.rect.centery) ** 2
            )
            self.target = (self.target_unit.rect.centerx, self.target_unit.rect.centery) if dist <= 200 else None
            self.target_unit = self.target_unit if self.target else None

    def draw(self, surface: pygame.Surface, camera: Camera) -> None:
        surface.blit(self.image, camera.apply(self.rect).topleft)
        if self.selected:
            pygame.draw.circle(surface, (255, 255, 255), camera.apply(self.rect).center, 10, 2)
        self.draw_health_bar(surface, camera)


class Harvester(GameObject):
    cost = 800

    def __init__(self, x, y, team, headquarters) -> None:
        super().__init__(x=x, y=y, team=team)
        self.image = pygame.Surface((50, 30), pygame.SRCALPHA)
        # Draw harvester as a truck
        pygame.draw.rect(self.image, (120, 120, 120), (0, 0, 50, 30))  # Body
        pygame.draw.rect(self.image, (100, 100, 100), (5, 5, 40, 20))  # Cargo area
        pygame.draw.circle(self.image, (50, 50, 50), (10, 30), 5)  # Wheel 1
        pygame.draw.circle(self.image, (50, 50, 50), (40, 30), 5)  # Wheel 2
        self.rect = self.image.get_rect(center=(x, y))
        self.speed = 2.5
        self.health = 300
        self.max_health = self.health
        self.capacity = 100
        self.iron = 0
        self.headquarters = headquarters
        self.state = "moving_to_field"
        self.target_field = None
        self.harvest_time = 40
        self.power_usage = 20
        self.attack_range = 50
        self.attack_damage = 10
        self.attack_cooldown = 30
        self.target_unit = None

    def update(self) -> None:
        super().update()
        if self.cooldown_timer == 0:
            closest_target, min_dist = None, float("inf")
            _units = {u for u in global_units}
            live_enemy_infantry = {
                u for u in _units if all((u.team != self.team, u.health > 0, isinstance(u, Infantry)))
            }
            for u in live_enemy_infantry:
                dist = math.sqrt((self.rect.centerx - u.rect.centerx) ** 2 + (self.rect.centery - u.rect.centery) ** 2)
                if dist < self.attack_range and dist < min_dist:
                    closest_target, min_dist = u, dist
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
                            (self.rect.centerx - f.rect.centerx) ** 2 + (self.rect.centery - f.rect.centery) ** 2
                        ),
                    )
                else:
                    self.target_field = min(
                        iron_fields,
                        key=lambda f: math.sqrt(
                            (self.rect.centerx - f.rect.centerx) ** 2 + (self.rect.centery - f.rect.centery) ** 2
                        ),
                        default=None,
                    )
            if self.target_field:
                self.target = self.target_field.rect.center
                if (
                    math.sqrt((self.rect.centerx - self.target[0]) ** 2 + (self.rect.centery - self.target[1]) ** 2)
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
                    raise TypeError("No target field")  # Temporary handling, review later

                harvested = min(self.target_field.resources, self.capacity)
                self.iron += harvested
                self.target_field.resources -= harvested
                self.state = "returning"
                self.target = self.headquarters.rect.center
        elif self.state == "returning":
            if not self.target:
                raise TypeError("No target")  # Temporary handling, review later

            if math.sqrt((self.rect.centerx - self.target[0]) ** 2 + (self.rect.centery - self.target[1]) ** 2) < 30:
                self.headquarters.iron += self.iron
                self.iron = 0
                self.state = "moving_to_field"
                self.target = None

    def draw(self, surface: pygame.Surface, camera: Camera) -> None:
        surface.blit(self.image, camera.apply(self.rect).topleft)
        if self.selected:
            pygame.draw.rect(surface, (255, 255, 255), camera.apply(self.rect), 2)
        self.draw_health_bar(surface, camera)
        if self.iron > 0:
            surface.blit(
                font.render(f"Iron: {self.iron}", True, (255, 255, 255)),
                (camera.apply(self.rect).x, camera.apply(self.rect).y - 35),
            )


class Building(GameObject):
    SIZE = (60, 60)  # overridden for some subclasses
    CONSTRUCTION_TIME = 50
    POWER_USAGE = 0  # overridden for some subclasses

    def __init__(self, x, y, team, color, health, cost) -> None:
        super().__init__(x=x, y=y, team=team)
        self.image = pygame.Surface(self.SIZE, pygame.SRCALPHA)
        # Add details to building
        pygame.draw.rect(self.image, color, ((0, 0), self.SIZE))  # Base
        # Clamp color values to prevent negative values
        inner_color = (max(0, color[0] - 50), max(0, color[1] - 50), max(0, color[2] - 50))
        pygame.draw.rect(self.image, inner_color, (5, 5, self.SIZE[0] - 10, self.SIZE[1] - 10))  # Inner
        for i in range(10, self.SIZE[0] - 10, 20):
            pygame.draw.rect(self.image, (200, 200, 200), (i, 10, 10, 10))  # Windows

        self.rect = self.image.get_rect(topleft=(x, y))
        self.health = health
        self.max_health = health
        self.cost = cost
        self.construction_progress = 0
        self.is_seen = False

    def update(self) -> None:
        if self.construction_progress < self.CONSTRUCTION_TIME:
            self.construction_progress += 1
            self.image.set_alpha(int(255 * self.construction_progress / self.CONSTRUCTION_TIME))

        super().update()
        if self.health <= 0:
            particles.add(Particle.building_explosion(self.rect.centerx, self.rect.centery))
            self.kill()

    def draw(self, surface: pygame.Surface, camera: Camera) -> None:
        surface.blit(self.image, camera.apply(self.rect).topleft)
        self.draw_health_bar(surface, camera)


class Headquarters(Building):
    SIZE = (80, 80)
    cost = 2000

    def __init__(self, x, y, team) -> None:
        super().__init__(x, y, team, GDI_COLOR if team == "GDI" else NOD_COLOR, 1200, self.cost)
        self.iron = 1500
        self.production_queue: list[type] = []
        self.production_timer: float = 0
        self.base_power = 300
        self.pending_building: GameObject | None = None
        self.pending_building_pos = FloatCoord | None
        self.has_enough_power = True
        self.power_output = 0

    def get_production_time(self, unit_class) -> float:
        _buildings = {b for b in global_buildings}
        live_friendly_buildings = {b for b in _buildings if b.team == self.team and b.health > 0}
        base_time = BASE_PRODUCTION_TIME
        if unit_class == Infantry:
            barracks_count = len({b for b in live_friendly_buildings if isinstance(b, Barracks)})
            return base_time * (0.9**barracks_count)
        elif unit_class in [Tank, Harvester]:
            warfactory_count = len({b for b in live_friendly_buildings if isinstance(b, WarFactory)})
            return base_time * (0.9**warfactory_count)
        return base_time

    def update(self) -> None:
        _buildings = {b for b in global_buildings}
        friendly_buildings = {b for b in _buildings if b.team == self.team}
        live_friendly_buildings = {b for b in friendly_buildings if b.health > 0}

        _units = {u for u in global_units}
        friendly_units = {u for u in _units if u.team == self.team}

        self.power_usage = sum(u.power_usage for u in friendly_units) + sum(b.power_usage for b in friendly_buildings)
        self.power_output = self.base_power + sum(
            POWER_PER_PLANT for b in friendly_buildings if isinstance(b, PowerPlant)
        )
        self.has_enough_power = self.power_output >= self.power_usage
        if self.production_queue and not self.production_timer and self.has_enough_power:
            self.production_timer = self.get_production_time(self.production_queue[0])
        if self.production_queue:
            if self.has_enough_power:
                self.production_timer -= 1
            else:
                self.production_timer -= 0.5
            if self.production_timer <= 0:
                unit_class = self.production_queue.pop(0)
                if unit_class in [
                    Headquarters,
                    Barracks,
                    WarFactory,
                    PowerPlant,
                    Turret,
                ]:
                    self.pending_building = unit_class
                    self.pending_building_pos = None
                else:
                    spawn_building = self
                    if unit_class == Infantry:
                        barracks = {b for b in live_friendly_buildings if isinstance(b, Barracks)}
                        if not barracks:
                            return
                        spawn_building = min(
                            barracks,
                            key=lambda b: math.sqrt(
                                (b.rect.centerx - self.rect.centerx) ** 2 + (b.rect.centery - self.rect.centery) ** 2
                            ),
                        )
                    elif unit_class in [Tank, Harvester]:
                        warfactories = {b for b in live_friendly_buildings if isinstance(b, WarFactory)}
                        if not warfactories:
                            return
                        spawn_building = min(
                            warfactories,
                            key=lambda b: math.sqrt(
                                (b.rect.centerx - self.rect.centerx) ** 2 + (b.rect.centery - self.rect.centery) ** 2
                            ),
                        )
                    spawn_x, spawn_y = (
                        spawn_building.rect.right + 20,
                        spawn_building.rect.centery,
                    )
                    new_units = [
                        unit_class(spawn_x, spawn_y, self.team, self)
                        if unit_class == Harvester
                        else unit_class(spawn_x, spawn_y, self.team)
                    ]
                    formation_positions = calculate_formation_positions(
                        (spawn_x, spawn_y), None, len(new_units), direction=0
                    )
                    for unit, pos in zip(new_units, formation_positions):
                        unit.rect.center = pos
                        unit.formation_target = pos
                        (player_units if self.team == "GDI" else ai_units).add(unit)
                        global_units.add(unit)
                self.production_timer = (
                    self.get_production_time(self.production_queue[0])
                    if self.production_queue and self.has_enough_power
                    else 0
                )
        super().update()

    def place_building(self, x, y, *, cls: type[Building]) -> None:
        x, y = snap_to_grid(x, y)
        if is_valid_building_position(x, y, team=self.team, cls=cls):
            global_buildings.add(cls(x, y, self.team))
            self.pending_building = None
            self.pending_building_pos = None
            if self.production_queue and self.has_enough_power:
                self.production_timer = self.get_production_time(self.production_queue[0])

    def draw(self, surface: pygame.Surface, camera: Camera) -> None:
        surface.blit(self.image, camera.apply(self.rect).topleft)
        self.draw_health_bar(surface, camera)


class Barracks(Building):
    POWER_USAGE = 25
    cost = 500

    def __init__(self, x, y, team) -> None:
        super().__init__(x, y, team, (150, 150, 0) if team == "GDI" else (150, 0, 0), 600, self.cost)


class WarFactory(Building):
    POWER_USAGE = 35
    cost = 1000

    def __init__(self, x, y, team) -> None:
        super().__init__(x, y, team, (170, 170, 0) if team == "GDI" else (170, 0, 0), 800, self.cost)


class PowerPlant(Building):
    cost = 300

    def __init__(self, x, y, team) -> None:
        super().__init__(x, y, team, (130, 130, 0) if team == "GDI" else (130, 0, 0), 500, self.cost)


class Turret(Building):
    SIZE = (50, 50)
    POWER_USAGE = 25
    cost = 600

    def __init__(self, x, y, team) -> None:
        super().__init__(x, y, team, (180, 180, 0) if team == "GDI" else (180, 0, 0), 500, self.cost)
        self.attack_range = 180
        self.attack_damage = 15
        self.attack_cooldown = 25
        self.cooldown_timer = 0
        self.target_unit = None
        self.angle: float = 0

    def update(self) -> None:
        _units = {u for u in global_units}
        live_enemy_units = {u for u in _units if u.team != self.team and u.health > 0}
        super().update()
        if self.cooldown_timer > 0:
            self.cooldown_timer -= 1
        if self.cooldown_timer == 0:
            closest_target, min_dist = None, float("inf")
            for u in live_enemy_units:
                dist = math.sqrt((self.rect.centerx - u.rect.centerx) ** 2 + (self.rect.centery - u.rect.centery) ** 2)
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
                    Projectile(self.rect.centerx, self.rect.centery, closest_target, self.attack_damage, self.team)
                )
                self.cooldown_timer = self.attack_cooldown
                particles.add(Particle.smoke_cloud(self.rect.centerx, self.rect.centery))
            else:
                self.target_unit = None
        self.image = pygame.Surface(self.SIZE, pygame.SRCALPHA)
        base = pygame.Surface((40, 40), pygame.SRCALPHA)
        base.fill((180, 180, 0) if self.team == "GDI" else (180, 0, 0))
        barrel = pygame.Surface((25, 6), pygame.SRCALPHA)
        pygame.draw.line(barrel, (80, 80, 80), (0, 3), (18, 3), 4)
        rotated_barrel = pygame.transform.rotate(barrel, self.angle)
        self.image.blit(base, (5, 5))
        self.image.blit(rotated_barrel, rotated_barrel.get_rect(center=(25, 25)))
        self.image.set_alpha(int(255 * self.construction_progress / Building.CONSTRUCTION_TIME))


class Projectile(pygame.sprite.Sprite):
    def __init__(self, x, y, target, damage, team) -> None:
        super().__init__()
        self.image = pygame.Surface((10, 5), pygame.SRCALPHA)
        pygame.draw.ellipse(self.image, (255, 200, 0), (0, 0, 10, 5))  # Brighter projectile
        self.rect = self.image.get_rect(center=(x, y))
        self.target = target
        self.speed = 6
        self.damage = damage
        self.team = team
        self.particle_timer = 2

    def update(self) -> None:
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
                    particles.add(Particle.projectile_trail(x=self.rect.centerx, y=self.rect.centery, angle=angle))
                    self.particle_timer = 2
                else:
                    self.particle_timer -= 1
            else:
                self.kill()
                for _ in range(5):
                    particles.add(Particle.projectile_explosion(self.rect.centerx, self.rect.centery))
        else:
            self.kill()

    def draw(self, surface: pygame.Surface, camera: Camera) -> None:
        surface.blit(self.image, camera.apply(self.rect).topleft)


class ProductionInterface:
    def __init__(self, headquarters) -> None:
        self.headquarters = headquarters
        self.panel_rect = pygame.Rect(SCREEN_WIDTH - 200, 0, 200, SCREEN_HEIGHT - CONSOLE_HEIGHT)
        self.current_tab = "Units"
        self.tab_buttons = [
            (pygame.Rect(SCREEN_WIDTH - 180, 10 + i * 40, 160, 30), tab)
            for i, tab in enumerate(["Units", "Buildings", "Defensive"])
        ]
        buildings = {b for b in global_buildings}
        self.buttons = {
            "Units": [
                (
                    pygame.Rect(SCREEN_WIDTH - 180, 130 + i * 50, 160, 40),
                    cls,
                    lambda t, cls=cls: cls.cost,
                    lambda: req,
                )
                for i, (cls, req) in enumerate(
                    [
                        (
                            Tank,
                            lambda: any(
                                b.team == self.headquarters.team and isinstance(b, WarFactory) and b.health > 0
                                for b in buildings
                            ),
                        ),
                        (
                            Infantry,
                            lambda: any(
                                b.team == self.headquarters.team and isinstance(b, Barracks) and b.health > 0
                                for b in buildings
                            ),
                        ),
                        (
                            Harvester,
                            lambda: any(
                                b.team == self.headquarters.team and isinstance(b, WarFactory) and b.health > 0
                                for b in buildings
                            ),
                        ),
                    ]
                )
            ],
            "Buildings": [
                (
                    pygame.Rect(SCREEN_WIDTH - 180, 130 + i * 50, 160, 40),
                    cls,
                    lambda t, cls=cls: cls.cost,
                    lambda: True,
                )
                for i, cls in enumerate([Barracks, WarFactory, PowerPlant, Headquarters])
            ],
            "Defensive": [
                (
                    pygame.Rect(SCREEN_WIDTH - 180, 130, 160, 40),
                    Turret,
                    lambda t, cls=Turret: cls.cost,
                    lambda: True,
                ),
                (
                    pygame.Rect(SCREEN_WIDTH - 180, 180, 160, 40),
                    None,
                    lambda t: 0,
                    lambda: True,
                ),
            ],
        }
        self.button_labels = {
            Tank: "Tank",
            Infantry: "Infantry",
            Harvester: "Harvester",
            Barracks: "Barracks",
            WarFactory: "War Factory",
            PowerPlant: "Power Plant",
            Headquarters: "Headquarters",
            Turret: "Turret",
            None: "Sell",
        }

    def draw(self, surface: pygame.Surface, iron: int) -> None:
        pygame.draw.rect(surface, (60, 60, 60), self.panel_rect)  # Darker panel
        pygame.draw.rect(surface, (100, 100, 100), self.panel_rect, 2)  # Border
        surface.blit(
            font.render(
                f"Power: {self.headquarters.power_output}/{self.headquarters.power_usage}",
                True,
                (0, 255, 0) if self.headquarters.has_enough_power else (255, 0, 0),
            ),
            (SCREEN_WIDTH - 180, 10),
        )
        for rect, tab_name in self.tab_buttons:
            pygame.draw.rect(
                surface, (0, 200, 200) if tab_name == self.current_tab else (50, 50, 50), rect, border_radius=5
            )
            surface.blit(font.render(tab_name, True, (255, 255, 255)), (rect.x + 10, rect.y + 10))
        for rect, unit_class, cost_fn, req_fn in self.buttons[self.current_tab]:
            cost = cost_fn(self.headquarters.team) if unit_class else 0
            can_produce = iron >= cost and req_fn()
            color = (
                (0, 200, 0)
                if (unit_class and can_produce) or (unit_class is None and selected_building)
                else (200, 0, 0)
            )
            pygame.draw.rect(surface, color, rect, border_radius=5)
            surface.blit(
                font.render(f"{self.button_labels[unit_class]} ({cost if unit_class else ''})", True, (255, 255, 255)),
                (rect.x + 10, rect.y + 10),
            )
        for i, unit_class in enumerate(self.headquarters.production_queue[:5]):
            surface.blit(
                font.render(f"{unit_class.__name__} ({unit_class.cost})", True, (255, 255, 255)),
                (SCREEN_WIDTH - 180, 350 + i * 25),
            )
        if self.headquarters.production_timer > 0:
            progress = 1 - self.headquarters.production_timer / self.headquarters.get_production_time(
                self.headquarters.production_queue[0] if self.headquarters.production_queue else Headquarters
            )
            pygame.draw.rect(surface, (0, 255, 0), (SCREEN_WIDTH - 180, 340, int(160 * progress), 10))
            pygame.draw.rect(surface, (255, 255, 255), (SCREEN_WIDTH - 180, 340, 160, 10), 1)
        if self.headquarters.pending_building:
            mouse_pos = pygame.mouse.get_pos()
            world_pos = snap_to_grid(*camera.screen_to_world(mouse_pos))
            building_size = self.headquarters.pending_building.SIZE
            temp_surface = pygame.Surface(building_size, pygame.SRCALPHA)
            temp_surface.fill(GDI_COLOR if self.headquarters.team == "GDI" else NOD_COLOR)
            temp_surface.set_alpha(100)
            valid = is_valid_building_position(
                world_pos[0], world_pos[1], team=self.headquarters.team, cls=self.headquarters.pending_building
            )
            pygame.draw.rect(
                temp_surface,
                VALID_PLACEMENT_COLOR if valid else INVALID_PLACEMENT_COLOR,
                ((0, 0), building_size),
                3,
            )
            surface.blit(
                temp_surface,
                (mouse_pos[0] - building_size[0] // 2, mouse_pos[1] - building_size[1] // 2),
            )

    def handle_click(self, pos: IntCoord, iron: int) -> bool:
        global selected_building
        for rect, tab_name in self.tab_buttons:
            if rect.collidepoint(pos):
                self.current_tab = tab_name
                return True
        if len(self.headquarters.production_queue) >= 5:
            return False
        for rect, unit_class, cost_fn, req_fn in self.buttons[self.current_tab]:
            if rect.collidepoint(pos):
                if unit_class is None and selected_building and selected_building.team == self.headquarters.team:
                    self.headquarters.iron += selected_building.cost // 2
                    selected_building.kill()
                    selected_building = None
                    return True
                cost = cost_fn(self.headquarters.team)
                if unit_class and iron >= cost and req_fn():
                    self.headquarters.production_queue.append(unit_class)
                    self.headquarters.iron -= cost
                    if not self.headquarters.production_timer:
                        self.production_timer = self.headquarters.get_production_time(unit_class)
                    return True
        return False


class AI:
    SCOUT_INTERVAL = 200
    ACTION_INTERVAL = 50
    MAX_WAVE_SIZE = 25
    SCALE_FACTOR = 1.8

    def __init__(
        self,
        *,
        headquarters: Headquarters,
        ai_units: Iterable[GameObject],
        all_units: Iterable[GameObject],
        iron_fields: Iterable[IronField],
        buildings: Iterable[Building],
    ) -> None:
        self.headquarters = headquarters
        self.ai_units = ai_units
        self.all_units = all_units
        self.iron_fields = iron_fields
        self.buildings = buildings
        self.timer = 0
        self.wave_timer = 0
        self.wave_interval = random.randint(150, 250)
        self.wave_number = 0
        self.target_ratio = {"Harvester": 4, "Infantry": 6, "Tank": 3, "Turret": 3}
        self.state: str = "BUILD_UP"
        self.defense_cooldown = 0
        self.scout_targets: list[FloatCoord] = []
        self.iron_income_rate: float = 0
        self.last_scout_update = 0
        self.surprise_attack_cooldown = 0

    @property
    def ai_buildings(self) -> set[Building]:
        return {b for b in self.buildings if b.team == "NOD"}

    @property
    def player_units(self) -> set[GameObject]:
        return {u for u in self.all_units if u.team == "GDI"}

    @property
    def player_buildings(self) -> set[Building]:
        return {b for b in self.buildings if b.team == "GDI"}

    def _evaluate_player(self) -> dict[str, int]:
        return {
            "base_size": len(self.player_units) + len(self.player_buildings),
            "harvesters": len({u for u in self.player_units if isinstance(u, Harvester)}),
            "tanks": len({u for u in self.player_units if isinstance(u, Tank)}),
            "infantry": len({u for u in self.player_units if isinstance(u, Infantry)}),
            "turrets": len({b for b in self.player_units if isinstance(b, Turret)}),
        }

    def _evaluate_state(self, *, player_base_size: int) -> str:
        self.iron_income_rate = (
            sum(h.iron for h in self.ai_units if isinstance(h, Harvester))
            / max(1, len([h for h in self.ai_units if isinstance(h, Harvester)]))
            * 60
            / 40
        )
        if self.headquarters.iron < 300 or self.iron_income_rate < 50:
            return "BROKE"
        elif self.headquarters.health < self.headquarters.max_health * 0.6 or self.defense_cooldown > 0:
            return "ATTACKED"
        elif any(
            u.team == "GDI"
            and math.sqrt(
                (u.rect.centerx - self.headquarters.rect.centerx) ** 2
                + (u.rect.centery - self.headquarters.rect.centery) ** 2
            )
            < 500
            for u in self.all_units
        ):
            return "THREATENED"
        elif self.wave_number >= 2 or player_base_size > 8:
            return "AGGRESSIVE"

        return "BUILD UP"

    def update_scouting(self) -> None:
        if self.last_scout_update <= 0:
            if not self.scout_targets:
                self.scout_targets = [(f.rect.centerx, f.rect.centery) for f in self.iron_fields] + [
                    (MAP_WIDTH // 2, MAP_HEIGHT // 2)
                ]
                gdi_hq = next((b for b in self.player_buildings if isinstance(b, Headquarters)), None)
                if gdi_hq:
                    self.scout_targets.append(gdi_hq.rect.center)
            for scout in [u for u in self.ai_units if isinstance(u, Infantry) and not u.target][:3]:
                if self.scout_targets:
                    scout.target = self.scout_targets.pop(0)
                    scout.target_unit = None
            self.last_scout_update = AI.SCOUT_INTERVAL
        else:
            self.last_scout_update -= 1

    def prioritize_targets(self, unit: GameObject | None) -> GameObject | None:
        if not unit:
            raise TypeError("No unit")

        targets = []
        for target in self.all_units:
            if target.team != unit.team and target.health > 0:
                dist = math.sqrt(
                    (unit.rect.centerx - target.rect.centerx) ** 2 + (unit.rect.centery - target.rect.centery) ** 2
                )
                priority = (
                    3
                    if isinstance(target, Harvester)
                    else 2.5
                    if isinstance(target, Headquarters)
                    else 2
                    if isinstance(target, Turret)
                    else 1.5
                    if target.health / target.max_health < 0.3
                    else 1
                )
                targets.append((target, dist, priority))
        for building in self.buildings:
            if building.team != unit.team and building.health > 0:
                dist = math.sqrt(
                    (unit.rect.centerx - building.rect.centerx) ** 2 + (unit.rect.centery - building.rect.centery) ** 2
                )
                priority = 2.5 if isinstance(building, Headquarters) else 2 if isinstance(building, Turret) else 1
                targets.append((building, dist, priority))
        targets.sort(key=lambda x: x[1] / x[2])
        return targets[0][0] if targets and targets[0][1] < 250 else None

    def find_valid_building_position(self, building_class: type[Building]) -> FloatCoord:
        closest_field = min(
            self.iron_fields,
            key=lambda f: math.sqrt(
                (f.rect.centerx - self.headquarters.rect.centerx) ** 2
                + (f.rect.centery - self.headquarters.rect.centery) ** 2
            ),
            default=None,
        )
        live_ai_buildings = {b for b in self.ai_buildings if building.health > 0}
        for b in live_ai_buildings:
            for angle in range(0, 360, 20):
                x = b.rect.centerx + math.cos(math.radians(angle)) * 120
                y = b.rect.centery + math.sin(math.radians(angle)) * 120
                x, y = snap_to_grid(x, y)
                if is_valid_building_position(x, y, team="NOD", cls=building_class):
                    if (
                        closest_field
                        and math.sqrt((x - closest_field.rect.centerx) ** 2 + (y - closest_field.rect.centery) ** 2)
                        < 600
                    ):
                        return x, y
                    elif not closest_field:
                        return x, y

        return snap_to_grid(self.headquarters.rect.centerx, self.headquarters.rect.centery)

    def produce_units(self, player_info: Mapping[str, int]) -> None:
        current_units = {
            "Harvester": len({u for u in self.ai_units if isinstance(u, Harvester)}),
            "Infantry": len({u for u in self.ai_units if isinstance(u, Infantry)}),
            "Tank": len({u for u in self.ai_units if isinstance(u, Tank)}),
            "Turret": len({b for b in self.ai_buildings if isinstance(b, Turret)}),
            "PowerPlant": len({b for b in self.ai_buildings if isinstance(b, PowerPlant)}),
            "Barracks": len({b for b in self.ai_buildings if isinstance(b, Barracks) and b.health > 0})
            + len({b for b in self.headquarters.production_queue if b == Barracks}),
            "WarFactory": len({b for b in self.ai_buildings if isinstance(b, WarFactory) and b.health > 0})
            + len([b for b in self.headquarters.production_queue if b == WarFactory]),
        }
        target_units = {unit: int(self.target_ratio[unit] * AI.SCALE_FACTOR) for unit in self.target_ratio}
        target_units["PowerPlant"] = max(1, (current_units["Harvester"] + 1) // 2)
        target_units["Barracks"] = 1
        target_units["WarFactory"] = 1
        has_barracks = current_units["Barracks"] > 0
        has_warfactory = current_units["WarFactory"] > 0
        total_military = current_units["Infantry"] + current_units["Tank"] + current_units["Turret"]
        iron = self.headquarters.iron
        console.log(
            f"AI production check: Iron = {iron}, Has Barracks = {has_barracks}, Has WarFactory = {has_warfactory}"
        )

        if not has_barracks and iron >= Barracks.cost:
            self.headquarters.production_queue.append(Barracks)
            iron -= Barracks.cost
            self.headquarters.iron = iron
            console.log(f"AI produced Barracks, cost: {Barracks.cost}, new iron: {self.headquarters.iron}")
            return
        elif not has_warfactory and iron >= WarFactory.cost:
            self.headquarters.production_queue.append(WarFactory)
            iron -= WarFactory.cost
            self.headquarters.iron = iron
            console.log(f"AI produced WarFactory, cost: {WarFactory.cost}, new iron: {self.headquarters.iron}")
            return
        elif (
            self.headquarters.power_usage > self.headquarters.power_output
            and iron >= PowerPlant.cost
            and current_units["PowerPlant"] < target_units["PowerPlant"]
        ):
            self.headquarters.production_queue.append(PowerPlant)
            iron -= PowerPlant.cost
            self.headquarters.iron = iron
            console.log(f"AI produced PowerPlant, cost: {PowerPlant.cost}, new iron: {self.headquarters.iron}")
            return

        if (
            (
                current_units["Harvester"] < min(target_units["Harvester"], player_info["harvesters"] + 1)
                or self.iron_income_rate < 50
            )
            and iron >= Harvester.cost
            and has_warfactory
        ):
            self.headquarters.production_queue.append(Harvester)
            iron -= Harvester.cost
            self.headquarters.iron = iron
            console.log(f"AI produced Harvester, cost: {Harvester.cost}, new iron: {self.headquarters.iron}")
            return

        if iron <= 0:
            console.log("AI production halted: Insufficient iron")
            return

        if self.state in ["BUILD UP", "AGGRESSIVE"]:
            production_options: list[tuple[type[GameObject], int]] = []
            if (
                total_military < 6
                and has_barracks
                and iron >= Infantry.cost
                and current_units["Infantry"] < target_units["Infantry"]
            ):
                production_options.append((Infantry, Infantry.cost))
            if (
                total_military < 6
                and has_warfactory
                and iron >= Tank.cost
                and current_units["Tank"] < target_units["Tank"]
            ):
                production_options.append((Tank, Tank.cost))
            if iron >= Turret.cost and current_units["Turret"] < target_units["Turret"]:
                production_options.append((Turret, Turret.cost))
            if has_barracks and iron >= Infantry.cost and current_units["Infantry"] < target_units["Infantry"]:
                production_options.append((Infantry, Infantry.cost))
            if has_warfactory and iron >= Tank.cost and current_units["Tank"] < target_units["Tank"]:
                production_options.append((Tank, Tank.cost))
            if current_units["Harvester"] < target_units["Harvester"] and iron >= Harvester.cost and has_warfactory:
                production_options.append((Harvester, Harvester.cost))
            if current_units["PowerPlant"] < target_units["PowerPlant"] and iron >= PowerPlant.cost:
                production_options.append((PowerPlant, PowerPlant.cost))
            if current_units["Barracks"] < 2 and iron >= Barracks.cost and total_military >= 6:
                production_options.append((Barracks, Barracks.cost))
            if current_units["WarFactory"] < 2 and iron >= WarFactory.cost and total_military >= 6:
                production_options.append((WarFactory, WarFactory.cost))
            if iron >= Headquarters.cost and current_units["Harvester"] >= 2:
                production_options.append((Headquarters, Headquarters.cost))

            if production_options:
                unit_class, cost = random.choice(production_options)
                self.headquarters.production_queue.append(unit_class)
                iron -= cost
                self.headquarters.iron = iron
                console.log(f"AI produced {unit_class.__name__}, cost: {cost}, new iron: {self.headquarters.iron}")

        elif self.state in ["ATTACKED", "THREATENED"]:
            production_options = []
            if iron >= Turret.cost and current_units["Turret"] < target_units["Turret"]:
                production_options.append((Turret, Turret.cost))
            if has_warfactory and iron >= Tank.cost and current_units["Tank"] < target_units["Tank"]:
                production_options.append((Tank, Tank.cost))
            if has_barracks and iron >= Infantry.cost and current_units["Infantry"] < target_units["Infantry"]:
                production_options.append((Infantry, Infantry.cost))
            if (
                current_units["Harvester"] < min(target_units["Harvester"], player_info["harvesters"] + 1)
                and iron >= Harvester.cost
                and has_warfactory
            ):
                production_options.append((Harvester, Harvester.cost))
            if current_units["PowerPlant"] < target_units["PowerPlant"] and iron >= PowerPlant.cost:
                production_options.append((PowerPlant, PowerPlant.cost))

            if production_options:
                unit_class, cost = random.choice(production_options)
                self.headquarters.production_queue.append(unit_class)
                iron -= cost
                self.headquarters.iron = iron
                console.log(f"AI produced {unit_class.__name__}, cost: {cost}, new iron: {self.headquarters.iron}")

        elif (
            self.state == "BROKE"
            and has_warfactory
            and iron >= Harvester.cost
            and current_units["Harvester"] < min(target_units["Harvester"], player_info["harvesters"] + 1)
        ):
            self.headquarters.production_queue.append(Harvester)
            iron -= Harvester.cost
            self.headquarters.iron = iron
            console.log(f"AI produced Harvester, cost: {Harvester.cost}, new iron: {self.headquarters.iron}")

        if self.headquarters.production_queue and not self.headquarters.production_timer:
            self.headquarters.production_timer = self.headquarters.get_production_time(
                self.headquarters.production_queue[0]
            )
        if self.headquarters.pending_building and not self.headquarters.pending_building_pos:
            x, y = self.find_valid_building_position(self.headquarters.pending_building)
            self.headquarters.pending_building_pos = (x, y)
            self.headquarters.place_building(x, y, cls=self.headquarters.pending_building)

    def coordinate_attack(self, surprise: bool = False) -> None:
        self.wave_timer = 0
        self.wave_number += 1
        if surprise:
            wave_size = min(12 + self.wave_number, AI.MAX_WAVE_SIZE)
        else:
            wave_size = min(8 + self.wave_number * 2, AI.MAX_WAVE_SIZE)

        self.wave_interval = random.randint(150, 250)
        combat_units = [u for u in self.ai_units if isinstance(u, (Tank, Infantry)) and not u.target]
        if not combat_units:
            return

        tactics = (
            ["balanced", "flank", "all_in"]
            if self.state == "AGGRESSIVE" or surprise
            else ["all_in", "defensive"]
            if self.state in ["THREATENED", "ATTACKED"]
            else ["balanced", "flank", "all_in"]
        )
        tactic = random.choice(tactics)
        if tactic == "balanced":
            infantry_count = min(int(wave_size * 0.6), len([u for u in combat_units if isinstance(u, Infantry)]))
            tank_count = min(int(wave_size * 0.4), len([u for u in combat_units if isinstance(u, Tank)]))
            attack_units = [u for u in combat_units if isinstance(u, Infantry)][:infantry_count] + [
                u for u in combat_units if isinstance(u, Tank)
            ][:tank_count]
            target = self.prioritize_targets(attack_units[0] if attack_units else None)
            if target:
                for unit in attack_units:
                    unit.target_unit = target
                    unit.target = (
                        target.rect.centerx + random.uniform(-20, 20),
                        target.rect.centery + random.uniform(-20, 20),
                    )
        elif tactic == "flank":
            attack_units = combat_units[:wave_size]
            gdi_hq = next((b for b in self.player_buildings if isinstance(b, Headquarters)), None)
            if gdi_hq:
                group_size = len(attack_units) // 2
                for i, unit in enumerate(attack_units):
                    offset_x = random.uniform(80, 120) if i < group_size else random.uniform(-120, -80)
                    offset_y = random.uniform(80, 120) if i < group_size else random.uniform(-120, -80)
                    unit.target = (gdi_hq.rect.centerx + offset_x, gdi_hq.rect.centery + offset_y)
                    unit.target_unit = gdi_hq
        elif tactic == "all_in":
            attack_units = combat_units[:wave_size]
            target = self.prioritize_targets(attack_units[0] if attack_units else None)
            if target:
                for unit in attack_units:
                    unit.target_unit = target
                    unit.target = (
                        target.rect.centerx + random.uniform(-20, 20),
                        target.rect.centery + random.uniform(-20, 20),
                    )
        elif tactic == "defensive":
            attack_units = combat_units[:wave_size]
            for unit in attack_units:
                unit.target = (
                    self.headquarters.rect.centerx + random.uniform(-50, 50),
                    self.headquarters.rect.centery + random.uniform(-50, 50),
                )
                unit.target_unit = None

    def update(self) -> None:
        self.timer += 1
        self.wave_timer += 1
        self.surprise_attack_cooldown = max(0, self.surprise_attack_cooldown - 1)
        player_info = self._evaluate_player()
        self.state = self._evaluate_state(player_base_size=player_info["base_size"])
        self.update_scouting()
        if self.timer >= AI.ACTION_INTERVAL:
            self.timer = 0
            self.produce_units(player_info)
        if (
            self.surprise_attack_cooldown <= 0
            and player_info["tanks"] + player_info["infantry"] + player_info["turrets"] < 5
            and random.random() < 0.1
        ):
            self.coordinate_attack(surprise=True)
            self.surprise_attack_cooldown = 300
        elif self.wave_timer >= self.wave_interval:
            self.coordinate_attack()


if __name__ == "__main__":
    pygame.init()
    screen = pygame.display.set_mode((SCREEN_WIDTH, SCREEN_HEIGHT))
    """The top-level `pygame.Surface`."""
    clock = pygame.time.Clock()
    font = pygame.font.SysFont(None, 24)

    global_units: SpriteGroup = pygame.sprite.Group()
    global_buildings: SpriteGroup = pygame.sprite.Group()
    player_units: SpriteGroup = pygame.sprite.Group()
    ai_units: SpriteGroup = pygame.sprite.Group()
    iron_fields: SpriteGroup = pygame.sprite.Group()
    projectiles: SpriteGroup = pygame.sprite.Group()
    particles: SpriteGroup = pygame.sprite.Group()
    selected_units: SpriteGroup = pygame.sprite.Group()

    gdi_headquarters = Headquarters(300, 300, "GDI")
    nod_headquarters = Headquarters(2000, 1200, "NOD")
    nod_headquarters.iron = 1500
    interface = ProductionInterface(gdi_headquarters)
    console = GameConsole()
    fog_of_war = FogOfWar(MAP_WIDTH, MAP_HEIGHT)
    selected_building = None
    selecting = False
    select_start = None
    select_rect = None
    camera = Camera(MAP_WIDTH, MAP_HEIGHT)
    base_map = pygame.Surface((MAP_WIDTH, MAP_HEIGHT))
    # Improved map with grass texture
    for x in range(0, MAP_WIDTH, TILE_SIZE):
        for y in range(0, MAP_HEIGHT, TILE_SIZE):
            color = (0, random.randint(100, 150), 0)
            pygame.draw.rect(base_map, color, (x, y, TILE_SIZE, TILE_SIZE))
            if random.random() < 0.1:
                pygame.draw.circle(
                    base_map,
                    (0, 80, 0),
                    (x + TILE_SIZE // 2, y + TILE_SIZE // 2),
                    TILE_SIZE // 4,
                )  # Dark spots

    ai = AI(
        headquarters=nod_headquarters,
        ai_units=ai_units,
        all_units=global_units,
        iron_fields=iron_fields,
        buildings=global_buildings,
    )

    player_units.add(Infantry(350, 300, "GDI"))
    player_units.add(Infantry(370, 300, "GDI"))
    player_units.add(Infantry(390, 300, "GDI"))
    player_units.add(Harvester(400, 400, "GDI", gdi_headquarters))

    ai_units.add(Infantry(2050, 1200, "NOD"))
    ai_units.add(Infantry(2070, 1200, "NOD"))
    ai_units.add(Infantry(2090, 1200, "NOD"))
    ai_units.add(Harvester(2200, 1300, "NOD", nod_headquarters))

    global_units.add(player_units, ai_units)
    global_buildings.add(gdi_headquarters, nod_headquarters)
    for _ in range(40):
        iron_fields.add(
            IronField(random.randint(100, MAP_WIDTH - 100), random.randint(100, MAP_HEIGHT - 100), font=font)
        )

    running = True
    while running:
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False
            elif event.type == pygame.MOUSEBUTTONDOWN:
                target_x, target_y = event.pos
                world_x, world_y = camera.screen_to_world((target_x, target_y))
                if event.button == 1:
                    if gdi_headquarters.pending_building:
                        world_x, world_y = snap_to_grid(world_x, world_y)
                        if is_valid_building_position(
                            world_x, world_y, team="GDI", cls=gdi_headquarters.pending_building
                        ):
                            gdi_headquarters.place_building(world_x, world_y, cls=gdi_headquarters.pending_building)
                        continue
                    if interface.handle_click(event.pos, gdi_headquarters.iron):
                        continue
                    clicked_building = next(
                        (
                            b
                            for b in global_buildings
                            if b.team == "GDI" and camera.apply(b.rect).collidepoint(target_x, target_y)
                        ),
                        None,
                    )
                    if clicked_building:
                        selected_building = clicked_building
                    else:
                        selected_building = None
                        selecting = True
                        select_start = event.pos
                        select_rect = pygame.Rect(target_x, target_y, 0, 0)
                elif event.button == 3:
                    if gdi_headquarters.pending_building:
                        gdi_headquarters.pending_building = None
                        gdi_headquarters.pending_building_pos = None
                        if gdi_headquarters.production_queue and gdi_headquarters.has_enough_power:
                            gdi_headquarters.production_timer = gdi_headquarters.get_production_time(
                                gdi_headquarters.production_queue[0]
                            )
                        continue
                    clicked_field = next(
                        (f for f in iron_fields if camera.apply(f.rect).collidepoint(target_x, target_y)), None
                    )
                    clicked_enemy_unit = next(
                        (
                            u
                            for u in global_units
                            if u.team != "GDI" and camera.apply(u.rect).collidepoint(target_x, target_y)
                        ),
                        None,
                    )
                    clicked_enemy_building = next(
                        (
                            b
                            for b in global_buildings
                            if b.team != "GDI" and camera.apply(b.rect).collidepoint(target_x, target_y)
                        ),
                        None,
                    )
                    if selected_units:
                        group_center = (
                            sum(u.rect.centerx for u in selected_units) / len(selected_units),
                            sum(u.rect.centery for u in selected_units) / len(selected_units),
                        )
                        formation_positions = calculate_formation_positions(
                            (world_x, world_y), (world_x, world_y), len(selected_units)
                        )
                        for unit, pos in zip(selected_units, formation_positions):
                            unit.target = pos
                            unit.formation_target = pos
                            unit.target_unit = None
                            if clicked_enemy_unit:
                                unit.target_unit = clicked_enemy_unit
                                unit.target = clicked_enemy_unit.rect.center
                            elif clicked_enemy_building:
                                unit.target_unit = clicked_enemy_building
                                unit.target = clicked_enemy_building.rect.center
                            elif clicked_field:
                                unit.target = clicked_field.rect.center
                                unit.formation_target = None
            elif event.type == pygame.MOUSEMOTION and selecting:
                current_pos = event.pos
                if not select_start:
                    raise TypeError("No selection rect start point")  # Temporary handling, review later

                select_rect = pygame.Rect(
                    min(select_start[0], current_pos[0]),
                    min(select_start[1], current_pos[1]),
                    abs(current_pos[0] - select_start[0]),
                    abs(current_pos[1] - select_start[1]),
                )
            elif event.type == pygame.MOUSEBUTTONUP and event.button == 1 and selecting:
                if not select_start:
                    raise TypeError("No selection rect start point")  # Temporary handling, review later

                selecting = False
                for unit in player_units:
                    unit.selected = False
                selected_units.empty()
                world_start = camera.screen_to_world(select_start)
                world_end = camera.screen_to_world(event.pos)
                world_rect = pygame.Rect(
                    min(world_start[0], world_end[0]),
                    min(world_start[1], world_end[1]),
                    abs(world_end[0] - world_start[0]),
                    abs(world_end[1] - world_start[1]),
                )
                for unit in player_units:
                    if world_rect.colliderect(unit.rect):
                        unit.selected = True
                        selected_units.add(unit)
            console.handle_event(event)

        camera.update(selected_units, pygame.mouse.get_pos(), interface.panel_rect)
        global_units.update()
        iron_fields.update()
        global_buildings.update()
        projectiles.update()
        particles.update()
        handle_collisions(global_units)
        handle_attacks(player_units, global_units, global_buildings, projectiles, particles)
        handle_attacks(ai_units, global_units, global_buildings, projectiles, particles)
        handle_projectiles(projectiles, global_units, global_buildings)
        ai.update()
        fog_of_war.update_visibility(player_units, global_buildings, "GDI")
        screen.blit(base_map, (-camera.rect.x, -camera.rect.y))
        for field in iron_fields:
            if field.resources > 0 and fog_of_war.is_tile_explored(field.rect.centerx, field.rect.centery):
                field.draw(screen, camera)
        for building in global_buildings:
            if building.health > 0 and (
                fog_of_war.is_tile_visible(building.rect.centerx, building.rect.centery)
                or (building.is_seen and fog_of_war.is_tile_explored(building.rect.centerx, building.rect.centery))
            ):
                building.draw(screen, camera)
        fog_of_war.draw(screen, camera)
        for unit in global_units:
            if unit.team == "GDI" or fog_of_war.is_tile_visible(unit.rect.centerx, unit.rect.centery):
                unit.draw(screen, camera)
        for projectile in projectiles:
            if projectile.team == "GDI" or fog_of_war.is_tile_visible(projectile.rect.centerx, projectile.rect.centery):
                projectile.draw(screen, camera)
        for particle in particles:
            if fog_of_war.is_tile_visible(particle.rect.centerx, particle.rect.centery):
                particle.draw(screen, camera)
        interface.draw(screen, gdi_headquarters.iron)
        screen.blit(font.render(f"Iron: {gdi_headquarters.iron}", True, (255, 255, 255)), (10, 10))
        if selecting and select_rect:
            pygame.draw.rect(screen, (255, 255, 255), select_rect, 2)
        console.draw(screen)
        for obj in global_units:
            if hasattr(obj, "under_attack") and obj.under_attack:
                obj.under_attack = False
        pygame.display.flip()
        clock.tick(60)

    pygame.quit()

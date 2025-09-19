from __future__ import annotations

import math
import random
from dataclasses import dataclass
from dataclasses import field as dataclass_field
from enum import Enum
from typing import TYPE_CHECKING, ClassVar

import pygame as pg

from src.constants import MAP_HEIGHT, MAP_WIDTH, TILE_SIZE
from src.game_object import GameObject
from src.geometry import is_valid_building_position, snap_to_grid
from src.shapes import draw_progress_bar

if TYPE_CHECKING:
    from collections.abc import Callable

    from src.geometry import Coordinate

SCREEN_WIDTH, SCREEN_HEIGHT = 1920, 1080
BASE_PRODUCTION_TIME = 180
GDI_COLOR = (200, 150, 0)  # Brighter yellow for GDI
NOD_COLOR = (200, 0, 0)  # Brighter red for NOD
CONSOLE_HEIGHT = 200


def calculate_formation_positions(
    center: Coordinate, target, num_units: int, direction=None
) -> list[Coordinate]:
    if num_units == 0:
        return []
    max_cols, max_rows = 5, 4
    spacing = 20
    positions = []
    if direction is None and target:
        dx, dy = target[0] - center[0], target[1] - center[1]
        angle = math.atan2(dy, dx) if dx != 0 or dy != 0 else 0
    else:
        angle = direction if direction is not None else 0
    cos_a, sin_a = math.cos(angle), math.sin(angle)
    for i in range(min(num_units, max_cols * max_rows)):
        row = i // max_cols
        col = i % max_cols
        offset_x = (col - (max_cols - 1) / 2) * spacing
        offset_y = (row - (max_rows - 1) / 2) * spacing
        rotated_x = offset_x * cos_a - offset_y * sin_a
        rotated_y = offset_x * sin_a + offset_y * cos_a
        positions.append((center[0] + rotated_x, center[1] + rotated_y))
    return positions


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
                    push = (
                        0.3
                        if isinstance(unit, Harvester) and isinstance(other, Harvester)
                        else 0.5
                    )
                    unit.rect.x += push * dx / dist
                    unit.rect.y += push * dy / dist
                    other.rect.x -= push * dx / dist
                    other.rect.y -= push * dy / dist


def handle_attacks(units, all_units, buildings, projectiles, particles) -> None:
    for unit in units:
        if isinstance(unit, (Tank, Infantry)) and unit.cooldown_timer == 0:
            closest_target, min_dist = None, float("inf")
            if (
                unit.target_unit
                and hasattr(unit.target_unit, "health")
                and unit.target_unit.health > 0
            ):
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
                    unit.angle = math.degrees(
                        math.atan2(dy, dx)
                    )  # Updated to match Tank's angle calculation
                    projectiles.add(
                        Projectile(
                            unit.rect.centerx,
                            unit.rect.centery,
                            closest_target,
                            unit.attack_damage,
                            unit.team,
                        )
                    )
                    unit.recoil = 5
                    barrel_angle = math.radians(unit.angle)
                    smoke_x = unit.rect.centerx + math.cos(barrel_angle) * (
                        unit.rect.width // 2 + 12
                    )
                    smoke_y = unit.rect.centery + math.sin(barrel_angle) * (
                        unit.rect.width // 2 + 12
                    )
                    for _ in range(5):
                        particles.add(
                            Particle(
                                smoke_x,
                                smoke_y,
                                random.uniform(-1.5, 1.5),
                                random.uniform(-1.5, 1.5),
                                random.randint(6, 10),
                                (100, 100, 100),
                                20,
                            )
                        )
                else:
                    closest_target.health -= unit.attack_damage
                    closest_target.under_attack = (
                        True  # Set under_attack only when damage is applied
                    )
                    for _ in range(3):
                        particles.add(
                            Particle(
                                unit.rect.centerx,
                                unit.rect.centery,
                                random.uniform(-1, 1),
                                random.uniform(-1, 1),
                                4,
                                (255, 200, 100),
                                10,
                            )
                        )
                    if closest_target.health <= 0:
                        closest_target.kill()
                        unit.target = unit.target_unit = None
                unit.cooldown_timer = unit.attack_cooldown


def handle_projectiles(projectiles, all_units, buildings) -> None:
    for projectile in projectiles:
        hit = False
        # Check collision with all units and buildings, not just the target
        for target in all_units:
            if (
                target.team != projectile.team
                and target.health > 0
                and projectile.rect.colliderect(target.rect)
            ):
                target.health -= projectile.damage
                target.under_attack = True  # Set under_attack when damage is applied
                for _ in range(5):
                    particles.add(
                        Particle(
                            projectile.rect.centerx,
                            projectile.rect.centery,
                            random.uniform(-2, 2),
                            random.uniform(-2, 2),
                            6,
                            (255, 200, 100),
                            15,
                        )
                    )
                if target.health <= 0:
                    target.kill()
                hit = True
                break
        if not hit:
            for target in buildings:
                if (
                    target.team != projectile.team
                    and target.health > 0
                    and projectile.rect.colliderect(target.rect)
                ):
                    target.health -= projectile.damage
                    target.under_attack = (
                        True  # Set under_attack when damage is applied
                    )
                    for _ in range(5):
                        particles.add(
                            Particle(
                                projectile.rect.centerx,
                                projectile.rect.centery,
                                random.uniform(-2, 2),
                                random.uniform(-2, 2),
                                6,
                                (255, 200, 100),
                                15,
                            )
                        )
                    if target.health <= 0:
                        target.kill()
                    hit = True
                    break
        if hit:
            projectile.kill()
        # Only kill projectile if it has no valid target or moves too far
        elif not (
            projectile.target
            and hasattr(projectile.target, "health")
            and projectile.target.health > 0
        ):
            projectile.kill()


def draw(surface_: pg.Surface) -> None:
    surface_.fill(pg.Color("black"))
    surface_.blit(base_map, (-camera.rect.x, -camera.rect.y))
    for field in iron_fields:
        if field.resources > 0 and fog_of_war.is_explored(field.rect.center):
            field.draw(surface_, camera)

    for building in buildings:
        if building.health > 0 and (
            fog_of_war.is_visible(building.rect.center)
            or (building.is_seen and fog_of_war.is_explored(building.rect.center))
        ):
            building.draw(surface_, camera)

    fog_of_war.draw(surface_, camera)
    for unit in all_units:
        if unit.team == Team.GDI or fog_of_war.is_visible(unit.rect.center):
            unit.draw(surface_, camera)

    for projectile in projectiles:
        if projectile.team == Team.GDI or fog_of_war.is_visible(projectile.rect.center):
            projectile.draw(surface_, camera)

    for particle in particles:
        if fog_of_war.is_visible(particle.rect.center):
            particle.draw(surface_, camera)

    interface.draw(surface_)
    if selecting and select_rect:
        pg.draw.rect(surface_, (255, 255, 255), select_rect, 2)

    console.draw(surface_)


class Team(Enum):
    GDI = "gdi"
    NOD = "nod"


class Camera:
    def __init__(self, map_width: int, map_height: int) -> None:
        self.rect = pg.Rect(0, 0, SCREEN_WIDTH - 200, SCREEN_HEIGHT - CONSOLE_HEIGHT)
        self.map_width = map_width
        self.map_height = map_height

    def update(
        self, selected_units, mouse_pos: Coordinate, interface_rect: pg.Rect
    ) -> None:
        mx, my = mouse_pos
        if interface_rect.collidepoint(mx, my) or my > SCREEN_HEIGHT - CONSOLE_HEIGHT:
            return
        if selected_units:
            avg_x = sum(unit.rect.centerx for unit in selected_units) / len(
                selected_units
            )
            avg_y = sum(unit.rect.centery for unit in selected_units) / len(
                selected_units
            )
            self.rect.center = (
                max(
                    self.rect.width // 2,
                    min(self.map_width - self.rect.width // 2, int(avg_x)),
                ),
                max(
                    self.rect.height // 2,
                    min(self.map_height - self.rect.height // 2, int(avg_y)),
                ),
            )
        else:
            if mx < 30 and self.rect.left > 0:
                self.rect.x -= 10
            elif mx > SCREEN_WIDTH - 230 and self.rect.right < self.map_width:
                self.rect.x += 10
            if my < 30 and self.rect.top > 0:
                self.rect.y -= 10
            elif (
                my > SCREEN_HEIGHT - CONSOLE_HEIGHT - 30
                and self.rect.bottom < self.map_height
            ):
                self.rect.y += 10
        self.rect.clamp_ip(pg.Rect(0, 0, self.map_width, self.map_height))

    def apply(self, rect: pg.Rect) -> pg.Rect:
        return pg.Rect(
            rect.x - self.rect.x, rect.y - self.rect.y, rect.width, rect.height
        )

    def screen_to_world(self, screen_pos: Coordinate) -> Coordinate:
        x, y = screen_pos
        map_area_y = int(min(y, SCREEN_HEIGHT - CONSOLE_HEIGHT))
        return (
            max(0, min(self.map_width, int(x) + self.rect.x)),
            max(0, min(self.map_height, map_area_y + self.rect.y)),
        )


@dataclass(kw_only=True)
class FogOfWar:
    map_size: tuple[int, int]
    tile_size: int
    explored: list[list[bool]] = dataclass_field(default_factory=list)
    visible: list[list[bool]] = dataclass_field(default_factory=list)
    surface: pg.Surface = dataclass_field(init=False)

    def __post_init__(self) -> None:
        map_width, map_height = self.map_size
        self.explored = [
            [False] * (map_height // self.tile_size)
            for _ in range(map_width // self.tile_size)
        ]
        self.visible = [
            [False] * (map_height // self.tile_size)
            for _ in range(map_width // self.tile_size)
        ]
        self.surface = pg.Surface(self.map_size, pg.SRCALPHA)
        self.surface.fill((0, 0, 0, 255))

    def tile(self, position: Coordinate) -> tuple[int, int]:
        """Return tile."""
        x, y = position
        return int(x // self.tile_size), int(y // self.tile_size)

    def _reveal(self, center: Coordinate, radius: float) -> None:
        """Set tiles within `radius` of `center` as explored and visible."""
        cx, cy = center
        tile_x, tile_y = self.tile(center)
        radius_tiles = int(radius // self.tile_size)
        for y in range(
            max(0, tile_y - radius_tiles),
            min(len(self.explored[0]), tile_y + radius_tiles + 1),
        ):
            for x in range(
                max(0, tile_x - radius_tiles),
                min(len(self.explored), tile_x + radius_tiles + 1),
            ):
                if (
                    (cx - (x * self.tile_size + self.tile_size // 2)) ** 2
                    + (cy - (y * self.tile_size + self.tile_size // 2)) ** 2
                ) <= radius**2:
                    self.explored[x][y] = True
                    self.visible[x][y] = True

    def update_visibility(self, units, buildings, team: Team) -> None:
        """Reveal tiles within range of `team`'s `unit`s and `buildings`."""
        self.visible = [
            [False] * len(self.explored[0]) for _ in range(len(self.explored))
        ]
        for unit in units:
            if unit.team == team:
                self._reveal(center=unit.rect.center, radius=150)

        for building in buildings:
            if building.team == team:
                self._reveal(center=building.rect.center, radius=200)

            if building.health > 0:
                tile_x, tile_y = self.tile(building.rect.center)
                if 0 <= tile_x < len(self.visible) and 0 <= tile_y < len(
                    self.visible[0]
                ):
                    self.visible[tile_x][tile_y] = True
                    # indirectly makes enemy buildings in tile visible

    def is_visible(self, position: Coordinate) -> bool:
        """Return whether `position` is in a visible tile."""
        tile_x, tile_y = self.tile(position)
        if 0 <= tile_x < len(self.visible) and 0 <= tile_y < len(self.visible[0]):
            return self.visible[tile_x][tile_y]

        return False

    def is_explored(self, position: Coordinate) -> bool:
        """Return whether `position` is in an explored tile."""
        tile_x, tile_y = self.tile(position)
        if 0 <= tile_x < len(self.explored) and 0 <= tile_y < len(self.explored[0]):
            return self.explored[tile_x][tile_y]

        return False

    def draw(self, surface_: pg.Surface, camera: Camera) -> None:
        """Draw opaque and semi-transparent fog tiles to `surface`.

        NB: drawn over buildings; under units.
        """
        for y in range(len(self.explored[0])):
            for x in range(len(self.explored)):
                if self.explored[x][y]:
                    alpha = 0 if self.visible[x][y] else 100
                    pg.draw.rect(
                        self.surface,
                        (0, 0, 0, alpha),
                        (
                            x * self.tile_size,
                            y * self.tile_size,
                            self.tile_size,
                            self.tile_size,
                        ),
                    )

        surface_.blit(self.surface, (-camera.rect.x, -camera.rect.y))


class Tank(GameObject):
    COST = 500
    POWER_USAGE = 15

    def __init__(self, x: float, y: float, team: Team) -> None:
        super().__init__(x, y, team)
        self.base_image = pg.Surface((30, 20), pg.SRCALPHA)
        # Draw tank body (front facing east/right)
        pg.draw.rect(self.base_image, (100, 100, 100), (0, 0, 30, 20))  # Hull
        pg.draw.rect(self.base_image, (80, 80, 80), (2, 2, 26, 16))  # Inner hull
        pg.draw.rect(self.base_image, (50, 50, 50), (0, -2, 30, 4))  # Tracks top
        pg.draw.rect(self.base_image, (50, 50, 50), (0, 18, 30, 4))  # Tracks bottom
        self.barrel_image = pg.Surface((20, 4), pg.SRCALPHA)
        pg.draw.rect(
            self.barrel_image, (70, 70, 70), (0, 0, 20, 4)
        )  # Barrel (extends right)
        self.image = self.base_image
        self.rect = self.image.get_rect(center=(x, y))
        self.speed = 2.5 if team == Team.GDI else 3
        self.health = 200 if team == Team.GDI else 120
        self.max_health = self.health
        self.attack_range = 200
        self.attack_damage = 20 if team == Team.GDI else 15
        self.attack_cooldown = 50
        self.angle: float = 0
        self.recoil = 0

    def update(self) -> None:
        super().update()
        if (
            self.target_unit
            and hasattr(self.target_unit, "health")
            and self.target_unit.health > 0
        ):
            dist = math.sqrt(
                (self.rect.centerx - self.target_unit.rect.centerx) ** 2
                + (self.rect.centery - self.target_unit.rect.centery) ** 2
            )
            self.target = (
                (self.target_unit.rect.centerx, self.target_unit.rect.centery)
                if dist <= 250
                else None
            )
            self.target_unit = self.target_unit if self.target else None
        if self.target:
            dx, dy = (
                self.target[0] - self.rect.centerx,
                self.target[1] - self.rect.centery,
            )
            self.angle = math.degrees(
                math.atan2(dy, dx)
            )  # Use dy instead of -dy to fix vertical direction
            self.image = pg.Surface((40, 40), pg.SRCALPHA)
            # Rotate base image to face target (base image faces east, so -angle aligns it correctly)
            rotated_base = pg.transform.rotate(self.base_image, -self.angle)
            self.image.blit(rotated_base, rotated_base.get_rect(center=(20, 20)))
            # Handle barrel with recoil
            barrel_length = 20 - self.recoil * 2
            barrel_image = pg.Surface((barrel_length, 4), pg.SRCALPHA)
            pg.draw.rect(barrel_image, (70, 70, 70), (0, 0, barrel_length, 4))
            # Rotate barrel to match target direction
            rotated_barrel = pg.transform.rotate(
                barrel_image, -self.angle
            )  # Barrel also faces east initially
            self.image.blit(rotated_barrel, rotated_barrel.get_rect(center=(20, 20)))
            if self.recoil > 0:
                self.recoil -= 1

    def draw(self, screen: pg.Surface, camera: Camera) -> None:
        screen.blit(self.image, camera.apply(self.rect).topleft)
        if self.selected:
            pg.draw.circle(
                screen,
                (255, 255, 255),
                camera.apply(self.rect).center,
                self.rect.width // 2 + 2,
                2,
            )  # Circular selection

        self.draw_health_bar(screen, camera)


class Infantry(GameObject):
    COST = 100
    POWER_USAGE = 5

    def __init__(self, x: float, y: float, team: Team) -> None:
        super().__init__(x, y, team)
        self.image = pg.Surface((16, 16), pg.SRCALPHA)
        # Draw infantry as a simple soldier
        pg.draw.circle(self.image, (150, 150, 150), (8, 4), 4)  # Head
        pg.draw.rect(self.image, (100, 100, 100), (6, 8, 4, 8))  # Body
        pg.draw.line(self.image, (80, 80, 80), (8, 16), (8, 20))  # Legs
        pg.draw.line(self.image, (120, 120, 120), (10, 10), (14, 10))  # Gun
        self.rect = self.image.get_rect(center=(x, y))
        self.speed = 3.5 if team == Team.GDI else 4
        self.health = 100 if team == Team.GDI else 60
        self.max_health = self.health
        self.attack_range = 50
        self.attack_damage = 8
        self.attack_cooldown = 25

    def update(self) -> None:
        super().update()
        if (
            self.target_unit
            and hasattr(self.target_unit, "health")
            and self.target_unit.health > 0
        ):
            dist = math.sqrt(
                (self.rect.centerx - self.target_unit.rect.centerx) ** 2
                + (self.rect.centery - self.target_unit.rect.centery) ** 2
            )
            self.target = (
                (self.target_unit.rect.centerx, self.target_unit.rect.centery)
                if dist <= 200
                else None
            )
            self.target_unit = self.target_unit if self.target else None

    def draw(self, screen: pg.Surface, camera: Camera) -> None:
        screen.blit(self.image, camera.apply(self.rect).topleft)
        if self.selected:
            pg.draw.circle(
                screen, (255, 255, 255), camera.apply(self.rect).center, 10, 2
            )
        self.draw_health_bar(screen, camera)


class Harvester(GameObject):
    COST = 800
    POWER_USAGE = 20

    def __init__(
        self, x: float, y: float, team: Team, headquarters: Headquarters
    ) -> None:
        super().__init__(x, y, team)
        self.image = pg.Surface((50, 30), pg.SRCALPHA)
        # Draw harvester as a truck
        pg.draw.rect(self.image, (120, 120, 120), (0, 0, 50, 30))  # Body
        pg.draw.rect(self.image, (100, 100, 100), (5, 5, 40, 20))  # Cargo area
        pg.draw.circle(self.image, (50, 50, 50), (10, 30), 5)  # Wheel 1
        pg.draw.circle(self.image, (50, 50, 50), (40, 30), 5)  # Wheel 2
        self.rect = self.image.get_rect(center=(x, y))
        self.speed = 2.5
        self.health = 300
        self.max_health = self.health
        self.capacity = 100
        self.iron = 0
        self.headquarters = headquarters
        self.state = "moving_to_field"
        self.target_field: IronField | None = None
        self.harvest_time = 40
        self.attack_range = 50
        self.attack_damage = 10
        self.attack_cooldown = 30

    def update(self) -> None:
        super().update()
        if self.cooldown_timer == 0:
            closest_target, min_dist = None, float("inf")
            for target in all_units:
                if (
                    target.team != self.team
                    and target.health > 0
                    and isinstance(target, Infantry)
                ):
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
                    raise TypeError(
                        "No target field"
                    )  # Temporary handling, review later

                harvested = min(self.target_field.resources, self.capacity)
                self.iron += harvested
                self.target_field.resources -= harvested
                self.state = "returning"
                self.target = self.headquarters.rect.center

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
                self.headquarters.iron += self.iron
                self.iron = 0
                self.state = "moving_to_field"
                self.target = None

    def draw(self, screen: pg.Surface, camera: Camera) -> None:
        screen.blit(self.image, camera.apply(self.rect).topleft)
        if self.selected:
            pg.draw.rect(screen, (255, 255, 255), camera.apply(self.rect), 2)
        self.draw_health_bar(screen, camera)
        if self.iron > 0:
            screen.blit(
                font.render(f"Iron: {self.iron}", True, (255, 255, 255)),
                (camera.apply(self.rect).x, camera.apply(self.rect).y - 35),
            )


class Building(GameObject):
    SIZE = 60, 60

    def __init__(self, x: float, y: float, team: Team, color, health: int) -> None:
        super().__init__(x, y, team)
        self.image = pg.Surface(self.SIZE, pg.SRCALPHA)
        # Add details to building
        pg.draw.rect(self.image, color, ((0, 0), self.SIZE))  # Base
        # Clamp color values to prevent negative values
        inner_color = (
            max(0, color[0] - 50),
            max(0, color[1] - 50),
            max(0, color[2] - 50),
        )
        pg.draw.rect(
            self.image, inner_color, ((5, 5), (self.SIZE[0] - 10, self.SIZE[1] - 10))
        )  # Inner
        for i in range(10, self.SIZE[0] - 10, 20):
            pg.draw.rect(self.image, (200, 200, 200), (i, 10, 10, 10))  # Windows

        self.rect = self.image.get_rect(topleft=(x, y))
        self.health = health
        self.max_health = health
        self.construction_progress = 0
        self.construction_time = 50
        self.is_seen = False

    def update(self) -> None:
        if self.construction_progress < self.construction_time:
            self.construction_progress += 1
            self.image.set_alpha(
                int(255 * self.construction_progress / self.construction_time)
            )
        super().update()
        if self.health <= 0:
            for _ in range(15):
                particles.add(
                    Particle(
                        self.rect.centerx,
                        self.rect.centery,
                        random.uniform(-3, 3),
                        random.uniform(-3, 3),
                        random.randint(6, 12),
                        (200, 100, 100),
                        30,
                    )
                )
            self.kill()

    def draw(self, screen: pg.Surface, camera: Camera) -> None:
        screen.blit(self.image, camera.apply(self.rect).topleft)
        self.draw_health_bar(screen, camera)


class Headquarters(Building):
    COST = 2000
    SIZE = 80, 80

    def __init__(self, x: float, y: float, team: Team) -> None:
        super().__init__(
            x,
            y,
            team,
            GDI_COLOR if team == Team.GDI else NOD_COLOR,
            1200,
        )
        self.iron = 1500
        self.production_queue: list[type[GameObject]] = []
        self.production_timer: float = 0
        self.base_power = 300
        self.pending_building: type[Building] | None = None
        self.pending_building_pos: Coordinate | None = None
        self.power_usage = 0

    @property
    def power_output(self) -> int:
        return self.base_power + sum(
            b.POWER_OUTPUT
            for b in buildings
            if b.team == self.team and isinstance(b, PowerPlant) and b.health > 0
        )

    @property
    def has_enough_power(self) -> bool:
        return self.power_output >= self.power_usage

    def get_production_time(self, unit_class: type[GameObject]) -> float:
        base_time = BASE_PRODUCTION_TIME
        if unit_class == Infantry:
            barracks_count = len(
                [
                    b
                    for b in buildings
                    if b.team == self.team and isinstance(b, Barracks) and b.health > 0
                ]
            )
            return base_time * (0.9**barracks_count)
        elif unit_class in [Tank, Harvester]:
            warfactory_count = len(
                [
                    b
                    for b in buildings
                    if b.team == self.team
                    and isinstance(b, WarFactory)
                    and b.health > 0
                ]
            )
            return base_time * (0.9**warfactory_count)
        return base_time

    def update(self) -> None:
        self.power_usage = sum(
            u.POWER_USAGE for u in all_units if u.team == self.team
        ) + sum(b.POWER_USAGE for b in buildings if b.team == self.team and b != self)
        if (
            self.production_queue
            and not self.production_timer
            and self.has_enough_power
        ):
            self.production_timer = self.get_production_time(self.production_queue[0])

        if self.production_queue:
            self.production_timer -= 1 if self.has_enough_power else 0.5
            if self.production_timer <= 0:
                unit_cls = self.production_queue.pop(0)
                if issubclass(unit_cls, Building):
                    self.pending_building = unit_cls
                    self.pending_building_pos = None

                else:
                    spawn_building: Building = self
                    if unit_cls == Infantry:
                        barracks = [
                            b
                            for b in buildings
                            if b.team == self.team
                            and isinstance(b, Barracks)
                            and b.health > 0
                        ]
                        if not barracks:
                            return

                        spawn_building = min(
                            barracks,
                            key=lambda b: math.sqrt(
                                (b.rect.centerx - self.rect.centerx) ** 2
                                + (b.rect.centery - self.rect.centery) ** 2
                            ),
                        )
                    elif unit_cls in [Tank, Harvester]:
                        warfactories = [
                            b
                            for b in buildings
                            if b.team == self.team
                            and isinstance(b, WarFactory)
                            and b.health > 0
                        ]
                        if not warfactories:
                            return

                        spawn_building = min(
                            warfactories,
                            key=lambda b: math.sqrt(
                                (b.rect.centerx - self.rect.centerx) ** 2
                                + (b.rect.centery - self.rect.centery) ** 2
                            ),
                        )
                    spawn_x, spawn_y = (
                        spawn_building.rect.right + 20,
                        spawn_building.rect.centery,
                    )
                    new_units = [
                        Harvester(spawn_x, spawn_y, self.team, self)
                        if unit_cls == Harvester
                        else unit_cls(spawn_x, spawn_y, self.team)
                    ]
                    formation_positions = calculate_formation_positions(
                        (spawn_x, spawn_y), None, len(new_units), direction=0
                    )
                    for unit, pos in zip(new_units, formation_positions):
                        unit.rect.center = pos
                        unit.formation_target = pos
                        (player_units if self.team == Team.GDI else enemy_units).add(
                            unit
                        )
                        all_units.add(unit)

                self.production_timer = (
                    self.get_production_time(self.production_queue[0])
                    if self.production_queue and self.has_enough_power
                    else 0
                )

        super().update()

    def place_building(self, x: float, y: float, unit_class) -> None:
        snapped_position = snap_to_grid((x, y))
        if is_valid_building_position(
            position=snapped_position,
            team=self.team,
            new_building_cls=unit_class,
            buildings=buildings,
        ):
            buildings.add(unit_class(x, y, self.team))
            self.pending_building = None
            self.pending_building_pos = None
            if self.production_queue and self.has_enough_power:
                self.production_timer = self.get_production_time(
                    self.production_queue[0]
                )

    def draw(self, screen: pg.Surface, camera: Camera) -> None:
        screen.blit(self.image, camera.apply(self.rect).topleft)
        self.draw_health_bar(screen, camera)


class Barracks(Building):
    COST = 500
    POWER_USAGE = 25

    def __init__(self, x: float, y: float, team: Team) -> None:
        super().__init__(
            x,
            y,
            team,
            (150, 150, 0) if team == Team.GDI else (150, 0, 0),
            600,
        )


class WarFactory(Building):
    COST = 1000
    POWER_USAGE = 35

    def __init__(self, x: float, y: float, team: Team) -> None:
        super().__init__(
            x,
            y,
            team,
            (170, 170, 0) if team == Team.GDI else (170, 0, 0),
            800,
        )


class PowerPlant(Building):
    COST = 300
    POWER_OUTPUT = 100
    POWER_USAGE = 0

    def __init__(self, x: float, y: float, team: Team) -> None:
        super().__init__(
            x,
            y,
            team,
            (130, 130, 0) if team == Team.GDI else (130, 0, 0),
            500,
        )


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

    def update(self) -> None:
        super().update()
        if self.cooldown_timer > 0:
            self.cooldown_timer -= 1
        if self.cooldown_timer == 0:
            closest_target, min_dist = None, float("inf")
            for target in all_units:
                if target.team != self.team and target.health > 0:
                    dist = math.sqrt(
                        (self.rect.centerx - target.rect.centerx) ** 2
                        + (self.rect.centery - target.rect.centery) ** 2
                    )
                    if dist < self.attack_range and dist < min_dist:
                        closest_target, min_dist = target, dist
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
            int(255 * self.construction_progress / self.construction_time)
        )


class Particle(pg.sprite.Sprite):
    def __init__(
        self, x: float, y: float, vx: float, vy: float, size: int, color, lifetime: int
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

    def draw(self, screen: pg.Surface, camera: Camera) -> None:
        screen.blit(self.image, camera.apply(self.rect).topleft)


class Projectile(pg.sprite.Sprite):
    def __init__(
        self, x: float, y: float, target: GameObject, damage: int, team: Team
    ) -> None:
        super().__init__()
        self.image: pg.Surface = pg.Surface((10, 5), pg.SRCALPHA)
        pg.draw.ellipse(self.image, (255, 200, 0), (0, 0, 10, 5))  # Brighter projectile
        self.rect: pg.Rect = self.image.get_rect(center=(x, y))
        self.target = target
        self.speed: float = 6
        self.damage = damage
        self.team = team
        self.particle_timer = 2

    def update(self) -> None:
        if self.target and hasattr(self.target, "health") and self.target.health > 0:
            dx, dy = (
                self.target.rect.centerx - self.rect.centerx,
                self.target.rect.centery - self.rect.centery,
            )
            dist = math.sqrt(dx**2 + dy**2)
            if dist > 3:
                angle = math.atan2(dy, dx)
                self.image = pg.transform.rotate(
                    pg.Surface((10, 5), pg.SRCALPHA), -math.degrees(angle)
                )
                pg.draw.ellipse(self.image, (255, 200, 0), (0, 0, 10, 5))
                self.rect.x += self.speed * math.cos(angle)
                self.rect.y += self.speed * math.sin(angle)
                if self.particle_timer <= 0:
                    particles.add(
                        Particle(
                            self.rect.centerx,
                            self.rect.centery,
                            -math.cos(angle) * random.uniform(0.5, 1.5),
                            -math.sin(angle) * random.uniform(0.5, 1.5),
                            5,
                            (255, 255, 150),
                            15,
                        )
                    )
                    self.particle_timer = 2
                else:
                    self.particle_timer -= 1
            else:
                self.kill()
                for _ in range(5):
                    particles.add(
                        Particle(
                            self.rect.centerx,
                            self.rect.centery,
                            random.uniform(-2, 2),
                            random.uniform(-2, 2),
                            6,
                            (255, 100, 0),
                            15,
                        )
                    )  # Orange explosion
        else:
            self.kill()

    def draw(self, screen: pg.Surface, camera: Camera) -> None:
        screen.blit(self.image, camera.apply(self.rect).topleft)


class IronField(pg.sprite.Sprite):
    def __init__(self, x: float, y: float, resources: int = 5000) -> None:
        super().__init__()
        self.image: pg.Surface = pg.Surface((40, 40), pg.SRCALPHA)
        pg.draw.polygon(
            self.image, (0, 200, 0), [(0, 20), (20, 0), (40, 20), (20, 40)]
        )  # Diamond shape for crystal
        self.rect: pg.Rect = self.image.get_rect(topleft=(x, y))
        self.resources = resources
        self.regen_timer = 500

    def update(self) -> None:
        if self.regen_timer > 0:
            self.regen_timer -= 1
        else:
            self.resources = min(5000, self.resources + 15)
            self.regen_timer = 500
        self.image.set_alpha(int(255 * self.resources / 5000))

    def draw(self, screen: pg.Surface, camera: Camera) -> None:
        screen.blit(self.image, camera.apply(self.rect).topleft)
        screen.blit(
            font.render(f"{self.resources}", True, (255, 255, 255)),
            (camera.apply(self.rect).x, camera.apply(self.rect).y - 20),
        )


@dataclass(kw_only=True)
class ProductionInterface:
    """Interface for player."""

    WIDTH: ClassVar = 200
    MARGIN_X: ClassVar = 20
    """Margin on left and right."""
    IRON_POS_Y: ClassVar = 20
    """y position of iron value."""
    POWER_POS_Y: ClassVar = 45
    """... power value."""
    TAB_BUTTONS_POS_Y: ClassVar = 70
    """... first tab button."""
    BUY_BUTTONS_POS_Y: ClassVar = 190
    """... first buy button."""
    SELL_BUTTON_POS_Y: ClassVar = 390
    """... sell button."""
    PRODUCTION_QUEUE_POS_Y: ClassVar = 460
    """... production queue."""
    BUTTON_SPACING_Y: ClassVar = 10
    BUTTON_RADIUS: ClassVar = 5
    TAB_BUTTON_HEIGHT: ClassVar = 30
    ACTION_BUTTON_HEIGHT: ClassVar = 40
    FILL_COLOR: ClassVar = pg.Color(60, 60, 60)
    LINE_COLOR: ClassVar = pg.Color(100, 100, 100)
    ACTIVE_TAB_COLOR: ClassVar = pg.Color(0, 200, 200)
    INACTIVE_TAB_COLOR: ClassVar = pg.Color(50, 50, 50)
    ACTION_ALLOWED_COLOR: ClassVar = pg.Color(0, 200, 0)
    ACTION_BLOCKED_COLOR: ClassVar = pg.Color(200, 0, 0)
    MAX_PRODUCTION_QUEUE_LENGTH: ClassVar = 5
    PLACEMENT_VALID_COLOR = (0, 255, 0)
    PLACEMENT_INVALID_COLOR = (255, 0, 0)

    _BUTTON_WIDTH = WIDTH - 2 * MARGIN_X

    headquarters: Headquarters
    surface: pg.Surface = dataclass_field(init=False)
    tab_buttons: dict[str, pg.Rect] = dataclass_field(default_factory=dict)
    buy_buttons: dict[
        str,
        dict[type[GameObject], tuple[pg.Rect, Callable]],
    ] = dataclass_field(default_factory=dict)
    sell_button: pg.Rect = dataclass_field(init=False)
    current_tab = "Units"
    production_timer: float | None = None

    def __post_init__(self) -> None:
        self.surface = pg.Surface((self.WIDTH, SCREEN_HEIGHT - CONSOLE_HEIGHT))

        tab_button_base = pg.Rect(
            (self.MARGIN_X, self.TAB_BUTTONS_POS_Y),
            (self._BUTTON_WIDTH, self.TAB_BUTTON_HEIGHT),
        )
        for i, tab_name in enumerate(["Units", "Buildings", "Defensive"]):
            self.tab_buttons[tab_name] = tab_button_base.move(
                0, i * (self.TAB_BUTTON_HEIGHT + self.BUTTON_SPACING_Y)
            )
            self.buy_buttons[tab_name] = {}

        action_button_base = pg.Rect(
            (self.MARGIN_X, 0),
            (self._BUTTON_WIDTH, self.ACTION_BUTTON_HEIGHT),
        )
        buy_button_base = action_button_base.move(0, self.BUY_BUTTONS_POS_Y)
        for i, (cls, req) in enumerate(
            [
                (
                    Tank,
                    lambda: any(
                        b.team == self.headquarters.team
                        and isinstance(b, WarFactory)
                        and b.health > 0
                        for b in buildings
                    ),
                ),
                (
                    Infantry,
                    lambda: any(
                        b.team == self.headquarters.team
                        and isinstance(b, Barracks)
                        and b.health > 0
                        for b in buildings
                    ),
                ),
                (
                    Harvester,
                    lambda: any(
                        b.team == self.headquarters.team
                        and isinstance(b, WarFactory)
                        and b.health > 0
                        for b in buildings
                    ),
                ),
            ]
        ):
            self.buy_buttons["Units"][cls] = (
                buy_button_base.move(
                    0, i * (self.ACTION_BUTTON_HEIGHT + self.BUTTON_SPACING_Y)
                ),
                lambda: req,
            )

        for i, cls in enumerate([Barracks, WarFactory, PowerPlant, Headquarters]):
            self.buy_buttons["Buildings"][cls] = (
                buy_button_base.move(
                    0, i * (self.ACTION_BUTTON_HEIGHT + self.BUTTON_SPACING_Y)
                ),
                lambda: True,
            )
        self.buy_buttons["Defensive"] = {Turret: (buy_button_base, lambda: True)}
        self.sell_button = action_button_base.move(0, self.SELL_BUTTON_POS_Y)
        self.unit_button_labels = {
            Tank: "Tank",
            Infantry: "Infantry",
            Harvester: "Harvester",
            Barracks: "Barracks",
            WarFactory: "War Factory",
            PowerPlant: "Power Plant",
            Headquarters: "Headquarters",
            Turret: "Turret",
        }

    def _local_pos(self, screen_pos: tuple[int, int]) -> tuple[int, int]:
        """Convert screen position to local position."""
        return screen_pos[0] - SCREEN_WIDTH + self.WIDTH, screen_pos[1]

    def _draw_iron(self, *, y_pos: int) -> None:
        self.surface.blit(
            font.render(
                f"Iron: {self.headquarters.iron}",
                color=pg.Color("white"),
                antialias=True,
            ),
            (self.MARGIN_X, y_pos),
        )

    def _draw_power(self, *, y_pos: int) -> None:
        color_ = (
            pg.Color("green") if self.headquarters.has_enough_power else pg.Color("red")
        )
        self.surface.blit(
            font.render(
                f"Power: {self.headquarters.power_output}"
                f"/{self.headquarters.power_usage}",
                color=color_,
                antialias=True,
            ),
            (self.MARGIN_X, y_pos),
        )

    def _draw_tab_button(self, *, rect: pg.Rect, label: str) -> None:
        pg.draw.rect(
            self.surface,
            self.ACTIVE_TAB_COLOR
            if label == self.current_tab
            else self.INACTIVE_TAB_COLOR,
            rect,
            border_radius=self.BUTTON_RADIUS,
        )
        self.surface.blit(
            font.render(label, color=pg.Color("white"), antialias=True),
            (rect.x + 10, rect.y + 10),
        )

    def _draw_buy_button(
        self, *, rect: pg.Rect, unit_cls: type[GameObject], req_fn: Callable
    ) -> None:
        can_produce = self.headquarters.iron >= unit_cls.COST and req_fn
        buy_fill_color = (
            self.ACTION_ALLOWED_COLOR if can_produce else self.ACTION_BLOCKED_COLOR
        )
        pg.draw.rect(
            self.surface, buy_fill_color, rect, border_radius=self.BUTTON_RADIUS
        )
        self.surface.blit(
            font.render(
                f"{self.unit_button_labels[unit_cls]} ({unit_cls.COST})",
                color=pg.Color("white"),
                antialias=True,
            ),
            (rect.x + 10, rect.y + 10),
        )

    def _draw_sell_button(self, *, rect: pg.Rect) -> None:
        sell_fill_color = (
            self.ACTION_ALLOWED_COLOR
            if selected_building
            else self.ACTION_BLOCKED_COLOR
        )
        pg.draw.rect(
            self.surface,
            sell_fill_color,
            rect,
            border_radius=self.BUTTON_RADIUS,
        )
        self.surface.blit(
            font.render("Sell", color=pg.Color("white"), antialias=True),
            (self.sell_button.x + 10, self.sell_button.y + 10),
        )

    def _draw_production_queue(self, y_pos: int) -> None:
        if self.headquarters.production_timer and self.headquarters.production_queue:
            progress = (
                1
                - self.headquarters.production_timer
                / self.headquarters.get_production_time(
                    self.headquarters.production_queue[0]
                )
            )
            draw_progress_bar(
                surface=self.surface,
                bar_color=pg.Color("green"),
                rect=pg.Rect(
                    (self.MARGIN_X, y_pos),
                    (self._BUTTON_WIDTH, 10),
                ),
                progress=progress,
            )

        for i, unit_class in enumerate(self.headquarters.production_queue[:5]):
            self.surface.blit(
                font.render(
                    f"{unit_class.__name__} ({unit_class.COST})",
                    color=pg.Color("white"),
                    antialias=True,
                ),
                (self.MARGIN_X, (y_pos + 20) + i * 25),
            )

    def _draw_pending_building(
        self, *, surface_: pg.Surface, mouse_pos: tuple[int, int]
    ) -> None:
        if not self.headquarters.pending_building:
            raise TypeError("No pending building")

        pending_building_cls_ = self.headquarters.pending_building
        world_pos = snap_to_grid(camera.screen_to_world(mouse_pos))
        temp_surface = pg.Surface(pending_building_cls_.SIZE, pg.SRCALPHA)
        temp_surface.fill(
            GDI_COLOR if self.headquarters.team == Team.GDI else NOD_COLOR
        )
        temp_surface.set_alpha(100)
        color_ = self.PLACEMENT_INVALID_COLOR
        if is_valid_building_position(
            position=world_pos,
            team=self.headquarters.team,
            new_building_cls=pending_building_cls_,
            buildings=buildings,
        ):
            color_ = self.PLACEMENT_VALID_COLOR

        pg.draw.rect(
            temp_surface,
            color_,
            ((0, 0), pending_building_cls_.SIZE),
            width=3,
        )
        surface_.blit(
            temp_surface,
            (
                mouse_pos[0] - pending_building_cls_.SIZE[0] // 2,
                mouse_pos[1] - pending_building_cls_.SIZE[1] // 2,
            ),
        )

    def draw(self, surface_: pg.Surface) -> None:
        """Draw to the `surface_`."""
        self.surface.fill(self.FILL_COLOR)
        pg.draw.rect(self.surface, self.LINE_COLOR, self.surface.get_rect(), width=2)
        self._draw_iron(y_pos=self.IRON_POS_Y)
        self._draw_power(y_pos=self.POWER_POS_Y)

        for tab_name, rect in self.tab_buttons.items():
            self._draw_tab_button(rect=rect, label=tab_name)

        for unit_cls, info in self.buy_buttons[self.current_tab].items():
            rect, req_fn = info
            self._draw_buy_button(rect=rect, unit_cls=unit_cls, req_fn=req_fn)

        self._draw_production_queue(y_pos=self.PRODUCTION_QUEUE_POS_Y)
        self._draw_sell_button(rect=self.sell_button)

        if self.headquarters.pending_building:
            self._draw_pending_building(surface_=surface_, mouse_pos=pg.mouse.get_pos())

        surface_.blit(source=self.surface, dest=(SCREEN_WIDTH - self.WIDTH, 0))

    def handle_click(self, screen_pos: tuple[int, int]) -> bool:
        local_pos = self._local_pos(screen_pos)
        global selected_building
        for tab_name, rect in self.tab_buttons.items():
            if rect.collidepoint(local_pos):
                self.current_tab = tab_name
                return True

        if len(self.headquarters.production_queue) >= self.MAX_PRODUCTION_QUEUE_LENGTH:
            return False

        for unit_cls, info in self.buy_buttons[self.current_tab].items():
            rect, req_fn = info
            if (
                rect.collidepoint(local_pos)
                and self.headquarters.iron >= unit_cls.COST
                and req_fn()
            ):
                self.headquarters.production_queue.append(unit_cls)
                self.headquarters.iron -= unit_cls.COST
                if not self.headquarters.production_timer:
                    self.production_timer = self.headquarters.get_production_time(
                        unit_cls
                    )
                return True

        if self.sell_button.collidepoint(local_pos) and selected_building:
            self.headquarters.iron += selected_building.COST // 2
            selected_building.kill()
            selected_building = None
            return True

        return False


class GameConsole:
    def __init__(self) -> None:
        self.rect = pg.Rect(
            0, SCREEN_HEIGHT - CONSOLE_HEIGHT, SCREEN_WIDTH, CONSOLE_HEIGHT
        )
        self.lines: list[str] = []
        self.max_lines = 20
        self.scroll_offset = 0
        self.scroll_speed = 20
        self.selected_text = ""

    def log(self, message: str) -> None:
        self.lines.append(message)
        if len(self.lines) > self.max_lines:
            self.lines.pop(0)

    def draw(self, screen: pg.Surface) -> None:
        pg.draw.rect(screen, (40, 40, 40), self.rect)  # Darker console
        pg.draw.rect(screen, (80, 80, 80), self.rect, 2)
        visible_lines = self.lines[self.scroll_offset :]
        for i, line in enumerate(visible_lines):
            if i >= self.max_lines:
                break
            text_surface = console_font.render(line, True, (200, 200, 200))
            screen.blit(text_surface, (self.rect.x + 5, self.rect.y + 5 + i * 18))
        scroll_height = self.rect.height - 20
        scroll_pos = (
            (self.scroll_offset / max(1, len(self.lines) - self.max_lines))
            * (scroll_height - 20)
            if len(self.lines) > self.max_lines
            else 0
        )
        pg.draw.rect(
            screen,
            (150, 150, 150),
            (self.rect.right - 15, self.rect.y + 5 + scroll_pos, 10, 20),
        )

    def handle_event(self, event: pg.Event) -> None:
        mouse_pos = pg.mouse.get_pos()
        if event.type == pg.MOUSEWHEEL:
            if self.rect.collidepoint(mouse_pos):
                max_scroll = max(0, len(self.lines) - self.max_lines)
                scroll_amount = event.y * self.scroll_speed
                self.scroll_offset = max(
                    0, min(max_scroll, self.scroll_offset - scroll_amount)
                )
                print(
                    f"Console scroll detected: y={event.y}, scroll_offset={self.scroll_offset}"
                )
        elif event.type == pg.KEYDOWN:
            if self.rect.collidepoint(mouse_pos):
                max_scroll = max(0, len(self.lines) - self.max_lines)
                if event.key == pg.K_UP:
                    self.scroll_offset = max(0, self.scroll_offset - 1)
                    print(f"Console scroll up: scroll_offset={self.scroll_offset}")
                elif event.key == pg.K_DOWN:
                    self.scroll_offset = min(max_scroll, self.scroll_offset + 1)
                    print(f"Console scroll down: scroll_offset={self.scroll_offset}")
        elif event.type == pg.MOUSEBUTTONDOWN and event.button == 1:
            if self.rect.collidepoint(event.pos):
                start_y = self.rect.y + 5
                line_idx = (event.pos[1] - start_y) // 18 + self.scroll_offset
                if 0 <= line_idx < len(self.lines):
                    self.selected_text = self.lines[line_idx]
                    try:
                        pg.scrap.put_text(pg.SCRAP_TEXT)
                        print(f"Copied to clipboard: {self.selected_text}")
                    except Exception as e:
                        print(f"Failed to copy to clipboard: {e}")


class AI:
    def __init__(
        self,
        headquarters: Headquarters,
        units_group,
        all_units_group,
        iron_fields,
        buildings,
    ) -> None:
        self.headquarters = headquarters
        self.units = units_group
        self.all_units = all_units_group
        self.iron_fields = iron_fields
        self.buildings = buildings
        self.timer = 0
        self.action_interval = 50
        self.wave_timer = 0
        self.wave_interval = random.randint(150, 250)
        self.wave_number = 0
        self.max_wave_size = 25
        self.target_ratio = {"Harvester": 4, "Infantry": 6, "Tank": 3, "Turret": 3}
        self.scale_factor = 1.8
        self.state = "Build Up"
        self.player_base_size = 0
        self.defense_cooldown = 0
        self.scout_targets: list[Coordinate] = []
        self.iron_income_rate: float = 0
        self.last_scout_update = 0
        self.scout_interval = 200
        self.surprise_attack_cooldown = 0

    def evaluate_game_state(self) -> dict[str, int]:
        self.player_base_size = len(
            [u for u in self.all_units if u.team == Team.GDI]
        ) + len([b for b in self.buildings if b.team == Team.GDI])
        player_harvesters = len(
            [
                u
                for u in self.all_units
                if u.team == Team.GDI and isinstance(u, Harvester)
            ]
        )
        player_tanks = len(
            [u for u in self.all_units if u.team == Team.GDI and isinstance(u, Tank)]
        )
        player_infantry = len(
            [
                u
                for u in self.all_units
                if u.team == Team.GDI and isinstance(u, Infantry)
            ]
        )
        player_turrets = len(
            [b for b in self.buildings if b.team == Team.GDI and isinstance(b, Turret)]
        )
        self.iron_income_rate = (
            sum(h.iron for h in self.units if isinstance(h, Harvester))
            / max(1, len([h for h in self.units if isinstance(h, Harvester)]))
            * 60
            / 40
        )
        self.state = (
            "Broke"
            if self.headquarters.iron < 300 or self.iron_income_rate < 50
            else "Attacked"
            if self.headquarters.health < self.headquarters.max_health * 0.6
            or self.defense_cooldown > 0
            else "Threatened"
            if any(
                u.team == Team.GDI
                and math.sqrt(
                    (u.rect.centerx - self.headquarters.rect.centerx) ** 2
                    + (u.rect.centery - self.headquarters.rect.centery) ** 2
                )
                < 500
                for u in self.all_units
            )
            else "Aggressive"
            if self.wave_number >= 2 or self.player_base_size > 8
            else "Build Up"
        )
        return {
            "player_harvesters": player_harvesters,
            "player_tanks": player_tanks,
            "player_infantry": player_infantry,
            "player_turrets": player_turrets,
        }

    def update_scouting(self) -> None:
        if self.last_scout_update <= 0:
            if not self.scout_targets:
                self.scout_targets = [
                    (f.rect.centerx, f.rect.centery) for f in self.iron_fields
                ] + [(MAP_WIDTH // 2, MAP_HEIGHT // 2)]
                gdi_hq = next(
                    (
                        b
                        for b in self.buildings
                        if b.team == Team.GDI and isinstance(b, Headquarters)
                    ),
                    None,
                )
                if gdi_hq:
                    self.scout_targets.append(gdi_hq.rect.center)
            for scout in [
                u for u in self.units if isinstance(u, Infantry) and not u.target
            ][:3]:
                if self.scout_targets:
                    scout.target = self.scout_targets.pop(0)
                    scout.target_unit = None
            self.last_scout_update = self.scout_interval
        else:
            self.last_scout_update -= 1

    def prioritize_targets(self, unit) -> Building | None:
        targets = []
        for target in self.all_units:
            if target.team != unit.team and target.health > 0:
                dist = math.sqrt(
                    (unit.rect.centerx - target.rect.centerx) ** 2
                    + (unit.rect.centery - target.rect.centery) ** 2
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
                    (unit.rect.centerx - building.rect.centerx) ** 2
                    + (unit.rect.centery - building.rect.centery) ** 2
                )
                priority = (
                    2.5
                    if isinstance(building, Headquarters)
                    else 2
                    if isinstance(building, Turret)
                    else 1
                )
                targets.append((building, dist, priority))
        targets.sort(key=lambda x: x[1] / x[2])
        return targets[0][0] if targets and targets[0][1] < 250 else None

    def find_valid_building_position(self, building_cls: type[Building]) -> Coordinate:
        closest_field = min(
            self.iron_fields,
            key=lambda f: math.sqrt(
                (f.rect.centerx - self.headquarters.rect.centerx) ** 2
                + (f.rect.centery - self.headquarters.rect.centery) ** 2
            ),
            default=None,
        )
        for building in self.buildings:
            if building.team == self.headquarters.team and building.health > 0:
                for angle in range(0, 360, 20):
                    x = building.rect.centerx + math.cos(math.radians(angle)) * 120
                    y = building.rect.centery + math.sin(math.radians(angle)) * 120
                    snapped_position = snap_to_grid((x, y))
                    if is_valid_building_position(
                        position=snapped_position,
                        team=self.headquarters.team,
                        new_building_cls=building_cls,
                        buildings=buildings,
                    ):
                        if (
                            closest_field
                            and math.sqrt(
                                (x - closest_field.rect.centerx) ** 2
                                + (y - closest_field.rect.centery) ** 2
                            )
                            < 600
                        ):
                            return x, y
                        elif not closest_field:
                            return x, y

        return snap_to_grid(self.headquarters.rect.center)

    def produce_units(self, player_info) -> None:
        current_units = {
            "Harvester": len([u for u in self.units if isinstance(u, Harvester)]),
            "Infantry": len([u for u in self.units if isinstance(u, Infantry)]),
            "Tank": len([u for u in self.units if isinstance(u, Tank)]),
            "Turret": len(
                [
                    b
                    for b in self.buildings
                    if isinstance(b, Turret) and b.team == self.headquarters.team
                ]
            ),
            "PowerPlant": len(
                [
                    b
                    for b in self.buildings
                    if isinstance(b, PowerPlant) and b.team == self.headquarters.team
                ]
            ),
            "Barracks": len(
                [
                    b
                    for b in self.buildings
                    if isinstance(b, Barracks)
                    and b.team == self.headquarters.team
                    and b.health > 0
                ]
            )
            + len([b for b in self.headquarters.production_queue if b == Barracks]),
            "WarFactory": len(
                [
                    b
                    for b in self.buildings
                    if isinstance(b, WarFactory)
                    and b.team == self.headquarters.team
                    and b.health > 0
                ]
            )
            + len([b for b in self.headquarters.production_queue if b == WarFactory]),
        }
        target_units = {
            unit: int(self.target_ratio[unit] * self.scale_factor)
            for unit in self.target_ratio
        }
        target_units["PowerPlant"] = max(1, (current_units["Harvester"] + 1) // 2)
        target_units["Barracks"] = 1
        target_units["WarFactory"] = 1
        has_barracks = current_units["Barracks"] > 0
        has_warfactory = current_units["WarFactory"] > 0
        total_military = (
            current_units["Infantry"] + current_units["Tank"] + current_units["Turret"]
        )
        iron = self.headquarters.iron
        console.log(
            f"AI production check: Iron = {iron}, Has Barracks = {has_barracks}, Has WarFactory = {has_warfactory}"
        )

        if not has_barracks and iron >= Barracks.COST:
            self.headquarters.production_queue.append(Barracks)
            iron -= Barracks.COST
            self.headquarters.iron = iron
            console.log(
                f"AI produced Barracks, cost: {Barracks.COST}, new iron: {self.headquarters.iron}"
            )
            return
        elif not has_warfactory and iron >= WarFactory.COST:
            self.headquarters.production_queue.append(WarFactory)
            iron -= WarFactory.COST
            self.headquarters.iron = iron
            console.log(
                f"AI produced WarFactory, cost: {WarFactory.COST}, new iron: {self.headquarters.iron}"
            )
            return
        elif (
            self.headquarters.has_enough_power
            and iron >= PowerPlant.COST
            and current_units["PowerPlant"] < target_units["PowerPlant"]
        ):
            self.headquarters.production_queue.append(PowerPlant)
            iron -= PowerPlant.COST
            self.headquarters.iron = iron
            console.log(
                f"AI produced PowerPlant, cost: {PowerPlant.COST}, new iron: {self.headquarters.iron}"
            )
            return

        if (
            (
                current_units["Harvester"]
                < min(target_units["Harvester"], player_info["player_harvesters"] + 1)
                or self.iron_income_rate < 50
            )
            and iron >= Harvester.COST
            and has_warfactory
        ):
            self.headquarters.production_queue.append(Harvester)
            iron -= Harvester.COST
            self.headquarters.iron = iron
            console.log(
                f"AI produced Harvester, cost: {Harvester.COST}, new iron: {self.headquarters.iron}"
            )
            return

        if iron <= 0:
            console.log("AI production halted: Insufficient iron")
            return

        production_options: list[tuple[type[GameObject], int]] = []
        if self.state in ["Build Up", "Aggressive"]:
            if (
                total_military < 6
                and has_barracks
                and iron >= Infantry.COST
                and current_units["Infantry"] < target_units["Infantry"]
            ):
                production_options.append((Infantry, Infantry.COST))
            if (
                total_military < 6
                and has_warfactory
                and iron >= Tank.COST
                and current_units["Tank"] < target_units["Tank"]
            ):
                production_options.append((Tank, Tank.COST))
            if iron >= Turret.COST and current_units["Turret"] < target_units["Turret"]:
                production_options.append((Turret, Turret.COST))
            if (
                has_barracks
                and iron >= Infantry.COST
                and current_units["Infantry"] < target_units["Infantry"]
            ):
                production_options.append((Infantry, Infantry.COST))
            if (
                has_warfactory
                and iron >= Tank.COST
                and current_units["Tank"] < target_units["Tank"]
            ):
                production_options.append((Tank, Tank.COST))
            if (
                current_units["Harvester"] < target_units["Harvester"]
                and iron >= Harvester.COST
                and has_warfactory
            ):
                production_options.append((Harvester, Harvester.COST))
            if (
                current_units["PowerPlant"] < target_units["PowerPlant"]
                and iron >= PowerPlant.COST
            ):
                production_options.append((PowerPlant, PowerPlant.COST))
            if (
                current_units["Barracks"] < 2
                and iron >= Barracks.COST
                and total_military >= 6
            ):
                production_options.append((Barracks, Barracks.COST))
            if (
                current_units["WarFactory"] < 2
                and iron >= WarFactory.COST
                and total_military >= 6
            ):
                production_options.append((WarFactory, WarFactory.COST))
            if iron >= Headquarters.COST and current_units["Harvester"] >= 2:
                production_options.append((Headquarters, Headquarters.COST))

            if production_options:
                unit_class, cost = random.choice(production_options)
                self.headquarters.production_queue.append(unit_class)
                iron -= cost
                self.headquarters.iron = iron
                console.log(
                    f"AI produced {unit_class.__name__}, cost: {cost}, new iron: {self.headquarters.iron}"
                )

        elif self.state in ["Attacked", "Threatened"]:
            if iron >= Turret.COST and current_units["Turret"] < target_units["Turret"]:
                production_options.append((Turret, Turret.COST))
            if (
                has_warfactory
                and iron >= Tank.COST
                and current_units["Tank"] < target_units["Tank"]
            ):
                production_options.append((Tank, Tank.COST))
            if (
                has_barracks
                and iron >= Infantry.COST
                and current_units["Infantry"] < target_units["Infantry"]
            ):
                production_options.append((Infantry, Infantry.COST))
            if (
                current_units["Harvester"]
                < min(target_units["Harvester"], player_info["player_harvesters"] + 1)
                and iron >= Harvester.COST
                and has_warfactory
            ):
                production_options.append((Harvester, Harvester.COST))
            if (
                current_units["PowerPlant"] < target_units["PowerPlant"]
                and iron >= PowerPlant.COST
            ):
                production_options.append((PowerPlant, PowerPlant.COST))

            if production_options:
                unit_class, cost = random.choice(production_options)
                self.headquarters.production_queue.append(unit_class)
                iron -= cost
                self.headquarters.iron = iron
                console.log(
                    f"AI produced {unit_class.__name__}, cost: {cost}, new iron: {self.headquarters.iron}"
                )

        elif (
            self.state == "Broke"
            and has_warfactory
            and iron >= Harvester.COST
            and current_units["Harvester"]
            < min(target_units["Harvester"], player_info["player_harvesters"] + 1)
        ):
            self.headquarters.production_queue.append(Harvester)
            iron -= Harvester.COST
            self.headquarters.iron = iron
            console.log(
                f"AI produced Harvester, cost: {Harvester.COST}, new iron: {self.headquarters.iron}"
            )

        if (
            self.headquarters.production_queue
            and not self.headquarters.production_timer
        ):
            self.headquarters.production_timer = self.headquarters.get_production_time(
                self.headquarters.production_queue[0]
            )
        if (
            self.headquarters.pending_building
            and not self.headquarters.pending_building_pos
        ):
            x, y = self.find_valid_building_position(self.headquarters.pending_building)
            self.headquarters.pending_building_pos = x, y
            self.headquarters.place_building(x, y, self.headquarters.pending_building)

    def coordinate_attack(self, surprise: bool = False) -> None:
        self.wave_timer = 0
        self.wave_number += 1
        wave_size = (
            min(8 + self.wave_number * 2, self.max_wave_size)
            if not surprise
            else min(12 + self.wave_number, self.max_wave_size)
        )
        self.wave_interval = random.randint(150, 250)
        combat_units = [
            u for u in self.units if isinstance(u, (Tank, Infantry)) and not u.target
        ]
        if not combat_units:
            return
        tactics = (
            ["balanced", "flank", "all_in"]
            if self.state == "Aggressive" or surprise
            else ["all_in", "defensive"]
            if self.state in ["Threatened", "Attacked"]
            else ["balanced", "flank", "all_in"]
        )
        tactic = random.choice(tactics)
        if tactic == "balanced":
            infantry_count = min(
                int(wave_size * 0.6),
                len([u for u in combat_units if isinstance(u, Infantry)]),
            )
            tank_count = min(
                int(wave_size * 0.4),
                len([u for u in combat_units if isinstance(u, Tank)]),
            )
            attack_units = [u for u in combat_units if isinstance(u, Infantry)][
                :infantry_count
            ] + [u for u in combat_units if isinstance(u, Tank)][:tank_count]
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
            gdi_hq = next(
                (
                    b
                    for b in self.buildings
                    if b.team == Team.GDI and isinstance(b, Headquarters)
                ),
                None,
            )
            if gdi_hq:
                group_size = len(attack_units) // 2
                for i, unit in enumerate(attack_units):
                    offset_x = (
                        random.uniform(80, 120)
                        if i < group_size
                        else random.uniform(-120, -80)
                    )
                    offset_y = (
                        random.uniform(80, 120)
                        if i < group_size
                        else random.uniform(-120, -80)
                    )
                    unit.target = (
                        gdi_hq.rect.centerx + offset_x,
                        gdi_hq.rect.centery + offset_y,
                    )
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
        player_info = self.evaluate_game_state()
        self.update_scouting()
        if self.timer >= self.action_interval:
            self.timer = 0
            self.produce_units(player_info)
        if (
            self.surprise_attack_cooldown <= 0
            and player_info["player_tanks"]
            + player_info["player_infantry"]
            + player_info["player_turrets"]
            < 5
            and random.random() < 0.1
        ):
            self.coordinate_attack(surprise=True)
            self.surprise_attack_cooldown = 300
        elif self.wave_timer >= self.wave_interval:
            self.coordinate_attack()


if __name__ == "__main__":
    pg.init()
    screen = pg.display.set_mode((SCREEN_WIDTH, SCREEN_HEIGHT))
    clock = pg.time.Clock()
    font = pg.font.SysFont(None, 24)
    console_font = pg.font.SysFont(None, 18)

    player_units: pg.sprite.Group = pg.sprite.Group()
    enemy_units: pg.sprite.Group = pg.sprite.Group()
    all_units: pg.sprite.Group = pg.sprite.Group()
    iron_fields: pg.sprite.Group = pg.sprite.Group()
    buildings: pg.sprite.Group = pg.sprite.Group()
    projectiles: pg.sprite.Group = pg.sprite.Group()
    particles: pg.sprite.Group = pg.sprite.Group()
    selected_units: pg.sprite.Group = pg.sprite.Group()

    gdi_headquarters = Headquarters(300, 300, Team.GDI)
    nod_headquarters = Headquarters(MAP_WIDTH - 300, MAP_HEIGHT - 300, Team.NOD)
    nod_headquarters.iron = 1500
    interface = ProductionInterface(headquarters=gdi_headquarters)
    console = GameConsole()
    fog_of_war = FogOfWar(map_size=(MAP_WIDTH, MAP_HEIGHT), tile_size=TILE_SIZE)

    selected_building = None
    selecting = False
    select_start = None
    select_rect = None
    camera = Camera(MAP_WIDTH, MAP_HEIGHT)
    base_map = pg.Surface((MAP_WIDTH, MAP_HEIGHT))
    # Improved map with grass texture
    for x in range(0, MAP_WIDTH, TILE_SIZE):
        for y in range(0, MAP_HEIGHT, TILE_SIZE):
            color = (0, random.randint(100, 150), 0)
            pg.draw.rect(base_map, color, (x, y, TILE_SIZE, TILE_SIZE))
            if random.random() < 0.1:
                pg.draw.circle(
                    base_map,
                    (0, 80, 0),
                    (x + TILE_SIZE // 2, y + TILE_SIZE // 2),
                    TILE_SIZE // 4,
                )  # Dark spots

    ai = AI(nod_headquarters, enemy_units, all_units, iron_fields, buildings)

    player_units.add(Infantry(350, 300, Team.GDI))
    player_units.add(Infantry(370, 300, Team.GDI))
    player_units.add(Infantry(390, 300, Team.GDI))
    player_units.add(Harvester(400, 400, Team.GDI, gdi_headquarters))

    enemy_units.add(Infantry(2050, 1200, Team.NOD))
    enemy_units.add(Infantry(2070, 1200, Team.NOD))
    enemy_units.add(Infantry(2090, 1200, Team.NOD))
    enemy_units.add(Harvester(2200, 1300, Team.NOD, nod_headquarters))

    all_units.add(player_units, enemy_units)
    buildings.add(gdi_headquarters, nod_headquarters)
    for _ in range(40):
        iron_fields.add(
            IronField(
                random.randint(100, MAP_WIDTH - 100),
                random.randint(100, MAP_HEIGHT - 100),
            )
        )

    running = True
    while running:
        for event in pg.event.get():
            if event.type == pg.QUIT:
                running = False
            elif event.type == pg.MOUSEBUTTONDOWN:
                world_x, world_y = camera.screen_to_world(event.pos)
                target_x, target_y = event.pos
                if event.button == 1:
                    if gdi_headquarters.pending_building:
                        snapped_position = snap_to_grid((world_x, world_y))
                        if is_valid_building_position(
                            position=snapped_position,
                            team=gdi_headquarters.team,
                            new_building_cls=gdi_headquarters.pending_building,
                            buildings=buildings,
                        ):
                            gdi_headquarters.place_building(
                                world_x, world_y, gdi_headquarters.pending_building
                            )
                        continue

                    if interface.handle_click(event.pos):
                        continue

                    clicked_building = next(
                        (
                            b
                            for b in buildings
                            if b.team == Team.GDI
                            and camera.apply(b.rect).collidepoint(target_x, target_y)
                        ),
                        None,
                    )
                    if clicked_building:
                        selected_building = clicked_building
                    else:
                        selected_building = None
                        selecting = True
                        select_start = event.pos
                        select_rect = pg.Rect(target_x, target_y, 0, 0)
                elif event.button == 3:
                    if gdi_headquarters.pending_building:
                        gdi_headquarters.pending_building = (
                            gdi_headquarters.pending_building_pos
                        ) = None
                        if (
                            gdi_headquarters.production_queue
                            and gdi_headquarters.has_enough_power
                        ):
                            gdi_headquarters.production_timer = (
                                gdi_headquarters.get_production_time(
                                    gdi_headquarters.production_queue[0]
                                )
                            )
                        continue
                    clicked_field = next(
                        (
                            f
                            for f in iron_fields
                            if camera.apply(f.rect).collidepoint(target_x, target_y)
                        ),
                        None,
                    )
                    clicked_enemy_unit = next(
                        (
                            u
                            for u in all_units
                            if u.team != Team.GDI
                            and camera.apply(u.rect).collidepoint(target_x, target_y)
                        ),
                        None,
                    )
                    clicked_enemy_building = next(
                        (
                            b
                            for b in buildings
                            if b.team != Team.GDI
                            and camera.apply(b.rect).collidepoint(target_x, target_y)
                        ),
                        None,
                    )
                    if selected_units:
                        group_center = (
                            sum(u.rect.centerx for u in selected_units)
                            / len(selected_units),
                            sum(u.rect.centery for u in selected_units)
                            / len(selected_units),
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
            elif event.type == pg.MOUSEMOTION and selecting:
                current_pos = event.pos
                if not select_start:
                    raise TypeError(
                        "No selection rect start point"
                    )  # Temporary handling, review later

                select_rect = pg.Rect(
                    min(select_start[0], current_pos[0]),
                    min(select_start[1], current_pos[1]),
                    abs(current_pos[0] - select_start[0]),
                    abs(current_pos[1] - select_start[1]),
                )
            elif event.type == pg.MOUSEBUTTONUP and event.button == 1 and selecting:
                if not select_start:
                    raise TypeError(
                        "No selection rect start point"
                    )  # Temporary handling, review later

                selecting = False
                for unit in player_units:
                    unit.selected = False
                selected_units.empty()
                world_start = camera.screen_to_world(select_start)
                world_end = camera.screen_to_world(event.pos)
                world_rect = pg.Rect(
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

        camera.update(selected_units, pg.mouse.get_pos(), interface.surface.get_rect())
        all_units.update()
        iron_fields.update()
        buildings.update()
        projectiles.update()
        particles.update()
        handle_collisions(all_units)
        handle_attacks(player_units, all_units, buildings, projectiles, particles)
        handle_attacks(enemy_units, all_units, buildings, projectiles, particles)
        handle_projectiles(projectiles, all_units, buildings)
        ai.update()
        fog_of_war.update_visibility(player_units, buildings, Team.GDI)
        draw(screen)
        for obj in all_units:
            if hasattr(obj, "under_attack") and obj.under_attack:
                obj.under_attack = False

        pg.display.flip()
        clock.tick(60)

    pg.quit()

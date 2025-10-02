from __future__ import annotations

import pygame as pg

from src.building import Building
from src.constants import Team


class PowerPlant(Building):
    COST = 300
    POWER_OUTPUT = 100
    POWER_USAGE = 0

    def __init__(self, *, x: float, y: float, team: Team) -> None:
        super().__init__(
            x=x,
            y=y,
            team=team,
            color=pg.Color(130, 130, 0) if team == Team.GDI else pg.Color(130, 0, 0),
        )
        self.max_health = 500
        self.health = self.max_health

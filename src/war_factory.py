from __future__ import annotations

import pygame as pg

from src.building import Building
from src.constants import Team


class WarFactory(Building):
    COST = 1000
    POWER_USAGE = 35

    def __init__(self, *, x: float, y: float, team: Team, font: pg.Font) -> None:
        super().__init__(
            x=x,
            y=y,
            team=team,
            color=pg.Color(170, 170, 0) if team == Team.GDI else pg.Color(170, 0, 0),
            font=font,
        )
        self.max_health = 800
        self.health = self.max_health

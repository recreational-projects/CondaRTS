from __future__ import annotations

import pygame as pg

from src.building import Building
from src.constants import Team


class Barracks(Building):
    COST = 500
    POWER_USAGE = 25

    def __init__(self, *, x: float, y: float, team: Team, font: pg.Font) -> None:
        super().__init__(
            x=x,
            y=y,
            team=team,
            color=pg.Color(150, 150, 0) if team == Team.GDI else pg.Color(150, 0, 0),
            font=font,
        )
        self.max_health = 600
        self.health = self.max_health

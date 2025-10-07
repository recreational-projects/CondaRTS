from __future__ import annotations

import pygame as pg

from src.building import Building
from src.constants import Team


class WarFactory(Building):
    COST = 1000
    POWER_USAGE = 35

    def __init__(
        self, *, position: pg.typing.SequenceLike, team: Team, font: pg.Font
    ) -> None:
        super().__init__(
            position=position,
            team=team,
            color=pg.Color(170, 170, 0) if team == Team.GDI else pg.Color(170, 0, 0),
            font=font,
        )
        self.max_health = 800
        self.health = self.max_health

from __future__ import annotations

from src.building import Building
from src.constants import Team


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

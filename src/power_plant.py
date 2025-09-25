from __future__ import annotations

from src.building import Building
from src.constants import Team


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

"""Constants used by `src/` modules."""

from enum import Enum

SCREEN_WIDTH, SCREEN_HEIGHT = 1920, 1080
MAP_WIDTH, MAP_HEIGHT = 1600, 800
TILE_SIZE = 32
CONSOLE_HEIGHT = 200
BUILDING_CONSTRUCTION_RANGE = 160


class Team(Enum):
    GDI = "gdi"
    NOD = "nod"

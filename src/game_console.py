from __future__ import annotations

from dataclasses import dataclass
from dataclasses import field as dataclass_field
from typing import ClassVar

import pygame as pg

from src.constants import CONSOLE_HEIGHT, SCREEN_HEIGHT, SCREEN_WIDTH


@dataclass(kw_only=True)
class GameConsole:
    MAX_LINES: ClassVar[int] = 20
    SCROLL_SPEED: ClassVar[int] = 20

    rect: pg.Rect = dataclass_field(init=False)
    font: pg.Font = dataclass_field(init=False)
    lines: list[str] = dataclass_field(init=False, default_factory=list)
    selected_text: str = dataclass_field(init=False)
    scroll_offset: int = dataclass_field(init=False)

    def __post_init__(self) -> None:
        self.rect = pg.Rect(
            0, SCREEN_HEIGHT - CONSOLE_HEIGHT, SCREEN_WIDTH, CONSOLE_HEIGHT
        )
        self.font = pg.font.SysFont(None, 18)
        self.selected_text = ""
        self.scroll_offset = 0

    def log(self, message: str) -> None:
        self.lines.append(message)
        if len(self.lines) > self.MAX_LINES:
            self.lines.pop(0)

    def draw(self, screen: pg.Surface) -> None:
        pg.draw.rect(screen, (40, 40, 40), self.rect)  # Darker console
        pg.draw.rect(screen, (80, 80, 80), self.rect, 2)
        visible_lines = self.lines[self.scroll_offset :]
        for i, line in enumerate(visible_lines):
            if i >= self.MAX_LINES:
                break

            text_surface = self.font.render(line, True, (200, 200, 200))
            screen.blit(text_surface, (self.rect.x + 5, self.rect.y + 5 + i * 18))

        scroll_height = self.rect.height - 20
        scroll_pos = (
            (self.scroll_offset / max(1, len(self.lines) - self.MAX_LINES))
            * (scroll_height - 20)
            if len(self.lines) > self.MAX_LINES
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
                max_scroll = max(0, len(self.lines) - self.MAX_LINES)
                scroll_amount = event.y * self.SCROLL_SPEED
                self.scroll_offset = max(
                    0, min(max_scroll, self.scroll_offset - scroll_amount)
                )
                print(
                    f"Console scroll detected: y={event.y}, scroll_offset={self.scroll_offset}"
                )

        elif event.type == pg.KEYDOWN:
            if self.rect.collidepoint(mouse_pos):
                max_scroll = max(0, len(self.lines) - self.MAX_LINES)
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

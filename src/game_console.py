from __future__ import annotations

import pygame

from src.constants import CONSOLE_HEIGHT, SCREEN_HEIGHT, SCREEN_WIDTH


class GameConsole:
    def __init__(self) -> None:
        self.font = pygame.font.SysFont(None, 18)
        self.rect = pygame.Rect(0, SCREEN_HEIGHT - CONSOLE_HEIGHT, SCREEN_WIDTH, CONSOLE_HEIGHT)
        self.lines: list[str] = []
        self.max_lines = 20
        self.scroll_offset = 0
        self.scroll_speed = 20
        self.selected_text = ""

    def log(self, message: str) -> None:
        self.lines.append(message)
        if len(self.lines) > self.max_lines:
            self.lines.pop(0)

    def draw(self, surface: pygame.Surface) -> None:
        pygame.draw.rect(surface, (40, 40, 40), self.rect)  # Darker console
        pygame.draw.rect(surface, (80, 80, 80), self.rect, 2)
        visible_lines = self.lines[self.scroll_offset :]
        for i, line in enumerate(visible_lines):
            if i >= self.max_lines:
                break
            text_surface = self.font.render(text=line, antialias=True, color=(200, 200, 200))
            surface.blit(text_surface, (self.rect.x + 5, self.rect.y + 5 + i * 18))
        scroll_height = self.rect.height - 20
        scroll_pos = (
            (self.scroll_offset / max(1, len(self.lines) - self.max_lines)) * (scroll_height - 20)
            if len(self.lines) > self.max_lines
            else 0
        )
        pygame.draw.rect(surface, (150, 150, 150), (self.rect.right - 15, self.rect.y + 5 + scroll_pos, 10, 20))

    def handle_event(self, event) -> None:
        mouse_pos = pygame.mouse.get_pos()
        if event.type == pygame.MOUSEWHEEL:
            if self.rect.collidepoint(mouse_pos):
                max_scroll = max(0, len(self.lines) - self.max_lines)
                scroll_amount = event.y * self.scroll_speed
                self.scroll_offset = max(0, min(max_scroll, self.scroll_offset - scroll_amount))
                print(f"Console scroll detected: y={event.y}, scroll_offset={self.scroll_offset}")

        elif event.type == pygame.KEYDOWN:
            if self.rect.collidepoint(mouse_pos):
                max_scroll = max(0, len(self.lines) - self.max_lines)
                if event.key == pygame.K_UP:
                    self.scroll_offset = max(0, self.scroll_offset - 1)
                    print(f"Console scroll up: scroll_offset={self.scroll_offset}")

                elif event.key == pygame.K_DOWN:
                    self.scroll_offset = min(max_scroll, self.scroll_offset + 1)
                    print(f"Console scroll down: scroll_offset={self.scroll_offset}")

        elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1 and self.rect.collidepoint(event.pos):
            start_y = self.rect.y + 5
            line_idx = (event.pos[1] - start_y) // 18 + self.scroll_offset
            if 0 <= line_idx < len(self.lines):
                self.selected_text = self.lines[line_idx]
                try:
                    pygame.scrap.put_text(pygame.SCRAP_TEXT)
                    print(f"Copied to clipboard: {self.selected_text}")
                except Exception as e:
                    print(f"Failed to copy to clipboard: {e}")

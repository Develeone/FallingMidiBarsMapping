"""Rendering for the top bar with file selection and track navigation."""

from __future__ import annotations

import os
from typing import List, Tuple

import pygame

from falling_midi_trainer import config


ChipInfo = Tuple[pygame.Rect, int]


def draw_topbar(
    screen: pygame.Surface,
    font: pygame.font.Font,
    files: List[str],
    selected_idx: int,
    scroll_x: int,
    track_idx: int,
    track_count: int,
) -> tuple[list[ChipInfo], pygame.Rect, pygame.Rect]:
    """Draw the topbar and return hit targets for interaction."""
    screen_width = config.WINDOW_WIDTH

    pygame.draw.rect(screen, config.TOPBAR_BG, pygame.Rect(0, 0, screen_width, config.TOPBAR_HEIGHT))
    pygame.draw.line(
        screen, config.TOPBAR_BORDER, (0, config.TOPBAR_HEIGHT - 1), (screen_width, config.TOPBAR_HEIGHT - 1), 1
    )

    selector_width = 220
    selector_x = screen_width - selector_width - 10
    selector_y = 6
    selector_height = config.TOPBAR_HEIGHT - 12

    pygame.draw.rect(screen, (35, 35, 40), pygame.Rect(selector_x, selector_y, selector_width, selector_height), border_radius=8)
    pygame.draw.rect(screen, (70, 70, 80), pygame.Rect(selector_x, selector_y, selector_width, selector_height), 1, border_radius=8)

    button_width = 28
    left_btn = pygame.Rect(selector_x + 8, selector_y + 6, button_width, selector_height - 12)
    right_btn = pygame.Rect(selector_x + selector_width - button_width - 8, selector_y + 6, button_width, selector_height - 12)
    pygame.draw.rect(screen, (55, 55, 65), left_btn, border_radius=6)
    pygame.draw.rect(screen, (55, 55, 65), right_btn, border_radius=6)

    screen.blit(font.render("<", True, (230, 230, 235)), (left_btn.x + 9, left_btn.y + 2))
    screen.blit(font.render(">", True, (230, 230, 235)), (right_btn.x + 9, right_btn.y + 2))

    label = f"Track: {track_idx + 1}/{track_count}" if track_count else "Track: -"
    screen.blit(font.render(label, True, (230, 230, 235)), (selector_x + 50, selector_y + 8))

    x_pos = 10 - scroll_x
    chips: list[ChipInfo] = []
    max_x = selector_x - 10

    for index, path in enumerate(files):
        name = os.path.basename(path)
        text = font.render(name, True, (240, 240, 245))
        padding_x = 14
        width = text.get_width() + padding_x * 2
        height = config.TOPBAR_HEIGHT - 12
        rect = pygame.Rect(x_pos, 6, width, height)

        if rect.right < 0:
            x_pos += width + 8
            continue
        if rect.left > max_x:
            break

        bg_color = (60, 60, 70) if index == selected_idx else (40, 40, 48)
        border_color = (110, 110, 130) if index == selected_idx else (70, 70, 85)
        pygame.draw.rect(screen, bg_color, rect, border_radius=10)
        pygame.draw.rect(screen, border_color, rect, 1, border_radius=10)
        screen.blit(text, (rect.x + padding_x, rect.y + 6))

        chips.append((rect, index))
        x_pos += width + 8

    return chips, left_btn, right_btn

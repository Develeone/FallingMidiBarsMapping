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
    reverb_mix: float,
) -> tuple[list[ChipInfo], pygame.Rect, pygame.Rect, pygame.Rect]:
    """Draw the topbar and return hit targets for interaction."""

    screen_width = config.WINDOW_WIDTH
    top_rect = pygame.Rect(0, 0, screen_width, config.TOPBAR_HEIGHT)

    # Gradient background
    gradient_surface = pygame.Surface((screen_width, config.TOPBAR_HEIGHT))
    for y in range(config.TOPBAR_HEIGHT):
        lerp = y / max(1, config.TOPBAR_HEIGHT - 1)
        r = int(config.TOPBAR_BG[0] + (config.TOPBAR_BG_ACCENT[0] - config.TOPBAR_BG[0]) * lerp)
        g = int(config.TOPBAR_BG[1] + (config.TOPBAR_BG_ACCENT[1] - config.TOPBAR_BG[1]) * lerp)
        b = int(config.TOPBAR_BG[2] + (config.TOPBAR_BG_ACCENT[2] - config.TOPBAR_BG[2]) * lerp)
        pygame.draw.line(gradient_surface, (r, g, b), (0, y), (screen_width, y))
    screen.blit(gradient_surface, top_rect)

    pygame.draw.line(screen, config.TOPBAR_BORDER, (0, config.TOPBAR_HEIGHT - 1), (screen_width, config.TOPBAR_HEIGHT - 1), 1)
    pygame.draw.line(screen, config.TOPBAR_GLOW, (0, config.TOPBAR_HEIGHT - 2), (screen_width, config.TOPBAR_HEIGHT - 2), 1)

    selector_width = 220
    selector_x = screen_width - selector_width - 12
    selector_y = 6
    selector_height = config.TOPBAR_HEIGHT - 12

    pygame.draw.rect(screen, (42, 52, 70), pygame.Rect(selector_x, selector_y, selector_width, selector_height), border_radius=10)
    pygame.draw.rect(screen, (86, 108, 140), pygame.Rect(selector_x, selector_y, selector_width, selector_height), 2, border_radius=10)

    button_width = 30
    left_btn = pygame.Rect(selector_x + 10, selector_y + 6, button_width, selector_height - 12)
    right_btn = pygame.Rect(selector_x + selector_width - button_width - 10, selector_y + 6, button_width, selector_height - 12)
    pygame.draw.rect(screen, (60, 76, 98), left_btn, border_radius=8)
    pygame.draw.rect(screen, (60, 76, 98), right_btn, border_radius=8)

    screen.blit(font.render("<", True, (230, 230, 235)), (left_btn.x + 9, left_btn.y + 2))
    screen.blit(font.render(">", True, (230, 230, 235)), (right_btn.x + 9, right_btn.y + 2))

    label = f"Track: {track_idx + 1}/{track_count}" if track_count else "Track: -"
    screen.blit(font.render(label, True, (230, 230, 235)), (selector_x + 52, selector_y + 8))

    # Reverb slider
    slider_width = 180
    slider_height = 12
    slider_x = selector_x - slider_width - 20
    slider_y = selector_y + (selector_height - slider_height) // 2
    slider_rect = pygame.Rect(slider_x, slider_y, slider_width, slider_height)
    pygame.draw.rect(screen, (32, 42, 55), slider_rect, border_radius=6)
    fill_width = int(slider_width * max(0.0, min(1.0, reverb_mix)))
    if fill_width:
        pygame.draw.rect(screen, (80, 160, 255), pygame.Rect(slider_x, slider_y, fill_width, slider_height), border_radius=6)
    knob_x = slider_x + max(0, fill_width - 6)
    knob_rect = pygame.Rect(knob_x, slider_y - 3, 12, slider_height + 6)
    pygame.draw.rect(screen, (210, 230, 255), knob_rect, border_radius=6)
    screen.blit(font.render("Reverb", True, (220, 230, 240)), (slider_x, slider_y - 18))

    x_pos = 12 - scroll_x
    chips: list[ChipInfo] = []
    max_x = slider_x - 12

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

        bg_color = (76, 88, 110) if index == selected_idx else (48, 54, 64)
        border_color = (120, 140, 170) if index == selected_idx else (72, 82, 98)
        pygame.draw.rect(screen, bg_color, rect, border_radius=10)
        pygame.draw.rect(screen, border_color, rect, 1, border_radius=10)
        screen.blit(text, (rect.x + padding_x, rect.y + 6))

        chips.append((rect, index))
        x_pos += width + 8

    return chips, left_btn, right_btn, slider_rect

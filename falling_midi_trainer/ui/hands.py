"""Compact mirrored hand icons for selecting the hands to practise."""
from functools import lru_cache
import pygame
from falling_midi_trainer import config


def hand_buttons() -> dict[str, pygame.Rect]:
    return {hand: pygame.Rect(16 + i * 48, config.TOPBAR_HEIGHT + 66, 40, 36)
            for i, hand in enumerate(('Л', 'П'))}


@lru_cache(maxsize=4)
def hand_icon(hand: str, enabled: bool) -> pygame.Surface:
    icon = pygame.Surface((30, 30), pygame.SRCALPHA)
    color = (225, 234, 245) if enabled else (130, 136, 147)
    # Palm, four fingers, and an opposing thumb; mirror the silhouette for L.
    pygame.draw.rect(icon, color, (9, 13, 17, 14), border_radius=6)
    for x, y, height in ((9, 6, 13), (14, 2, 17), (19, 4, 15), (24, 9, 11)):
        pygame.draw.rect(icon, color, (x, y, 4, height), border_radius=2)
    pygame.draw.line(icon, color, (11, 22), (5, 16), 5)
    pygame.draw.circle(icon, color, (5, 16), 2)
    if hand == 'Л':
        icon = pygame.transform.flip(icon, True, False)
    return icon


def draw_hand_buttons(screen, font, enabled_hands):
    for hand, rect in hand_buttons().items():
        enabled = hand in enabled_hands
        pygame.draw.rect(screen, (31, 38, 48), rect, border_radius=8)
        border = (77, 170, 255) if enabled else (83, 89, 101)
        pygame.draw.rect(screen, border, rect, 2 if enabled else 1, border_radius=8)
        screen.blit(hand_icon(hand, enabled), (rect.x + 5, rect.y + 3))
        if rect.collidepoint(pygame.mouse.get_pos()):
            label = font.render('Левая рука' if hand == 'Л' else 'Правая рука', True, config.HUD_COLOR)
            screen.blit(label, (114, rect.y + 8))

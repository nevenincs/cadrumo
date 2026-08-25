"""Public facade for reusable TUI presentation mechanics."""

from __future__ import annotations

from .theme import (
    BASE_CSS,
    CADRUMO_DARK,
    CADRUMO_DARK_THEME_NAME,
    CADRUMO_LIGHT,
    CADRUMO_LIGHT_THEME_NAME,
    CADRUMO_THEMES,
    CONTENT_WIDTH_PERCENT,
    NOTICE_BAND_CSS,
    ContentDataTable,
    ContentScroll,
    NoticeBand,
    install_cadrumo_themes,
    resolve_theme_name,
    toggle_appearance,
)

__all__ = [
    "BASE_CSS",
    "CADRUMO_DARK",
    "CADRUMO_DARK_THEME_NAME",
    "CADRUMO_LIGHT",
    "CADRUMO_LIGHT_THEME_NAME",
    "CADRUMO_THEMES",
    "CONTENT_WIDTH_PERCENT",
    "NOTICE_BAND_CSS",
    "ContentDataTable",
    "ContentScroll",
    "NoticeBand",
    "install_cadrumo_themes",
    "resolve_theme_name",
    "toggle_appearance",
]

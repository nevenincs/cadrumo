"""Every character the TUI can put on screen exists in the pinned terminal font.

A glyph the font lacks renders as a filled box in the visual review and depends
on font fallback in a real terminal, so a state mark meant to be read without
colour can silently become unreadable. The gate collects every non-ASCII
character from the string literals of the production TUI modules and from every
locale catalogue value, and asks the pinned font for each one by the same
``.notdef`` comparison the raster tool uses.

The probe is proven able to fail first: characters known to be absent from the
font must be reported missing, or a green result would say nothing.
"""

from __future__ import annotations

import ast
from functools import cache
from pathlib import Path

import pytest
import yaml
from PIL import ImageFont

from dev._paths import REPO_ROOT
from dev.source_tree import repository_files
from dev.tui._raster import FONT_PATH, _mask_bytes

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]

_PROBE_SIZE = 22
_NOTDEF_PROBE = "\ue000"
_TUI_SOURCE = "src/cadrumo/entrypoints/tui"
_CATALOGUES = "src/cadrumo/locales"


@cache
def _font() -> ImageFont.FreeTypeFont:
    return ImageFont.truetype(str(FONT_PATH), size=_PROBE_SIZE)


@cache
def _notdef() -> bytes:
    return _mask_bytes(_font().getmask(_NOTDEF_PROBE))


def _is_missing(character: str) -> bool:
    """Whether the pinned font draws its ``.notdef`` box for ``character``."""
    return _mask_bytes(_font().getmask(character)) == _notdef()


def _string_literals(path: Path) -> list[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    return [node.value for node in ast.walk(tree) if isinstance(node, ast.Constant) and isinstance(node.value, str)]


def _catalogue_strings(value: object) -> list[str]:
    if isinstance(value, dict):
        return [text for item in value.values() for text in _catalogue_strings(item)]
    if isinstance(value, list):
        return [text for item in value for text in _catalogue_strings(item)]
    return [value] if isinstance(value, str) else []


def _shipped_characters() -> dict[str, set[str]]:
    """Map every shipped non-ASCII, non-space character to the files that ship it."""
    shipped: dict[str, set[str]] = {}
    sources = [
        relative
        for relative in repository_files(under=(_TUI_SOURCE,))
        if relative.endswith(".py") and "/tests/" not in relative
    ]
    catalogues = [relative for relative in repository_files(under=(_CATALOGUES,)) if relative.endswith(".yml")]
    for relative in sources:
        for text in _string_literals(REPO_ROOT / relative):
            for character in text:
                if ord(character) > 127 and not character.isspace():
                    shipped.setdefault(character, set()).add(relative)
    for relative in catalogues:
        document = yaml.safe_load((REPO_ROOT / relative).read_text(encoding="utf-8"))
        for text in _catalogue_strings(document):
            for character in text:
                if ord(character) > 127 and not character.isspace():
                    shipped.setdefault(character, set()).add(relative)
    return shipped


@pytest.mark.parametrize("character", ("\u26a0", "\u24d8", "\u2716", "\x96"))
def test_the_probe_reports_a_glyph_the_font_lacks(character: str) -> None:
    assert _is_missing(character)


@pytest.mark.parametrize("character", ("\u2713", "\u25b2", "\u00d7", "\u00e9", "\u0151", "\u20ac"))
def test_the_probe_accepts_a_glyph_the_font_has(character: str) -> None:
    assert not _is_missing(character)


def test_every_shipped_character_is_in_the_pinned_font() -> None:
    shipped = _shipped_characters()
    missing = {
        f"U+{ord(character):04X}": sorted(files)[:3] for character, files in shipped.items() if _is_missing(character)
    }

    assert shipped, "the gate collected no characters, so it cannot have checked any"
    assert missing == {}

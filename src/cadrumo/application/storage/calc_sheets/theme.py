"""Shared visual design system for modelo workbook exports.

This module is the single source of truth for the export look — the font
family and the role→style palette — consumed identically by both transports
(the offline openpyxl materializer in ``workbook_export`` and the online
Google-Sheets apply adapter in ``_calc_sheets_apply``). Centralising the design
here is what makes "uniform application across all exports" structural rather
than coincidental: neither transport hard-codes a colour or a font; both import
:data:`WORKBOOK_FONT_FAMILY` and :data:`ROLE_STYLES` and translate the same
declarative :class:`RoleStyle` into their respective formatting API. The palette
mirrors the calm, boxed look of the official AEAT paper modelo: a slate header
band, light blue-grey section banners, pale-yellow operator-input boxes,
light-grey computed/protected cells, and a green-accented final result.

The colours are stored as plain ``RRGGBB`` hex; :func:`hex_to_rgb_floats`
converts to the 0..1 channel floats the Sheets API wants, and openpyxl consumes
the hex directly (prefixed with the opaque alpha ``FF``).
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Final, Literal

# A single declared monospace family. Roboto Mono is a native Google-Sheets
# font (crisp online); the offline xls renderer substitutes the nearest
# installed monospace (Consolas / Liberation Mono) when Roboto Mono is absent.
WORKBOOK_FONT_FAMILY: Final[str] = "Roboto Mono"

STYLED_RANGE_VERTICAL_ALIGN: Final[str] = "top"
"""Vertical alignment applied to every role-styled range, in both transports.

Unlike the horizontal alignment this is uniform across roles, which is why it
belongs here rather than on :class:`RoleStyle`. It lived as a literal inside
the offline materialiser instead, so the online request builder simply never
emitted the facet and Sheets kept its bottom-aligned default -- the two
transports disagreed on a plan they both claim to mirror, and no palette entry
was wrong, so nothing pointed at the gap.
"""

# Slate brand ink used for header-band text and emphasis foregrounds.
_SLATE: Final[str] = "1F3864"
_WHITE: Final[str] = "FFFFFF"
_INK: Final[str] = "1A1A1A"


class StyleRole(StrEnum):
    """The closed set of presentation roles a styled range can carry.

    Each role maps to exactly one :class:`RoleStyle` in :data:`ROLE_STYLES`;
    the engine tags ranges with a role and both transports resolve the role to
    concrete fill / font / alignment through this module.
    """

    HEADER = "header"
    SECTION_BANNER = "section_banner"
    INPUT = "input"
    COMPUTED = "computed"
    RESULT = "result"
    TITLE = "title"
    BODY = "body"


HorizontalAlign = Literal["left", "center", "right"]


@dataclass(frozen=True, slots=True)
class RoleStyle:
    """A declarative cell style independent of any rendering backend.

    ``fill_hex`` / ``font_hex`` are ``RRGGBB`` (or ``None`` for "no fill" /
    "default ink"); ``bold`` toggles weight; ``align`` is the horizontal
    alignment; ``wrap`` requests text wrapping (the renderer auto-grows row
    height to fit).
    """

    fill_hex: str | None
    font_hex: str | None
    bold: bool
    align: HorizontalAlign
    wrap: bool = False


ROLE_STYLES: Final[dict[StyleRole, RoleStyle]] = {
    # Slate band, white bold, centred — the column-title row on every tab.
    StyleRole.HEADER: RoleStyle(fill_hex=_SLATE, font_hex=_WHITE, bold=True, align="center"),
    # Light blue-grey banner, slate bold — the first cell of each casilla section.
    StyleRole.SECTION_BANNER: RoleStyle(fill_hex="D6E4F0", font_hex=_SLATE, bold=True, align="left"),
    # Pale yellow box, right-aligned — operator fills these in.
    StyleRole.INPUT: RoleStyle(fill_hex="FFF8E1", font_hex=_INK, bold=False, align="right"),
    # Light grey, right-aligned — derived / protected values.
    StyleRole.COMPUTED: RoleStyle(fill_hex="F2F2F2", font_hex=_INK, bold=False, align="right"),
    # Green accent, slate bold — the filing result (resultado / cuota).
    StyleRole.RESULT: RoleStyle(fill_hex="C6E0B4", font_hex=_SLATE, bold=True, align="right"),
    # No fill, slate bold — the Guía title and other headline prose.
    StyleRole.TITLE: RoleStyle(fill_hex=None, font_hex=_SLATE, bold=True, align="left"),
    # No fill, default ink, left — plain body text (concepto / refs), wrap opt-in.
    StyleRole.BODY: RoleStyle(fill_hex=None, font_hex=None, bold=False, align="left"),
}


def hex_to_rgb_floats(value: str) -> dict[str, float]:
    """Convert an ``RRGGBB`` hex string to the Sheets API ``{red,green,blue}`` floats.

    Args:
        value: A six-character ``RRGGBB`` hex colour (case-insensitive).

    Returns:
        A mapping with ``red`` / ``green`` / ``blue`` keys, each a 0..1 float.
    """
    cleaned = value.lstrip("#")
    red = int(cleaned[0:2], 16) / 255.0
    green = int(cleaned[2:4], 16) / 255.0
    blue = int(cleaned[4:6], 16) / 255.0
    return {"red": red, "green": green, "blue": blue}


def openpyxl_argb(value: str) -> str:
    """Return the opaque ``AARRGGBB`` form openpyxl fills / fonts expect."""
    return f"FF{value.lstrip('#').upper()}"


__all__ = [
    "ROLE_STYLES",
    "STYLED_RANGE_VERTICAL_ALIGN",
    "WORKBOOK_FONT_FAMILY",
    "HorizontalAlign",
    "RoleStyle",
    "StyleRole",
    "hex_to_rgb_floats",
    "openpyxl_argb",
]

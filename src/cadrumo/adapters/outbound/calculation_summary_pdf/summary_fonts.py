"""The typefaces a calculation summary is set in, registered from package data.

Text is set in Hanken Grotesk and figures, casilla numbers and identifiers in
JetBrains Mono, the product's documentation faces. Both ship as static TrueType
instances under ``cadrumo/_data/calculation_summary_pdf/fonts`` with their SIL
Open Font License texts, and a subset of each face used is embedded in every
summary, as PDF/A requires.

Static TrueType rather than the documentation's WOFF2 subsets because the page
writer reads neither WOFF2 nor variable-font instances. Every shipped face must
also keep a full horizontal-metrics table: the writer subsets a font whose
metrics use the compact form with glyph widths that disagree with the font
program, which archival validators reject. The owning tests measure that for
every face shipped here.

Importing this module imports the page writer, so only the writer path, which is
already behind the ``pdf`` extra, imports it.
"""

from __future__ import annotations

from collections.abc import Mapping
from enum import StrEnum
from types import MappingProxyType
from typing import Final

from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont

from ....core.resources.bundled_data import bundled_path

FONT_DIRECTORY: Final[tuple[str, ...]] = ("calculation_summary_pdf", "fonts")
"""Location of the shipped faces under the package data root."""


class SummaryFace(StrEnum):
    """The faces a summary uses, by the name each is registered under.

    The names are distinct from any face a caller of the same page writer might
    register, so two users of the writer in one process cannot collide.
    """

    TEXT = "CadrumoSummary-Text"
    TEXT_SEMIBOLD = "CadrumoSummary-TextSemiBold"
    TEXT_BOLD = "CadrumoSummary-TextBold"
    FIGURE = "CadrumoSummary-Figure"
    FIGURE_BOLD = "CadrumoSummary-FigureBold"


SUMMARY_FONT_FILES: Final[Mapping[SummaryFace, str]] = MappingProxyType(
    {
        SummaryFace.TEXT: "HankenGrotesk-Regular.ttf",
        SummaryFace.TEXT_SEMIBOLD: "HankenGrotesk-SemiBold.ttf",
        SummaryFace.TEXT_BOLD: "HankenGrotesk-Bold.ttf",
        SummaryFace.FIGURE: "JetBrainsMono-Regular.ttf",
        SummaryFace.FIGURE_BOLD: "JetBrainsMono-Bold.ttf",
    },
)
"""The shipped TrueType file behind each face; total over :class:`SummaryFace`."""


def register_summary_fonts() -> None:
    """Register every summary face with the page writer, once per process."""
    registered = set(pdfmetrics.getRegisteredFontNames())
    for face, filename in SUMMARY_FONT_FILES.items():
        if face.value in registered:
            continue
        pdfmetrics.registerFont(TTFont(face.value, str(bundled_path(*FONT_DIRECTORY, filename))))


__all__ = ["FONT_DIRECTORY", "SUMMARY_FONT_FILES", "SummaryFace", "register_summary_fonts"]

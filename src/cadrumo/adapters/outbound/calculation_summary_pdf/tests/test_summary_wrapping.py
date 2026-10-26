"""A hyphen that belongs to a casilla identifier or label survives the line break.

Text extraction treats a hyphen at the end of a line as one the layout added to
split a word: pdfium, which reads the text layer for verification, joins the two
lines and returns U+FFFE where the hyphen was. The layout therefore never ends a
line in a hyphen while text follows it; the hyphen starts the next line instead.

The identifiers and labels below are registry shapes that break across a
column: slugs (Modelo 100, 130, 303), dotted paths with a hyphenated segment
(Modelo 390), numeric ranges (Modelo 180, 190) and labels with a spaced
separator (Modelo 303, 390), plus a suspended hyphen before a space.
"""

from __future__ import annotations

from typing import Final

import pytest
from reportlab.pdfbase import pdfmetrics

from .....application.modelo.calculation_report import ModeloCalculationReportRow
from .....application.modelo.calculation_report_verification import (
    CalculationSummaryVerificationOutcome,
    verify_calculation_summary,
)
from .....core.external_constants import OutputLanguage
from ..summary_fonts import SummaryFace, register_summary_fonts
from ..summary_layout import INK, DrawText, SummaryPage, draw_summary_pages, wrap_text
from ..summary_reading import read_calculation_summary_pdf
from .summary_report_support import render_summary, synthetic_keypair, synthetic_report, synthetic_report_rows

pytestmark = [pytest.mark.unit, pytest.mark.hex_outbound_adapter]

_KEY = synthetic_keypair()
_SIZE: Final[float] = 9.0
_PDFIUM_HYPHENATION_MARK: Final[str] = "\ufffe"

#: One long identifier per shape, each a casilla number the registry declares.
_IDENTIFIERS: Final[tuple[str, ...]] = (
    "prorrata-volumen-con-derecho",
    "iva.anual.repercutido.recargo.super-reducido",
    "prestacion-inss-maternidad-paternidad-exenta",
    "base-liq-neg-general-2024-aplicada-maxima",
    "saldo-negativo-fin-periodo",
    "108-120",
)
_LABELS: Final[tuple[str, ...]] = (
    "Compensaciones régimen especial agricultura ganadería y pesca - Cuota",
    "Recargo de equivalencia al tipo super-reducido (0,5%) - Cuota",
    "Información adicional - Entregas criterio caja devengado art 75 LIVA - Base imponible",
    "Entregas intra- y extracomunitarias de bienes",
)


def _compact(text: str) -> str:
    return "".join(text.split())


def _width(text: str, face: SummaryFace) -> float:
    return pdfmetrics.stringWidth(text, face.value, _SIZE)


@pytest.mark.parametrize(
    ("text", "face"),
    (
        *((identifier, SummaryFace.FIGURE) for identifier in _IDENTIFIERS),
        *((label, SummaryFace.TEXT) for label in _LABELS),
        *((label, SummaryFace.TEXT_BOLD) for label in _LABELS),
    ),
)
def test_no_column_width_leaves_a_hyphen_at_a_line_end(text: str, face: SummaryFace) -> None:
    """Every character, every hyphen included, meets the column edge at one of these widths.

    The narrowest column swept holds any three consecutive characters: a line
    that starts with a hyphen and the space after it needs one character more to
    end in something else. The summary's narrowest column holds nine.
    """
    register_summary_fonts()
    narrowest = max(_width(text[start : start + 3], face) for start in range(len(text) - 2))
    widths = sorted(width for width in {_width(text[:end], face) for end in range(1, len(text))} if width >= narrowest)

    assert widths
    for width in widths:
        lines = wrap_text(text, face, _SIZE, width)

        assert not [line for line in lines[:-1] if line.rstrip(" ").endswith("-")], (width, lines)
        assert "".join(lines).replace(" ", "") == text.replace(" ", ""), (width, lines)
        assert all(_width(line, face) <= width for line in lines if len(line) > 1), (width, lines)


def _hyphenated_rows() -> tuple[ModeloCalculationReportRow, ...]:
    template = next(row for row in synthetic_report_rows() if row.casilla_id == "01")
    return tuple(
        template.model_copy(
            update={"casilla_id": f"h{index}", "number": number, "label": _LABELS[index % len(_LABELS)]},
        )
        for index, number in enumerate(_IDENTIFIERS)
    )


def test_every_hyphenated_identifier_and_label_reads_back_whole_and_the_summary_verifies() -> None:
    rows = (*synthetic_report_rows(), *_hyphenated_rows())
    payload = render_summary(synthetic_report(OutputLanguage.ES, rows=rows), keypair=_KEY).payload

    page_text = read_calculation_summary_pdf(payload).page_text
    verification = verify_calculation_summary(
        payload,
        reader=read_calculation_summary_pdf,
        trusted_public_key_hex=_KEY.public_key_hex,
    )

    assert _PDFIUM_HYPHENATION_MARK not in page_text
    missing = [text for text in (*_IDENTIFIERS, *_LABELS) if _compact(text) not in _compact(page_text)]
    assert missing == []
    assert verification.outcome is CalculationSummaryVerificationOutcome.VERIFIED
    assert verification.reasons == ()
    assert render_summary(synthetic_report(OutputLanguage.ES, rows=rows), keypair=_KEY).payload == payload


def _drawn(lines: tuple[str, ...]) -> str:
    page = SummaryPage(
        operations=[
            DrawText(60.0, 700.0 - 11.0 * index, line, SummaryFace.FIGURE, _SIZE, INK, False, None)
            for index, line in enumerate(lines)
        ],
    )
    return read_calculation_summary_pdf(draw_summary_pages((page,), language="es").payload).page_text


def test_a_hyphen_left_at_a_line_end_is_lost_to_extraction_and_the_layout_keeps_it() -> None:
    """The hazard the layout avoids, shown on the reader the verifier uses."""
    register_summary_fonts()
    identifier = _IDENTIFIERS[0]
    width = _width("prorrata-", SummaryFace.FIGURE)
    naive = ("prorrata-", identifier.removeprefix("prorrata-"))

    wrapped = wrap_text(identifier, SummaryFace.FIGURE, _SIZE, width)
    naive_text = _drawn(naive)
    wrapped_text = _drawn(wrapped)

    assert _PDFIUM_HYPHENATION_MARK in naive_text
    assert _compact(identifier) not in _compact(naive_text)
    assert _PDFIUM_HYPHENATION_MARK not in wrapped_text
    assert _compact(identifier) in _compact(wrapped_text)

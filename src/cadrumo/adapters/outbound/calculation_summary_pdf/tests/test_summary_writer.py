"""What a calculation summary shows, what it embeds, and what it keeps out of metadata.

Every expected page string here is written out by hand -- the grouped figures in
each language's convention, the three value-state texts -- rather than produced
by the presentation code under test, so a formatting regression cannot pass by
agreeing with itself.
"""

from __future__ import annotations

import hashlib
import io
import json
import os
import sys
from pathlib import Path
from typing import Final

import pikepdf
import pypdfium2
import pytest

from .....application.modelo.calculation_report_document import serialize_calculation_report_csv
from .....application.modelo.calculation_summary_pdf_ports import (
    CSV_ATTACHMENT_NAME,
    REPORT_ATTACHMENT_NAME,
)
from .....core.external_constants import OutputLanguage
from .....tests.audited_process import run_audited_process
from ..summary_layout import INK, MUTED_INK, PANEL, RUST_INK, SUCCESS_INK, SUCCESS_WASH, WARNING_INK
from .summary_report_support import (
    TAXPAYER_NAME,
    TAXPAYER_TAX_ID,
    render_summary,
    synthetic_report,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_outbound_adapter]

#: What each language must show for the measured figure, the result, the proven
#: zero and the two value states that are not figures.
_EXPECTED_PAGE_TEXT: Final[dict[OutputLanguage, tuple[str, ...]]] = {
    OutputLanguage.ES: ("1.234.567,89", "-2.750,40", "0,00", "sin dato", "n/a · no aplicable", "Sí"),
    OutputLanguage.EN: ("1,234,567.89", "-2,750.40", "0.00", "no data", "n/a · not applicable", "Yes"),
    OutputLanguage.CA: ("1.234.567,89", "-2.750,40", "0,00", "sense dada", "n/a · no aplicable", "Sí"),
    OutputLanguage.HU: ("1 234 567,89", "-2 750,40", "0,00", "nincs adat", "n/a · nem alkalmazandó", "Igen"),
}
_WCAG_AA_TEXT: Final[float] = 4.5
_WHITE: Final[tuple[float, float, float]] = (1.0, 1.0, 1.0)


def _page_text(payload: bytes) -> str:
    document = pypdfium2.PdfDocument(payload)
    try:
        text = "\n".join(document[index].get_textpage().get_text_range() for index in range(len(document)))
    finally:
        document.close()
    return " ".join(text.replace("\u00a0", " ").split())


def _attachment(payload: bytes, name: str) -> bytes:
    with pikepdf.open(io.BytesIO(payload)) as pdf:
        return pdf.attachments[name].get_file().read_bytes()


@pytest.mark.parametrize("language", tuple(OutputLanguage))
def test_every_value_and_state_reads_off_the_page_in_the_report_language(language: OutputLanguage) -> None:
    text = _page_text(render_summary(synthetic_report(language)).payload)

    for expected in _EXPECTED_PAGE_TEXT[language]:
        assert expected in text, f"{expected!r} is not on the {language.value} page"
    assert TAXPAYER_TAX_ID in text
    assert TAXPAYER_NAME in text


def test_the_embedded_report_and_csv_are_the_builder_bytes() -> None:
    report = synthetic_report(OutputLanguage.CA)
    payload = render_summary(report).payload

    embedded_report = _attachment(payload, REPORT_ATTACHMENT_NAME)
    embedded_csv = _attachment(payload, CSV_ATTACHMENT_NAME)

    assert embedded_report == report.canonical_bytes()
    assert hashlib.sha256(embedded_report).hexdigest() == report.report_sha256
    assert embedded_csv == serialize_calculation_report_csv(report)
    assert json.loads(embedded_report)["header"]["taxpayer_tax_id"] == TAXPAYER_TAX_ID


def test_two_renders_of_one_report_are_byte_identical() -> None:
    first = render_summary(synthetic_report()).payload
    second = render_summary(synthetic_report()).payload

    assert first == second


def test_a_second_process_renders_the_same_bytes() -> None:
    """Determinism holds across interpreters, not only across calls in one."""
    source_root = str(Path(__file__).resolve().parents[5])
    completed = run_audited_process(
        [
            sys.executable,
            "-c",
            "import hashlib;"
            "from cadrumo.adapters.outbound.calculation_summary_pdf.tests.summary_report_support import"
            " render_summary, synthetic_report;"
            "print(hashlib.sha256(render_summary(synthetic_report()).payload).hexdigest())",
        ],
        capture_output=True,
        text=True,
        env={**os.environ, "PYTHONPATH": source_root},
    )

    assert completed.returncode == 0, completed.stderr
    assert completed.stdout.strip() == hashlib.sha256(render_summary(synthetic_report()).payload).hexdigest()


def test_no_taxpayer_identity_reaches_the_document_metadata() -> None:
    """The NIF and name are on the page and in the embedded data, never in metadata."""
    payload = render_summary(synthetic_report(OutputLanguage.HU)).payload
    identity = (TAXPAYER_TAX_ID, TAXPAYER_NAME, *TAXPAYER_NAME.split())

    with pikepdf.open(io.BytesIO(payload)) as pdf:
        packet = pdf.Root.Metadata.read_bytes().decode("utf-8")
        described = " ".join(f"{name} {spec.obj.get('/Desc', '')}" for name, spec in pdf.attachments.items())
        assert "/Info" not in pdf.trailer
    for fragment in identity:
        assert fragment not in packet
        assert fragment not in described


def _linear_channel(value: float) -> float:
    return value / 12.92 if value <= 0.03928 else float(((value + 0.055) / 1.055) ** 2.4)


def _relative_luminance(colour: tuple[float, float, float]) -> float:
    red, green, blue = (_linear_channel(value) for value in colour)
    return 0.2126 * red + 0.7152 * green + 0.0722 * blue


@pytest.mark.parametrize(
    ("ink", "ground"),
    (
        (INK, _WHITE),
        (INK, PANEL),
        (INK, SUCCESS_WASH),
        (MUTED_INK, _WHITE),
        (MUTED_INK, PANEL),
        (RUST_INK, _WHITE),
        (RUST_INK, PANEL),
        (WARNING_INK, _WHITE),
        (WARNING_INK, PANEL),
        (SUCCESS_INK, SUCCESS_WASH),
    ),
)
def test_every_text_ink_clears_wcag_aa_on_its_ground(
    ink: tuple[float, float, float],
    ground: tuple[float, float, float],
) -> None:
    lighter, darker = sorted((_relative_luminance(ink), _relative_luminance(ground)), reverse=True)

    assert (lighter + 0.05) / (darker + 0.05) >= _WCAG_AA_TEXT

"""The inbound extractor honours the canonical AEAT CSV width.

The extractor's regex tiers used to stop at 24 characters while every other
surface accepted up to 32. That is not a conservative reading: a longer CSV
was either missed entirely or truncated to a 24-character prefix that names no
document, and the receipt it was lifted from is filing evidence.
"""

from __future__ import annotations

import pytest

from .....core.aeat_csv import AEAT_CSV_MAX_LENGTH, is_aeat_csv
from .....core.config import Settings
from .....domain.justificante import JustificanteCsvNotFoundError
from .._extract import _extract_csv

pytestmark = [pytest.mark.unit, pytest.mark.hex_inbound_adapter]

_SEDE_ORIGIN = Settings.external_constants().aeat.domains.sede

_CSV_24 = "A1B2C3D4E5F6G7H8J9K0L1M2"
_CSV_32 = "A1B2C3D4E5F6G7H8J9K0L1M2N3P4Q5R6"


def _footer(csv: str) -> str:
    return (
        "La autenticidad de este documento puede ser comprobada mediante "
        f"el Código Seguro de Verificación {csv} en {_SEDE_ORIGIN}"
    )


@pytest.mark.parametrize("csv", [_CSV_24, _CSV_32])
def test_documented_widths_are_extracted_whole(csv: str) -> None:
    text = _footer(csv)

    assert _extract_csv(text, text, "fixture.pdf") == csv


def test_the_extractor_reaches_the_canonical_maximum_width() -> None:
    """A CSV at the canonical ceiling must survive intact, not be truncated."""
    assert len(_CSV_32) == AEAT_CSV_MAX_LENGTH
    text = _footer(_CSV_32)

    extracted = _extract_csv(text, text, "fixture.pdf")

    assert extracted == _CSV_32
    assert is_aeat_csv(extracted)


@pytest.mark.parametrize("label_text", ["Código Seguro de Verificación: {csv}", "Secure Verification Code: {csv}"])
def test_every_label_tier_accepts_the_full_width(label_text: str) -> None:
    text = label_text.format(csv=_CSV_32)

    assert _extract_csv(text, text, "fixture.pdf") == _CSV_32


def test_a_receipt_with_no_csv_still_refuses() -> None:
    with pytest.raises(JustificanteCsvNotFoundError):
        _extract_csv("no code here", "no code here", "fixture.pdf")

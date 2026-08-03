"""Real receipt-to-filing target matching coverage."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import pytest
from pydantic import AnyHttpUrl, TypeAdapter

from ....core import Period
from ....tests.aeat_literal_fixtures import JUSTIFICANTE_FILING_TARGET_VERIFY_URL_FIXTURE
from .._schema import Justificante

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]

_PERIOD = Period.from_year_and_code(2025, "1T")
_PRESENTED_AT = datetime(2025, 4, 15, 12, 0, tzinfo=UTC)


def _receipt(**updates: object) -> Justificante:
    values: dict[str, object] = {
        "csv": "JUST-303-2025-1T",
        "modelo": "303",
        "ejercicio": "2025",
        "period": _PERIOD,
        "presentation_id": "EXP-2025-1T",
        "presented_at": _PRESENTED_AT,
        "tax_id": "X1234567L",
        "verification_url": TypeAdapter(AnyHttpUrl).validate_python(JUSTIFICANTE_FILING_TARGET_VERIFY_URL_FIXTURE),
        "source_pdf_path": Path("var/justificantes/just-303.pdf"),
        "source_pdf_sha256": "a" * 64,
        "parsed_at": _PRESENTED_AT,
    }
    values.update(updates)
    return Justificante.model_validate(values)


@pytest.mark.parametrize(
    ("updates", "presentation_id", "expected"),
    (
        ({"modelo": " 303 "}, "exp-2025-1t", True),
        ({"modelo": "130"}, "EXP-2025-1T", False),
        ({"ejercicio": "2024"}, "EXP-2025-1T", False),
        ({"period": Period.from_year_and_code(2025, "2T")}, "EXP-2025-1T", False),
        ({"tax_id": "Y7654321Z"}, "EXP-2025-1T", False),
        ({}, "different-expediente", False),
        ({"presentation_id": None}, "different-expediente", True),
    ),
)
def test_matches_filing_target_uses_one_normalised_axis_matrix(
    updates: dict[str, object],
    presentation_id: str,
    expected: bool,
) -> None:
    receipt = _receipt(**updates)

    assert (
        receipt.matches_filing_target(
            modelo="303",
            filing_year=2025,
            period=_PERIOD,
            tax_id=" x1234567l ",
            presentation_id=presentation_id,
        )
        is expected
    )

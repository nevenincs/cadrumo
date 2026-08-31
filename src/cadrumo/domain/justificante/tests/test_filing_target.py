"""Real receipt-to-filing target matching coverage."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import pytest
from pydantic import AnyHttpUrl, TypeAdapter

from ....core.period import Period
from ....tests.aeat_literal_fixtures import JUSTIFICANTE_FILING_TARGET_VERIFY_URL_FIXTURE
from ..schema import Justificante

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]

_PERIOD = Period.from_year_and_code(2025, "1T")
_PRESENTED_AT = datetime(2025, 4, 15, 12, 0, tzinfo=UTC)


def _receipt(**updates: object) -> Justificante:
    values: dict[str, object] = {
        "csv": "JUST3032025X1T7",
        "modelo": "303",
        "ejercicio": "2025",
        "period": _PERIOD,
        # A receipt-shaped Número de justificante. It used to be an
        # expediente-shaped literal, which read as evidence that a register
        # expediente id belongs in this field; it does not, and no assertion
        # below consumes this value as a matching axis.
        "presentation_id": "30320250415ABCD1234EFGH5678",
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
    ("updates", "expected"),
    (
        ({"modelo": " 303 "}, True),
        ({"modelo": "130"}, False),
        ({"ejercicio": "2024"}, False),
        ({"period": Period.from_year_and_code(2025, "2T")}, False),
        ({"tax_id": "Y7654321G"}, False),
        # The receipt's own presentation identifier is not a matching axis, so
        # neither carrying a different one nor carrying none at all changes the
        # verdict. These two cases previously asserted the opposite.
        ({"presentation_id": "30320250415ZZZZ9999YYYY8888"}, True),
        ({"presentation_id": None}, True),
    ),
)
def test_matches_filing_target_uses_one_normalised_axis_matrix(
    updates: dict[str, object],
    expected: bool,
) -> None:
    receipt = _receipt(**updates)

    assert (
        receipt.matches_filing_target(
            modelo="303",
            filing_year=2025,
            period=_PERIOD,
            tax_id=" x1234567l ",
        )
        is expected
    )


def test_matches_filing_target_refuses_a_presentation_identifier_argument() -> None:
    """The predicate accepts no receipt-identifier axis, and says so at call time.

    Every caller that ever populated such a parameter passed a register
    expediente id, which is a different AEAT namespace from anything printed on
    a receipt, so the comparison could never agree and every real receipt was
    rejected. Verifying the receipt is now the caller's own csv comparison
    against an independently obtained csv.

    This asserts the removal itself rather than the behaviour it removed: a
    future author reintroducing the argument gets a ``TypeError`` here, which a
    docstring warning on a live parameter could not deliver.
    """
    receipt = _receipt()

    with pytest.raises(TypeError, match="presentation_id"):
        receipt.matches_filing_target(  # type: ignore[call-arg]
            modelo="303",
            filing_year=2025,
            period=_PERIOD,
            tax_id="X1234567L",
            presentation_id="202530300000101A",  # ty: ignore[unknown-argument]  # reason: passing the removed parameter is the refusal under test
        )

    # Anchor: the same call without the argument is accepted, so the TypeError
    # above is about the parameter and not about an unrelatedly broken call.
    assert receipt.matches_filing_target(
        modelo="303",
        filing_year=2025,
        period=_PERIOD,
        tax_id="X1234567L",
    )

"""Tests for :func:`aeat.core.identity.validate_spanish_tax_id`.

The sibling :func:`aeat.core.identity.validate_identity` parser (covered by
``test_documents.py``) returns an :class:`aeat.core.identity.IdentityDocument`
member; ``validate_spanish_tax_id`` returns the canonical identifier string and
is the surface the encrypted master-key NIF canary, invoice counterparty checks,
the PDF sanitiser, and the registry schema scalars consume. A non-resident
heredero (or any foreigner) carries a **NIE** — an ``X``/``Y``/``Z``-led
identifier — so the canonical-string validator's NIE branch must accept the
legitimate forms and reject malformed ones with an instructive message.

The NIE check digit is derived by substituting the leading ``X``/``Y``/``Z``
with ``0``/``1``/``2`` and applying the AEAT control-letter table
``TRWAGMYFPDXBNJZSQVHLCKE`` indexed by ``number % 23`` — the same algorithm as a
NIF. The known-good check letters asserted below are computed from that table,
not copied from a validator run.
"""

from __future__ import annotations

import pytest

from .._documents import IdentityError
from .._tax_id import nif_check_letter, validate_spanish_tax_id

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]


@pytest.mark.parametrize(
    ("candidate", "substituted"),
    (
        pytest.param("X1234567L", 1234567, id="x-prefix"),
        pytest.param("Y0000000Z", 10000000, id="y-zero-body"),
        pytest.param("Z0000000M", 20000000, id="z-zero-body"),
        pytest.param("Y5678901P", 15678901, id="y-nonzero-body"),
        pytest.param("Z2345678M", 22345678, id="z-nonzero-body"),
    ),
)
def test_valid_nie_forms_are_accepted(candidate: str, substituted: int) -> None:
    # The asserted check letter is derived from the AEAT table, not the
    # validator: prove the fixture's check letter is the algorithm's answer.
    assert candidate[-1] == nif_check_letter(substituted)
    assert validate_spanish_tax_id(candidate) == candidate


@pytest.mark.parametrize(
    ("raw", "expected"),
    (
        pytest.param("x1234567l", "X1234567L", id="lowercase"),
        pytest.param("  X-1234567-L  ", "X1234567L", id="punctuation-and-padding"),
        pytest.param("ESX1234567L", "X1234567L", id="foreign-vat-prefix"),
    ),
)
def test_valid_nie_forms_are_normalised(raw: str, expected: str) -> None:
    assert validate_spanish_tax_id(raw) == expected


@pytest.mark.parametrize(
    ("candidate", "expected_message"),
    (
        pytest.param("X1234567Z", "NIE checksum letter is invalid", id="bad-check-letter"),
        pytest.param(
            "X123A567L",
            "NIE must be a leading X/Y/Z plus 7 digits and a checksum letter",
            id="non-digit-body",
        ),
        pytest.param(
            "X12345678",
            "NIE must be a leading X/Y/Z plus 7 digits and a checksum letter",
            id="digit-control",
        ),
        pytest.param("X123456L", "9 characters long", id="too-short"),
        pytest.param("   ", "must not be blank", id="blank"),
    ),
)
def test_invalid_nie_inputs_are_rejected_with_instructive_messages(
    candidate: str,
    expected_message: str,
) -> None:
    with pytest.raises(IdentityError, match=expected_message):
        validate_spanish_tax_id(candidate)

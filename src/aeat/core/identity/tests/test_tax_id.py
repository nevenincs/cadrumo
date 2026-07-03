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


def test_valid_nie_forms_are_accepted_and_normalised() -> None:
    canonical_cases = (
        # X -> 0: 01234567 % 23 = 19 -> L
        ("X1234567L", 1234567),
        # Y -> 1: 10000000 % 23 = 14 -> Z
        ("Y0000000Z", 10000000),
        # Z -> 2: 20000000 % 23 = 5 -> M
        ("Z0000000M", 20000000),
        # Y -> 1: 15678901 % 23 = 8 -> P
        ("Y5678901P", 15678901),
        # Z -> 2: 22345678 % 23 = 5 -> M
        ("Z2345678M", 22345678),
    )

    for candidate, substituted in canonical_cases:
        # The asserted check letter is derived from the AEAT table, not the
        # validator: prove the fixture's check letter is the algorithm's answer.
        assert candidate[-1] == nif_check_letter(substituted)
        assert validate_spanish_tax_id(candidate) == candidate

    normalised_cases = (
        ("x1234567l", "X1234567L"),
        ("  X-1234567-L  ", "X1234567L"),
        # The foreign-facing VAT form ``ES`` + NIE is accepted and stripped.
        ("ESX1234567L", "X1234567L"),
    )

    for raw, expected in normalised_cases:
        assert validate_spanish_tax_id(raw) == expected


def test_invalid_nie_inputs_are_rejected_with_instructive_messages() -> None:
    shape_message = "NIE must be a leading X/Y/Z plus 7 digits and a checksum letter"
    cases = (
        # X1234567 has check letter L (01234567 % 23 = 19); Z is wrong.
        ("X1234567Z", "NIE checksum letter is invalid"),
        ("X123A567L", shape_message),
        # A NIE control character must be a letter, never a digit.
        ("X12345678", shape_message),
        ("X123456L", "9 characters long"),
        ("   ", "must not be blank"),
    )

    for candidate, expected_message in cases:
        with pytest.raises(IdentityError, match=expected_message):
            validate_spanish_tax_id(candidate)

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


class TestValidateSpanishTaxIdNie:
    """NIE acceptance and rejection on the canonical-string validator."""

    @pytest.mark.parametrize(
        ("candidate", "substituted"),
        [
            # X -> 0: 01234567 % 23 = 19 -> L
            pytest.param("X1234567L", 1234567, id="x-prefix"),
            # Y -> 1: 10000000 % 23 = 14 -> Z
            pytest.param("Y0000000Z", 10000000, id="y-prefix"),
            # Z -> 2: 20000000 % 23 = 5 -> M
            pytest.param("Z0000000M", 20000000, id="z-prefix"),
            # Y -> 1: 15678901 % 23 = 8 -> P
            pytest.param("Y5678901P", 15678901, id="y-prefix-nonzero"),
            # Z -> 2: 22345678 % 23 = 5 -> M
            pytest.param("Z2345678M", 22345678, id="z-prefix-nonzero"),
        ],
    )
    def test_valid_nie_accepted_and_returned_canonical(self, candidate: str, substituted: int) -> None:
        # The asserted check letter is derived from the AEAT table, not the
        # validator: prove the fixture's check letter is the algorithm's answer.
        assert candidate[-1] == nif_check_letter(substituted)
        assert validate_spanish_tax_id(candidate) == candidate

    def test_lowercase_prefix_normalised(self) -> None:
        assert validate_spanish_tax_id("x1234567l") == "X1234567L"

    def test_surrounding_whitespace_and_dashes_tolerated(self) -> None:
        assert validate_spanish_tax_id("  X-1234567-L  ") == "X1234567L"

    def test_es_prefixed_nie_stripped(self) -> None:
        # The foreign-facing VAT form ``ES`` + NIE is accepted and the ES
        # prefix stripped to the canonical 9-character identifier.
        assert validate_spanish_tax_id("ESX1234567L") == "X1234567L"

    def test_wrong_check_letter_rejected(self) -> None:
        # X1234567 has check letter L (01234567 % 23 = 19); Z is wrong.
        with pytest.raises(IdentityError, match="NIE checksum letter is invalid"):
            validate_spanish_tax_id("X1234567Z")

    def test_non_digit_body_rejected_with_instructive_message(self) -> None:
        with pytest.raises(
            IdentityError,
            match="NIE must be a leading X/Y/Z plus 7 digits and a checksum letter",
        ):
            validate_spanish_tax_id("X123A567L")

    def test_digit_control_rejected_with_instructive_message(self) -> None:
        # A NIE control character must be a letter, never a digit.
        with pytest.raises(
            IdentityError,
            match="NIE must be a leading X/Y/Z plus 7 digits and a checksum letter",
        ):
            validate_spanish_tax_id("X12345678")

    def test_too_short_nie_rejected(self) -> None:
        with pytest.raises(IdentityError, match="9 characters long"):
            validate_spanish_tax_id("X123456L")

    def test_blank_rejected(self) -> None:
        with pytest.raises(IdentityError, match="must not be blank"):
            validate_spanish_tax_id("   ")

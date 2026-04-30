"""Tests for the Spanish identity-document validator."""

from __future__ import annotations

import pytest

from . import IdentityDocument, IdentityError, validate_identity

pytestmark = [pytest.mark.unit, pytest.mark.domain_local_state]


class TestNif:
    """Spanish NIF (8 digits + check letter)."""

    @pytest.mark.parametrize(
        "candidate",
        [
            # AEAT example: 00000000T -> 0 % 23 = 0 -> T
            "00000000T",
            # 12345678Z -> 12345678 % 23 = 14 -> Z
            "12345678Z",
            # 87654321X -> 87654321 % 23 = 10 -> X
            "87654321X",
        ],
    )
    def test_valid_nif_round_trip(self, candidate: str) -> None:
        assert validate_identity(candidate) is IdentityDocument.NIF

    def test_lowercase_input_normalised(self) -> None:
        assert validate_identity("12345678z") is IdentityDocument.NIF

    def test_surrounding_whitespace_trimmed(self) -> None:
        assert validate_identity("  12345678Z  ") is IdentityDocument.NIF

    def test_dash_separator_tolerated(self) -> None:
        assert validate_identity("12345678-Z") is IdentityDocument.NIF

    def test_wrong_check_letter_rejected(self) -> None:
        with pytest.raises(IdentityError):
            validate_identity("12345678A")

    def test_too_short_rejected(self) -> None:
        with pytest.raises(IdentityError):
            validate_identity("1234567Z")

    def test_too_long_rejected(self) -> None:
        with pytest.raises(IdentityError):
            validate_identity("123456789Z")


class TestNie:
    """Spanish NIE (X/Y/Z + 7 digits + check letter)."""

    @pytest.mark.parametrize(
        "candidate",
        [
            # X1234567L -> 01234567 % 23 = 0 + offset; verify by direct table.
            # Computed: 01234567 % 23 = 1234567 % 23 = 16 -> L
            "X1234567L",
            # Y0000000Z -> 10000000 % 23 = 14 -> Z
            "Y0000000Z",
            # Z0000000M -> 20000000 % 23 = 5 -> M
            "Z0000000M",
        ],
    )
    def test_valid_nie_round_trip(self, candidate: str) -> None:
        assert validate_identity(candidate) is IdentityDocument.NIE

    def test_lowercase_prefix_normalised(self) -> None:
        assert validate_identity("x1234567L") is IdentityDocument.NIE

    def test_wrong_check_letter_rejected(self) -> None:
        with pytest.raises(IdentityError):
            validate_identity("X1234567Z")

    def test_invalid_prefix_rejected(self) -> None:
        with pytest.raises(IdentityError):
            validate_identity("W1234567L")  # W is a CIF kind, not a NIE prefix


class TestCif:
    """Spanish CIF (kind letter + 7 digits + check character)."""

    def test_valid_digit_only_kind(self) -> None:
        # A12345674 — kind A is digit-only.
        # sum = (1*2/sum-digits) + 2 + (3*2) + 4 + (5*2/sd) + 6 + (7*2/sd)
        #     =  2 + 2 + 6 + 4 + 1 (10 -> 1+0) + 6 + 5 (14 -> 1+4) = 26
        # check = (10 - 26 % 10) % 10 = (10 - 6) % 10 = 4
        assert validate_identity("A12345674") is IdentityDocument.CIF

    def test_valid_letter_only_kind(self) -> None:
        # Reuse same digit body 1234567 -> check int 4 -> letter D.
        assert validate_identity("P1234567D") is IdentityDocument.CIF

    def test_mixed_kind_accepts_digit(self) -> None:
        # Kind C (mixed): digit form acceptable.
        assert validate_identity("C12345674") is IdentityDocument.CIF

    def test_mixed_kind_accepts_letter(self) -> None:
        # Same C kind, letter form (D for index 4).
        assert validate_identity("C1234567D") is IdentityDocument.CIF

    def test_wrong_check_rejected(self) -> None:
        with pytest.raises(IdentityError):
            validate_identity("A12345670")

    def test_invalid_kind_letter_rejected(self) -> None:
        # I, K, O, T, X, Y, Z are not valid CIF kind letters.
        # I should be misinterpreted as a NIF first because of leading-letter logic;
        # NIF requires 8 digits. So this still raises.
        with pytest.raises(IdentityError):
            validate_identity("I12345674")


class TestRejection:
    """Non-strings, empty values, and arbitrary garbage are rejected."""

    def test_empty_string_rejected(self) -> None:
        with pytest.raises(IdentityError):
            validate_identity("")

    def test_whitespace_only_rejected(self) -> None:
        with pytest.raises(IdentityError):
            validate_identity("   ")

    def test_non_string_rejected(self) -> None:
        from typing import cast

        with pytest.raises(IdentityError):
            validate_identity(cast(str, 12345))

    def test_arbitrary_garbage_rejected(self) -> None:
        with pytest.raises(IdentityError):
            validate_identity("not-an-identity-doc")


class TestErrorCodeBinding:
    def test_class_binds_to_registered_code(self) -> None:
        from ..errors._registry import bind_error_code

        bound = bind_error_code(IdentityError)
        assert bound.code == "INTEGRITY_IDENTITY_DOCUMENT"
        assert bound.category.value == "INTEGRITY"

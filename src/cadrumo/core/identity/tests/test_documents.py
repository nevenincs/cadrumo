"""Tests for :func:`cadrumo.core.identity.validate_identity` and friends.

Covers the three accepted shapes (NIF / NIE / CIF) including check-letter
disambiguation across digit-only, letter-only, and mixed CIF kinds, plus
every documented rejection mode (empty / non-string / arbitrary garbage).
A final test pins the :class:`cadrumo.core.identity.IdentityError` registry
binding so removing the bound error code is a CI failure.
"""

from __future__ import annotations

import pytest

from .. import IdentityDocument, IdentityError, validate_identity

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]


def test_valid_identity_document_variants_round_trip() -> None:
    cases: tuple[tuple[str, tuple[str, ...], IdentityDocument], ...] = (
        (
            "nif",
            (
                "00000000T",
                "12345678Z",
                "87654321X",
                "12345678z",
                "  12345678Z  ",
                "12345678-Z",
            ),
            IdentityDocument.NIF,
        ),
        (
            "nie",
            (
                "X1234567L",
                "Y0000000Z",
                "Z0000000M",
                "x1234567L",
            ),
            IdentityDocument.NIE,
        ),
        (
            "cif",
            ("A12345674", "P1234567D", "C12345674", "C1234567D"),
            IdentityDocument.CIF,
        ),
    )

    for label, candidates, expected in cases:
        for candidate in candidates:
            assert validate_identity(candidate) is expected, (label, candidate)


def test_check_letter_mismatches_carry_operator_context() -> None:
    """Check failures name the body and correct letter needed for one-step repair."""
    cases: tuple[tuple[str, dict[str, str]], ...] = (
        ("12345678A", {"digits": "12345678", "expected": "Z", "got": "A"}),
        ("X1234567Z", {"body": "X1234567", "expected": "L", "got": "Z"}),
    )

    for candidate, expected_context in cases:
        with pytest.raises(IdentityError) as excinfo:
            validate_identity(candidate)
        context = excinfo.value.context
        assert context is not None, candidate
        for key, expected_value in expected_context.items():
            assert context[key] == expected_value, candidate


def test_invalid_documents_rejected_with_expected_message() -> None:
    # "not-an-identity-doc" upper-cases to "NOTANIDENTITYDOC"; leading
    # 'N' is in _CIF_KIND_LETTERS so the validator dispatches to CIF,
    # whose regex expects exactly [kind-letter][7 digits][char].
    non_string: object = 12345
    assert not isinstance(non_string, str)
    cases: tuple[tuple[object, str], ...] = (
        ("", "errors.identity.document_empty"),
        ("   ", "errors.identity.document_empty"),
        (non_string, "errors.identity.validate_expects_str"),
        ("not-an-identity-doc", "errors.identity.cif_invalid_shape"),
        ("1234567Z", "errors.identity.nif_invalid_shape"),
        ("123456789Z", "errors.identity.nif_invalid_shape"),
        ("W1234567L", "errors.identity.cif_invalid_shape"),
        ("A12345670", "errors.identity.cif_check_digit_mismatch"),
        ("I12345674", "errors.identity.nif_invalid_shape"),
        ("12345678A", "errors.identity.nif_check_letter_mismatch"),
        ("NOTANIF", "errors.identity.cif_invalid_shape"),
    )
    for candidate, expected_message in cases:
        with pytest.raises(IdentityError) as excinfo:
            validate_identity(candidate)
        assert excinfo.value.translated_message == expected_message, candidate


class TestActionableMessages:
    """The resolved operator-facing message must be actionable.

    A taxpayer does not know the modulo-23 checksum algorithm. A
    rejection that only says "not valid" forces trial-and-error; the
    resolved message must instead name the correct check letter (for a
    checksum failure) or describe the expected document shape (for a
    malformed input).
    """

    def test_checksum_message_names_correct_letter(self) -> None:
        from ...errors.error_codes import resolve_error_message

        cases = (
            ("12345678A", "12345678", "Z"),
            ("X1234567Z", "X1234567", "L"),
        )
        for candidate, expected_body, expected_letter in cases:
            with pytest.raises(IdentityError) as excinfo:
                validate_identity(candidate)
            message = resolve_error_message(excinfo.value)
            assert expected_body in message
            assert expected_letter in message

    def test_malformed_document_messages_state_expected_shape(self) -> None:
        from ...errors.error_codes import resolve_error_message

        cases = (
            # The NIF shape rule must be stated: 8 digits + a check letter.
            ("1234567Z", "errors.identity.nif_invalid_shape", "8"),
            # Leading X routes to NIE; six digits is the wrong NIE shape.
            ("X123456Z", "errors.identity.nie_invalid_shape", "X"),
        )
        for candidate, expected_translated_message, expected_fragment in cases:
            with pytest.raises(IdentityError) as excinfo:
                validate_identity(candidate)
            message = resolve_error_message(excinfo.value)
            assert excinfo.value.translated_message == expected_translated_message
            assert expected_fragment in message


class TestCifKindCatalogue:
    """Pin the distinction between NIF prefixes and CIF kind letters."""

    def test_nif_prefix_absent_from_cif_kind_letters(self) -> None:
        from .._documents import _CIF_KIND_LETTERS

        for nif_prefix in ("K", "L", "M"):
            assert nif_prefix not in _CIF_KIND_LETTERS

    def test_current_prefixed_nif_variants_validate_as_nif(self) -> None:
        from .._tax_id import validate_spanish_tax_id

        for candidate in ("K1234567L", "L1234567L", "M1234567L"):
            assert validate_spanish_tax_id(candidate) == candidate
            assert validate_identity(candidate) is IdentityDocument.NIF

        for candidate in ("K1234567D", "L1234567D", "M1234567D"):
            with pytest.raises(IdentityError) as excinfo:
                validate_identity(candidate)
            assert excinfo.value.translated_message == "errors.identity.nif_check_letter_mismatch"


class TestErrorCodeBinding:
    def test_class_binds_to_registered_code(self) -> None:
        from ...errors.error_codes import bind_error_code

        bound = bind_error_code(IdentityError)
        assert bound is not None
        assert bound.code == "INTEGRITY_IDENTITY_DOCUMENT"
        assert bound.category.value == "INTEGRITY"

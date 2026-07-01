"""Tests for :func:`aeat.core.identity.validate_identity` and friends.

Covers the three accepted shapes (NIF / NIE / CIF) including check-letter
disambiguation across digit-only, letter-only, and mixed CIF kinds, plus
every documented rejection mode (empty / non-string / arbitrary garbage).
A final test pins the :class:`aeat.core.identity.IdentityError` registry
binding so removing the bound error code is a CI failure.
"""

from __future__ import annotations

import pytest

from .. import IdentityDocument, IdentityError, validate_identity

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]


class TestNif:
    """Spanish NIF (8 digits + check letter)."""

    def test_valid_nif_variants_round_trip(self) -> None:
        candidates = (
            # AEAT example: 00000000T -> 0 % 23 = 0 -> T
            "00000000T",
            # 12345678Z -> 12345678 % 23 = 14 -> Z
            "12345678Z",
            # 87654321X -> 87654321 % 23 = 10 -> X
            "87654321X",
            "12345678z",
            "  12345678Z  ",
            "12345678-Z",
        )
        for candidate in candidates:
            assert validate_identity(candidate) is IdentityDocument.NIF

    def test_wrong_check_letter_rejected_with_correct_letter_context(self) -> None:
        """The rejection carries the numeric body and the correct check letter.

        An operator who typed ``12345678A`` must be told that the check
        letter for ``12345678`` is ``Z`` — a one-step fix — rather than
        an opaque "not valid" refusal. The context feeds the localised
        ``nif_check_letter_mismatch`` message that interpolates them.
        """

        with pytest.raises(IdentityError) as excinfo:
            validate_identity("12345678A")
        context = excinfo.value.context
        assert context is not None
        assert context["digits"] == "12345678"
        assert context["expected"] == "Z"
        assert context["got"] == "A"

    def test_invalid_shape_rejected(self) -> None:
        for candidate in ("1234567Z", "123456789Z"):
            with pytest.raises(IdentityError) as excinfo:
                validate_identity(candidate)
            assert excinfo.value.translated_message == "errors.identity.nif_invalid_shape"


class TestNie:
    """Spanish NIE (X/Y/Z + 7 digits + check letter)."""

    def test_valid_nie_variants_round_trip(self) -> None:
        candidates = (
            # X1234567L -> 01234567 % 23 = 0 + offset; verify by direct table.
            # Computed: 01234567 % 23 = 1234567 % 23 = 16 -> L
            "X1234567L",
            # Y0000000Z -> 10000000 % 23 = 14 -> Z
            "Y0000000Z",
            # Z0000000M -> 20000000 % 23 = 5 -> M
            "Z0000000M",
            "x1234567L",
        )
        for candidate in candidates:
            assert validate_identity(candidate) is IdentityDocument.NIE

    def test_wrong_check_letter_rejected_with_correct_letter_context(self) -> None:
        """The rejection carries the NIE body and the correct check letter.

        ``X1234567`` has check letter ``L``; an operator who typed
        ``X1234567Z`` must be told the correct letter so the fix is a
        single character, not a guess.
        """

        with pytest.raises(IdentityError) as excinfo:
            validate_identity("X1234567Z")
        context = excinfo.value.context
        assert context is not None
        assert context["body"] == "X1234567"
        assert context["expected"] == "L"
        assert context["got"] == "Z"

    def test_invalid_prefix_rejected(self) -> None:
        # W is a CIF kind-letter (letter-only family), not a NIE prefix.
        # The validator routes W to CIF; the CIF regex constrains the
        # control character to ``[0-9A-J]`` and 'L' is outside that set,
        # so the shape regex fails before any checksum runs.
        with pytest.raises(IdentityError) as excinfo:
            validate_identity("W1234567L")
        assert excinfo.value.translated_message == "errors.identity.cif_invalid_shape"


class TestCif:
    """Spanish CIF (kind letter + 7 digits + check character)."""

    def test_valid_cif_round_trip(self) -> None:
        for candidate in ("A12345674", "P1234567D", "C12345674", "C1234567D"):
            assert validate_identity(candidate) is IdentityDocument.CIF

    def test_wrong_check_rejected(self) -> None:
        with pytest.raises(IdentityError) as excinfo:
            validate_identity("A12345670")
        assert excinfo.value.translated_message == "errors.identity.cif_check_digit_mismatch"

    def test_invalid_kind_letter_rejected(self) -> None:
        # I, K, O, T, X, Y, Z are not valid CIF kind letters.
        # I is not in _CIF_KIND_LETTERS, so the validator falls through
        # to NIF dispatch — NIF requires 8 digits, so the regex fails.
        with pytest.raises(IdentityError) as excinfo:
            validate_identity("I12345674")
        assert excinfo.value.translated_message == "errors.identity.nif_invalid_shape"


class TestRejection:
    """Non-strings, empty values, and arbitrary garbage are rejected."""

    def test_invalid_documents_rejected(self) -> None:
        # "not-an-identity-doc" upper-cases to "NOTANIDENTITYDOC"; leading
        # 'N' is in _CIF_KIND_LETTERS so the validator dispatches to CIF,
        # whose regex expects exactly [kind-letter][7 digits][char] — the
        # garbage shape fails the CIF regex.
        non_string: object = 12345
        assert not isinstance(non_string, str)
        cases: tuple[tuple[object, str], ...] = (
            ("", "errors.identity.document_empty"),
            ("   ", "errors.identity.document_empty"),
            (non_string, "errors.identity.validate_expects_str"),
            ("not-an-identity-doc", "errors.identity.cif_invalid_shape"),
        )
        for candidate, expected_message in cases:
            with pytest.raises(IdentityError) as excinfo:
                validate_identity(candidate)
            assert excinfo.value.translated_message == expected_message


class TestActionableMessages:
    """The resolved operator-facing message must be actionable.

    A taxpayer does not know the modulo-23 checksum algorithm. A
    rejection that only says "not valid" forces trial-and-error; the
    resolved message must instead name the correct check letter (for a
    checksum failure) or describe the expected document shape (for a
    malformed input).
    """

    def test_checksum_message_names_correct_letter(self) -> None:
        from ...errors import resolve_error_message

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
        from ...errors import resolve_error_message

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
        from ....core.errors._registry import bind_error_code

        bound = bind_error_code(IdentityError)
        assert bound is not None
        assert bound.code == "INTEGRITY_IDENTITY_DOCUMENT"
        assert bound.category.value == "INTEGRITY"


class TestNifHardeningRejection:
    """Regression gate: validate_identity rejects malformed NIFs that a bare
    strip().upper() normaliser would silently pass through.

    The canonical bug is: ``_normalise_tax_identity("12345678A")`` returns
    ``"12345678A"`` (string passes through untouched) while
    ``validate_identity("12345678A")`` raises ``IdentityError`` because the
    check-letter for ``12345678`` is ``Z``, not ``A``.  This class pins that
    validate_identity is the correct boundary enforcer.
    """

    def test_malformed_nifs_rejected_not_silently_normalised(self) -> None:
        cases = (
            ("12345678A", "errors.identity.nif_check_letter_mismatch"),
            ("1234567Z", "errors.identity.nif_invalid_shape"),
            ("NOTANIF", None),
        )
        for candidate, expected_message in cases:
            with pytest.raises(IdentityError) as excinfo:
                validate_identity(candidate)
            if expected_message is not None:
                assert excinfo.value.translated_message == expected_message

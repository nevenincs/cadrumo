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
        with pytest.raises(IdentityError) as excinfo:
            validate_identity("12345678A")
        assert excinfo.value.translated_message == "errors.identity.nif_check_letter_mismatch"

    def test_wrong_check_letter_error_names_correct_letter(self) -> None:
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

    def test_too_short_rejected(self) -> None:
        with pytest.raises(IdentityError) as excinfo:
            validate_identity("1234567Z")
        assert excinfo.value.translated_message == "errors.identity.nif_invalid_shape"

    def test_too_long_rejected(self) -> None:
        with pytest.raises(IdentityError) as excinfo:
            validate_identity("123456789Z")
        assert excinfo.value.translated_message == "errors.identity.nif_invalid_shape"


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
        with pytest.raises(IdentityError) as excinfo:
            validate_identity("X1234567Z")
        assert excinfo.value.translated_message == "errors.identity.nie_check_letter_mismatch"

    def test_wrong_check_letter_error_names_correct_letter(self) -> None:
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

    def test_empty_string_rejected(self) -> None:
        with pytest.raises(IdentityError) as excinfo:
            validate_identity("")
        assert excinfo.value.translated_message == "errors.identity.document_empty"

    def test_whitespace_only_rejected(self) -> None:
        with pytest.raises(IdentityError) as excinfo:
            validate_identity("   ")
        assert excinfo.value.translated_message == "errors.identity.document_empty"

    def test_non_string_rejected(self) -> None:
        non_string: object = 12345
        assert not isinstance(non_string, str)
        with pytest.raises(IdentityError) as excinfo:
            validate_identity(non_string)  # type: ignore[arg-type]  # ty: ignore[invalid-argument-type]  # pyrefly: ignore[bad-argument-type]  # reason: deliberate non-string to exercise runtime guard
        assert excinfo.value.translated_message == "errors.identity.validate_expects_str"

    def test_arbitrary_garbage_rejected(self) -> None:
        # "not-an-identity-doc" upper-cases to "NOTANIDENTITYDOC"; leading
        # 'N' is in _CIF_KIND_LETTERS so the validator dispatches to CIF,
        # whose regex expects exactly [kind-letter][7 digits][char] — the
        # garbage shape fails the CIF regex.
        with pytest.raises(IdentityError) as excinfo:
            validate_identity("not-an-identity-doc")
        assert excinfo.value.translated_message == "errors.identity.cif_invalid_shape"


class TestActionableMessages:
    """The resolved operator-facing message must be actionable.

    A taxpayer does not know the modulo-23 checksum algorithm. A
    rejection that only says "not valid" forces trial-and-error; the
    resolved message must instead name the correct check letter (for a
    checksum failure) or describe the expected document shape (for a
    malformed input).
    """

    def test_nif_checksum_message_names_correct_letter(self) -> None:
        from ...errors import resolve_error_message

        with pytest.raises(IdentityError) as excinfo:
            validate_identity("12345678A")
        message = resolve_error_message(excinfo.value)
        assert "12345678" in message
        assert "Z" in message

    def test_nie_checksum_message_names_correct_letter(self) -> None:
        from ...errors import resolve_error_message

        with pytest.raises(IdentityError) as excinfo:
            validate_identity("X1234567Z")
        message = resolve_error_message(excinfo.value)
        assert "X1234567" in message
        assert "L" in message

    def test_malformed_nif_message_states_expected_shape(self) -> None:
        from ...errors import resolve_error_message

        with pytest.raises(IdentityError) as excinfo:
            validate_identity("1234567Z")
        message = resolve_error_message(excinfo.value)
        # The shape rule must be stated: 8 digits + a check letter.
        assert "8" in message

    def test_malformed_nie_message_states_expected_shape(self) -> None:
        from ...errors import resolve_error_message

        # Leading X routes to NIE; six digits is the wrong NIE shape.
        with pytest.raises(IdentityError) as excinfo:
            validate_identity("X123456Z")
        message = resolve_error_message(excinfo.value)
        assert excinfo.value.translated_message == "errors.identity.nie_invalid_shape"
        # The shape rule names the X/Y/Z prefix.
        assert "X" in message


class TestCifKindLetterSplit:
    """Pin the intentional split between _CIF_KIND_LETTERS and _CIF_LEADERS.

    ``_CIF_KIND_LETTERS`` is the AEAT current-spec closed catalogue (17
    letters).  ``_tax_id._CIF_LEADERS`` is the historical-tolerance superset
    (20 letters) that keeps K, L, and M so that ``validate_spanish_tax_id``
    accepts legacy entities.  These tests prevent a future consolidation from
    silently collapsing the two sets.
    """

    def test_k_l_m_absent_from_cif_kind_letters(self) -> None:
        from .._documents import _CIF_KIND_LETTERS

        assert "K" not in _CIF_KIND_LETTERS
        assert "L" not in _CIF_KIND_LETTERS
        assert "M" not in _CIF_KIND_LETTERS

    def test_validate_spanish_tax_id_accepts_k_led_cif(self) -> None:
        # Synthetic K-led CIF: K + 1234567 + check character.
        # K is in _CIF_LETTER_CONTROL_LEADERS so the check must be a letter.
        # Computed: even_sum=12, odd_sum_doubled=14, total=26,
        # digit_control=4, letter_control=_CIF_CONTROL_LETTERS[4]='D'.
        from .._tax_id import validate_spanish_tax_id

        result = validate_spanish_tax_id("K1234567D")
        assert result == "K1234567D"


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

    def test_wrong_check_letter_rejected_not_silently_normalised(self) -> None:
        # 12345678 % 23 = 14 -> correct check letter is Z, not A.
        # A bare strip().upper() would accept "12345678A" as a string.
        with pytest.raises(IdentityError) as excinfo:
            validate_identity("12345678A")
        assert excinfo.value.translated_message == "errors.identity.nif_check_letter_mismatch"

    def test_short_nif_rejected_not_silently_normalised(self) -> None:
        # 7 digits + check letter: wrong shape; bare normaliser returns "1234567Z".
        with pytest.raises(IdentityError) as excinfo:
            validate_identity("1234567Z")
        assert excinfo.value.translated_message == "errors.identity.nif_invalid_shape"

    def test_uppercase_garbage_rejected_not_silently_normalised(self) -> None:
        # "NOTANIF" would be returned unchanged by strip().upper(); rejected by validate_identity.
        with pytest.raises(IdentityError):
            validate_identity("NOTANIF")

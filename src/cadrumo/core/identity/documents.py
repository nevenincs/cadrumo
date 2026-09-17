"""Spanish tax-identifier parser and check-character validator.

This module owns the immutable format shape and pure validation arithmetic,
while a caller supplies every operative declaration from its authority. Core
validation performs no registry lookup, file access, or provider registration.
The public :func:`validate_identity` parser returns an
:class:`IdentityDocument` member and raises :class:`IdentityError` on
malformed input.  Callers that need the canonical string form use
:func:`~cadrumo.core.identity.tax_id.validate_spanish_tax_id`.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from enum import StrEnum

from ..errors.hierarchy import CadrumoError

TAX_ID_FORMAT_CONTEXT = "spanish_tax_id_format"


@dataclass(frozen=True, slots=True)
class SpanishTaxIdFormat:
    """Immutable declarations required by the pure Spanish tax-ID kernel.

    This type defines structure only.  Every operative value is supplied by a
    governed authority fact and no default is intentionally available here.
    """

    width: int
    country_prefix: str
    country_prefixed_width: int
    country_prefix_strip_width: int
    prefixed_nif_leaders: str
    nie_leaders: str
    cif_leaders: str
    nif_letters: str
    nie_prefix_substitutions: tuple[tuple[str, str], ...]
    cif_digit_only_kinds: str
    cif_letter_only_kinds: str
    cif_letter_table: str

    def __post_init__(self) -> None:
        """Reject incomplete or internally inconsistent declarations."""
        if self.width < 3 or self.country_prefixed_width != self.width + self.country_prefix_strip_width:
            raise ValueError("Spanish tax-ID format has invalid widths")
        if self.country_prefix_strip_width <= 0 or len(self.country_prefix) != self.country_prefix_strip_width:
            raise ValueError("Spanish tax-ID format has an invalid country prefix")
        if not self.country_prefix.isascii() or not self.country_prefix.isalpha() or not self.country_prefix.isupper():
            raise ValueError("Spanish tax-ID format country prefix must contain uppercase ASCII letters")
        if not all((self.prefixed_nif_leaders, self.nie_leaders, self.cif_leaders)):
            raise ValueError("Spanish tax-ID format leader sets must not be empty")
        if (
            len(self.nif_letters) != 23
            or not self.nif_letters.isascii()
            or not self.nif_letters.isalpha()
            or not self.nif_letters.isupper()
            or len(set(self.nif_letters)) != len(self.nif_letters)
        ):
            raise ValueError(
                "Spanish tax-ID format NIF check-letter table must contain 23 unique uppercase ASCII letters"
            )
        if (
            len(self.cif_letter_table) != 10
            or not self.cif_letter_table.isascii()
            or not self.cif_letter_table.isalpha()
            or not self.cif_letter_table.isupper()
            or len(set(self.cif_letter_table)) != len(self.cif_letter_table)
        ):
            raise ValueError(
                "Spanish tax-ID format CIF check-letter table must contain ten unique uppercase ASCII letters"
            )
        substitutions = dict(self.nie_prefix_substitutions)
        if len(substitutions) != len(self.nie_prefix_substitutions) or set(substitutions) != set(self.nie_leaders):
            raise ValueError("Spanish tax-ID format NIE substitutions must cover every NIE leader exactly once")
        if not all(len(value) == 1 and value.isascii() and value.isdigit() for value in substitutions.values()):
            raise ValueError(
                "Spanish tax-ID format NIE substitutions must be single decimal digits using ASCII characters"
            )
        if set(self.cif_digit_only_kinds) & set(self.cif_letter_only_kinds):
            raise ValueError("Spanish tax-ID format CIF control partitions must not overlap")
        leaders = self.prefixed_nif_leaders + self.nie_leaders + self.cif_leaders
        if not leaders.isascii() or not leaders.isalpha() or not leaders.isupper() or len(set(leaders)) != len(leaders):
            raise ValueError("Spanish tax-ID format leaders must be unique uppercase ASCII letters")
        if not set(self.cif_digit_only_kinds + self.cif_letter_only_kinds).issubset(set(self.cif_leaders)):
            raise ValueError("Spanish tax-ID format CIF control partitions must name CIF leaders")
        if len(set(self.cif_digit_only_kinds)) != len(self.cif_digit_only_kinds) or len(
            set(self.cif_letter_only_kinds)
        ) != len(self.cif_letter_only_kinds):
            raise ValueError("Spanish tax-ID format CIF control partitions must not repeat leaders")


def _nif_pattern(tax_id_format: SpanishTaxIdFormat) -> re.Pattern[str]:
    """Build the NIF shape gate from the authored width declaration."""
    return re.compile(rf"^(\d{{{tax_id_format.width - 1}}})([A-Z])$")


def _prefixed_nif_pattern(tax_id_format: SpanishTaxIdFormat) -> re.Pattern[str]:
    """Build the prefixed-NIF shape gate from authored width and leaders."""
    leaders = re.escape(tax_id_format.prefixed_nif_leaders)
    return re.compile(rf"^([{leaders}])(\d{{{tax_id_format.width - 2}}})([A-Z])$")


def _nie_pattern(tax_id_format: SpanishTaxIdFormat) -> re.Pattern[str]:
    """Build the NIE shape gate from authored width and leaders."""
    leaders = re.escape(tax_id_format.nie_leaders)
    return re.compile(rf"^([{leaders}])(\d{{{tax_id_format.width - 2}}})([A-Z])$")


def _cif_pattern(tax_id_format: SpanishTaxIdFormat) -> re.Pattern[str]:
    """Build the CIF shape gate from authored width and leaders."""
    leaders = re.escape(tax_id_format.cif_leaders)
    return re.compile(rf"^([{leaders}])(\d{{{tax_id_format.width - 2}}})(.)$")


class IdentityDocument(StrEnum):
    """Closed catalogue of recognised Spanish identity-document kinds.

    Attributes:
        NIF: Número de Identificación Fiscal — Spanish nationals.
        NIE: Número de Identidad de Extranjero — foreign residents.
        CIF: Código de Identificación Fiscal — legal entities.
    """

    NIF = "NIF"
    NIE = "NIE"
    CIF = "CIF"


def is_identity_structurally_shaped(candidate: object) -> bool:
    """Return whether *candidate* has a tax-identity lexical shape.

    This is intentionally a syntax-only admission predicate for low-level
    consumers such as redaction. It does not claim that the candidate is a
    currently recognised Spanish NIF, NIE, or CIF: leader membership,
    checksum tables, and control-character partitions remain supplied by an
    explicit authority format to :func:`validate_identity`.
    """
    if not isinstance(candidate, str):
        return False
    normalised = candidate.strip().upper().replace("-", "").replace(" ", "").replace(".", "")
    if not normalised.isascii() or not normalised.isalnum():
        return False
    return bool(re.fullmatch(r"[0-9]+[A-Z]", normalised) or re.fullmatch(r"[A-Z][0-9]+[A-Z0-9]", normalised))


class IdentityError(CadrumoError):
    """Raised when a candidate string is not a valid Spanish identity document.

    Bound to the registered error code ``INTEGRITY_IDENTITY_DOCUMENT``
    in :data:`~core.errors.registry.declared_codes.ALL_DECLARED_ERROR_CODES`. Carries a human-readable
    diagnostic that names the failing shape (``NIF``, ``NIE``, ``CIF``)
    and, where relevant, the expected vs observed check character.

    Its canonical registered ancestry is :class:`CadrumoError`. Pydantic
    validators translate this registered failure to ``ValueError`` at their
    narrow validator boundary.
    """


def nif_check_letter(number: int, tax_id_format: SpanishTaxIdFormat) -> str:
    """Return the AEAT NIF / NIE check letter for a numeric body.

    Resolves the governed check-letter table without retaining a local
    catalogue. This is the single source of the check-letter computation for
    the whole :mod:`cadrumo.core.identity` package; the sibling
    :mod:`cadrumo.core.identity.tax_id` consumes it rather than re-declaring
    the modulo expression, and every enum-returning validator in this module
    computes its expected letter through it.
    """
    return _nif_check_letter(number, tax_id_format)


def _nif_check_letter(number: int, tax_id_format: SpanishTaxIdFormat) -> str:
    """Return one registry-declared NIF/NIE check letter, failing closed."""
    return tax_id_format.nif_letters[number % len(tax_id_format.nif_letters)]


def _cif_check_value(digits: str) -> int:
    """Return the AEAT CIF Luhn-style check value (0-9) for a 7-digit body.

    For each digit position ``i`` (1-indexed) the running sum is built as:

    * odd positions: ``2 * digit``; if the doubled value is >= 10, sum
      its decimal digits (i.e. ``divmod(2*digit, 10)``).
    * even positions: ``digit`` directly.

    The check value is ``(10 - (sum mod 10)) mod 10``. This kernel returns
    the raw integer; :func:`_validate_cif` renders it as a digit or a letter
    and applies the per-kind acceptance policy. That policy exists once, here,
    and both identity surfaces reach it -- the enum-returning
    :func:`validate_identity` and the string-returning
    :func:`cadrumo.core.identity.tax_id.validate_spanish_tax_id`.

    Args:
        digits: The 7-digit body of the CIF.

    Returns:
        The check value as an integer in ``range(10)``.
    """
    total = 0
    for index, raw in enumerate(digits, start=1):
        digit = int(raw)
        if index % 2 == 1:
            doubled = digit * 2
            total += doubled // 10 + doubled % 10
        else:
            total += digit
    return (10 - (total % 10)) % 10


def _validate_nif(candidate: str, tax_id_format: SpanishTaxIdFormat) -> IdentityDocument:
    """Validate a NIF candidate, raising :class:`IdentityError` on mismatch."""
    match = _nif_pattern(tax_id_format).match(candidate)
    if match is None:
        raise IdentityError(
            f"tax identifier {candidate!r} is not shaped like a NIF",
            translated_message="errors.identity.nif_invalid_shape",
            context={"candidate": candidate},
        )
    digits, letter = match.group(1), match.group(2)
    expected = _nif_check_letter(int(digits), tax_id_format)
    if letter != expected:
        raise IdentityError(
            f"NIF checksum mismatch for {digits}: expected check letter {expected!r}, got {letter!r}",
            translated_message="errors.identity.nif_check_letter_mismatch",
            context={"digits": digits, "expected": expected, "got": letter},
        )
    return IdentityDocument.NIF


def _validate_prefixed_nif(candidate: str, tax_id_format: SpanishTaxIdFormat) -> IdentityDocument:
    """Validate a registry-declared prefixed-NIF candidate."""
    match = _prefixed_nif_pattern(tax_id_format).match(candidate)
    if match is None:
        raise IdentityError(
            f"tax identifier {candidate!r} is not shaped like a NIF",
            translated_message="errors.identity.nif_invalid_shape",
            context={"candidate": candidate},
        )
    prefix, digits, letter = match.group(1), match.group(2), match.group(3)
    expected = _nif_check_letter(int(digits), tax_id_format)
    if letter != expected:
        raise IdentityError(
            f"NIF checksum mismatch for {prefix + digits}: expected check letter {expected!r}, got {letter!r}",
            translated_message="errors.identity.nif_check_letter_mismatch",
            context={"digits": prefix + digits, "expected": expected, "got": letter},
        )
    return IdentityDocument.NIF


def _validate_nie(candidate: str, tax_id_format: SpanishTaxIdFormat) -> IdentityDocument:
    """Validate a NIE candidate, raising :class:`IdentityError` on mismatch."""
    match = _nie_pattern(tax_id_format).match(candidate)
    if match is None:
        raise IdentityError(
            f"tax identifier {candidate!r} is not shaped like a NIE",
            translated_message="errors.identity.nie_invalid_shape",
            context={"candidate": candidate},
        )
    prefix, digits, letter = match.group(1), match.group(2), match.group(3)
    numeric_str = dict(tax_id_format.nie_prefix_substitutions)[prefix] + digits
    expected = _nif_check_letter(int(numeric_str), tax_id_format)
    if letter != expected:
        raise IdentityError(
            f"NIE checksum mismatch for {prefix + digits}: expected check letter {expected!r}, got {letter!r}",
            translated_message="errors.identity.nie_check_letter_mismatch",
            context={"body": prefix + digits, "expected": expected, "got": letter},
        )
    return IdentityDocument.NIE


def _validate_cif(candidate: str, tax_id_format: SpanishTaxIdFormat) -> IdentityDocument:
    """Validate a CIF candidate, raising :class:`IdentityError` on mismatch.

    The one home of the CIF leader policy. AEAT partitions the kind letters
    three ways and the registry-declared partition decides which control
    characters are legal. Digit-only kinds accept only the digit form,
    letter-only kinds only the letter form, and every remaining kind accepts
    either, both being historically in circulation.

    The middle class is the one worth naming. A digit-only kind that also
    accepts the letter form is not a laxer reading of the same rule -- it
    accepts an identifier AEAT rejects, so a counterparty passes the boundary
    here and bounces at the sede with the declaration already built.
    """
    match = _cif_pattern(tax_id_format).match(candidate)
    if match is None:
        raise IdentityError(
            f"tax identifier {candidate!r} is not shaped like a CIF",
            translated_message="errors.identity.cif_invalid_shape",
            context={"candidate": candidate},
        )
    kind, digits, check = match.group(1), match.group(2), match.group(3)
    if not check.isalnum():
        raise IdentityError(
            f"CIF checksum control character {check!r} in tax identifier {candidate!r} must be a digit or letter",
            translated_message="errors.identity.cif_control_char_invalid",
            context={"candidate": candidate, "got": check},
        )
    check_int = _cif_check_value(digits)
    expected_digit = str(check_int)
    expected_letter = tax_id_format.cif_letter_table[check_int]
    cif_digit_only_kinds = tax_id_format.cif_digit_only_kinds
    cif_letter_only_kinds = tax_id_format.cif_letter_only_kinds
    if kind in cif_digit_only_kinds:
        if check != expected_digit:
            raise IdentityError(
                f"CIF checksum mismatch (kind {kind}): expected check digit {expected_digit!r}, got {check!r}",
                translated_message="errors.identity.cif_check_digit_mismatch",
                context={"kind": kind, "expected": expected_digit, "got": check},
            )
    elif kind in cif_letter_only_kinds:
        if check != expected_letter:
            raise IdentityError(
                f"CIF checksum mismatch (kind {kind}): expected check letter {expected_letter!r}, got {check!r}",
                translated_message="errors.identity.cif_check_letter_mismatch_kind",
                context={"kind": kind, "expected": expected_letter, "got": check},
            )
    elif check not in (expected_digit, expected_letter):
        raise IdentityError(
            f"CIF checksum mismatch (kind {kind}): expected {expected_digit} or "
            f"check letter {expected_letter!r}, got {check!r}",
            translated_message="errors.identity.cif_check_char_mismatch_mixed",
            context={
                "kind": kind,
                "expected": expected_digit,
                "alt": expected_letter,
                "got": check,
            },
        )
    return IdentityDocument.CIF


def validate_identity(candidate: object, tax_id_format: SpanishTaxIdFormat) -> IdentityDocument:
    """Parse and check-letter-validate a Spanish identity document.

    Disambiguates by the leader sets in the registry-owned mapping, then
    applies the checksum/control algorithm for the selected shape and returns
    the parsed :class:`IdentityDocument`.

    Args:
        candidate: A free-form candidate value. Strings tolerate surrounding
            whitespace, dashes, spaces, and casing; non-string values are
            rejected with a typed :class:`IdentityError`.
        tax_id_format: Complete authority-supplied format declarations.

    Returns:
        The matching :class:`IdentityDocument` enum member.

    Raises:
        IdentityError: When ``candidate`` is not a string, is empty, or
            does not match any valid shape, or when the check letter or
            digit fails the AEAT algorithm.
    """
    if not isinstance(candidate, str):
        raise IdentityError(
            translated_message="errors.identity.validate_expects_str",
            context={"got_type": type(candidate).__name__},
        )
    normalised = candidate.strip().upper().replace("-", "").replace(" ", "")
    if not normalised:
        raise IdentityError(
            "tax identifier is empty",
            translated_message="errors.identity.document_empty",
        )
    prefixed_nif_leaders = tax_id_format.prefixed_nif_leaders
    nie_leaders = tax_id_format.nie_leaders
    cif_leaders = tax_id_format.cif_leaders

    # Try prefixed NIF and NIE first (they have unambiguous prefixes);
    # then CIF (also unambiguous on its leading letter set); then NIF.
    if normalised[0] in prefixed_nif_leaders:
        return _validate_prefixed_nif(normalised, tax_id_format)
    if normalised[0] in nie_leaders:
        return _validate_nie(normalised, tax_id_format)
    if normalised[0] in cif_leaders:
        return _validate_cif(normalised, tax_id_format)
    return _validate_nif(normalised, tax_id_format)

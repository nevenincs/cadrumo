"""Read localized number lexemes and enforce their declared numeric grammar."""

from __future__ import annotations

import re
from decimal import Decimal, InvalidOperation
from typing import Final

from ...core.decimal.grammar import european_thousands_reading_is_ambiguous
from ...core.external_constants import OutputLanguage
from ...domain.calculations.registry.schema_base import CasillaSignConstraint
from ...domain.filing.schema import ModeloScalar
from ...domain.identifiers import canonical_decimal_string
from .edit_locale_input import SPACE_GROUPS, ModeloEditLocaleMarks, locale_marks
from .edit_models import ModeloEditNormalisation, ModeloEditParseReason
from .edit_parse_errors import ModeloEditParseRefusedError
from .edit_value_grammar import MONEY_OPERAND_MAXIMUM, ModeloEditValueFamily, ModeloEditValueGrammarV1

_NON_FINITE: Final = frozenset({"nan", "-nan", "inf", "-inf", "infinity", "-infinity", "+inf", "+infinity"})


_SCIENTIFIC_RE: Final = re.compile(r"^-?[\d.,\s]*\d[eE][+-]?\d+$")


_NUMERIC_CHARS_RE: Final = re.compile(r"^-?[\d.,\s]+$")


_CANONICAL_DECIMAL_RE: Final = re.compile(r"^-?\d+(\.\d+)?$")


_GROUPED_INTEGER_RE: Final = re.compile(r"^[1-9]\d{0,2}$")


def _valid_groups(integer_part: str, separator_set: frozenset[str]) -> str:
    """Return the digits of a grouped integer part, refusing a malformed grouping."""
    pattern = "[" + re.escape("".join(sorted(separator_set))) + "]"
    groups = re.split(pattern, integer_part)
    if len(groups) == 1:
        return integer_part
    if not _GROUPED_INTEGER_RE.fullmatch(groups[0]) or any(
        len(group) != 3 or not group.isdigit() for group in groups[1:]
    ):
        raise ModeloEditParseRefusedError(ModeloEditParseReason.BAD_GROUPING)
    return "".join(groups)


def _split_on_decimal(body: str, decimal_mark: str) -> tuple[str, str | None]:
    head, mark, tail = body.rpartition(decimal_mark)
    if not mark:
        return body, None
    if not tail.isdigit() or not head:
        raise ModeloEditParseRefusedError(ModeloEditParseReason.BAD_GROUPING)
    return head, tail


def _read_single_mark(
    body: str,
    mark: str,
    marks: ModeloEditLocaleMarks,
    normalisations: list[ModeloEditNormalisation],
    sign: str,
) -> str:
    """Read a number carrying one kind of separator, once or repeatedly.

    A single mark that could group thousands or separate decimals is refused
    with both readings, the whole number and the one in this locale's decimal
    mark, each carrying the entry's ``sign``, so the filer can type the one meant.
    """
    count = body.count(mark)
    if count > 1:
        # Repeated, it can only be a grouping, whichever convention it belongs to.
        normalisations.append(ModeloEditNormalisation.SEPARATORS_REMOVED)
        return _valid_groups(body, frozenset({mark}))
    lead, _, tail = body.partition(mark)
    if not lead or not tail.isdigit() or not lead.isdigit():
        raise ModeloEditParseRefusedError(ModeloEditParseReason.BAD_GROUPING)
    if mark == marks.decimal:
        return f"{lead}.{tail}"
    # The mark is this locale's grouping or the other convention's decimal mark.
    if european_thousands_reading_is_ambiguous(f"{lead}.{tail}"):
        raise ModeloEditParseRefusedError(
            ModeloEditParseReason.AMBIGUOUS_SEPARATOR_READINGS,
            f"{sign}{lead}{tail}",
            f"{sign}{lead}{marks.decimal}{tail}",
        )
    normalisations.append(ModeloEditNormalisation.FOREIGN_DECIMAL_MARK_READ)
    return f"{lead}.{tail}"


def read_edit_number_lexeme(
    lexeme: str, locale: OutputLanguage, normalisations: list[ModeloEditNormalisation]
) -> Decimal:
    """Read one localized number into a decimal, refusing anything two-way readable."""
    text = lexeme.strip()
    negative, body = _checked_number_lexeme_shape(text)
    canonical = _localized_number_body(body, locale, normalisations, sign="-" if negative else "")
    if not _CANONICAL_DECIMAL_RE.fullmatch(canonical):
        raise ModeloEditParseRefusedError(ModeloEditParseReason.NOT_A_NUMBER)
    return _finite(f"-{canonical}" if negative else canonical)


def _checked_number_lexeme_shape(text: str) -> tuple[bool, str]:
    if not text:
        raise ModeloEditParseRefusedError(ModeloEditParseReason.EMPTY)
    if text.lower() in _NON_FINITE:
        raise ModeloEditParseRefusedError(ModeloEditParseReason.NON_FINITE)
    if text.startswith("+"):
        raise ModeloEditParseRefusedError(ModeloEditParseReason.EXPLICIT_PLUS)
    if _SCIENTIFIC_RE.fullmatch(text):
        raise ModeloEditParseRefusedError(ModeloEditParseReason.SCIENTIFIC_NOTATION)
    if not _NUMERIC_CHARS_RE.fullmatch(text):
        raise ModeloEditParseRefusedError(ModeloEditParseReason.NOT_A_NUMBER)
    negative = text.startswith("-")
    return negative, text[1:] if negative else text


def _localized_number_body(
    body: str,
    locale: OutputLanguage,
    normalisations: list[ModeloEditNormalisation],
    *,
    sign: str,
) -> str:
    marks = locale_marks(locale)
    canonical = _space_grouped_body(body, marks, normalisations)
    if canonical is not None:
        return canonical
    canonical = _mixed_mark_body(body, marks, normalisations)
    if canonical is not None:
        return canonical
    canonical = _single_mark_body(body, marks, normalisations, sign=sign)
    return body if canonical is None else canonical


def _space_grouped_body(
    body: str,
    marks: ModeloEditLocaleMarks,
    normalisations: list[ModeloEditNormalisation],
) -> str | None:
    if not any(character in SPACE_GROUPS for character in body):
        return None
    if not marks.groups <= SPACE_GROUPS:
        raise ModeloEditParseRefusedError(ModeloEditParseReason.BAD_GROUPING)
    integer_part, fraction = _split_on_decimal(body, marks.decimal)
    if "." in integer_part or "," in integer_part:
        raise ModeloEditParseRefusedError(ModeloEditParseReason.BAD_GROUPING)
    normalisations.append(ModeloEditNormalisation.SEPARATORS_REMOVED)
    digits = _valid_groups(integer_part, SPACE_GROUPS)
    return digits if fraction is None else f"{digits}.{fraction}"


def _mixed_mark_body(
    body: str,
    marks: ModeloEditLocaleMarks,
    normalisations: list[ModeloEditNormalisation],
) -> str | None:
    if "." not in body or "," not in body:
        return None
    # Both marks: the last one is the decimal mark, the other the grouping.
    decimal_mark = "." if body.rfind(".") > body.rfind(",") else ","
    group_mark = "," if decimal_mark == "." else "."
    integer_part, fraction = _split_on_decimal(body, decimal_mark)
    if decimal_mark in integer_part:
        raise ModeloEditParseRefusedError(ModeloEditParseReason.BAD_GROUPING)
    digits = _valid_groups(integer_part, frozenset({group_mark}))
    normalisations.append(ModeloEditNormalisation.SEPARATORS_REMOVED)
    if decimal_mark != marks.decimal:
        normalisations.append(ModeloEditNormalisation.FOREIGN_DECIMAL_MARK_READ)
    return f"{digits}.{fraction}"


def _single_mark_body(
    body: str,
    marks: ModeloEditLocaleMarks,
    normalisations: list[ModeloEditNormalisation],
    *,
    sign: str,
) -> str | None:
    if "." not in body and "," not in body:
        return None
    mark = "." if "." in body else ","
    return _read_single_mark(body, mark, marks, normalisations, sign)


def _finite(canonical: str) -> Decimal:
    try:
        value = Decimal(canonical)
    except InvalidOperation as exc:
        raise ModeloEditParseRefusedError(ModeloEditParseReason.NOT_A_NUMBER) from exc
    if not value.is_finite():
        raise ModeloEditParseRefusedError(ModeloEditParseReason.NON_FINITE)
    return value


def read_typed_edit_number(value: ModeloScalar) -> Decimal:
    """Read an already-typed or machine-canonical value; no locale grammar applies."""
    if isinstance(value, bool):
        raise ModeloEditParseRefusedError(ModeloEditParseReason.NOT_A_NUMBER)
    if isinstance(value, Decimal):
        if not value.is_finite():
            raise ModeloEditParseRefusedError(ModeloEditParseReason.NON_FINITE)
        return value
    if isinstance(value, int):
        return Decimal(value)
    if isinstance(value, str):
        text = value.strip()
        if text.lower() in _NON_FINITE:
            raise ModeloEditParseRefusedError(ModeloEditParseReason.NON_FINITE)
        if text.startswith("+"):
            raise ModeloEditParseRefusedError(ModeloEditParseReason.EXPLICIT_PLUS)
        if _SCIENTIFIC_RE.fullmatch(text):
            raise ModeloEditParseRefusedError(ModeloEditParseReason.SCIENTIFIC_NOTATION)
        if not _CANONICAL_DECIMAL_RE.fullmatch(text):
            raise ModeloEditParseRefusedError(ModeloEditParseReason.NOT_A_NUMBER)
        return _finite(text)
    raise ModeloEditParseRefusedError(ModeloEditParseReason.NOT_A_NUMBER)


def _fraction_digits(value: Decimal) -> int:
    exponent = value.as_tuple().exponent
    return -exponent if isinstance(exponent, int) and exponent < 0 else 0


def validate_edit_number(value: Decimal, grammar: ModeloEditValueGrammarV1) -> Decimal:
    """Apply precision, sign, bounds and the money operand range; never round."""
    value = _apply_number_precision(value, grammar)
    _check_number_sign(value, grammar.sign)
    _check_number_bounds(value, grammar)
    _check_money_operand(value, grammar)
    return value


def _apply_number_precision(value: Decimal, grammar: ModeloEditValueGrammarV1) -> Decimal:
    if grammar.family is ModeloEditValueFamily.INTEGER:
        if value != value.to_integral_value():
            raise ModeloEditParseRefusedError(ModeloEditParseReason.NOT_AN_INTEGER)
        value = Decimal(int(value))
    elif grammar.max_fraction_digits is not None and _fraction_digits(value.normalize()) > grammar.max_fraction_digits:
        raise ModeloEditParseRefusedError(ModeloEditParseReason.TOO_MANY_DECIMALS, str(grammar.max_fraction_digits))

    return value


def _check_number_sign(value: Decimal, sign: CasillaSignConstraint) -> None:
    if sign == CasillaSignConstraint.NON_NEGATIVE and value < 0:
        raise ModeloEditParseRefusedError(ModeloEditParseReason.NEGATIVE_NOT_ALLOWED)
    if sign == CasillaSignConstraint.NON_POSITIVE and value > 0:
        raise ModeloEditParseRefusedError(ModeloEditParseReason.POSITIVE_NOT_ALLOWED)


def _check_number_bounds(value: Decimal, grammar: ModeloEditValueGrammarV1) -> None:
    _check_number_minimum(value, grammar.minimum_value())
    _check_number_maximum(value, grammar.maximum_value())


def _check_number_minimum(value: Decimal, minimum: Decimal | None) -> None:
    if minimum is not None and value < minimum:
        raise ModeloEditParseRefusedError(ModeloEditParseReason.BELOW_MINIMUM, canonical_decimal_string(minimum))


def _check_number_maximum(value: Decimal, maximum: Decimal | None) -> None:
    if maximum is not None and value > maximum:
        raise ModeloEditParseRefusedError(ModeloEditParseReason.ABOVE_MAXIMUM, canonical_decimal_string(maximum))


def _check_money_operand(value: Decimal, grammar: ModeloEditValueGrammarV1) -> None:
    if grammar.money_operand_bound and abs(value) > MONEY_OPERAND_MAXIMUM:
        raise ModeloEditParseRefusedError(
            ModeloEditParseReason.OUT_OF_OPERAND_RANGE, canonical_decimal_string(MONEY_OPERAND_MAXIMUM)
        )


__all__ = ["read_edit_number_lexeme", "read_typed_edit_number", "validate_edit_number"]

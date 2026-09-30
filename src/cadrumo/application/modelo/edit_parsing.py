"""The one lexical and typed reader of Modelo edit values, owned by the application.

Every frontend reads what an operator types through :func:`parse_modelo_edit_lexeme`,
and the edit executor re-applies the typed half, :func:`validate_modelo_edit_value`,
to every submitted value. Both read against the address's
:class:`~.edit_value_grammar.ModeloEditValueGrammarV1` and call the same
registry validators the engine calls, so a value that passes here passes the
calculation.

Locale is an entry grammar only. Spanish and Catalan write ``1.234,56``,
Hungarian ``1 234,56`` and English ``1,234.56``; the parsed value is
locale-free. The reader never guesses and never rounds: a token that could be
read two ways (``1.234`` in Spanish), a finer precision than the address takes,
scientific notation, an explicit plus and non-finite values are all refused
with a stable reason. The other convention's decimal mark is read when it
cannot be a grouping (``1234.56`` typed in Spanish), and the reading is
reported so an editor can show it back. A refusal never echoes the lexeme.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from typing import Annotated, Final

from pydantic import Field

from ...core.decimal.grammar import european_thousands_reading_is_ambiguous
from ...core.errors.hierarchy import CadrumoError
from ...core.external_constants import OutputLanguage
from ...core.iban import IBAN_SHAPE_RE, iban_mod_97, normalise_iban
from ...core.identity.documents import IdentityError, SpanishTaxIdFormat
from ...core.identity.tax_id import validate_spanish_tax_id
from ...domain.calculations.registry.errors import RegistryValidationError
from ...domain.calculations.registry.schema_base import CasillaSignConstraint
from ...domain.calculations.registry.schema_scalars import validate_registry_text_scalar
from ...domain.filing.schema import ModeloScalar
from ...domain.identifiers import canonical_decimal_string
from .edit_contract import EditModel
from .edit_models import (
    ModeloEditBaselineV1,
    ModeloEditBindingAddressV1,
    ModeloEditNormalisation,
    ModeloEditParsedValueV1,
    ModeloEditParseReason,
    ModeloEditParseRefusalV1,
    ModeloEditParseResultV1,
    ModeloEditRefusedV1,
    ModeloEditScalarAddressV1,
    ModeloEditValueAddressV1,
    ModeloEditWritableBindingOverrideSurfaceEntryV1,
    ModeloEditWritableScalarSurfaceEntryV1,
)
from .edit_value_grammar import (
    MONEY_OPERAND_MAXIMUM,
    ModeloEditValueChannel,
    ModeloEditValueFamily,
    ModeloEditValueGrammarV1,
)

MAX_EDIT_LEXEME_LENGTH: Final[int] = 512
"""The longest entry the parser reads; an editor stops the filer typing past it."""


class ModeloEditParseRequestV1(EditModel):
    """One typed lexeme for one address, in the locale the operator typed it in.

    The lexeme is transient: it is excluded from every dump and from ``repr``,
    so it can never reach a log, a notice or a persisted record.
    """

    address: ModeloEditValueAddressV1
    entry_locale: OutputLanguage
    lexeme: Annotated[str, Field(max_length=MAX_EDIT_LEXEME_LENGTH, exclude=True, repr=False)]


@dataclass(frozen=True, slots=True)
class _LocaleMarks:
    decimal: str
    groups: frozenset[str]
    booleans: dict[str, bool]


_SPACE_GROUPS: Final = frozenset({" ", chr(0x00A0), chr(0x202F)})
"""A plain, a no-break and a narrow no-break space: the ways a Hungarian number is grouped."""
_ROMANCE_BOOLEANS: Final = {"sí": True, "si": True, "no": False}
_LOCALE_MARKS: Final[dict[OutputLanguage, _LocaleMarks]] = {
    OutputLanguage.ES: _LocaleMarks(
        decimal=",", groups=frozenset({"."}), booleans={"sí": True, "si": True, "no": False}
    ),
    OutputLanguage.CA: _LocaleMarks(
        decimal=",", groups=frozenset({"."}), booleans={"sí": True, "si": True, "no": False}
    ),
    OutputLanguage.HU: _LocaleMarks(decimal=",", groups=_SPACE_GROUPS, booleans={"igen": True, "nem": False}),
    OutputLanguage.EN: _LocaleMarks(decimal=".", groups=frozenset({","}), booleans={"yes": True, "no": False}),
}
_UNIVERSAL_BOOLEANS: Final = {"1": True, "0": False}
_TYPED_BOOLEAN_TOKENS: Final = {"1": True, "0": False, "true": True, "false": False}

_NON_FINITE: Final = frozenset({"nan", "-nan", "inf", "-inf", "infinity", "-infinity", "+inf", "+infinity"})
_SCIENTIFIC_RE: Final = re.compile(r"^-?[\d.,\s]*\d[eE][+-]?\d+$")
_NUMERIC_CHARS_RE: Final = re.compile(r"^-?[\d.,\s]+$")
_CANONICAL_DECIMAL_RE: Final = re.compile(r"^-?\d+(\.\d+)?$")
_GROUPED_INTEGER_RE: Final = re.compile(r"^[1-9]\d{0,2}$")
_NIF_SEPARATORS: Final = str.maketrans("", "", " -.")
_UPPER_CASED_TEXT_TYPES: Final = frozenset({"nif", "nif_iva", "iban", "bic", "country_code"})
_NIF_IDENTITY_REASONS: Final = {
    "errors.identity.document_empty": ModeloEditParseReason.EMPTY,
    "errors.identity.tax_id_invalid_length": ModeloEditParseReason.NIF_LENGTH,
    "errors.identity.tax_id_unrecognised_leader": ModeloEditParseReason.NIF_LEADER,
}


_PARSE_REFUSED_KEY: Final[str] = "errors.refused.refused_modelo_edit_parse"


class ModeloEditParseRefusedError(CadrumoError):
    """One entry the grammar refuses, with its reason and message arguments.

    Raised inside the parser and turned into a typed refusal at its boundary,
    so a caller receives a refusal value, never this error.
    """

    def __init__(self, reason: ModeloEditParseReason, *arguments: str) -> None:
        """Carry the refusal's reason and its message arguments, never the refused text."""
        super().__init__(translated_message=_PARSE_REFUSED_KEY, context={"reason": reason.value})
        self.reason = reason
        self.arguments = arguments


# --- numbers -------------------------------------------------------------------------------------------------


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
    marks: _LocaleMarks,
    normalisations: list[ModeloEditNormalisation],
) -> str:
    """Read a number carrying one kind of separator, once or repeatedly."""
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
        raise ModeloEditParseRefusedError(ModeloEditParseReason.AMBIGUOUS_SEPARATOR)
    normalisations.append(ModeloEditNormalisation.FOREIGN_DECIMAL_MARK_READ)
    return f"{lead}.{tail}"


def _canonical_number(lexeme: str, locale: OutputLanguage, normalisations: list[ModeloEditNormalisation]) -> Decimal:
    """Read one localized number into a decimal, refusing anything two-way readable."""
    text = lexeme.strip()
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
    body = text[1:] if negative else text
    marks = _LOCALE_MARKS[locale]
    spaces = [character for character in body if character in _SPACE_GROUPS]
    if spaces:
        if not marks.groups <= _SPACE_GROUPS:
            raise ModeloEditParseRefusedError(ModeloEditParseReason.BAD_GROUPING)
        integer_part, fraction = _split_on_decimal(body, marks.decimal)
        if "." in integer_part or "," in integer_part:
            raise ModeloEditParseRefusedError(ModeloEditParseReason.BAD_GROUPING)
        normalisations.append(ModeloEditNormalisation.SEPARATORS_REMOVED)
        digits = _valid_groups(integer_part, _SPACE_GROUPS)
        canonical = digits if fraction is None else f"{digits}.{fraction}"
    elif "." in body and "," in body:
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
        canonical = f"{digits}.{fraction}"
    elif "." in body or "," in body:
        canonical = _read_single_mark(body, "." if "." in body else ",", marks, normalisations)
    else:
        canonical = body
    if not _CANONICAL_DECIMAL_RE.fullmatch(canonical):
        raise ModeloEditParseRefusedError(ModeloEditParseReason.NOT_A_NUMBER)
    return _finite(f"-{canonical}" if negative else canonical)


def _finite(canonical: str) -> Decimal:
    try:
        value = Decimal(canonical)
    except InvalidOperation as exc:
        raise ModeloEditParseRefusedError(ModeloEditParseReason.NOT_A_NUMBER) from exc
    if not value.is_finite():
        raise ModeloEditParseRefusedError(ModeloEditParseReason.NON_FINITE)
    return value


def _typed_number(value: ModeloScalar) -> Decimal:
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


def _checked_number(value: Decimal, grammar: ModeloEditValueGrammarV1) -> Decimal:
    """Apply precision, sign, bounds and the money operand range; never round."""
    if grammar.family is ModeloEditValueFamily.INTEGER:
        if value != value.to_integral_value():
            raise ModeloEditParseRefusedError(ModeloEditParseReason.NOT_AN_INTEGER)
        value = Decimal(int(value))
    elif grammar.max_fraction_digits is not None and _fraction_digits(value.normalize()) > grammar.max_fraction_digits:
        raise ModeloEditParseRefusedError(ModeloEditParseReason.TOO_MANY_DECIMALS, str(grammar.max_fraction_digits))
    if grammar.sign == CasillaSignConstraint.NON_NEGATIVE and value < 0:
        raise ModeloEditParseRefusedError(ModeloEditParseReason.NEGATIVE_NOT_ALLOWED)
    if grammar.sign == CasillaSignConstraint.NON_POSITIVE and value > 0:
        raise ModeloEditParseRefusedError(ModeloEditParseReason.POSITIVE_NOT_ALLOWED)
    minimum = grammar.minimum_value()
    if minimum is not None and value < minimum:
        raise ModeloEditParseRefusedError(ModeloEditParseReason.BELOW_MINIMUM, canonical_decimal_string(minimum))
    maximum = grammar.maximum_value()
    if maximum is not None and value > maximum:
        raise ModeloEditParseRefusedError(ModeloEditParseReason.ABOVE_MAXIMUM, canonical_decimal_string(maximum))
    if grammar.money_operand_bound and abs(value) > MONEY_OPERAND_MAXIMUM:
        raise ModeloEditParseRefusedError(
            ModeloEditParseReason.OUT_OF_OPERAND_RANGE, canonical_decimal_string(MONEY_OPERAND_MAXIMUM)
        )
    return value


# --- booleans and text ---------------------------------------------------------------------------------------


def _typed_boolean(value: ModeloScalar) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, Decimal | int):
        token = canonical_decimal_string(Decimal(value))
    elif isinstance(value, str):
        token = value.strip().lower()
    else:
        raise ModeloEditParseRefusedError(ModeloEditParseReason.NOT_A_BOOLEAN)
    if token not in _TYPED_BOOLEAN_TOKENS:
        raise ModeloEditParseRefusedError(ModeloEditParseReason.NOT_A_BOOLEAN)
    return _TYPED_BOOLEAN_TOKENS[token]


def _lexeme_boolean(lexeme: str, locale: OutputLanguage) -> bool:
    token = lexeme.strip().lower()
    if not token:
        raise ModeloEditParseRefusedError(ModeloEditParseReason.EMPTY)
    words = {**_LOCALE_MARKS[locale].booleans, **_UNIVERSAL_BOOLEANS}
    if token not in words:
        raise ModeloEditParseRefusedError(ModeloEditParseReason.NOT_A_BOOLEAN)
    return words[token]


def _chosen_token(text: str, grammar: ModeloEditValueGrammarV1, normalisations: list[ModeloEditNormalisation]) -> str:
    choices = grammar.choices
    if choices is None:
        return text
    tokens = [choice.code for choice in choices]
    if text in tokens:
        return text
    folded = [token for token in tokens if token.casefold() == text.casefold()]
    if len(folded) != 1:
        raise ModeloEditParseRefusedError(ModeloEditParseReason.NOT_IN_CHOICES, str(len(tokens)))
    normalisations.append(ModeloEditNormalisation.CASE_MATCHED)
    return folded[0]


def _checked_nif(text: str, tax_id_format: SpanishTaxIdFormat) -> str:
    try:
        return validate_spanish_tax_id(text, tax_id_format)
    except IdentityError as refused:
        reason = _NIF_IDENTITY_REASONS.get(refused.translated_message or "", ModeloEditParseReason.NIF_CHECKSUM)
        raise ModeloEditParseRefusedError(reason) from refused


def _checked_iban(text: str) -> str:
    canonical = normalise_iban(text)
    if IBAN_SHAPE_RE.fullmatch(canonical) is None:
        raise ModeloEditParseRefusedError(ModeloEditParseReason.IBAN_SHAPE)
    if iban_mod_97(canonical) != 1:
        raise ModeloEditParseRefusedError(ModeloEditParseReason.IBAN_CHECKSUM)
    return canonical


def _checked_text(
    value: ModeloScalar,
    grammar: ModeloEditValueGrammarV1,
    *,
    tax_id_format: SpanishTaxIdFormat | None,
    normalisations: list[ModeloEditNormalisation],
) -> str:
    """Canonicalise text through the registry validator the engine runs, then its declared shape."""
    if not isinstance(value, str):
        raise ModeloEditParseRefusedError(ModeloEditParseReason.NOT_TEXT)
    text = value.strip()
    if text != value:
        normalisations.append(ModeloEditNormalisation.TRIMMED)
    data_type = grammar.data_type
    if not text and data_type != "text":
        raise ModeloEditParseRefusedError(ModeloEditParseReason.EMPTY)
    if data_type in {"nif", "iban"}:
        stripped = text.translate(_NIF_SEPARATORS)
        if stripped != text:
            normalisations.append(ModeloEditNormalisation.SEPARATORS_REMOVED)
    if data_type == "nif":
        if tax_id_format is None:
            raise ModeloEditParseRefusedError(ModeloEditParseReason.CHANNEL_UNAVAILABLE)
        canonical = _checked_nif(text, tax_id_format)
    elif data_type == "iban":
        canonical = _checked_iban(text)
    else:
        canonical = _chosen_token(text, grammar, normalisations)
        if data_type in _UPPER_CASED_TEXT_TYPES:
            canonical = canonical.upper()
        try:
            canonical = validate_registry_text_scalar(data_type, canonical, tax_id_format=tax_id_format)
        except RegistryValidationError as refused:
            raise ModeloEditParseRefusedError(ModeloEditParseReason.INVALID_CODE) from refused
    if data_type in _UPPER_CASED_TEXT_TYPES and any(character.islower() for character in text):
        normalisations.append(ModeloEditNormalisation.UPPER_CASED)
    if grammar.min_length is not None and len(canonical) < grammar.min_length:
        raise ModeloEditParseRefusedError(ModeloEditParseReason.TOO_SHORT, str(grammar.min_length))
    if grammar.max_length is not None and len(canonical) > grammar.max_length:
        raise ModeloEditParseRefusedError(ModeloEditParseReason.TOO_LONG, str(grammar.max_length))
    if grammar.pattern is not None and re.fullmatch(grammar.pattern, canonical) is None:
        raise ModeloEditParseRefusedError(ModeloEditParseReason.PATTERN_MISMATCH)
    return canonical


# --- public API ----------------------------------------------------------------------------------------------


def _outcome(
    address: ModeloEditValueAddressV1,
    value: ModeloScalar,
    normalisations: list[ModeloEditNormalisation],
) -> ModeloEditParsedValueV1:
    return ModeloEditParsedValueV1(
        address=address,
        value=value,
        normalisations=tuple(dict.fromkeys(normalisations)),
    )


def validate_modelo_edit_value(
    value: ModeloScalar,
    *,
    address: ModeloEditValueAddressV1,
    grammar: ModeloEditValueGrammarV1,
    tax_id_format: SpanishTaxIdFormat | None,
) -> ModeloEditParsedValueV1 | ModeloEditParseRefusalV1:
    """Apply the typed half of the grammar to an already-typed value.

    This is what the executor runs on every submitted value: no locale
    grammar, only the machine-canonical forms a typed value or its wire mirror
    can take, then the same precision, sign, bound, choice, registry-validator
    and shape checks the parser applies.
    """
    normalisations: list[ModeloEditNormalisation] = []
    try:
        if grammar.channel is ModeloEditValueChannel.UNAVAILABLE:
            raise ModeloEditParseRefusedError(ModeloEditParseReason.CHANNEL_UNAVAILABLE)
        if grammar.family is ModeloEditValueFamily.BOOLEAN:
            return _outcome(address, _typed_boolean(value), normalisations)
        if grammar.family in {ModeloEditValueFamily.DECIMAL, ModeloEditValueFamily.INTEGER}:
            return _outcome(address, _checked_number(_typed_number(value), grammar), normalisations)
        text = _checked_text(value, grammar, tax_id_format=tax_id_format, normalisations=normalisations)
        return _outcome(address, text, normalisations)
    except ModeloEditParseRefusedError as refused:
        return ModeloEditParseRefusalV1(address=address, reason=refused.reason, message_arguments=refused.arguments)


def modelo_edit_address_grammar(
    baseline: ModeloEditBaselineV1,
    address: ModeloEditValueAddressV1,
) -> ModeloEditValueGrammarV1 | None:
    """Return the grammar the baseline admitted for ``address``, or ``None`` when it is not writable."""
    for entry in baseline.permitted_surface:
        if (
            isinstance(address, ModeloEditScalarAddressV1)
            and isinstance(entry, ModeloEditWritableScalarSurfaceEntryV1)
            and entry.casilla_id == address.casilla_id
        ) or (
            isinstance(address, ModeloEditBindingAddressV1)
            and isinstance(entry, ModeloEditWritableBindingOverrideSurfaceEntryV1)
            and entry.binding_id == address.binding_id
        ):
            return entry.grammar
    return None


def parse_modelo_edit_lexeme(
    request: ModeloEditParseRequestV1,
    *,
    baseline: ModeloEditBaselineV1,
    tax_id_format: SpanishTaxIdFormat | None,
) -> ModeloEditParseResultV1:
    """Read one typed lexeme as its address's locale-free value, or refuse with a stable reason.

    ``tax_id_format`` is the governed Spanish tax-identifier format; ``None``
    refuses NIF addresses rather than validating them against nothing.
    """
    address = request.address
    grammar = modelo_edit_address_grammar(baseline, address)
    if grammar is None:
        return ModeloEditRefusedV1(
            refusal=ModeloEditParseRefusalV1(address=address, reason=ModeloEditParseReason.ADDRESS_NOT_WRITABLE)
        )
    normalisations: list[ModeloEditNormalisation] = []
    try:
        if grammar.channel is ModeloEditValueChannel.UNAVAILABLE:
            raise ModeloEditParseRefusedError(ModeloEditParseReason.CHANNEL_UNAVAILABLE)
        if grammar.family is ModeloEditValueFamily.BOOLEAN:
            return _outcome(address, _lexeme_boolean(request.lexeme, request.entry_locale), normalisations)
        if grammar.family in {ModeloEditValueFamily.DECIMAL, ModeloEditValueFamily.INTEGER}:
            number = _canonical_number(request.lexeme, request.entry_locale, normalisations)
            return _outcome(address, _checked_number(number, grammar), normalisations)
    except ModeloEditParseRefusedError as refused:
        return ModeloEditRefusedV1(
            refusal=ModeloEditParseRefusalV1(
                address=address, reason=refused.reason, message_arguments=refused.arguments
            )
        )
    outcome = validate_modelo_edit_value(request.lexeme, address=address, grammar=grammar, tax_id_format=tax_id_format)
    if isinstance(outcome, ModeloEditParseRefusalV1):
        return ModeloEditRefusedV1(refusal=outcome)
    return outcome


__all__ = [
    "ModeloEditParseRefusedError",
    "ModeloEditParseRequestV1",
    "modelo_edit_address_grammar",
    "parse_modelo_edit_lexeme",
    "validate_modelo_edit_value",
]

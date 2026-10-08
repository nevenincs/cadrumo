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
read two ways, a finer precision than the address takes, scientific notation,
an explicit plus and non-finite values are refused with a stable reason. A
refusal never echoes the lexeme.
"""

from __future__ import annotations

from typing import Annotated, Final

from pydantic import Field

from ...core.external_constants import OutputLanguage
from ...core.identity.documents import SpanishTaxIdFormat
from ...domain.filing.schema import ModeloScalar
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
from .edit_number_parsing import read_edit_number_lexeme, read_typed_edit_number, validate_edit_number
from .edit_parse_errors import ModeloEditParseRefusedError
from .edit_text_parsing import read_edit_boolean_lexeme, read_typed_edit_boolean, validate_edit_text_value
from .edit_value_grammar import ModeloEditValueChannel, ModeloEditValueFamily, ModeloEditValueGrammarV1

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
            return _outcome(address, read_typed_edit_boolean(value), normalisations)
        if grammar.family in {ModeloEditValueFamily.DECIMAL, ModeloEditValueFamily.INTEGER}:
            return _outcome(address, validate_edit_number(read_typed_edit_number(value), grammar), normalisations)
        text = validate_edit_text_value(value, grammar, tax_id_format=tax_id_format, normalisations=normalisations)
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
            return _outcome(address, read_edit_boolean_lexeme(request.lexeme, request.entry_locale), normalisations)
        if grammar.family in {ModeloEditValueFamily.DECIMAL, ModeloEditValueFamily.INTEGER}:
            number = read_edit_number_lexeme(request.lexeme, request.entry_locale, normalisations)
            return _outcome(address, validate_edit_number(number, grammar), normalisations)
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
    "ModeloEditParseRequestV1",
    "modelo_edit_address_grammar",
    "parse_modelo_edit_lexeme",
    "validate_modelo_edit_value",
]

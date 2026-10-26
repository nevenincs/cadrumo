"""Validate boolean, identifier, and registry-defined text edit values."""

from __future__ import annotations

import re
from decimal import Decimal
from typing import Final

from ...core.external_constants import OutputLanguage
from ...core.iban import IBAN_SHAPE_RE, iban_mod_97, normalise_iban
from ...core.identity.documents import IdentityError, SpanishTaxIdFormat
from ...core.identity.tax_id import validate_spanish_tax_id
from ...domain.calculations.registry.errors import RegistryValidationError
from ...domain.calculations.registry.schema_scalars import validate_registry_text_scalar
from ...domain.filing.schema import ModeloScalar
from ...domain.identifiers import canonical_decimal_string
from .edit_locale_input import locale_marks
from .edit_models import ModeloEditNormalisation, ModeloEditParseReason
from .edit_parse_errors import ModeloEditParseRefusedError
from .edit_value_grammar import ModeloEditValueGrammarV1

_UNIVERSAL_BOOLEANS: Final = {"1": True, "0": False}


_TYPED_BOOLEAN_TOKENS: Final = {"1": True, "0": False, "true": True, "false": False}


_NIF_SEPARATORS: Final = str.maketrans("", "", " -.")


_UPPER_CASED_TEXT_TYPES: Final = frozenset({"nif", "nif_iva", "iban", "bic", "country_code"})


_NIF_IDENTITY_REASONS: Final = {
    "errors.identity.document_empty": ModeloEditParseReason.EMPTY,
    "errors.identity.tax_id_invalid_length": ModeloEditParseReason.NIF_LENGTH,
    "errors.identity.tax_id_unrecognised_leader": ModeloEditParseReason.NIF_LEADER,
}


def read_typed_edit_boolean(value: ModeloScalar) -> bool:
    """Read a typed boolean scalar without accepting locale-specific words."""
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


def read_edit_boolean_lexeme(lexeme: str, locale: OutputLanguage) -> bool:
    """Read a source lexeme using the declared locale's boolean vocabulary."""
    token = lexeme.strip().lower()
    if not token:
        raise ModeloEditParseRefusedError(ModeloEditParseReason.EMPTY)
    words = {**locale_marks(locale).booleans, **_UNIVERSAL_BOOLEANS}
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


def validate_edit_text_value(
    value: ModeloScalar,
    grammar: ModeloEditValueGrammarV1,
    *,
    tax_id_format: SpanishTaxIdFormat | None,
    normalisations: list[ModeloEditNormalisation],
) -> str:
    """Canonicalise text through the registry validator the engine runs, then its declared shape."""
    text, data_type = _prepare_text(value, grammar, normalisations)
    canonical = _canonical_text_value(text, data_type, grammar, tax_id_format, normalisations)
    _record_uppercase_normalisation(text, data_type, normalisations)
    _validate_text_shape(canonical, grammar)
    return canonical


def _prepare_text(
    value: ModeloScalar,
    grammar: ModeloEditValueGrammarV1,
    normalisations: list[ModeloEditNormalisation],
) -> tuple[str, str]:
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
    return text, data_type


def _canonical_text_value(
    text: str,
    data_type: str,
    grammar: ModeloEditValueGrammarV1,
    tax_id_format: SpanishTaxIdFormat | None,
    normalisations: list[ModeloEditNormalisation],
) -> str:
    if data_type == "nif":
        if tax_id_format is None:
            raise ModeloEditParseRefusedError(ModeloEditParseReason.CHANNEL_UNAVAILABLE)
        return _checked_nif(text, tax_id_format)
    if data_type == "iban":
        return _checked_iban(text)
    return _canonical_registry_text(text, data_type, grammar, tax_id_format, normalisations)


def _canonical_registry_text(
    text: str,
    data_type: str,
    grammar: ModeloEditValueGrammarV1,
    tax_id_format: SpanishTaxIdFormat | None,
    normalisations: list[ModeloEditNormalisation],
) -> str:
    canonical = _chosen_token(text, grammar, normalisations)
    if data_type in _UPPER_CASED_TEXT_TYPES:
        canonical = canonical.upper()
    try:
        return validate_registry_text_scalar(data_type, canonical, tax_id_format=tax_id_format)
    except RegistryValidationError as refused:
        raise ModeloEditParseRefusedError(ModeloEditParseReason.INVALID_CODE) from refused


def _record_uppercase_normalisation(text: str, data_type: str, normalisations: list[ModeloEditNormalisation]) -> None:
    if data_type in _UPPER_CASED_TEXT_TYPES and any(character.islower() for character in text):
        normalisations.append(ModeloEditNormalisation.UPPER_CASED)


def _validate_text_shape(canonical: str, grammar: ModeloEditValueGrammarV1) -> None:
    if grammar.min_length is not None and len(canonical) < grammar.min_length:
        raise ModeloEditParseRefusedError(ModeloEditParseReason.TOO_SHORT, str(grammar.min_length))
    if grammar.max_length is not None and len(canonical) > grammar.max_length:
        raise ModeloEditParseRefusedError(ModeloEditParseReason.TOO_LONG, str(grammar.max_length))
    if grammar.pattern is not None and re.fullmatch(grammar.pattern, canonical) is None:
        raise ModeloEditParseRefusedError(ModeloEditParseReason.PATTERN_MISMATCH)


__all__ = ["read_edit_boolean_lexeme", "read_typed_edit_boolean", "validate_edit_text_value"]

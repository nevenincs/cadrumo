"""What a staged edit's check says to the filer: each entry read back, each finding and any refusal, in words.

Every frontend shows the same sentences for an edit under review, so they are
said here, once:

* an entry read through its address's grammar is read back as the value it
  will be, written as the box shows its kind of value; an entry that cannot be
  read says why, with its bound in the filer's number format;
* each finding of the check says what it found, a refused value saying how to
  fix it; the findings the review states in its own sentence (an entry that
  replaces a source's value, the filer's earlier entries being unknown) are
  left to the review, and only whether the earlier entries are unknown is
  carried;
* a refusal of the whole check, or of renewing the edit's baseline, says why
  in the registered message of its refusal family.
"""

from __future__ import annotations

from typing import Final

from pydantic import BaseModel, Field

from ...core.errors.error_codes import resolve_error_message
from ...core.external_constants import OutputLanguage
from ...core.i18n.render import tr
from ...core.models import STRICT_FROZEN_CONFIG
from ...domain.filing.schema import ModeloScalar
from .action_errors import modelo_edit_refusal_error
from .edit_models import (
    ModeloEditAddressV1,
    ModeloEditBindingAddressV1,
    ModeloEditFindingSeverity,
    ModeloEditFindingV1,
    ModeloEditParseReason,
    ModeloEditParseRefusalV1,
    ModeloEditRefusalV1,
    ModeloEditScalarAddressV1,
    ModeloEditValueAddressV1,
)
from .edit_parse_text import parse_refusal_text
from .edit_preflight import (
    CLEAR_OF_SOURCE_FED_CASILLA,
    INTENT_NOT_ADMITTED,
    NOTHING_TO_RESTORE,
    OPERATOR_LAYER_UNKNOWN,
    OVERRIDES_SOURCE_VALUE,
    REQUIRED_EMPTY,
    VALUE_REFUSED_PREFIX,
)
from .edit_value_grammar import ModeloEditValueGrammarV1
from .value_presentation import format_casilla_value
from .work_form_field_state import BINDING_DATA_TYPE
from .work_form_models import ModeloFormAddressV1, ModeloFormBindingAddressV1, ModeloFormCasillaAddressV1

WORDED_FINDING_CODES: Final[tuple[str, ...]] = (
    INTENT_NOT_ADMITTED,
    CLEAR_OF_SOURCE_FED_CASILLA,
    REQUIRED_EMPTY,
    NOTHING_TO_RESTORE,
)
"""The check's findings worded by their own catalogue sentence; a refused value says how to fix it instead."""

STATED_BY_THE_REVIEW: Final[frozenset[str]] = frozenset({OPERATOR_LAYER_UNKNOWN, OVERRIDES_SOURCE_VALUE})
"""The check's findings the review says in its own sentence, so the list of findings does not repeat them."""

_FINDING_LOCALE_ROOT: Final[str] = "workspace.modelo.review.finding"
_TEXT: Final[str] = "text"


class ModeloEditReviewFindingV1(BaseModel):
    """One finding of an edit's check as the review lists it, in the language asked for.

    ``address`` is the field the finding concerns, ``None`` when it concerns
    the whole submission; a blocking finding would make applying the changes
    refuse until it is resolved.
    """

    model_config = STRICT_FROZEN_CONFIG

    code: str = Field(min_length=1)
    address: ModeloFormAddressV1 | None
    blocking: bool
    words: str = Field(min_length=1)


def entry_read_back(value: ModeloScalar | None, *, data_type: str, language: OutputLanguage) -> str:
    """The value an entry will be read as, written as its box shows its kind of value; empty for no value."""
    return "" if value is None else format_casilla_value(value, data_type=data_type, language=language)


def grammar_data_type(grammar: ModeloEditValueGrammarV1, address: ModeloEditValueAddressV1) -> str:
    """The data type an entry's value reads as, the one the form gives the field at that address."""
    if isinstance(address, ModeloEditBindingAddressV1):
        return BINDING_DATA_TYPE.get(grammar.data_type, _TEXT)
    return grammar.data_type


def edit_refusal_words(refusal: ModeloEditRefusalV1, language: OutputLanguage) -> str:
    """Why an edit, an entry or a baseline renewal was refused, as one sentence in ``language``."""
    if isinstance(refusal, ModeloEditParseRefusalV1):
        return parse_refusal_text(refusal, language)
    return resolve_error_message(modelo_edit_refusal_error(refusal), locale=language.value)


def _form_address(address: ModeloEditAddressV1 | None) -> ModeloFormAddressV1 | None:
    if isinstance(address, ModeloEditScalarAddressV1):
        return ModeloFormCasillaAddressV1(casilla_id=address.casilla_id)
    if isinstance(address, ModeloEditBindingAddressV1):
        return ModeloFormBindingAddressV1(binding_id=address.binding_id)
    return None


def edit_finding_words(finding: ModeloEditFindingV1, language: OutputLanguage) -> str:
    """One finding of the check in the filer's words; a refused value says how to fix it."""
    target = finding.address
    if finding.code.startswith(VALUE_REFUSED_PREFIX) and isinstance(
        target, ModeloEditScalarAddressV1 | ModeloEditBindingAddressV1
    ):
        refusal = ModeloEditParseRefusalV1(
            address=target,
            reason=ModeloEditParseReason(finding.code.removeprefix(VALUE_REFUSED_PREFIX)),
            message_arguments=finding.message_arguments,
        )
        return parse_refusal_text(refusal, language)
    return tr(f"{_FINDING_LOCALE_ROOT}.{finding.code}", locale=language.value)


def review_findings(
    findings: tuple[ModeloEditFindingV1, ...], language: OutputLanguage
) -> tuple[ModeloEditReviewFindingV1, ...]:
    """The check's findings the review lists, in order, each in ``language``."""
    return tuple(
        ModeloEditReviewFindingV1(
            code=finding.code,
            address=_form_address(finding.address),
            blocking=finding.severity is ModeloEditFindingSeverity.ERROR,
            words=edit_finding_words(finding, language),
        )
        for finding in findings
        if finding.code not in STATED_BY_THE_REVIEW
    )


def operator_entries_unknown(findings: tuple[ModeloEditFindingV1, ...]) -> bool:
    """Whether the check could not read the filer's earlier entries, which the review says in its own sentence."""
    return any(finding.code == OPERATOR_LAYER_UNKNOWN for finding in findings)


__all__ = [
    "STATED_BY_THE_REVIEW",
    "WORDED_FINDING_CODES",
    "ModeloEditReviewFindingV1",
    "edit_finding_words",
    "edit_refusal_words",
    "entry_read_back",
    "grammar_data_type",
    "operator_entries_unknown",
    "review_findings",
]

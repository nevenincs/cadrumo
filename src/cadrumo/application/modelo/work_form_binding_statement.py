"""The statements a Modelo form offers on one carry, and the mark a figure the filer stated carries.

The edit admits two statements on a single carry it reads from an earlier
return: that no amount is pending (``attest_no_amount``), on a carry whose
binding declares a statement of absence, and the figure itself
(``attest_prior_value``), on a carry whose earlier return the application does
not hold. A frontend offers a statement only where the edit admits it and only
with words served here: what the action is, what it states, what it does to
the carry and, for a figure, the earlier return it stands in for. A statement
whose earlier return cannot be named is not offered, since the filer could not
tell what the figure answers for.

A carry holding a figure the filer stated is marked with the earlier return it
stands in for and the words that say where its value comes from, so it never
reads as a figure typed or one read from a stored return.
"""

from __future__ import annotations

from collections.abc import Mapping
from types import MappingProxyType
from typing import Final

from ...core.i18n.render import tr
from ...core.period import Period
from ...domain.calculations.registry.ids import BindingId
from ...domain.modelos.calculation_revision_operator_layer import ValueAttestation
from .edit_models import ModeloEditBindingIntentKind, ModeloEditWritableBindingOverrideSurfaceEntryV1
from .work_form_context import WorkFormContext
from .work_form_field_vocabulary import ModeloFormEarlierFiling
from .work_form_models import (
    ModeloFormBindingAddressV1,
    ModeloFormBindingStatement,
    ModeloFormField,
    ModeloFormStatedPriorValue,
)
from .work_form_prior_value_models import prior_value_family_id
from .work_form_source_groups import earlier_filing_text

_ACTION_LOCALE_KEYS: Final[Mapping[ModeloEditBindingIntentKind, str]] = MappingProxyType(
    {
        ModeloEditBindingIntentKind.ATTEST_NO_AMOUNT: (
            "application.modelo.work_form.binding_statement.attest_no_amount.action"
        ),
        ModeloEditBindingIntentKind.ATTEST_PRIOR_VALUE: (
            "application.modelo.work_form.binding_statement.attest_prior_value.action"
        ),
    }
)
"""The action of each per-carry statement, as a control names it."""

_STATEMENT_LOCALE_KEYS: Final[Mapping[ModeloEditBindingIntentKind, str]] = MappingProxyType(
    {
        ModeloEditBindingIntentKind.ATTEST_NO_AMOUNT: (
            "application.modelo.work_form.binding_statement.attest_no_amount.statement"
        ),
        ModeloEditBindingIntentKind.ATTEST_PRIOR_VALUE: (
            "application.modelo.work_form.binding_statement.attest_prior_value.statement"
        ),
    }
)
"""What each per-carry statement records, and what follows when an earlier return later disagrees."""

_EFFECT_LOCALE_KEYS: Final[Mapping[ModeloEditBindingIntentKind, str]] = MappingProxyType(
    {
        ModeloEditBindingIntentKind.ATTEST_NO_AMOUNT: (
            "application.modelo.work_form.binding_statement.attest_no_amount.effect"
        ),
        ModeloEditBindingIntentKind.ATTEST_PRIOR_VALUE: (
            "application.modelo.work_form.binding_statement.attest_prior_value.effect"
        ),
    }
)
"""What each per-carry statement does to the carry, as a review lists each staged change."""

_STATED_PRIOR_VALUE_ORIGIN_LOCALE_KEY: Final = (
    "application.modelo.work_form.binding_statement.attest_prior_value.origin"
)
"""Where a stated figure's value comes from; it takes ``{source}``, the earlier return it stands in for."""

_STATEMENT_INTENTS: Final[tuple[ModeloEditBindingIntentKind, ...]] = (
    ModeloEditBindingIntentKind.ATTEST_NO_AMOUNT,
    ModeloEditBindingIntentKind.ATTEST_PRIOR_VALUE,
)


def _edit_binding_id(field: ModeloFormField) -> BindingId | None:
    """The binding a change to the field is submitted to, when it is a binding."""
    address = field.edit_address
    return address.binding_id if isinstance(address, ModeloFormBindingAddressV1) else None


def _value_attestation(binding_id: BindingId, context: WorkFormContext) -> ValueAttestation | None:
    revision = context.revision
    layer = None if revision is None else revision.operator_layer
    return None if layer is None else layer.value_attestations.get(binding_id)


def _attested_filings(attestation: ValueAttestation) -> tuple[ModeloFormEarlierFiling, ...]:
    """The earlier returns a stated figure stands in for, first the one the statement names first."""
    sources = (
        (attestation.source_modelo, attestation.source_filing_year, attestation.source_period),
        *((item.source_modelo, item.source_filing_year, item.source_period) for item in attestation.further_sources),
    )
    return tuple(
        ModeloFormEarlierFiling(modelo=modelo, period=Period.from_year_and_code(year, period))
        for modelo, year, period in sources
    )


def _statement(
    intent: ModeloEditBindingIntentKind, binding_id: BindingId, source_words: str | None, locale: str
) -> ModeloFormBindingStatement:
    return ModeloFormBindingStatement(
        intent=intent,
        binding_id=binding_id,
        action_words=tr(_ACTION_LOCALE_KEYS[intent], locale=locale),
        statement_words=tr(_STATEMENT_LOCALE_KEYS[intent], locale=locale),
        effect_words=tr(_EFFECT_LOCALE_KEYS[intent], locale=locale),
        source_words=source_words,
    )


def _offered_statements(
    field: ModeloFormField, binding_id: BindingId, context: WorkFormContext
) -> tuple[ModeloFormBindingStatement, ...]:
    """The statements the edit admits on the field's carry that the filer has not already made."""
    entry = None if context.surface is None else context.surface.get(("binding", binding_id))
    if not isinstance(entry, ModeloEditWritableBindingOverrideSurfaceEntryV1):
        return ()
    locale = context.language.value
    filings = () if field.source is None else field.source.earlier_filings
    statements: list[ModeloFormBindingStatement] = []
    for intent in _STATEMENT_INTENTS:
        if intent not in entry.allowed_intents:
            continue
        if intent is ModeloEditBindingIntentKind.ATTEST_NO_AMOUNT:
            if field.stated_absent is None:
                statements.append(_statement(intent, binding_id, None, locale))
        elif filings and field.stated_prior_value is None:
            statements.append(_statement(intent, binding_id, earlier_filing_text(filings, context.language), locale))
    return tuple(statements)


def with_binding_statements(field: ModeloFormField, context: WorkFormContext) -> ModeloFormField:
    """``field`` with the mark of a figure the filer stated on its carry, and the statements it can still take."""
    binding_id = _edit_binding_id(field)
    if binding_id is None:
        return field
    attestation = _value_attestation(binding_id, context)
    if attestation is not None:
        filings = _attested_filings(attestation)
        source_words = earlier_filing_text(filings, context.language)
        stated = ModeloFormStatedPriorValue(
            source_words=source_words,
            family_id=prior_value_family_id(filings),
            origin_words=tr(_STATED_PRIOR_VALUE_ORIGIN_LOCALE_KEY, source=source_words, locale=context.language.value),
        )
        field = field.model_copy(update={"stated_prior_value": stated})
    statements = _offered_statements(field, binding_id, context)
    if not statements:
        return field
    return field.model_copy(update={"statements": statements})


__all__ = ["with_binding_statements"]

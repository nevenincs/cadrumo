"""The statements a Modelo form offers when an amount carried from an earlier ejercicio holds no value.

A declaration can read amounts still pending from earlier ejercicios out of the
earlier return, such as the negative general bases a Modelo 100 compensates
over the four following years (Ley 35/2006 art. 50.3). With no earlier return
stored, those carries are unknown, never zero, and the filer who has nothing
pending says so here. Only a carry whose binding the registry declares a
statement of absence for takes one; each declared family is one action that
states it for every carry of the family still open, and the edit records each
as a zero the filer stated, apart from a zero typed.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from types import MappingProxyType
from typing import Final, TypeIs

from ...core.errors.hierarchy import InternalInvariantError
from ...core.i18n.render import tr
from ...domain.calculations.registry.binding_absence_attestation import AbsenceAttestationFamily
from ...domain.calculations.registry.ids import BindingId
from .edit_models import (
    ModeloEditBindingIntentKind,
    ModeloEditPermittedSurfaceEntryV1,
    ModeloEditWritableBindingOverrideSurfaceEntryV1,
)
from .trabajo_income_findings import trabajo_recorded
from .work_form_context import WorkFormContext
from .work_form_models import ModeloFormCarryAttestation

_ACTION_LOCALE_KEYS: Final[Mapping[AbsenceAttestationFamily, str]] = MappingProxyType(
    {
        AbsenceAttestationFamily.RENTA_NEGATIVE_GENERAL_BASES_PENDING: (
            "application.modelo.work_form.carry_attestation.renta_negative_general_bases_pending.action"
        ),
        AbsenceAttestationFamily.RENTA_TRABAJO_INCOME_NOT_STATED: (
            "application.modelo.work_form.carry_attestation.renta_trabajo_income_not_stated.action"
        ),
    }
)
_STATEMENT_LOCALE_KEYS: Final[Mapping[AbsenceAttestationFamily, str]] = MappingProxyType(
    {
        AbsenceAttestationFamily.RENTA_NEGATIVE_GENERAL_BASES_PENDING: (
            "application.modelo.work_form.carry_attestation.renta_negative_general_bases_pending.statement"
        ),
        AbsenceAttestationFamily.RENTA_TRABAJO_INCOME_NOT_STATED: (
            "application.modelo.work_form.carry_attestation.renta_trabajo_income_not_stated.statement"
        ),
    }
)
_EFFECT_LOCALE_KEYS: Final[Mapping[AbsenceAttestationFamily, str]] = MappingProxyType(
    {
        AbsenceAttestationFamily.RENTA_NEGATIVE_GENERAL_BASES_PENDING: (
            "application.modelo.work_form.carry_attestation.renta_negative_general_bases_pending.effect"
        ),
        AbsenceAttestationFamily.RENTA_TRABAJO_INCOME_NOT_STATED: (
            "application.modelo.work_form.carry_attestation.renta_trabajo_income_not_stated.effect"
        ),
    }
)

for _family_words in (_ACTION_LOCALE_KEYS, _STATEMENT_LOCALE_KEYS, _EFFECT_LOCALE_KEYS):
    if frozenset(_family_words) != frozenset(AbsenceAttestationFamily):
        raise InternalInvariantError("every statement family the registry can declare needs its words")


def _attestable_open(
    entry: ModeloEditPermittedSurfaceEntryV1, held: frozenset[BindingId], entered: frozenset[BindingId]
) -> TypeIs[ModeloEditWritableBindingOverrideSurfaceEntryV1]:
    """Whether the entry is a binding the filer may state absent and that holds no value yet."""
    return (
        isinstance(entry, ModeloEditWritableBindingOverrideSurfaceEntryV1)
        and ModeloEditBindingIntentKind.ATTEST_NO_AMOUNT in entry.allowed_intents
        and entry.binding_id not in held
        and entry.binding_id not in entered
    )


def _open_carries_by_family(
    context: WorkFormContext, entries: Iterable[ModeloEditPermittedSurfaceEntryV1]
) -> dict[AbsenceAttestationFamily, list[BindingId]]:
    """The carries that hold no value, grouped by the family whose statement can absent them."""
    revision = context.revision
    held = frozenset(()) if revision is None else frozenset(revision.binding_overrides)
    entered = context.overridden or frozenset(())
    open_by_family: dict[AbsenceAttestationFamily, list[BindingId]] = {}
    for entry in entries:
        if not _attestable_open(entry, held, entered):
            continue
        binding = context.bindings.get(entry.binding_id)
        if binding is not None and binding.absence_attestation is not None:
            open_by_family.setdefault(binding.absence_attestation, []).append(entry.binding_id)
    if revision is None or not trabajo_recorded(revision):
        # No payer record of work income, so the employer's contributions are not in question.
        open_by_family.pop(AbsenceAttestationFamily.RENTA_TRABAJO_INCOME_NOT_STATED, None)
    return open_by_family


def form_carry_attestations(context: WorkFormContext) -> tuple[ModeloFormCarryAttestation, ...]:
    """One statement per declared family with a carry that holds no value; none on a form that admits no edit.

    A carry holds a value when the current calculation resolved one for it from
    any source, a stored earlier return included, or the filer entered or
    stated one.
    """
    if context.surface is None:
        return ()
    open_by_family = _open_carries_by_family(context, context.surface.values())
    locale = context.language.value
    return tuple(
        ModeloFormCarryAttestation(
            family=family,
            binding_ids=tuple(sorted(open_by_family[family])),
            action_words=tr(_ACTION_LOCALE_KEYS[family], locale=locale),
            statement_words=tr(_STATEMENT_LOCALE_KEYS[family], locale=locale),
            effect_words=tr(_EFFECT_LOCALE_KEYS[family], locale=locale),
        )
        for family in AbsenceAttestationFamily
        if family in open_by_family
    )


__all__ = ["form_carry_attestations"]

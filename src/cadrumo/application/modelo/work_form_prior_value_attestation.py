"""The figures a Modelo form offers the filer to state for earlier returns the application does not hold.

The registry declares which carries read their value from earlier returns
through a previous-filing binding or a relation; a figure the filer states can
stand in for those returns (``attest_prior_value``). The form serves one entry
per such carry its edit takes, in served words: the statement while the edit
admits it, and otherwise why not and the way out: an earlier return the
application holds decides the carry, so a statement over it is refused. The
carries that stand in for the same earlier returns form one family, and the
filer withdraws the figures stated for it together. A form whose edit was not
admitted, a declaration recorded as filed included, offers none of this.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Final

from ...core.i18n.render import tr
from ...core.operator_action_enums import ActionEvidenceProvenance
from ...domain.calculations.registry.ids import BindingId
from ..calculations.cross_period_clean_state import declared_attestable_carry_requirements
from ..calculations.cross_period_models import CrossPeriodDependencyRequirement
from ..operator_actions.projection import PreconditionVerdictSnapshot
from .edit_models import ModeloEditBindingIntentKind, ModeloEditWritableBindingOverrideSurfaceEntryV1
from .preconditions import build_modelo_precondition_failure_for_scenario
from .work_form_context import WorkFormContext
from .work_form_field_vocabulary import ModeloFormBindingAddressV1, ModeloFormEarlierFiling
from .work_form_prior_value_models import (
    ModeloFormPriorValueAttestation,
    ModeloFormPriorValueRefusal,
    ModeloFormPriorValueWithdrawal,
    prior_value_family_id,
)
from .work_form_source_groups import earlier_filing_text

_WITHDRAWAL_ACTION: Final = "application.modelo.work_form.prior_value_attestation.withdrawal.action"
_WITHDRAWAL_EFFECT: Final = "application.modelo.work_form.prior_value_attestation.withdrawal.effect"
_SOURCE_HELD_WORDS: Final = "application.modelo.work_form.prior_value_attestation.refusal.source_held"


def _earlier_filings(requirements: Sequence[CrossPeriodDependencyRequirement]) -> tuple[ModeloFormEarlierFiling, ...]:
    return tuple(ModeloFormEarlierFiling(modelo=item.source_modelo, period=item.period) for item in requirements)


def _source_held_refusal(context: WorkFormContext) -> PreconditionVerdictSnapshot:
    """The way out of a statement over an earlier return the application holds: open that return."""
    failure = build_modelo_precondition_failure_for_scenario(
        subject_leaf_key="modelo.work.set_value",
        scenario_id="modelo.work.edit.prior_value.source_held",
        evidence_id="modelo.work.edit.prior_value",
        evidence_values={"admitted": False},
        provenance=ActionEvidenceProvenance.APPLICATION_STATE,
    )
    return PreconditionVerdictSnapshot.from_verdict(failure.verdict, context.language)


def _stated_binding_ids(context: WorkFormContext) -> frozenset[BindingId]:
    revision = context.revision
    layer = None if revision is None else revision.operator_layer
    return frozenset(() if layer is None else layer.value_attestations)


def _taken_bindings(
    declared: Mapping[BindingId, tuple[CrossPeriodDependencyRequirement, ...]], context: WorkFormContext
) -> dict[BindingId, ModeloEditWritableBindingOverrideSurfaceEntryV1]:
    """The declared carries the form's edit takes, each with its edit surface entry, in registry order."""
    surface = context.surface
    if surface is None:
        return {}
    taken: dict[BindingId, ModeloEditWritableBindingOverrideSurfaceEntryV1] = {}
    for binding_id in declared:
        entry = surface.get(("binding", binding_id))
        if isinstance(entry, ModeloEditWritableBindingOverrideSurfaceEntryV1):
            taken[binding_id] = entry
    return taken


def _withdrawals(
    families: Mapping[BindingId, str], stated: frozenset[BindingId], context: WorkFormContext
) -> dict[str, ModeloFormPriorValueWithdrawal]:
    """One withdrawal per family holding a stated figure."""
    by_family: dict[str, list[BindingId]] = {}
    for binding_id, family_id in families.items():
        if binding_id in stated:
            by_family.setdefault(family_id, []).append(binding_id)
    locale = context.language.value
    return {
        family_id: ModeloFormPriorValueWithdrawal(
            family_id=family_id,
            binding_ids=tuple(sorted(binding_ids)),
            action_words=tr(_WITHDRAWAL_ACTION, locale=locale),
            effect_words=tr(_WITHDRAWAL_EFFECT, locale=locale),
        )
        for family_id, binding_ids in by_family.items()
    }


def _attestation(
    entry: ModeloEditWritableBindingOverrideSurfaceEntryV1,
    filings: tuple[ModeloFormEarlierFiling, ...],
    *,
    stated: bool,
    withdrawal: ModeloFormPriorValueWithdrawal | None,
    context: WorkFormContext,
) -> ModeloFormPriorValueAttestation:
    locale = context.language.value
    admitted = ModeloEditBindingIntentKind.ATTEST_PRIOR_VALUE in entry.allowed_intents
    return ModeloFormPriorValueAttestation(
        binding_id=entry.binding_id,
        edit_address=ModeloFormBindingAddressV1(binding_id=entry.binding_id),
        family_id=prior_value_family_id(filings),
        earlier_filings=filings,
        source_words=earlier_filing_text(filings, context.language),
        action_words=tr("application.modelo.work_form.binding_statement.attest_prior_value.action", locale=locale),
        statement_words=tr(
            "application.modelo.work_form.binding_statement.attest_prior_value.statement", locale=locale
        ),
        effect_words=tr("application.modelo.work_form.binding_statement.attest_prior_value.effect", locale=locale),
        stated=stated,
        admitted=admitted,
        refusal_reason=None if admitted else ModeloFormPriorValueRefusal.SOURCE_HELD,
        refusal_words=None if admitted else tr(_SOURCE_HELD_WORDS, locale=locale),
        refusal=None if admitted else _source_held_refusal(context),
        withdrawal=withdrawal,
    )


def form_prior_value_attestations(context: WorkFormContext) -> tuple[ModeloFormPriorValueAttestation, ...]:
    """One entry per carry the registry lets the filer state a figure for and the form's edit takes, in registry order.

    None on a form whose edit was not admitted.
    """
    declared = declared_attestable_carry_requirements(context.snapshot)
    taken = _taken_bindings(declared, context)
    stated = _stated_binding_ids(context)
    filings = {binding_id: _earlier_filings(declared[binding_id]) for binding_id in taken}
    families = {binding_id: prior_value_family_id(items) for binding_id, items in filings.items()}
    withdrawals = _withdrawals(families, stated, context)
    return tuple(
        _attestation(
            entry,
            filings[binding_id],
            stated=binding_id in stated,
            withdrawal=withdrawals.get(families[binding_id]),
            context=context,
        )
        for binding_id, entry in taken.items()
    )


__all__ = ["form_prior_value_attestations"]

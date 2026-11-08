"""Whether a modelo-scoped profile requirement's declared conditions hold.

``required_for_modelos`` on its own demands a fact of every taxpayer filing the
named modelo. Some facts only concern part of them: Modelo 111's colegio
concertado header is about the payroll of a concertado teaching centre, so a
consultant with no employees has nothing to attest. The schema field names the
conditions that decide the requirement, and this module reads them through the
registry machinery that already owns each one: the dated payer-fact catalogue
for what the declarant does, and the IAE activity-group facts for how the
declared activities are classified.

Three states, and the difference between the last two is the whole point.
:attr:`ModeloScopedRequirementState.REQUIRED` means every condition holds and
the fact is owed. :attr:`ModeloScopedRequirementState.DEFERRED` means a
condition is unanswered, so what is owed is the condition's own fact -- asking
for the gated attestation first is how an operator was shown a prerequisite
that could not apply to them. :attr:`ModeloScopedRequirementState.DERIVED_ABSENT`
means a condition is positively absent, so the fact is not owed and follows
deterministically as a no.

Every resolver read here takes its vocabulary from the active governed-fact
scope, so callers enter :func:`completeness.pinned_registry_scope` first and one
generation answers the whole judgement.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from enum import StrEnum
from typing import TYPE_CHECKING

from ...domain.calculations.registry.applicability_payer_facts import (
    PayerFactDeclaration,
    payer_fact_declaration,
    payer_fact_profile_keys,
    resolve_payer_fact,
)
from ...domain.calculations.registry.iae_activity_groups import (
    ActivityGroupMembership,
    activity_group_membership,
)

if TYPE_CHECKING:
    from ...domain.deadlines.models import TaxpayerProfile
    from ...domain.user_profile.schema import ProfileFieldDefinition, ProfileSchemaDefinition

__all__ = [
    "ModeloScopedRequirement",
    "ModeloScopedRequirementState",
    "field_declaring_selector",
    "field_is_conditionally_modelo_scoped",
    "modelo_scoped_requirement",
]


class ModeloScopedRequirementState(StrEnum):
    """What a conditionally modelo-scoped field's declared conditions say now."""

    REQUIRED = "required"
    """Every condition holds, so the taxpayer owes this fact for this modelo."""
    DEFERRED = "deferred"
    """A condition is unanswered; its own facts are owed before this one is."""
    DERIVED_ABSENT = "derived_absent"
    """A condition is positively absent, so the fact is a deterministic no."""


@dataclass(frozen=True, slots=True)
class ModeloScopedRequirement:
    """One field's conditional requirement, with the facts a deferral owes instead."""

    state: ModeloScopedRequirementState
    deferred_paths: tuple[str, ...] = ()


def field_is_conditionally_modelo_scoped(field: ProfileFieldDefinition) -> bool:
    """Report whether ``field`` gates its modelo-scoped requirement on any condition."""
    return bool(field.required_for_modelos_when_payer_facts) or (
        field.required_for_modelos_when_activity_iae_groups_fact is not None
    )


def modelo_scoped_requirement(
    field: ProfileFieldDefinition,
    *,
    profile: TaxpayerProfile,
    schema: ProfileSchemaDefinition,
    effective_date: date,
) -> ModeloScopedRequirement:
    """Judge ``field``'s declared conditions against ``profile`` on ``effective_date``.

    Every condition is read before the verdict: a positively absent condition
    settles the requirement even when another is unanswered, because an absence
    means the fact cannot be owed whatever the open question answers.

    Args:
        field: The schema field carrying the conditions.
        profile: Projected :class:`domain.deadlines.models.TaxpayerProfile` the
            conditions read their answers from.
        schema: Loaded schema, used to address each unanswered condition's own
            field by the selector the schema already declares for it.
        effective_date: Date the dated payer-fact catalogue and IAE group facts
            are selected on, which is the target filing period's end.

    Returns:
        The :class:`ModeloScopedRequirement` for this field and profile.
    """
    unanswered: list[str] = []
    absent = False
    for token in field.required_for_modelos_when_payer_facts:
        fact = resolve_payer_fact(token, effective_date=effective_date)
        declaration = payer_fact_declaration(profile, fact)
        if declaration is PayerFactDeclaration.DECLARED_NO:
            absent = True
        elif declaration is not PayerFactDeclaration.DECLARED_YES:
            unanswered.extend(
                path for key in payer_fact_profile_keys(fact) for path in _schema_paths_for_selector(schema, key)
            )
    groups_fact = field.required_for_modelos_when_activity_iae_groups_fact
    epigraph_path = field.required_for_modelos_when_activity_iae_epigraph_path
    if groups_fact is not None and epigraph_path is not None:
        membership = activity_group_membership(
            profile.activity_iae_epigraphs,
            fact_id=groups_fact,
            effective_date=effective_date,
        )
        if membership is ActivityGroupMembership.DECLARED_ABSENT:
            absent = True
        elif membership is ActivityGroupMembership.UNKNOWN:
            unanswered.append(epigraph_path)
    if absent:
        return ModeloScopedRequirement(ModeloScopedRequirementState.DERIVED_ABSENT)
    if unanswered:
        return ModeloScopedRequirement(
            ModeloScopedRequirementState.DEFERRED,
            tuple(dict.fromkeys(unanswered)),
        )
    return ModeloScopedRequirement(ModeloScopedRequirementState.REQUIRED)


def field_declaring_selector(schema: ProfileSchemaDefinition, selector: str) -> ProfileFieldDefinition | None:
    """Return the one schema field declaring ``selector``, or ``None`` where none does.

    A consumer holding a taxpayer-projection attribute reaches that attribute's
    schema field, and its conditions, through the selector the schema already
    declares for it. ``None`` where the loaded schema declares no such field:
    an authority generation that does not carry the field cannot be asked about
    its conditions, and inventing one would answer for a rule it never stated.
    """
    for section in schema.sections:
        for field in section.fields:
            if selector in field.model_selectors:
                return field
    return None


def _schema_paths_for_selector(schema: ProfileSchemaDefinition, selector: str) -> tuple[str, ...]:
    """Return the ``section.field`` paths whose schema field declares ``selector``.

    A payer fact names the taxpayer-projection attribute it reads, and the
    schema field that answers it declares the same token in its
    ``model_selectors``. Reading the correspondence from the schema keeps the
    deferral's address out of Python: a field that moves section takes its
    selector with it. A selector no field declares addresses nothing, and
    contributes no row rather than inventing one.
    """
    return tuple(
        f"{section.key}.{field.key}"
        for section in schema.sections
        for field in section.fields
        if selector in field.model_selectors
    )

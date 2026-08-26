"""Modelo lifecycle guard for required calculation bindings.

The gate compares required binding declarations on a registry
:class:`ModeloRevision` with the binding ids resolved for a work-unit action.
Persisted replay checks derive those ids from a saved
:class:`CalculationRevision`.

This gate is deliberately M202-only and hard-blocking, with no exclusion for
``previous_filing`` / ``relation_prefill`` / ``manual_input`` sources — it is
NOT a stricter reimplementation of the generic, all-modelos, non-blocking
silent-zero advisory in
:func:`~cadrumo.application.modelo._calculation_source_staging.expected_but_missing_binding_ids`,
which explicitly excludes those three source kinds. The two gates answer
different questions for different reasons: this one refuses M202 lifecycle
actions outright when a declared binding has no resolved value at
all (Ley 27/2014 art. 40.2/40.3 modalidad-cuota requires every input present
before a pago fraccionado can be computed), while the generic advisory flags a
narrower "present source produced no value" silent-zero shape across every
modelo without blocking. Collapsing either gate into the other would either
silence M202's hard stop or over-block every other modelo's advisory path —
this is a constraint-shape mismatch, not duplication, and the divergence is
intentional. Do not "fix" it by aligning the two.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from datetime import date
from decimal import Decimal

from ...core import ActionEvidenceProvenance, Modelo
from ...core.resources import bundled_path
from ...domain.calculations.registry.ids import BindingId
from ...domain.calculations.registry.loader import load_registry_tree
from ...domain.calculations.registry.schema import ModeloRevision
from ...domain.calculations.registry.temporal import select_revision
from ...domain.modelos import CalculationRevision, WorkUnit
from ...domain.user_profile.errors import ProfileNotFoundError
from ...domain.user_profile.loader import load_user_profile_schema
from ..user_profile.profile_record_repository import ProfileRecordRepository
from ._action_errors import ModeloRequiredBindingsMissingError
from ._preconditions import build_modelo_precondition_failure
from .profile_binding import profile_fact_index, resolve_profile_binding_value


def require_modelo_required_bindings_resolved(
    *,
    work_unit: WorkUnit,
    registry_revision: ModeloRevision,
    resolved_binding_ids: Iterable[BindingId],
    action: str,
) -> None:
    """Refuse M202 lifecycle work when declared bindings are absent.

    Args:
        work_unit: Modelo work unit whose action is being gated.
        registry_revision: Registry :class:`ModeloRevision` declaring the
            required bindings for the target modelo/year/period.
        resolved_binding_ids: Binding ids already supplied by the caller or
            source resolvers.
        action: Operator action name used in the refusal message.
    """
    missing = missing_modelo_required_binding_ids(
        work_unit=work_unit,
        registry_revision=registry_revision,
        resolved_binding_ids=resolved_binding_ids,
    )
    if not missing:
        return
    _raise_required_bindings_missing(work_unit=work_unit, missing_bindings=missing, action=action)


def require_persisted_revision_required_bindings_resolved(
    *,
    work_unit: WorkUnit,
    revision: CalculationRevision,
    action: str,
) -> None:
    """Refuse saved M202 revisions whose replay payload lacks required bindings.

    Args:
        work_unit: Modelo work unit whose persisted replay is being gated.
        revision: Saved :class:`CalculationRevision` carrying binding overrides
            from the previous calculation payload.
        action: Operator action name used in the refusal message.
    """
    if str(work_unit.modelo) != Modelo.M202.value:
        return
    modelos, _catalogues = load_registry_tree(bundled_path("registry", "aeat"))
    modelo_definition = next(candidate for candidate in modelos if candidate.id == str(work_unit.modelo))
    registry_revision = select_revision(
        modelo_definition,
        filing_year=work_unit.filing_year,
        period=work_unit.period.registry_token,
    )
    require_modelo_required_bindings_resolved(
        work_unit=work_unit,
        registry_revision=registry_revision,
        resolved_binding_ids=_persisted_binding_ids(revision.binding_overrides),
        action=action,
    )


def missing_modelo_required_binding_ids(
    *,
    work_unit: WorkUnit,
    registry_revision: ModeloRevision,
    resolved_binding_ids: Iterable[BindingId],
) -> tuple[BindingId, ...]:
    """Return required M202 binding ids absent from a resolved channel set.

    Args:
        work_unit: Modelo work unit whose target determines whether the M202
            required-binding gate applies.
        registry_revision: Registry :class:`ModeloRevision` whose binding
            declarations are inspected.
        resolved_binding_ids: Binding ids available from caller inputs or
            resolved source data.
    """
    if str(work_unit.modelo) != Modelo.M202.value:
        return ()
    resolved = frozenset(str(binding_id) for binding_id in resolved_binding_ids)
    return tuple(
        sorted(binding.id for binding in registry_revision.bindings if str(binding.id) not in resolved),
    )


def resolved_required_profile_binding_values(
    *,
    work_unit: WorkUnit,
    registry_revision: ModeloRevision,
) -> dict[BindingId, Decimal]:
    """Return M202 required profile bindings even when they are not formula-consumed.

    Args:
        work_unit: Modelo work unit whose target determines whether the M202
            required-binding profile lift applies.
        registry_revision: Registry :class:`ModeloRevision` whose required
            profile-sourced binding declarations are inspected.
    """
    if str(work_unit.modelo) != Modelo.M202.value:
        return {}
    try:
        record = ProfileRecordRepository.for_current_session(work_unit.bucket_id).load(work_unit.bucket_id)
    except ProfileNotFoundError:
        return {}
    facts = profile_fact_index(record, load_user_profile_schema())
    resolved: dict[BindingId, Decimal] = {}
    for binding in registry_revision.bindings:
        if _binding_source_value(binding.source) != "profile":
            continue
        value = resolve_profile_binding_value(binding, facts)
        if value is None or isinstance(value, date):
            continue
        if isinstance(value, bool):
            resolved[binding.id] = Decimal("1") if value else Decimal("0")
        elif isinstance(value, Decimal):
            resolved[binding.id] = value
        elif isinstance(value, int):
            resolved[binding.id] = Decimal(value)
    return dict(sorted(resolved.items()))


def _persisted_binding_ids(binding_overrides: Mapping[BindingId, str]) -> tuple[BindingId, ...]:
    return tuple(sorted(binding_overrides))


def _binding_source_value(source: object) -> str:
    value = getattr(source, "value", source)
    return str(value)


def _raise_required_bindings_missing(
    *,
    work_unit: WorkUnit,
    missing_bindings: tuple[BindingId, ...],
    action: str,
) -> None:
    period = work_unit.period.registry_token
    subject_leaf_key = {
        "calculate": "modelo.work.calculate",
        "verify": "modelo.work.verify",
        "file": "modelo.work.file",
    }.get(action)
    context = {
        "modelo": str(work_unit.modelo),
        "filing_year": work_unit.filing_year,
        "period": period,
        "missing_binding_count": len(missing_bindings),
        "missing_bindings": missing_bindings,
    }
    if subject_leaf_key is None:
        raise ModeloRequiredBindingsMissingError(context=context)
    raise ModeloRequiredBindingsMissingError(
        context=context,
        precondition_failure=build_modelo_precondition_failure(
            subject_leaf_key=subject_leaf_key,
            condition_id="modelo.work.required_bindings.resolved",
            scenario_id=f"{subject_leaf_key}.required_bindings_missing",
            evidence_id="modelo.work.required_bindings",
            evidence_values={
                "work_unit_id": work_unit.work_unit_id,
                "modelo": str(work_unit.modelo),
                "year": work_unit.filing_year,
                "period": period,
                "missing_binding_count": len(missing_bindings),
                "missing_binding_ids": "|".join(str(binding_id) for binding_id in missing_bindings),
            },
            provenance=ActionEvidenceProvenance.REGISTRY_RECORD,
            action_id="operator.modelo.bindings.list",
            action_argument_values={
                "modelo": str(work_unit.modelo),
                "year": work_unit.filing_year,
                "period": period,
            },
        ),
    )

"""Modelo lifecycle guard for required calculation bindings.

The gate compares required binding declarations on a registry
:class:`ModeloRevision` with the binding ids resolved for a work-unit action.
Persisted replay checks derive those ids from a saved
:class:`CalculationRevision`.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from datetime import date
from decimal import Decimal

from ...core import Modelo
from ...core.resources import resources
from ...domain.calculations.registry import BindingId, ModeloRevision
from ...domain.modelos._calculation_revision import CalculationRevision
from ...domain.modelos._work_unit import WorkUnit
from ...domain.user_profile import ProfileNotFoundError, load_user_profile_schema
from ..user_profile import UserProfileLifecycleRepository
from ._action_errors import ModeloRequiredBindingsMissingError
from ._profile_binding import profile_fact_index, resolve_profile_binding_value

_CONSTANT_VALUE_SOURCE = "constant_value"


def require_modelo_required_bindings_resolved(
    *,
    work_unit: WorkUnit,
    registry_revision: ModeloRevision,
    resolved_binding_ids: Iterable[BindingId],
    action: str,
) -> None:
    """Refuse M202 lifecycle work when declared non-constant bindings are absent.

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
    snapshot = resources().modelos.authority.snapshot(
        str(work_unit.modelo),
        filing_year=work_unit.filing_year,
        period=work_unit.period.registry_token,
    )
    require_modelo_required_bindings_resolved(
        work_unit=work_unit,
        registry_revision=snapshot.revision,
        resolved_binding_ids=_persisted_binding_ids(revision.binding_overrides),
        action=action,
    )


def missing_modelo_required_binding_ids(
    *,
    work_unit: WorkUnit,
    registry_revision: ModeloRevision,
    resolved_binding_ids: Iterable[BindingId],
) -> tuple[BindingId, ...]:
    """Return required non-constant M202 binding ids absent from a resolved channel set.

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
        sorted(
            binding.id
            for binding in registry_revision.bindings
            if _binding_source_value(binding.source) != _CONSTANT_VALUE_SOURCE and str(binding.id) not in resolved
        ),
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
        record = UserProfileLifecycleRepository(bucket_id=work_unit.bucket_id).load(work_unit.bucket_id)
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
    command = (
        f"aeat app modelo bindings list --modelo {work_unit.modelo} "
        f"--year {work_unit.filing_year} --period {period} --missing"
    )
    joined = ", ".join(missing_bindings)
    raise ModeloRequiredBindingsMissingError(
        f"Modelo {work_unit.modelo} {work_unit.filing_year} {period} cannot {action} because required "
        f"calculation bindings are missing: {joined}. Run `{command}`, then supply the missing source data "
        "or explicit binding values before calculating.",
        context={
            "modelo": str(work_unit.modelo),
            "filing_year": work_unit.filing_year,
            "period": period,
            "missing_binding_count": len(missing_bindings),
            "missing_bindings": missing_bindings,
        },
        suggestion=command,
    )

"""Filed-state comparison: local registry calculation versus captured AEAT state.

Reads captured filed observations through the active-bucket encrypted
observation store, recomputes a registry snapshot locally, and reports the
per-casilla comparison. This is one of three local registry read surfaces
(the others are corpus/manual projection in
:mod:`application.registry.corpus` and structural tree inspection in
:mod:`application.registry.tree`); unlike tree inspection, this surface's
input is a captured observation file, not just a registry root, and its
concern is reconciling that observation against a local recalculation, not
inventorying the registry tree's own shape.
"""

from __future__ import annotations

from collections.abc import Mapping
from decimal import Decimal
from pathlib import Path

from pydantic import BaseModel

from ...core.aggregation import BindingSourceKind as _BindingSourceKind
from ...core.casilla_id import CasillaId as _CasillaId
from ...core.casilla_id import validated_casilla_id as _validated_casilla_id
from ...core.models import STRICT_FROZEN_CONFIG
from ...core.operator_action_enums import ActionEvidenceProvenance, NoRecoveryOutcome
from ...core.resources import bundled_path as _bundled_path
from ...domain.calculations.registry.authority import ValidatedRegistryAuthority as _ValidatedRegistryAuthority
from ...domain.calculations.registry.bindings import RegistryModeloObservation as _RegistryModeloObservation
from ...domain.calculations.registry.bindings_previous_filing import (
    resolve_previous_filing_binding_values as _resolve_previous_filing_binding_values,
)
from ...domain.calculations.registry.casilla_membership import undeclared_casilla_ids as _undeclared_casilla_ids
from ...domain.calculations.registry.filed_state import RegistryFiledStateComparison as _RegistryFiledStateComparison
from ...domain.calculations.registry.filed_state import (
    compare_calculation_to_filed_observation as _compare_calculation_to_filed_observation,
)
from ...domain.calculations.registry.formula_runtime import calculate_registry_snapshot as _calculate_registry_snapshot
from ...domain.calculations.registry.ids import BindingId as _BindingId
from ...domain.calculations.registry.relations import (
    resolve_relation_values_from_observations as _resolve_relation_values_from_observations,
)
from ...domain.calculations.registry.schema import DataBindingDefinition as _DataBindingDefinition
from ...domain.calculations.registry.schema import RegistrySnapshot as _RegistrySnapshot
from ...domain.calculations.registry.schema_input_kind import InputKind as _InputKind
from ...domain.calculations.registry.schema_surfaces import CasillaDefinition as _CasillaDefinition
from ...domain.calculations.registry.verification_tolerance import (
    verification_tolerance_or_exact as _verification_tolerance_or_exact,
)
from ...domain.period import calculation_filing_date as _calculation_filing_date
from .errors import RegistryPreconditionCondition, registry_terminal_refusal


class FiledStateVerificationReport(BaseModel):
    """Local registry calculation versus filed AEAT state verification report."""

    model_config = STRICT_FROZEN_CONFIG

    observation_path: str
    source_observation_paths: tuple[str, ...]
    comparison: _RegistryFiledStateComparison


def _verified_required_casilla_ids(
    required_casilla_refs: tuple[object, ...],
    *,
    snapshot: _RegistrySnapshot,
) -> tuple[_CasillaId, ...]:
    """Validate requested filed-state casillas against the resolved revision."""
    requested: list[_CasillaId] = []
    for raw_casilla_id in required_casilla_refs:
        try:
            casilla_id = _validated_casilla_id(
                raw_casilla_id,
                surface="registry.verify_filed_state --casilla",
            )
        except ValueError as exc:
            raise registry_terminal_refusal(
                condition=RegistryPreconditionCondition.FILED_STATE_CASILLA_ID_CANONICAL,
                context={
                    "modelo": snapshot.modelo.id,
                    "revision_id": snapshot.revision.id,
                    "casilla_id": str(raw_casilla_id),
                },
                facts={
                    "modelo": str(snapshot.modelo.id),
                    "revision_id": str(snapshot.revision.id),
                    "casilla_id_canonical": False,
                },
                provenance=ActionEvidenceProvenance.RUNTIME_OBSERVATION,
                outcome=NoRecoveryOutcome.OPERATOR_DECISION,
            ) from exc
        if _undeclared_casilla_ids(snapshot.revision, (casilla_id,)):
            raise registry_terminal_refusal(
                condition=RegistryPreconditionCondition.FILED_STATE_CASILLA_DECLARED,
                context={
                    "modelo": snapshot.modelo.id,
                    "revision_id": snapshot.revision.id,
                    "casilla_id": casilla_id,
                },
                facts={
                    "modelo": str(snapshot.modelo.id),
                    "revision_id": str(snapshot.revision.id),
                    "casilla_id_declared": False,
                },
                provenance=ActionEvidenceProvenance.RUNTIME_OBSERVATION,
                outcome=NoRecoveryOutcome.OPERATOR_DECISION,
            )
        requested.append(casilla_id)
    return tuple(requested)


def verify_filed_state(
    *,
    observation_path: Path,
    source_observation_paths: tuple[Path, ...] = (),
    registry_root: Path | None = None,
    source_root: Path | None = None,
    required_casilla_ids: tuple[_CasillaId, ...] = (),
) -> FiledStateVerificationReport:
    """Compare a local registry calculation to a captured filed observation.

    Returns a :class:`FiledStateVerificationReport` with the per-casilla
    comparison results between the registry calculation and the filed values.
    """
    # The sede adapter is reached only by this comparison and the loader below.
    # At module scope it put an application-to-adapter edge on every consumer of
    # this package, and because CommandSpec annotations resolve through here it
    # dragged the auth session store -- and the whole persistence family -- into
    # merely RESOLVING unrelated registry commands.
    from ...adapters.outbound.aeat.sede.declarations_observations import registry_observation_from_filed_declaration

    filed_observation = _load_filed_observation(observation_path)
    registry_observation = registry_observation_from_filed_declaration(filed_observation)
    source_observations = tuple(_load_filed_observation(path) for path in source_observation_paths)
    registry_source_observations = tuple(
        registry_observation_from_filed_declaration(observation) for observation in source_observations
    )
    authority = _ValidatedRegistryAuthority.load(
        registry_root or _bundled_path("registry", "aeat"),
        source_root=source_root or _bundled_path(),
    )
    filing_period_token = filed_observation.period.registry_token
    snapshot = authority.snapshot(
        filed_observation.modelo,
        filing_year=filed_observation.ejercicio,
        period=filing_period_token,
    )
    requested_required_casilla_ids = _verified_required_casilla_ids(required_casilla_ids, snapshot=snapshot)
    binding_values = _resolve_previous_filing_binding_values(
        snapshot.revision,
        registry_source_observations,
        filing_year=filed_observation.ejercicio,
        period=filing_period_token,
    )
    inputs = _filed_state_inputs(
        snapshot,
        registry_observation,
        binding_values=binding_values,
    )
    relation_values = _resolve_relation_values_from_observations(
        snapshot.revision,
        registry_source_observations,
        filing_year=filed_observation.ejercicio,
        period=filing_period_token,
    )
    calculation = _calculate_registry_snapshot(
        snapshot,
        inputs=inputs,
        date_context={"filing_period": _calculation_filing_date(filed_observation.period)},
        binding_values=binding_values,
        relation_values=relation_values,
        # Recomputation reconciles a filed observation's own values, carrying no
    )
    casilla_ids = requested_required_casilla_ids or tuple(
        casilla.id for casilla in snapshot.revision.casillas if casilla.input_kind == _InputKind.COMPUTED
    )
    comparison = _compare_calculation_to_filed_observation(
        calculation,
        registry_observation,
        required_casilla_ids=casilla_ids,
        tolerance=_verification_tolerance_or_exact(snapshot),
    )
    return FiledStateVerificationReport(
        observation_path=str(observation_path),
        source_observation_paths=tuple(str(path) for path in source_observation_paths),
        comparison=comparison,
    )


def _filed_state_inputs(
    snapshot: _RegistrySnapshot,
    registry_observation: _RegistryModeloObservation,
    *,
    binding_values: Mapping[_BindingId, Decimal],
) -> dict[_CasillaId, Decimal]:
    bindings_by_id = {binding.id: binding for binding in snapshot.revision.bindings}
    input_casilla_ids = {
        casilla.id
        for casilla in snapshot.revision.casillas
        if _filed_state_casilla_is_input(casilla, bindings_by_id=bindings_by_id, binding_values=binding_values)
    }
    return {
        casilla_id: value
        for casilla_id, value in registry_observation.casilla_values.items()
        if casilla_id in input_casilla_ids
    }


def _filed_state_casilla_is_input(
    casilla: _CasillaDefinition,
    *,
    bindings_by_id: Mapping[_BindingId, _DataBindingDefinition],
    binding_values: Mapping[_BindingId, Decimal],
) -> bool:
    if casilla.input_kind == _InputKind.COMPUTED:
        return False
    if casilla.input_kind != _InputKind.BOUND or casilla.binding is None:
        return True
    binding_def = bindings_by_id.get(casilla.binding)
    return not (
        binding_def is not None
        and binding_def.source == _BindingSourceKind.PREVIOUS_FILING
        and binding_def.id not in binding_values
    )


def _load_filed_observation(path: Path):
    from ...adapters.outbound.aeat.sede.observation_store import FiledDeclaracionObservationStore

    return FiledDeclaracionObservationStore(path.parent).load_observation(path)


__all__ = [
    "FiledStateVerificationReport",
    "verify_filed_state",
]

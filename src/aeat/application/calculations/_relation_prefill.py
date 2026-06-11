"""Relation prefill: resolve registry relations from prior filings.

Sits between the engine and the local observation store. The engine
asks "what's the resolved value of every relation this revision
declares?" and this module answers by consulting a :class:`RegistrySnapshot`
to enumerate the declared relations:

1. Reading the revision's relations to determine `(source_modelo,
   source_revision_selector, source_periods, source_output,
   aggregation.op)`.
2. Scanning the local `CalculationObservationRepository` for prior
   filings matching the source quadruple.
3. Folding the source filings' casilla values through the declared
   aggregation op (`sum`, `copy`).
4. Returning a `RelationValues` record stamped with provenance the
   apply adapter writes onto the workbook so the pull adapter can
   detect stale prefills.

When no prior filings exist for a relation, the resolver returns a
`RelationValue` with `value=None` and `provenance="operator_manual"`
so the engine emits a blank cell the operator must fill by hand.

This is the local-tier prefill. The AEAT-live tier (parsing
justificantes from Sede) lives in a separate adapter that produces
the same `RelationValues` shape; callers route between tiers based
on the operator's preferences and the local store's coverage.
"""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Final

from ...adapters.persistence.storage.errors import ClassificationError, DecryptionError, EnvelopeVersionError
from ...application.storage.calc_sheets._records import RelationValue, RelationValues
from ...core import Period
from ...core.logging import get_logger
from ...core.time import now
from ...domain.calculations.registry import (
    RegistryModeloObservation,
    RegistryRelationSourceRequirement,
    RegistrySnapshot,
    RegistryValidationError,
    materialize_relation_binding_values,
    relation_source_requirements,
)
from ..aggregation._source_mesh import (
    CalculationSourceContext,
    CalculationSourceDiagnostic,
    CalculationSourceProvenance,
    CalculationSourceResolution,
    storage_degradation_resolution,
)
from ._observations_repository import CalculationObservationRepository

_LOCAL_FILING_PROVENANCE: Final = "local_filing"
_STORAGE_DEGRADATION_ERRORS = (ClassificationError, DecryptionError, EnvelopeVersionError)
_log = get_logger(__name__)


def _gather_observations_for_snapshot(
    snapshot: RegistrySnapshot,
    *,
    repository: CalculationObservationRepository,
) -> tuple[RegistryModeloObservation, ...]:
    """Collect every observation a relation in `snapshot.revision` could need.

    Uses the registry relation requirement resolver to compute the set of
    `(source_modelo, filing_year, period)` requirements, and pulls matching observations
    from the local store. Returns the union (deduplicated) so the
    runtime resolver can fold them through the declared aggregation
    in one pass.
    """
    needed: dict[tuple[str, int, str], RegistryModeloObservation] = {}
    requirements = relation_source_requirements(
        snapshot.revision,
        filing_year=snapshot.filing_year,
        period=snapshot.period,
    )
    for requirement in requirements:
        for period in requirement.periods:
            payload = repository.load_observation(
                requirement.source_modelo,
                Period.from_year_and_code(requirement.filing_year, period),
            )
            if payload is None:
                continue
            obs = payload.observation
            key = (obs.modelo, obs.filing_year, obs.period)
            needed.setdefault(key, obs)
    return tuple(needed.values())


def _provenance_note(
    relation_id: str,
    source_modelo: str,
    source_periods: tuple[str, ...],
    source_year: int,
    resolved_at: datetime,
) -> str:
    period_text = "+".join(source_periods) if source_periods else "(any)"
    when = resolved_at.isoformat()
    return (
        f"prefilled from operator's local filing of modelo {source_modelo} "
        f"{period_text} {source_year} (resolved {when})"
    )


def resolve_relations_from_local_store(
    snapshot: RegistrySnapshot,
    *,
    repository: CalculationObservationRepository | None = None,
    captured_at: datetime | None = None,
) -> RelationValues:
    """Build a :class:`RelationValues` record from the local observation store.

    Args:
        snapshot: The :class:`RegistrySnapshot` whose declared relations are resolved
            from prior observation records in the local store.
        repository: Optional observation repository. Defaults to the active
            profile's calculation observation repository.
        captured_at: Optional timestamp for relation provenance. Defaults to
            the current clock.

    Returns a :class:`RelationValues` whose ``values`` tuple has one
    ``RelationValue`` per relation declared in the snapshot's
    revision, with provenance stamped per entry. Relations the
    local store cannot resolve get ``value=None`` and
    ``provenance="operator_manual"`` so the engine emits a blank cell
    the operator can fill by hand.
    """
    repo = repository if repository is not None else CalculationObservationRepository()
    when = captured_at if captured_at is not None else now()
    observations = _gather_observations_for_snapshot(snapshot, repository=repo)
    requirements_by_relation = {
        relation_id: requirement
        for requirement in relation_source_requirements(
            snapshot.revision,
            filing_year=snapshot.filing_year,
            period=snapshot.period,
        )
        for relation_id in requirement.relation_ids
    }

    resolved_map = _resolve_available_relation_values(observations, requirements_by_relation=requirements_by_relation)

    values: list[RelationValue] = []
    for relation in snapshot.revision.relations:
        requirement = requirements_by_relation.get(relation.id)
        target_year = (
            requirement.filing_year
            if requirement is not None
            else snapshot.filing_year
            + int(
                relation.source_revision_selector.get("filing_year_delta", 0)
                if relation.source_revision_selector
                else 0,
            )
        )
        source_periods = requirement.periods if requirement is not None else tuple(relation.source_periods)
        resolved = resolved_map.get(relation.id)
        if resolved is None:
            values.append(RelationValue(relation=relation.id, value=None))
            continue
        values.append(
            RelationValue(
                relation=relation.id,
                value=Decimal(resolved),
                provenance=_LOCAL_FILING_PROVENANCE,
                source_filing_year=target_year,
                source_periods=source_periods,
                resolved_at=when,
                note=_provenance_note(
                    relation.id,
                    relation.source_modelo,
                    source_periods,
                    target_year,
                    when,
                ),
            ),
        )
    return RelationValues(values=tuple(values))


def _resolve_available_relation_values(
    observations: tuple[RegistryModeloObservation, ...],
    *,
    requirements_by_relation: dict[str, RegistryRelationSourceRequirement],
) -> dict[str, Decimal]:
    """Resolve each relation requirement independently from available observations."""
    by_requirement = {requirement: requirement for requirement in requirements_by_relation.values()}
    resolved: dict[str, Decimal] = {}
    for requirement in by_requirement:
        try:
            value = _resolve_requirement_value(requirement, observations)
        except RegistryValidationError as exc:
            _log.warning(
                "relation prefill: relation requirement %s remains operator-manual: %s",
                requirement.relation_ids,
                exc,
            )
            continue
        for relation_id in requirement.relation_ids:
            resolved[relation_id] = value
    return resolved


def _resolve_requirement_value(
    requirement: RegistryRelationSourceRequirement,
    observations: tuple[RegistryModeloObservation, ...],
) -> Decimal:
    values = tuple(_observed_requirement_values(requirement, observations))
    if requirement.aggregation_op == "copy":
        if len(values) != 1:
            raise RegistryValidationError(
                f"relation requirement {requirement.relation_ids!r} copy aggregation requires one observation",
            )
        return values[0]
    if requirement.aggregation_op == "sum":
        return sum(values, Decimal("0"))
    raise RegistryValidationError(
        f"relation requirement {requirement.relation_ids!r} uses unsupported aggregation op "
        f"{requirement.aggregation_op!r}",
    )


def _observed_requirement_values(
    requirement: RegistryRelationSourceRequirement,
    observations: tuple[RegistryModeloObservation, ...],
) -> tuple[Decimal, ...]:
    values: list[Decimal] = []
    for source_period in requirement.periods:
        matches = tuple(
            observation
            for observation in observations
            if observation.modelo == requirement.source_modelo
            and observation.filing_year == requirement.filing_year
            and observation.period == source_period
        )
        if len(matches) != 1:
            raise RegistryValidationError(
                f"expected one observed filing {requirement.source_modelo!r}/"
                f"{requirement.filing_year}/{source_period!r}, found {len(matches)}",
            )
        value = matches[0].casilla_values.get(requirement.source_output)
        if value is None:
            raise RegistryValidationError(
                f"requires observed output {requirement.source_output!r} from "
                f"{requirement.source_modelo!r}/{requirement.filing_year}/{source_period!r}",
            )
        values.append(value)
    return tuple(values)


def _formula_relation_ids(snapshot: RegistrySnapshot) -> frozenset[str]:
    relation_ids: set[str] = set()
    for formula in snapshot.revision.formulas:
        _collect_expression_relation_ids(formula.expression, relation_ids)
    return frozenset(relation_ids)


def _collect_expression_relation_ids(expression: object, relation_ids: set[str]) -> None:
    relation_id = getattr(expression, "relation", None)
    if relation_id is not None:
        relation_ids.add(str(relation_id))
    for arg in getattr(expression, "args", ()):
        _collect_expression_relation_ids(arg, relation_ids)


def _unresolved_relation_diagnostics(
    *,
    unresolved_relation_ids: frozenset[str],
    requirements_by_relation: dict[str, RegistryRelationSourceRequirement],
    resolver_id: str,
) -> tuple[CalculationSourceDiagnostic, ...]:
    diagnostics: list[CalculationSourceDiagnostic] = []
    for relation_id in sorted(unresolved_relation_ids):
        requirement = requirements_by_relation.get(relation_id)
        if requirement is None:
            diagnostics.append(
                CalculationSourceDiagnostic(
                    reason="source_issue",
                    source_kind="relation_prefill",
                    resolver_id=resolver_id,
                    relation_id=relation_id,
                    message=f"relation {relation_id!r} has no resolved source filing",
                ),
            )
            continue
        period_text = ",".join(requirement.periods)
        binding_id = requirement.target_bindings[0] if len(requirement.target_bindings) == 1 else None
        diagnostics.append(
            CalculationSourceDiagnostic(
                reason="source_issue",
                source_kind="relation_prefill",
                resolver_id=resolver_id,
                binding_id=binding_id,
                relation_id=relation_id,
                message=(
                    f"relation {relation_id!r} requires modelo {requirement.source_modelo} "
                    f"{requirement.filing_year} periods {period_text} output {requirement.source_output}; "
                    "the source filing is missing or incomplete"
                ),
            ),
        )
    return tuple(diagnostics)


class RelationPrefillSourceResolver:
    """Source mesh adapter for local relation prefill values."""

    resolver_id = "relation_prefill"
    owned_sources = ("relation_prefill",)

    def __init__(
        self,
        *,
        repository: CalculationObservationRepository | None = None,
        registry_snapshot: RegistrySnapshot | None = None,
        captured_at: datetime | None = None,
    ) -> None:
        self._repository = repository
        self._registry_snapshot = registry_snapshot
        self._captured_at = captured_at

    def resolve(self, context: CalculationSourceContext) -> CalculationSourceResolution:
        snapshot = self._registry_snapshot
        if snapshot is None:
            from ...core.resources import resources

            snapshot = resources().modelos.authority.snapshot(
                context.modelo,
                filing_year=context.filing_year,
                period=context.period.registry_token,
            )
        try:
            relation_values = resolve_relations_from_local_store(
                snapshot,
                repository=self._repository,
                captured_at=self._captured_at or context.calculated_at,
            )
        except _STORAGE_DEGRADATION_ERRORS as exc:
            return storage_degradation_resolution(
                resolver_id=self.resolver_id,
                owned_sources=self.owned_sources,
                source_kinds=self.owned_sources,
                error=exc,
            )
        requirements_by_relation = {
            relation_id: requirement
            for requirement in relation_source_requirements(
                snapshot.revision,
                filing_year=snapshot.filing_year,
                period=snapshot.period,
            )
            for relation_id in requirement.relation_ids
        }
        resolved = tuple(item for item in relation_values.values if item.value is not None)
        formula_relation_ids = _formula_relation_ids(snapshot)
        unresolved_relation_ids = frozenset(
            item.relation
            for item in relation_values.values
            if item.value is None and item.relation in formula_relation_ids
        )
        resolved_relation_values = {item.relation: item.value for item in resolved if item.value is not None}
        # Materialise the resolved relation values into their declared
        # ``target_binding`` slots HERE, inside the resolver, so the merged
        # resolution carries them in ``binding_values`` and the mesh
        # ``_claim_binding`` exclusive-ownership guard adjudicates any collision
        # with another resolver loudly (aggregation-taxonomy ADR ruling 4). This
        # replaces the silent post-mesh merge that previously let every other
        # source override a relation-materialised value without a finding.
        binding_values = materialize_relation_binding_values(
            snapshot.revision,
            resolved_relation_values,
            period=context.period.registry_token,
        )
        return CalculationSourceResolution(
            resolver_id=self.resolver_id,
            owned_sources=self.owned_sources,
            relation_values=resolved_relation_values,
            unresolved_relation_ids=tuple(sorted(unresolved_relation_ids)),
            binding_values=binding_values,
            diagnostics=_unresolved_relation_diagnostics(
                unresolved_relation_ids=unresolved_relation_ids,
                requirements_by_relation=requirements_by_relation,
                resolver_id=self.resolver_id,
            ),
            provenance=tuple(
                CalculationSourceProvenance(
                    source_kind="relation_prefill",
                    source_ref=(f"{item.relation}:{item.source_filing_year}:{','.join(item.source_periods)}"),
                )
                for item in resolved
            ),
        )


__all__ = ["RelationPrefillSourceResolver", "resolve_relations_from_local_store"]

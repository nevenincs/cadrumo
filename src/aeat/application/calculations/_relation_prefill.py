"""Relation prefill: resolve registry relations from prior filings.

Sits between the engine and the local observation store. The engine
asks "what's the resolved value of every relation this revision
declares?" and this module answers by:

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

from datetime import UTC, datetime
from decimal import Decimal
from typing import Final

from ...application.storage.calc_sheets._records import RelationValue, RelationValues
from ...core.logging import get_logger
from ...domain.calculations.registry._bindings import RegistryFilingObservation
from ...domain.calculations.registry._errors import RegistryValidationError
from ...domain.calculations.registry._relations import (
    relation_source_requirements,
    resolve_relation_values_from_observations,
)
from ...domain.calculations.registry._schema import RegistrySnapshot
from ._observations_repository import CalculationObservationRepository

_LOCAL_FILING_PROVENANCE: Final = "local_filing"
_log = get_logger(__name__)


def _gather_observations_for_snapshot(
    snapshot: RegistrySnapshot,
    *,
    repository: CalculationObservationRepository,
) -> tuple[RegistryFilingObservation, ...]:
    """Collect every observation a relation in `snapshot.revision` could need.

    Uses the registry relation requirement resolver to compute the set of
    `(source_modelo, filing_year, period)` requirements, and pulls matching observations
    from the local store. Returns the union (deduplicated) so the
    runtime resolver can fold them through the declared aggregation
    in one pass.
    """

    needed: dict[tuple[str, int, str], RegistryFilingObservation] = {}
    requirements = relation_source_requirements(
        snapshot.revision,
        filing_year=snapshot.filing_year,
        period=snapshot.period,
    )
    for requirement in requirements:
        required_periods = set(requirement.periods)
        for payload in repository.iter_modelo(requirement.source_modelo):
            obs = payload.observation
            if obs.filing_year != requirement.filing_year:
                continue
            if obs.period not in required_periods:
                continue
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
    """Build a `RelationValues` record from the local observation store.

    Returns a `RelationValues` whose `values` tuple has one
    `RelationValue` per relation declared in the snapshot's
    revision, with provenance stamped per entry. Relations the
    local store cannot resolve get `value=None` and
    `provenance="operator_manual"` so the engine emits a blank cell
    the operator can fill by hand.
    """

    repo = repository if repository is not None else CalculationObservationRepository()
    when = captured_at if captured_at is not None else datetime.now(UTC)
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

    if observations:
        try:
            resolved_map = resolve_relation_values_from_observations(
                snapshot.revision,
                observations,
                filing_year=snapshot.filing_year,
                period=snapshot.period,
            )
        except RegistryValidationError as exc:
            # The runtime resolver raises ``RegistryValidationError``
            # when a relation requires observations the local store
            # does not yet hold. Downgrade with a logged warning so
            # the engine emits blank cells the operator fills by
            # hand, but the operator-substrate log records the
            # specific resolver complaint rather than silently
            # falling back to ``operator_manual`` provenance.
            _log.warning(
                "relation prefill: resolver refused observations for "
                "modelo=%s filing_year=%s period=%s; "
                "engine will emit blank relation cells: %s",
                snapshot.modelo.id,
                snapshot.filing_year,
                snapshot.period,
                exc,
            )
            resolved_map = {}
    else:
        resolved_map = {}

    values: list[RelationValue] = []
    for relation in snapshot.revision.relations:
        requirement = requirements_by_relation.get(relation.id)
        target_year = requirement.filing_year if requirement is not None else snapshot.filing_year + int(
            relation.source_revision_selector.get("filing_year_delta", 0) if relation.source_revision_selector else 0
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
            )
        )
    return RelationValues(values=tuple(values))


__all__ = ["resolve_relations_from_local_store"]

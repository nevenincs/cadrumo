"""Registry-wide closure of the filed-observation cross-checks a credit reconciliation declares.

A filed-observation cross-check reads one casilla of another modelo's return, so
it can only be checked against the whole tree: the source modelo must exist,
some revision of it must declare the period, and the casilla must record
withholding the declarant suffered.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping

from cadrumo.domain.calculations.registry.credit_reconciliation import FiledObservationCrossCheck
from cadrumo.domain.calculations.registry.credit_reconciliation_checks import filed_observation_source_failures
from cadrumo.domain.calculations.registry.schema import ModeloDefinition


def credit_filed_observation_source_failures(
    modelos: Iterable[ModeloDefinition],
    modelos_by_id: Mapping[str, ModeloDefinition],
) -> list[str]:
    """Return every refusal earned by a credit reconciliation's filed-observation cross-checks."""
    failures: list[str] = []
    for modelo in modelos:
        for revision in modelo.revisions.values():
            for entry in revision.credit_reconciliation:
                owner = (
                    f"modelo {modelo.id} revision {revision.id}: credit reconciliation of casilla {entry.casilla_id!r}"
                )
                for cross_check in entry.cross_checks:
                    if isinstance(cross_check, FiledObservationCrossCheck):
                        failures.extend(_cross_check_failures(cross_check, modelos_by_id, owner=owner))
    return failures


def _cross_check_failures(
    cross_check: FiledObservationCrossCheck,
    modelos_by_id: Mapping[str, ModeloDefinition],
    *,
    owner: str,
) -> tuple[str, ...]:
    source = modelos_by_id.get(cross_check.modelo)
    if source is None:
        return (f"{owner}: filed-observation cross-check names unknown modelo {cross_check.modelo!r}",)
    in_period = tuple(
        revision
        for revision in source.revisions.values()
        if cross_check.period in revision.period_selector.declared_periods
    )
    if not in_period:
        return (f"{owner}: no revision of modelo {cross_check.modelo} declares period {cross_check.period!r}",)
    return filed_observation_source_failures(cross_check, in_period, owner=owner)

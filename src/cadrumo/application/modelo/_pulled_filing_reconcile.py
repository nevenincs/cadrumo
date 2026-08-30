"""Reconcile a local calculation against this taxpayer's own pulled AEAT filing.

The filed-history sweep persists, per pullable modelo, the per-casilla values
AEAT holds for a filing the taxpayer already made. The local calculation for the
same modelo and period persists its own casilla values. Both sides live in the
same encrypted bucket, and nothing compared them: a taxpayer whose local figures
disagree with what AEAT records them as having filed learned it from neither
surface.

WHAT THIS IS NOT. It is not the engine-drift check. That already ships: the
filed-state verification path re-runs the registry calculation using the FILED
declaration's own input casillas and compares the computed outputs, which asks
whether this engine reproduces AEAT's arithmetic from AEAT's inputs. It never
consults the taxpayer's own calculation, so it cannot answer whether the
taxpayer's working disagrees with their filing. That second question is this
module's, and the two must not be collapsed.

WHY IT IS SCOPED RATHER THAN TOTAL. A freshly onboarded profile computes zero
nearly everywhere, so comparing every pulled figure against it would raise a
mismatch on essentially every reconciled casilla — the alert fatigue that trains
an operator to ignore a channel. The comparison is therefore restricted to the
casillas the local revision supplied independent evidence for, resolved by
:func:`~application.modelo.resolve_casilla_population_scope`. An untouched bucket
produces no findings at all, which is the intended behaviour and not a failure
to detect.

GROUNDING IS CARRIED, NEVER MINTED. A divergence finding makes no independent
legal claim: it says the value the registry grounds at these references does not
match what was filed. So each finding carries the diverging casilla's own
``legal_refs`` and ``source_refs`` rather than references invented for the
finding. The registry schema types both as minimum-length-one tuples on every
casilla definition, so there is always something to carry and no substitution
path exists.

THE AGREEMENT THRESHOLD IS THE REGISTRY'S, NOT THIS MODULE'S. How close two
values must be to count as agreeing is a regulatory question versioned by filing
year and revision: the registry publishes a tolerance per verification
expectation and folds the strictest across them. Some revisions publish one cent;
others publish ``0.00`` and so demand exact equality. This module therefore reads
``verification_policy().tolerance`` from the law-resolved snapshot rather than
carrying a constant of its own — a hardcoded cent would silently absorb a
one-cent divergence on every revision of the second kind, which is an
under-declaration this channel exists to surface.

See Also:
    :func:`~application.modelo.detect_casilla_divergences`
        The pure comparison this delegates to.
    :func:`~application.modelo.resolve_casilla_population_scope`
        Supplies the casilla scope that keeps an empty bucket silent.
    :class:`~CalculationRevision`
        The local side of the comparison.
    :class:`ModeloRevision`
        Law-resolved from the work unit's own triple, never from a stored
        revision id. Supplies the formula graph the population scope walks and
        the casilla definitions each finding carries its grounding from, so a
        divergence cites the same references the registry grounds the value at.
    :class:`RegistrySnapshot`
        Carries that revision together with the verification policy the
        comparison tolerance is published on.
"""

from __future__ import annotations

from decimal import Decimal
from typing import TYPE_CHECKING

from ...domain.calculations.registry.verification_tolerance import verification_tolerance_or_exact
from ...domain.modelos.verification_report import ModeloVerificationFinding, ModeloVerificationFindingKind, ModeloVerificationFindingSeverity
from ._reconcile_casilla import detect_casilla_divergences
from ._reconcile_population import resolve_casilla_population_scope

if TYPE_CHECKING:
    from ...core import CasillaId
    from ...domain.calculations.registry.schema import RegistrySnapshot
    from ...domain.calculations.registry.schema_surfaces import CasillaDefinition
    from ...domain.modelos.work_unit import WorkUnit
    from ...domain.modelos.calculation_revision import CalculationRevision
    from ..calculations import CalculationObservationRepository


def _pulled_filed_values(
    *,
    work_unit: WorkUnit,
    repository: CalculationObservationRepository | None,
) -> dict[CasillaId, Decimal] | None:
    """Return the pulled filing's casilla values for this work unit, or ``None``.

    ``None`` covers both "no sweep has run" and "this modelo and period were
    never pulled"; neither is an error and neither should produce a finding.
    """
    from ..calculations import CalculationObservationRepository as _Repository

    repo = repository if repository is not None else _Repository()
    stored = repo.load_observation(str(work_unit.modelo), work_unit.period)
    if stored is None:
        return None
    return dict(stored.observation.casilla_values)


def _law_resolved_snapshot(work_unit: WorkUnit) -> RegistrySnapshot | None:
    """Resolve this work unit's registry snapshot from its own triple, or ``None``.

    Resolution is law-determined from modelo, filing year and period, never from
    a stored revision id. A failure here means the registry publishes no revision
    for the triple, which is a legitimate state for an unpublished filing year;
    an advisory reconcile must not turn it into a verification error.

    The whole snapshot is kept rather than only its revision because the
    comparison tolerance is published on the snapshot's verification policy, not
    on the revision.
    """
    from ...core.errors import CadrumoError
    from ._calculation_helpers import resolve_registry_snapshot_for_work_unit

    try:
        return resolve_registry_snapshot_for_work_unit(work_unit)
    except (LookupError, KeyError, AttributeError, ValueError, CadrumoError):
        return None


def pulled_filing_divergence_findings(
    *,
    work_unit: WorkUnit,
    target: CalculationRevision,
    observation_repository: CalculationObservationRepository | None = None,
) -> list[ModeloVerificationFinding]:
    """Compare the local calculation against this taxpayer's pulled filing.

    Args:
        work_unit: The work unit being verified. Supplies the modelo and period
            the pulled observation is looked up by, and the triple the registry
            revision is law-resolved from.
        target: The :class:`~CalculationRevision` under
            verification, supplying the local side and the supplied-input
            evidence the scope is resolved from.
        observation_repository: Injection point for the pulled-observation
            store. Production passes nothing.

    Returns:
        One non-blocking WARNING finding per diverging casilla, empty when no
        filing was pulled, when no revision resolves, when the local calculation
        supplied no independent evidence, or when every compared casilla agrees
        within tolerance.
    """
    filed_values = _pulled_filed_values(work_unit=work_unit, repository=observation_repository)
    if not filed_values:
        return []

    snapshot = _law_resolved_snapshot(work_unit)
    if snapshot is None:
        return []
    registry_revision = snapshot.revision

    scope = resolve_casilla_population_scope(registry_revision=registry_revision, calculation=target)
    if scope.is_empty:
        return []

    divergences = detect_casilla_divergences(
        computed=target.casilla_values,
        filed=filed_values,
        scope=scope.divergence_scope,
        tolerance=verification_tolerance_or_exact(snapshot),
    )
    if not divergences:
        return []

    casillas_by_id: dict[CasillaId, CasillaDefinition] = {casilla.id: casilla for casilla in registry_revision.casillas}
    findings: list[ModeloVerificationFinding] = []
    for divergence in divergences:
        casilla = casillas_by_id.get(divergence.casilla_id)
        if casilla is None:
            continue
        findings.append(
            ModeloVerificationFinding(
                kind=ModeloVerificationFindingKind.RECONCILIATION_MISMATCH,
                severity=ModeloVerificationFindingSeverity.WARNING,
                # The subject rides a field, never a locale-rendered message.
                casilla_id=divergence.casilla_id,
                message_locale_key="application.modelo.findings.pulled_filing_casilla_mismatch",
                message_facts={
                    "casilla_number": casilla.number,
                    "period_code": work_unit.period.registry_token,
                    "filing_year": work_unit.filing_year,
                    "computed_value": divergence.computed_value if divergence.computed_value is not None else "absent",
                    "filed_value": divergence.filed_value if divergence.filed_value is not None else "absent",
                    "mismatch_kind": divergence.kind.value,
                },
                legal_refs=casilla.legal_refs,
                source_refs=casilla.source_refs,
            ),
        )
    return findings


__all__ = ["pulled_filing_divergence_findings"]

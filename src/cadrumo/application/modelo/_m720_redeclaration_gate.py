"""Verify-time Modelo 720 foreign-asset re-declaration gate.

RD 1065/2007 arts. 42-bis.5 / 42-ter.5 / 54-bis.7 re-impose the declaration
obligation on an already-declared foreign-asset bloque once its year-end
valuation grows more than the re-declaration delta over the last declared
baseline. A taxpayer who holds the position but omits it from the current
Modelo 720 under-declares silently: the omitted row simply is not there, so no
formula, total, or export gate can notice its absence.

This module converts that omission into an operator-visible, non-blocking
advisory at verify time. It compares three independent projections of the same
filing year:

- the prior-year declared baseline, carried through the revision's
  ``previous_filing`` bindings (already revision-stamp re-confirmed by the
  shared carry gate);
- the current per-asset-row valuation evidence, from the foreign-asset source
  mesh rows persisted on the revision;
- the operator's current declaration, from the manual casilla inputs.

The declaration and the evidence come from genuinely different channels. Were
both read from one source the omitted-position test could never be satisfied
and the advisory would be permanently silent.

See Also:
    :func:`~cadrumo.application.calculations.modelo_720_redeclaration_advisory_findings`
        Threshold and finding authority this gate feeds.
    :func:`~cadrumo.application.calculations.resolve_bindings_from_local_store`
        Previous-filing carry that supplies the prior-year baseline.
    :func:`~cadrumo.application.modelo.verify_modelo_revision`
        Verification entry point that appends these findings.
"""

from __future__ import annotations

from ...core.modelo import Modelo
from ...domain.calculations.registry.authority import bundled_authority
from ...domain.calculations.registry.errors import RegistrySnapshotError
from ...domain.modelos.calculation_revision import CalculationRevision
from ...domain.modelos.verification_report import ModeloVerificationFinding
from ...domain.modelos.work_unit import WorkUnit
from ..calculations._binding_prefill import resolve_bindings_from_local_store
from ..calculations._foreign_asset_redeclaration import (
    modelo_720_declared_observation,
    modelo_720_evidence_observation,
    modelo_720_prior_baseline_observation,
    modelo_720_redeclaration_advisory_findings,
)
from ..calculations.observations_repository import CalculationObservationRepository


def modelo_720_redeclaration_findings(
    *,
    work_unit: WorkUnit,
    revision: CalculationRevision,
    observation_repository: CalculationObservationRepository,
) -> tuple[ModeloVerificationFinding, ...]:
    """Return non-blocking re-declaration advisories for the Modelo 720 draft under verification.

    Returns an empty tuple for any modelo other than Modelo 720, when the
    registry revision cannot be resolved, when no prior-year baseline carries,
    or when the revision holds no foreign-asset row evidence to judge the
    declaration against. Silence in those cases is the honest outcome: there is
    nothing independent to compare, and a fabricated zero baseline would
    manufacture advisories on first-year filings.

    **THIS ADVISORY CANNOT FIRE IN PRODUCTION TODAY, AND THAT IS A
    DELIBERATE BOUNDARY RATHER THAN A DEFECT.** The evidence side is read
    from the revision's foreign-asset row bindings, which are written only
    when a caller supplies foreign-asset observations to the calculation.
    No production caller does: the single calculate entry point takes an
    input bundle carrying no observation field of any kind, and every
    operator surface routes through it. So the resolver runs with an empty
    collection, the evidence projection joins nothing, and the guard below
    returns at its own evidence check.

    The observations parameter on the aggregation path is an explicit
    injection point left for a durable foreign-asset observation store that
    was consciously not approved when this resolver was enrolled. Nothing is
    broken between here and the registry: the producer, the row-binding
    replay and this projection agree on binding id, row-index key and value
    form.

    The consequence is worth stating plainly, because everything visible
    argues the other way. This module is wired to the verification path, its
    end-to-end test passes, and the paragraph above correctly says no
    formula, total or export gate can notice a re-declaration omission. A
    reviewer doing everything right concludes the omission case is covered.
    It is not covered, and it will not be until the store lands.

    Args:
        work_unit: The unit under verification; its modelo, filing year and
            period drive the law-determined revision resolution.
        revision: The persisted :class:`CalculationRevision` supplying both the
            operator's declaration and the foreign-asset row evidence.
        observation_repository: Source of the carried prior-year baseline.
    """
    if work_unit.modelo != Modelo.M720:
        return ()

    # Law-determined resolution from (modelo, filing_year, period); the work
    # unit's stored revision id is never fed back in as the selector.
    try:
        snapshot = bundled_authority().snapshot(
            Modelo.M720.value,
            filing_year=work_unit.filing_year,
            period=work_unit.period.registry_token,
        )
    except RegistrySnapshotError:
        return ()

    modelo_revision = snapshot.revision
    filing_year = work_unit.filing_year
    period = work_unit.period.registry_token

    evidence = modelo_720_evidence_observation(
        revision=revision,
        modelo_revision=modelo_revision,
        filing_year=filing_year,
        period=period,
    )
    if not evidence.observations:
        return ()

    prefill = resolve_bindings_from_local_store(snapshot, repository=observation_repository)
    prior = modelo_720_prior_baseline_observation(
        binding_values=dict(prefill.binding_values),
        modelo_revision=modelo_revision,
        filing_year=filing_year,
        period=period,
    )
    if not prior.observations:
        return ()

    declared = modelo_720_declared_observation(
        revision=revision,
        modelo_revision=modelo_revision,
        filing_year=filing_year,
        period=period,
    )
    return modelo_720_redeclaration_advisory_findings(
        prior_observation=prior,
        current_observation=evidence,
        current_declaration_observation=declared,
    )


__all__ = ["modelo_720_redeclaration_findings"]

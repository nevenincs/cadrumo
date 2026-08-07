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

from ...core import Modelo
from ...domain.calculations.registry import RegistrySnapshotError
from ...domain.modelos import CalculationRevision, ModeloVerificationFinding, WorkUnit
from ..calculations import (
    CalculationObservationRepository,
    modelo_720_declared_observation,
    modelo_720_evidence_observation,
    modelo_720_prior_baseline_observation,
    modelo_720_redeclaration_advisory_findings,
    resolve_bindings_from_local_store,
)
from ._registry_resources import authority_via_resources


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
    """
    if work_unit.modelo != Modelo.M720:
        return ()

    # Law-determined resolution from (modelo, filing_year, period); the work
    # unit's stored revision id is never fed back in as the selector.
    try:
        snapshot = authority_via_resources().snapshot(
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

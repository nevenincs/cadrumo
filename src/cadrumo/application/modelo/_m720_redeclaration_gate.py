"""Verify-time Modelo 720 foreign-asset re-declaration gate.

RD 1065/2007 arts. 42-bis.5 / 42-ter.5 / 54-bis.7 re-impose the declaration
obligation on an already-declared foreign-asset bloque once its year-end
valuation grows more than the re-declaration delta over the last declared
baseline. A taxpayer who holds the position but omits it from the current
Modelo 720 under-declares silently: the omitted row simply is not there, so no
formula, total, or export gate can notice its absence.

This module turns that omission into an operator-visible, non-blocking advisory
at verify time by comparing three independent projections of one filing year:
the prior-year declared baseline carried through the revision's
``previous_filing`` bindings, the per-asset-row valuation evidence persisted on
the revision, and the operator's own declared casilla inputs. The declaration
and the evidence come from different channels; were both read from one source
the omitted-position test could never be satisfied.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from ...core.modelo import Modelo
from ...domain.calculations.registry.errors import RegistrySnapshotError
from ...domain.modelos.calculation_revision import CalculationRevision
from ...domain.modelos.verification_report import ModeloVerificationFinding
from ...domain.modelos.work_unit import WorkUnit
from ..calculations.binding_prefill import resolve_bindings_from_local_store
from ..calculations.foreign_asset_redeclaration import (
    modelo_720_declared_observation,
    modelo_720_evidence_observation,
    modelo_720_prior_baseline_observation,
    modelo_720_redeclaration_advisory_findings,
)
from ..calculations.iva_compensation_history_ports import IvaCompensationHistoryRepositoryProtocol
from ..calculations.observations_repository import CalculationObservationRepositoryProtocol

if TYPE_CHECKING:
    from ...domain.calculations.registry.authority import PinnedAuthorityOperation


def modelo_720_redeclaration_findings(
    *,
    work_unit: WorkUnit,
    revision: CalculationRevision,
    observation_repository: CalculationObservationRepositoryProtocol,
    iva_history_repository: IvaCompensationHistoryRepositoryProtocol,
    operation: PinnedAuthorityOperation,
) -> tuple[ModeloVerificationFinding, ...]:
    """Return non-blocking re-declaration advisories for the Modelo 720 draft under verification.

    Returns an empty tuple for any other modelo, when the coordinate selects no
    registry revision, when no prior-year baseline carries, or when the revision
    holds no foreign-asset row evidence to judge the declaration against. There
    is nothing independent to compare in those cases, and a fabricated zero
    baseline would manufacture advisories on first-year filings.

    Core types:
    :class:`~cadrumo.domain.modelos.calculation_revision.CalculationRevision`.
    """
    if str(work_unit.modelo) != Modelo("720").value:
        return ()
    filing_year = work_unit.filing_year
    period = work_unit.period.registry_token
    try:
        snapshot = operation.snapshot(Modelo("720").value, filing_year=filing_year, period=period)
    except RegistrySnapshotError:
        return ()
    modelo_revision = snapshot.revision

    evidence = modelo_720_evidence_observation(
        revision=revision,
        modelo_revision=modelo_revision,
        filing_year=filing_year,
        period=period,
        operation=operation,
    )
    if not evidence.observations:
        return ()

    prefill = resolve_bindings_from_local_store(
        snapshot,
        operation=operation,
        repository=observation_repository,
        iva_history_repository=iva_history_repository,
    )
    prior = modelo_720_prior_baseline_observation(
        binding_values=dict(prefill.binding_values),
        modelo_revision=modelo_revision,
        filing_year=filing_year,
        period=period,
        operation=operation,
    )
    if not prior.observations:
        return ()

    declared = modelo_720_declared_observation(
        revision=revision,
        modelo_revision=modelo_revision,
        filing_year=filing_year,
        period=period,
        operation=operation,
    )
    return modelo_720_redeclaration_advisory_findings(
        prior_observation=prior,
        current_observation=evidence,
        current_declaration_observation=declared,
        operation=operation,
    )


__all__ = ["modelo_720_redeclaration_findings"]

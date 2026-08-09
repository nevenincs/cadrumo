"""Fail-closed authority for Modelo 303's prior-domiciliation marker.

The page-three ``X`` marker is not a statement about the return currently
being exported.  It asks AEAT to cancel or modify a direct debit established
by the externally attested baseline being rectified.  This module therefore
requires a persisted, source-header-derived ``U`` observation joined by the
baseline's justificante CSV; a computed amount, a current profile, or an old
local export cannot substitute for that official evidence.
"""

from __future__ import annotations

from ...core import Modelo, PriorDomiciliationElection, ResultDisposition
from ...domain.modelos import (
    CalculationRevision,
    CalculationRevisionAmendmentKind,
    ModeloRecordCatalogueRepositoryProtocol,
    WorkUnit,
)
from ..calculations import (
    CalculationObservationRepository,
    PriorDomiciliationElectionProjection,
)
from ._action_errors import ModeloPriorDomiciliationElectionRefusedError


def resolve_prior_domiciliation_election(
    *,
    election: PriorDomiciliationElection,
    work_unit: WorkUnit,
    revision: CalculationRevision,
    filing_repository: ModeloRecordCatalogueRepositoryProtocol,
    observation_repository: CalculationObservationRepository,
) -> PriorDomiciliationElectionProjection:
    """Return safe election provenance, refusing any unproven ``X`` request.

    ``KEEP`` is intentionally a neutral no-proof default.  ``CANCEL_OR_MODIFY``
    requires the rectificativa's explicit amendment link, an externally
    evidenced baseline record, and the official same-target filed observation
    that carries the exact baseline CSV and a submitted-file ``U`` header.
    """
    if not isinstance(election, PriorDomiciliationElection):
        raise ModeloPriorDomiciliationElectionRefusedError(
            "prior domiciliation election must be a PriorDomiciliationElection value",
            context={"received_type": type(election).__name__},
        )
    if election is PriorDomiciliationElection.KEEP:
        return PriorDomiciliationElectionProjection(election=election)

    if work_unit.modelo != Modelo.M303.value:
        raise ModeloPriorDomiciliationElectionRefusedError(
            "prior domiciliation cancellation/modification is supported only for Modelo 303",
            context={"modelo": str(work_unit.modelo)},
        )
    if revision.amendment_kind is not CalculationRevisionAmendmentKind.RECTIFICATIVA:
        raise ModeloPriorDomiciliationElectionRefusedError(
            "prior domiciliation cancellation/modification requires a Modelo 303 rectificativa",
            context={"amendment_kind": revision.amendment_kind.value if revision.amendment_kind is not None else ""},
        )
    baseline_id = revision.amends_filing_record_id
    if baseline_id is None:
        raise ModeloPriorDomiciliationElectionRefusedError(
            "prior domiciliation cancellation/modification requires an explicit baseline filing link",
            context={"calculation_revision_id": revision.calculation_revision_id},
        )

    baseline = filing_repository.load().get(baseline_id)
    if baseline is None or baseline.external_evidence is None or not baseline.aeat_accepted:
        raise ModeloPriorDomiciliationElectionRefusedError(
            "prior domiciliation cancellation/modification requires an externally evidenced baseline filing",
            context={"baseline_filing_record_id": baseline_id},
        )
    if (
        baseline.bucket_id != work_unit.bucket_id
        or baseline.modelo != work_unit.modelo
        or baseline.filing_year != work_unit.filing_year
        or baseline.period != work_unit.period
    ):
        raise ModeloPriorDomiciliationElectionRefusedError(
            "prior domiciliation baseline does not match the rectificativa filing target",
            context={"baseline_filing_record_id": baseline_id},
        )

    observation = observation_repository.load_observation(str(baseline.modelo), baseline.period)
    if observation is None or not observation.source_kind.is_official_aeat:
        raise ModeloPriorDomiciliationElectionRefusedError(
            "prior domiciliation cancellation/modification requires an official baseline filed observation",
            context={"baseline_filing_record_id": baseline_id},
        )
    if (
        observation.observation.filing_year != baseline.filing_year
        or observation.observation.period != baseline.period.registry_token
        or observation.source_metadata.get("aeat_justificante_csv") != baseline.external_evidence.reference_id
    ):
        raise ModeloPriorDomiciliationElectionRefusedError(
            "official baseline observation does not match the baseline evidence reference",
            context={"baseline_filing_record_id": baseline_id},
        )
    disposition = observation.result_disposition
    if (
        disposition is None
        or disposition.provenance_kind != "source_header"
        or disposition.disposition is not ResultDisposition.DOMICILIACION
    ):
        raise ModeloPriorDomiciliationElectionRefusedError(
            "prior domiciliation cancellation/modification requires official baseline disposition U evidence",
            context={"baseline_filing_record_id": baseline_id},
        )
    return PriorDomiciliationElectionProjection(
        election=election,
        baseline_filing_record_id=baseline.filing_record_id,
        baseline_evidence_reference_id=baseline.external_evidence.reference_id,
        baseline_result_disposition=disposition.disposition,
        baseline_source_header_locator=disposition.provenance_locator,
    )


__all__ = ["resolve_prior_domiciliation_election"]

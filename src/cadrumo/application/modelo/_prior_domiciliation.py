"""Fail-closed authority for Modelo 303's prior-domiciliation marker.

The page-three ``X`` marker is not a statement about the return currently
being exported.  It asks AEAT to cancel or modify a direct debit established
by the externally attested baseline being rectified.  This module therefore
requires a persisted, source-header-derived ``U`` observation joined by the
baseline's justificante CSV; a computed amount, a current profile, or an old
local export cannot substitute for that official evidence.

The baseline is read from the :class:`ModeloRecord` that filed it and the
:class:`CalculationRevision` that produced its figures — both persisted, so the
marker rests on what was actually filed rather than on what the current export
would compute.
"""

from __future__ import annotations

from ...core import Modelo, ObservedHeaderFact, PriorDomiciliationElection, ResultDisposition
from ...domain.modelos import ExternalEvidence, ModeloRecord, ModeloRecordCatalogueRepositoryProtocol, WorkUnit
from ...domain.modelos.calculation_revision import CalculationRevision, CalculationRevisionAmendmentKind
from ..calculations import (
    M303_DECLARATION_TYPE_HEADER_KEY,
    CalculationObservationRepository,
    ObservationEnvelopePayload,
    PriorDomiciliationElectionProjection,
)
from ._action_errors import ModeloPriorDomiciliationElectionRefusedError


def _require_rectificativa_baseline_link(
    *,
    work_unit: WorkUnit,
    revision: CalculationRevision,
) -> str:
    """Return the baseline filing id an ``X`` request must name, or refuse.

    The marker asks AEAT to act on a PRIOR return, so the request is only
    coherent from a Modelo 303 rectificativa that says which return it amends.
    """
    if work_unit.modelo != Modelo.M303.value:
        raise ModeloPriorDomiciliationElectionRefusedError(
            "prior domiciliation cancellation/modification is supported only for Modelo 303",
            context={"modelo": str(work_unit.modelo)},
        )
    amendment_identity = revision.amendment_identity
    if amendment_identity is None or amendment_identity.kind is not CalculationRevisionAmendmentKind.RECTIFICATIVA:
        raise ModeloPriorDomiciliationElectionRefusedError(
            "prior domiciliation cancellation/modification requires a Modelo 303 rectificativa",
            context={"amendment_kind": amendment_identity.kind.value if amendment_identity is not None else ""},
        )
    return amendment_identity.amends_filing_record_id


def _require_evidenced_baseline_filing(
    *,
    baseline_id: str,
    work_unit: WorkUnit,
    filing_repository: ModeloRecordCatalogueRepositoryProtocol,
) -> tuple[ModeloRecord, ExternalEvidence]:
    """Return the externally attested baseline filing, or refuse.

    Both gates are about the same thing from opposite sides: the record must
    carry AEAT's own acceptance, and it must be the SAME filing target as the
    rectificativa -- a baseline for another period would move a direct debit
    the operator never asked about.
    """
    baseline = filing_repository.load().get(baseline_id)
    if baseline is None:
        raise ModeloPriorDomiciliationElectionRefusedError(
            "prior domiciliation cancellation/modification requires an externally evidenced baseline filing",
            context={"baseline_filing_record_id": baseline_id},
        )
    baseline_evidence = baseline.external_evidence
    if baseline_evidence is None or not baseline.aeat_accepted:
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
    return baseline, baseline_evidence


def _require_official_baseline_observation(
    *,
    baseline: ModeloRecord,
    baseline_evidence: ExternalEvidence,
    baseline_id: str,
    observation_repository: CalculationObservationRepository,
) -> ObservationEnvelopePayload:
    """Return the official filed observation joined to the baseline, or refuse.

    The join is by the baseline's own justificante CSV rather than by
    coordinates alone: matching year and period would also accept a different
    filing for the same target, which is exactly the substitution this module
    exists to prevent.
    """
    observation = observation_repository.load_observation(str(baseline.modelo), baseline.period)
    if observation is None or not observation.source_kind.is_official_aeat:
        raise ModeloPriorDomiciliationElectionRefusedError(
            "prior domiciliation cancellation/modification requires an official baseline filed observation",
            context={"baseline_filing_record_id": baseline_id},
        )
    if (
        observation.observation.filing_year != baseline.filing_year
        or observation.observation.period != baseline.period.registry_token
        or observation.source_metadata.get("aeat_justificante_csv") != baseline_evidence.reference_id
    ):
        raise ModeloPriorDomiciliationElectionRefusedError(
            "official baseline observation does not match the baseline evidence reference",
            context={"baseline_filing_record_id": baseline_id},
        )
    return observation


def _require_submitted_file_domiciliacion_header(
    *,
    observation: ObservationEnvelopePayload,
    baseline_id: str,
) -> ObservedHeaderFact:
    """Return the single submitted-file ``U`` declaration-type header, or refuse.

    Exactly one is required rather than at least one: two headers disagreeing
    about the baseline's disposition leave no fact to rectify against.
    """
    declaration_type_headers = tuple(
        header for header in observation.source_headers if header.header_key == M303_DECLARATION_TYPE_HEADER_KEY
    )
    if len(declaration_type_headers) != 1:
        raise ModeloPriorDomiciliationElectionRefusedError(
            "prior domiciliation cancellation/modification requires exactly one submitted-file "
            "baseline declaration type header",
            context={
                "baseline_filing_record_id": baseline_id,
                "header_key": M303_DECLARATION_TYPE_HEADER_KEY,
                "header_count": str(len(declaration_type_headers)),
            },
        )
    declaration_type_header = declaration_type_headers[0]
    if declaration_type_header.value != ResultDisposition.DOMICILIACION.value:
        raise ModeloPriorDomiciliationElectionRefusedError(
            "prior domiciliation cancellation/modification requires submitted-file baseline declaration type U",
            context={
                "baseline_filing_record_id": baseline_id,
                "header_key": M303_DECLARATION_TYPE_HEADER_KEY,
                "header_value": declaration_type_header.value,
            },
        )
    return declaration_type_header


def resolve_prior_domiciliation_election(
    *,
    election: object,
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

    The proof runs as an ordered chain of refusals, each stage narrowing what
    the next may assume.  Order is load-bearing rather than cosmetic: the
    baseline link is what the filing lookup needs, the filing is what the
    observation join keys on, and the header is what the disposition below is
    checked against -- so no stage can be reordered without weakening the one
    after it.

    ``revision`` is the draft :class:`CalculationRevision` being exported; it
    supplies the amendment link the chain starts from and never the proof
    itself, which is why a computed figure cannot stand in for the baseline.
    """
    if not isinstance(election, PriorDomiciliationElection):
        raise ModeloPriorDomiciliationElectionRefusedError(
            "prior domiciliation election must be a PriorDomiciliationElection value",
            context={"received_type": type(election).__name__},
        )
    if election is PriorDomiciliationElection.KEEP:
        return PriorDomiciliationElectionProjection(election=election)

    baseline_id = _require_rectificativa_baseline_link(work_unit=work_unit, revision=revision)
    baseline, baseline_evidence = _require_evidenced_baseline_filing(
        baseline_id=baseline_id,
        work_unit=work_unit,
        filing_repository=filing_repository,
    )
    observation = _require_official_baseline_observation(
        baseline=baseline,
        baseline_evidence=baseline_evidence,
        baseline_id=baseline_id,
        observation_repository=observation_repository,
    )
    declaration_type_header = _require_submitted_file_domiciliacion_header(
        observation=observation,
        baseline_id=baseline_id,
    )

    disposition = observation.result_disposition
    if (
        disposition is None
        or disposition.provenance_kind != "source_header"
        or disposition.disposition is not ResultDisposition.DOMICILIACION
        or disposition.provenance_locator != declaration_type_header.source_locator
    ):
        raise ModeloPriorDomiciliationElectionRefusedError(
            "prior domiciliation cancellation/modification requires a matching submitted-file "
            "baseline disposition U projection",
            context={"baseline_filing_record_id": baseline_id},
        )
    return PriorDomiciliationElectionProjection(
        election=election,
        baseline_filing_record_id=baseline.filing_record_id,
        baseline_evidence_reference_id=baseline_evidence.reference_id,
        baseline_result_disposition=disposition.disposition,
        baseline_source_header_locator=disposition.provenance_locator,
    )


__all__ = ["resolve_prior_domiciliation_election"]

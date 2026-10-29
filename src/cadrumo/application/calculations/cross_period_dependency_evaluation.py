"""Resolve source observations and filed history for cross-period dependencies.

Core types:
:class:`~cadrumo.domain.modelos.filing_record.ModeloRecord`.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from typing import NamedTuple, cast

from ...core.casilla_id import CasillaId
from ...core.identity.hex_ids import CalculationRevisionId
from ...core.identity.tax_id import same_tax_identifier
from ...core.period import Period
from ...domain.calculations.registry.authority import PinnedAuthorityOperation
from ...domain.calculations.registry.ids import RevisionId
from ...domain.calculations.registry.relations import (
    source_presence_gaps,
)
from ...domain.calculations.registry.schema_references import RegistrySnapshotRef
from ...domain.justificante.protocols import JustificanteRepositoryProtocol
from ...domain.modelos.calculation_revision import CalculationRevisionCatalogue, CalculationRevisionState
from ...domain.modelos.filing_record import (
    ExternalEvidenceKind,
    ModeloRecord,
    ModeloRecordCatalogue,
    ModeloRecordStatus,
)
from ...domain.modelos.verification_report import VerificationCompletenessStatus, VerificationReportCatalogue
from .cross_period_external_evidence import filing_external_evidence_blockers as _filing_external_evidence_blockers
from .cross_period_models import (
    CrossPeriodCleanStateBlocker,
    CrossPeriodDependencyEvidence,
    CrossPeriodDependencyRequirement,
    CrossPeriodExpectedMemberSet,
    ObservationPayload,
)
from .observations_repository import (
    CalculationObservationRepositoryProtocol,
    ObservationSourceKind,
    is_official_aeat_observation_source,
)
from .revision_carry_gate import revision_carry_outcome


class _CrossPeriodSource(NamedTuple):
    value_member_payloads: tuple[ObservationPayload, ...]
    observed_member_nifs: tuple[str, ...]
    expected_member_nifs: tuple[str, ...]
    missing_member_nifs: tuple[str, ...]
    unexpected_member_nifs: tuple[str, ...]
    payload: ObservationPayload | None
    blockers: tuple[CrossPeriodCleanStateBlocker, ...]


class _MemberSourceSelection(NamedTuple):
    value_member_payloads: tuple[ObservationPayload, ...]
    observed_member_nifs: tuple[str, ...]
    expected_member_nifs: tuple[str, ...]
    missing_member_nifs: tuple[str, ...]
    unexpected_member_nifs: tuple[str, ...]
    blockers: tuple[CrossPeriodCleanStateBlocker, ...]


class _MemberHistory(NamedTuple):
    member_filing_record_ids: tuple[str, ...]
    member_calculation_revision_ids: tuple[str, ...]
    calculation_revision_state: CalculationRevisionState | None
    verification_status: VerificationCompletenessStatus | None
    aeat_accepted: bool | None
    external_evidence_kind: ExternalEvidenceKind | None
    blockers: list[CrossPeriodCleanStateBlocker]


def _revision_carry_check(
    stamped_revision_id: RevisionId,
    source_modelo: str,
    source_filing_year: int,
    source_period: Period,
    *,
    operation: PinnedAuthorityOperation,
) -> list[CrossPeriodCleanStateBlocker]:
    """Return blockers for a carry-read revision check.

    Thin adapter over the single shared
    :func:`~application.calculations.revision_carry_gate.revision_carry_outcome`
    gate: it maps the shared refusal decision onto this site's
    blocker shape. A divergent or unreconfirmable stamp becomes a
    ``REGISTRY_REVISION_DIVERGENCE`` blocker so the cross-period clean-state,
    binding-prefill, and relation-prefill carry reads share one fail-closed
    law-determined re-confirmation.
    """
    refused = revision_carry_outcome(
        RegistrySnapshotRef(
            modelo=source_modelo,
            revision_id=stamped_revision_id,
            modelo_year=source_filing_year,
            period=source_period.registry_token,
        ),
        operation=operation,
    ).refused
    if refused:
        return [CrossPeriodCleanStateBlocker.REGISTRY_REVISION_DIVERGENCE]
    return []


def _aeat_register_provenance_blockers(
    payload: ObservationPayload,
    *,
    expected_tax_id: str | None,
) -> list[CrossPeriodCleanStateBlocker]:
    if not is_official_aeat_observation_source(payload.source_kind):
        return []
    metadata = payload.source_metadata
    if not metadata:
        return [CrossPeriodCleanStateBlocker.MISMATCHED_EXTERNAL_EVIDENCE_RECORD]

    blockers: list[CrossPeriodCleanStateBlocker] = []
    register_status = metadata.get("aeat_register_status", "").strip().upper()
    if not register_status or register_status != "ALTA":
        blockers.append(CrossPeriodCleanStateBlocker.MISMATCHED_EXTERNAL_EVIDENCE_RECORD)

    expediente_id = metadata.get("aeat_expediente_id", "").strip()
    if not expediente_id:
        blockers.append(CrossPeriodCleanStateBlocker.MISMATCHED_EXTERNAL_EVIDENCE_RECORD)

    authenticated_identity = metadata.get("authenticated_identity", "")
    if (expected_tax_id is not None and expected_tax_id) and not same_tax_identifier(
        authenticated_identity, expected_tax_id
    ):
        blockers.append(CrossPeriodCleanStateBlocker.MISMATCHED_EXTERNAL_EVIDENCE_RECORD)
    return blockers


def _member_payloads_for_requirement(
    requirement: CrossPeriodDependencyRequirement,
    observation_repository: CalculationObservationRepositoryProtocol,
) -> tuple[ObservationPayload, ...]:
    # CAST-RATIONALE-CROSS-PERIOD-MEMBER-PAYLOAD: iter_modelo records are typed envelopes at runtime.
    return tuple(
        # CAST-RATIONALE-CROSS-PERIOD-MEMBER-ITEM: iter_modelo records are typed envelopes at runtime.
        cast(  # nosemgrep: no-cast-in-domain-application reason: repository rows satisfy _ObservationPayload.
            ObservationPayload,
            item,
        )
        for item in observation_repository.iter_modelo(requirement.source_modelo)
        if item.observation.filing_year == requirement.filing_year
        and item.observation.period == requirement.period.registry_token
        and item.member_nif is not None
    )


def _select_member_source_payloads(
    requirement: CrossPeriodDependencyRequirement,
    observation_repository: CalculationObservationRepositoryProtocol,
    expected_member_set: CrossPeriodExpectedMemberSet | None,
) -> _MemberSourceSelection:
    member_payloads = _member_payloads_for_requirement(requirement, observation_repository)
    observed_member_nifs = tuple(sorted({str(item.member_nif) for item in member_payloads}))
    if expected_member_set is None:
        value_member_payloads = member_payloads
        roster_blockers: tuple[CrossPeriodCleanStateBlocker, ...] = (
            CrossPeriodCleanStateBlocker.MISSING_EXPECTED_GROUP_MEMBER_ROSTER,
            CrossPeriodCleanStateBlocker.INCOMPLETE_GROUP_MEMBER_COVERAGE,
        )
        return _MemberSourceSelection(
            value_member_payloads,
            observed_member_nifs,
            (),
            (),
            (),
            roster_blockers,
        )

    expected_member_nifs = tuple(sorted(set(expected_member_set.member_nifs)))
    expected_member_nif_set = set(expected_member_nifs)
    observed_member_nif_set = set(observed_member_nifs)
    missing_member_nifs = tuple(sorted(expected_member_nif_set - observed_member_nif_set))
    unexpected_member_nifs = tuple(sorted(observed_member_nif_set - expected_member_nif_set))
    blockers: list[CrossPeriodCleanStateBlocker] = []
    if missing_member_nifs:
        blockers.append(CrossPeriodCleanStateBlocker.INCOMPLETE_GROUP_MEMBER_COVERAGE)
    if unexpected_member_nifs:
        blockers.append(CrossPeriodCleanStateBlocker.UNEXPECTED_GROUP_MEMBER_SOURCE)
    value_member_payloads = tuple(item for item in member_payloads if str(item.member_nif) in expected_member_nif_set)
    return _MemberSourceSelection(
        value_member_payloads,
        observed_member_nifs,
        expected_member_nifs,
        missing_member_nifs,
        unexpected_member_nifs,
        tuple(blockers),
    )


def _member_source_revision_blockers(
    requirement: CrossPeriodDependencyRequirement,
    value_member_payloads: tuple[ObservationPayload, ...],
    *,
    operation: PinnedAuthorityOperation,
) -> tuple[CrossPeriodCleanStateBlocker, ...]:
    blockers: list[CrossPeriodCleanStateBlocker] = []
    for item in value_member_payloads:
        blockers.extend(_aeat_register_provenance_blockers(item, expected_tax_id=item.member_nif))
        blockers.extend(
            _revision_carry_check(
                item.stamped_revision_id,
                requirement.source_modelo,
                requirement.filing_year,
                requirement.period,
                operation=operation,
            ),
        )
    return tuple(blockers)


def _single_source_payload(
    requirement: CrossPeriodDependencyRequirement,
    observation_repository: CalculationObservationRepositoryProtocol,
) -> ObservationPayload | None:
    # CAST-RATIONALE-CROSS-PERIOD-SINGLE-PAYLOAD: load_observation returns the same envelope contract as iteration.
    # CAST-RATIONALE-CROSS-PERIOD-SINGLE-RESULT: load_observation returns the same envelope contract as iteration.
    return cast(  # nosemgrep: no-cast-in-domain-application reason: lookup returns this Protocol or None.
        ObservationPayload | None,
        observation_repository.load_observation(
            requirement.source_modelo,
            requirement.period,
        ),
    )


def _single_source_revision_blockers(
    requirement: CrossPeriodDependencyRequirement,
    payload: ObservationPayload | None,
    taxpayer_tax_id: str | None,
    *,
    operation: PinnedAuthorityOperation,
) -> tuple[CrossPeriodCleanStateBlocker, ...]:
    if payload is None:
        return ()
    blockers = _aeat_register_provenance_blockers(payload, expected_tax_id=taxpayer_tax_id)
    blockers.extend(
        _revision_carry_check(
            payload.stamped_revision_id,
            requirement.source_modelo,
            requirement.filing_year,
            requirement.period,
            operation=operation,
        ),
    )
    return tuple(blockers)


def _resolve_cross_period_source(
    requirement: CrossPeriodDependencyRequirement,
    observation_repository: CalculationObservationRepositoryProtocol,
    expected_member_set: CrossPeriodExpectedMemberSet | None,
    taxpayer_tax_id: str | None,
    *,
    operation: PinnedAuthorityOperation,
) -> _CrossPeriodSource:
    if requirement.requires_member_fan_in:
        selection = _select_member_source_payloads(
            requirement,
            observation_repository,
            expected_member_set,
        )
        blockers = [
            *selection.blockers,
            *_member_source_revision_blockers(
                requirement,
                selection.value_member_payloads,
                operation=operation,
            ),
        ]
        return _CrossPeriodSource(
            selection.value_member_payloads,
            selection.observed_member_nifs,
            selection.expected_member_nifs,
            selection.missing_member_nifs,
            selection.unexpected_member_nifs,
            None,
            tuple(blockers),
        )
    payload = _single_source_payload(requirement, observation_repository)
    blockers = _single_source_revision_blockers(requirement, payload, taxpayer_tax_id, operation=operation)
    return _CrossPeriodSource(
        (),
        (),
        (),
        (),
        (),
        payload,
        tuple(blockers),
    )


def _resolve_observation_values(
    requirement: CrossPeriodDependencyRequirement,
    value_member_payloads: tuple[ObservationPayload, ...],
    payload: ObservationPayload | None,
) -> tuple[ObservationSourceKind | None, dict[CasillaId, object], list[CrossPeriodCleanStateBlocker]]:
    if requirement.requires_member_fan_in and value_member_payloads:
        return _member_observation_values(requirement, value_member_payloads)
    if payload is None:
        return None, {}, [CrossPeriodCleanStateBlocker.MISSING_OBSERVATION]
    return _single_observation_values(requirement, payload)


def _is_missing_declared_source(
    requirement: CrossPeriodDependencyRequirement,
    values: Mapping[CasillaId, object],
) -> bool:
    missing_required, missing_groups = source_presence_gaps(
        required_source_casilla_ids=requirement.enforced_source_casilla_ids,
        source_presence_groups=requirement.source_presence_groups,
        observed_source_casilla_ids=values,
    )
    return bool(missing_required or missing_groups)


def _member_observation_values(
    requirement: CrossPeriodDependencyRequirement,
    value_member_payloads: tuple[ObservationPayload, ...],
) -> tuple[ObservationSourceKind | None, dict[CasillaId, object], list[CrossPeriodCleanStateBlocker]]:
    observation_source_kind = _combined_source_kind(item.source_kind for item in value_member_payloads)
    blockers: list[CrossPeriodCleanStateBlocker] = []
    if any(item.source_kind is ObservationSourceKind.OPERATOR_MANUAL for item in value_member_payloads):
        blockers.append(CrossPeriodCleanStateBlocker.OPERATOR_MANUAL_SOURCE)
    for item in value_member_payloads:
        if _is_missing_declared_source(requirement, item.observation.casilla_values):
            blockers.append(CrossPeriodCleanStateBlocker.MISSING_OBSERVED_CASILLA)
    return observation_source_kind, {}, blockers


def _single_observation_values(
    requirement: CrossPeriodDependencyRequirement,
    payload: ObservationPayload,
) -> tuple[ObservationSourceKind | None, dict[CasillaId, object], list[CrossPeriodCleanStateBlocker]]:
    observation_source_kind = payload.source_kind
    observation_values: dict[CasillaId, object] = dict(payload.observation.casilla_values)
    blockers: list[CrossPeriodCleanStateBlocker] = []
    if payload.source_kind is ObservationSourceKind.OPERATOR_MANUAL:
        blockers.append(CrossPeriodCleanStateBlocker.OPERATOR_MANUAL_SOURCE)
    if _is_missing_declared_source(requirement, observation_values):
        blockers.append(CrossPeriodCleanStateBlocker.MISSING_OBSERVED_CASILLA)
    return observation_source_kind, observation_values, blockers


def _aggregate_member_history(
    requirement: CrossPeriodDependencyRequirement,
    *,
    bucket_id: str,
    filing_catalogue: ModeloRecordCatalogue,
    calculation_catalogue: CalculationRevisionCatalogue,
    verification_catalogue: VerificationReportCatalogue,
    justificante_repository: JustificanteRepositoryProtocol,
    taxpayer_tax_id: str | None,
    observation_source_kind: ObservationSourceKind | None,
    value_member_payloads: tuple[ObservationPayload, ...],
    expected_member_nifs: tuple[str, ...],
    observed_member_nifs: tuple[str, ...],
    operation: PinnedAuthorityOperation,
) -> _MemberHistory:
    member_payload_by_nif = {str(item.member_nif): item for item in value_member_payloads}
    members_to_check = expected_member_nifs or observed_member_nifs
    results = tuple(
        _evaluate_member_history(
            requirement,
            member_nif=member_nif,
            member_payload=member_payload_by_nif.get(member_nif),
            bucket_id=bucket_id,
            filing_catalogue=filing_catalogue,
            calculation_catalogue=calculation_catalogue,
            verification_catalogue=verification_catalogue,
            justificante_repository=justificante_repository,
            taxpayer_tax_id=taxpayer_tax_id,
            observation_source_kind=observation_source_kind,
            operation=operation,
        )
        for member_nif in members_to_check
    )
    return _member_history_from_results(results)


def evaluate_requirement(
    requirement: CrossPeriodDependencyRequirement,
    *,
    operation: PinnedAuthorityOperation,
    bucket_id: str,
    observation_repository: CalculationObservationRepositoryProtocol,
    filing_catalogue: ModeloRecordCatalogue,
    calculation_catalogue: CalculationRevisionCatalogue,
    verification_catalogue: VerificationReportCatalogue,
    justificante_repository: JustificanteRepositoryProtocol,
    taxpayer_tax_id: str | None,
    expected_member_set: CrossPeriodExpectedMemberSet | None,
) -> CrossPeriodDependencyEvidence:
    """Evaluate observed values and filing history for one dependency."""
    source = _resolve_cross_period_source(
        requirement,
        observation_repository,
        expected_member_set,
        taxpayer_tax_id,
        operation=operation,
    )
    observation_source_kind, observation_values, value_blockers = _resolve_observation_values(
        requirement,
        source.value_member_payloads,
        source.payload,
    )
    blockers: list[CrossPeriodCleanStateBlocker] = [*source.blockers, *value_blockers]

    if requirement.requires_member_fan_in:
        history = _aggregate_member_history(
            requirement,
            bucket_id=bucket_id,
            filing_catalogue=filing_catalogue,
            calculation_catalogue=calculation_catalogue,
            verification_catalogue=verification_catalogue,
            justificante_repository=justificante_repository,
            taxpayer_tax_id=taxpayer_tax_id,
            observation_source_kind=observation_source_kind,
            value_member_payloads=source.value_member_payloads,
            expected_member_nifs=source.expected_member_nifs,
            observed_member_nifs=source.observed_member_nifs,
            operation=operation,
        )
        blockers.extend(history.blockers)
        return CrossPeriodDependencyEvidence(
            requirement=requirement,
            observation_source_kind=observation_source_kind,
            observed_member_nifs=source.observed_member_nifs,
            expected_member_nifs=source.expected_member_nifs,
            missing_member_nifs=source.missing_member_nifs,
            unexpected_member_nifs=source.unexpected_member_nifs,
            member_filing_record_ids=history.member_filing_record_ids,
            member_calculation_revision_ids=history.member_calculation_revision_ids,
            calculation_revision_state=history.calculation_revision_state,
            verification_status=history.verification_status,
            aeat_accepted=history.aeat_accepted,
            external_evidence_kind=history.external_evidence_kind,
            blockers=_unique_blockers(blockers),
        )

    filing_result = _evaluate_filing_history(
        requirement,
        bucket_id=bucket_id,
        filing_catalogue=filing_catalogue,
        calculation_catalogue=calculation_catalogue,
        verification_catalogue=verification_catalogue,
        justificante_repository=justificante_repository,
        taxpayer_tax_id=taxpayer_tax_id,
        observation_source_kind=observation_source_kind,
        observation_source_metadata=source.payload.source_metadata if source.payload is not None else None,
        observation_values=observation_values,
        member_nif=None,
        operation=operation,
    )
    blockers.extend(filing_result.blockers)

    return CrossPeriodDependencyEvidence(
        requirement=requirement,
        observation_source_kind=observation_source_kind,
        filing_record_id=filing_result.filing_record_id,
        calculation_revision_id=filing_result.calculation_revision_id,
        calculation_revision_state=filing_result.calculation_revision_state,
        verification_status=filing_result.verification_status,
        aeat_accepted=filing_result.aeat_accepted,
        external_evidence_kind=filing_result.external_evidence_kind,
        observed_member_nifs=source.observed_member_nifs,
        expected_member_nifs=source.expected_member_nifs,
        missing_member_nifs=source.missing_member_nifs,
        unexpected_member_nifs=source.unexpected_member_nifs,
        blockers=_unique_blockers(blockers),
    )


def _filing_revision_blockers(
    filing: ModeloRecord,
    requirement: CrossPeriodDependencyRequirement,
    calculation_catalogue: CalculationRevisionCatalogue,
    observation_values: Mapping[CasillaId, object],
    *,
    operation: PinnedAuthorityOperation,
) -> tuple[CalculationRevisionState | None, list[CrossPeriodCleanStateBlocker]]:
    blockers: list[CrossPeriodCleanStateBlocker] = []
    revision = calculation_catalogue.get(filing.calculation_revision_id)
    revision_state: CalculationRevisionState | None = None
    if revision is None:
        blockers.append(CrossPeriodCleanStateBlocker.MISSING_CALCULATION_REVISION)
    else:
        if revision_carry_outcome(revision.registry_snapshot_ref, operation=operation).refused:
            blockers.append(CrossPeriodCleanStateBlocker.REGISTRY_REVISION_DIVERGENCE)
            return None, blockers
        revision_state = revision.state
        if revision.state is not CalculationRevisionState.PRESENTADO:
            blockers.append(CrossPeriodCleanStateBlocker.UNFILED_CALCULATION_REVISION)
        for casilla_id in requirement.source_casilla_ids:
            observed = observation_values.get(casilla_id)
            if observed is None:
                continue
            if revision.casilla_values.get(casilla_id) != observed:
                blockers.append(CrossPeriodCleanStateBlocker.OBSERVATION_REVISION_VALUE_DIVERGENCE)
    return revision_state, blockers


def _filing_verification_blockers(
    filing: ModeloRecord,
    verification_catalogue: VerificationReportCatalogue,
) -> tuple[VerificationCompletenessStatus | None, list[CrossPeriodCleanStateBlocker]]:
    blockers: list[CrossPeriodCleanStateBlocker] = []
    verification_status: VerificationCompletenessStatus | None = None
    if filing.external_evidence is None:
        complete_reports = tuple(
            report
            for report in verification_catalogue.for_calculation_revision(filing.calculation_revision_id)
            if report.granted_verificado_completo
            and report.completeness_status is VerificationCompletenessStatus.COMPLETE
        )
        if complete_reports:
            verification_status = complete_reports[-1].completeness_status
        else:
            blockers.append(CrossPeriodCleanStateBlocker.MISSING_COMPLETE_VERIFICATION_REPORT)
    return verification_status, blockers


class _FilingHistory(NamedTuple):
    filing_record_id: str | None
    calculation_revision_id: CalculationRevisionId | None
    calculation_revision_state: CalculationRevisionState | None
    verification_status: VerificationCompletenessStatus | None
    aeat_accepted: bool | None
    external_evidence_kind: ExternalEvidenceKind | None
    blockers: list[CrossPeriodCleanStateBlocker]


def _evaluate_member_history(
    requirement: CrossPeriodDependencyRequirement,
    *,
    member_nif: str,
    member_payload: ObservationPayload | None,
    bucket_id: str,
    filing_catalogue: ModeloRecordCatalogue,
    calculation_catalogue: CalculationRevisionCatalogue,
    verification_catalogue: VerificationReportCatalogue,
    justificante_repository: JustificanteRepositoryProtocol,
    taxpayer_tax_id: str | None,
    observation_source_kind: ObservationSourceKind | None,
    operation: PinnedAuthorityOperation,
) -> _FilingHistory:
    member_values = dict(member_payload.observation.casilla_values) if member_payload is not None else {}
    member_source_kind = member_payload.source_kind if member_payload is not None else observation_source_kind
    member_source_metadata = member_payload.source_metadata if member_payload is not None else None
    return _evaluate_filing_history(
        requirement,
        bucket_id=bucket_id,
        filing_catalogue=filing_catalogue,
        calculation_catalogue=calculation_catalogue,
        verification_catalogue=verification_catalogue,
        justificante_repository=justificante_repository,
        taxpayer_tax_id=taxpayer_tax_id,
        observation_source_kind=member_source_kind,
        observation_source_metadata=member_source_metadata,
        observation_values=member_values,
        member_nif=member_nif,
        operation=operation,
    )


def _member_history_from_results(results: tuple[_FilingHistory, ...]) -> _MemberHistory:
    return _MemberHistory(
        _member_filing_record_ids(results),
        _member_calculation_revision_ids(results),
        _last_member_revision_state(results),
        _last_member_verification_status(results),
        _last_member_aeat_acceptance(results),
        _last_member_external_evidence_kind(results),
        _member_history_blockers(results),
    )


def _member_filing_record_ids(results: tuple[_FilingHistory, ...]) -> tuple[str, ...]:
    return tuple(result.filing_record_id for result in results if result.filing_record_id is not None)


def _member_calculation_revision_ids(results: tuple[_FilingHistory, ...]) -> tuple[CalculationRevisionId, ...]:
    return tuple(result.calculation_revision_id for result in results if result.calculation_revision_id is not None)


def _last_member_revision_state(
    results: tuple[_FilingHistory, ...],
) -> CalculationRevisionState | None:
    return next(
        (
            result.calculation_revision_state
            for result in reversed(results)
            if (result.calculation_revision_state is not None and result.calculation_revision_state)
        ),
        None,
    )


def _last_member_verification_status(
    results: tuple[_FilingHistory, ...],
) -> VerificationCompletenessStatus | None:
    return next(
        (
            result.verification_status
            for result in reversed(results)
            if (result.verification_status is not None and result.verification_status)
        ),
        None,
    )


def _last_member_aeat_acceptance(results: tuple[_FilingHistory, ...]) -> bool | None:
    return next((result.aeat_accepted for result in reversed(results) if result.aeat_accepted is not None), None)


def _last_member_external_evidence_kind(
    results: tuple[_FilingHistory, ...],
) -> ExternalEvidenceKind | None:
    return next(
        (
            result.external_evidence_kind
            for result in reversed(results)
            if (result.external_evidence_kind is not None and result.external_evidence_kind)
        ),
        None,
    )


def _member_history_blockers(results: tuple[_FilingHistory, ...]) -> list[CrossPeriodCleanStateBlocker]:
    return [blocker for result in results for blocker in result.blockers]


def _evaluate_filing_history(
    requirement: CrossPeriodDependencyRequirement,
    *,
    bucket_id: str,
    filing_catalogue: ModeloRecordCatalogue,
    calculation_catalogue: CalculationRevisionCatalogue,
    verification_catalogue: VerificationReportCatalogue,
    justificante_repository: JustificanteRepositoryProtocol,
    taxpayer_tax_id: str | None,
    observation_source_kind: ObservationSourceKind | None,
    observation_source_metadata: Mapping[str, str] | None,
    observation_values: Mapping[CasillaId, object],
    member_nif: str | None,
    operation: PinnedAuthorityOperation,
) -> _FilingHistory:
    blockers: list[CrossPeriodCleanStateBlocker] = []
    filing_history = filing_catalogue.history_for(
        bucket_id=bucket_id,
        modelo=requirement.source_modelo,
        filing_year=requirement.filing_year,
        period=requirement.period,
        member_nif=member_nif,
    )
    current_filings = tuple(record for record in filing_history if record.status is ModeloRecordStatus.VIGENTE)
    superseded_filings = tuple(record for record in filing_history if record.status is ModeloRecordStatus.SUPERSEDIDO)
    if len(current_filings) > 1:
        blockers.append(CrossPeriodCleanStateBlocker.DUPLICATE_CURRENT_FILING_RECORD)
    filing = current_filings[-1] if current_filings else None
    if filing is None:
        if superseded_filings:
            blockers.append(CrossPeriodCleanStateBlocker.SUPERSEDED_DEPENDENCY)
        blockers.append(CrossPeriodCleanStateBlocker.MISSING_CURRENT_FILING_RECORD)
        return _FilingHistory(None, None, None, None, None, None, blockers)

    blockers.extend(
        _filing_external_evidence_blockers(
            filing,
            observation_source_kind,
            justificante_repository,
            taxpayer_tax_id,
            observation_source_metadata,
        ),
    )
    revision_state, revision_blockers = _filing_revision_blockers(
        filing,
        requirement,
        calculation_catalogue,
        observation_values,
        operation=operation,
    )
    blockers.extend(revision_blockers)
    verification_status, verification_blockers = _filing_verification_blockers(filing, verification_catalogue)
    blockers.extend(verification_blockers)

    return _FilingHistory(
        filing.filing_record_id,
        filing.calculation_revision_id,
        revision_state,
        verification_status,
        filing.aeat_accepted,
        filing.external_evidence.kind if filing.external_evidence is not None else None,
        blockers,
    )


def _unique_blockers(
    blockers: Iterable[CrossPeriodCleanStateBlocker],
) -> tuple[CrossPeriodCleanStateBlocker, ...]:
    return tuple(dict.fromkeys(blockers))


def _combined_source_kind(source_kinds: Iterable[ObservationSourceKind]) -> ObservationSourceKind | None:
    unique = tuple(dict.fromkeys(source_kinds))
    if len(unique) == 1:
        return unique[0]
    return None

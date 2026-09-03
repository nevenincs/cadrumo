"""Contract tests for the safe AEAT Sync workspace projection."""

from __future__ import annotations

import ast
from datetime import UTC, date, datetime
from pathlib import Path

import pytest
from pydantic import ValidationError

from .....core.period import Period
from .....domain.modelos.codes import ModeloCode
from ..workspace import (
    AeatSyncAeatObservationState,
    AeatSyncCensusCategory,
    AeatSyncCensusStatus,
    AeatSyncDiscrepancyKind,
    AeatSyncDocumentCustodyState,
    AeatSyncJustificanteState,
    AeatSyncLocalFilingState,
    AeatSyncNotificationCategory,
    AeatSyncNotificationReadState,
    AeatSyncOverviewArea,
    AeatSyncReconciliationState,
    AeatSyncSourceState,
    AeatSyncSupportedAction,
    AeatSyncWorkspaceAvailability,
    AeatSyncWorkspaceCensusRowV1,
    AeatSyncWorkspaceEvidenceComparisonRowV1,
    AeatSyncWorkspaceFiledDeclarationRowV1,
    AeatSyncWorkspaceNotificationRowV1,
    AeatSyncWorkspaceOverviewRowV1,
    AeatSyncWorkspaceProjectionError,
    AeatSyncWorkspaceSource,
    AeatSyncWorkspaceZone,
    AeatSyncWorkspaceZoneObservationV1,
    project_aeat_sync_workspace,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_BUCKET = "11111111-1111-4111-8111-111111111111"
_OTHER_BUCKET = "22222222-2222-4222-8222-222222222222"
_T0 = datetime(2026, 1, 2, 9, tzinfo=UTC)
_T1 = datetime(2026, 1, 3, 10, tzinfo=UTC)
_T2 = datetime(2026, 1, 4, 11, tzinfo=UTC)
_PRIVATE_ID = "private-semantic-identifier"
_PRIVATE_NAME = "Taxpayer secret name"
_PRIVATE_NIF = "12345678Z"
_PRIVATE_CONCEPT = "Secret authority concept"
_PRIVATE_URL = "https://private.example/secret"
_PRIVATE_TEXT = "Confidential document text"
_PRIVATE_CERTIFICATE = "private-certificado-id"
_PRIVATE_SECRET = "private-secret"


def _period(code: str = "1T", year: int = 2026) -> Period:
    return Period.from_year_and_code(year, code)


def _observations(
    *,
    availability: AeatSyncWorkspaceAvailability = AeatSyncWorkspaceAvailability.AVAILABLE,
) -> tuple[AeatSyncWorkspaceZoneObservationV1, ...]:
    refusal = None if availability is AeatSyncWorkspaceAvailability.AVAILABLE else "aeat.sync.source.refused"
    observed_at = _T2 if availability in {
        AeatSyncWorkspaceAvailability.AVAILABLE,
        AeatSyncWorkspaceAvailability.STALE,
    } else None
    if availability is AeatSyncWorkspaceAvailability.STALE:
        refusal = "aeat.sync.source.stale"
    return tuple(
        AeatSyncWorkspaceZoneObservationV1(
            zone=zone,
            availability=availability,
            observed_at=observed_at,
            refusal=refusal,
        )
        for zone in AeatSyncWorkspaceZone
    )


def _mixed_observations() -> tuple[AeatSyncWorkspaceZoneObservationV1, ...]:
    states = (
        AeatSyncWorkspaceAvailability.AVAILABLE,
        AeatSyncWorkspaceAvailability.STALE,
        AeatSyncWorkspaceAvailability.UNAVAILABLE,
        AeatSyncWorkspaceAvailability.NEVER_CAPTURED,
        AeatSyncWorkspaceAvailability.LOCKED,
        AeatSyncWorkspaceAvailability.AVAILABLE,
    )
    return tuple(
        AeatSyncWorkspaceZoneObservationV1(
            zone=zone,
            availability=availability,
            observed_at=_T1
            if availability in {
                AeatSyncWorkspaceAvailability.AVAILABLE,
                AeatSyncWorkspaceAvailability.STALE,
            }
            else None,
            refusal=None
            if availability is AeatSyncWorkspaceAvailability.AVAILABLE
            else "aeat.sync.source.refused",
        )
        for zone, availability in zip(AeatSyncWorkspaceZone, states, strict=True)
    )


def _census(
    path: str = "address",
    *,
    bucket_id: str | None = _BUCKET,
    subject_key: str | None = "subject-a",
) -> AeatSyncWorkspaceCensusRowV1:
    return AeatSyncWorkspaceCensusRowV1(
        path=path,
        category=AeatSyncCensusCategory.ADDRESS,
        status=AeatSyncCensusStatus.CONFLICT,
        semantic_identity=_PRIVATE_ID + path,
        bucket_id=bucket_id,
        subject_key=subject_key,
        observed_value=_PRIVATE_NAME,
        local_value=_PRIVATE_NIF,
        name=_PRIVATE_NAME,
        nif=_PRIVATE_NIF,
        source_url=_PRIVATE_URL,
        raw_evidence={"text": _PRIVATE_TEXT},
        secret=_PRIVATE_SECRET,
    )


def _filed(
    modelo: str = "130",
    *,
    local_state: AeatSyncLocalFilingState = AeatSyncLocalFilingState.FILED,
    aeat_state: AeatSyncAeatObservationState = AeatSyncAeatObservationState.ACCEPTED,
    semantic_identity: str = _PRIVATE_ID,
    bucket_id: str | None = _BUCKET,
    subject_key: str | None = "subject-a",
) -> AeatSyncWorkspaceFiledDeclarationRowV1:
    local_filed_at = _T1 if local_state is AeatSyncLocalFilingState.FILED else None
    aeat_observed_at = _T2 if aeat_state is not AeatSyncAeatObservationState.NOT_OBSERVED else None
    justificante = (
        AeatSyncJustificanteState.VERIFIED
        if aeat_state is AeatSyncAeatObservationState.ACCEPTED
        else AeatSyncJustificanteState.NOT_OBSERVED
    )
    return AeatSyncWorkspaceFiledDeclarationRowV1(
        modelo=ModeloCode(modelo),
        filing_year=2026,
        period=_period(year=2026),
        local_filing_state=local_state,
        local_filed_at=local_filed_at,
        aeat_observation_state=aeat_state,
        aeat_observed_at=aeat_observed_at,
        justificante_state=justificante,
        justificante_observed_at=_T2 if justificante is AeatSyncJustificanteState.VERIFIED else None,
        semantic_identity=semantic_identity,
        bucket_id=bucket_id,
        subject_key=subject_key,
        expediente_id="private-expediente-id",
        certificado_id=_PRIVATE_CERTIFICATE,
        justificante_id="private-justificante-id",
        source_url=_PRIVATE_URL,
        document_text=_PRIVATE_TEXT,
        raw_evidence={"secret": _PRIVATE_SECRET},
        name=_PRIVATE_NAME,
        nif=_PRIVATE_NIF,
        secret=_PRIVATE_SECRET,
    )


def _notification(
    semantic_identity: str = _PRIVATE_ID,
    *,
    issued_on: date = date(2026, 1, 2),
    bucket_id: str | None = _BUCKET,
    subject_key: str | None = "subject-a",
) -> AeatSyncWorkspaceNotificationRowV1:
    return AeatSyncWorkspaceNotificationRowV1(
        semantic_identity=semantic_identity,
        issued_on=issued_on,
        read_on=date(2026, 1, 3),
        read_state=AeatSyncNotificationReadState.READ,
        category=AeatSyncNotificationCategory.FORMAL,
        document_custody_state=AeatSyncDocumentCustodyState.HELD,
        document_custody_observed_at=_T2,
        bucket_id=bucket_id,
        subject_key=subject_key,
        certificado_id=_PRIVATE_CERTIFICATE,
        concepto=_PRIVATE_CONCEPT,
        titular_nombre=_PRIVATE_NAME,
        destinatario_nombre=_PRIVATE_NAME,
        titular_nif=_PRIVATE_NIF,
        destinatario_nif=_PRIVATE_NIF,
        source_url=_PRIVATE_URL,
        document_text=_PRIVATE_TEXT,
        raw_evidence={"secret": _PRIVATE_SECRET},
        secret=_PRIVATE_SECRET,
    )


def _comparison(
    modelo: str = "130",
    *,
    local_state: AeatSyncSourceState = AeatSyncSourceState.PRESENT,
    aeat_state: AeatSyncSourceState = AeatSyncSourceState.ABSENT,
    semantic_identity: str | None = _PRIVATE_ID,
    bucket_id: str | None = _BUCKET,
    subject_key: str | None = "subject-a",
) -> AeatSyncWorkspaceEvidenceComparisonRowV1:
    discrepancy = (
        AeatSyncDiscrepancyKind.LOCAL_ONLY
        if local_state is AeatSyncSourceState.PRESENT and aeat_state is AeatSyncSourceState.ABSENT
        else AeatSyncDiscrepancyKind.NONE
    )
    return AeatSyncWorkspaceEvidenceComparisonRowV1(
        modelo=ModeloCode(modelo),
        filing_year=2026,
        period=_period(year=2026),
        local_state=local_state,
        aeat_state=aeat_state,
        local_observed_at=_T1,
        aeat_observed_at=_T2,
        discrepancy_kind=discrepancy,
        supported_actions=(AeatSyncSupportedAction.REVIEW, AeatSyncSupportedAction.COMPARE),
        semantic_identity=semantic_identity,
        bucket_id=bucket_id,
        subject_key=subject_key,
        source_url=_PRIVATE_URL,
        raw_evidence={"secret": _PRIVATE_SECRET},
        document_text=_PRIVATE_TEXT,
        secret=_PRIVATE_SECRET,
    )


def _reconciliation(
    modelo: str = "130",
    *,
    semantic_identity: str | None = _PRIVATE_ID,
    bucket_id: str | None = _BUCKET,
    subject_key: str | None = "subject-a",
) -> AeatSyncWorkspaceReconciliationRowV1:
    return AeatSyncWorkspaceReconciliationRowV1(
        modelo=ModeloCode(modelo),
        filing_year=2026,
        period=_period(year=2026),
        local_state=AeatSyncSourceState.PRESENT,
        aeat_state=AeatSyncSourceState.ABSENT,
        local_observed_at=_T1,
        aeat_observed_at=_T2,
        discrepancy_kind=AeatSyncDiscrepancyKind.LOCAL_ONLY,
        reconciliation_state=AeatSyncReconciliationState.KEEP_LOCAL,
        supported_actions=(AeatSyncSupportedAction.RECONCILE, AeatSyncSupportedAction.REVIEW),
        semantic_identity=semantic_identity,
        bucket_id=bucket_id,
        subject_key=subject_key,
        source_url=_PRIVATE_URL,
        raw_evidence={"secret": _PRIVATE_SECRET},
        document_text=_PRIVATE_TEXT,
        secret=_PRIVATE_SECRET,
    )


def _overview(
    area: AeatSyncOverviewArea = AeatSyncOverviewArea.CENSUS,
    *,
    semantic_identity: str | None = _PRIVATE_ID,
    bucket_id: str | None = _BUCKET,
    subject_key: str | None = "subject-a",
) -> AeatSyncWorkspaceOverviewRowV1:
    return AeatSyncWorkspaceOverviewRowV1(
        area=area,
        local_state=AeatSyncSourceState.PRESENT,
        aeat_state=AeatSyncSourceState.PRESENT,
        local_observed_at=_T1,
        aeat_observed_at=_T2,
        discrepancy_kind=AeatSyncDiscrepancyKind.NONE,
        supported_actions=(AeatSyncSupportedAction.REVIEW, AeatSyncSupportedAction.COMPARE),
        semantic_identity=semantic_identity,
        bucket_id=bucket_id,
        subject_key=subject_key,
        name=_PRIVATE_NAME,
        nif=_PRIVATE_NIF,
        source_url=_PRIVATE_URL,
        concept=_PRIVATE_CONCEPT,
        document_text=_PRIVATE_TEXT,
        raw_evidence={"secret": _PRIVATE_SECRET},
        secret=_PRIVATE_SECRET,
    )


def _projection(**kwargs: object):
    return project_aeat_sync_workspace(
        bucket_id=_BUCKET,
        zone_observations=_observations(),
        overview=kwargs.get("overview", (_overview(),)),
        census=kwargs.get("census", (_census(),)),
        filed_declarations=kwargs.get("filed_declarations", (_filed(),)),
        notifications=kwargs.get("notifications", (_notification(),)),
        evidence_comparison=kwargs.get("evidence_comparison", (_comparison(),)),
        reconciliation=kwargs.get("reconciliation", (_reconciliation(),)),
    )


def test_projection_has_exact_six_zones_and_safe_source_counts() -> None:
    projection = _projection()

    assert tuple(zone.zone for zone in projection.zones) == tuple(AeatSyncWorkspaceZone)
    assert tuple(zone.item_count for zone in projection.zones) == (1, 1, 1, 1, 1, 1)
    assert tuple(zone.sources for zone in projection.zones) == (
        (
            AeatSyncWorkspaceSource.LOCAL_PROFILE,
            AeatSyncWorkspaceSource.LOCAL_FILINGS,
            AeatSyncWorkspaceSource.LOCAL_NOTIFICATION_CUSTODY,
            AeatSyncWorkspaceSource.LOCAL_RECONCILIATION,
            AeatSyncWorkspaceSource.AEAT_CENSUS,
            AeatSyncWorkspaceSource.AEAT_FILED_DECLARATIONS,
            AeatSyncWorkspaceSource.AEAT_NOTIFICATIONS,
        ),
        (AeatSyncWorkspaceSource.LOCAL_PROFILE, AeatSyncWorkspaceSource.AEAT_CENSUS),
        (AeatSyncWorkspaceSource.LOCAL_FILINGS, AeatSyncWorkspaceSource.AEAT_FILED_DECLARATIONS),
        (AeatSyncWorkspaceSource.AEAT_NOTIFICATIONS, AeatSyncWorkspaceSource.LOCAL_NOTIFICATION_CUSTODY),
        (AeatSyncWorkspaceSource.LOCAL_FILINGS, AeatSyncWorkspaceSource.AEAT_FILED_DECLARATIONS),
        (
            AeatSyncWorkspaceSource.LOCAL_FILINGS,
            AeatSyncWorkspaceSource.AEAT_FILED_DECLARATIONS,
            AeatSyncWorkspaceSource.LOCAL_RECONCILIATION,
        ),
    )


def test_serialization_is_redacted_by_construction_and_projection_is_frozen() -> None:
    projection = _projection()
    exposed = projection.model_dump_json() + repr(projection)
    forbidden = (
        _BUCKET,
        _PRIVATE_ID,
        _PRIVATE_NAME,
        _PRIVATE_NIF,
        _PRIVATE_CONCEPT,
        _PRIVATE_URL,
        _PRIVATE_TEXT,
        _PRIVATE_CERTIFICATE,
        _PRIVATE_SECRET,
        "name",
        "nif",
        "concept",
        "source_url",
        "document_text",
        "raw_evidence",
        "certificado_id",
        "secret",
    )
    assert all(value not in exposed for value in forbidden)
    with pytest.raises(ValidationError):
        projection.contract_version = 2  # type: ignore[misc]


def test_independent_filing_axes_allow_local_only_and_aeat_only_observations() -> None:
    local_only = _filed(
        "130",
        local_state=AeatSyncLocalFilingState.FILED,
        aeat_state=AeatSyncAeatObservationState.NOT_OBSERVED,
        semantic_identity="local-only",
    )
    aeat_only = _filed(
        "303",
        local_state=AeatSyncLocalFilingState.NOT_OBSERVED,
        aeat_state=AeatSyncAeatObservationState.ACCEPTED,
        semantic_identity="aeat-only",
    )
    projection = _projection(filed_declarations=(aeat_only, local_only))
    assert tuple(row.local_filing_state for row in projection.filed_declarations) == (
        AeatSyncLocalFilingState.FILED,
        AeatSyncLocalFilingState.NOT_OBSERVED,
    )
    assert tuple(row.aeat_observation_state for row in projection.filed_declarations) == (
        AeatSyncAeatObservationState.NOT_OBSERVED,
        AeatSyncAeatObservationState.ACCEPTED,
    )
    with pytest.raises(ValidationError, match="unobserved AEAT filing"):
        _filed(
            local_state=AeatSyncLocalFilingState.FILED,
            aeat_state=AeatSyncAeatObservationState.NOT_OBSERVED,
        ).model_copy(update={"justificante_state": AeatSyncJustificanteState.AVAILABLE})


def test_availability_freshness_and_known_empty_are_distinct() -> None:
    observations = list(_observations())
    observations[0] = AeatSyncWorkspaceZoneObservationV1(
        zone=AeatSyncWorkspaceZone.OVERVIEW,
        availability=AeatSyncWorkspaceAvailability.STALE,
        observed_at=_T0,
        refusal="aeat.sync.source.stale",
    )
    projection = project_aeat_sync_workspace(
        bucket_id=_BUCKET,
        zone_observations=tuple(observations),
        overview=(_overview(),),
    )
    assert projection.zones[0].item_count == 1
    assert projection.zones[0].observed_at == _T0
    assert projection.zones[0].refusal == "aeat.sync.source.stale"

    empty = project_aeat_sync_workspace(bucket_id=_BUCKET, zone_observations=_observations())
    assert empty.zones[0].item_count == 0
    unavailable = list(_observations())
    unavailable[0] = AeatSyncWorkspaceZoneObservationV1(
        zone=AeatSyncWorkspaceZone.OVERVIEW,
        availability=AeatSyncWorkspaceAvailability.UNAVAILABLE,
        refusal="aeat.sync.source.unavailable",
    )
    unavailable_projection = project_aeat_sync_workspace(
        bucket_id=_BUCKET,
        zone_observations=tuple(unavailable),
    )
    assert unavailable_projection.zones[0].item_count is None
    with pytest.raises(AeatSyncWorkspaceProjectionError, match="confident rows"):
        project_aeat_sync_workspace(
            bucket_id=_BUCKET,
            zone_observations=tuple(unavailable),
            overview=(_overview(),),
        )


def test_duplicate_identity_scope_and_contradiction_validation() -> None:
    with pytest.raises(AeatSyncWorkspaceProjectionError, match="duplicate census"):
        _projection(census=(_census("same"), _census("same")))
    with pytest.raises(AeatSyncWorkspaceProjectionError, match="duplicate filed"):
        _projection(filed_declarations=(_filed(), _filed()))
    with pytest.raises(AeatSyncWorkspaceProjectionError, match="duplicate notification"):
        _projection(notifications=(_notification(), _notification()))
    with pytest.raises(AeatSyncWorkspaceProjectionError, match="foreign bucket"):
        _projection(census=(_census(bucket_id=_OTHER_BUCKET),))
    with pytest.raises(AeatSyncWorkspaceProjectionError, match="mix subjects"):
        _projection(census=(_census(subject_key="subject-b"),))
    with pytest.raises(ValidationError, match="discrepancy kind"):
        _comparison().model_copy(update={"discrepancy_kind": AeatSyncDiscrepancyKind.NONE})


def test_deterministic_ordering_and_action_order_are_independent_of_input_order() -> None:
    census_a = _census("a")
    census_b = _census("b")
    filed_a = _filed("130", semantic_identity="filed-a")
    filed_b = _filed("303", semantic_identity="filed-b")
    notification_a = _notification("notification-a", issued_on=date(2026, 1, 2))
    notification_b = _notification("notification-b", issued_on=date(2026, 1, 4))
    comparison_a = _comparison("130", semantic_identity="comparison-a")
    comparison_b = _comparison("303", semantic_identity="comparison-b")
    reconciliation_a = _reconciliation("130", semantic_identity="reconciliation-a")
    reconciliation_b = _reconciliation("303", semantic_identity="reconciliation-b")
    first = _projection(
        census=(census_b, census_a),
        filed_declarations=(filed_b, filed_a),
        notifications=(notification_b, notification_a),
        evidence_comparison=(comparison_b, comparison_a),
        reconciliation=(reconciliation_b, reconciliation_a),
    )
    second = _projection(
        census=(census_a, census_b),
        filed_declarations=(filed_a, filed_b),
        notifications=(notification_a, notification_b),
        evidence_comparison=(comparison_a, comparison_b),
        reconciliation=(reconciliation_a, reconciliation_b),
    )
    assert first == second
    assert first.model_dump_json() == second.model_dump_json()
    assert first.evidence_comparison[0].supported_actions == (
        AeatSyncSupportedAction.COMPARE,
        AeatSyncSupportedAction.REVIEW,
    )


def test_defining_module_has_no_adapter_filesystem_network_or_tui_import() -> None:
    path = Path(__file__).parents[1] / "workspace.py"
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    imports = {
        alias.name
        for node in ast.walk(tree)
        if isinstance(node, ast.Import)
        for alias in node.names
    } | {
        node.module or ""
        for node in ast.walk(tree)
        if isinstance(node, ast.ImportFrom)
    }
    forbidden = ("adapters", "entrypoints", "pathlib", "requests", "httpx", "socket", "tui", "network")
    assert not any(term in imported for imported in imports for term in forbidden)
    calls = {
        node.func.id
        for node in ast.walk(tree)
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
    }
    assert calls.isdisjoint({"open", "print", "input"})

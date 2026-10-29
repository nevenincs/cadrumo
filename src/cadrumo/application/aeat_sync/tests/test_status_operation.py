"""The registered `live.sync.status` read: what it loads, what it refuses, what it hides."""

from __future__ import annotations

import tomllib
from collections.abc import Callable
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from pathlib import Path

import pytest

from cadrumo_client.contracts.access_refusals import AccessDenialCode
from cadrumo_client.contracts.automation_codes import AutomationCustodyCode, AutomationCustodyError
from cadrumo_client.contracts.contracts import RefusalCode, RefusalError

from ....core.errors.hierarchy import CadrumoError, InternalInvariantError
from ....core.identity_check_verdict import IdentityCheckVerdict
from ....core.operations import OperationEffect
from ....core.period import Period
from ....domain.calculations.registry.authority import PinnedAuthorityOperation
from ....domain.modelos.work_unit import WorkUnit
from ...live.borrador_100 import Borrador100Snapshot, Borrador100SnapshotService
from ...live.notification_ports import NotificationType, RemoteNotification
from ...live.notifications import PersistedNotificationsSnapshot
from ...live.verify import VerifyObservation, VerifySurface
from ...operations.access_facts import operation_access_facts
from ...overview.evidence import AeatCalendarEvidenceSources, CalendarEvidenceReadOutcome
from ...persistence_errors import PersistenceDegradationError
from ...user_profile.access_errors import ProfileAccessRefusedError
from ...workbench_generation_calendar import unbound_calendar_aeat_evidence
from ..status_operation import (
    LIVE_SYNC_STATUS_DEFINITION_ID,
    AeatSyncStatusPorts,
    build_aeat_sync_status_definition,
    build_aeat_sync_status_registration,
    load_aeat_sync_status,
)
from ..workspace import AeatSyncAreaState, AeatSyncStatusArea
from ..workspace_reader import AeatSyncAreaAttempt

pytestmark = [pytest.mark.unit, pytest.mark.hex_application, pytest.mark.usefixtures("authority_operation")]

_BUCKET = "5aa00000-0000-4000-8000-0000000000aa"
_OTHER_BUCKET = "6bb00000-0000-4000-8000-0000000000bb"
_NOW = datetime(2026, 10, 29, 12, 0, tzinfo=UTC)
_NIF = "B12345674"


def _notification(*, leida: bool | None) -> RemoteNotification:
    return RemoteNotification(
        certificado_id="2699101808461",
        tipo=NotificationType.NOTIFICACION,
        concepto="Synthetic notification",
        titular_nif=_NIF,
        titular_nombre="Synthetic taxpayer",
        destinatario_nif=_NIF,
        destinatario_nombre="Synthetic taxpayer",
        fecha_emision=date(2026, 10, 1),
        leida=leida,
        source_url="https://sede.example/notification/1",
    )


def _snapshot(
    rows: tuple[RemoteNotification, ...], *, captured_at: datetime, bucket_id: str = _BUCKET
) -> PersistedNotificationsSnapshot:
    return PersistedNotificationsSnapshot(
        snapshot_id="a" * 64,
        bucket_id=bucket_id,
        captured_at=captured_at,
        persisted_at=captured_at,
        source_url="https://sede.example/notifications",
        rows=rows,
    )


def _verification(
    *,
    checked_at: datetime,
    bucket_id: str = _BUCKET,
    verdict: IdentityCheckVerdict = IdentityCheckVerdict.VALID,
) -> VerifyObservation:
    return VerifyObservation(
        observation_id=f"{int(checked_at.timestamp()):064x}",
        bucket_id=bucket_id,
        surface=VerifySurface.NIF_IVA,
        nif=_NIF,
        verdict=verdict,
        expected=None,
        matched_expectation=None,
        checked_at=checked_at,
        raw_evidence_locator="synthetic-private-evidence-locator",
        persisted_at=checked_at,
    )


class _BorradorRepository:
    """In-memory borrador snapshot store, so the lifecycle runs without secure storage."""

    def __init__(self) -> None:
        self.bucket_id = _BUCKET
        self._snapshots: dict[str, Borrador100Snapshot] = {}

    def exists(self, snapshot_id: str) -> bool:
        return snapshot_id in self._snapshots

    def load(self, snapshot_id: str) -> Borrador100Snapshot:
        return self._snapshots[snapshot_id]

    def resolve(self, snapshot_id: str) -> Borrador100Snapshot:
        return self._snapshots[snapshot_id]

    def list_snapshots(self) -> tuple[Borrador100Snapshot, ...]:
        return tuple(sorted(self._snapshots.values(), key=lambda item: (item.captured_at, item.snapshot_id)))

    def save(self, snapshot: Borrador100Snapshot) -> None:
        self._snapshots[snapshot.snapshot_id] = snapshot


def _borrador(operation: PinnedAuthorityOperation, *captured: datetime) -> tuple[Borrador100Snapshot, ...]:
    service = Borrador100SnapshotService(bucket_id=_BUCKET, repository=_BorradorRepository())
    period = Period.from_year_and_code(2023, "0A")
    for index, captured_at in enumerate(captured):
        service.capture(
            filing_year=period.filing_year,
            period=period,
            captured_at=captured_at,
            source_url=f"file-import:sha256:{index:064x}",
            binding_values={"casilla.0550": Decimal(index)},
            operation=operation,
        )
    return service.list_snapshots(operation=operation)


def _no_wallet_capture() -> datetime | None:
    return None


def _ports(
    *,
    profile_tax_id: Callable[[], str | None] = lambda: _NIF,
    calendar_aeat_reader: Callable[[], CalendarEvidenceReadOutcome[AeatCalendarEvidenceSources]] = (
        unbound_calendar_aeat_evidence
    ),
    filed_attempt: Callable[[], AeatSyncAreaAttempt | None] = lambda: None,
    drafts: Callable[[], tuple[WorkUnit, ...]] = lambda: (),
    latest_notifications: Callable[[], PersistedNotificationsSnapshot | None] = lambda: None,
    iva_wallet_captured_at: Callable[[], datetime | None] = _no_wallet_capture,
    borrador_snapshots: Callable[[], tuple[Borrador100Snapshot, ...]] = lambda: (),
    verify_observations: Callable[[str], tuple[VerifyObservation, ...]] = lambda _nif: (),
) -> AeatSyncStatusPorts:
    """Real stored values behind each port; a store a scenario does not seed answers empty."""
    return AeatSyncStatusPorts(
        profile_tax_id=profile_tax_id,
        filings=lambda: (),
        drafts=drafts,
        census_observation=lambda: None,
        calendar_aeat_reader=calendar_aeat_reader,
        filed_attempt=filed_attempt,
        latest_notifications=latest_notifications,
        iva_wallet_captured_at=iva_wallet_captured_at,
        borrador_snapshots=borrador_snapshots,
        verify_observations=verify_observations,
    )


def _load(ports: AeatSyncStatusPorts, operation: PinnedAuthorityOperation):
    return load_aeat_sync_status(ports, bucket_id=_BUCKET, observed_at=_NOW, operation=operation)


def _area(result, area: AeatSyncStatusArea):
    return next(item for item in result.status.areas if item.area is area)


def test_an_empty_profile_has_every_area_never_brought(authority_operation: PinnedAuthorityOperation) -> None:
    result = _load(_ports(), authority_operation)

    assert result.bucket_id == _BUCKET
    assert {item.state for item in result.status.areas} == {AeatSyncAreaState.NEVER_BROUGHT}


def test_unread_notifications_count_only_rows_the_aeat_marked_unread(
    authority_operation: PinnedAuthorityOperation,
) -> None:
    captured_at = _NOW - timedelta(days=2)
    rows = (
        _notification(leida=False),
        _notification(leida=False),
        _notification(leida=True),
        _notification(leida=None),
    )

    row = _area(
        _load(_ports(latest_notifications=lambda: _snapshot(rows, captured_at=captured_at)), authority_operation),
        AeatSyncStatusArea.NOTIFICATIONS,
    )

    assert row.state is AeatSyncAreaState.CURRENT
    assert row.last_brought_at == captured_at
    assert row.unread_notification_count == 2


def test_an_eight_day_old_notification_capture_is_possibly_stale(
    authority_operation: PinnedAuthorityOperation,
) -> None:
    snapshot = _snapshot((), captured_at=_NOW - timedelta(days=8))

    row = _area(
        _load(_ports(latest_notifications=lambda: snapshot), authority_operation), AeatSyncStatusArea.NOTIFICATIONS
    )

    assert row.state is AeatSyncAreaState.POSSIBLY_STALE
    assert row.unread_notification_count == 0


def test_the_newest_borrador_import_and_identity_check_set_their_areas(
    authority_operation: PinnedAuthorityOperation,
) -> None:
    older, newer = _NOW - timedelta(days=40), _NOW - timedelta(days=5)
    checks = (_verification(checked_at=older), _verification(checked_at=newer))

    result = _load(
        _ports(
            borrador_snapshots=lambda: _borrador(authority_operation, older, newer),
            verify_observations=lambda nif: checks,
        ),
        authority_operation,
    )

    assert _area(result, AeatSyncStatusArea.BORRADOR_100).last_brought_at == newer
    assert _area(result, AeatSyncStatusArea.IDENTITY_CHECKS).last_brought_at == newer


def test_identity_checks_are_read_for_the_profile_own_tax_number_only(
    authority_operation: PinnedAuthorityOperation,
) -> None:
    asked: list[str] = []

    def observations(nif: str) -> tuple[VerifyObservation, ...]:
        asked.append(nif)
        return ()

    result = _load(_ports(verify_observations=observations), authority_operation)

    assert asked == [_NIF]
    assert _NIF not in result.model_dump_json()


def test_a_profile_without_a_tax_number_cannot_scope_filed_or_identity_evidence(
    authority_operation: PinnedAuthorityOperation,
) -> None:
    def never_asked_for_identity(_nif: str) -> tuple[VerifyObservation, ...]:
        raise AssertionError("no tax number, so identity checks may not be asked for")

    def never_asked_for_register() -> CalendarEvidenceReadOutcome[AeatCalendarEvidenceSources]:
        raise AssertionError("no tax number, so the register capture may not be joined")

    result = _load(
        _ports(
            profile_tax_id=lambda: None,
            verify_observations=never_asked_for_identity,
            calendar_aeat_reader=never_asked_for_register,
        ),
        authority_operation,
    )

    for area in (AeatSyncStatusArea.FILED_DECLARATIONS, AeatSyncStatusArea.IDENTITY_CHECKS):
        row = _area(result, area)
        assert (row.state, row.refusal) == (AeatSyncAreaState.UNAVAILABLE, "aeat_sync.status.profile_tax_id_missing")
    assert _area(result, AeatSyncStatusArea.NOTIFICATIONS).state is AeatSyncAreaState.NEVER_BROUGHT


def test_one_unreadable_store_makes_only_its_own_area_unavailable(
    authority_operation: PinnedAuthorityOperation,
) -> None:
    def broken() -> PersistedNotificationsSnapshot | None:
        raise OSError("synthetic storage failure")

    brought_at = _NOW - timedelta(days=3)

    result = _load(_ports(latest_notifications=broken, iva_wallet_captured_at=lambda: brought_at), authority_operation)

    notifications = _area(result, AeatSyncStatusArea.NOTIFICATIONS)
    assert (notifications.state, notifications.refusal) == (
        AeatSyncAreaState.UNAVAILABLE,
        "aeat_sync.status.store_unreadable",
    )
    wallet = _area(result, AeatSyncStatusArea.IVA_WALLET)
    assert (wallet.state, wallet.last_brought_at) == (AeatSyncAreaState.CURRENT, brought_at)


def test_an_identity_check_that_got_no_answer_does_not_date_the_area(
    authority_operation: PinnedAuthorityOperation,
) -> None:
    answered, outage = _NOW - timedelta(days=60), _NOW - timedelta(days=1)
    checks = (
        _verification(checked_at=answered),
        _verification(checked_at=outage, verdict=IdentityCheckVerdict.UNKNOWN),
    )

    row = _area(
        _load(_ports(verify_observations=lambda _nif: checks), authority_operation), AeatSyncStatusArea.IDENTITY_CHECKS
    )

    assert (row.state, row.last_brought_at) == (AeatSyncAreaState.CURRENT, answered)


def test_identity_checks_that_only_got_no_answer_leave_the_area_never_brought(
    authority_operation: PinnedAuthorityOperation,
) -> None:
    checks = (_verification(checked_at=_NOW - timedelta(days=1), verdict=IdentityCheckVerdict.UNKNOWN),)

    row = _area(
        _load(_ports(verify_observations=lambda _nif: checks), authority_operation), AeatSyncStatusArea.IDENTITY_CHECKS
    )

    assert (row.state, row.last_brought_at) == (AeatSyncAreaState.NEVER_BROUGHT, None)


def test_a_persistence_degradation_from_one_store_makes_only_its_area_unavailable(
    authority_operation: PinnedAuthorityOperation,
) -> None:
    def refused() -> PersistedNotificationsSnapshot | None:
        raise PersistenceDegradationError("synthetic")

    brought_at = _NOW - timedelta(days=3)

    result = _load(_ports(latest_notifications=refused, iva_wallet_captured_at=lambda: brought_at), authority_operation)

    notifications = _area(result, AeatSyncStatusArea.NOTIFICATIONS)
    assert (notifications.state, notifications.refusal) == (
        AeatSyncAreaState.UNAVAILABLE,
        "aeat_sync.status.store_unreadable",
    )
    wallet = _area(result, AeatSyncStatusArea.IVA_WALLET)
    assert (wallet.state, wallet.last_brought_at) == (AeatSyncAreaState.CURRENT, brought_at)


@pytest.mark.parametrize(
    "error",
    [
        RefusalError(RefusalCode.UNAVAILABLE),
        AutomationCustodyError(AutomationCustodyCode.UNAVAILABLE),
        InternalInvariantError("synthetic invariant violation"),
    ],
    ids=["transport-refusal", "automation-custody", "internal-invariant"],
)
def test_a_refusal_or_other_registered_error_from_a_store_propagates_instead_of_reading_as_unavailable(
    error: CadrumoError, authority_operation: PinnedAuthorityOperation
) -> None:
    def failing() -> PersistedNotificationsSnapshot | None:
        raise error

    with pytest.raises(type(error)) as raised:
        _load(_ports(latest_notifications=failing), authority_operation)

    assert raised.value is error


def test_a_failed_filed_sweep_is_carried_as_the_last_attempt(authority_operation: PinnedAuthorityOperation) -> None:
    attempt = AeatSyncAreaAttempt(attempted_at=_NOW - timedelta(hours=1), succeeded=False)

    row = _area(
        _load(_ports(filed_attempt=lambda: attempt), authority_operation), AeatSyncStatusArea.FILED_DECLARATIONS
    )

    assert (row.state, row.last_attempt_at, row.last_attempt_succeeded) == (
        AeatSyncAreaState.NEVER_BROUGHT,
        attempt.attempted_at,
        False,
    )


def test_year_choices_span_the_registry_declared_support_floor_to_horizon(
    authority_operation: PinnedAuthorityOperation,
) -> None:
    declared = tomllib.loads(
        (Path(__file__).parents[3] / "_data/registry/aeat/legal/supported-filing-years.toml").read_text("utf-8")
    )["supported_filing_years"]
    assert "hard_ceiling" not in declared

    status = _load(_ports(), authority_operation).status

    assert status.filed_declaration_years == status.iva_wallet_years
    assert status.filed_declaration_years[0] == declared["floor"]
    assert status.filed_declaration_years[-1] >= declared["horizon"]
    assert list(status.filed_declaration_years) == list(
        range(status.filed_declaration_years[0], status.filed_declaration_years[-1] + 1)
    )


def test_a_capture_that_belongs_to_another_profile_is_refused_not_reported(
    authority_operation: PinnedAuthorityOperation,
) -> None:
    foreign = _snapshot((), captured_at=_NOW, bucket_id=_OTHER_BUCKET)

    with pytest.raises(ProfileAccessRefusedError) as refused:
        _load(_ports(latest_notifications=lambda: foreign), authority_operation)

    assert refused.value.reason is AccessDenialCode.PROFILE_MISMATCH


def test_the_registered_contract_is_a_local_read_with_no_effect_and_no_network() -> None:
    def unused(_bucket_id: str, _operation: PinnedAuthorityOperation) -> AeatSyncStatusPorts:
        raise AssertionError("registration must not compose any store")

    definition = build_aeat_sync_status_definition(unused)
    contract = build_aeat_sync_status_registration(definition).contract

    assert contract.definition_id == LIVE_SYNC_STATUS_DEFINITION_ID == "live.sync.status"
    assert contract.permitted_effects == {OperationEffect.NONE}
    assert contract.request_schema.schema_id == "live.sync.status.request"
    assert contract.result_schema is not None
    assert contract.result_schema.schema_id == "live.sync.status.result"
    facts = operation_access_facts(LIVE_SYNC_STATUS_DEFINITION_ID)
    assert (facts.changes_records, facts.reaches_network) == (False, False)

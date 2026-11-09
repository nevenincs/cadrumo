"""Contract tests for the pure installed-workbench generation assembler."""

from __future__ import annotations

import asyncio
import logging
from datetime import UTC, datetime
from types import SimpleNamespace
from typing import Any, cast
from uuid import UUID

import pytest
from pydantic import BaseModel

from cadrumo.application.user_profile.tests.persona_profile_facts import persona_facts_beneath
from cadrumo.tests.log_records import delivered_records

from ...core.errors.hierarchy import InternalInvariantError
from ...core.external_constants import OutputLanguage
from ...core.operations import profile_operation_subject
from ...domain.calculations.registry.authority import PinnedAuthorityOperation
from ...domain.modelos.calculation_revision import CalculationRevisionCatalogue
from ...domain.modelos.filing_record import ModeloRecordCatalogue
from ...domain.modelos.work_unit import WorkUnitCatalogue
from ...domain.user_profile.values import (
    ProfileSetupState,
    UserProfileFact,
    create_user_profile_record,
)
from ...tests.aeat_literal_fixtures import (
    CENSO_SOURCE_URL_FIXTURE,
)
from ..modelo.declarations_list_operation import (
    MODELO_DECLARATIONS_LIST_OPERATION_DEFINITION_ID,
    ModeloDeclarationsListExecutor,
    ModeloDeclarationsListProjectionV1,
    ModeloDeclarationsListRequest,
)
from ..operations import profile_guard
from ..operations.models import OperationIdentity, OperationRequest
from ..operations.owner import OperationExecutorContext
from ..operations.registry import OperationPublicContractSetV1
from ..overview.home import (
    HomeAccountSession,
    HomeAvailability,
    HomeSessionPosture,
    HomeZoneState,
)
from ..user_profile.censal_observation import CensalObservation
from ..user_profile.censal_operation import (
    build_censal_operation_registration,
)
from ..user_profile.censal_readback import CensalHistoryRead
from ..workbench_generation import (
    InstalledWorkbenchGenerationProviderV1,
)
from ..workbench_generation_reader import NotificationCustodyCount, SecureProfileWorkbenchGenerationReadDoorV1
from .workbench_generation_support import (
    NOW,
    PROFILE_ID,
    Repository,
    StableStore,
    censal_test_operation_definition,
    declaration_work_unit,
    ledger_ports,
    plain_generation_door,
    profile_record,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]


_PHASE_EVENTS = frozenset(
    {"workbench_capture_phase", "workbench_calendar_phase", "overview_applicability_phase", "declarations_list_phase"}
)
_PRIVATE_NAME = "synthetic-private-taxpayer-canary"


class _Custody:
    """A custody counter whose count holds, then answers ``recounted`` when rechecked; it logs each call."""

    def __init__(self, count: int, *, recounted: int | None = None, calls: list[str] | None = None) -> None:
        self._count = count
        self._recounted = count if recounted is None else recounted
        self.calls = [] if calls is None else calls

    def count(self) -> NotificationCustodyCount:
        self.calls.append("custody")
        return NotificationCustodyCount(count=self._count, stored_keys=())

    def recount(self, prior: NotificationCustodyCount) -> int:
        assert prior.count == self._count
        self.calls.append("custody recheck")
        return self._recounted


class _Census:
    """A census reader that reads ``observation``, then answers ``rechecked``; it logs each call."""

    def __init__(
        self,
        observation: CensalObservation | None,
        *,
        rechecked: CensalObservation | None = None,
        calls: list[str] | None = None,
    ) -> None:
        self._read = CensalHistoryRead(observation=observation, classified=frozenset(), census_operations=frozenset())
        self._rechecked = rechecked
        self.calls = [] if calls is None else calls

    def read(self) -> CensalHistoryRead:
        self.calls.append("census")
        return self._read

    def recheck(self, prior: CensalHistoryRead) -> CensalObservation | None:
        assert prior is self._read
        self.calls.append("census recheck")
        return self._rechecked


def _declaration_list_door(operation: PinnedAuthorityOperation) -> SecureProfileWorkbenchGenerationReadDoorV1:
    """Read one declaration, an empty ledger and a census and custody reader, from in-memory stores."""
    from ...domain.buckets.event import BucketEventHistoryCatalogue
    from ...domain.invoices.catalogue import InvoiceCatalogue
    from ...domain.transactions.models import TransactionCatalogue

    unit = declaration_work_unit(operation)
    record = profile_record(operation, facts=(UserProfileFact(path="identity.name", value=_PRIVATE_NAME),))
    return SecureProfileWorkbenchGenerationReadDoorV1(
        profile_id=PROFILE_ID,
        operation=operation,
        profile_repository=cast(Any, Repository(record)),
        work_unit_repository=cast(Any, Repository(WorkUnitCatalogue(work_units={unit.work_unit_id: unit}))),
        calculation_repository=cast(Any, Repository(CalculationRevisionCatalogue())),
        filing_repository=cast(Any, Repository(ModeloRecordCatalogue())),
        clock=lambda: NOW,
        bucket_event_repository=cast(Any, Repository(BucketEventHistoryCatalogue())),
        ledger_action_ports=ledger_ports(
            operation, transactions=StableStore(TransactionCatalogue()), invoices=StableStore(InvoiceCatalogue())
        ),
        notification_custody_reader=_Custody(4),
        census_observation_reader=_Census(None),
    )


def _phase_records(caplog: pytest.LogCaptureFixture, event: str | None = None) -> list[logging.LogRecord]:
    """The phase records a read delivered, in the order their phases ended."""
    return [
        record
        for record in delivered_records(caplog)
        if record.getMessage() in _PHASE_EVENTS and (event is None or record.getMessage() == event)
    ]


def _phase_names(records: list[logging.LogRecord]) -> list[str]:
    return [cast(str, record.__dict__["phase"]) for record in records]


def _assert_phase_records_are_timed_correlated_and_value_free(records: list[logging.LogRecord]) -> None:
    for record in records:
        elapsed = record.__dict__["elapsed_seconds"]
        assert isinstance(elapsed, float) and elapsed >= 0.0
        assert record.__dict__["outcome"] == "completed"
        assert (record.levelno >= logging.WARNING) == (elapsed >= 1.0), "only a phase from the slow bound warns"
        assert _PRIVATE_NAME not in repr(record.__dict__)
    assert len({record.__dict__["_cadrumo_diagnostic_id"] for record in records}) == 1
    assert records[0].__dict__["_cadrumo_diagnostic_id"] is not None


def test_the_declaration_list_capture_records_every_phase_with_its_seconds_and_counts(
    caplog: pytest.LogCaptureFixture, authority_operation: PinnedAuthorityOperation
) -> None:
    """The seconds of one list capture are attributed to named phases, down to the re-read that closes it."""
    door = _declaration_list_door(authority_operation)

    with caplog.at_level(logging.DEBUG):
        door.read_declaration_list_inputs()
    records = _phase_records(caplog)

    assert _phase_names(_phase_records(caplog, "workbench_capture_phase")) == [
        "profile_record",
        "work_units",
        "calculation_revisions",
        "filings",
        "verification_reports",
        "bucket_events",
        "lifecycle_facts",
        "declarations_portfolio",
        "declaration_summaries",
        "ledger_revision",
        "ledger_transactions",
        "ledger_invoices",
        "calendar_aeat_evidence",
        "calendar_memo_key",
        "calendar_inputs",
        "recheck_profile_record",
        "recheck_work_units",
        "recheck_calculation_revisions",
        "recheck_filings",
        "recheck_ledger_transactions",
        "recheck_ledger_invoices",
        "recheck_ledger",
        "recheck_verification_reports",
        "recheck_bucket_events",
        "recheck",
        "declaration_list_inputs",
    ]
    assert _phase_names(_phase_records(caplog, "workbench_calendar_phase")) == [
        "taxpayer_projection",
        "calendar_schedule",
        "calendar_with_filing_evidence",
        "agenda",
        "declarations_calendar",
    ]
    counts = {record.__dict__["phase"]: record.__dict__.get("item_count") for record in records}
    assert counts["work_units"] == counts["declarations_portfolio"] == counts["declaration_summaries"] == 1
    assert counts["calculation_revisions"] == counts["filings"] == counts["bucket_events"] == 0
    assert counts["ledger_transactions"] == counts["ledger_invoices"] == 0
    assert counts["calendar_inputs"] is None, "a phase that counts nothing says so rather than claiming zero"
    _assert_phase_records_are_timed_correlated_and_value_free(records)


@pytest.mark.parametrize("surface", ("generation", "declarations"))
def test_both_surfaces_capture_declaration_sources_in_the_same_order(
    caplog: pytest.LogCaptureFixture, authority_operation: PinnedAuthorityOperation, surface: str
) -> None:
    """Sharing the read retains the timed I/O prefix and the generation's session bracket."""
    from dataclasses import replace

    session_reads: list[str] = []
    clock_reads: list[str] = []

    def account_session() -> HomeAccountSession:
        session_reads.append("session")
        return HomeAccountSession(posture=HomeSessionPosture.ACTIVE, profile_label="Perfil local", expires_at=NOW)

    def clock() -> datetime:
        clock_reads.append("clock")
        return NOW

    door = replace(_declaration_list_door(authority_operation), account_session_reader=account_session, clock=clock)
    with caplog.at_level(logging.DEBUG):
        if surface == "generation":
            door.read_workbench_generation_inputs()
        else:
            door.read_declaration_list_inputs()

    phases = _phase_names(_phase_records(caplog, "workbench_capture_phase"))
    prefix = [
        "profile_record",
        "work_units",
        "calculation_revisions",
        "filings",
        "verification_reports",
        "bucket_events",
        "lifecycle_facts",
        "declarations_portfolio",
        "declaration_summaries",
        "ledger_revision",
        "ledger_transactions",
        "ledger_invoices",
        "calendar_aeat_evidence",
        "calendar_memo_key",
        "calendar_inputs",
    ]
    if surface == "generation":
        prefix.insert(0, "account_session")
        assert session_reads == ["session", "session"]
        assert phases.index("aeat_sync_workspace") < phases.index("account_session", 1) < phases.index("recheck")
    else:
        assert session_reads == []
    assert phases[: len(prefix)] == prefix
    assert clock_reads == ["clock"]


@pytest.mark.parametrize("surface", ("generation", "declarations"))
def test_a_failed_source_stops_both_captures_before_ledger_and_calendar_reads(
    caplog: pytest.LogCaptureFixture, authority_operation: PinnedAuthorityOperation, surface: str
) -> None:
    """The original failure propagates before later readers or a final session observation."""
    from dataclasses import replace

    error = ValueError("synthetic catalogue read failure")
    held_operations: list[PinnedAuthorityOperation] = []
    session_reads: list[str] = []

    class FailedCalculationRepository:
        def load_revisioned(self, *, operation: PinnedAuthorityOperation) -> tuple[CalculationRevisionCatalogue, str]:
            held_operations.append(operation)
            raise error

    def account_session() -> HomeAccountSession:
        session_reads.append("session")
        return HomeAccountSession(posture=HomeSessionPosture.ACTIVE, profile_label="Perfil local", expires_at=NOW)

    door = replace(
        _declaration_list_door(authority_operation),
        account_session_reader=account_session,
        calculation_repository=cast(Any, FailedCalculationRepository()),
    )
    with caplog.at_level(logging.DEBUG), pytest.raises(ValueError) as raised:
        if surface == "generation":
            door.read_workbench_generation_inputs()
        else:
            door.read_declaration_list_inputs()

    assert raised.value is error
    assert held_operations == [authority_operation]
    assert session_reads == (["session"] if surface == "generation" else [])
    phases = _phase_names(_phase_records(caplog, "workbench_capture_phase"))
    expected = ["profile_record", "work_units", "calculation_revisions"]
    if surface == "generation":
        expected.insert(0, "account_session")
    assert phases == [*expected, "generation_inputs" if surface == "generation" else "declaration_list_inputs"]


def test_the_declarations_list_read_records_every_phase_from_binding_the_reader_to_storing_the_result(
    caplog: pytest.LogCaptureFixture, monkeypatch: pytest.MonkeyPatch, authority_operation: PinnedAuthorityOperation
) -> None:
    """The executor's phases and the door's belong to one request, so its uncovered seconds are visible."""
    door = _declaration_list_door(authority_operation)
    request = OperationRequest[ModeloDeclarationsListRequest](
        definition_id=MODELO_DECLARATIONS_LIST_OPERATION_DEFINITION_ID,
        subject_ref=profile_operation_subject(PROFILE_ID),
        payload=ModeloDeclarationsListRequest(profile_id=UUID(PROFILE_ID), output_language=OutputLanguage.EN),
    )
    stored: list[BaseModel] = []

    async def put(operand: BaseModel, *, written_at: datetime) -> str:
        del written_at
        stored.append(operand)
        return "sha256:" + "a" * 64

    async def ignore(*_args: object) -> None:
        return None

    context = cast(
        OperationExecutorContext,
        SimpleNamespace(
            identity=OperationIdentity(
                operation_id="a" * 64, definition_id=request.definition_id, subject_ref=request.subject_ref
            ),
            events=SimpleNamespace(phase=ignore, effect=ignore),
            operands=SimpleNamespace(put=put),
            authority_operation=authority_operation,
        ),
    )
    monkeypatch.setattr(profile_guard, "require_active_bucket_id", lambda: PROFILE_ID)
    executor = ModeloDeclarationsListExecutor(lambda _profile_id, _operation: door.read_declaration_list_inputs)

    with caplog.at_level(logging.DEBUG):
        asyncio.run(executor.execute(request, context))
    records = _phase_records(caplog)

    (projection,) = stored
    assert isinstance(projection, ModeloDeclarationsListProjectionV1)
    listed = _phase_records(caplog, "declarations_list_phase")
    assert _phase_names(listed) == ["reader_binding", "capture", "rows", "wording", "read", "read_and_store"]
    assert {record.__dict__["definition_id"] for record in listed} == {MODELO_DECLARATIONS_LIST_OPERATION_DEFINITION_ID}
    counts = {record.__dict__["phase"]: record.__dict__.get("item_count") for record in listed}
    assert counts["capture"] == 1 and counts["rows"] == len(projection.rows)
    assert len(_phase_records(caplog, "workbench_capture_phase")) > 1, "the door's phases belong to the same read"
    _assert_phase_records_are_timed_correlated_and_value_free(records)


def test_the_filing_history_reads_the_bucket_event_log(
    authority_operation: PinnedAuthorityOperation,
) -> None:
    """A bound event log makes the filing history observable, not permanently unavailable."""
    from ...domain.buckets.event import BucketEventHistoryCatalogue, BucketEventObjectType, BucketEventType
    from ...domain.buckets.event_repository import build_bucket_event
    from ..modelo.declarations_workspace_contracts import DeclarationsLifecycleKind, DeclarationsWorkspaceZone

    unit = declaration_work_unit(authority_operation)
    created = build_bucket_event(
        bucket_id=PROFILE_ID,
        event_type=BucketEventType.MODELO_WORK_UNIT_CREATED,
        occurred_at=NOW,
        actor="operator",
        object_type=BucketEventObjectType.WORK_UNIT,
        object_id=unit.work_unit_id,
        payload={"modelo": "130", "filing_year": "2026", "period": "1T"},
        payload_version=1,
    )
    unrelated = build_bucket_event(
        bucket_id=PROFILE_ID,
        event_type=BucketEventType.MODELO_EXPORTED,
        occurred_at=NOW,
        actor="operator",
        object_type=BucketEventObjectType.WORK_UNIT,
        object_id=unit.work_unit_id,
        payload={"modelo": "130"},
        payload_version=1,
    )
    events = BucketEventHistoryCatalogue(events={created.event_id: created, unrelated.event_id: unrelated})

    generation = InstalledWorkbenchGenerationProviderV1(
        plain_generation_door(
            authority_operation,
            profile=Repository(profile_record(authority_operation)),
            work_units=Repository(WorkUnitCatalogue(work_units={unit.work_unit_id: unit})),
            bucket_events=Repository(events),
        )
    )()

    declarations = generation.declarations.projection
    assert declarations is not None
    history = next(zone for zone in declarations.zones if zone.zone is DeclarationsWorkspaceZone.FILING_HISTORY)
    assert history.reason_code is None
    assert [row.kind for row in declarations.lifecycle] == [DeclarationsLifecycleKind.CREATED]


def test_secure_generation_refuses_a_census_capture_changed_during_read(
    authority_operation: PinnedAuthorityOperation,
) -> None:
    """A concurrent pull cannot publish a generation with mismatched census evidence."""
    from dataclasses import replace

    from ..user_profile.censal_observation import (
        CensalObservation,
        CensalObservationAddress,
        CensalObservationIdentity,
    )

    observation = CensalObservation(
        identity=CensalObservationIdentity(nif="00001005Q"),
        domicilio_fiscal=CensalObservationAddress(),
        domicilio_notificacion=CensalObservationAddress(),
        captured_at=NOW,
        source_url=CENSO_SOURCE_URL_FIXTURE,
    )
    door = replace(
        plain_generation_door(authority_operation, profile=Repository(profile_record(authority_operation))),
        census_observation_reader=_Census(None, rechecked=observation),
    )
    with pytest.raises(InternalInvariantError, match="changed during capture"):
        door.read_workbench_generation_inputs()


def test_secure_generation_refuses_a_notification_document_stored_during_read(
    authority_operation: PinnedAuthorityOperation,
) -> None:
    """AEAT Sync cannot publish a custody count that was never true at one instant."""
    from dataclasses import replace

    door = replace(
        plain_generation_door(authority_operation, profile=Repository(profile_record(authority_operation))),
        notification_custody_reader=_Custody(4, recounted=5),
    )
    with pytest.raises(InternalInvariantError, match="changed during capture"):
        door.read_workbench_generation_inputs()


@pytest.mark.parametrize(
    ("surface", "expected_calls"),
    (("generation", ["custody", "census", "custody recheck", "census recheck"]), ("declarations", [])),
)
def test_only_a_generation_reads_the_census_and_custody_count_it_shows_in_aeat_sync(
    authority_operation: PinnedAuthorityOperation, surface: str, expected_calls: list[str]
) -> None:
    """The list shows neither, so it never pays the census scan of every journaled operation.

    A generation reads each once and rechecks each once at the close of the
    capture; neither is read whole a second time.
    """
    from dataclasses import replace

    calls: list[str] = []
    door = replace(
        _declaration_list_door(authority_operation),
        account_session_reader=lambda: HomeAccountSession(
            posture=HomeSessionPosture.ACTIVE, profile_label="Perfil local", expires_at=NOW
        ),
        census_observation_reader=_Census(None, calls=calls),
        notification_custody_reader=_Custody(4, calls=calls),
    )
    if surface == "generation":
        door.read_workbench_generation_inputs()
    else:
        door.read_declaration_list_inputs()

    assert calls == expected_calls


def test_a_resident_s_calendar_survives_the_registered_result_round_trip(
    authority_operation: PinnedAuthorityOperation,
) -> None:
    """A resident's calendar crosses the operation boundary with its meaning intact.

    The registered read projects the generation, stores it as JSON and the
    frontend restores it with no pinned authority; its calendar rows must
    survive both legs unchanged.
    """
    from uuid import UUID

    from ..workbench_generation_projection import (
        WorkbenchGenerationOperationProjection,
        project_workbench_generation,
        restore_workbench_generation,
    )

    record = create_user_profile_record(
        context=authority_operation.profile_create_context(),
        profile_id=PROFILE_ID,
        setup_state=ProfileSetupState.COMPLETE,
        facts=persona_facts_beneath(
            (
                UserProfileFact(path="identity.tax_id", value="X0001500M"),
                UserProfileFact(path="taxpayer_type.fiscal_residency", value="resident_irpf"),
            )
        ),
    )
    generation = InstalledWorkbenchGenerationProviderV1(
        plain_generation_door(authority_operation, profile=Repository(record))
    )()
    calendar = generation.declarations_calendar.projection
    assert calendar is not None
    assert calendar.entries

    public = project_workbench_generation(UUID(PROFILE_ID), generation)
    decoded = WorkbenchGenerationOperationProjection.model_validate_json(public.model_dump_json(), strict=True)
    restored = restore_workbench_generation(decoded)

    assert restored == generation
    assert restored.declarations_calendar.projection is not None
    assert restored.declarations_calendar.projection.entries == calendar.entries


def test_stored_filed_captures_reach_aeat_sync_through_the_calendar_reader(
    authority_operation: PinnedAuthorityOperation,
) -> None:
    """AEAT Sync reads the same stored captures the calendar does, in the same capture.

    The profile holds no local filing: a captured submission must still appear
    as an AEAT-only declaration rather than leaving the area never captured.
    """
    from dataclasses import replace

    from ..overview.evidence import AeatCalendarEvidenceSources, CalendarEvidenceReadOutcome
    from ..overview.tests.calendar_test_support import filed_declaration_observation

    captured_at = datetime(2025, 4, 16, 8, 0, tzinfo=UTC)
    reads: list[None] = []

    def read_captures() -> CalendarEvidenceReadOutcome[AeatCalendarEvidenceSources]:
        reads.append(None)
        return CalendarEvidenceReadOutcome(
            state=HomeZoneState(availability=HomeAvailability.AVAILABLE, observed_at=captured_at),
            value=AeatCalendarEvidenceSources(
                filed_declaration_observations=(filed_declaration_observation(artefacts=()),)
            ),
        )

    profile = Repository(
        profile_record(authority_operation, facts=(UserProfileFact(path="identity.tax_id", value="X0001500M"),))
    )
    door = replace(
        plain_generation_door(authority_operation, profile=profile),
        operation_contracts=OperationPublicContractSetV1.build(
            (build_censal_operation_registration(censal_test_operation_definition()).contract,)
        ),
        calendar_aeat_reader=read_captures,
    )

    generation = InstalledWorkbenchGenerationProviderV1(door)()

    assert len(reads) == 1
    projection = generation.aeat_sync.projection
    assert projection is not None
    (row,) = projection.filed_declarations
    assert (str(row.modelo), row.filing_year, row.period.registry_token) == ("303", 2025, "1T")
    assert row.local_filing_state.value == "not_observed"
    assert row.aeat_observation_state.value == "submitted"
    assert row.aeat_observed_at == captured_at
    assert row.justificante_state.value == "not_observed"
    filed = next(item for item in projection.overview if item.area.value == "filed_declarations")
    assert (filed.local_state.value, filed.aeat_state.value) == ("absent", "present")

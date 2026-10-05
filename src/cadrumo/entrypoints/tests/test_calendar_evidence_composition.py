"""The installed calendar preserves confirmed encrypted observations across read failures."""

from __future__ import annotations

import inspect
from datetime import UTC, date, datetime
from pathlib import Path

import pytest
from pydantic import AnyHttpUrl, TypeAdapter

from ...adapters.outbound.aeat.sede.observation_store import (
    FiledDeclaracionObservationStore,
    filed_declaracion_observation_object_key,
)
from ...adapters.outbound.aeat.sede.schema import FiledDeclaracionArtefact, FiledDeclaracionObservation
from ...adapters.persistence.storage.secure_object_namespaces import AEAT_FILED_DECLARATION_OBSERVATIONS_NAMESPACE
from ...adapters.persistence.storage.tests.secure_sql import isolated_runtime_profile, read_db_at_rest_bytes
from ...application.overview.calendar import build_overview_calendar
from ...application.overview.calendar_models import (
    OverviewAeatSubmissionState,
    OverviewCalendarEntry,
    OverviewCalendarRange,
)
from ...application.overview.evidence import (
    AeatCalendarEvidenceSources,
    CalendarEvidenceReadOutcome,
    LocalCalendarEvidenceSources,
    build_calendar_evidence_projection,
)
from ...application.overview.home import HomeAvailability, HomeZoneState
from ...application.overview.tests.calendar_test_support import profile
from ...core.authority_grade import RegistryAuthorityGrade
from ...core.config import load_settings
from ...core.hashing import sha256_hex
from ...core.period import Period
from ...domain.calculations.registry.authority import PinnedAuthorityOperation
from ...domain.deadlines.models import ObligationStatus
from ..calendar_evidence_composition import compose_calendar_aeat_reader

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint]

_PRESENTED_AT = datetime(2025, 4, 14, 11, 22, 33, tzinfo=UTC)
_CAPTURED_AT = datetime(2025, 4, 16, 9, 8, 7, tzinfo=UTC)
_PERIOD = Period.from_year_and_code(2025, "1T")
_RAW_MARKER = "calendar-private-register-payload-678921"
_EXPEDIENTE = "3032025Q1ABCDEFGH12345678"


def _store_observation(
    operation: PinnedAuthorityOperation,
    *,
    expediente: str = _EXPEDIENTE,
    period: str = "1T",
    wrong_revision: bool = False,
    captured_at: tuple[datetime, ...] = (_CAPTURED_AT,),
) -> FiledDeclaracionObservation:
    store = FiledDeclaracionObservationStore(load_settings().cadrumo_filed_declarations_dir)
    body = _RAW_MARKER.encode("utf-8")
    artefacts = tuple(
        store.persist_artefact(
            ("303", 2025, Period.from_year_and_code(2025, period), expediente),
            FiledDeclaracionArtefact(
                kind="register_row",
                source_url=TypeAdapter(AnyHttpUrl).validate_python("https://sede.agenciatributaria.gob.es/"),
                content_type="text/html",
                byte_count=len(body),
                sha256=sha256_hex(body),
                captured_at=capture,
            ),
            body,
        )
        for capture in captured_at
    )
    snapshot = operation.snapshot("303", filing_year=2025, period=period, grade=RegistryAuthorityGrade.CALCULATION)
    coordinate = snapshot.snapshot_ref
    if wrong_revision:
        coordinate = coordinate.model_copy(update={"revision_id": "2023"})
    observation = FiledDeclaracionObservation(
        modelo="303",
        ejercicio=2025,
        period=Period.from_year_and_code(2025, period),
        expediente_id=expediente,
        status="ALTA",
        presented_at=_PRESENTED_AT,
        authenticated_identity=profile().tax_id,
        artefacts=artefacts,
        metadata={"raw_register_payload": _RAW_MARKER},
        registry_snapshot_ref=coordinate,
    )
    store.persist_observation(observation, operation=operation)
    return observation


def _calendar_row(
    operation: PinnedAuthorityOperation,
    outcome: CalendarEvidenceReadOutcome[AeatCalendarEvidenceSources],
) -> OverviewCalendarEntry:
    persona = profile()
    projected = build_calendar_evidence_projection(
        local=CalendarEvidenceReadOutcome(
            state=HomeZoneState(availability=HomeAvailability.AVAILABLE), value=LocalCalendarEvidenceSources()
        ),
        aeat=outcome,
        expected_tax_id=persona.tax_id,
    )
    calendar = build_overview_calendar(
        persona,
        OverviewCalendarRange(from_date=date(2025, 4, 1), to_date=date(2025, 4, 30)),
        operation=operation,
        today=date(2025, 4, 30),
        filing_evidence=projected.evidence,
    )
    return next(row for row in calendar.entries if row.modelo == "303" and row.period == _PERIOD)


def _assert_confirmed(row: OverviewCalendarEntry, observation: FiledDeclaracionObservation) -> None:
    assert row.status is ObligationStatus.FILED
    assert row.recovery is None
    assert row.days_overdue is None
    assert row.filing_evidence.aeat_submission_state is OverviewAeatSubmissionState.SUBMITTED_OBSERVED
    assert row.filing_evidence.aeat_reference_id == observation.expediente_id
    assert row.filing_evidence.aeat_submitted_at == _PRESENTED_AT
    assert row.filing_evidence.justificante_verified is False


def test_an_encrypted_authenticated_alta_completes_the_calendar_without_a_receipt(
    tmp_path: Path, operation: PinnedAuthorityOperation
) -> None:
    with isolated_runtime_profile(tmp_path=tmp_path) as runtime:
        observation = _store_observation(operation)
        assert all(item.kind != "justificante_pdf" for item in observation.artefacts)
        assert _RAW_MARKER.encode("utf-8") not in read_db_at_rest_bytes(runtime.paths.database_file)
        read = compose_calendar_aeat_reader(operation)
        outcome = read()
        assert outcome.state.availability is HomeAvailability.AVAILABLE
        assert outcome.state.observed_at == _CAPTURED_AT
        assert outcome.value is not None
        assert outcome.value.filed_declaration_observations == (observation,)
        _assert_confirmed(_calendar_row(operation, outcome), observation)


def test_a_later_locked_read_retains_confirmed_metadata_without_raw_payloads(
    tmp_path: Path, operation: PinnedAuthorityOperation
) -> None:
    with isolated_runtime_profile(tmp_path=tmp_path):
        observation = _store_observation(operation)
        read = compose_calendar_aeat_reader(operation)
        _assert_confirmed(_calendar_row(operation, read()), observation)
    outcome = read()
    assert outcome.state.availability is HomeAvailability.STALE
    assert outcome.state.reason_code == "workbench.calendar.aeat_reader_unavailable"
    assert outcome.state.observed_at == _CAPTURED_AT
    assert outcome.value is not None
    assert outcome.value.filed_declaration_observations == ()
    (event,) = outcome.value.observed_events
    assert event.authenticated_identity == profile().tax_id
    assert event.status == "ALTA"
    assert event.event_date == _PRESENTED_AT.date()
    assert event.aeat_submitted_at == _PRESENTED_AT
    assert event.reference_id == _EXPEDIENTE
    assert _RAW_MARKER not in repr(inspect.getclosurevars(read).nonlocals)
    _assert_confirmed(_calendar_row(operation, outcome), observation)


def test_an_unconfirmed_coordinate_does_not_erase_a_healthy_encrypted_neighbour(
    tmp_path: Path, operation: PinnedAuthorityOperation
) -> None:
    with isolated_runtime_profile(tmp_path=tmp_path):
        healthy = _store_observation(operation)
        unconfirmed = _store_observation(
            operation, expediente="3032025Q2ABCDEFGH12345678", period="2T", wrong_revision=True
        )
        store = FiledDeclaracionObservationStore(load_settings().cadrumo_filed_declarations_dir)
        assert len(store.list_observations()) == 2
        read = compose_calendar_aeat_reader(operation)
        outcome = read()
        assert outcome.state.availability is HomeAvailability.STALE
        assert outcome.state.reason_code == "workbench.calendar.aeat_coordinate_unconfirmed"
        assert outcome.value is not None
        assert outcome.value.filed_declaration_observations == (healthy,)
        assert unconfirmed.registry_snapshot_ref != healthy.registry_snapshot_ref
        _assert_confirmed(_calendar_row(operation, outcome), healthy)
    failed_read = read()
    assert failed_read.state.availability is HomeAvailability.STALE
    assert failed_read.value is not None
    assert tuple(event.reference_id for event in failed_read.value.observed_events) == (healthy.expediente_id,)
    _assert_confirmed(_calendar_row(operation, failed_read), healthy)


def test_an_empty_encrypted_history_is_never_captured_and_a_locked_read_is_unavailable(
    tmp_path: Path, operation: PinnedAuthorityOperation
) -> None:
    with isolated_runtime_profile(tmp_path=tmp_path):
        store = FiledDeclaracionObservationStore(load_settings().cadrumo_filed_declarations_dir)
        assert store.list_observations() == ()
        read = compose_calendar_aeat_reader(operation)
        outcome = read()
        assert outcome.state.availability is HomeAvailability.NEVER_CAPTURED
        assert outcome.state.reason_code == "workbench.calendar.no_aeat_observations"
        assert outcome.state.observed_at is None
        assert outcome.value is None
        assert _calendar_row(operation, outcome).status is not ObligationStatus.FILED
    failed_read = read()
    assert failed_read.state.availability is HomeAvailability.UNAVAILABLE
    assert failed_read.state.reason_code == "workbench.calendar.aeat_reader_unavailable"
    assert failed_read.state.observed_at is None
    assert failed_read.value is None


def test_a_later_successful_empty_read_preserves_confirmed_metadata_as_stale(
    tmp_path: Path, operation: PinnedAuthorityOperation
) -> None:
    with isolated_runtime_profile(tmp_path=tmp_path) as runtime:
        observation = _store_observation(operation)
        read = compose_calendar_aeat_reader(operation)
        _assert_confirmed(_calendar_row(operation, read()), observation)
        assert runtime.repository.delete(
            AEAT_FILED_DECLARATION_OBSERVATIONS_NAMESPACE.namespace,
            filed_declaracion_observation_object_key(
                observation.modelo, observation.ejercicio, observation.period, observation.expediente_id
            ),
        )
        store = FiledDeclaracionObservationStore(load_settings().cadrumo_filed_declarations_dir)
        assert store.list_observations() == ()
        outcome = read()
        assert outcome.state.availability is HomeAvailability.STALE
        assert outcome.state.reason_code == "workbench.calendar.no_aeat_observations"
        assert outcome.state.observed_at == _CAPTURED_AT
        assert outcome.value is not None
        assert outcome.value.filed_declaration_observations == ()
        assert tuple(event.reference_id for event in outcome.value.observed_events) == (observation.expediente_id,)
        assert _RAW_MARKER not in repr(inspect.getclosurevars(read).nonlocals)
        _assert_confirmed(_calendar_row(operation, outcome), observation)


def test_observed_at_is_the_latest_actual_artefact_capture_across_observations(
    tmp_path: Path, operation: PinnedAuthorityOperation
) -> None:
    later_capture = datetime(2025, 7, 18, 16, 15, 14, tzinfo=UTC)
    with isolated_runtime_profile(tmp_path=tmp_path):
        first = _store_observation(operation, captured_at=(_CAPTURED_AT, later_capture))
        second = _store_observation(
            operation,
            expediente="3032025Q2ABCDEFGH12345678",
            period="2T",
            captured_at=(_PRESENTED_AT,),
        )
        read = compose_calendar_aeat_reader(operation)
        outcome = read()
        assert outcome.state.availability is HomeAvailability.AVAILABLE
        assert outcome.state.observed_at == later_capture
        assert outcome.value is not None
        assert len(outcome.value.filed_declaration_observations) == 2
        assert (
            max(artefact.captured_at for observation in (first, second) for artefact in observation.artefacts)
            == later_capture
        )
    assert read().state.observed_at == later_capture

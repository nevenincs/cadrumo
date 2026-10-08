"""Tests for bulk filed-declaration capture report models."""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator, Mapping
from contextlib import asynccontextmanager
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import cast

import pytest

from ....core.filed_history_discovery_signal import FiledHistoryDiscoverySignal
from ....core.observed_header_fact import ObservedHeaderFact
from ....core.period import Period
from ....domain.buckets.event import BucketEvent
from ....domain.calculations.registry.authority import PinnedAuthorityOperation, bundled_indexed_authority
from ....domain.calculations.registry.schema_references import RegistrySnapshotRef
from ...storage.sync_runs.records import SyncRunRecord
from ...user_profile.access_contracts import AccessDenialCode
from ...user_profile.access_errors import ProfileAccessRefusedError
from ...user_profile.automation_custody_port import AutomationCustodyCode, AutomationCustodyError
from ..errors import LiveApplicationError, LiveIvaSurfaceTimeoutError
from ..filed_data_capture import (
    FiledCaptureAccumulator,
    _absorb_declarations,
    _await_filed_register_walk,
    _walk_or_failure_row,
    capture_filed_data,
    capture_filed_data_bulk,
    capture_source_filed_data,
    filed_data_capture_failure_row,
    list_filed_data_bulk,
)
from ..filed_data_ports import (
    FiledDataCapturePort,
    FiledDataRegisterPort,
    FiledEffectGuard,
    FiledRegisterDeclarationProtocol,
)
from ..filed_history_discovery import (
    FiledHistoryDiscoveryPair,
    FiledHistoryDiscoveryReport,
    FiledHistoryOnboardingRun,
    expected_but_not_found_notice,
)
from ..filed_history_pull import _filed_history_pair_outcomes
from ..filed_observation_ports import FiledObservationArtefactProtocol, FiledObservedCasillaProtocol
from ..remote_state_models import (
    BulkFiledDataCaptureReport,
    FiledCapturePairOutcome,
    FiledDataCaptureFailureRow,
)
from ..session import SessionWriteReporter
from .filed_observation_test_support import in_memory_filed_observation_test_bundle

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]


@dataclass(frozen=True, slots=True)
class _Declaration:
    """Minimal inward register-row fake for application tests."""

    modelo: str = "303"
    ejercicio: int = 2025
    period: Period = field(default_factory=lambda: Period.from_year_and_code(2025, "1T"))
    expediente_id: str = "12345678901234567890"
    estado: str = "ALTA"
    tipo_solicitud: str | None = None
    observaciones: str | None = None
    justificante_link_text: str | None = None
    archive_link_text: str | None = None
    declaration_copy_link_text: str | None = None
    justificante_cell_index: int = 7
    archive_cell_index: int | None = 8
    declaration_copy_cell_index: int | None = None
    presented_at: datetime = datetime(2025, 4, 15, 9, 30, tzinfo=UTC)


def _declaration() -> FiledRegisterDeclarationProtocol:
    return _Declaration()


def test_revoked_filed_capture_discards_staged_bytes_before_any_local_write(tmp_path: Path) -> None:
    class Staged:
        persisted = False

        def persist_artefacts(self, sink):
            del sink
            self.persisted = True
            raise AssertionError("revoked capture reached artefact persistence")

    class Register:
        def __init__(self, staged: Staged) -> None:
            self.staged = staged

        async def capture_observation_deferred(self, declaration):
            del declaration
            return self.staged

    class DeniedGuard:
        async def __aenter__(self) -> None:
            raise ProfileAccessRefusedError(AccessDenialCode.GRANT_INACTIVE)

        async def __aexit__(self, exc_type, exc, traceback) -> bool:
            del exc_type, exc, traceback
            return False

    staged = Staged()
    bundle = in_memory_filed_observation_test_bundle()
    failures: list[FiledDataCaptureFailureRow] = []
    with bundled_indexed_authority().operation() as operation:
        accumulator = FiledCaptureAccumulator(operation=operation)
        with pytest.raises(ProfileAccessRefusedError) as refusal:
            asyncio.run(
                _absorb_declarations(
                    (_declaration(),),
                    opened_register=cast(FiledDataRegisterPort, Register(staged)),
                    accumulator=accumulator,
                    ports=bundle.ports,
                    bucket_id="11111111-1111-4111-8111-111111111111",
                    output_root=tmp_path,
                    dry_run=False,
                    modelo="303",
                    year=2025,
                    failures=failures,
                    effect_guard=DeniedGuard,
                )
            )

    assert refusal.value.reason is AccessDenialCode.GRANT_INACTIVE
    assert not staged.persisted
    assert failures == []


def test_single_capture_revocation_after_remote_fetch_discards_bytes(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The single-file route must fence artefacts before its first local write."""
    from .. import filed_data_capture as capture_module

    monkeypatch.setattr(capture_module, "require_active_bucket_id", lambda: "11111111-1111-4111-8111-111111111111")
    events: list[str] = []

    class Staged:
        def persist_artefacts(self, sink):
            del sink
            events.append("persist")
            raise AssertionError("revoked single capture persisted artefacts")

    class Register:
        walk_timeout_ms = 1000

        async def walk(self, *, modelo: str, ejercicio: int):
            assert (modelo, ejercicio) == ("303", 2025)
            return (_declaration(),)

        async def capture_observation_deferred(self, declaration):
            assert declaration == _declaration()
            events.append("remote")
            return Staged()

    class Port:
        @asynccontextmanager
        async def open_register(
            self,
            *,
            operation: str,
            authority_operation: PinnedAuthorityOperation | None = None,
            effect_guard: FiledEffectGuard | None = None,
            on_session_write: SessionWriteReporter | None = None,
        ) -> AsyncIterator[Register]:
            assert operation == "live-filed-read"
            assert effect_guard is DeniedGuard
            assert on_session_write is None
            yield Register()

    class DeniedGuard:
        async def __aenter__(self) -> None:
            events.append("guard")
            raise ProfileAccessRefusedError(AccessDenialCode.GRANT_INACTIVE)

        async def __aexit__(self, exc_type, exc, traceback) -> bool:
            del exc_type, exc, traceback
            return False

    bundle = in_memory_filed_observation_test_bundle()
    with bundled_indexed_authority().operation() as operation, pytest.raises(ProfileAccessRefusedError) as refusal:
        asyncio.run(
            capture_filed_data(
                filed_data_port=cast(FiledDataCapturePort, Port()),
                modelo="303",
                year=2025,
                output_root=tmp_path,
                ports=bundle.ports,
                effect_guard=DeniedGuard,
                operation=operation,
            )
        )
    assert refusal.value.reason is AccessDenialCode.GRANT_INACTIVE
    assert events == ["remote", "guard"]


def test_source_capture_revocation_after_remote_fetch_discards_batch(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Source capture must never persist a downloaded batch after revocation."""
    from .. import filed_data_capture as capture_module

    monkeypatch.setattr(capture_module, "require_active_bucket_id", lambda: "11111111-1111-4111-8111-111111111111")
    events: list[str] = []

    class Staged:
        def persist_artefacts(self, sink):
            del sink
            events.append("persist")
            raise AssertionError("revoked source capture persisted artefacts")

    class Port:
        async def capture_source_observations_deferred(
            self,
            revision,
            *,
            filing_year,
            period,
            operation,
            effect_guard: FiledEffectGuard | None = None,
            on_session_write: SessionWriteReporter | None = None,
        ):
            del revision
            assert (filing_year, period, operation) == (2025, Period.from_year_and_code(2025, "1T"), "live-filed-read")
            assert effect_guard is DeniedGuard
            assert on_session_write is None
            events.append("remote")
            return Staged()

    class DeniedGuard:
        async def __aenter__(self) -> None:
            events.append("guard")
            raise ProfileAccessRefusedError(AccessDenialCode.GRANT_INACTIVE)

        async def __aexit__(self, exc_type, exc, traceback) -> bool:
            del exc_type, exc, traceback
            return False

    bundle = in_memory_filed_observation_test_bundle()
    with bundled_indexed_authority().operation() as operation, pytest.raises(ProfileAccessRefusedError) as refusal:
        asyncio.run(
            capture_source_filed_data(
                filed_data_port=cast(FiledDataCapturePort, Port()),
                modelo="303",
                year=2025,
                period=Period.from_year_and_code(2025, "1T"),
                output_root=tmp_path,
                ports=bundle.ports,
                effect_guard=DeniedGuard,
                operation=operation,
            )
        )
    assert refusal.value.reason is AccessDenialCode.GRANT_INACTIVE
    assert events == ["remote", "guard"]


def test_source_capture_revocation_before_finalization_preserves_first_fence(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Calculation writes require a fresh fence after artefacts have settled."""
    from .. import filed_data_capture as capture_module

    monkeypatch.setattr(capture_module, "require_active_bucket_id", lambda: "11111111-1111-4111-8111-111111111111")
    events: list[str] = []

    class Staged:
        def persist_artefacts(self, sink):
            del sink
            events.append("artefacts")
            return ()

    class Port:
        async def capture_source_observations_deferred(
            self,
            revision,
            *,
            filing_year,
            period,
            operation,
            effect_guard: FiledEffectGuard | None = None,
            on_session_write: SessionWriteReporter | None = None,
        ):
            del revision, filing_year, period, operation
            assert effect_guard is Guard
            assert on_session_write is None
            events.append("remote")
            return Staged()

    class Guard:
        async def __aenter__(self) -> None:
            events.append("guard")
            if events.count("guard") == 2:
                raise ProfileAccessRefusedError(AccessDenialCode.GRANT_INACTIVE)

        async def __aexit__(self, exc_type, exc, traceback) -> bool:
            del exc_type, exc, traceback
            return False

    def forbidden_finalization(*args, **kwargs):
        del args, kwargs
        raise AssertionError("revoked source capture finalized calculations")

    monkeypatch.setattr(capture_module, "finalize_filed_capture", forbidden_finalization)
    bundle = in_memory_filed_observation_test_bundle()
    with bundled_indexed_authority().operation() as operation, pytest.raises(ProfileAccessRefusedError):
        asyncio.run(
            capture_source_filed_data(
                filed_data_port=cast(FiledDataCapturePort, Port()),
                modelo="303",
                year=2025,
                period=Period.from_year_and_code(2025, "1T"),
                output_root=tmp_path,
                ports=bundle.ports,
                effect_guard=Guard,
                operation=operation,
            )
        )
    assert events == ["remote", "guard", "artefacts", "guard"]


async def _slow_empty_declarations() -> tuple[FiledRegisterDeclarationProtocol, ...]:
    await asyncio.sleep(0.05)
    return ()


@pytest.mark.parametrize(
    "refusal",
    [
        ProfileAccessRefusedError(AccessDenialCode.GRANT_INACTIVE),
        AutomationCustodyError(AutomationCustodyCode.UNAVAILABLE),
    ],
)
def test_register_authority_loss_stops_pair_walk_without_a_failure_row(refusal: Exception) -> None:
    async def revoked() -> tuple[FiledRegisterDeclarationProtocol, ...]:
        raise refusal

    failures: list[FiledDataCaptureFailureRow] = []
    with pytest.raises(type(refusal)):
        asyncio.run(
            _walk_or_failure_row(
                revoked(),
                modelo="303",
                year=2025,
                timeout_ms=1000,
                failures=failures,
            )
        )
    assert failures == []


def test_bulk_failure_row_preserves_declaration_coordinates() -> None:
    row = filed_data_capture_failure_row(
        modelo="303",
        year=2025,
        declaration=_declaration(),
        error=ValueError("AEAT row did not expose a justificante link"),
    )

    assert row == FiledDataCaptureFailureRow(
        modelo="303",
        year=2025,
        period=Period.from_year_and_code(2025, "1T"),
        expediente_id="12345678901234567890",
        error_type="ValueError",
        message="AEAT row did not expose a justificante link",
    )


def test_filed_register_walk_timeout_reports_modelo_year_context() -> None:
    with pytest.raises(LiveIvaSurfaceTimeoutError) as raised:
        asyncio.run(
            _await_filed_register_walk(
                _slow_empty_declarations(),
                modelo="303",
                year=2026,
                timeout_ms=1,
            ),
        )

    assert raised.value.surface == "filed_declarations_register_walk"
    assert raised.value.timeout_ms == 1
    assert raised.value.context is not None
    assert raised.value.context["progress"] == {"modelo": "303", "year": 2026}


def test_bulk_report_counts_successes_and_failures_explicitly() -> None:
    failure = filed_data_capture_failure_row(
        modelo="130",
        year=2025,
        error=RuntimeError("modelo not offered by AEAT form"),
    )

    report = BulkFiledDataCaptureReport(
        output_root="var/aeat/filed-declarations",
        modelos=("130", "303"),
        year_from=2025,
        year_to=2025,
        captured_count=1,
        reached_count=1,
        pair_outcomes=(
            FiledCapturePairOutcome(
                modelo="130",
                year=2025,
                walk_attempted=True,
                walk_completed=False,
                row_count=0,
                reached_count=0,
                captured_count=0,
            ),
            FiledCapturePairOutcome(
                modelo="303",
                year=2025,
                walk_attempted=True,
                walk_completed=True,
                row_count=1,
                reached_count=1,
                captured_count=1,
            ),
        ),
        failed_count=1,
        observation_paths=("303/2025/1T/manifest.json",),
        artefact_refs=("sha256:abc123",),
        casilla_count=12,
        calculation_observation_count=1,
        calculation_observation_keys=("303:2025:1T",),
        failures=(failure,),
    )

    assert report.modelos == ("130", "303")
    assert report.captured_count == 1
    assert report.failed_count == 1
    assert report.failures[0].modelo == "130"
    report.require_consistent()


@pytest.mark.parametrize("dry_run", [False, True])
def test_bulk_capture_reports_registry_unsupported_modelos_as_local_boundaries(tmp_path: Path, dry_run: bool) -> None:
    report = asyncio.run(
        capture_filed_data_bulk(
            year_from=2024,
            year_to=2024,
            output_root=tmp_path,
            ports=(bundle := in_memory_filed_observation_test_bundle()).ports,
            filed_data_port=bundle.filed_data_port,
            modelos=("151", "721"),
            dry_run=dry_run,
        ),
    )

    assert report.modelos == ("151", "721")
    assert report.captured_count == 0
    assert report.dry_run is dry_run
    assert report.failed_count == 2
    failures = {failure.modelo: failure for failure in report.failures}
    assert set(failures) == {"151", "721"}
    assert failures["151"].year == 2024
    assert failures["151"].error_type == "LiveApplicationInputError"
    assert "declares no authenticated filed-declarations read surface" in failures["151"].message
    assert failures["721"].year == 2024
    assert failures["721"].error_type == "LiveApplicationInputError"
    assert "declares no authenticated filed-declarations read surface" in failures["721"].message


def test_bulk_capture_report_exposes_its_evidence_notices_channel(tmp_path: Path) -> None:
    """The report carries ``evidence_notices``, and a caller can read it off the report.

    The per-artefact evidence advisories are raised during enrolment and accumulated
    during capture; the report is what carries them out to a caller. When it did not,
    :func:`pull_filed_history` read the attribute anyway and raised ``AttributeError``
    on a path nothing in this suite executed — so the missing channel and the caller
    that wanted it were both invisible.

    Asserts the attribute READS and is the declared empty tuple, not that it holds any
    particular advisory: this scenario is refused before live contact and captures
    nothing, so an empty channel is the correct answer here and a populated expectation
    would be manufactured from a capture that never happened.
    """
    report = asyncio.run(
        capture_filed_data_bulk(
            year_from=2024,
            year_to=2024,
            output_root=tmp_path,
            ports=(bundle := in_memory_filed_observation_test_bundle()).ports,
            filed_data_port=bundle.filed_data_port,
            modelos=("151",),
        ),
    )

    assert report.evidence_notices == ()


def test_bulk_capture_accepts_limit_for_locally_bounded_unsupported_modelos(tmp_path: Path) -> None:
    report = asyncio.run(
        capture_filed_data_bulk(
            year_from=2024,
            year_to=2024,
            output_root=tmp_path,
            ports=(bundle := in_memory_filed_observation_test_bundle()).ports,
            filed_data_port=bundle.filed_data_port,
            modelos=("151",),
            limit=10,
        ),
    )

    assert report.modelos == ("151",)
    assert report.captured_count == 0
    assert report.failed_count == 1
    assert report.failures[0].modelo == "151"
    assert "declares no authenticated filed-declarations read surface" in report.failures[0].message


def test_bulk_listing_reports_registry_unsupported_modelos_as_local_boundaries() -> None:
    report = asyncio.run(
        list_filed_data_bulk(
            filed_data_port=in_memory_filed_observation_test_bundle().filed_data_port,
            year_from=2024,
            year_to=2024,
            modelos=("151", "721"),
        ),
    )

    assert report.modelos == ("151", "721")
    assert report.row_count == 0
    assert report.failed_count == 2
    failures = {failure.modelo: failure for failure in report.failures}
    assert set(failures) == {"151", "721"}
    assert failures["151"].year == 2024
    assert failures["151"].error_type == "LiveApplicationInputError"
    assert "declares no authenticated filed-declarations read surface" in failures["151"].message
    assert failures["721"].year == 2024
    assert failures["721"].error_type == "LiveApplicationInputError"
    assert "declares no authenticated filed-declarations read surface" in failures["721"].message


def test_truncated_register_read_reuses_the_per_pair_failure_taxonomy() -> None:
    """A refused short register read becomes an ordinary per-pair failure row, not a new channel.

    The bulk sweep's walk arm folds any walk exception into a
    :class:`FiledDataCaptureFailureRow` and moves to the next pair, so a
    register read that refuses because the grid declared more records than it
    rendered needs no bulk-level mechanism of its own -- it only needs to be a
    plain exception the arm already catches, mapped with its type and its
    operator-facing reason intact. Both halves are asserted here: that the
    refusal is catchable by that arm at all, and that nothing about it is lost
    on the way into the report -- the row's message is length-bounded, so a
    refusal wording that pushed its counts past the bound would arrive with the
    only actionable part cut off.
    """
    assert issubclass(LiveApplicationError, Exception), (
        "the bulk walk arm catches Exception; a refusal outside it escapes"
    )

    refusal = LiveApplicationError(
        "declaraciones register modelo 100 ejercicio 2026 rendered 3 row(s) but its pager "
        "declares 8 in total; refusing an under-reported filing history",
        context={"modelo": "100", "ejercicio": 2026, "rendered_count": 3, "declared_total": 8},
    )

    row = filed_data_capture_failure_row(modelo="100", year=2026, error=refusal)

    assert row.modelo == "100"
    assert row.year == 2026
    assert row.period is None
    assert row.expediente_id is None
    assert row.error_type == "LiveApplicationError"
    assert "rendered 3 row(s)" in row.message
    assert "declares 8 in total" in row.message
    assert "under-reported filing history" in row.message
    assert not row.message.endswith("…"), "the refusal wording overran the row's message bound and lost its tail"


async def _refusing_walk() -> tuple[FiledRegisterDeclarationProtocol, ...]:
    """A real walk coroutine that refuses the way a truncated register read does."""
    raise LiveApplicationError(
        "declaraciones register modelo 100 ejercicio 2026 rendered 3 row(s) but its pager "
        "declares 8 in total; refusing an under-reported filing history",
        context={"modelo": "100", "ejercicio": 2026, "rendered_count": 3, "declared_total": 8},
    )


async def _one_declaration_walk() -> tuple[FiledRegisterDeclarationProtocol, ...]:
    """A real walk coroutine that succeeds, standing for a healthy pair."""
    return (_declaration(),)


def test_walk_failure_is_absorbed_into_a_row_and_signals_the_pair_be_skipped() -> None:
    """A refusing walk yields no rows and one failure row; a healthy walk is untouched.

    This covers the PER-PAIR arm only: the failure becomes a typed row and the
    helper returns None so its caller skips that pair. Cross-pair continuation --
    that the sweep goes on to the next pair -- lives in the bulk functions behind
    the live-session gate and is NOT proven here.

    Both coroutines are real: one raises the genuine refusal a truncated register
    read produces, the other returns a real inward register-row fake. Nothing is stubbed and
    no production path is patched.
    """
    failures: list[FiledDataCaptureFailureRow] = []

    refused = asyncio.run(
        _walk_or_failure_row(
            _refusing_walk(),
            modelo="100",
            year=2026,
            timeout_ms=5_000,
            failures=failures,
        ),
    )

    assert refused is None, "an absorbed failure must signal the pair be skipped rather than yield rows"
    assert len(failures) == 1
    assert failures[0].error_type == "LiveApplicationError"
    assert "declares 8 in total" in failures[0].message

    healthy = asyncio.run(
        _walk_or_failure_row(
            _one_declaration_walk(),
            modelo="303",
            year=2025,
            timeout_ms=5_000,
            failures=failures,
        ),
    )

    assert healthy == (_declaration(),), "a healthy walk must return its rows unchanged"
    assert len(failures) == 1, "a healthy walk must not add a failure row"


@dataclass(frozen=True, slots=True)
class _AccountingObservation:
    """Synthetic declaration observations consumed by the real persistence funnel."""

    modelo: str
    ejercicio: int
    period: Period
    expediente_id: str
    presented_at: datetime
    status: str = "ALTA"
    authenticated_identity: str = "X1234567L"
    artefacts: tuple[FiledObservationArtefactProtocol, ...] = ()
    casillas: tuple[FiledObservedCasillaProtocol, ...] = ()
    headers: tuple[ObservedHeaderFact, ...] = ()
    metadata: Mapping[str, str] = field(default_factory=dict)

    @property
    def registry_snapshot_ref(self) -> RegistrySnapshotRef:
        """Identify the existing annual Modelo 100 fixture revision."""
        return RegistrySnapshotRef(
            modelo=self.modelo,
            revision_id=str(self.ejercicio),
            modelo_year=self.ejercicio,
            period=self.period.registry_token,
        )


class _AccountingRegister:
    """Control only register rows and remote capture failures for actual orchestration."""

    walk_timeout_ms = 1000

    def __init__(
        self,
        rows: Mapping[tuple[str, int], tuple[_Declaration, ...]],
        *,
        fail_walk: bool = False,
        fail_capture: str | None = None,
    ) -> None:
        self.rows = rows
        self.fail_walk = fail_walk
        self.fail_capture = fail_capture
        self.walks: list[tuple[str, int]] = []
        self.captures: list[str] = []
        self.opened = 0

    async def walk(self, *, modelo: str, ejercicio: int) -> tuple[_Declaration, ...]:
        """Return independent full register counts before the use case applies a cap."""
        self.walks.append((modelo, ejercicio))
        if self.fail_walk:
            raise RuntimeError("synthetic register walk refusal")
        return self.rows.get((modelo, ejercicio), ())

    async def capture_observation(
        self, declaration: FiledRegisterDeclarationProtocol, *, artefact_sink=None
    ) -> _AccountingObservation:
        """Return captured facts or a deterministic remote acquisition failure."""
        self.captures.append(declaration.expediente_id)
        if declaration.expediente_id == self.fail_capture:
            raise RuntimeError("synthetic declaration capture failure")
        return _AccountingObservation(
            modelo=declaration.modelo,
            ejercicio=declaration.ejercicio,
            period=declaration.period,
            expediente_id=declaration.expediente_id,
            presented_at=declaration.presented_at,
        )

    @asynccontextmanager
    async def open_register(self, **_kwargs: object) -> AsyncIterator[_AccountingRegister]:
        """Supply one explicit synthetic acquisition session, without authentication or network."""
        self.opened += 1
        yield self


class _AccountingRunRepository:
    """Retain provenance written by the actual bulk finalizer."""

    def __init__(self) -> None:
        self.records: list[SyncRunRecord] = []
        self.events: list[BucketEvent] = []

    def save_with_bucket_event(self, record: SyncRunRecord, event: BucketEvent) -> None:
        """Accept the writer's exact record and event together."""
        self.records.append(record)
        self.events.append(event)


def _annual_declaration(year: int, suffix: str) -> _Declaration:
    """Create distinct real rows for one annual filed period."""
    return _Declaration(
        modelo="100",
        ejercicio=year,
        period=Period.from_year_and_code(year, "0A"),
        expediente_id="1234567890123456789" + suffix,
    )


@pytest.mark.parametrize("dry_run", [False, True], ids=["persisted", "preview"])
def test_bulk_pair_accounting_distinguishes_preview_rows_and_unattempted_cap(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, dry_run: bool
) -> None:
    """The cap cannot turn present or unwalked filings into proven remote emptiness."""
    from .. import filed_data_capture as capture_module

    monkeypatch.setattr(capture_module, "require_active_bucket_id", lambda: "11111111-1111-4111-8111-111111111111")
    register = _AccountingRegister({("100", 2025): (_annual_declaration(2025, "1"), _annual_declaration(2025, "2"))})
    repository = _AccountingRunRepository()
    bundle = in_memory_filed_observation_test_bundle()
    report = asyncio.run(
        capture_filed_data_bulk(
            filed_data_port=cast(FiledDataCapturePort, register),
            ports=bundle.ports,
            year_from=2024,
            year_to=2025,
            modelos=("100",),
            output_root=tmp_path,
            limit=1,
            dry_run=dry_run,
            sync_run_repository=repository,
        )
    )
    report.require_consistent()
    assert register.walks == [("100", 2025)]
    assert register.captures == ["12345678901234567891"]
    assert [(pair.modelo, pair.year) for pair in report.pair_outcomes] == [("100", 2025), ("100", 2024)]
    first, capped = report.pair_outcomes
    assert first.walk_attempted and first.walk_completed
    assert (first.row_count, first.reached_count, first.captured_count) == (2, 1, 0 if dry_run else 1)
    assert not capped.walk_attempted and not capped.walk_completed
    assert (capped.row_count, capped.reached_count, capped.captured_count) == (0, 0, 0)
    assert report.reached_count == 1
    assert report.captured_count == (0 if dry_run else 1)
    assert len(repository.records) == (0 if dry_run else 1)
    assert report.calculation_observation_count == (0 if dry_run else 1)
    discovery = FiledHistoryDiscoveryReport(
        pairs=(
            FiledHistoryDiscoveryPair(
                modelo="100", ejercicio=2025, signals=(FiledHistoryDiscoverySignal.PROFILE_APPLICABILITY,)
            ),
            FiledHistoryDiscoveryPair(
                modelo="100", ejercicio=2024, signals=(FiledHistoryDiscoverySignal.PROFILE_APPLICABILITY,)
            ),
        )
    )
    pairs = _filed_history_pair_outcomes(discovery, report)
    run = FiledHistoryOnboardingRun(
        pairs=pairs, dry_run=dry_run, reached_count=report.reached_count, captured_count=report.captured_count
    )
    assert [pair.row_count for pair in pairs] == [2, 0]
    assert [pair.walk_completed for pair in pairs] == [True, False]
    assert run.genuinely_empty_pairs == ()
    assert expected_but_not_found_notice(run) is None


@pytest.mark.parametrize("failed_capture", [False, True], ids=["same-period", "remote-failure"])
def test_bulk_pair_accounting_preserves_same_period_and_failed_capture_counts(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, failed_capture: bool
) -> None:
    """Independent row and capture facts survive latest-per-period calculation selection."""
    from .. import filed_data_capture as capture_module

    monkeypatch.setattr(capture_module, "require_active_bucket_id", lambda: "11111111-1111-4111-8111-111111111111")
    register = _AccountingRegister(
        {("100", 2025): (_annual_declaration(2025, "1"), _annual_declaration(2025, "2"))},
        fail_capture="12345678901234567892" if failed_capture else None,
    )
    repository = _AccountingRunRepository()
    bundle = in_memory_filed_observation_test_bundle()
    report = asyncio.run(
        capture_filed_data_bulk(
            filed_data_port=cast(FiledDataCapturePort, register),
            ports=bundle.ports,
            year_from=2025,
            year_to=2025,
            modelos=("100",),
            output_root=tmp_path,
            sync_run_repository=repository,
        )
    )
    report.require_consistent()
    (pair,) = report.pair_outcomes
    assert pair.walk_attempted and pair.walk_completed
    assert pair.row_count == 2
    assert pair.reached_count == pair.captured_count == (1 if failed_capture else 2)
    assert report.calculation_observation_keys == ("100:2025:0A",)
    assert report.calculation_observation_count == 1
    assert len(report.observation_paths) == (1 if failed_capture else 2)
    assert len(register.captures) == 2
    assert report.failed_count == (1 if failed_capture else 0)
    if failed_capture:
        assert report.failures[0].expediente_id == "12345678901234567892"
    assert len(repository.records) == 1
    assert repository.records[0].unit_count == report.reached_count
    discovery = FiledHistoryDiscoveryReport(
        pairs=(
            FiledHistoryDiscoveryPair(
                modelo="100", ejercicio=2025, signals=(FiledHistoryDiscoverySignal.PROFILE_APPLICABILITY,)
            ),
        )
    )
    (history_pair,) = _filed_history_pair_outcomes(discovery, report)
    assert history_pair.row_count == 2
    assert history_pair.captured_count == (1 if failed_capture else 2)
    assert history_pair.reached_count == report.reached_count
    assert not history_pair.is_a_genuine_empty


def test_bulk_pair_accounting_keeps_planning_refusals_and_failed_walks_distinct(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A locally refused pair and a contacted unreadable pair retain their actual walk facts."""
    from .. import filed_data_capture as capture_module

    monkeypatch.setattr(capture_module, "require_active_bucket_id", lambda: "11111111-1111-4111-8111-111111111111")
    register = _AccountingRegister({}, fail_walk=True)
    report = asyncio.run(
        capture_filed_data_bulk(
            filed_data_port=cast(FiledDataCapturePort, register),
            ports=in_memory_filed_observation_test_bundle().ports,
            year_from=2025,
            year_to=2025,
            modelos=("151", "100"),
            output_root=tmp_path,
            dry_run=True,
        )
    )
    report.require_consistent()
    local, remote = report.pair_outcomes
    assert (local.modelo, remote.modelo) == ("151", "100")
    assert not local.walk_attempted and not local.walk_completed
    assert remote.walk_attempted and not remote.walk_completed
    assert [(pair.row_count, pair.reached_count, pair.captured_count) for pair in report.pair_outcomes] == [
        (0, 0, 0)
    ] * 2
    assert register.walks == [("100", 2025)]
    assert report.failed_count == 2


def test_bulk_capture_refuses_duplicate_coordinates_before_register_contact(tmp_path: Path) -> None:
    """Repeated caller coordinates must be refused rather than overwritten in the accounting join."""
    register = _AccountingRegister({})
    with pytest.raises(ValueError, match="unique modelo/year"):
        asyncio.run(
            capture_filed_data_bulk(
                filed_data_port=cast(FiledDataCapturePort, register),
                ports=in_memory_filed_observation_test_bundle().ports,
                year_from=2025,
                year_to=2025,
                modelos=("100", "100"),
                output_root=tmp_path,
                dry_run=True,
            )
        )
    assert register.opened == 0
    assert register.walks == []

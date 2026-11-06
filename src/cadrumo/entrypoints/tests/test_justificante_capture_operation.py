"""Registered, guarded contracts for live justificante capture."""

from __future__ import annotations

import asyncio
import hashlib
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from types import SimpleNamespace
from typing import Any, cast
from uuid import UUID

import pytest

from cadrumo_client.contracts.access_vocabulary import AccessAction

from ...adapters.persistence.operations.journal import OperationJournalRepository
from ...adapters.persistence.operations.secure_references import (
    OperationSecureReferenceRepository,
)
from ...adapters.persistence.storage.tests.secure_sql import isolated_runtime_profile
from ...application.live import justificante as justificante_module
from ...application.live.justificante import (
    JustificanteAuthenticity,
    JustificanteCaptureSnapshot,
    JustificanteCaptureSnapshotNotFoundError,
    JustificanteCaptureSnapshotRepository,
    JustificanteCaptureSnapshotService,
)
from ...application.live.justificante_capture_operation import (
    JUSTIFICANTE_CAPTURE_DEFINITION_ID,
    JustificanteCapturePorts,
    JustificanteCapturePublicResultV1,
    JustificanteCaptureRequest,
    build_justificante_capture_definition,
    build_justificante_capture_registration,
)
from ...application.live.justificante_ports import (
    CapturedJustificante,
    JustificanteDeclaration,
    JustificanteRegistrationPorts,
)
from ...application.modelo.filing_chain_reconciliation import (
    AeatRegisterEntry,
    FilingReconciliationOutcome,
    FilingReconciliationResult,
)
from ...application.operations.access_resolution import resolve_operation_access
from ...application.operations.capabilities import OperationOwnedResource
from ...application.operations.frontend_requests import (
    OperationResultProjectionRequestV1,
    OperationResultProjectionSuccessV1,
)
from ...application.operations.models import OperationRequest
from ...application.operations.persistence.journal import OperationPersistedSnapshot
from ...application.operations.projection_services import OperationResultProjectionService
from ...application.operations.registry import OperationRegistry
from ...core.operations import (
    OperationEffect,
    OperationFrontendProjection,
    OperationLifecycle,
    OperationTerminalCondition,
    profile_operation_subject,
)
from ...core.period import Period
from ...domain.calculations.registry.authority import PinnedAuthorityOperation, bundled_indexed_authority
from ...domain.justificante.schema import Justificante
from ...tests.aeat_literal_fixtures import (
    CSV_CONSULTATION_URL_FIXTURE,
)
from .capture_stand_in_support import FencedExecutionAuthority, ObservableBrowserResources
from .supervised_operation_rig import build_supervised_operation, operation_access_context, run_to_terminal

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint]

_NOW = datetime(2026, 9, 29, 12, tzinfo=UTC)
_MODELO = "130"
_YEAR = 2026
_PERIOD = Period.from_year_and_code(_YEAR, "1T")
_EXPEDIENTE = "202613000010001A"
_CSV = "ABCD1234EFGH5678"
_TAX_ID = "X0001500M"
_FILING_RECORD_ID = "6" * 64
_PDF = b"%PDF-1.4\nsynthetic AEAT receipt\n%%EOF"
_PDF_SHA256 = hashlib.sha256(_PDF).hexdigest()


class _SnapshotPersistence:
    def __init__(self, *, bucket_id: str, events: list[str], authority: FencedExecutionAuthority) -> None:
        self.bucket_id = bucket_id
        self.events = events
        self.authority = authority
        self.snapshots: dict[str, JustificanteCaptureSnapshot] = {}

    def exists(self, snapshot_id: str) -> bool:
        return snapshot_id in self.snapshots

    def load(self, snapshot_id: str) -> JustificanteCaptureSnapshot:
        return self.snapshots[snapshot_id]

    def list_snapshots(self) -> tuple[JustificanteCaptureSnapshot, ...]:
        return tuple(self.snapshots.values())

    def resolve(self, snapshot_id: str) -> JustificanteCaptureSnapshot:
        matches = tuple(
            snapshot for key, snapshot in self.snapshots.items() if key == snapshot_id or key.startswith(snapshot_id)
        )
        if not matches:
            raise JustificanteCaptureSnapshotNotFoundError(
                translated_message="application.live.justificante.errors.snapshot_not_found",
                context={"snapshot_id": snapshot_id},
            )
        if len(matches) != 1:
            raise JustificanteCaptureSnapshotNotFoundError(
                translated_message="application.live.justificante.errors.snapshot_prefix_ambiguous",
                context={"snapshot_id": snapshot_id, "match_count": len(matches)},
            )
        return matches[0]

    def save(self, snapshot: object) -> None:
        assert isinstance(snapshot, JustificanteCaptureSnapshot)
        assert self.authority.guard_depth == 1, "snapshot writes require a fresh COMMIT guard"
        stage = (
            "snapshot-save" if snapshot.authenticity is JustificanteAuthenticity.NOT_CHECKED else "authenticity-save"
        )
        self.events.append(stage)
        self.snapshots[str(snapshot.snapshot_id)] = snapshot


class _ReadPort:
    def __init__(
        self,
        events: list[str],
        *,
        resources: ObservableBrowserResources,
        authority: FencedExecutionAuthority,
    ) -> None:
        self.events = events
        self.resources = resources
        self.authority = authority

    async def declarations(
        self,
        *,
        modelo: str,
        year: int,
        **_kwargs: object,
    ) -> Sequence[JustificanteDeclaration]:
        assert self.resources.active
        assert (modelo, year) == (_MODELO, _YEAR)
        self.events.append("declarations-and-expedientes-read")
        declaration = JustificanteDeclaration(
            modelo=_MODELO,
            period=_PERIOD,
            expediente_id=_EXPEDIENTE,
            estado="ALTA",
            presented_at=_NOW,
        )
        return (declaration,)

    async def capture(self, *, expediente_id: str) -> CapturedJustificante:
        assert self.resources.active
        assert self.authority.guard_depth == 0, "AEAT bytes must be fetched before the local COMMIT fence"
        assert expediente_id == _EXPEDIENTE
        self.events.append("remote-pdf-fetch")
        return CapturedJustificante(
            expediente_id=_EXPEDIENTE,
            csv=_CSV,
            pdf_bytes=_PDF,
            pdf_sha256=_PDF_SHA256,
        )


class _Verifier:
    def __init__(self, events: list[str], *, resources: ObservableBrowserResources) -> None:
        self.events = events
        self.resources = resources

    async def verify(self, csv: str, *, browser: object | None = None, browser_session_factory: object = None) -> bool:
        assert self.resources.active
        assert csv == _CSV
        assert browser is None and browser_session_factory is None
        self.events.append("csv-verification")
        return True


class _Metadata:
    def __init__(self, events: list[str], authority: FencedExecutionAuthority) -> None:
        self.events = events
        self.authority = authority
        self.saved: list[Justificante] = []

    def save(self, payload: Justificante) -> None:
        assert self.authority.guard_depth == 1, "receipt metadata writes require a fresh COMMIT guard"
        self.events.append("metadata-save")
        self.saved.append(payload)


class _Filing:
    def __init__(self, events: list[str], authority: FencedExecutionAuthority, *, bucket_id: str) -> None:
        self.events = events
        self.authority = authority
        self.bucket_id = bucket_id
        self.current = SimpleNamespace(
            bucket_id=bucket_id,
            modelo=_MODELO,
            filing_year=_YEAR,
            period=_PERIOD,
            member_nif=_TAX_ID,
            filing_record_id=_FILING_RECORD_ID,
            external_evidence=None,
        )
        self.settled = SimpleNamespace(filing_record_id=_FILING_RECORD_ID, aeat_accepted=True)

    def load(self) -> SimpleNamespace:
        self.events.append("filing-load")

        def current_for(*, bucket_id: str, modelo: str, filing_year: int, period: Period, **_kwargs: object):
            assert (bucket_id, modelo, filing_year, period) == (self.bucket_id, _MODELO, _YEAR, _PERIOD)
            return self.current

        return SimpleNamespace(
            current_for=current_for,
            get=lambda filing_record_id: self.settled if filing_record_id == _FILING_RECORD_ID else None,
        )


class _FilingReconciliation:
    def __init__(
        self,
        events: list[str],
        authority: FencedExecutionAuthority,
        pinned_authority: PinnedAuthorityOperation,
        *,
        bucket_id: str,
    ) -> None:
        self.events = events
        self.authority = authority
        self.pinned_authority = pinned_authority
        self.bucket_id = bucket_id

    def reconcile(
        self,
        entry: AeatRegisterEntry,
        *,
        actor: str,
        clock: datetime,
        authority_operation: PinnedAuthorityOperation | None = None,
    ) -> FilingReconciliationResult:
        assert self.authority.guard_depth == 1, "filing reconciliation writes require a fresh COMMIT guard"
        assert actor == "aeat-live-capture"
        assert clock.tzinfo is not None
        assert authority_operation is self.pinned_authority
        assert entry.bucket_id == self.bucket_id
        assert entry.modelo == _MODELO
        assert entry.filing_year == _YEAR
        assert entry.period == _PERIOD
        assert entry.register.csv == _CSV
        self.events.append("filing-reconcile")
        return FilingReconciliationResult(
            outcome=FilingReconciliationOutcome.CONFIRMED,
            bucket_id=self.bucket_id,
            modelo=_MODELO,
            filing_year=_YEAR,
            period=_PERIOD,
            member_nif=_TAX_ID,
            filing_record_id=_FILING_RECORD_ID,
        )


def _parsed_receipt() -> Justificante:
    return Justificante(
        csv=_CSV,
        modelo=_MODELO,
        ejercicio=str(_YEAR),
        period=_PERIOD,
        presented_at=datetime(2026, 4, 18, 9, 0),
        tax_id=_TAX_ID,
        verification_url=CSV_CONSULTATION_URL_FIXTURE,
        source_pdf_path=Path("synthetic-justificante.pdf"),
        source_pdf_sha256=_PDF_SHA256,
        parsed_at=_NOW,
    )


@dataclass(frozen=True)
class _Capture:
    """What one supervised justificante capture left behind, for outcome assertions."""

    bucket_id: str
    terminal: OperationPersistedSnapshot
    submitted_id: str
    events: list[str]
    writes: list[str]
    execution_authority: FencedExecutionAuthority
    composition_calls: list[tuple[str, PinnedAuthorityOperation]]
    authority: PinnedAuthorityOperation
    metadata: _Metadata
    journal: OperationJournalRepository
    registry: OperationRegistry
    operands: OperationSecureReferenceRepository


def _assert_each_write_runs_inside_its_guard(capture: _Capture) -> None:
    events, writes, execution_authority = capture.events, capture.writes, capture.execution_authority
    # Four fresh local-write fences protect capture, authenticity,
    # metadata, and filing evidence. The supervisor also fences its
    # final encrypted result operand, which is a separate fifth guard.
    assert execution_authority.guard_calls == 5
    write_positions = [index for index, event in enumerate(events) if event in writes]
    for guard_number, write_position in enumerate(write_positions[:3], start=1):
        assert events.index(f"commit-guard-enter:{guard_number}") < write_position
        assert write_position < events.index(f"commit-guard-exit:{guard_number}")
    metadata_filing_guard = 4
    assert events.index(f"commit-guard-enter:{metadata_filing_guard}") < write_positions[3]
    assert write_positions[3] < write_positions[4]
    assert write_positions[4] < events.index(f"commit-guard-exit:{metadata_filing_guard}")


def _assert_safe_projection(capture: _Capture) -> None:
    bucket_id, submitted_id, terminal = capture.bucket_id, capture.submitted_id, capture.terminal
    metadata, journal, registry, operands = capture.metadata, capture.journal, capture.registry, capture.operands
    result_service = OperationResultProjectionService(reader=journal, registry=registry, operands=operands)
    contract = registry.lookup_public_contract(JUSTIFICANTE_CAPTURE_DEFINITION_ID)
    assert contract.result_schema is not None
    projection_result = asyncio.run(
        result_service.resolve(
            OperationResultProjectionRequestV1(
                operation_id=submitted_id,
                terminal_revision=terminal.revision,
                definition_contract_digest=contract.definition_contract_digest,
                result_schema=contract.result_schema,
            ),
            JustificanteCapturePublicResultV1,
        )
    )
    assert isinstance(projection_result, OperationResultProjectionSuccessV1)
    projection = projection_result.projection
    assert isinstance(projection, JustificanteCapturePublicResultV1)
    assert projection.bucket_id == bucket_id
    assert projection.modelo == _MODELO
    assert projection.filing_year == _YEAR
    assert projection.period == _PERIOD.registry_token
    assert projection.expediente_id == _EXPEDIENTE
    assert projection.csv == _CSV
    assert projection.pdf_sha256 == _PDF_SHA256
    assert projection.justificante_metadata_registered
    assert projection.filing_evidence_stamped
    assert projection.filing_record_id == _FILING_RECORD_ID
    assert set(projection.model_dump()) == {
        "bucket_id",
        "snapshot_id",
        "modelo",
        "filing_year",
        "period",
        "expediente_id",
        "csv",
        "pdf_sha256",
        "source_kind",
        "state",
        "captured_at",
        "justificante_metadata_registered",
        "calendar_evidence_available",
        "modelo_filing_record_required",
        "filing_evidence_stamped",
        "filing_record_id",
    }
    assert "pdf_base64" not in projection.model_dump()
    assert "pdf_bytes" not in projection.model_dump()
    assert len(metadata.saved) == 2


def _assert_succeeded_capture(capture: _Capture) -> None:
    terminal, writes = capture.terminal, capture.writes
    composition_calls, authority = capture.composition_calls, capture.authority
    assert terminal.terminal_condition is OperationTerminalCondition.SUCCEEDED
    assert terminal.effect is OperationEffect.UPDATED
    assert terminal.terminal_receipt is not None
    assert terminal.terminal_receipt.effect is OperationEffect.UPDATED
    assert writes == [
        "snapshot-save",
        "authenticity-save",
        "metadata-save",
        "metadata-save",
        "filing-reconcile",
    ]
    _assert_each_write_runs_inside_its_guard(capture)
    assert composition_calls[0][1] is authority

    _assert_safe_projection(capture)


def _assert_refused_capture(capture: _Capture) -> None:
    terminal, events, writes = capture.terminal, capture.events, capture.writes
    execution_authority, metadata = capture.execution_authority, capture.metadata
    assert terminal.terminal_condition is OperationTerminalCondition.REFUSED
    assert terminal.effect is OperationEffect.UNKNOWN
    assert terminal.terminal_receipt is not None
    assert terminal.terminal_receipt.effect is OperationEffect.UNKNOWN
    assert terminal.terminal_receipt.result_ref is None
    assert execution_authority.guard_calls == 4
    assert writes == ["snapshot-save", "authenticity-save", "metadata-save"]
    assert "commit-guard-refused:4" in events
    assert "filing-reconcile" not in events
    assert len(metadata.saved) == 1


@pytest.mark.parametrize("refuse_guard", [None, 4], ids=["all-writes-commit", "late-commit-refused"])
def test_registered_capture_supervises_guarded_writes_and_projects_only_safe_receipt_fields(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    refuse_guard: int | None,
) -> None:
    """Use the actual operation owner and encrypted operand path with synthetic AEAT ports."""
    with isolated_runtime_profile(tmp_path=tmp_path) as profile, bundled_indexed_authority().operation() as authority:
        profile_id = UUID(profile.bucket_id)
        events: list[str] = []
        execution_authority = FencedExecutionAuthority(events, refuse_guard=refuse_guard)
        persistence = _SnapshotPersistence(
            bucket_id=profile.bucket_id,
            events=events,
            authority=execution_authority,
        )
        service = JustificanteCaptureSnapshotService(
            bucket_id=profile.bucket_id,
            repository=JustificanteCaptureSnapshotRepository(persistence=persistence),
        )
        resources = ObservableBrowserResources(events)
        read_port = _ReadPort(events, resources=resources, authority=execution_authority)
        metadata = _Metadata(events, execution_authority)
        filing = _Filing(events, execution_authority, bucket_id=profile.bucket_id)
        reconciliation = _FilingReconciliation(
            events,
            execution_authority,
            authority,
            bucket_id=profile.bucket_id,
        )
        registration_ports = JustificanteRegistrationPorts(
            parse_pdf=lambda body: _parsed_receipt() if body == _PDF else pytest.fail("parser received unexpected PDF"),
            metadata=cast(Any, metadata),
            filing=cast(Any, filing),
            filing_reconciliation=cast(Any, reconciliation),
        )
        ports = JustificanteCapturePorts(
            service=service,
            read_port=cast(Any, read_port),
            registration_ports=registration_ports,
            verifier=cast(Any, _Verifier(events, resources=resources)),
        )

        composition_calls: list[tuple[str, PinnedAuthorityOperation]] = []

        def composition_factory(bucket_id: str, pinned_authority: PinnedAuthorityOperation) -> JustificanteCapturePorts:
            composition_calls.append((bucket_id, pinned_authority))
            events.append("composition-built")
            return ports

        def provider_preflight(profile_arg: UUID, pinned_authority: PinnedAuthorityOperation) -> None:
            assert profile_arg == profile_id
            assert pinned_authority is authority
            events.append("provider-preflight")

        monkeypatch.setattr(justificante_module, "now", lambda: _NOW)

        definition = build_justificante_capture_definition(
            composition_factory=composition_factory,
            browser_resources_factory=lambda: resources,
            provider_preflight=provider_preflight,
        )
        assert OperationOwnedResource.PROCESS in definition.capabilities.owned_resources
        registration = build_justificante_capture_registration(definition)
        registry = OperationRegistry(definitions=(definition,), public_registrations=(registration,))
        request = OperationRequest(
            definition_id=JUSTIFICANTE_CAPTURE_DEFINITION_ID,
            subject_ref=profile_operation_subject(profile.bucket_id),
            payload=JustificanteCaptureRequest(
                profile_id=profile_id,
                modelo=_MODELO,
                year=_YEAR,
                period=_PERIOD.registry_token,
            ),
        )
        admitted = resolve_operation_access(
            registry=registry,
            request=request,
            context=operation_access_context(
                registration.contract,
                profile_id=profile_id,
                frontend=OperationFrontendProjection.EXTERNAL_CLIENT,
                authority_operation=authority,
            ),
        )
        assert admitted.request.profile_id == profile_id
        assert AccessAction.COMMIT in admitted.policy.actions

        journal, _, operands, supervisor, _ = build_supervised_operation(
            tmp_path=tmp_path,
            objects=profile.repository,
            authority=authority,
            registry=registry,
            now=_NOW,
            execution_authority=execution_authority,
        )
        operation_id = "3" * 64 if refuse_guard is None else "4" * 64
        submitted_id = asyncio.run(supervisor.submit(request, operation_id=operation_id))
        terminal = asyncio.run(run_to_terminal(supervisor, submitted_id))

        assert terminal.lifecycle is OperationLifecycle.TERMINAL
        assert composition_calls == [(profile.bucket_id, authority)]
        assert events.index("remote-pdf-fetch") < events.index("commit-guard-enter:1")
        assert events.index("browser-deactivate") < events.index("browser-close")
        assert resources.closed and resources.close_calls == 1

        writes = [
            event
            for event in events
            if event
            in {
                "snapshot-save",
                "authenticity-save",
                "metadata-save",
                "filing-reconcile",
            }
        ]
        capture = _Capture(
            bucket_id=profile.bucket_id,
            terminal=terminal,
            submitted_id=submitted_id,
            events=events,
            writes=writes,
            execution_authority=execution_authority,
            composition_calls=composition_calls,
            authority=authority,
            metadata=metadata,
            journal=journal,
            registry=registry,
            operands=operands,
        )
        if refuse_guard is None:
            _assert_succeeded_capture(capture)
        else:
            _assert_refused_capture(capture)

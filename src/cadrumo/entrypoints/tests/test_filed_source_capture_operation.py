"""Conformance proof for recorded source-dependency filed capture."""

from __future__ import annotations

import asyncio
from collections.abc import AsyncGenerator, Callable
from contextlib import AbstractAsyncContextManager, asynccontextmanager
from dataclasses import dataclass, replace
from datetime import UTC, datetime
from hashlib import sha256
from pathlib import Path
from typing import cast
from uuid import UUID

import pytest
from pydantic import AnyHttpUrl, TypeAdapter

from cadrumo.adapters.outbound.aeat.sede.schema import (
    FiledDeclaracionArtefact,
    FiledDeclaracionObservation,
    ObservedCasillaValue,
)
from cadrumo.adapters.persistence.storage.tests.secure_sql import isolated_runtime_profile
from cadrumo.application.calculations.observations_repository import ObservationEnvelopePayload
from cadrumo.application.live.filed_data_ports import (
    DeferredFiledObservations,
    FiledArtefactSink,
    FiledDataCapturePort,
    FiledDataRegisterPort,
    FiledEffectGuard,
)
from cadrumo.application.live.filed_history_operation import FiledHistoryComposition
from cadrumo.application.live.filed_observation_ports import (
    FiledObservationArtefactProtocol,
    FiledObservationPersistencePorts,
    FiledObservationProtocol,
)
from cadrumo.application.live.filed_source_capture_operation import (
    FILED_SOURCE_CAPTURE_DEFINITION_ID,
    FiledSourceCapturePublicResultV1,
    FiledSourceCaptureRequest,
    build_filed_source_capture_definition,
    build_filed_source_capture_registration,
)
from cadrumo.application.live.remote_state_models import SourceFiledDataCaptureReport
from cadrumo.application.live.session import SessionWriteReporter
from cadrumo.application.live.tests.filed_observation_test_support import in_memory_filed_observation_test_bundle
from cadrumo.application.modelo.filing_chain_reconciliation import (
    AeatRegisterEntry,
    FilingReconciliationNotice,
    FilingReconciliationNoticeCode,
    FilingReconciliationOutcome,
    FilingReconciliationResult,
)
from cadrumo.application.operations.access_resolution import resolve_operation_access
from cadrumo.application.operations.frontend_requests import (
    OperationResultProjectionSuccessV1,
)
from cadrumo.application.operations.models import OperationRequest
from cadrumo.application.operations.registry import OperationRegistry
from cadrumo.core.casilla_value_kind import CasillaValueKind
from cadrumo.core.operations import (
    OperationEffect,
    OperationLifecycle,
    OperationTerminalCondition,
    profile_operation_subject,
)
from cadrumo.core.period import Period
from cadrumo.domain.calculations.registry.authority import PinnedAuthorityOperation, bundled_indexed_authority
from cadrumo.domain.calculations.registry.schema import ModeloRevision
from cadrumo.domain.justificante.schema import Justificante
from cadrumo_client.contracts.access_vocabulary import AccessAction

from ...domain.calculations.registry.tests.authored_editions import filing_year_envelope, newest_authored_edition
from .supervised_operation_rig import (
    ProcessResourceScope,
    assert_foreign_profile_refused,
    build_supervised_operation,
    cli_submit_context,
    settle_and_project,
)

pytestmark = [pytest.mark.integration, pytest.mark.hex_application]

_YEAR = filing_year_envelope().horizon
_FILING_YEAR = newest_authored_edition("100")

_NOW = datetime(_YEAR, 8, 24, 20, tzinfo=UTC)
_TARGET_PERIOD = Period.from_year_and_code(_YEAR, "1T")
_SOURCE_PERIOD = Period.from_year_and_code(_FILING_YEAR, "0A")
_SOURCE_EXPEDIENTE_ID = "202510013522222A"
_SUBMITTED_BODY = b"synthetic source declaration"
_JUSTIFICANTE_BODY = b"synthetic source justificante"
_JUSTIFICANTE_CSV = "ABCD1234"
_TAX_ID = "12345678Z"


class _SyntheticSourceBatch:
    """Hold source bytes until the supervisor-provided local write fence."""

    def __init__(self, observation: FiledDeclaracionObservation, *, is_guarded: Callable[[], bool]) -> None:
        self._observation = observation
        self._is_guarded = is_guarded

    def persist_artefacts(self, sink: FiledArtefactSink) -> tuple[FiledObservationProtocol, ...]:
        assert self._is_guarded(), "source bytes reached local persistence outside the operation fence"
        bodies = {
            "submitted_file": _SUBMITTED_BODY,
            "justificante_pdf": _JUSTIFICANTE_BODY,
        }
        stored_artefacts: list[FiledDeclaracionArtefact] = []
        observation_key = (
            self._observation.modelo,
            self._observation.ejercicio,
            self._observation.period,
            self._observation.expediente_id,
        )
        for artefact in self._observation.artefacts:
            stored = sink(observation_key, artefact, bodies[artefact.kind])
            stored_artefacts.append(artefact.model_copy(update={"storage_ref": stored.storage_ref}))
        return (self._observation.model_copy(update={"artefacts": tuple(stored_artefacts)}),)


class _SyntheticSourcePort:
    """Return one synthetic dependency observation without opening a Sede session."""

    def __init__(
        self,
        batch: _SyntheticSourceBatch,
        *,
        is_guarded: Callable[[], bool],
    ) -> None:
        self._batch = batch
        self._is_guarded = is_guarded
        self.acquired: list[tuple[str, int, Period, str]] = []

    async def capture_source_observations_deferred(
        self,
        revision: ModeloRevision,
        *,
        filing_year: int,
        period: Period,
        operation: str,
        effect_guard: FiledEffectGuard | None = None,
        on_session_write: SessionWriteReporter | None = None,
    ) -> DeferredFiledObservations:
        assert not self._is_guarded(), "source acquisition must finish before local writes"
        assert effect_guard is not None and on_session_write is not None
        assert revision.id
        assert (filing_year, period, operation) == (_YEAR, _TARGET_PERIOD, "live-filed-read")
        self.acquired.append(("130", filing_year, period, operation))
        return self._batch

    async def capture_source_observations(self, *args: object, **kwargs: object):
        del args, kwargs
        raise AssertionError("the recorded source operation must defer local artefact persistence")

    def open_register(self, *, operation: str, **_kwargs: object) -> AbstractAsyncContextManager[FiledDataRegisterPort]:
        del operation
        raise AssertionError("source capture must use the registry dependency port")

    async def discover_availability(self, *, operation: str, **_kwargs: object):
        del operation
        raise AssertionError("source capture must not discover register options")


class _SyntheticReceiptParser:
    def __init__(self, receipt: Justificante) -> None:
        self._receipt = receipt

    def parse_justificante(self, body: bytes) -> Justificante:
        assert body == _JUSTIFICANTE_BODY
        return self._receipt

    def csv_from_source_url(self, source_url: str) -> str:
        assert f"CSV={_JUSTIFICANTE_CSV}" in source_url
        return _JUSTIFICANTE_CSV


class _SyntheticReconciliation:
    def __init__(self, *, is_guarded: Callable[[], bool]) -> None:
        self._is_guarded = is_guarded
        self.entries: list[AeatRegisterEntry] = []

    def reconcile(
        self,
        entry: AeatRegisterEntry,
        *,
        actor: str,
        clock: datetime,
        authority_operation: PinnedAuthorityOperation | None = None,
    ) -> FilingReconciliationResult:
        assert self._is_guarded(), "filing-chain enrollment must use the operation write fence"
        assert actor == "aeat-filed-history"
        assert clock == _NOW
        assert entry.modelo == "100"
        assert entry.filing_year == _FILING_YEAR
        assert entry.period == _SOURCE_PERIOD
        assert entry.register.csv == _JUSTIFICANTE_CSV
        assert entry.casilla_values is None
        self.entries.append(entry)
        return FilingReconciliationResult(
            outcome=FilingReconciliationOutcome.UNVERIFIABLE,
            bucket_id=entry.bucket_id,
            modelo=entry.modelo,
            filing_year=entry.filing_year,
            period=entry.period,
            member_nif=None,
            filing_record_id=None,
            notices=(
                FilingReconciliationNotice(
                    code=FilingReconciliationNoticeCode.CONTENT_UNAVAILABLE,
                    context={"source": "synthetic"},
                ),
            ),
        )


@dataclass(frozen=True, slots=True)
class _Composition:
    ports: FiledObservationPersistencePorts
    filed_data_port: FiledDataCapturePort


def _assert_source_capture_collaborators(
    provider_preflights,
    profile_id,
    authority,
    filed_port,
    reconciliation_port,
    guard_entries,
    guarded_writes,
    resources,
):
    assert provider_preflights == [(profile_id, authority)]
    assert filed_port.acquired == [("130", _YEAR, _TARGET_PERIOD, "live-filed-read")]
    assert len(reconciliation_port.entries) == 1
    assert guard_entries == 2
    assert guarded_writes == ["artefact", "artefact", "manifest", "calculation"]
    assert resources.closed


def _assert_source_capture_result(definition, terminal, projected, tmp_path):
    assert definition.definition_id == "live.filed-capture.source"
    assert terminal.lifecycle is OperationLifecycle.TERMINAL
    assert terminal.terminal_condition is OperationTerminalCondition.SUCCEEDED
    assert terminal.effect is OperationEffect.UPDATED
    assert isinstance(projected, OperationResultProjectionSuccessV1)
    assert isinstance(projected.projection, FiledSourceCapturePublicResultV1)
    result = projected.projection
    assert result.output_root == str(tmp_path / "filed-source-output")
    assert (result.target_modelo, result.target_year, result.target_period) == ("130", _YEAR, "1T")
    assert (result.captured_count, result.reached_count) == (1, 1)
    assert result.observation_paths == (str(Path("memory-observations") / "1" / "manifest.json"),)
    assert result.artefact_refs == ("memory-artefact:1", "memory-artefact:2")
    assert result.casilla_count == 1
    assert result.calculation_observation_count == 1
    assert result.calculation_observation_keys == (f"100:{_FILING_YEAR}:0A",)
    assert result.justificante_metadata_count == 1
    assert result.justificante_csvs == (_JUSTIFICANTE_CSV,)
    assert result.filing_evidence_stamped_count == 0
    assert result.filing_evidence_conflict_count == 0
    assert result.evidence_notices == ()
    return result


def _assert_period_independent_commit_admission(admitted):
    assert admitted.request.period_independent
    assert admitted.request.periods == frozenset()
    assert admitted.policy.requires_all_periods
    assert AccessAction.COMMIT in admitted.policy.actions


def _synthetic_source_observation(source_snapshot):
    observation = FiledDeclaracionObservation(
        modelo="100",
        ejercicio=_FILING_YEAR,
        period=_SOURCE_PERIOD,
        expediente_id=_SOURCE_EXPEDIENTE_ID,
        status="ALTA",
        presented_at=_NOW,
        authenticated_identity=_TAX_ID,
        artefacts=(
            FiledDeclaracionArtefact(
                kind="submitted_file",
                source_url="https://test.invalid/declared-file",
                content_type="application/octet-stream",
                byte_count=len(_SUBMITTED_BODY),
                sha256=sha256(_SUBMITTED_BODY).hexdigest(),
                captured_at=_NOW,
            ),
            FiledDeclaracionArtefact(
                kind="justificante_pdf",
                source_url=f"https://test.invalid/cotejo?CSV={_JUSTIFICANTE_CSV}",
                content_type="application/pdf",
                byte_count=len(_JUSTIFICANTE_BODY),
                sha256=sha256(_JUSTIFICANTE_BODY).hexdigest(),
                captured_at=_NOW,
            ),
        ),
        casillas=(
            ObservedCasillaValue(
                casilla_id="synthetic.text",
                value="synthetic-source-value",
                value_kind=CasillaValueKind.TEXT,
                source_artefact_kind="submitted_file",
                source_locator="synthetic:1",
                confidence=1.0,
            ),
        ),
        registry_snapshot_ref=source_snapshot.snapshot_ref,
    )
    return observation


def _synthetic_source_receipt():
    receipt = Justificante(
        csv=_JUSTIFICANTE_CSV,
        modelo="100",
        ejercicio=str(_FILING_YEAR),
        period=_SOURCE_PERIOD,
        presented_at=_NOW.replace(tzinfo=None),
        tax_id=_TAX_ID,
        verification_url=TypeAdapter(AnyHttpUrl).validate_python("https://test.invalid/verificar"),
        source_pdf_path=Path(f"justificantes/source-100-{_FILING_YEAR}.pdf"),
        source_pdf_sha256=sha256(_JUSTIFICANTE_BODY).hexdigest(),
        parsed_at=_NOW,
    )
    return receipt


def _assert_source_capture_reconciliation(result, profile):
    assert len(result.reconciliations) == 1
    public_reconciliation = result.reconciliations[0]
    assert public_reconciliation.outcome == FilingReconciliationOutcome.UNVERIFIABLE.value
    assert (
        public_reconciliation.bucket_id,
        public_reconciliation.modelo,
        public_reconciliation.filing_year,
    ) == (
        profile.bucket_id,
        "100",
        _FILING_YEAR,
    )
    assert public_reconciliation.period == "0A"
    assert public_reconciliation.notices[0].code == FilingReconciliationNoticeCode.CONTENT_UNAVAILABLE.value
    assert public_reconciliation.notices[0].context == (("source", "synthetic"),)


def test_supervisor_binds_source_capture_to_exact_profile_and_projects_reconciliation(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A real supervisor records source evidence and projects its safe reconciliation tally."""
    with isolated_runtime_profile(tmp_path=tmp_path) as profile, bundled_indexed_authority().operation() as authority:
        profile_id = UUID(profile.bucket_id)
        source_snapshot = authority.snapshot("100", filing_year=_FILING_YEAR, period="0A")
        observation = _synthetic_source_observation(source_snapshot)
        guard_depth = 0
        guard_entries = 0
        guarded_writes: list[str] = []

        def is_guarded() -> bool:
            return guard_depth > 0

        bundle = in_memory_filed_observation_test_bundle()
        receipt = _synthetic_source_receipt()
        reconciliation_port = _SyntheticReconciliation(is_guarded=is_guarded)
        ports = replace(
            bundle.ports,
            parser=_SyntheticReceiptParser(receipt),
            filing_reconciliation=reconciliation_port,
        )
        batch = _SyntheticSourceBatch(observation, is_guarded=is_guarded)
        filed_port = _SyntheticSourcePort(batch, is_guarded=is_guarded)
        resources = ProcessResourceScope()

        observation_persistence = ports.observation_persistence
        persist_artefact = observation_persistence.persist_artefact
        persist_observation = observation_persistence.persist_observation

        def guarded_persist_artefact(
            _self: object,
            observation_key: tuple[str, int, Period, str],
            artefact: FiledObservationArtefactProtocol,
            body: bytes,
        ) -> FiledObservationArtefactProtocol:
            assert is_guarded()
            guarded_writes.append("artefact")
            return persist_artefact(observation_key, artefact, body)

        def guarded_persist_observation(_self: object, observed: FiledObservationProtocol) -> Path:
            assert is_guarded()
            guarded_writes.append("manifest")
            return persist_observation(observed)

        monkeypatch.setattr(type(observation_persistence), "persist_artefact", guarded_persist_artefact)
        monkeypatch.setattr(type(observation_persistence), "persist_observation", guarded_persist_observation)

        calculation_repository = ports.calculation_repository
        save_calculation_observation = calculation_repository.save

        def guarded_save_calculation_observation(_self: object, payload: ObservationEnvelopePayload) -> None:
            assert is_guarded()
            guarded_writes.append("calculation")
            save_calculation_observation(payload)

        monkeypatch.setattr(type(calculation_repository), "save", guarded_save_calculation_observation)

        from cadrumo.application.live import filed_source_capture_operation as operation_module

        capture_sources = operation_module.capture_source_filed_data
        guard_entries = 0

        async def capture_sources_with_tracked_guard(
            *,
            filed_data_port: FiledDataCapturePort,
            modelo: str,
            year: int,
            period: Period,
            output_root: Path,
            ports: FiledObservationPersistencePorts,
            effect_guard: FiledEffectGuard | None = None,
            on_session_write: SessionWriteReporter | None = None,
            operation: PinnedAuthorityOperation | None = None,
        ) -> SourceFiledDataCaptureReport:
            assert effect_guard is not None
            assert on_session_write is not None

            @asynccontextmanager
            async def tracked_guard() -> AsyncGenerator[None]:
                nonlocal guard_depth, guard_entries
                async with effect_guard():
                    guard_depth += 1
                    guard_entries += 1
                    try:
                        yield
                    finally:
                        guard_depth -= 1

            return await capture_sources(
                filed_data_port=filed_data_port,
                modelo=modelo,
                year=year,
                period=period,
                output_root=output_root,
                ports=ports,
                effect_guard=tracked_guard,
                on_session_write=on_session_write,
                operation=operation,
            )

        monkeypatch.setattr(operation_module, "capture_source_filed_data", capture_sources_with_tracked_guard)

        composition = _Composition(ports=ports, filed_data_port=cast(FiledDataCapturePort, filed_port))
        provider_preflights: list[tuple[UUID, PinnedAuthorityOperation]] = []

        def provider_preflight(profile: UUID, pinned_authority: PinnedAuthorityOperation) -> None:
            provider_preflights.append((profile, pinned_authority))

        def composition_factory(output_root: Path, *, operation: PinnedAuthorityOperation) -> FiledHistoryComposition:
            return cast(FiledHistoryComposition, composition)

        definition = build_filed_source_capture_definition(
            composition_factory=composition_factory,
            browser_resources_factory=lambda: resources,
            provider_preflight=provider_preflight,
        )
        registration = build_filed_source_capture_registration(definition)
        registry = OperationRegistry(definitions=(definition,), public_registrations=(registration,))
        request = OperationRequest(
            definition_id=FILED_SOURCE_CAPTURE_DEFINITION_ID,
            subject_ref=profile_operation_subject(profile.bucket_id),
            payload=FiledSourceCaptureRequest(
                profile_id=profile_id,
                output_root=tmp_path / "filed-source-output",
                modelo="130",
                year=_YEAR,
                period="1T",
            ),
        )

        access_context = cli_submit_context(profile_id=profile_id, contract=registration.contract)
        admitted = resolve_operation_access(registry=registry, request=request, context=access_context)
        _assert_period_independent_commit_admission(admitted)
        assert_foreign_profile_refused(registry=registry, request=request, context=access_context)

        _, _, _, supervisor, result_service = build_supervised_operation(
            tmp_path=tmp_path, objects=profile.repository, authority=authority, registry=registry, now=_NOW
        )

        terminal, projected = asyncio.run(
            settle_and_project(
                supervisor,
                result_service,
                registry,
                request,
                FiledSourceCapturePublicResultV1,
            )
        )

    result = _assert_source_capture_result(definition, terminal, projected, tmp_path)
    _assert_source_capture_reconciliation(result, profile)
    _assert_source_capture_collaborators(
        provider_preflights,
        profile_id,
        authority,
        filed_port,
        reconciliation_port,
        guard_entries,
        guarded_writes,
        resources,
    )

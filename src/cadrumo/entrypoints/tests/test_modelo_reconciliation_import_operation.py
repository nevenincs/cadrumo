"""Registered execution coverage for profile-bound reconciliation persistence."""

from __future__ import annotations

import asyncio
import shutil
from collections.abc import AsyncGenerator, Callable
from contextlib import asynccontextmanager
from functools import partial
from pathlib import Path
from typing import TYPE_CHECKING, cast, override
from uuid import UUID, uuid4

import pytest
from pydantic import BaseModel

from ...adapters.persistence.profile.buckets import BucketEventHistoryRepository
from ...adapters.persistence.profile.modelo_reconciliation import ModeloReconciliationPersistence
from ...application.modelo.reconciliation import ReconciliationEvidenceInvalidError
from ...application.modelo.reconciliation_import_operation import (
    MODELO_RECONCILIATION_IMPORT_OPERATION_DEFINITION_ID,
    HandleVerifiedEvidenceParser,
    ModeloReconciliationImportProjection,
    ModeloReconciliationImportRequest,
)
from ...application.modelo.reconciliation_parsing import (
    ReconciliationDeclaracionObservation,
    ReconciliationEvidenceParserPort,
    reconciliation_evidence_parser,
)
from ...application.modelo.reconciliation_records import (
    ModeloReconciliationEvidenceKind,
    ModeloReconciliationRecord,
)
from ...application.operations.models import OperationIdentity, OperationRequest
from ...application.user_profile.access_contracts import AccessAction
from ...core.config import override_settings
from ...core.errors.error_codes import ErrorCategory, get_registered_error_code
from ...core.operations import OperationEffect, OperationTerminalCondition, profile_operation_subject
from ...domain.buckets.event import BucketEvent
from ...domain.calculations.registry.authority import PinnedAuthorityOperation
from ...domain.calculations.registry.governed_fact_scope import validating_governed_facts
from . import modelo_operation_test_support
from . import test_registered_executor_conformance as conformance

if TYPE_CHECKING:
    from ...domain.calculations.registry.schema import RegistrySnapshot
    from ...domain.justificante.schema import Justificante

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint]

_JUSTIFICANTE_FIXTURE = (
    Path(__file__).resolve().parents[2] / "tests" / "fixtures" / "justificantes" / "130" / "2024-1T.pdf"
)


class _CommitWitness:
    """Observe exact operation identity and its guarded persistence boundary."""

    def __init__(self, definition_id: str = MODELO_RECONCILIATION_IMPORT_OPERATION_DEFINITION_ID) -> None:
        self.definition_id = definition_id
        self.profile_id: UUID | None = None
        self.active = False
        self.active_operation_id: str | None = None
        self.events: list[tuple[str, str]] = []
        self.checked_actions: list[AccessAction] = []

    def _assert_exact_identity(self, identity: OperationIdentity) -> None:
        assert self.profile_id is not None
        assert identity.definition_id == self.definition_id
        assert identity.subject_ref == profile_operation_subject(str(self.profile_id))

    async def require[Payload: BaseModel](
        self,
        *,
        identity: OperationIdentity,
        request: OperationRequest[Payload],
        action: AccessAction,
    ) -> None:
        self._assert_exact_identity(identity)
        assert request.definition_id == self.definition_id
        assert request.subject_ref == identity.subject_ref
        assert getattr(request.payload, "profile_id", None) == self.profile_id
        self.checked_actions.append(action)

    @asynccontextmanager
    async def commit_guard(self, identity: OperationIdentity) -> AsyncGenerator[None]:
        self._assert_exact_identity(identity)
        assert not self.active
        self.active = True
        self.active_operation_id = identity.operation_id
        self.events.append(("commit-enter", identity.operation_id))
        try:
            yield
        finally:
            self.events.append(("commit-exit", identity.operation_id))
            self.active_operation_id = None
            self.active = False


def test_registered_import_checks_exact_profile_and_guards_atomic_persistence(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    operation: PinnedAuthorityOperation,
) -> None:
    """The real registered executor refuses retargeting and settles its write as UPDATED."""
    witness = _CommitWitness()
    original_compose = conformance.compose_operation_services
    monkeypatch.setattr(
        conformance,
        "compose_operation_services",
        partial(original_compose, execution_authority=witness),
    )

    original_persist = ModeloReconciliationPersistence.persist_with_event

    def guarded_persist(
        persistence: ModeloReconciliationPersistence,
        record: ModeloReconciliationRecord,
        event: BucketEvent,
    ) -> None:
        assert witness.active
        assert witness.active_operation_id is not None
        assert record.bucket_id == str(witness.profile_id)
        assert record.bucket_event_id == event.event_id
        witness.events.append(("atomic-persist", event.event_id))
        original_persist(persistence, record, event)

    monkeypatch.setattr(ModeloReconciliationPersistence, "persist_with_event", guarded_persist)

    with conformance._runtime(tmp_path / "modelo-reconciliation-import", cleanup=conformance._CloseWitness()) as (
        driver,
        registry,
        profile_id,
    ):
        witness.profile_id = profile_id
        subject_ref = profile_operation_subject(str(profile_id))
        with override_settings(cadrumo_active_profile=str(profile_id)):
            work_unit = modelo_operation_test_support.seeded_modelo_work_unit(profile_id, operation=operation)
            records_before = tuple(ModeloReconciliationPersistence().iter_records())
            events_before = BucketEventHistoryRepository().load().events

        request = ModeloReconciliationImportRequest(
            profile_id=profile_id,
            work_unit_id=work_unit.work_unit_id,
            source_kind=ModeloReconciliationEvidenceKind.JUSTIFICANTE,
            source_path=str(
                Path(__file__).resolve().parents[2] / "tests" / "fixtures" / "justificantes" / "130" / "2024-1T.pdf"
            ),
            actor=modelo_operation_test_support.MODELO_OPERATION_TEST_ACTOR,
        )

        other_profile_id = uuid4()
        with override_settings(cadrumo_active_profile=str(other_profile_id)):
            refused_submission, refused_observation = asyncio.run(
                driver.run(
                    definition_id=MODELO_RECONCILIATION_IMPORT_OPERATION_DEFINITION_ID,
                    subject_ref=subject_ref,
                    payload=request,
                )
            )
        refused_snapshot = asyncio.run(
            driver.services.submission.supervisor.inspect(refused_submission.receipt.operation_id)
        )
        refused_receipt = refused_snapshot.terminal_receipt
        assert refused_receipt is not None
        assert refused_receipt.identity.subject_ref == subject_ref
        assert refused_receipt.condition is OperationTerminalCondition.REFUSED
        assert refused_receipt.effect is OperationEffect.NONE
        assert refused_receipt.result_ref is None
        assert refused_observation.projection.terminal_condition is OperationTerminalCondition.REFUSED
        assert witness.events == []

        with override_settings(cadrumo_active_profile=str(profile_id)):
            submission, observation = asyncio.run(
                driver.run(
                    definition_id=MODELO_RECONCILIATION_IMPORT_OPERATION_DEFINITION_ID,
                    subject_ref=subject_ref,
                    payload=request,
                )
            )
            terminal_snapshot = asyncio.run(
                driver.services.submission.supervisor.inspect(submission.receipt.operation_id)
            )
            records_after = tuple(ModeloReconciliationPersistence().iter_records())
            events_after = BucketEventHistoryRepository().load().events

        receipt = terminal_snapshot.terminal_receipt
        assert receipt is not None
        assert receipt.identity.definition_id == MODELO_RECONCILIATION_IMPORT_OPERATION_DEFINITION_ID
        assert receipt.identity.subject_ref == subject_ref
        assert receipt.condition is OperationTerminalCondition.SUCCEEDED
        assert receipt.effect is OperationEffect.UPDATED
        assert receipt.result_ref is not None
        assert observation.projection.terminal_condition is OperationTerminalCondition.SUCCEEDED
        assert observation.projection.effect is OperationEffect.UPDATED

        projection = conformance._resolve_result_projection(
            driver,
            registry,
            definition_id=MODELO_RECONCILIATION_IMPORT_OPERATION_DEFINITION_ID,
            operation_id=submission.receipt.operation_id,
            terminal_revision=observation.projection.revision,
            projection_type=ModeloReconciliationImportProjection,
        )
        assert isinstance(projection, ModeloReconciliationImportProjection)
        assert projection.bucket_id == str(profile_id)
        assert projection.work_unit_id == work_unit.work_unit_id
        assert projection.source_path == request.source_path

        assert records_after[: len(records_before)] == records_before
        assert len(records_after) == len(records_before) + 1
        persisted = records_after[-1]
        assert persisted.bucket_id == str(profile_id)
        assert persisted.work_unit_id == work_unit.work_unit_id
        assert persisted.bucket_event_id in events_after
        assert set(events_before).issubset(events_after)
        assert witness.checked_actions.count(AccessAction.START) >= 2
        assert witness.events[:3] == [
            ("commit-enter", submission.receipt.operation_id),
            ("atomic-persist", persisted.bucket_event_id),
            ("commit-exit", submission.receipt.operation_id),
        ]
        assert not witness.active


def test_registered_import_refuses_a_relative_source_that_the_working_directory_would_resolve(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    operation: PinnedAuthorityOperation,
) -> None:
    """A readable file reached only through the worker's own directory is refused, and nothing is written."""
    working_directory = tmp_path / "working-directory"
    working_directory.mkdir()
    shutil.copyfile(_JUSTIFICANTE_FIXTURE, working_directory / "evidence.pdf")

    with conformance._runtime(tmp_path / "modelo-reconciliation-relative", cleanup=conformance._CloseWitness()) as (
        driver,
        _registry,
        profile_id,
    ):
        with override_settings(cadrumo_active_profile=str(profile_id)):
            work_unit = modelo_operation_test_support.seeded_modelo_work_unit(profile_id, operation=operation)
            records_before = tuple(ModeloReconciliationPersistence().iter_records())
            request = ModeloReconciliationImportRequest(
                profile_id=profile_id,
                work_unit_id=work_unit.work_unit_id,
                source_kind=ModeloReconciliationEvidenceKind.JUSTIFICANTE,
                source_path="evidence.pdf",
                actor=modelo_operation_test_support.MODELO_OPERATION_TEST_ACTOR,
            )
            monkeypatch.chdir(working_directory)
            assert Path(request.source_path).is_file()

            _submitted, observed = asyncio.run(
                driver.run(
                    definition_id=MODELO_RECONCILIATION_IMPORT_OPERATION_DEFINITION_ID,
                    subject_ref=profile_operation_subject(str(profile_id)),
                    payload=request,
                )
            )
            records_after = tuple(ModeloReconciliationPersistence().iter_records())

        assert observed.projection.terminal_condition is OperationTerminalCondition.REFUSED
        assert observed.projection.refusal_ref == "REFUSED_RECONCILIATION_EVIDENCE_INVALID"
        assert observed.projection.effect is OperationEffect.NONE
        assert records_after == records_before


class _FileChangingParser(ReconciliationEvidenceParserPort):
    """A path parser during whose parse the named file is, or is not, rewritten.

    It stands in for whatever else can write to the file while a real parser
    reads it; the guard under test is the wrapper around it.
    """

    def __init__(self, during_parse: Callable[[Path], object]) -> None:
        self._during_parse = during_parse
        self.parsed: list[Path] = []
        self.observation = cast(ReconciliationDeclaracionObservation, object())

    @override
    def parse_justificante(self, source: Path) -> Justificante:
        raise AssertionError("a justificante is parsed from its verified bytes, never from its path")

    @override
    def parse_justificante_bytes(self, source: bytes) -> Justificante:
        raise AssertionError("this parser is asked for a declaración only")

    @override
    def parse_declaracion(
        self, source: Path, *, modelo: str, filing_year: int, period: str
    ) -> ReconciliationDeclaracionObservation:
        del modelo, filing_year, period
        self.parsed.append(source)
        self._during_parse(source)
        return self.observation

    @override
    def parse_declaracion_bytes(
        self, source: bytes, *, modelo: str, filing_year: int, period: str, registry_snapshot: RegistrySnapshot
    ) -> ReconciliationDeclaracionObservation:
        raise AssertionError("this parser is asked for a declaración path only")


def _refusal_reason(error: ReconciliationEvidenceInvalidError) -> str:
    """Return the reason of a refusal that is registered as one and names no path."""
    registered = get_registered_error_code(error)
    assert registered.category is ErrorCategory.REFUSED
    assert registered.code == "REFUSED_RECONCILIATION_EVIDENCE_INVALID"
    assert error.context is not None
    assert set(error.context) == {"reason"}
    return str(error.context["reason"])


def test_a_justificante_is_parsed_from_the_bytes_of_its_verified_handle(
    tmp_path: Path, operation: PinnedAuthorityOperation
) -> None:
    source = tmp_path / "justificante.pdf"
    shutil.copyfile(_JUSTIFICANTE_FIXTURE, source)
    composed = reconciliation_evidence_parser()

    # The executor parses inside the pinned generation's governed-fact scope; so does this.
    with validating_governed_facts(operation):
        verified = HandleVerifiedEvidenceParser(composed).parse_justificante(source)
        expected = composed.parse_justificante_bytes(_JUSTIFICANTE_FIXTURE.read_bytes())

    assert (verified.modelo, verified.ejercicio, verified.period, verified.tax_id) == (
        expected.modelo,
        expected.ejercicio,
        expected.period,
        expected.tax_id,
    )


def test_a_source_the_guard_does_not_accept_never_reaches_a_parser(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    source = tmp_path / "justificante.pdf"
    shutil.copyfile(_JUSTIFICANTE_FIXTURE, source)
    monkeypatch.chdir(tmp_path)
    parser = _FileChangingParser(lambda _source: None)
    refused: dict[Path, tuple[str, int]] = {
        Path("justificante.pdf"): ("relative_path", source.stat().st_size),
        tmp_path / "nested" / ".." / "justificante.pdf": ("parent_traversal", source.stat().st_size),
        tmp_path: ("not_a_regular_file", source.stat().st_size),
        tmp_path / "absent.pdf": ("not_found", source.stat().st_size),
        source: ("too_large", source.stat().st_size - 1),
    }

    for path, (reason, ceiling) in refused.items():
        guarded = HandleVerifiedEvidenceParser(parser, max_bytes=ceiling)
        with pytest.raises(ReconciliationEvidenceInvalidError) as justificante_refusal:
            guarded.parse_justificante(path)
        with pytest.raises(ReconciliationEvidenceInvalidError) as declaracion_refusal:
            guarded.parse_declaracion(path, modelo="130", filing_year=2024, period="1T")

        assert _refusal_reason(justificante_refusal.value) == reason
        assert _refusal_reason(declaracion_refusal.value) == reason
    assert parser.parsed == []


def test_a_declaracion_rewritten_while_it_is_parsed_is_refused(tmp_path: Path) -> None:
    source = tmp_path / "declaracion.pdf"
    source.write_bytes(b"%PDF-synthetic declaration as first read")
    rewriting = _FileChangingParser(lambda path: path.write_bytes(b"%PDF-synthetic declaration swapped in"))
    steady = _FileChangingParser(lambda _path: None)

    with pytest.raises(ReconciliationEvidenceInvalidError) as refusal:
        HandleVerifiedEvidenceParser(rewriting).parse_declaracion(source, modelo="130", filing_year=2024, period="1T")
    source.write_bytes(b"%PDF-synthetic declaration left alone")
    observation = HandleVerifiedEvidenceParser(steady).parse_declaracion(
        source, modelo="130", filing_year=2024, period="1T"
    )

    assert _refusal_reason(refusal.value) == "changed_while_read"
    assert rewriting.parsed == [source]
    assert observation is steady.observation
    assert steady.parsed == [source]

"""Encrypted ledger review continuity with a local subprocess reader.

The storage fixture supplies synthetic custody material. These cases exercise
the real classifier parser, executor, response broker, journal, and CAS writer;
they do not establish native login, credential custody, or model availability.
"""

from __future__ import annotations

import asyncio
import json
import sys
from collections.abc import Callable, Generator
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from pathlib import Path
from typing import Literal, NoReturn, override
from uuid import UUID

import pytest
from pydantic import ValidationError

from cadrumo.adapters.outbound.llm.tests.subprocess_classifier_support import SubprocessLLMClassifier
from cadrumo.adapters.persistence.operations.journal import OperationJournalRepository
from cadrumo.adapters.persistence.operations.lease import OperationLeaseFilesystemRepository
from cadrumo.adapters.persistence.operations.secure_references import operation_secure_reference_repository
from cadrumo.adapters.persistence.profile.tests.ledger_action_create_support import ledger_ports_for_test
from cadrumo.adapters.persistence.profile.transactions import TransactionCatalogueRepository
from cadrumo.adapters.persistence.storage.sql.secure_objects import SecureObjectRepository
from cadrumo.adapters.persistence.storage.tests.secure_sql import isolated_runtime_profile, read_db_at_rest_bytes
from cadrumo.application.ledger.actions_manual import update_manual_transaction_fields
from cadrumo.application.ledger.evidence_textlayer_ports import EvidenceTextLayerPorts
from cadrumo.application.ledger.llm_classification_ports import LLMClassificationPorts
from cadrumo.application.ledger.llm_review_contracts import (
    LEDGER_CLASSIFY_REVIEW_DEFINITION_ID,
    LedgerLlmReviewProjection,
    LedgerLlmReviewRequest,
    ledger_llm_review_subject,
)
from cadrumo.application.ledger.llm_review_execution import LedgerLlmOperationPorts, LedgerLlmReviewExecutor
from cadrumo.application.ledger.llm_review_operand import LedgerLlmReviewedOperand
from cadrumo.application.ledger.llm_review_operation import (
    build_ledger_llm_review_definition,
    build_ledger_llm_review_registration,
)
from cadrumo.application.ledger.llm_review_results import LedgerLlmOperationResult
from cadrumo.application.ledger.llm_review_workflow import LlmReviewInvocationOrigin
from cadrumo.application.ledger.models import ManualLedgerTransactionPatch
from cadrumo.application.ledger.view_operation import (
    LEDGER_VIEW_OPERATION_DEFINITION_ID,
    LedgerViewProjection,
    LedgerViewRequest,
    build_ledger_view_definition,
    build_ledger_view_registration,
)
from cadrumo.application.operations.composition import (
    OperationComposedServices,
    OperationSubmission,
    compose_operation_services,
)
from cadrumo.application.operations.errors import OperationSubjectBusyError
from cadrumo.application.operations.frontend_projection import OperationReviewProjectionReferenceV1
from cadrumo.application.operations.frontend_requests import (
    OperationCancellationRefusalCode,
    OperationCancellationRefusalV1,
    OperationCancellationRequestV1,
    OperationCancellationSuccessV1,
    OperationObservationRequestV1,
    OperationObservationSuccessV1,
    OperationResponseApplyRequestV1,
    OperationResponseControlRefusalV1,
    OperationResponseControlRequestV1,
    OperationResponseControlSuccessV1,
    OperationResponseMutationSuccessV1,
    OperationResultProjectionRequestV1,
    OperationResultProjectionSuccessV1,
    OperationReviewProjectionRequestV1,
    OperationReviewProjectionSuccessV1,
)
from cadrumo.application.operations.models import OperationRequest
from cadrumo.application.operations.operation_definition import OperationExecutorFactory
from cadrumo.application.operations.owner import OperationExecutorContext, OperationResumeCheckpoint
from cadrumo.application.operations.persistence.journal import OperationPersistedSnapshot, serialize_operation_operand
from cadrumo.application.operations.registry import OperationRegistry
from cadrumo.core.config import load_settings
from cadrumo.core.errors.error_codes import get_registered_error_code
from cadrumo.core.hashing import sha256_hex
from cadrumo.core.model_catalogue import ModelRole
from cadrumo.core.operations import (
    OperationEffect,
    OperationLifecycle,
    OperationTerminalCondition,
    profile_operation_subject,
)
from cadrumo.domain.calculations.registry.authority import PinnedAuthorityOperation
from cadrumo.domain.calculations.registry.governed_fact_scope import validating_governed_facts
from cadrumo.domain.transactions.enums import BusinessClassification, TransactionDirection
from cadrumo.domain.transactions.errors import TransactionIdPrefixError
from cadrumo.domain.transactions.llm import PromptSpec
from cadrumo.domain.transactions.models import Transaction, TransactionCatalogue
from cadrumo.domain.transactions.raw_transaction import RawProvenance, RawTransaction, SourceFormat

from .supervision_support import run_to_settlement

pytestmark = [pytest.mark.integration, pytest.mark.hex_persistence_adapter]

_PROFILE = "71111111-1111-4111-8111-111111111117"
_NOW = datetime(2026, 5, 4, tzinfo=UTC)
_REASON = "recorded local classification for encrypted continuation"


def _unused_reader(*_args: object, **_kwargs: object) -> NoReturn:
    raise AssertionError("the no-evidence review must not acquire evidence or vision")


def _run_reader(_role: ModelRole, run: Callable[[], object]) -> object:
    return run()


def _record_reader(run: Callable[[], object], _provider: str) -> object:
    return run()


def _movement(provider_id: str, amount: str, *, row: int) -> Transaction:
    return Transaction.model_validate(
        {
            "raw": RawTransaction(
                provider_transaction_id=provider_id,
                booked_date=date(2026, 5, 1),
                amount=Decimal(amount),
                currency="EUR",
                description="synthetic private baseline",
                provenance=RawProvenance(
                    source_path=Path("synthetic-review.csv"),
                    source_sha256="c" * 64,
                    source_row_index=row,
                    source_format=SourceFormat.CSV,
                    ingested_at=_NOW,
                    provider_name="csv",
                ),
                raw_fields={},
            ),
            "direction": TransactionDirection.OUTGOING,
            "group_label": None,
            "source_jurisdiction": "ES",
        }
    )


class _ResumeBarrier:
    """Pause scheduling before delegating the unchanged production resume body."""

    def __init__(self) -> None:
        self.enabled = False
        self.entered = asyncio.Event()
        self.release = asyncio.Event()


class _ScheduledExecutor(LedgerLlmReviewExecutor):
    def __init__(self, ports: LedgerLlmOperationPorts, barrier: _ResumeBarrier) -> None:
        self.barrier = barrier

        def factory(*, bucket_id: str, operation: PinnedAuthorityOperation) -> LedgerLlmOperationPorts:
            assert bucket_id == _PROFILE and operation is ports.ledger.operation
            return ports

        super().__init__(factory)

    @override
    async def resume(
        self,
        request: OperationRequest[LedgerLlmReviewRequest],
        checkpoint: OperationResumeCheckpoint,
        context: OperationExecutorContext,
    ) -> str | None:
        if self.barrier.enabled:
            self.barrier.entered.set()
            await self.barrier.release.wait()
        return await super().resume(request, checkpoint, context)


@dataclass
class _Case:
    root: Path
    database: Path
    objects: SecureObjectRepository
    registry: OperationRegistry
    ports: LedgerLlmOperationPorts
    baseline: Transaction
    other: Transaction
    barrier: _ResumeBarrier
    acquisitions: list[PromptSpec]

    def services(self, *, recovery: bool = False) -> OperationComposedServices:
        journal = OperationJournalRepository(storage_root=self.root)
        return compose_operation_services(
            registry=self.registry,
            authority_operation=self.ports.ledger.operation,
            journal=journal,
            reader=journal,
            event_stream=journal,
            leases=OperationLeaseFilesystemRepository(storage_root=self.root),
            operands=operation_secure_reference_repository(objects=self.objects),
            owner_id=("4" if recovery else "1") * 64,
            lease_token_factory=lambda: ("5" if recovery else "2") * 64,
            clock=lambda: _NOW + (timedelta(minutes=2) if recovery else timedelta()),
            lease_duration=timedelta(minutes=1),
            execution_timeout=timedelta(minutes=5),
            cleanup_timeout=timedelta(minutes=1),
        )

    def request(self, movement: Transaction | None = None) -> OperationRequest[LedgerLlmReviewRequest]:
        payload = LedgerLlmReviewRequest(
            profile_id=UUID(_PROFILE),
            transaction_id=(movement or self.baseline).transaction_id,
            mode="classification",
            origin=LlmReviewInvocationOrigin.CLASSIFY_LLM_APPLY,
        )
        return OperationRequest(
            definition_id=LEDGER_CLASSIFY_REVIEW_DEFINITION_ID,
            subject_ref=ledger_llm_review_subject(payload),
            payload=payload,
        )


@contextmanager
def _case(tmp_path: Path, authority_operation: PinnedAuthorityOperation) -> Generator[_Case]:
    with (
        validating_governed_facts(authority_operation),
        isolated_runtime_profile(tmp_path=tmp_path, bucket_id=_PROFILE) as profile,
    ):
        repository = TransactionCatalogueRepository(bucket_id=_PROFILE, objects=profile.repository)
        baseline = _movement("encrypted-reviewed-row", "121.00", row=1)
        other = _movement("encrypted-other-row", "64.00", row=2)
        repository.save(TransactionCatalogue.from_transactions((baseline, other)))
        acquisitions: list[PromptSpec] = []

        def classifier(spec: PromptSpec) -> SubprocessLLMClassifier:
            acquisitions.append(spec)
            return SubprocessLLMClassifier(
                name="recorded-local",
                command=(
                    sys.executable,
                    "-c",
                    "import sys; sys.stdin.read(); "
                    f'print(\'{{"classification":"PERSONAL","confidence":"0.9000","reason":"{_REASON}"}}\')',
                ),
                spec=spec,
            )

        with (
            ledger_ports_for_test(
                bucket_id=_PROFILE, objects=profile.repository, transaction_repository=repository
            ) as ledger,
            validating_governed_facts(ledger.operation),
        ):
            assert ledger.operation.generation.logical_generation == authority_operation.generation.logical_generation
            ports = LedgerLlmOperationPorts(
                ledger=ledger,
                settings=load_settings(),
                llm=LLMClassificationPorts(
                    resolve_evidence_input=_unused_reader,
                    text_layer_ports=EvidenceTextLayerPorts(extract_pages_text=_unused_reader),
                    rasterise_pdf=_unused_reader,
                    make_text_classifier=classifier,
                    make_vision_classifier=_unused_reader,
                    run_reader=_run_reader,
                    record_classifier_run=_record_reader,
                ),
            )
            barrier = _ResumeBarrier()
            definition = build_ledger_llm_review_definition(
                LEDGER_CLASSIFY_REVIEW_DEFINITION_ID,
                lambda *, bucket_id, operation: ports,
            ).model_copy(
                update={
                    "executor_factory": OperationExecutorFactory(
                        request_type=LedgerLlmReviewRequest,
                        executor_type=_ScheduledExecutor,
                        build=lambda: _ScheduledExecutor(ports, barrier),
                    )
                }
            )
            view = build_ledger_view_definition(lambda *, bucket_id, operation: ports.ledger)
            yield _Case(
                root=tmp_path / "operations",
                database=profile.paths.database_file,
                objects=profile.repository,
                registry=OperationRegistry(
                    definitions=(definition, view),
                    public_registrations=(
                        build_ledger_llm_review_registration(definition),
                        build_ledger_view_registration(view),
                    ),
                ),
                ports=ports,
                baseline=baseline,
                other=other,
                barrier=barrier,
                acquisitions=acquisitions,
            )


async def _publish(
    case: _Case, services: OperationComposedServices, movement: Transaction | None = None
) -> tuple[OperationSubmission, OperationPersistedSnapshot]:
    submission = await services.submission.submit(case.request(movement), actor_ref="operator:reviewer")
    waiting = await run_to_settlement(services.submission.supervisor, submission.receipt.operation_id)
    assert waiting.lifecycle is OperationLifecycle.WAITING_FOR_INTERACTION and waiting.effect is OperationEffect.NONE
    assert submission.response_capability is not None
    return submission, waiting


def _control(waiting: OperationPersistedSnapshot) -> OperationResponseControlRequestV1:
    pending = waiting.pending_interaction
    assert pending is not None
    return OperationResponseControlRequestV1(
        operation_id=waiting.identity.operation_id,
        interaction_id=pending.request.interaction_id,
        revision=pending.request.revision,
        actor_ref="operator:reviewer",
    )


async def _apply(
    services: OperationComposedServices, submission: OperationSubmission, waiting: OperationPersistedSnapshot
) -> None:
    request = OperationResponseApplyRequestV1(**_control(waiting).model_dump(), responded_at=_NOW)
    response = await services.response(request, submission.response_capability)
    assert isinstance(await response.apply(request), OperationResponseMutationSuccessV1)


def test_secure_review_publication_and_result_bind_the_actual_encrypted_operand(
    tmp_path: Path, authority_operation: PinnedAuthorityOperation
) -> None:
    with _case(tmp_path, authority_operation) as case:
        services = case.services()

        async def run() -> None:
            try:
                submission, waiting = await _publish(case, services)
                pending = waiting.pending_interaction
                assert pending is not None
                operands = operation_secure_reference_repository(objects=case.objects)
                secured = await operands.resolve(pending.reviewed_proposal_digest, LedgerLlmReviewedOperand)
                assert secured.identity == waiting.identity and secured.request == case.request().payload
                assert sha256_hex(serialize_operation_operand(secured)) == pending.reviewed_proposal_digest
                baseline, suggestion = secured.decode(case.ports.ledger.operation)
                assert baseline == case.baseline and suggestion.reason == _REASON
                contract = case.registry.lookup_public_contract(LEDGER_CLASSIFY_REVIEW_DEFINITION_ID)
                assert contract.review_projection_schema is not None
                assert contract.result_schema is not None
                projected = await services.review.resolve(
                    OperationReviewProjectionRequestV1(
                        reference=OperationReviewProjectionReferenceV1(
                            operation_id=waiting.identity.operation_id,
                            interaction_id=pending.request.interaction_id,
                            revision=pending.request.revision,
                            review_projection_schema=contract.review_projection_schema,
                            definition_contract_digest=contract.definition_contract_digest,
                            expires_at=pending.request.expires_at,
                        )
                    ),
                    LedgerLlmReviewProjection,
                )
                assert isinstance(projected, OperationReviewProjectionSuccessV1)
                assert projected.projection.reviewed_proposal_digest == pending.reviewed_proposal_digest
                assert projected.projection.suggestion.confidence == "0.9000"
                inspected = await (
                    await services.inspect_response(_control(waiting), submission.response_capability)
                ).inspect(_control(waiting))
                assert isinstance(inspected, OperationResponseControlSuccessV1)
                await _apply(services, submission, waiting)
                terminal = await services.submission.supervisor.await_terminal(waiting.identity.operation_id)
                assert terminal.terminal_condition is OperationTerminalCondition.SUCCEEDED
                assert terminal.effect is OperationEffect.UPDATED
                result = await services.result.resolve(
                    OperationResultProjectionRequestV1(
                        operation_id=terminal.identity.operation_id,
                        terminal_revision=terminal.revision,
                        definition_contract_digest=contract.definition_contract_digest,
                        result_schema=contract.result_schema,
                    ),
                    LedgerLlmOperationResult,
                )
                assert isinstance(result, OperationResultProjectionSuccessV1)
                assert result.projection.reviewed_proposal_digest == pending.reviewed_proposal_digest
                assert result.projection.outcome == "classified"
                persisted = case.ports.ledger.transaction_repository.load().get(case.baseline.transaction_id)
                assert persisted is not None and persisted.business_classification is BusinessClassification.PERSONAL
                assert len(case.acquisitions) == 1
                assert _REASON.encode() not in read_db_at_rest_bytes(case.database)
                assert case.baseline.raw.description.encode() not in read_db_at_rest_bytes(case.database)
                assert all(_REASON.encode() not in file.read_bytes() for file in case.root.rglob("*") if file.is_file())
            finally:
                await services.shutdown()

        asyncio.run(run())


def test_consumed_response_recovers_without_classifier_reacquisition(
    tmp_path: Path, authority_operation: PinnedAuthorityOperation
) -> None:
    with _case(tmp_path, authority_operation) as case:
        services = case.services()
        case.barrier.enabled = True

        async def consume() -> OperationPersistedSnapshot:
            submission, waiting = await _publish(case, services)
            await _apply(services, submission, waiting)
            await asyncio.wait_for(case.barrier.entered.wait(), timeout=5)
            recorded = await OperationJournalRepository(storage_root=case.root).load(waiting.identity.operation_id)
            assert recorded.pending_interaction is None and len(recorded.consumed_interactions) == 1
            assert recorded.effect is OperationEffect.NONE and len(case.acquisitions) == 1
            assert submission.response_capability is not None
            submission.response_capability.close()
            return recorded

        # Closing this loop cancels the paused original task before the writer;
        # its actual consumed checkpoint and expiring filesystem lease remain.
        consumed = asyncio.run(consume())
        case.barrier.enabled = False
        recovery = case.services(recovery=True)

        async def resume() -> None:
            try:
                admitted = await recovery.submission.supervisor.reconcile(consumed.identity.operation_id)
                assert admitted.lifecycle is OperationLifecycle.RUNNING
                terminal = await recovery.submission.supervisor.settled(consumed.identity.operation_id)
                assert terminal.terminal_condition is OperationTerminalCondition.SUCCEEDED
                assert terminal.effect is OperationEffect.UPDATED
                assert terminal.consumed_interactions == consumed.consumed_interactions
                persisted = case.ports.ledger.transaction_repository.load().get(case.baseline.transaction_id)
                assert persisted is not None and persisted.business_classification is BusinessClassification.PERSONAL
                assert len(case.acquisitions) == 1
            finally:
                await recovery.shutdown()

        asyncio.run(resume())


@pytest.mark.parametrize("changed_field", ["notes", "description"])
def test_stale_review_refuses_cas_without_overwrite_or_partial_audit(
    tmp_path: Path, authority_operation: PinnedAuthorityOperation, changed_field: Literal["notes", "description"]
) -> None:
    with _case(tmp_path, authority_operation) as case:
        services = case.services()
        fresh = case.services(recovery=True)

        async def run() -> None:
            try:
                submission, waiting = await _publish(case, services)
                unavailable = await (
                    await fresh.inspect_response(_control(waiting), submission.response_capability)
                ).inspect(_control(waiting))
                assert isinstance(unavailable, OperationResponseControlRefusalV1)
                assert (await services.submission.supervisor.inspect(waiting.identity.operation_id)) == waiting
                changed = update_manual_transaction_fields(
                    bucket_id=_PROFILE,
                    transaction_id=case.baseline.transaction_id,
                    patch=(
                        ManualLedgerTransactionPatch(notes="competing real writer")
                        if changed_field == "notes"
                        else ManualLedgerTransactionPatch(description="competing real writer")
                    ),
                    actor="other-operator",
                    source_command="synthetic competing edit",
                    ports=case.ports.ledger,
                    occurred_at=_NOW,
                    expected_current=case.baseline,
                ).transaction
                if changed_field == "notes":
                    assert changed.transaction_id == case.baseline.transaction_id
                    assert changed.notes == "competing real writer"
                else:
                    assert changed.transaction_id != case.baseline.transaction_id
                    assert changed.raw.description == "competing real writer"
                    assert case.ports.ledger.transaction_repository.load().get(case.baseline.transaction_id) is None
                competing = case.ports.ledger.transaction_repository.load()
                history = case.ports.ledger.bucket_event_repository.load()
                await _apply(services, submission, waiting)
                terminal = await services.submission.supervisor.await_terminal(waiting.identity.operation_id)
                assert terminal.terminal_condition is OperationTerminalCondition.FAILED
                assert terminal.effect is OperationEffect.NONE
                catalogue = case.ports.ledger.transaction_repository.load()
                assert catalogue == competing
                persisted = catalogue.get(changed.transaction_id)
                assert persisted == changed
                if changed_field == "notes":
                    assert persisted.notes == "competing real writer"
                else:
                    assert persisted.raw.description == "competing real writer"
                    assert catalogue.get(case.baseline.transaction_id) is None
                    assert terminal.terminal_receipt is not None
                    assert terminal.terminal_receipt.failure_error_code == "ERROR_TRANSACTION_NOT_FOUND"
                assert case.ports.ledger.bucket_event_repository.load() == history
                assert len(case.acquisitions) == 1
            finally:
                await services.shutdown()
                await fresh.shutdown()

        asyncio.run(run())


async def _cancel(
    services: OperationComposedServices, observed: OperationPersistedSnapshot
) -> OperationCancellationSuccessV1 | OperationCancellationRefusalV1:
    return await services.cancellation.request(
        OperationCancellationRequestV1(operation_id=observed.identity.operation_id, expected_revision=observed.revision)
    )


def test_reviews_of_different_movements_wait_together_and_one_movement_holds_one_review(
    tmp_path: Path, authority_operation: PinnedAuthorityOperation
) -> None:
    with _case(tmp_path, authority_operation) as case:
        services = case.services()

        async def run() -> None:
            try:
                _, first = await _publish(case, services)
                _, second = await _publish(case, services, case.other)
                assert first.identity.subject_ref == case.baseline.transaction_id
                assert second.identity.subject_ref == case.other.transaction_id
                with pytest.raises(OperationSubjectBusyError):
                    await services.submission.submit(case.request(), actor_ref="operator:reviewer")
                supervisor = services.submission.supervisor
                for waiting in (first, second):
                    current = await supervisor.inspect(waiting.identity.operation_id)
                    assert current.lifecycle is OperationLifecycle.WAITING_FOR_INTERACTION
                observed = await services.observation.observe(
                    OperationObservationRequestV1(
                        operation_id=first.identity.operation_id, after_cursor=0, page_limit=1
                    )
                )
                assert isinstance(observed, OperationObservationSuccessV1)
                assert observed.projection.cancellable_now is True
                assert len(case.acquisitions) == 2
            finally:
                await services.shutdown()

        asyncio.run(run())


def test_cancelling_a_waiting_review_releases_its_movement_with_no_effect(
    tmp_path: Path, authority_operation: PinnedAuthorityOperation
) -> None:
    with _case(tmp_path, authority_operation) as case:
        services = case.services()

        async def run() -> None:
            try:
                submission, waiting = await _publish(case, services)
                history = case.ports.ledger.bucket_event_repository.load()
                cancelled = await _cancel(services, waiting)
                assert isinstance(cancelled, OperationCancellationSuccessV1)
                assert cancelled.cancellation_acknowledged is True
                terminal = await services.submission.supervisor.inspect(waiting.identity.operation_id)
                assert terminal.lifecycle is OperationLifecycle.TERMINAL
                assert terminal.terminal_condition is OperationTerminalCondition.CANCELLED
                assert terminal.effect is OperationEffect.NONE
                # The answer that arrives after the cancel finds nothing to take.
                request = OperationResponseApplyRequestV1(**_control(waiting).model_dump(), responded_at=_NOW)
                late = await (await services.response(request, submission.response_capability)).apply(request)
                assert not isinstance(late, OperationResponseMutationSuccessV1)
                persisted = case.ports.ledger.transaction_repository.load().get(case.baseline.transaction_id)
                assert persisted == case.baseline
                assert case.ports.ledger.bucket_event_repository.load() == history
                # The movement is free again: the next ask about it waits for its own answer.
                _, again = await _publish(case, services)
                assert again.identity.operation_id != waiting.identity.operation_id
            finally:
                await services.shutdown()

        asyncio.run(run())


def test_a_cancel_after_the_answer_was_taken_is_refused_and_the_answer_settles(
    tmp_path: Path, authority_operation: PinnedAuthorityOperation
) -> None:
    with _case(tmp_path, authority_operation) as case:
        services = case.services()
        case.barrier.enabled = True

        async def run() -> None:
            try:
                submission, waiting = await _publish(case, services)
                await _apply(services, submission, waiting)
                await asyncio.wait_for(case.barrier.entered.wait(), timeout=5)
                refused = await _cancel(services, waiting)
                assert isinstance(refused, OperationCancellationRefusalV1)
                assert refused.code is OperationCancellationRefusalCode.STALE_OPERATION_REVISION
                case.barrier.release.set()
                terminal = await services.submission.supervisor.await_terminal(waiting.identity.operation_id)
                assert terminal.terminal_condition is OperationTerminalCondition.SUCCEEDED
                assert terminal.effect is OperationEffect.UPDATED
                persisted = case.ports.ledger.transaction_repository.load().get(case.baseline.transaction_id)
                assert persisted is not None and persisted.business_classification is BusinessClassification.PERSONAL
            finally:
                await services.shutdown()

        asyncio.run(run())


def test_a_cancel_that_reaches_an_answered_review_before_its_write_stops_it_with_no_effect(
    tmp_path: Path, authority_operation: PinnedAuthorityOperation
) -> None:
    with _case(tmp_path, authority_operation) as case:
        services = case.services()
        case.barrier.enabled = True

        async def run() -> None:
            try:
                submission, waiting = await _publish(case, services)
                await _apply(services, submission, waiting)
                await asyncio.wait_for(case.barrier.entered.wait(), timeout=5)
                answered = await services.submission.supervisor.inspect(waiting.identity.operation_id)
                assert answered.lifecycle is OperationLifecycle.RUNNING
                requested = await _cancel(services, answered)
                assert isinstance(requested, OperationCancellationSuccessV1)
                case.barrier.release.set()
                terminal = await services.submission.supervisor.await_terminal(waiting.identity.operation_id)
                assert terminal.terminal_condition is OperationTerminalCondition.CANCELLED
                assert terminal.effect is OperationEffect.NONE
                assert (
                    case.ports.ledger.transaction_repository.load().get(case.baseline.transaction_id) == case.baseline
                )
            finally:
                await services.shutdown()

        asyncio.run(run())


async def _view(case: _Case, services: OperationComposedServices, handle: str) -> OperationPersistedSnapshot:
    """Resolve an operator's handle the way the command line does: through the profile's ledger view."""
    submission = await services.submission.submit(
        OperationRequest(
            definition_id=LEDGER_VIEW_OPERATION_DEFINITION_ID,
            subject_ref=profile_operation_subject(_PROFILE),
            payload=LedgerViewRequest(profile_id=UUID(_PROFILE), transaction_prefix=handle),
        ),
        actor_ref="operator:reviewer",
    )
    return await run_to_settlement(services.submission.supervisor, submission.receipt.operation_id)


def test_a_review_asked_by_a_handle_and_one_asked_by_the_full_id_hold_one_movement(
    tmp_path: Path, authority_operation: PinnedAuthorityOperation
) -> None:
    with _case(tmp_path, authority_operation) as case:
        services = case.services()

        async def run() -> None:
            try:
                viewed = await _view(case, services, case.baseline.transaction_id[:8])
                assert viewed.terminal_condition is OperationTerminalCondition.SUCCEEDED
                contract = case.registry.lookup_public_contract(LEDGER_VIEW_OPERATION_DEFINITION_ID)
                assert contract.result_schema is not None
                resolved = await services.result.resolve(
                    OperationResultProjectionRequestV1(
                        operation_id=viewed.identity.operation_id,
                        terminal_revision=viewed.revision,
                        definition_contract_digest=contract.definition_contract_digest,
                        result_schema=contract.result_schema,
                    ),
                    LedgerViewProjection,
                )
                assert isinstance(resolved, OperationResultProjectionSuccessV1)
                canonical = resolved.projection.transaction.transaction_id
                assert canonical == case.baseline.transaction_id
                _, waiting = await _publish(case, services, case.baseline)
                assert waiting.identity.subject_ref == canonical
                with pytest.raises(OperationSubjectBusyError):
                    await services.submission.submit(case.request(), actor_ref="operator:reviewer")
            finally:
                await services.shutdown()

        asyncio.run(run())


def test_a_handle_that_names_more_than_one_movement_is_refused_by_the_ledger_view(
    tmp_path: Path, authority_operation: PinnedAuthorityOperation
) -> None:
    with _case(tmp_path, authority_operation) as case:
        repository = case.ports.ledger.transaction_repository
        movements = dict(repository.load().transactions)
        row = 3
        # Among seventeen ids two share a first hex digit.
        while len({transaction_id[0] for transaction_id in movements}) == len(movements):
            added = _movement(f"encrypted-extra-row-{row}", f"{row}.00", row=row)
            movements[added.transaction_id] = added
            row += 1
        repository.save(TransactionCatalogue.from_transactions(tuple(movements.values())))
        firsts = [transaction_id[0] for transaction_id in movements]
        shared = next(first for first in firsts if firsts.count(first) > 1)
        services = case.services()

        async def run() -> None:
            try:
                refused = await _view(case, services, shared)
                receipt = refused.terminal_receipt
                assert receipt is not None and receipt.effect is OperationEffect.NONE
                assert refused.terminal_condition is OperationTerminalCondition.REFUSED
                assert receipt.refusal_ref == get_registered_error_code(TransactionIdPrefixError).code
            finally:
                await services.shutdown()

        asyncio.run(run())


@pytest.mark.parametrize(
    "spelling",
    [
        pytest.param(lambda full: full[:12], id="short-handle"),
        pytest.param(lambda full: full.upper(), id="uppercase"),
        pytest.param(lambda full: full + "0", id="too-long"),
    ],
)
def test_the_registered_review_request_refuses_a_movement_not_named_by_its_canonical_id(
    tmp_path: Path, authority_operation: PinnedAuthorityOperation, spelling: Callable[[str], str]
) -> None:
    with _case(tmp_path, authority_operation) as case:
        full = case.baseline.transaction_id
        document = {
            "profile_id": _PROFILE,
            "transaction_id": full,
            "mode": "classification",
            "origin": "classify_llm_apply",
        }
        decoded = case.registry.decode_request_payload(LEDGER_CLASSIFY_REVIEW_DEFINITION_ID, json.dumps(document))
        assert isinstance(decoded, LedgerLlmReviewRequest) and decoded.transaction_id == full
        with pytest.raises(ValidationError):
            case.registry.decode_request_payload(
                LEDGER_CLASSIFY_REVIEW_DEFINITION_ID,
                json.dumps({**document, "transaction_id": spelling(full)}),
            )

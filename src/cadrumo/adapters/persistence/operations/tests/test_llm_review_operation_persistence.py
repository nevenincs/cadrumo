"""Encrypted ledger review continuity with a local subprocess reader.

The storage fixture supplies synthetic custody material. These cases exercise
the real classifier parser, executor, response broker, journal, and CAS writer;
they do not establish native login, credential custody, or model availability.
"""

from __future__ import annotations

import asyncio
import sys
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from pathlib import Path
from typing import Literal, NoReturn, override
from uuid import UUID

import pytest

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
from cadrumo.application.ledger.llm_review_operation import (
    LEDGER_CLASSIFY_REVIEW_DEFINITION_ID,
    LedgerLlmOperationPorts,
    LedgerLlmOperationResult,
    LedgerLlmReviewedOperand,
    LedgerLlmReviewExecutor,
    LedgerLlmReviewProjection,
    LedgerLlmReviewRequest,
    build_ledger_llm_review_definition,
    build_ledger_llm_review_registration,
)
from cadrumo.application.ledger.llm_review_workflow import LlmReviewInvocationOrigin
from cadrumo.application.ledger.models import ManualLedgerTransactionPatch
from cadrumo.application.operations.composition import (
    OperationComposedServices,
    OperationSubmission,
    compose_operation_services,
)
from cadrumo.application.operations.frontend_projection import OperationReviewProjectionReferenceV1
from cadrumo.application.operations.frontend_requests import (
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
from cadrumo.application.operations.owner import OperationExecutorContext, OperationResumeCheckpoint
from cadrumo.application.operations.persistence.journal import OperationPersistedSnapshot, serialize_operation_operand
from cadrumo.application.operations.registry import OperationExecutorFactory, OperationRegistry
from cadrumo.core.config import load_settings
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

    def request(self) -> OperationRequest[LedgerLlmReviewRequest]:
        return OperationRequest(
            definition_id=LEDGER_CLASSIFY_REVIEW_DEFINITION_ID,
            subject_ref=profile_operation_subject(_PROFILE),
            payload=LedgerLlmReviewRequest(
                profile_id=UUID(_PROFILE),
                transaction_id=self.baseline.transaction_id[:12],
                mode="classification",
                origin=LlmReviewInvocationOrigin.CLASSIFY_LLM_APPLY,
            ),
        )


@contextmanager
def _case(tmp_path: Path, authority_operation: PinnedAuthorityOperation) -> Iterator[_Case]:
    with (
        validating_governed_facts(authority_operation),
        isolated_runtime_profile(tmp_path=tmp_path, bucket_id=_PROFILE) as profile,
    ):
        repository = TransactionCatalogueRepository(bucket_id=_PROFILE, objects=profile.repository)
        baseline = Transaction.model_validate(
            {
                "raw": RawTransaction(
                    provider_transaction_id="encrypted-reviewed-row",
                    booked_date=date(2026, 5, 1),
                    amount=Decimal("121.00"),
                    currency="EUR",
                    description="synthetic private baseline",
                    provenance=RawProvenance(
                        source_path=Path("synthetic-review.csv"),
                        source_sha256="c" * 64,
                        source_row_index=1,
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
        repository.save(TransactionCatalogue.from_transactions((baseline,)))
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
            yield _Case(
                root=tmp_path / "operations",
                database=profile.paths.database_file,
                objects=profile.repository,
                registry=OperationRegistry(
                    definitions=(definition,),
                    public_registrations=(build_ledger_llm_review_registration(definition),),
                ),
                ports=ports,
                baseline=baseline,
                barrier=barrier,
                acquisitions=acquisitions,
            )


async def _publish(
    case: _Case, services: OperationComposedServices
) -> tuple[OperationSubmission, OperationPersistedSnapshot]:
    submission = await services.submission.submit(case.request(), actor_ref="operator:reviewer")
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
                terminal = await recovery.submission.supervisor.reconcile(consumed.identity.operation_id)
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

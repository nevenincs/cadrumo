"""A refused model classification settles with the agent service's typed verdict, so every frontend can act on it.

The registered classification review runs through the real registry,
supervisor, journal and encrypted operand store, with the production ledger
model composition, against a stored ledger row. Its model runs reach a
recording stand-in for the agent service through an execution authority, as
the runtime host's authority relays them. The refusal is then read back the
way a frontend in another process reads it: as the operation's recorded error
detail. A selected model that is not installed is named in the verdict; a
role with no selection names the role and says it needs one. The detail must
not carry the row's private text, and no run may reach the service.
"""

from __future__ import annotations

import asyncio
from collections.abc import Iterator, Mapping
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from pathlib import Path
from uuid import UUID

import pytest
from pydantic import BaseModel

from cadrumo_client.contracts.model_runs import ModelRunRefusalCode

from ...adapters.outbound.llm.preconditions import LLMPreconditionCondition
from ...adapters.outbound.llm.tests.model_run_support import RecordingModelRuns
from ...adapters.persistence.operations.tests.supervision_support import run_to_settlement
from ...adapters.persistence.operations.tests.supervisor_test_support import operation_repositories
from ...adapters.persistence.profile.tests.ledger_action_create_support import ledger_ports_for_test
from ...adapters.persistence.profile.transactions import TransactionCatalogueRepository
from ...adapters.persistence.storage.tests.secure_sql import TestRuntimeProfile, isolated_runtime_profile
from ...application.ledger.evidence_errors import (
    EVIDENCE_READER_UNAVAILABLE_LOCALE_KEY,
    PurchaseInvoiceEvidenceReaderError,
)
from ...application.ledger.llm_review_contracts import (
    LEDGER_CLASSIFY_REVIEW_DEFINITION_ID,
    LedgerLlmReviewRequest,
    ledger_llm_review_subject,
)
from ...application.ledger.llm_review_execution import LedgerLlmOperationPorts
from ...application.ledger.llm_review_operation import (
    build_ledger_llm_review_definition,
    build_ledger_llm_review_registration,
)
from ...application.ledger.llm_review_workflow import LlmReviewInvocationOrigin
from ...application.operations.error_detail import (
    OperationErrorDetailKind,
    OperationErrorDetailV1,
    operation_error_detail_schema,
)
from ...application.operations.frontend_requests import (
    OperationResultProjectionRequestV1,
    OperationResultProjectionSuccessV1,
)
from ...application.operations.models import OperationRequest
from ...application.operations.projection_services import OperationResultProjectionService
from ...application.operations.registry import OperationRegistry
from ...application.operations.supervisor import OperationSupervisor
from ...core.config import load_settings
from ...core.errors.error_codes import get_registered_error_code
from ...core.model_roles import ModelRole
from ...core.operations import OperationEffect, OperationTerminalCondition
from ...domain.calculations.registry.governed_fact_scope import validating_governed_facts
from ...domain.transactions.enums import TransactionDirection
from ...domain.transactions.models import Transaction, TransactionCatalogue
from ...domain.transactions.raw_transaction import RawProvenance, RawTransaction, SourceFormat
from ..ledger_llm_composition import compose_ledger_llm
from .dependency_operation_gating_support import RecordingRunsAuthority, agent_refusing

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint]

_PROFILE = UUID("8e3f5a7b-9c2d-4e4f-8a6b-7c8d9e0f1a2b")
_REGISTERED = get_registered_error_code(PurchaseInvoiceEvidenceReaderError)

#: The row's own text: it is what the model would read, so it must never reach the published detail.
_PRIVATE_DESCRIPTION = "synthetic private classification row 5f2c"


@pytest.fixture
def profile(tmp_path: Path) -> Iterator[TestRuntimeProfile]:
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=str(_PROFILE)) as runtime_profile:
        yield runtime_profile


def _stored_row(repository: TransactionCatalogueRepository) -> Transaction:
    row = Transaction.model_validate(
        {
            "raw": RawTransaction(
                provider_transaction_id="reader-refusal-row",
                booked_date=date(2026, 10, 20),
                amount=Decimal("121.00"),
                currency="EUR",
                description=_PRIVATE_DESCRIPTION,
                provenance=RawProvenance(
                    source_path=Path("synthetic-classification.csv"),
                    source_sha256="d" * 64,
                    source_row_index=1,
                    source_format=SourceFormat.CSV,
                    ingested_at=datetime(2026, 10, 20, tzinfo=UTC),
                    provider_name="csv",
                ),
                raw_fields={},
            ),
            "direction": TransactionDirection.OUTGOING,
            "group_label": None,
            "source_jurisdiction": "ES",
        }
    )
    repository.save(TransactionCatalogue.from_transactions((row,)))
    return row


def _settle_and_read_detail(
    tmp_path: Path, profile: TestRuntimeProfile, service: RecordingModelRuns
) -> tuple[OperationTerminalCondition, str | None, OperationErrorDetailV1]:
    repository = TransactionCatalogueRepository(bucket_id=str(_PROFILE), objects=profile.repository)
    settings = load_settings()
    with (
        ledger_ports_for_test(
            bucket_id=str(_PROFILE), objects=profile.repository, transaction_repository=repository
        ) as ledger,
        validating_governed_facts(ledger.operation),
    ):
        row = _stored_row(repository)
        ports = LedgerLlmOperationPorts(
            ledger=ledger,
            llm=compose_ledger_llm(bucket_id=str(_PROFILE), settings=settings).ports,
            settings=settings,
        )
        definition = build_ledger_llm_review_definition(
            LEDGER_CLASSIFY_REVIEW_DEFINITION_ID, lambda *, bucket_id, operation: ports
        )
        registration = build_ledger_llm_review_registration(definition)
        registry = OperationRegistry(definitions=(definition,), public_registrations=(registration,))
        journal, leases, operands = operation_repositories(
            storage_root=tmp_path / "durable-state", profile_objects=profile.repository
        )
        supervisor = OperationSupervisor(
            authority_operation=ledger.operation,
            registry=registry,
            journal=journal,
            event_stream=journal,
            leases=leases,
            operands=operands,
            owner_id="1" * 64,
            lease_token_factory=lambda: "2" * 64,
            clock=lambda: datetime.now(UTC),
            lease_duration=timedelta(minutes=5),
            execution_timeout=timedelta(minutes=2),
            cleanup_timeout=timedelta(minutes=1),
            response_token_factory=lambda: "3" * 64,
            execution_authority=RecordingRunsAuthority(service),
        )

        async def settle() -> tuple[OperationTerminalCondition, str | None, OperationErrorDetailV1]:
            review = LedgerLlmReviewRequest(
                profile_id=_PROFILE,
                transaction_id=row.transaction_id,
                mode="classification",
                origin=LlmReviewInvocationOrigin.CLASSIFY_LLM_APPLY,
            )
            operation_id = await supervisor.submit(
                OperationRequest[BaseModel](
                    definition_id=LEDGER_CLASSIFY_REVIEW_DEFINITION_ID,
                    subject_ref=ledger_llm_review_subject(review),
                    payload=review,
                ),
                operation_id="4" * 64,
            )
            terminal = await run_to_settlement(supervisor, operation_id)
            receipt = terminal.terminal_receipt
            assert receipt is not None
            assert receipt.effect is OperationEffect.NONE
            resolved = await OperationResultProjectionService(
                reader=journal, registry=registry, operands=operands
            ).resolve(
                OperationResultProjectionRequestV1(
                    operation_id=operation_id,
                    terminal_revision=terminal.revision,
                    definition_contract_digest=registration.contract.definition_contract_digest,
                    result_schema=operation_error_detail_schema(),
                ),
                OperationErrorDetailV1,
            )
            assert isinstance(resolved, OperationResultProjectionSuccessV1), resolved
            detail = resolved.projection
            assert isinstance(detail, OperationErrorDetailV1)
            return receipt.condition, receipt.refusal_ref, detail

        return asyncio.run(settle())


def _assert_refused_by_the_reader(
    settled: tuple[OperationTerminalCondition, str | None, OperationErrorDetailV1],
    service: RecordingModelRuns,
    *,
    message_key: str,
    condition: LLMPreconditionCondition,
) -> Mapping[str, str | int | bool | Decimal]:
    refused, refusal_ref, detail = settled
    assert refused is OperationTerminalCondition.REFUSED
    assert refusal_ref == _REGISTERED.code
    assert detail.kind is OperationErrorDetailKind.REGISTERED_ERROR
    assert detail.error_code == _REGISTERED.code
    assert detail.message_key == message_key
    verdict = detail.precondition_verdict()
    assert verdict is not None, "the settled refusal lost the service's verdict"
    assert verdict.failed_condition_id == condition.value
    facts = verdict.evidence[0].values
    assert facts["role"] == ModelRole.TEXT_EXTRACTION.value
    assert _PRIVATE_DESCRIPTION not in detail.model_dump_json(), "the published detail carries the row's text"
    assert service.lookups == [ModelRole.TEXT_EXTRACTION]
    assert service.runs == [], "a run was sent for a role the service cannot run"
    assert verdict.action is None
    return facts


def test_a_classification_refused_for_its_missing_text_model_settles(
    tmp_path: Path, profile: TestRuntimeProfile
) -> None:
    with agent_refusing(ModelRunRefusalCode.MODEL_NOT_INSTALLED) as service:
        settled = _settle_and_read_detail(tmp_path, profile, service)

    _assert_refused_by_the_reader(
        settled,
        service,
        message_key=EVIDENCE_READER_UNAVAILABLE_LOCALE_KEY,
        condition=LLMPreconditionCondition.AGENT_MODEL_RUN_COMPLETED,
    )


def test_a_classification_with_no_text_selection_settles_naming_the_role_that_needs_one(
    tmp_path: Path, profile: TestRuntimeProfile
) -> None:
    with agent_refusing(ModelRunRefusalCode.NO_SELECTION) as service:
        settled = _settle_and_read_detail(tmp_path, profile, service)

    facts = _assert_refused_by_the_reader(
        settled,
        service,
        message_key=EVIDENCE_READER_UNAVAILABLE_LOCALE_KEY,
        condition=LLMPreconditionCondition.AGENT_MODEL_RUN_COMPLETED,
    )
    assert facts["model_run_refusal"] == ModelRunRefusalCode.NO_SELECTION.value
    assert facts["role_selection_required"] is True

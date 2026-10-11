"""An agent's execution records its session's label, and a person's execution records the label it sent.

The production registry and the real executors run over a stored profile with
a session host that answers for the frontend that admitted the invocation.
Each operation below stores who acted from a label the request carries, and
for an execution admitted on the MCP frontend that label is the session's.
"""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime
from pathlib import Path
from uuid import UUID

import pytest

from ...adapters.persistence.profile.counterparty_establishment import build_counterparty_establishment_repository
from ...adapters.persistence.profile.modelo_reconciliation import ModeloReconciliationPersistence
from ...application.bucket_event_repository import bucket_event_history_repository
from ...application.inventory.registered_requests import (
    INVENTORY_CLOSING_AUTHORITY_RECORD_OPERATION_DEFINITION_ID,
    InventoryClosingAuthorityRecordRequest,
)
from ...application.inventory.tests.registered_operation_conformance_support import (
    prepare_inventory_operation_conformance_case,
    read_inventory_operation_conformance_ledger,
)
from ...application.invoices.catalogue_add_operation import InvoiceAddResult
from ...application.invoices.catalogue_update_operation import InvoiceUpdateResult
from ...application.ledger.counterparty_operation import LedgerCounterpartyRequest, LedgerCounterpartyResult
from ...application.ledger.link_operation import LedgerLinkOperationResult, LedgerLinkRequest
from ...application.ledger.operator_iva_contracts import LedgerOperatorIvaRequest, LedgerOperatorIvaResult
from ...application.modelo.reconciliation_import_operation import (
    MODELO_RECONCILIATION_IMPORT_OPERATION_DEFINITION_ID,
    ModeloReconciliationImportRequest,
)
from ...application.modelo.reconciliation_pull_operation import (
    MODELO_RECONCILIATION_PULL_OPERATION_DEFINITION_ID,
    ModeloReconciliationPullRequest,
)
from ...application.modelo.reconciliation_records import ModeloReconciliationEvidenceKind
from ...application.operations.execution_actor import OperationExecutionCaller, OperationExecutionCallerReader
from ...application.operations.models import OperationIdentity
from ...application.operations.registry import OperationFrontendProjection
from ...application.user_profile.access_contracts import SessionKind
from ...core.config import override_settings
from ...core.hashing import sha256_hex
from ...core.operations import OperationEffect, OperationTerminalCondition, profile_operation_subject
from ...domain.calculations.registry.authority import PinnedAuthorityOperation
from ..adapter_composition import build_inventory_service_ports
from ..justificante_composition import build_justificante_capture_service
from . import modelo_operation_test_support
from . import test_registered_executor_conformance as conformance

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint]

_MCP = OperationFrontendProjection.MCP
_CLI = OperationFrontendProjection.CLI
_SESSION_CLIENT = UUID("5aa00000-0000-4000-8000-0000000000dd")
_TYPED_ACTOR = "typed by the caller"
_AGENT_LABEL = f"agent:mcp.attended.{_SESSION_CLIENT}"
_JUSTIFICANTE_FIXTURE = (
    Path(__file__).resolve().parents[2] / "tests" / "fixtures" / "justificantes" / "130" / "2024-1T.pdf"
)
_FRONTENDS = pytest.mark.parametrize(
    ("frontend", "recorded"),
    [(_MCP, _AGENT_LABEL), (_CLI, _TYPED_ACTOR)],
    ids=["mcp", "cli"],
)


def _session_host(definition_id: str, frontend: OperationFrontendProjection) -> OperationExecutionCallerReader:
    """What a session host answers for an invocation of ``definition_id`` it admitted on ``frontend``."""

    def read(identity: OperationIdentity) -> OperationExecutionCaller:
        assert identity.definition_id == definition_id
        return OperationExecutionCaller(frontend=frontend, session_kind=SessionKind.ATTENDED, client_id=_SESSION_CLIENT)

    return read


def _event_actors(profile_id: UUID, event_ids: tuple[str, ...]) -> set[str]:
    events = bucket_event_history_repository(bucket_id=str(profile_id)).load().events
    assert event_ids
    return {events[event_id].actor for event_id in event_ids}


@_FRONTENDS
def test_operator_iva_derivation_records_the_session_label_for_an_agent(
    tmp_path: Path,
    operation: PinnedAuthorityOperation,
    frontend: OperationFrontendProjection,
    recorded: str,
) -> None:
    """The audit events of the derivation carry the label the executor derived, not the typed one."""
    definition_id = "ledger.classify.iva-derive"
    with (
        conformance._model_runtime_for(definition_id),
        conformance._runtime(
            tmp_path / "runtime",
            cleanup=conformance._CloseWitness(),
            execution_caller_reader=_session_host(definition_id, frontend),
        ) as (driver, registry, profile_id),
    ):
        definition = {item.definition_id: item for item in registry.definitions}[definition_id]
        preparation = conformance._prepare_family_case(
            definition, profile_id=profile_id, tmp_path=tmp_path, operation=operation
        )
        assert preparation is not None
        assert isinstance(preparation.request, LedgerOperatorIvaRequest)
        request = preparation.request.model_copy(update={"actor": _TYPED_ACTOR})

        submitted, observed = asyncio.run(
            driver.run(definition_id=definition_id, subject_ref=preparation.subject_ref, payload=request)
        )

        assert observed.projection.terminal_condition is OperationTerminalCondition.SUCCEEDED
        result = conformance._resolve_result_projection(
            driver,
            registry,
            definition_id=definition_id,
            operation_id=submitted.receipt.operation_id,
            terminal_revision=observed.projection.revision,
            projection_type=LedgerOperatorIvaResult,
        )
        assert result.classification is not None
        assert _event_actors(profile_id, result.classification.bucket_event_ids) == {recorded}


@_FRONTENDS
def test_ledger_link_records_the_session_label_for_an_agent(
    tmp_path: Path,
    operation: PinnedAuthorityOperation,
    frontend: OperationFrontendProjection,
    recorded: str,
) -> None:
    """The link's result and its audit event name the derived label, not the typed one."""
    definition_id = "ledger.link"
    with conformance._runtime(
        tmp_path / "runtime",
        cleanup=conformance._CloseWitness(),
        execution_caller_reader=_session_host(definition_id, frontend),
    ) as (driver, registry, profile_id):
        definition = {item.definition_id: item for item in registry.definitions}[definition_id]
        preparation = conformance._prepare_family_case(
            definition, profile_id=profile_id, tmp_path=tmp_path, operation=operation
        )
        assert preparation is not None
        assert isinstance(preparation.request, LedgerLinkRequest)
        request = preparation.request.model_copy(update={"actor": _TYPED_ACTOR})

        submitted, observed = asyncio.run(
            driver.run(definition_id=definition_id, subject_ref=preparation.subject_ref, payload=request)
        )

        assert observed.projection.terminal_condition is OperationTerminalCondition.SUCCEEDED
        result = conformance._resolve_result_projection(
            driver,
            registry,
            definition_id=definition_id,
            operation_id=submitted.receipt.operation_id,
            terminal_revision=observed.projection.revision,
            projection_type=LedgerLinkOperationResult,
        )
        assert result.projection is not None
        assert result.projection.actor == recorded
        assert _event_actors(profile_id, result.projection.bucket_event_ids) == {recorded}


@_FRONTENDS
def test_counterparty_confirmation_records_the_session_label_for_an_agent(
    tmp_path: Path,
    frontend: OperationFrontendProjection,
    recorded: str,
) -> None:
    """The stored assertion names the label the executor derived, not the typed one."""
    definition_id = "ledger.counterparty"
    with conformance._runtime(
        tmp_path / "runtime",
        cleanup=conformance._CloseWitness(),
        execution_caller_reader=_session_host(definition_id, frontend),
    ) as (driver, registry, profile_id):
        request = LedgerCounterpartyRequest(
            profile_id=profile_id,
            action="confirm",
            tax_identifier="B12345674",
            territorial_scope="es_canarias",
            asserted_by=_TYPED_ACTOR,
            note="synthetic assertion",
        )

        submitted, observed = asyncio.run(
            driver.run(
                definition_id=definition_id,
                subject_ref=profile_operation_subject(str(profile_id)),
                payload=request,
            )
        )

        assert observed.projection.terminal_condition is OperationTerminalCondition.SUCCEEDED
        result = conformance._resolve_result_projection(
            driver,
            registry,
            definition_id=definition_id,
            operation_id=submitted.receipt.operation_id,
            terminal_revision=observed.projection.revision,
            projection_type=LedgerCounterpartyResult,
        )
        assert result.facts is not None
        assert result.facts.asserted_by == recorded
        persisted = build_counterparty_establishment_repository(bucket_id=str(profile_id)).load(
            result.facts.counterparty_key
        )
        assert persisted is not None
        assert persisted.asserted_by == recorded


@_FRONTENDS
def test_inventory_closing_authority_records_the_session_label_for_an_agent(
    tmp_path: Path,
    frontend: OperationFrontendProjection,
    recorded: str,
) -> None:
    """The stored decision, and so its fingerprint, carry the derived label."""
    definition_id = INVENTORY_CLOSING_AUTHORITY_RECORD_OPERATION_DEFINITION_ID
    with conformance._runtime(
        tmp_path / "runtime",
        cleanup=conformance._CloseWitness(),
        execution_caller_reader=_session_host(definition_id, frontend),
    ) as (driver, _registry, profile_id):
        case = prepare_inventory_operation_conformance_case(
            definition_id, profile_id, ports_factory=build_inventory_service_ports
        )
        seeded = case.request
        assert isinstance(seeded, InventoryClosingAuthorityRecordRequest)
        decision = seeded.authority_record.decision.model_copy(update={"actor": _TYPED_ACTOR})
        request = seeded.model_copy(
            update={"authority_record": seeded.authority_record.model_copy(update={"decision": decision})}
        )

        _submitted, observed = asyncio.run(
            driver.run(
                definition_id=definition_id,
                subject_ref=profile_operation_subject(str(profile_id)),
                payload=request,
            )
        )

        assert observed.projection.terminal_condition is OperationTerminalCondition.SUCCEEDED
        ledger = read_inventory_operation_conformance_ledger(
            case, profile_id, ports_factory=build_inventory_service_ports
        )
        assert ledger.closing_authority_record is not None
        assert ledger.closing_authority_record.decision.actor == recorded


@_FRONTENDS
def test_reconciliation_import_records_the_session_label_for_an_agent(
    tmp_path: Path,
    operation: PinnedAuthorityOperation,
    frontend: OperationFrontendProjection,
    recorded: str,
) -> None:
    """The stored reconciliation record names the label the executor derived."""
    definition_id = MODELO_RECONCILIATION_IMPORT_OPERATION_DEFINITION_ID
    with conformance._runtime(
        tmp_path / "runtime",
        cleanup=conformance._CloseWitness(),
        execution_caller_reader=_session_host(definition_id, frontend),
    ) as (driver, _registry, profile_id):
        with override_settings(cadrumo_active_profile=str(profile_id)):
            unit = modelo_operation_test_support.seeded_modelo_work_unit(profile_id, operation=operation)
            records_before = tuple(ModeloReconciliationPersistence().iter_records())
            request = ModeloReconciliationImportRequest(
                profile_id=profile_id,
                work_unit_id=unit.work_unit_id,
                source_kind=ModeloReconciliationEvidenceKind.JUSTIFICANTE,
                source_path=str(_JUSTIFICANTE_FIXTURE),
                actor=_TYPED_ACTOR,
            )

            _submitted, observed = asyncio.run(
                driver.run(
                    definition_id=definition_id,
                    subject_ref=profile_operation_subject(str(profile_id)),
                    payload=request,
                )
            )
            records_after = tuple(ModeloReconciliationPersistence().iter_records())

        assert observed.projection.terminal_condition is OperationTerminalCondition.SUCCEEDED
        assert observed.projection.effect is OperationEffect.UPDATED
        assert len(records_after) == len(records_before) + 1
        assert records_after[-1].actor == recorded


@_FRONTENDS
def test_reconciliation_pull_records_the_session_label_for_an_agent(
    tmp_path: Path,
    operation: PinnedAuthorityOperation,
    frontend: OperationFrontendProjection,
    recorded: str,
) -> None:
    """The stored reconciliation record of a captured receipt names the derived label."""
    definition_id = MODELO_RECONCILIATION_PULL_OPERATION_DEFINITION_ID
    with conformance._runtime(
        tmp_path / "runtime",
        cleanup=conformance._CloseWitness(),
        execution_caller_reader=_session_host(definition_id, frontend),
    ) as (driver, _registry, profile_id):
        with override_settings(cadrumo_active_profile=str(profile_id)):
            unit = modelo_operation_test_support.seeded_modelo_work_unit(profile_id, operation=operation)
            pdf = _JUSTIFICANTE_FIXTURE.read_bytes()
            snapshot = build_justificante_capture_service(str(profile_id)).capture(
                modelo=str(unit.modelo),
                filing_year=unit.filing_year,
                period=unit.period,
                expediente_id="202413000000001Z",
                csv="ABCD1234EFGH",
                pdf_bytes=pdf,
                pdf_sha256=sha256_hex(pdf),
                captured_at=datetime(2026, 9, 29, tzinfo=UTC),
            )
            records_before = tuple(ModeloReconciliationPersistence().iter_records())
            request = ModeloReconciliationPullRequest(
                profile_id=profile_id,
                work_unit_id=unit.work_unit_id,
                snapshot_id=snapshot.snapshot_id,
                actor=_TYPED_ACTOR,
            )

            _submitted, observed = asyncio.run(
                driver.run(
                    definition_id=definition_id,
                    subject_ref=profile_operation_subject(str(profile_id)),
                    payload=request,
                )
            )
            records_after = tuple(ModeloReconciliationPersistence().iter_records())

        assert observed.projection.terminal_condition is OperationTerminalCondition.SUCCEEDED
        assert observed.projection.effect is OperationEffect.UPDATED
        assert len(records_after) == len(records_before) + 1
        assert records_after[-1].actor == recorded


_PERSON_INVOICE_ACTOR = "runtime"
_INVOICE_FRONTENDS = pytest.mark.parametrize(
    ("frontend", "recorded"),
    [(_MCP, _AGENT_LABEL), (_CLI, _PERSON_INVOICE_ACTOR)],
    ids=["mcp", "cli"],
)


@_INVOICE_FRONTENDS
def test_invoice_add_records_the_session_label_for_an_agent(
    tmp_path: Path,
    operation: PinnedAuthorityOperation,
    frontend: OperationFrontendProjection,
    recorded: str,
) -> None:
    """The creation event of an added invoice names the derived label; a person's frontend keeps its own."""
    definition_id = "ledger.invoice.add"
    with conformance._runtime(
        tmp_path / "runtime",
        cleanup=conformance._CloseWitness(),
        execution_caller_reader=_session_host(definition_id, frontend),
    ) as (driver, registry, profile_id):
        definition = {item.definition_id: item for item in registry.definitions}[definition_id]
        submission = conformance._seeded_conformance_submission(
            definition, profile_id=profile_id, tmp_path=tmp_path, operation=operation
        )

        submitted, observed = asyncio.run(
            driver.run(definition_id=definition_id, subject_ref=submission.subject_ref, payload=submission.payload)
        )

        assert observed.projection.terminal_condition is OperationTerminalCondition.SUCCEEDED
        result = conformance._resolve_result_projection(
            driver,
            registry,
            definition_id=definition_id,
            operation_id=submitted.receipt.operation_id,
            terminal_revision=observed.projection.revision,
            projection_type=InvoiceAddResult,
        )
        assert isinstance(result, InvoiceAddResult)
        assert _event_actors(profile_id, result.bucket_event_ids) == {recorded}


@_INVOICE_FRONTENDS
def test_invoice_update_records_the_session_label_for_an_agent(
    tmp_path: Path,
    operation: PinnedAuthorityOperation,
    frontend: OperationFrontendProjection,
    recorded: str,
) -> None:
    """The correction event of an updated invoice names the derived label; a person's frontend keeps its own."""
    definition_id = "ledger.invoice.update"
    with conformance._runtime(
        tmp_path / "runtime",
        cleanup=conformance._CloseWitness(),
        execution_caller_reader=_session_host(definition_id, frontend),
    ) as (driver, registry, profile_id):
        definition = {item.definition_id: item for item in registry.definitions}[definition_id]
        submission = conformance._seeded_conformance_submission(
            definition, profile_id=profile_id, tmp_path=tmp_path, operation=operation
        )

        submitted, observed = asyncio.run(
            driver.run(definition_id=definition_id, subject_ref=submission.subject_ref, payload=submission.payload)
        )

        assert observed.projection.terminal_condition is OperationTerminalCondition.SUCCEEDED
        result = conformance._resolve_result_projection(
            driver,
            registry,
            definition_id=definition_id,
            operation_id=submitted.receipt.operation_id,
            terminal_revision=observed.projection.revision,
            projection_type=InvoiceUpdateResult,
        )
        assert isinstance(result, InvoiceUpdateResult)
        assert _event_actors(profile_id, result.bucket_event_ids) == {recorded}

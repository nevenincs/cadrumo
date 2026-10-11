"""An evidence update, a typed invoice entry and an extraction, run on each frontend through the real executors.

The production registry and the real executors run over a stored profile with
a session host that answers for the frontend that admitted the invocation.
Each operation settles with the same result on the command line, the terminal
interface and MCP: the update result carries the stored record whole, and the
extraction result carries the full draft. What an agent's write records
carries its session's label; a person's carries the frontend's own.
"""

from __future__ import annotations

import asyncio
from pathlib import Path
from uuid import UUID

import pytest

from ...application.bucket_event_repository import bucket_event_history_repository
from ...application.invoices.catalogue_intake_contracts import InvoiceWizardOutcome, InvoiceWizardRequest
from ...application.ledger.evidence import PurchaseInvoiceEvidenceService
from ...application.ledger.evidence_mutation_operation import (
    LedgerEvidenceUpdatePatch,
    LedgerEvidenceUpdateProjection,
    LedgerEvidenceUpdateRequest,
)
from ...application.ledger.invoice_evidence_extract_operation import LedgerEvidenceExtractProjection
from ...application.operations.execution_actor import OperationExecutionCaller, OperationExecutionCallerReader
from ...application.operations.models import OperationIdentity
from ...application.operations.registry import OperationFrontendProjection
from ...application.user_profile.access_contracts import SessionKind
from ...core.operations import OperationTerminalCondition, profile_operation_subject
from ...domain.calculations.registry.authority import PinnedAuthorityOperation
from ..adapter_composition import build_ledger_evidence_ports
from . import test_registered_executor_conformance as conformance
from .invoice_evidence_operation_test_support import prepare_invoice_evidence_conformance_case

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint]

_MCP = OperationFrontendProjection.MCP
_CLI = OperationFrontendProjection.CLI
_TUI = OperationFrontendProjection.TUI
_SESSION_CLIENT = UUID("5aa00000-0000-4000-8000-0000000000dd")
_AGENT_LABEL = f"agent:mcp.attended.{_SESSION_CLIENT}"
_PERSON_LABEL = "cli"
_FRONTENDS = pytest.mark.parametrize(
    ("frontend", "recorded"),
    [(_MCP, _AGENT_LABEL), (_CLI, _PERSON_LABEL), (_TUI, _PERSON_LABEL)],
    ids=["mcp", "cli", "tui"],
)
_MINIMAL_PDF = b"%PDF-1.4\n1 0 obj<</Type/Catalog>>endobj\ntrailer<</Root 1 0 R>>\n%%EOF\n"


def _session_host(definition_id: str, frontend: OperationFrontendProjection) -> OperationExecutionCallerReader:
    """What a session host answers for an invocation of ``definition_id`` it admitted on ``frontend``."""

    def read(identity: OperationIdentity) -> OperationExecutionCaller:
        assert identity.definition_id == definition_id
        return OperationExecutionCaller(frontend=frontend, session_kind=SessionKind.ATTENDED, client_id=_SESSION_CLIENT)

    return read


def _actors_of(profile_id: UUID, *, object_id: str) -> set[str]:
    events = bucket_event_history_repository(bucket_id=str(profile_id)).load().events
    return {event.actor for event in events.values() if event.object_id == object_id}


@_FRONTENDS
def test_evidence_update_records_who_acted_and_returns_the_stored_record_whole_on_every_frontend(
    tmp_path: Path,
    frontend: OperationFrontendProjection,
    recorded: str,
) -> None:
    """The replacement event names the derived label; the result and the stored record keep the typed path."""
    definition_id = "ledger.evidence.update"
    with conformance._runtime(
        tmp_path / "runtime",
        cleanup=conformance._CloseWitness(),
        execution_caller_reader=_session_host(definition_id, frontend),
    ) as (driver, registry, profile_id):
        source_directory = tmp_path / "typed-by-the-person"
        source_directory.mkdir()
        source = source_directory / "synthetic-purchase-invoice.pdf"
        source.write_bytes(_MINIMAL_PDF)
        service = PurchaseInvoiceEvidenceService(ports=build_ledger_evidence_ports(bucket_id=str(profile_id)))
        added = service.add(bucket_id=str(profile_id), source_path=source).record
        request = LedgerEvidenceUpdateRequest(
            profile_id=profile_id,
            evidence_id=added.evidence_id,
            patch=LedgerEvidenceUpdatePatch(supplier="Synthetic Supplier SL", taxable_base="100.5"),
            patch_fields=("supplier", "taxable_base"),
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
            projection_type=LedgerEvidenceUpdateProjection,
        )
        stored = service.view(bucket_id=str(profile_id), evidence_id=added.evidence_id)
        replaced = bucket_event_history_repository(bucket_id=str(profile_id)).load().events

        assert {replaced[event_id].actor for event_id in result.bucket_event_ids} == {recorded}
        assert (result.record.supplier, result.record.taxable_base) == ("Synthetic Supplier SL", "100.5")
        assert result.record.source_path == added.source_path
        assert source_directory.name in result.model_dump_json()
        assert (stored.source_path, stored.attachment_id, stored.source_sha256) == (
            added.source_path,
            added.attachment_id,
            added.source_sha256,
        )
        assert stored.supplier == "Synthetic Supplier SL"


@_FRONTENDS
def test_a_typed_invoice_entry_records_who_made_it(
    tmp_path: Path,
    operation: PinnedAuthorityOperation,
    frontend: OperationFrontendProjection,
    recorded: str,
) -> None:
    """The creation event of an invoice entered through the wizard names the derived label."""
    definition_id = "ledger.invoice.wizard"
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
        assert isinstance(preparation.request, InvoiceWizardRequest)

        submitted, observed = asyncio.run(
            driver.run(definition_id=definition_id, subject_ref=preparation.subject_ref, payload=preparation.request)
        )

        assert observed.projection.terminal_condition is OperationTerminalCondition.SUCCEEDED
        outcome = conformance._resolve_result_projection(
            driver,
            registry,
            definition_id=definition_id,
            operation_id=submitted.receipt.operation_id,
            terminal_revision=observed.projection.revision,
            projection_type=InvoiceWizardOutcome,
        )
        assert outcome.outcome == "succeeded" and outcome.result is not None
        assert outcome.result.already_existed is False
        assert _actors_of(profile_id, object_id=outcome.result.invoice.invoice_id) == {recorded}


@pytest.mark.parametrize("frontend", [_MCP, _CLI, _TUI], ids=["mcp", "cli", "tui"])
def test_an_extraction_seals_the_full_draft_whichever_frontend_submits_it(
    tmp_path: Path,
    operation: PinnedAuthorityOperation,
    frontend: OperationFrontendProjection,
) -> None:
    """The same stored document is read on this machine, and the whole reading is sealed for every caller."""
    definition_id = "ledger.evidence.extract"
    with (
        conformance._model_runtime_for(definition_id),
        conformance._runtime(
            tmp_path / "runtime",
            cleanup=conformance._CloseWitness(),
            execution_caller_reader=_session_host(definition_id, frontend),
        ) as (driver, registry, profile_id),
    ):
        case = prepare_invoice_evidence_conformance_case(definition_id, profile_id=profile_id, operation=operation)
        expected = case.expected_read
        assert isinstance(expected, LedgerEvidenceExtractProjection)

        submitted, observed = asyncio.run(
            driver.run(
                definition_id=definition_id,
                subject_ref=profile_operation_subject(str(profile_id)),
                payload=case.request,
            )
        )

        assert observed.projection.terminal_condition is OperationTerminalCondition.SUCCEEDED
        result = conformance._resolve_result_projection(
            driver,
            registry,
            definition_id=definition_id,
            operation_id=submitted.receipt.operation_id,
            terminal_revision=observed.projection.revision,
            projection_type=LedgerEvidenceExtractProjection,
        )
        assert result == expected
        assert result.draft.provenance

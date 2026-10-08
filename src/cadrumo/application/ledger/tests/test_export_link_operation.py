"""Canonical export/link effects and disclosure; synthetic inward repositories only."""

from __future__ import annotations

import asyncio
from collections.abc import Iterator
from dataclasses import replace
from pathlib import Path
from uuid import uuid4

import pytest
from pydantic import BaseModel

from ....core.config import override_settings
from ....core.hashing import sha256_hex
from ....core.operations import OperationEffect, OperationTerminalCondition, profile_operation_subject
from ....core.time.clock import now
from ....domain.calculations.registry.authority import PinnedAuthorityOperation
from ....domain.invoices.models import InvoiceCatalogue
from ...modelo.tests.m036_operation_support import PROFILE_ID as POLICY_PROFILE_ID
from ...modelo.tests.m036_operation_support import policy_decision
from ...operations.access_resolution import OperationAccessContext, resolve_operation_access
from ...operations.models import OperationIdentity, OperationRequest, OperationTerminalReceipt
from ...operations.operation_definition import OperationDefinition
from ...operations.public_period import PublicPeriod
from ...operations.refusal_evidence import OperationRefusalEvidence
from ...operations.registry import OperationFrontendProjection, OperationRegistry
from ...user_profile.access_contracts import (
    AccessAction,
    AccessAllowed,
    AccessDenialCode,
    AccessDenied,
    Availability,
    DisclosureCategory,
)
from ...user_profile.access_errors import ProfileAccessRefusedError
from ..action_ports import LedgerActionPorts
from ..export_operation import (
    LedgerExportExecutionResult,
    LedgerExportRequest,
    build_ledger_export_definition,
    build_ledger_export_registration,
)
from ..link_operation import (
    LEDGER_LINK_VALIDATION_REFUSAL_CODE,
    LedgerLinkExecutionResult,
    LedgerLinkRequest,
    build_ledger_link_definition,
    build_ledger_link_registration,
)
from ..persistence_ports import LedgerPersistenceConflictError
from .bulk_classify_operation_support import PROFILE_ID
from .export_link_operation_support import Subject

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]


def _definition(subject: Subject, kind: str) -> OperationDefinition:
    def factory(*, bucket_id: str, operation: PinnedAuthorityOperation) -> LedgerActionPorts:
        assert bucket_id == str(PROFILE_ID) and operation is subject.operation and not subject.fence.active
        return subject.ports

    return build_ledger_export_definition(factory) if kind == "export" else build_ledger_link_definition(factory)


def _request(definition: OperationDefinition, payload: BaseModel) -> OperationRequest[BaseModel]:
    return OperationRequest[BaseModel](
        definition_id=definition.definition_id, subject_ref=profile_operation_subject(str(PROFILE_ID)), payload=payload
    )


def _receipt(definition: OperationDefinition, *, refusal: bool = False) -> OperationTerminalReceipt:
    return OperationTerminalReceipt(
        identity=OperationIdentity(
            operation_id="a" * 64,
            definition_id=definition.definition_id,
            subject_ref=profile_operation_subject(str(PROFILE_ID)),
        ),
        revision=1,
        settled_at=now(),
        condition=OperationTerminalCondition.REFUSED if refusal else OperationTerminalCondition.SUCCEEDED,
        effect=OperationEffect.NONE if refusal else OperationEffect.UPDATED,
        result_ref=None if refusal else "d" * 64,
        refusal_ref=LEDGER_LINK_VALIDATION_REFUSAL_CODE if refusal else None,
        refusal_detail_ref="d" * 64 if refusal else None,
    )


@pytest.fixture
def subject(authority_operation: PinnedAuthorityOperation) -> Iterator[Subject]:
    with override_settings(cadrumo_active_profile=str(PROFILE_ID)):
        yield Subject(authority_operation)


def test_both_strict_public_contracts_compile_and_share_no_artifact_agent_purpose(subject: Subject) -> None:
    definitions = tuple(
        sorted((_definition(subject, "link"), _definition(subject, "export")), key=lambda item: item.definition_id)
    )
    registrations = tuple(
        build_ledger_export_registration(row)
        if row.definition_id == "ledger.export"
        else build_ledger_link_registration(row)
        for row in definitions
    )
    registry = OperationRegistry(definitions=definitions, public_registrations=registrations)
    assert registry.lookup_public_registration("ledger.export").contract.result_schema is not None
    assert OperationFrontendProjection.MCP not in definitions[0].permitted_frontends
    assert OperationFrontendProjection.MCP in definitions[1].permitted_frontends
    assert all(row.capabilities.request_storage.value == "secure_reference" for row in definitions)


@pytest.mark.parametrize("mode", ["normal", "conflict", "uncertain"])
def test_export_fences_real_file_then_guarded_event_and_preserves_effects(
    subject: Subject, tmp_path: Path, mode: str
) -> None:
    subject.repository.mode = mode
    target = tmp_path / "ledger.csv"
    definition = _definition(subject, "export")
    payload = LedgerExportRequest(profile_id=PROFILE_ID, output_path=str(target))
    request = _request(definition, payload)
    task = definition.executor_factory.create().execute(request, subject.context(definition.definition_id))
    if mode == "normal":
        asyncio.run(task)
        retained = subject.operands.values[0]
        assert isinstance(retained, LedgerExportExecutionResult)
        projection = retained.projection
        assert projection.sha256 == sha256_hex(target.read_bytes()) and projection.byte_size == target.stat().st_size
        assert projection.row_count == 1 and projection.rows[0].transaction_id == subject.transaction.transaction_id
        assert (
            projection.rows[0].notes == ""
            and projection.rows[0].iva_amount == ""
            and projection.rows[0].amount == "10.00"
        )
        assert "payload" not in projection.model_dump()
        assert len(subject.events.load().events) == 1 and subject.repository.commits == 1
        registration = build_ledger_export_registration(definition)
        assert registration.result_projector is not None
        assert registration.result_projector(retained, _receipt(definition)) == projection
        with pytest.raises(ValueError):
            registration.result_projector(
                retained, _receipt(definition).model_copy(update={"effect": OperationEffect.PARTIAL})
            )
        assert subject.effects.effects[-1] is OperationEffect.UPDATED
    else:
        with pytest.raises(LedgerPersistenceConflictError if mode == "conflict" else OSError):
            asyncio.run(task)
        assert target.is_file() and not subject.operands.values
        assert subject.effects.effects[-1] is (
            OperationEffect.PARTIAL if mode == "conflict" else OperationEffect.UNKNOWN
        )
        assert len(subject.events.load().events) == (0 if mode == "conflict" else 1)
    assert not subject.fence.active


def test_denied_artifact_writer_creates_no_file_or_event(subject: Subject, tmp_path: Path) -> None:
    subject.fence.deny = True
    target = tmp_path / "ledger.csv"
    definition = _definition(subject, "export")
    request = _request(definition, LedgerExportRequest(profile_id=PROFILE_ID, output_path=str(target)))
    with pytest.raises(ProfileAccessRefusedError):
        asyncio.run(definition.executor_factory.create().execute(request, subject.context(definition.definition_id)))
    assert not target.exists() and not subject.events.load().events and subject.repository.commits == 0
    assert subject.effects.effects[-1] is OperationEffect.NONE


@pytest.mark.parametrize("mode", ["normal", "conflict", "uncertain"])
def test_link_single_atomic_writer_returns_full_quintet_or_truthful_failure(subject: Subject, mode: str) -> None:
    subject.repository.mode = mode
    definition = _definition(subject, "link")
    payload = LedgerLinkRequest(
        profile_id=PROFILE_ID,
        transaction_id=subject.transaction.transaction_id[:12],
        invoice_id=subject.invoice.invoice_id,
    )
    request = _request(definition, payload)
    task = definition.executor_factory.create().execute(request, subject.context(definition.definition_id))
    if mode == "normal":
        asyncio.run(task)
        retained = subject.operands.values[0]
        assert isinstance(retained, LedgerLinkExecutionResult) and retained.result.projection is not None
        projection = retained.result.projection
        assert (
            projection.bucket_id == str(PROFILE_ID) and projection.transaction_id == subject.transaction.transaction_id
        )
        assert projection.transaction.invoice_id == subject.invoice.invoice_id and projection.review_status is not None
        assert len(projection.bucket_event_ids) == 1 and projection.bucket_event_ids[0] in subject.events.load().events
        invoice = subject.invoices.load().get(subject.invoice.invoice_id)
        assert invoice is not None and subject.transaction.transaction_id in invoice.linked_transaction_ids
        assert subject.repository.commits == 1 and subject.fence.entries == 1
        registration = build_ledger_link_registration(definition)
        assert registration.result_projector is not None
        assert registration.result_projector(retained, _receipt(definition)) == retained.result
        with pytest.raises(ValueError):
            registration.result_projector(
                retained, _receipt(definition).model_copy(update={"effect": OperationEffect.UNKNOWN})
            )
    else:
        with pytest.raises(LedgerPersistenceConflictError if mode == "conflict" else OSError):
            asyncio.run(task)
        assert not subject.operands.values
        assert subject.effects.effects[-1] is (OperationEffect.NONE if mode == "conflict" else OperationEffect.UNKNOWN)
        assert subject.repository.commits == (0 if mode == "conflict" else 1)


@pytest.mark.parametrize("reason", ["missing_invoice", "cross_bucket_invoice"])
def test_operator_invoice_refusal_retains_only_closed_no_write_facts(subject: Subject, reason: str) -> None:
    if reason == "missing_invoice":
        subject.invoices._catalogue = InvoiceCatalogue()
    else:
        foreign = subject.invoice.model_copy(update={"bucket_id": str(uuid4())})
        subject.invoices._catalogue = InvoiceCatalogue(invoices={foreign.invoice_id: foreign})
    definition = _definition(subject, "link")
    request = _request(
        definition,
        LedgerLinkRequest(
            profile_id=PROFILE_ID,
            transaction_id=subject.transaction.transaction_id[:12],
            invoice_id=subject.invoice.invoice_id,
        ),
    )
    evidence = asyncio.run(
        definition.executor_factory.create().execute(request, subject.context(definition.definition_id))
    )
    assert (
        isinstance(evidence, OperationRefusalEvidence) and evidence.refusal_code == LEDGER_LINK_VALIDATION_REFUSAL_CODE
    )
    retained = subject.operands.values[0]
    assert (
        isinstance(retained, LedgerLinkExecutionResult)
        and retained.result.reason == reason
        and retained.result.projection is None
    )
    assert (
        not subject.events.load().events
        and subject.repository.commits == 0
        and subject.effects.effects[-1] is OperationEffect.NONE
    )
    assert "counterparty" not in retained.model_dump_json() and "invoice_bucket_id" not in retained.model_dump_json()
    registration = build_ledger_link_registration(definition)
    assert registration.result_projector is not None
    assert registration.result_projector(retained, _receipt(definition, refusal=True)) == retained.result
    with pytest.raises(ValueError):
        registration.result_projector(
            retained, _receipt(definition, refusal=True).model_copy(update={"effect": OperationEffect.UNKNOWN})
        )


def test_guarded_invoice_owner_recheck_refuses_changed_snapshot_before_atomic_writer(
    subject: Subject, monkeypatch: pytest.MonkeyPatch
) -> None:
    foreign = subject.invoice.model_copy(update={"bucket_id": str(uuid4())})
    changed = InvoiceCatalogue(invoices={foreign.invoice_id: foreign})

    def revised_invoice() -> tuple[InvoiceCatalogue, str]:
        assert not subject.fence.active
        return changed, "0" * 64

    monkeypatch.setattr(subject.invoices, "load_revisioned", revised_invoice)
    definition = _definition(subject, "link")
    request = _request(
        definition,
        LedgerLinkRequest(
            profile_id=PROFILE_ID,
            transaction_id=subject.transaction.transaction_id,
            invoice_id=subject.invoice.invoice_id,
        ),
    )
    evidence = asyncio.run(
        definition.executor_factory.create().execute(request, subject.context(definition.definition_id))
    )
    assert isinstance(evidence, OperationRefusalEvidence)
    retained = subject.operands.values[0]
    assert isinstance(retained, LedgerLinkExecutionResult) and retained.result.reason == "cross_bucket_invoice"
    assert subject.repository.attempts == 0 and not subject.events.load().events


@pytest.mark.parametrize("kind", ["export", "link"])
def test_foreign_worker_subject_refuses_before_private_ports(subject: Subject, tmp_path: Path, kind: str) -> None:
    definition = _definition(subject, kind)
    foreign = uuid4()
    payload = (
        LedgerExportRequest(profile_id=foreign, output_path=str(tmp_path / "private.csv"))
        if kind == "export"
        else LedgerLinkRequest(
            profile_id=foreign, transaction_id=subject.transaction.transaction_id, invoice_id=subject.invoice.invoice_id
        )
    )
    with pytest.raises(ProfileAccessRefusedError) as raised:
        asyncio.run(
            definition.executor_factory.create().execute(
                _request(definition, payload), subject.context(definition.definition_id)
            )
        )
    assert (
        raised.value.reason is AccessDenialCode.PROFILE_MISMATCH
        and subject.repository.attempts == 0
        and not subject.operands.values
    )


@pytest.mark.parametrize("kind", ["export", "link"])
def test_exact_scope_human_artifact_and_dual_category_consent(subject: Subject, tmp_path: Path, kind: str) -> None:
    definition = _definition(subject, kind)
    registration = (
        build_ledger_export_registration(definition) if kind == "export" else build_ledger_link_registration(definition)
    )
    registry = OperationRegistry(definitions=(definition,), public_registrations=(registration,))
    payload = (
        LedgerExportRequest(
            profile_id=POLICY_PROFILE_ID,
            output_path=str(tmp_path / "ledger.csv"),
            period=PublicPeriod(filing_year=2024, code="2T"),
        )
        if kind == "export"
        else LedgerLinkRequest(
            profile_id=POLICY_PROFILE_ID,
            transaction_id=subject.transaction.transaction_id[:12],
            invoice_id=subject.invoice.invoice_id,
        )
    )
    request = OperationRequest[BaseModel](
        definition_id=definition.definition_id,
        subject_ref=profile_operation_subject(str(POLICY_PROFILE_ID)),
        payload=payload,
    )
    context = OperationAccessContext(
        profile_id=POLICY_PROFILE_ID,
        destination_id=uuid4(),
        action=AccessAction.RESULT,
        frontend=OperationFrontendProjection.CLI,
        contract=registration.contract,
        published_authority=Availability.AVAILABLE,
        authority_operation=subject.operation,
    )
    resolved = resolve_operation_access(registry=registry, request=request, context=context)
    assert resolved.policy.requires_all_periods is (kind == "link")
    assert resolved.policy.requires_human is (kind == "export")
    assert {row.category for row in resolved.policy.disclosures} == {
        DisclosureCategory.PROFILE_VALUES,
        DisclosureCategory.TAX_VALUES,
    }
    assert isinstance(
        policy_decision(resolved, registry, disclosures=resolved.policy.disclosures, human=kind == "export"),
        AccessAllowed,
    )
    for missing in (DisclosureCategory.PROFILE_VALUES, DisclosureCategory.TAX_VALUES):
        denied = policy_decision(
            resolved,
            registry,
            disclosures=frozenset(row for row in resolved.policy.disclosures if row.category is not missing),
            human=kind == "export",
        )
        assert isinstance(denied, AccessDenied) and denied.code is AccessDenialCode.DISCLOSURE_DENIED
    observed = resolve_operation_access(
        registry=registry, request=request, context=replace(context, action=AccessAction.OBSERVE)
    )
    assert {row.category for row in observed.policy.disclosures} == {DisclosureCategory.OPERATION_METADATA}
    if kind == "export":
        with pytest.raises(ProfileAccessRefusedError):
            resolve_operation_access(
                registry=registry, request=request, context=replace(context, frontend=OperationFrontendProjection.MCP)
            )
        denied = policy_decision(resolved, registry, disclosures=resolved.policy.disclosures)
        assert isinstance(denied, AccessDenied) and denied.code is AccessDenialCode.HUMAN_AUTHORITY_REQUIRED

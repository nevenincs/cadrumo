"""Closed schemas, exact-profile intake, and actual commit/no-op handoffs."""

from __future__ import annotations

import asyncio
from collections.abc import Callable
from contextlib import asynccontextmanager
from dataclasses import replace
from datetime import UTC, datetime
from pathlib import Path
from types import SimpleNamespace
from typing import cast
from uuid import UUID, uuid4

import pytest
from pydantic import BaseModel

from ....core.hashing import sha256_hex
from ....core.operations import OperationEffect, OperationTerminalCondition, profile_operation_subject
from ....domain.buckets.event import BucketEvent
from ....domain.calculations.registry.authority import PinnedAuthorityOperation
from ....domain.invoices.errors import InvoiceValidationError
from ....domain.invoices.models import InvoiceCatalogue
from ....domain.iva.classification import InvoiceKind
from ...operations import profile_guard
from ...operations.access_resolution import OperationAccessContext, resolve_operation_access
from ...operations.models import OperationIdentity, OperationRequest, OperationTerminalReceipt
from ...operations.owner import OperationExecutorContext
from ...operations.refusal_evidence import OperationRefusalEvidence
from ...operations.registry import OperationFrontendProjection, OperationRegistry
from ...user_profile.access_contracts import AccessAction, Availability
from ...user_profile.access_errors import ProfileAccessRefusedError
from .. import catalogue_intake_contracts as intake_contracts
from .. import catalogue_intake_operation as intake_operation
from ..catalogue_creation_ports import CatalogueInvoiceAuditCommitPort
from ..catalogue_intake_executor import InvoiceIntakeExecutor
from ..catalogue_intake_operation_ports import (
    InvoiceIntakeCommit,
    InvoiceIntakeCommitConflictError,
    InvoiceIntakePorts,
    InvoiceIntakeProviderAdmission,
)
from ..catalogue_intake_projection import project_invoice_intake_result
from ..catalogue_intake_refusal import INVOICE_WIZARD_VALIDATION_REFUSAL_CODE
from ._catalogue_creation_fakes import in_memory_catalogue_creation_ports

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]
_PROFILE = UUID("29292929-2929-4292-8292-292929292929")


class _Events:
    def __init__(self) -> None:
        self.phases: list[str] = []
        self.effects: list[OperationEffect] = []

    async def phase(self, phase: str) -> None:
        self.phases.append(phase)

    async def effect(self, effect: OperationEffect) -> None:
        self.effects.append(effect)


class _Operands:
    def __init__(self) -> None:
        self.value: BaseModel | None = None

    async def put(self, value: BaseModel, *, written_at: datetime) -> str:
        assert written_at.tzinfo is not None
        self.value = value
        return "d" * 64


class _Fence:
    def __init__(self) -> None:
        self.inside = False

    @asynccontextmanager
    async def irreversible_section(self):
        assert not self.inside
        self.inside = True
        try:
            yield
        finally:
            self.inside = False


class _PreparedFakeCommit:
    """An application fake; physical preparation/CAS has separate adapter tests."""

    def __init__(
        self,
        delegate: CatalogueInvoiceAuditCommitPort,
        commit: InvoiceIntakeCommit,
        fence: _Fence,
        *,
        conflict: bool = False,
        failure: bool = False,
    ) -> None:
        self.delegate, self.commit, self.fence = delegate, commit, fence
        self.conflict, self.failure = conflict, failure

    def mutate_with_event(
        self, mutation: Callable[[InvoiceCatalogue], InvoiceCatalogue], event: BucketEvent, *, attempts: int = 4
    ) -> InvoiceCatalogue:
        result: InvoiceCatalogue | None = None

        def save() -> None:
            nonlocal result
            assert self.fence.inside
            if self.conflict:
                raise InvoiceIntakeCommitConflictError("synthetic atomic refusal")
            if self.failure:
                raise OSError("synthetic uncertain handoff")
            result = self.delegate.mutate_with_event(mutation, event, attempts=attempts)

        self.commit(save)
        assert result is not None
        return result


def _wire(payload: BaseModel, definition_id: str) -> OperationRequest[BaseModel]:
    return OperationRequest[BaseModel](
        definition_id=definition_id, subject_ref=profile_operation_subject(str(_PROFILE)), payload=payload
    )


def _context(request: OperationRequest[BaseModel], operation: PinnedAuthorityOperation):
    events, operands, fence = _Events(), _Operands(), _Fence()
    context = cast(
        OperationExecutorContext,
        cast(
            object,
            SimpleNamespace(
                identity=OperationIdentity(
                    operation_id="a" * 64, definition_id=request.definition_id, subject_ref=request.subject_ref
                ),
                authority_operation=operation,
                events=events,
                operands=operands,
                cancellation=fence,
            ),
        ),
    )
    return context, events, operands, fence


def _wizard() -> intake_contracts.InvoiceWizardRequest:
    return intake_contracts.InvoiceWizardRequest(
        profile_id=_PROFILE,
        kind=InvoiceKind.RECEIVED,
        counterparty_nif="A58818501",
        counterparty_name="Synthetic supplier",
        invoice_number="WIZARD-1",
        invoice_date="2026-05-01",
        taxable_base="100.00",
        iva_rate="21",
        currency="EUR",
        country_code="ES",
        series="S",
        recargo_amount="5.20",
    )


def test_both_public_contracts_compile_without_constructing_storage(
    authority_operation: PinnedAuthorityOperation, tmp_path: Path
) -> None:
    def unused(**_kwargs: object) -> InvoiceIntakePorts:
        pytest.fail("schema compilation constructed profile capabilities")

    for definition in (
        intake_operation.build_invoice_import_definition(unused),
        intake_operation.build_invoice_wizard_definition(unused),
    ):
        registration = intake_operation.build_invoice_intake_registration(definition)
        registry = OperationRegistry(definitions=(definition,), public_registrations=(registration,))
        contract = registry.lookup_public_contract(definition.definition_id)
        assert contract.request_schema is not None and contract.result_schema is not None
        payload = (
            _wizard()
            if definition.definition_id == intake_contracts.INVOICE_WIZARD_OPERATION_DEFINITION_ID
            else intake_contracts.InvoiceImportRequest(
                profile_id=_PROFILE,
                kind=InvoiceKind.RECEIVED,
                source_path=str(tmp_path / "book.csv"),
                source_sha256="e" * 64,
            )
        )
        request = _wire(payload, definition.definition_id)
        context = OperationAccessContext(
            profile_id=_PROFILE,
            destination_id=uuid4(),
            action=AccessAction.SUBMIT,
            frontend=OperationFrontendProjection.CLI,
            contract=registration.contract,
            published_authority=Availability.AVAILABLE,
            authority_operation=authority_operation,
        )
        access = resolve_operation_access(registry=registry, request=request, context=context)
        assert access.policy.requires_all_periods and AccessAction.COMMIT in access.policy.actions
        assert definition.permitted_frontends == frozenset({OperationFrontendProjection.CLI})
        assert definition.refusal_detail_codes == (
            frozenset({INVOICE_WIZARD_VALIDATION_REFUSAL_CODE})
            if isinstance(payload, intake_contracts.InvoiceWizardRequest)
            else frozenset()
        )
        with pytest.raises(ProfileAccessRefusedError):
            resolve_operation_access(registry=registry, request=request, context=replace(context, profile_id=uuid4()))


def test_wizard_worker_preserves_noop_and_fences_only_actual_commit(
    authority_operation: PinnedAuthorityOperation, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(profile_guard, "require_active_bucket_id", lambda: str(_PROFILE))
    creation = in_memory_catalogue_creation_ports()
    request = _wire(_wizard(), intake_contracts.INVOICE_WIZARD_OPERATION_DEFINITION_ID)
    for repeat in (False, True):
        context, events, operands, fence = _context(request, authority_operation)

        def factory(
            *,
            profile_id: UUID,
            operation: PinnedAuthorityOperation,
            commit: InvoiceIntakeCommit,
            admit_provider: InvoiceIntakeProviderAdmission,
            fence: _Fence = fence,
        ) -> InvoiceIntakePorts:
            assert operation is authority_operation and profile_id == _PROFILE
            assert not fence.inside
            ports = replace(creation, audit_commit=_PreparedFakeCommit(creation.audit_commit, commit, fence))
            return InvoiceIntakePorts(profile_id, operation, lambda: ports, lambda _headers: None, lambda: ())

        assert asyncio.run(InvoiceIntakeExecutor(factory).execute(request, context)) == "d" * 64
        assert isinstance(operands.value, intake_contracts.InvoiceIntakeExecutionResult)
        assert isinstance(operands.value.projection, intake_contracts.InvoiceWizardOutcome)
        assert operands.value.projection.outcome == "succeeded" and operands.value.projection.refusal is None
        result = operands.value.projection.result
        assert result is not None
        assert result.already_existed is repeat
        assert result.invoice.series == "S"
        assert events.effects[-1] is (OperationEffect.NONE if repeat else OperationEffect.UPDATED)
        assert (OperationEffect.UNKNOWN in events.effects) is not repeat
        receipt = OperationTerminalReceipt(
            identity=context.identity,
            revision=1,
            condition=OperationTerminalCondition.SUCCEEDED,
            effect=events.effects[-1],
            settled_at=datetime.now(UTC),
            result_ref="d" * 64,
        )
        assert project_invoice_intake_result(operands.value, receipt) == operands.value.projection
        wrong_effect = OperationEffect.UPDATED if repeat else OperationEffect.NONE
        with pytest.raises(ValueError, match="terminal receipt"):
            project_invoice_intake_result(operands.value, receipt.model_copy(update={"effect": wrong_effect}))
    assert len(creation.invoice_repository.load()) == 1 and len(creation.event_repository.load().events) == 1


def test_wizard_field_refusal_retains_order_and_correlates_only_prewrite_receipts(
    authority_operation: PinnedAuthorityOperation, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(profile_guard, "require_active_bucket_id", lambda: str(_PROFILE))
    payload = _wizard().model_copy(update={"counterparty_name": " ", "taxable_base": "invalid", "series": " "})
    request = _wire(payload, intake_contracts.INVOICE_WIZARD_OPERATION_DEFINITION_ID)
    context, events, operands, fence = _context(request, authority_operation)
    creation = in_memory_catalogue_creation_ports()

    def factory(
        *,
        profile_id: UUID,
        operation: PinnedAuthorityOperation,
        commit: InvoiceIntakeCommit,
        admit_provider: InvoiceIntakeProviderAdmission,
    ) -> InvoiceIntakePorts:
        def unexpected_admission(*_args: object) -> None:
            pytest.fail("canonical field refusal reached provider or actual commit")

        assert profile_id == _PROFILE and operation is authority_operation and not fence.inside
        ports = replace(creation, audit_commit=_PreparedFakeCommit(creation.audit_commit, unexpected_admission, fence))
        return InvoiceIntakePorts(profile_id, operation, lambda: ports, unexpected_admission, lambda: ())

    evidence = asyncio.run(InvoiceIntakeExecutor(factory).execute(request, context))
    assert isinstance(evidence, OperationRefusalEvidence)
    assert evidence.refusal_code == INVOICE_WIZARD_VALIDATION_REFUSAL_CODE and evidence.detail_ref == "d" * 64
    assert events.effects and all(effect is OperationEffect.NONE for effect in events.effects)
    assert len(creation.invoice_repository.load()) == 0 and not creation.event_repository.load().events
    assert isinstance(operands.value, intake_contracts.InvoiceIntakeExecutionResult)
    outcome = operands.value.projection
    assert isinstance(outcome, intake_contracts.InvoiceWizardOutcome)
    assert outcome.outcome == "refused" and outcome.result is None and outcome.refusal is not None
    assert tuple(row.field for row in outcome.refusal.field_errors) == ("counterparty_name", "taxable_base", "series")
    restored = outcome.refusal.to_validation_error()
    assert restored.context == outcome.refusal.presentation_context()
    assert restored.translated_message == "application.invoices.wizard.errors.field_errors"
    receipt = OperationTerminalReceipt(
        identity=context.identity,
        revision=1,
        condition=OperationTerminalCondition.REFUSED,
        effect=OperationEffect.NONE,
        settled_at=datetime.now(UTC),
        refusal_ref=evidence.refusal_code,
        refusal_detail_ref=evidence.detail_ref,
    )
    assert project_invoice_intake_result(operands.value, receipt) == outcome
    invalid_receipts = (
        receipt.model_copy(update={"condition": OperationTerminalCondition.SUCCEEDED}),
        receipt.model_copy(update={"effect": OperationEffect.UPDATED}),
        receipt.model_copy(update={"refusal_ref": "REFUSED_PROFILE_ACCESS"}),
        receipt.model_copy(update={"refusal_detail_ref": None}),
        receipt.model_copy(update={"result_ref": "e" * 64}),
        receipt.model_copy(update={"failure_error_code": "ERROR_INVOICE_VALIDATION"}),
        receipt.model_copy(update={"diagnostic_ref": "e" * 64}),
        receipt.model_copy(
            update={
                "identity": context.identity.model_copy(update={"subject_ref": profile_operation_subject(str(uuid4()))})
            }
        ),
        receipt.model_copy(
            update={
                "identity": context.identity.model_copy(
                    update={"definition_id": intake_contracts.INVOICE_IMPORT_OPERATION_DEFINITION_ID}
                )
            }
        ),
    )
    for invalid in invalid_receipts:
        with pytest.raises(ValueError, match="terminal receipt"):
            project_invoice_intake_result(operands.value, invalid)
    with pytest.raises(ValueError, match="terminal receipt"):
        project_invoice_intake_result(operands.value.model_copy(update={"effect": "updated"}), receipt)


def test_import_worker_retains_every_row_refusal_unmapped_header_and_repeat_noop(
    tmp_path: Path, authority_operation: PinnedAuthorityOperation, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(profile_guard, "require_active_bucket_id", lambda: str(_PROFILE))
    path = tmp_path / "synthetic.csv"
    source = b"counterparty_nif,counterparty_name,invoice_number,invoice_date,taxable_base,iva_rate,unused\nA58818501,Supplier,BOOK-1,2026-05-01,100.00,21,x\nA58818501,Supplier,BOOK-2,invalid,100.00,21,y\n"
    path.write_bytes(source)
    request = _wire(
        intake_contracts.InvoiceImportRequest(
            profile_id=_PROFILE,
            kind=InvoiceKind.RECEIVED,
            source_path=str(path),
            source_sha256=sha256_hex(source),
            country="ES",
        ),
        intake_contracts.INVOICE_IMPORT_OPERATION_DEFINITION_ID,
    )
    creation = in_memory_catalogue_creation_ports()
    for repeat in (False, True):
        context, events, operands, fence = _context(request, authority_operation)

        def factory(
            *,
            profile_id: UUID,
            operation: PinnedAuthorityOperation,
            commit: InvoiceIntakeCommit,
            admit_provider: InvoiceIntakeProviderAdmission,
            fence: _Fence = fence,
        ) -> InvoiceIntakePorts:
            def mapper(_headers):
                admit_provider()
                assert not fence.inside
                return None

            return InvoiceIntakePorts(
                profile_id,
                operation,
                lambda: replace(creation, audit_commit=_PreparedFakeCommit(creation.audit_commit, commit, fence)),
                mapper,
                lambda: ("synthetic mapping explanation",),
            )

        asyncio.run(InvoiceIntakeExecutor(factory).execute(request, context))
        assert isinstance(operands.value, intake_contracts.InvoiceIntakeExecutionResult)
        projection = operands.value.projection
        assert isinstance(projection, intake_contracts.InvoiceImportProjection)
        assert (
            projection.rows == 2
            and projection.created == int(not repeat)
            and projection.skipped_duplicate == int(repeat)
        )
        assert projection.refused[0].row_number == 3 and projection.refused[0].field == "invoice_date"
        assert projection.unmapped_column_headers == ("unused",) and projection.mapping_reasons == (
            "synthetic mapping explanation",
        )
        assert events.effects[-1] is (OperationEffect.NONE if repeat else OperationEffect.PARTIAL)
    invoice = next(iter(creation.invoice_repository.load().invoices.values()))
    assert invoice.provenance is not None and invoice.provenance.source_sha256 == sha256_hex(source)


@pytest.mark.parametrize("content", [b"unfamiliar,headers\n", b""])
def test_source_substitution_refuses_before_mapping_provider_or_write(
    tmp_path: Path, authority_operation: PinnedAuthorityOperation, monkeypatch: pytest.MonkeyPatch, content: bytes
) -> None:
    monkeypatch.setattr(profile_guard, "require_active_bucket_id", lambda: str(_PROFILE))
    path = tmp_path / "changed.csv"
    path.write_bytes(content)
    request = _wire(
        intake_contracts.InvoiceImportRequest(
            profile_id=_PROFILE, kind=InvoiceKind.RECEIVED, source_path=str(path), source_sha256="f" * 64, country="ES"
        ),
        intake_contracts.INVOICE_IMPORT_OPERATION_DEFINITION_ID,
    )
    context, events, operands, _fence = _context(request, authority_operation)

    def factory(
        *,
        profile_id: UUID,
        operation: PinnedAuthorityOperation,
        commit: InvoiceIntakeCommit,
        admit_provider: InvoiceIntakeProviderAdmission,
    ) -> InvoiceIntakePorts:
        def unavailable(*_args: object):
            pytest.fail("substituted source reached an outbound or storage capability")

        return InvoiceIntakePorts(profile_id, operation, unavailable, unavailable, lambda: ())

    with pytest.raises(InvoiceValidationError):
        asyncio.run(InvoiceIntakeExecutor(factory).execute(request, context))
    assert events.effects[-1] is OperationEffect.NONE and operands.value is None


@pytest.mark.parametrize("conflict", [True, False], ids=["atomic-cas-refusal", "uncertain-dispatch"])
def test_actual_save_failure_preserves_definitive_or_uncertain_effect(
    authority_operation: PinnedAuthorityOperation, monkeypatch: pytest.MonkeyPatch, conflict: bool
) -> None:
    monkeypatch.setattr(profile_guard, "require_active_bucket_id", lambda: str(_PROFILE))
    creation = in_memory_catalogue_creation_ports()
    request = _wire(_wizard(), intake_contracts.INVOICE_WIZARD_OPERATION_DEFINITION_ID)
    context, events, operands, fence = _context(request, authority_operation)

    def factory(
        *,
        profile_id: UUID,
        operation: PinnedAuthorityOperation,
        commit: InvoiceIntakeCommit,
        admit_provider: InvoiceIntakeProviderAdmission,
    ) -> InvoiceIntakePorts:
        return InvoiceIntakePorts(
            profile_id,
            operation,
            lambda: replace(
                creation,
                audit_commit=_PreparedFakeCommit(
                    creation.audit_commit, commit, fence, conflict=conflict, failure=not conflict
                ),
            ),
            lambda _headers: None,
            lambda: (),
        )

    with pytest.raises(InvoiceIntakeCommitConflictError if conflict else OSError):
        asyncio.run(InvoiceIntakeExecutor(factory).execute(request, context))
    assert events.effects[-1] is (OperationEffect.NONE if conflict else OperationEffect.UNKNOWN)
    assert operands.value is None and len(creation.invoice_repository.load()) == 0


def test_worker_refuses_foreign_active_profile_before_any_capability(
    authority_operation: PinnedAuthorityOperation, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(profile_guard, "require_active_bucket_id", lambda: str(uuid4()))
    request = _wire(_wizard(), intake_contracts.INVOICE_WIZARD_OPERATION_DEFINITION_ID)
    context, events, operands, _fence = _context(request, authority_operation)

    def unused(**_kwargs: object) -> InvoiceIntakePorts:
        pytest.fail("foreign active profile reached canonical capabilities")

    with pytest.raises(ProfileAccessRefusedError):
        asyncio.run(InvoiceIntakeExecutor(unused).execute(request, context))
    assert not events.phases and not events.effects and operands.value is None


def test_correct_digest_header_only_source_keeps_zero_rows_and_no_write(
    tmp_path: Path, authority_operation: PinnedAuthorityOperation, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(profile_guard, "require_active_bucket_id", lambda: str(_PROFILE))
    source = b"counterparty_nif,counterparty_name,invoice_number,invoice_date,taxable_base\n"
    path = tmp_path / "empty-book.csv"
    path.write_bytes(source)
    request = _wire(
        intake_contracts.InvoiceImportRequest(
            profile_id=_PROFILE,
            kind=InvoiceKind.RECEIVED,
            source_path=str(path),
            source_sha256=sha256_hex(source),
            country="ES",
        ),
        intake_contracts.INVOICE_IMPORT_OPERATION_DEFINITION_ID,
    )
    context, events, operands, fence = _context(request, authority_operation)
    creation = in_memory_catalogue_creation_ports()

    def factory(
        *,
        profile_id: UUID,
        operation: PinnedAuthorityOperation,
        commit: InvoiceIntakeCommit,
        admit_provider: InvoiceIntakeProviderAdmission,
    ) -> InvoiceIntakePorts:
        return InvoiceIntakePorts(
            profile_id,
            operation,
            lambda: replace(creation, audit_commit=_PreparedFakeCommit(creation.audit_commit, commit, fence)),
            lambda _headers: None,
            lambda: (),
        )

    asyncio.run(InvoiceIntakeExecutor(factory).execute(request, context))
    assert isinstance(operands.value, intake_contracts.InvoiceIntakeExecutionResult)
    assert isinstance(operands.value.projection, intake_contracts.InvoiceImportProjection)
    assert operands.value.projection.rows == 0 and operands.value.projection.created == 0
    assert events.effects[-1] is OperationEffect.NONE and OperationEffect.UNKNOWN not in events.effects
    assert len(creation.invoice_repository.load()) == 0

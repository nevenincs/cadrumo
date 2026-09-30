"""Purchase-invoice evidence read contracts stay bounded and profile-wide."""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
from uuid import UUID, uuid4

import pytest
from pydantic import BaseModel

from ....application.ledger.evidence import MediaKind, PurchaseInvoiceEvidence
from ....application.ledger.evidence_errors import PurchaseInvoiceEvidenceNotFoundError
from ....application.ledger.evidence_ports import LedgerEvidencePorts
from ....application.ledger.evidence_read_operation import (
    LEDGER_EVIDENCE_LIST_OPERATION_DEFINITION_ID,
    LEDGER_EVIDENCE_VIEW_OPERATION_DEFINITION_ID,
    LedgerEvidenceListExecutionResult,
    LedgerEvidenceListProjection,
    LedgerEvidenceListRequest,
    LedgerEvidenceRecordProjection,
    LedgerEvidenceViewExecutionResult,
    LedgerEvidenceViewProjection,
    LedgerEvidenceViewRequest,
    _project_list_result,
    _project_view_result,
    build_ledger_evidence_list_definition,
    build_ledger_evidence_list_registration,
    build_ledger_evidence_view_definition,
    build_ledger_evidence_view_registration,
)
from ....application.operations.access_resolution import OperationAccessContext, resolve_operation_access
from ....application.operations.models import OperationIdentity, OperationRequest, OperationTerminalReceipt
from ....application.operations.registry import (
    OperationFrontendProjection,
    OperationPublicDefinitionRegistrationV1,
    OperationRegistry,
)
from ....application.user_profile.access_contracts import (
    AccessAction,
    AccessDenialCode,
    Availability,
    DisclosureCategory,
)
from ....application.user_profile.access_errors import ProfileAccessRefusedError
from ....core.errors.error_codes import ErrorCategory, get_registered_error_code
from ....core.operations import OperationEffect, OperationTerminalCondition, profile_operation_subject
from ....core.time.clock import now

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_PROFILE = UUID("5aa00000-0000-4000-8000-0000000000aa")
_OTHER_PROFILE = UUID("6bb00000-0000-4000-8000-0000000000bb")


def _unused_factory(*, bucket_id: str) -> LedgerEvidencePorts:
    raise AssertionError(f"schema and access construction must not compose evidence ports for {bucket_id}")


def _registry() -> tuple[
    OperationRegistry,
    OperationPublicDefinitionRegistrationV1,
    OperationPublicDefinitionRegistrationV1,
]:
    factory = _unused_factory
    list_definition = build_ledger_evidence_list_definition(factory)
    list_registration = build_ledger_evidence_list_registration(list_definition)
    view_definition = build_ledger_evidence_view_definition(factory)
    view_registration = build_ledger_evidence_view_registration(view_definition)
    registry = OperationRegistry(
        definitions=(list_definition, view_definition),
        public_registrations=(list_registration, view_registration),
    )
    return registry, list_registration, view_registration


def _record(**changes: object) -> PurchaseInvoiceEvidence:
    data: dict[str, object] = {
        "evidence_id": "e" * 16,
        "bucket_id": str(_PROFILE),
        "source_path": "invoice.pdf",
        "source_sha256": "a" * 64,
        "attachment_id": "a" * 64,
        "media_kind": MediaKind.PDF,
        "supplier": "Supplier SL",
        "invoice_number": "INV-001",
        "invoice_date": "2026-04-01",
        "taxable_base": Decimal("100.00"),
        "iva_rate": Decimal("0.21"),
        "iva_amount": Decimal("21.00"),
        "notes": "read fixture",
        "created_at": datetime(2026, 4, 2, 10, 30, tzinfo=UTC),
        "updated_at": datetime(2026, 4, 2, 10, 30, tzinfo=UTC),
    }
    data.update(changes)
    return PurchaseInvoiceEvidence.model_validate(data)


def _request(
    definition_id: str,
    *,
    profile_id: UUID = _PROFILE,
    subject_profile_id: UUID | None = None,
) -> OperationRequest[BaseModel]:
    subject_profile = profile_id if subject_profile_id is None else subject_profile_id
    payload: BaseModel = (
        LedgerEvidenceListRequest(profile_id=profile_id)
        if definition_id == LEDGER_EVIDENCE_LIST_OPERATION_DEFINITION_ID
        else LedgerEvidenceViewRequest(profile_id=profile_id, evidence_id="e" * 16)
    )
    return OperationRequest[BaseModel](
        definition_id=definition_id,
        subject_ref=profile_operation_subject(str(subject_profile)),
        payload=payload,
    )


def _access_context(
    registration: OperationPublicDefinitionRegistrationV1,
    *,
    profile_id: UUID = _PROFILE,
) -> OperationAccessContext:
    contract = registration.contract
    return OperationAccessContext(
        profile_id=profile_id,
        destination_id=uuid4(),
        action=AccessAction.RESULT,
        frontend=OperationFrontendProjection.CLI,
        contract=contract,
        published_authority=Availability.AVAILABLE,
    )


def _receipt(*, definition_id: str, profile_id: UUID = _PROFILE) -> OperationTerminalReceipt:
    return OperationTerminalReceipt(
        identity=OperationIdentity(
            operation_id="f" * 64,
            definition_id=definition_id,
            subject_ref=profile_operation_subject(str(profile_id)),
        ),
        revision=1,
        condition=OperationTerminalCondition.SUCCEEDED,
        effect=OperationEffect.NONE,
        settled_at=now(),
        result_ref="a" * 64,
    )


@pytest.mark.parametrize(
    ("definition_id", "registration_index", "request_type"),
    [
        (LEDGER_EVIDENCE_LIST_OPERATION_DEFINITION_ID, 1, LedgerEvidenceListRequest),
        (LEDGER_EVIDENCE_VIEW_OPERATION_DEFINITION_ID, 2, LedgerEvidenceViewRequest),
    ],
)
def test_read_contracts_require_whole_profile_tax_value_disclosure(
    definition_id: str,
    registration_index: int,
    request_type: type[BaseModel],
) -> None:
    registry, list_registration, view_registration = _registry()
    registration = (list_registration, view_registration)[registration_index - 1]
    request = _request(definition_id)
    context = _access_context(registration)

    resolved = resolve_operation_access(registry=registry, request=request, context=context)

    assert isinstance(request.payload, request_type)
    assert resolved.request.profile_id == _PROFILE
    assert resolved.request.periods == frozenset()
    assert resolved.request.period_independent is True
    assert resolved.policy.requires_all_periods is True
    assert resolved.policy.allow_period_independent is True
    assert registration.contract.result_schema is not None
    assert any(
        disclosure.destination_id == context.destination_id
        and disclosure.projection_id == registration.contract.result_schema.schema_id
        and disclosure.category is DisclosureCategory.TAX_VALUES
        for disclosure in resolved.policy.disclosures
    )


@pytest.mark.parametrize(
    ("definition_id", "registration_index"),
    [
        (LEDGER_EVIDENCE_LIST_OPERATION_DEFINITION_ID, 1),
        (LEDGER_EVIDENCE_VIEW_OPERATION_DEFINITION_ID, 2),
    ],
)
def test_read_access_refuses_a_foreign_profile_subject(
    definition_id: str,
    registration_index: int,
) -> None:
    registry, list_registration, view_registration = _registry()
    registration = (list_registration, view_registration)[registration_index - 1]
    request = _request(definition_id, subject_profile_id=_OTHER_PROFILE)

    with pytest.raises(ProfileAccessRefusedError) as refused:
        resolve_operation_access(
            registry=registry,
            request=request,
            context=_access_context(registration),
        )

    assert refused.value.reason is AccessDenialCode.PROFILE_MISMATCH


def test_record_projection_preserves_the_cli_json_facts() -> None:
    record = _record()

    projected = LedgerEvidenceRecordProjection.from_record(record)

    assert projected.model_dump(mode="json") == record.model_dump(mode="json")


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("source_path", "x" * 4_097),
        ("supplier", "x" * 1_025),
        ("invoice_number", "x" * 1_025),
        ("invoice_date", "x" * 65),
        ("taxable_base", Decimal("1" * 129)),
        ("notes", "x" * 16_385),
    ],
)
def test_unbounded_persisted_metadata_refuses_before_result_validation(field: str, value: object) -> None:
    with pytest.raises(ProfileAccessRefusedError) as refused:
        LedgerEvidenceRecordProjection.from_record(_record(**{field: value}))

    assert refused.value.reason is AccessDenialCode.OPERATION_DENIED


def test_list_terminal_projector_binds_definition_subject_and_success_shape() -> None:
    projection = LedgerEvidenceListProjection(
        profile_id=_PROFILE,
        count=1,
        rows=(LedgerEvidenceRecordProjection.from_record(_record()),),
    )
    execution_result = LedgerEvidenceListExecutionResult(profile_id=_PROFILE, result=projection)
    receipt = _receipt(definition_id=LEDGER_EVIDENCE_LIST_OPERATION_DEFINITION_ID)

    assert _project_list_result(execution_result, receipt) == projection
    with pytest.raises(ValueError):
        _project_list_result(
            execution_result,
            receipt.model_copy(
                update={"identity": receipt.identity.model_copy(update={"definition_id": "ledger.evidence.view"})},
            ),
        )
    with pytest.raises(ValueError):
        _project_list_result(execution_result, receipt.model_copy(update={"result_ref": None}))


def test_view_terminal_projector_binds_definition_subject_and_success_shape() -> None:
    projection = LedgerEvidenceViewProjection(
        profile_id=_PROFILE,
        record=LedgerEvidenceRecordProjection.from_record(_record()),
    )
    execution_result = LedgerEvidenceViewExecutionResult(profile_id=_PROFILE, result=projection)
    receipt = _receipt(definition_id=LEDGER_EVIDENCE_VIEW_OPERATION_DEFINITION_ID)

    assert _project_view_result(execution_result, receipt) == projection
    wrong_subject = receipt.model_copy(
        update={
            "identity": receipt.identity.model_copy(
                update={"subject_ref": profile_operation_subject(str(_OTHER_PROFILE))}
            )
        },
    )
    with pytest.raises(ValueError):
        _project_view_result(execution_result, wrong_subject)
    with pytest.raises(ValueError):
        _project_view_result(execution_result, receipt.model_copy(update={"effect": OperationEffect.UPDATED}))


def test_missing_evidence_has_a_registered_refusal_error() -> None:
    code = get_registered_error_code(PurchaseInvoiceEvidenceNotFoundError)

    assert code.category is ErrorCategory.REFUSED

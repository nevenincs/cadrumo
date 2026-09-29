"""Registered invoice catalogue reads keep exact scopes and receipt correlation."""

from __future__ import annotations

from datetime import UTC, date, datetime
from decimal import Decimal
from uuid import UUID, uuid4

import pytest
from pydantic import BaseModel, ValidationError

from ....core.operations import OperationEffect, OperationTerminalCondition, profile_operation_subject
from ....domain.calculations.registry.authority import PinnedAuthorityOperation
from ....domain.iva.classification import InvoiceKind
from ...exchange_rate_provider import exchange_rate_provider
from ...operations.access_resolution import OperationAccessContext, resolve_operation_access
from ...operations.models import OperationIdentity, OperationRequest, OperationTerminalReceipt
from ...operations.registry import (
    OperationFrontendProjection,
    OperationPublicDefinitionRegistrationV1,
    OperationRegistry,
)
from ...user_profile.access_contracts import (
    AccessAction,
    AccessDenialCode,
    Availability,
    DisclosureCategory,
)
from ...user_profile.access_errors import ProfileAccessRefusedError
from ..catalogue_creation import build_catalogue_invoice
from ..catalogue_read_operation import (
    INVOICE_LIST_OPERATION_DEFINITION_ID,
    INVOICE_VIEW_OPERATION_DEFINITION_ID,
    INVOICE_VIEW_REFUSAL_CODE,
    InvoiceListProjection,
    InvoiceListRequest,
    InvoiceListResult,
    InvoiceViewProjection,
    InvoiceViewRefusal,
    InvoiceViewRequest,
    InvoiceViewResult,
    InvoiceViewSuccess,
    build_invoice_list_definition,
    build_invoice_list_registration,
    build_invoice_view_definition,
    build_invoice_view_registration,
    project_invoice_list_result,
    project_invoice_view_result,
)
from ..catalogue_read_projection import CatalogueInvoiceSnapshot
from ..catalogue_selection import InvoiceLookupRefusalReason
from ..inspection_read_ports import InvoiceInspectionReadPorts

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_PROFILE = UUID("5aa00000-0000-4000-8000-0000000000aa")
_OTHER_PROFILE = UUID("6bb00000-0000-4000-8000-0000000000bb")


def _unexpected_ports(*, bucket_id: str, operation: PinnedAuthorityOperation) -> InvoiceInspectionReadPorts:
    """Fail if registration or policy resolution composes private repositories."""
    raise AssertionError(f"invoice schema construction composed ports for {bucket_id} with {operation!r}")


def _registrations() -> tuple[OperationRegistry, dict[str, OperationPublicDefinitionRegistrationV1]]:
    """Build the real schemas without opening profile storage."""
    list_definition = build_invoice_list_definition(_unexpected_ports)
    view_definition = build_invoice_view_definition(_unexpected_ports)
    list_registration = build_invoice_list_registration(list_definition)
    view_registration = build_invoice_view_registration(view_definition)
    registry = OperationRegistry(
        definitions=(list_definition, view_definition),
        public_registrations=(list_registration, view_registration),
    )
    return registry, {
        INVOICE_LIST_OPERATION_DEFINITION_ID: list_registration,
        INVOICE_VIEW_OPERATION_DEFINITION_ID: view_registration,
    }


def _list_request(
    *, profile_id: UUID = _PROFILE, subject_profile_id: UUID | None = None
) -> OperationRequest[BaseModel]:
    subject_profile = profile_id if subject_profile_id is None else subject_profile_id
    return OperationRequest[BaseModel](
        definition_id=INVOICE_LIST_OPERATION_DEFINITION_ID,
        subject_ref=profile_operation_subject(str(subject_profile)),
        payload=InvoiceListRequest(profile_id=profile_id),
    )


def _view_request(
    *, profile_id: UUID = _PROFILE, subject_profile_id: UUID | None = None
) -> OperationRequest[BaseModel]:
    subject_profile = profile_id if subject_profile_id is None else subject_profile_id
    return OperationRequest[BaseModel](
        definition_id=INVOICE_VIEW_OPERATION_DEFINITION_ID,
        subject_ref=profile_operation_subject(str(subject_profile)),
        payload=InvoiceViewRequest(profile_id=profile_id, invoice_id="a" * 64),
    )


def _context(
    registration: OperationPublicDefinitionRegistrationV1,
    *,
    profile_id: UUID = _PROFILE,
    action: AccessAction = AccessAction.SUBMIT,
    admitted_request=None,
    published_authority: Availability = Availability.AVAILABLE,
) -> OperationAccessContext:
    return OperationAccessContext(
        profile_id=profile_id,
        destination_id=uuid4(),
        action=action,
        frontend=OperationFrontendProjection.CLI,
        contract=registration.contract,
        published_authority=published_authority,
        admitted_request=admitted_request,
    )


def _receipt(
    *,
    definition_id: str,
    profile_id: UUID = _PROFILE,
    condition: OperationTerminalCondition = OperationTerminalCondition.SUCCEEDED,
    effect: OperationEffect = OperationEffect.NONE,
    refused: bool = False,
) -> OperationTerminalReceipt:
    return OperationTerminalReceipt(
        identity=OperationIdentity(
            operation_id="a" * 64,
            definition_id=definition_id,
            subject_ref=profile_operation_subject(str(profile_id)),
        ),
        revision=1,
        condition=condition,
        effect=effect,
        settled_at=datetime(2026, 9, 28, 12, tzinfo=UTC),
        result_ref="b" * 64 if condition is OperationTerminalCondition.SUCCEEDED else None,
        refusal_ref=INVOICE_VIEW_REFUSAL_CODE if refused else None,
        refusal_detail_ref="c" * 64 if refused else None,
    )


def _invoice_snapshot() -> CatalogueInvoiceSnapshot:
    invoice = build_catalogue_invoice(
        bucket_id=str(_PROFILE),
        kind=InvoiceKind.RECEIVED,
        invoice_number="2026-0142",
        issued_at=date(2026, 4, 15),
        counterparty_name="Synthetic supplier",
        counterparty_tax_id="A58818501",
        counterparty_country="ES",
        taxable_base=Decimal("100.00"),
        iva_rate=Decimal("21"),
        currency="EUR",
        rate_provider=exchange_rate_provider(),
    )
    return CatalogueInvoiceSnapshot.from_invoice(invoice)


def test_registration_uses_independent_closed_request_and_result_schemas() -> None:
    registry, registrations = _registrations()
    list_registration = registrations[INVOICE_LIST_OPERATION_DEFINITION_ID]
    view_registration = registrations[INVOICE_VIEW_OPERATION_DEFINITION_ID]

    assert registry.lookup(INVOICE_LIST_OPERATION_DEFINITION_ID).request_type is InvoiceListRequest
    assert registry.lookup(INVOICE_LIST_OPERATION_DEFINITION_ID).result_type is InvoiceListResult
    assert registry.lookup(INVOICE_VIEW_OPERATION_DEFINITION_ID).request_type is InvoiceViewRequest
    assert registry.lookup(INVOICE_VIEW_OPERATION_DEFINITION_ID).result_type is InvoiceViewResult
    assert InvoiceListResult is not InvoiceListProjection
    assert InvoiceViewResult is not InvoiceViewProjection
    assert {binding.model_type for binding in list_registration.schema_bindings} == {
        InvoiceListRequest,
        InvoiceListProjection,
    }
    assert {binding.model_type for binding in view_registration.schema_bindings} == {
        InvoiceViewRequest,
        InvoiceViewProjection,
    }
    assert list_registration.contract.result_schema is not None
    assert view_registration.contract.result_schema is not None
    assert list_registration.contract.result_schema.schema_id == "ledger.invoice.list.result"
    assert view_registration.contract.result_schema.schema_id == "ledger.invoice.view.result"

    with pytest.raises(ValidationError):
        InvoiceListProjection.model_validate(
            {"profile_id": _PROFILE, "kind": None, "invoices": (), "future_fact": "not silently dropped"}
        )


@pytest.mark.parametrize("request_kind", ("list", "view"))
def test_invoice_read_submission_requires_all_periods_and_historical_result_admission(request_kind: str) -> None:
    registry, registrations = _registrations()
    registration = registrations[
        INVOICE_LIST_OPERATION_DEFINITION_ID if request_kind == "list" else INVOICE_VIEW_OPERATION_DEFINITION_ID
    ]
    request = _list_request() if request_kind == "list" else _view_request()
    submitted = resolve_operation_access(registry=registry, request=request, context=_context(registration))

    assert submitted.request.profile_id == _PROFILE
    assert submitted.request.periods == frozenset()
    assert submitted.request.period_independent is True
    assert submitted.policy.requires_all_periods is True
    assert submitted.policy.allow_period_independent is True
    assert AccessAction.COMMIT not in submitted.policy.actions

    historical = resolve_operation_access(
        registry=registry,
        request=request,
        context=_context(registration, action=AccessAction.RESULT, admitted_request=submitted.request),
    )
    assert historical.request.periods == frozenset()
    assert historical.policy.requires_all_periods is True
    assert historical.policy.allow_period_independent is True
    assert registration.contract.result_schema is not None
    assert any(
        disclosure.destination_id == historical.request.destination_id
        and disclosure.projection_id == registration.contract.result_schema.schema_id
        and disclosure.category is DisclosureCategory.TAX_VALUES
        for disclosure in historical.policy.disclosures
    )


@pytest.mark.parametrize("request_kind", ("list", "view"))
@pytest.mark.parametrize("mismatch", ("context", "subject"))
def test_invoice_read_refuses_foreign_profile_and_wrong_subject(request_kind: str, mismatch: str) -> None:
    registry, registrations = _registrations()
    definition_id = (
        INVOICE_LIST_OPERATION_DEFINITION_ID if request_kind == "list" else INVOICE_VIEW_OPERATION_DEFINITION_ID
    )
    registration = registrations[definition_id]
    request = _list_request() if request_kind == "list" else _view_request()
    context = _context(registration, profile_id=_OTHER_PROFILE if mismatch == "context" else _PROFILE)
    if mismatch == "subject":
        request = (
            _list_request(subject_profile_id=_OTHER_PROFILE)
            if request_kind == "list"
            else _view_request(subject_profile_id=_OTHER_PROFILE)
        )

    with pytest.raises(ProfileAccessRefusedError) as refused:
        resolve_operation_access(registry=registry, request=request, context=context)

    assert isinstance(request.payload, InvoiceListRequest | InvoiceViewRequest)
    assert request.payload.profile_id == _PROFILE
    assert refused.value.reason is AccessDenialCode.PROFILE_MISMATCH


def test_invoice_list_projector_preserves_result_and_requires_success_none_receipt() -> None:
    private = InvoiceListResult(profile_id=_PROFILE, kind=None, invoices=())
    receipt = _receipt(definition_id=INVOICE_LIST_OPERATION_DEFINITION_ID)

    projection = project_invoice_list_result(private, receipt)

    assert type(projection) is InvoiceListProjection
    assert InvoiceListProjection.model_validate_json(projection.model_dump_json()) == projection
    assert projection.model_dump(mode="json") == private.model_dump(mode="json")
    for inconsistent in (
        receipt.model_copy(update={"condition": OperationTerminalCondition.REFUSED}),
        receipt.model_copy(update={"effect": OperationEffect.UNKNOWN}),
        receipt.model_copy(update={"identity": receipt.identity.model_copy(update={"subject_ref": "foreign"})}),
        receipt.model_copy(
            update={"identity": receipt.identity.model_copy(update={"definition_id": "ledger.invoice.view"})}
        ),
        receipt.model_copy(update={"refusal_ref": INVOICE_VIEW_REFUSAL_CODE}),
        receipt.model_copy(update={"refusal_detail_ref": "c" * 64}),
    ):
        with pytest.raises(ValueError, match="terminal receipt"):
            project_invoice_list_result(private, inconsistent)


def test_invoice_view_projector_correlates_success_and_registered_refusal_receipts() -> None:
    snapshot = _invoice_snapshot()
    success = InvoiceViewResult(
        profile_id=_PROFILE,
        invoice_id=str(snapshot.invoice_id),
        outcome=InvoiceViewSuccess(invoice=snapshot),
    )
    success_projection = project_invoice_view_result(
        success,
        _receipt(definition_id=INVOICE_VIEW_OPERATION_DEFINITION_ID),
    )
    assert type(success_projection) is InvoiceViewProjection
    assert InvoiceViewProjection.model_validate_json(success_projection.model_dump_json()) == success_projection
    assert success_projection.model_dump(mode="json") == success.model_dump(mode="json")

    refused_result = InvoiceViewResult(
        profile_id=_PROFILE,
        invoice_id="deadbeefdeadbeef",
        outcome=InvoiceViewRefusal(reason=InvoiceLookupRefusalReason.NOT_FOUND),
    )
    refused_receipt = _receipt(
        definition_id=INVOICE_VIEW_OPERATION_DEFINITION_ID,
        condition=OperationTerminalCondition.REFUSED,
        refused=True,
    )
    refused_projection = project_invoice_view_result(refused_result, refused_receipt)
    assert type(refused_projection.outcome) is InvoiceViewRefusal
    assert InvoiceViewProjection.model_validate_json(refused_projection.model_dump_json()) == refused_projection

    for inconsistent in (
        refused_receipt.model_copy(update={"condition": OperationTerminalCondition.SUCCEEDED}),
        refused_receipt.model_copy(update={"effect": OperationEffect.UNKNOWN}),
        refused_receipt.model_copy(
            update={"identity": refused_receipt.identity.model_copy(update={"subject_ref": "foreign"})}
        ),
        refused_receipt.model_copy(
            update={"identity": refused_receipt.identity.model_copy(update={"definition_id": "ledger.invoice.list"})}
        ),
        refused_receipt.model_copy(update={"refusal_ref": "REFUSED_OTHER"}),
        refused_receipt.model_copy(update={"refusal_detail_ref": None}),
    ):
        with pytest.raises(ValueError, match="terminal receipt"):
            project_invoice_view_result(refused_result, inconsistent)


def test_invoice_view_refusal_requires_candidates_only_for_ambiguity() -> None:
    candidate_ids = ("a" * 64, "a" + "b" * 63)
    ambiguous = InvoiceViewResult(
        profile_id=_PROFILE,
        invoice_id="a",
        outcome=InvoiceViewRefusal(reason=InvoiceLookupRefusalReason.AMBIGUOUS, candidate_ids=candidate_ids),
    )
    assert isinstance(ambiguous.outcome, InvoiceViewRefusal)
    assert ambiguous.outcome.candidate_ids == candidate_ids
    with pytest.raises(ValidationError):
        InvoiceViewRefusal(reason=InvoiceLookupRefusalReason.NOT_FOUND, candidate_ids=candidate_ids)
    with pytest.raises(ValidationError):
        InvoiceViewRefusal(reason=InvoiceLookupRefusalReason.AMBIGUOUS, candidate_ids=(candidate_ids[0],))

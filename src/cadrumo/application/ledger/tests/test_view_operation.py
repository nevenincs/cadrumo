"""Registered transaction view preserves canonical facts under whole-profile authority."""

from __future__ import annotations

from datetime import UTC, date, datetime
from decimal import Decimal
from pathlib import Path
from uuid import UUID, uuid4

import pytest
from pydantic import BaseModel, ValidationError

from ....core.operations import profile_operation_subject
from ....domain.calculations.registry.authority import PinnedAuthorityOperation
from ....domain.transactions.enums import BusinessClassification, TransactionDirection
from ....domain.transactions.m210_income_classification import (
    M210IncomeClassification,
    required_m210_payer_mode_for_code,
    resolve_m210_payer_mode,
)
from ....domain.transactions.models import Transaction
from ....domain.transactions.raw_transaction import RawProvenance, RawTransaction, SourceFormat
from ...ledger.action_ports import LedgerActionPorts
from ...ledger.actions_manual import ledger_transaction_payload
from ...ledger.models import LedgerTransactionPayload
from ...ledger.transaction_projection import LedgerM210IncomeProjection, LedgerTransactionProjection
from ...ledger.view_operation import (
    LEDGER_VIEW_OPERATION_DEFINITION_ID,
    LedgerViewProjection,
    LedgerViewRequest,
    build_ledger_view_definition,
    build_ledger_view_registration,
)
from ...operations.access_resolution import OperationAccessContext, resolve_operation_access
from ...operations.models import OperationRequest
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

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_PROFILE = UUID("5aa00000-0000-4000-8000-0000000000aa")
_OTHER_PROFILE = UUID("6bb00000-0000-4000-8000-0000000000bb")
_M210_CODE = "35"
_M210_EFFECTIVE_DATE = date(2025, 12, 31)
_CREATED_AT = datetime(2025, 2, 15, 12, 0, tzinfo=UTC)
_GROSS_INCOME = Decimal("123456789012345678901234567890.12345678901234567890")
_APPLICABLE_RATE = Decimal("0.2400000000000000000000000000000000000000")


class _FutureLedgerTransactionPayload(LedgerTransactionPayload):
    """Isolated future canonical field used to prove projection closure."""

    future_canonical_fact: str


def _unexpected_ports(*, bucket_id: str, operation: PinnedAuthorityOperation) -> LedgerActionPorts:
    raise AssertionError(f"schema or access resolution composed ports for {bucket_id} under {operation!r}")


def _registry() -> tuple[OperationRegistry, OperationPublicDefinitionRegistrationV1]:
    definition = build_ledger_view_definition(_unexpected_ports)
    registration = build_ledger_view_registration(definition)
    return OperationRegistry(definitions=(definition,), public_registrations=(registration,)), registration


def _request(*, profile_id: UUID = _PROFILE, subject_profile_id: UUID | None = None) -> OperationRequest[BaseModel]:
    subject_profile = profile_id if subject_profile_id is None else subject_profile_id
    return OperationRequest[BaseModel](
        definition_id=LEDGER_VIEW_OPERATION_DEFINITION_ID,
        subject_ref=profile_operation_subject(str(subject_profile)),
        payload=LedgerViewRequest(profile_id=profile_id, transaction_prefix="a" * 12),
    )


def _access_context(
    registration: OperationPublicDefinitionRegistrationV1, *, profile_id: UUID = _PROFILE
) -> OperationAccessContext:
    return OperationAccessContext(
        profile_id=profile_id,
        destination_id=uuid4(),
        action=AccessAction.RESULT,
        frontend=OperationFrontendProjection.CLI,
        contract=registration.contract,
        published_authority=Availability.AVAILABLE,
    )


def _m210_canonical_payload(operation: PinnedAuthorityOperation) -> LedgerTransactionPayload:
    """Build a canonical payload through the existing domain and application owners.

    The code, payer mode, payer absence, rate, and income classification follow
    `_classification("35", ...)` in the profile-persistence M210 ledger fixture.
    The enlarged coefficient and scale exercise exact registered JSON transfer.
    """
    payer_mode = required_m210_payer_mode_for_code(
        _M210_CODE,
        effective_date=_M210_EFFECTIVE_DATE,
        operation=operation,
    ) or resolve_m210_payer_mode(effective_date=_M210_EFFECTIVE_DATE, operation=operation)
    classification = M210IncomeClassification(
        official_tipo_renta_code=_M210_CODE,
        gross_income_amount=_GROSS_INCOME,
        applicable_rate=_APPLICABLE_RATE,
        payer_mode=payer_mode,
        payer_id=None,
        asset_or_right_id="ES-ACTIVO-210",
    )
    raw = RawTransaction(
        provider_transaction_id="m210-view-projection-row",
        booked_date=date(2025, 2, 15),
        value_date=None,
        amount=_GROSS_INCOME,
        currency="EUR",
        counterparty=None,
        description="Synthetic M210 transaction projection",
        provenance=RawProvenance(
            source_path=Path("m210-view-fixture.csv"),
            source_sha256="c" * 64,
            source_row_index=1,
            source_format=SourceFormat.MANUAL,
            ingested_at=_CREATED_AT,
            provider_name="M210 view fixture",
        ),
        raw_fields={},
    )
    transaction = Transaction.model_validate(
        {
            "raw": raw,
            "direction": TransactionDirection.INCOMING,
            "business_classification": BusinessClassification.BUSINESS,
            "source_jurisdiction": "ES",
            "group_label": None,
            "m210_income_classification": classification,
            "created_at": _CREATED_AT,
            "modified_at": _CREATED_AT,
        }
    )
    return ledger_transaction_payload(transaction)


def test_view_registers_exact_strict_request_and_result_models() -> None:
    registry, registration = _registry()

    definition = registry.lookup(LEDGER_VIEW_OPERATION_DEFINITION_ID)
    contract = registration.contract

    assert definition.request_type is LedgerViewRequest
    assert definition.result_type is LedgerViewProjection
    assert contract.request_schema.schema_id == "ledger.view.request"
    assert contract.result_schema is not None
    assert contract.result_schema.schema_id == "ledger.view.result"
    assert {binding.identity.schema_id for binding in registration.schema_bindings} == {
        "ledger.view.request",
        "ledger.view.result",
    }


def test_view_access_is_exact_profile_whole_profile_result_without_commit() -> None:
    registry, registration = _registry()
    request = _request()
    resolved = resolve_operation_access(
        registry=registry,
        request=request,
        context=_access_context(registration),
    )

    assert request.subject_ref == profile_operation_subject(str(_PROFILE))
    assert resolved.request.profile_id == _PROFILE
    assert resolved.request.periods == frozenset()
    assert resolved.request.period_independent is True
    assert resolved.policy.requires_all_periods is True
    assert AccessAction.COMMIT not in resolved.policy.actions
    result_schema = registration.contract.result_schema
    assert result_schema is not None
    assert any(
        disclosure.projection_id == result_schema.schema_id and disclosure.category is DisclosureCategory.TAX_VALUES
        for disclosure in resolved.policy.disclosures
    )


def test_view_access_refuses_only_the_wrong_subject_for_matching_payload_and_context() -> None:
    registry, registration = _registry()
    request = _request(subject_profile_id=_OTHER_PROFILE)

    with pytest.raises(ProfileAccessRefusedError) as error:
        resolve_operation_access(
            registry=registry,
            request=request,
            context=_access_context(registration, profile_id=_PROFILE),
        )

    assert isinstance(request.payload, LedgerViewRequest)
    assert request.payload.profile_id == _PROFILE
    assert request.subject_ref == profile_operation_subject(str(_OTHER_PROFILE))
    assert error.value.reason is AccessDenialCode.PROFILE_MISMATCH


def test_transaction_projection_roundtrips_the_live_canonical_m210_field_set(
    authority_operation: PinnedAuthorityOperation,
) -> None:
    canonical = _m210_canonical_payload(authority_operation)
    projection = LedgerTransactionProjection.from_payload(canonical)

    assert set(LedgerTransactionPayload.model_fields) == set(LedgerTransactionProjection.model_fields)
    assert set(M210IncomeClassification.model_fields) == set(LedgerM210IncomeProjection.model_fields)
    assert projection.model_dump(mode="json") == canonical.model_dump(mode="json")
    assert canonical.m210_income_classification is not None
    assert projection.m210_income_classification is not None
    assert projection.m210_income_classification.gross_income_amount == str(
        canonical.m210_income_classification.gross_income_amount
    )
    assert projection.m210_income_classification.applicable_rate == str(
        canonical.m210_income_classification.applicable_rate
    )
    assert projection.m210_income_classification.payer_id is None


def test_transaction_projection_rejects_a_future_canonical_field(
    authority_operation: PinnedAuthorityOperation,
) -> None:
    canonical = _m210_canonical_payload(authority_operation)
    expanded = _FutureLedgerTransactionPayload.model_validate(
        {**canonical.model_dump(), "future_canonical_fact": "must not be dropped"}
    )

    with pytest.raises(ValidationError):
        LedgerTransactionProjection.from_payload(expanded)

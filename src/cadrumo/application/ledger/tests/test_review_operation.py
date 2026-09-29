"""The registered ledger review binds private filters and closed row facts."""

from __future__ import annotations

import json
from uuid import UUID, uuid4

import pytest
from pydantic import BaseModel, ValidationError

from ....core.hashing import canonical_json_bytes
from ....core.operations import OperationEffect, profile_operation_subject
from ....core.period import Period
from ....domain.calculations.registry.authority import PinnedAuthorityOperation
from ...operations.access_resolution import OperationAccessContext, resolve_operation_access
from ...operations.capabilities import OperationRequestStoragePolicy, OperationSensitiveInputPolicy
from ...operations.models import OperationRequest
from ...operations.registry import (
    OperationFrontendProjection,
    OperationPublicDefinitionRegistrationV1,
    OperationRegistry,
)
from ...review.filter import LedgerReviewStatus
from ...user_profile.access_contracts import (
    AccessAction,
    AccessDenialCode,
    Availability,
    DisclosureCategory,
)
from ...user_profile.access_errors import ProfileAccessRefusedError
from ..action_ports import LedgerActionPorts
from ..models import LedgerTransactionPayload
from ..review_operation import (
    LEDGER_REVIEW_OPERATION_DEFINITION_ID,
    LedgerReviewProjection,
    LedgerReviewRequest,
    LedgerReviewRowProjection,
    build_ledger_review_definition,
    build_ledger_review_registration,
)
from ..transaction_projection import LedgerTransactionProjection

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_PROFILE = UUID("5aa00000-0000-4000-8000-0000000000aa")
_OTHER_PROFILE = UUID("6bb00000-0000-4000-8000-0000000000bb")
_TRANSACTION_ID = "a" * 64
_OTHER_TRANSACTION_ID = "b" * 64


def _unexpected_ports(*, bucket_id: str, operation: PinnedAuthorityOperation) -> LedgerActionPorts:
    raise AssertionError(f"review schema or access admission composed ports for {bucket_id} with {operation!r}")


def _registry() -> tuple[OperationRegistry, OperationPublicDefinitionRegistrationV1]:
    definition = build_ledger_review_definition(_unexpected_ports)
    registration = build_ledger_review_registration(definition)
    return OperationRegistry(definitions=(definition,), public_registrations=(registration,)), registration


def _request(
    *,
    profile_id: UUID = _PROFILE,
    subject_profile_id: UUID | None = None,
    filters: tuple[str, ...] = (),
    transaction_prefix: str | None = None,
) -> OperationRequest[BaseModel]:
    subject_profile = profile_id if subject_profile_id is None else subject_profile_id
    return OperationRequest[BaseModel](
        definition_id=LEDGER_REVIEW_OPERATION_DEFINITION_ID,
        subject_ref=profile_operation_subject(str(subject_profile)),
        payload=LedgerReviewRequest(
            profile_id=profile_id,
            filters=filters,
            transaction_prefix=transaction_prefix,
        ),
    )


def _access_context(
    registration: OperationPublicDefinitionRegistrationV1,
    *,
    profile_id: UUID = _PROFILE,
) -> OperationAccessContext:
    return OperationAccessContext(
        profile_id=profile_id,
        destination_id=uuid4(),
        action=AccessAction.RESULT,
        frontend=OperationFrontendProjection.CLI,
        contract=registration.contract,
        published_authority=Availability.AVAILABLE,
    )


def _transaction(transaction_id: str) -> LedgerTransactionProjection:
    payload = LedgerTransactionPayload(
        transaction_id=transaction_id,
        date="2026-01-02",
        booked_date="2026-01-02",
        amount="10.00",
        currency="EUR",
        direction="incoming",
        description="Canonical review row",
        business_classification="business",
        lifecycle_state="active",
        classified_by="operator",
        created_at="2026-01-02T10:00:00Z",
        modified_at="2026-01-02T10:00:00Z",
    )
    return LedgerTransactionProjection.from_payload(payload)


def _row(
    transaction_id: str,
    *,
    transaction: LedgerTransactionProjection | None = None,
) -> LedgerReviewRowProjection:
    return LedgerReviewRowProjection(
        id=transaction_id,
        date="2026-01-02",
        amount="10.00",
        description="Canonical review row",
        status=LedgerReviewStatus.PENDING,
        transaction=transaction,
    )


def test_review_registration_binds_exact_request_and_result_models() -> None:
    registry, registration = _registry()
    definition = registry.lookup(LEDGER_REVIEW_OPERATION_DEFINITION_ID)

    assert definition.request_type is LedgerReviewRequest
    assert definition.result_type is LedgerReviewProjection
    assert registration.contract.request_schema.schema_id == "ledger.review.request"
    result_schema = registration.contract.result_schema
    assert result_schema is not None
    assert result_schema.schema_id == "ledger.review.result"
    assert {binding.model_type for binding in registration.schema_bindings} == {
        LedgerReviewRequest,
        LedgerReviewProjection,
    }
    assert definition.capabilities.permitted_effects == frozenset({OperationEffect.NONE, OperationEffect.UNKNOWN})
    assert definition.capabilities.request_storage is OperationRequestStoragePolicy.SECURE_REFERENCE
    assert definition.capabilities.sensitive_input is OperationSensitiveInputPolicy.SECURE_REFERENCE


def test_review_request_hides_malformed_private_filter_text() -> None:
    private_filter = "review-private-filter-sentinel"

    with pytest.raises(ValidationError) as error:
        LedgerReviewRequest(profile_id=_PROFILE, filters=(private_filter,))

    assert "invalid ledger review filters" in str(error.value)
    assert private_filter not in str(error.value)


@pytest.mark.parametrize(
    ("filters", "expected_period"),
    [
        ((), None),
        (("period=1T", "year=2026"), Period.from_year_and_code(2026, "1T")),
    ],
)
def test_review_access_uses_only_canonical_period_scope_and_never_commit(
    filters: tuple[str, ...],
    expected_period: Period | None,
) -> None:
    registry, registration = _registry()
    request = _request(filters=filters, transaction_prefix=_TRANSACTION_ID[:12])
    context = _access_context(registration)
    assert isinstance(request.payload, LedgerReviewRequest)
    assert request.payload.filter_spec().period == expected_period

    resolved = resolve_operation_access(registry=registry, request=request, context=context)

    expected_periods = frozenset({expected_period}) if expected_period is not None else frozenset()
    assert resolved.request.profile_id == _PROFILE
    assert resolved.request.periods == expected_periods
    assert resolved.request.period_independent is (expected_period is None)
    assert resolved.policy.requires_all_periods is (expected_period is None)
    assert resolved.policy.allow_period_independent is (expected_period is None)
    assert AccessAction.COMMIT not in resolved.policy.actions
    result_schema = registration.contract.result_schema
    assert result_schema is not None
    assert any(
        disclosure.destination_id == context.destination_id
        and disclosure.projection_id == result_schema.schema_id
        and disclosure.category is DisclosureCategory.TAX_VALUES
        for disclosure in resolved.policy.disclosures
    )


@pytest.mark.parametrize(
    ("context_profile", "payload_profile", "subject_profile"),
    [
        (_OTHER_PROFILE, _PROFILE, _PROFILE),
        (_PROFILE, _PROFILE, _OTHER_PROFILE),
    ],
)
def test_review_access_refuses_a_foreign_profile_or_subject(
    context_profile: UUID,
    payload_profile: UUID,
    subject_profile: UUID,
) -> None:
    registry, registration = _registry()
    request = _request(profile_id=payload_profile, subject_profile_id=subject_profile)

    with pytest.raises(ProfileAccessRefusedError) as error:
        resolve_operation_access(
            registry=registry,
            request=request,
            context=_access_context(registration, profile_id=context_profile),
        )

    assert error.value.reason is AccessDenialCode.PROFILE_MISMATCH


def test_review_projection_json_roundtrip_preserves_list_and_optional_detail_facts() -> None:
    list_projection = LedgerReviewProjection(
        profile_id=_PROFILE,
        transaction_prefix=None,
        rows=(_row(_TRANSACTION_ID),),
        filters=("status=pending",),
    )
    detail_transaction = _transaction(_TRANSACTION_ID)
    detail_projection = LedgerReviewProjection(
        profile_id=_PROFILE,
        transaction_prefix=_TRANSACTION_ID[:12],
        rows=(_row(_TRANSACTION_ID, transaction=detail_transaction),),
        filters=(),
    )

    restored_list = LedgerReviewProjection.model_validate_json(list_projection.model_dump_json())
    restored_detail = LedgerReviewProjection.model_validate_json(detail_projection.model_dump_json())

    assert restored_list == list_projection
    assert restored_list.rows[0].transaction is None
    assert restored_detail == detail_projection
    assert restored_detail.rows[0].transaction == detail_transaction
    restored_transaction = restored_detail.rows[0].transaction
    assert restored_transaction is not None
    assert restored_transaction.amount == "10.00"


def test_review_projection_rejects_open_result_facts() -> None:
    projection = LedgerReviewProjection(
        profile_id=_PROFILE,
        transaction_prefix=None,
        rows=(_row(_TRANSACTION_ID),),
        filters=(),
    )
    data = json.loads(projection.model_dump_json())
    data["rows"][0]["future_private_fact"] = "must not cross the registered result schema"

    with pytest.raises(ValidationError):
        LedgerReviewProjection.model_validate_json(canonical_json_bytes(data))


def test_review_detail_rejects_more_than_one_row() -> None:
    with pytest.raises(ValidationError, match="ledger review detail contains multiple rows"):
        LedgerReviewProjection(
            profile_id=_PROFILE,
            transaction_prefix=_TRANSACTION_ID[:12],
            rows=(_row(_TRANSACTION_ID, transaction=_transaction(_TRANSACTION_ID)), _row(_OTHER_TRANSACTION_ID)),
            filters=(),
        )


def test_review_detail_rejects_mismatched_transaction_identity() -> None:
    with pytest.raises(ValidationError, match="ledger review row and transaction identities disagree"):
        LedgerReviewProjection(
            profile_id=_PROFILE,
            transaction_prefix=_TRANSACTION_ID[:12],
            rows=(_row(_TRANSACTION_ID, transaction=_transaction(_OTHER_TRANSACTION_ID)),),
            filters=(),
        )


def test_review_list_and_detail_rows_cannot_mix_fact_shapes() -> None:
    with pytest.raises(ValidationError, match="ledger review detail facts disagree with selection"):
        LedgerReviewProjection(
            profile_id=_PROFILE,
            transaction_prefix=None,
            rows=(_row(_TRANSACTION_ID, transaction=_transaction(_TRANSACTION_ID)),),
            filters=(),
        )

    with pytest.raises(ValidationError, match="ledger review detail facts disagree with selection"):
        LedgerReviewProjection(
            profile_id=_PROFILE,
            transaction_prefix=_TRANSACTION_ID[:12],
            rows=(_row(_TRANSACTION_ID),),
            filters=(),
        )

"""Invoice-update wire models preserve selected-field PATCH semantics."""

from __future__ import annotations

import asyncio
from decimal import Decimal
from types import SimpleNamespace
from typing import cast
from uuid import UUID

import pytest
from pydantic import ValidationError

from ....core.operations import profile_operation_subject
from ...operations import profile_guard
from ...operations.models import OperationIdentity, OperationRequest
from ...operations.owner import OperationExecutorContext
from ...user_profile.access_contracts import AccessDenialCode
from ...user_profile.access_errors import ProfileAccessRefusedError
from ..catalogue_lifecycle import CatalogueInvoicePatch
from ..catalogue_lifecycle_ports import CatalogueLifecyclePorts
from ..catalogue_update_operation import (
    INVOICE_UPDATE_OPERATION_DEFINITION_ID,
    InvoiceUpdateExecutor,
    InvoiceUpdatePatch,
    InvoiceUpdateRequest,
    InvoiceUpdateValues,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]
_PROFILE = UUID("5aa00000-0000-4000-8000-0000000000aa")
_OTHER_PROFILE = UUID("6bb00000-0000-4000-8000-0000000000bb")


def test_full_json_roundtrip_preserves_omission_explicit_null_and_decimal_zero() -> None:
    explicit_null = CatalogueInvoicePatch.model_validate({"notes": None, "retention_amount": Decimal("0.00")})
    omitted = CatalogueInvoicePatch.model_validate({"retention_amount": Decimal("0.00")})
    explicit_request = InvoiceUpdateRequest(
        profile_id=UUID("5aa00000-0000-4000-8000-0000000000aa"),
        invoice_id="a" * 64,
        patch=InvoiceUpdatePatch.from_patch(explicit_null),
    )
    omitted_request = InvoiceUpdateRequest(
        profile_id=explicit_request.profile_id,
        invoice_id=explicit_request.invoice_id,
        patch=InvoiceUpdatePatch.from_patch(omitted),
    )

    explicit_roundtrip = InvoiceUpdateRequest.model_validate_json(explicit_request.model_dump_json())
    omitted_roundtrip = InvoiceUpdateRequest.model_validate_json(omitted_request.model_dump_json())

    assert explicit_roundtrip == explicit_request
    assert omitted_roundtrip == omitted_request
    explicit_patch = explicit_roundtrip.patch.to_patch()
    omitted_patch = omitted_roundtrip.patch.to_patch()
    assert explicit_patch.model_fields_set == {"notes", "retention_amount"}
    assert omitted_patch.model_fields_set == {"retention_amount"}
    assert explicit_patch.notes is None
    assert explicit_patch.retention_amount == omitted_patch.retention_amount == Decimal("0.00")
    assert "notes" not in omitted_patch.model_fields_set
    assert "retention_rate" not in explicit_patch.model_fields_set | omitted_patch.model_fields_set


@pytest.mark.parametrize(
    ("values", "fields"),
    (
        ({}, frozenset()),
        ({}, frozenset({"unknown_field"})),
        ({"counterparty_name": "unselected"}, frozenset({"notes"})),
    ),
)
def test_patch_rejects_empty_unknown_and_unselected_masks(values: dict[str, object], fields: frozenset[str]) -> None:
    with pytest.raises(ValidationError):
        InvoiceUpdatePatch(values=InvoiceUpdateValues.model_validate(values), fields=fields)


def test_update_executor_refuses_foreign_active_profile_before_phase_or_factory(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    request = OperationRequest[InvoiceUpdateRequest](
        definition_id=INVOICE_UPDATE_OPERATION_DEFINITION_ID,
        subject_ref=profile_operation_subject(str(_PROFILE)),
        payload=InvoiceUpdateRequest(
            profile_id=_PROFILE,
            invoice_id="a" * 64,
            patch=InvoiceUpdatePatch(values=InvoiceUpdateValues(notes="correction"), fields=frozenset({"notes"})),
        ),
    )
    phases: list[str] = []

    async def record_phase(phase: str) -> None:
        phases.append(phase)

    context = cast(
        OperationExecutorContext,
        SimpleNamespace(
            identity=OperationIdentity(
                operation_id="a" * 64,
                definition_id=request.definition_id,
                subject_ref=request.subject_ref,
            ),
            events=SimpleNamespace(phase=record_phase),
        ),
    )
    monkeypatch.setattr(profile_guard, "require_active_bucket_id", lambda: str(_OTHER_PROFILE))

    def unused_factory(*, bucket_id: str) -> CatalogueLifecyclePorts:
        pytest.fail(f"foreign active profile reached invoice update ports for {bucket_id}")

    with pytest.raises(ProfileAccessRefusedError) as refused:
        asyncio.run(InvoiceUpdateExecutor(unused_factory).execute(request, context))

    assert refused.value.reason is AccessDenialCode.PROFILE_MISMATCH
    assert phases == []

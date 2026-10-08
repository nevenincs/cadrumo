"""Exact-profile bridge checks for invoice extract and reviewed confirm routes."""

from __future__ import annotations

from types import SimpleNamespace
from typing import cast
from uuid import UUID

import pytest
import typer
from pydantic import BaseModel

from ....adapters.local_runtime.frontend_client import RuntimeFrontendClient
from ....application.ledger.invoice_evidence_confirm_operation import (
    LEDGER_EVIDENCE_CONFIRM_OPERATION_DEFINITION_ID,
    LedgerEvidenceConfirmProjection,
    LedgerEvidenceConfirmRequest,
)
from ....application.ledger.invoice_evidence_extract_operation import (
    LEDGER_EVIDENCE_EXTRACT_OPERATION_DEFINITION_ID,
    LedgerEvidenceExtractProjection,
    LedgerEvidenceExtractRequest,
)
from ....application.ledger.invoice_evidence_operation_dtos import InvoiceConfirmationProjectionV1
from ....application.operations.models import OperationId
from ....application.runtime.contracts import RuntimeRefusalCode, RuntimeRefusalError
from ....core.operations import OperationEffect, profile_operation_subject
from ....domain.iva.classification import InvoiceKind
from .. import runtime_ledger_invoice_evidence as bridge
from ..errors import CliRefusedBoundaryError
from ..registered_operation_contracts import RegisteredOperationCompletion

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint]

_PROFILE = UUID("5aa00000-0000-4000-8000-0000000000aa")
_OTHER_PROFILE = UUID("6bb00000-0000-4000-8000-0000000000bb")
_EVIDENCE_ID = "e" * 16
_SOURCE_SHA256 = "a" * 64
_DRAFT_SHA256 = "b" * 64
_OPERATION_ID = cast(OperationId, "f" * 64)
#: Extraction and confirmation results carry the label-reading fallback beside
#: the draft, so both read the second result schema.
_RESULT_VERSIONS = {
    LEDGER_EVIDENCE_EXTRACT_OPERATION_DEFINITION_ID: 2,
    LEDGER_EVIDENCE_CONFIRM_OPERATION_DEFINITION_ID: 2,
}


def _bind(
    monkeypatch: pytest.MonkeyPatch,
    *,
    definition_id: str,
    result_type: type[BaseModel],
    completion: RegisteredOperationCompletion[BaseModel],
    requests: list[BaseModel],
) -> None:
    client = cast(RuntimeFrontendClient, SimpleNamespace(profile_id=_PROFILE))
    monkeypatch.setattr(bridge, "active_bucket_id_or_refuse", lambda: str(_PROFILE))

    def bound_client(_ctx: typer.Context, *, expected_profile_id: UUID) -> RuntimeFrontendClient:
        assert expected_profile_id == _PROFILE
        return client

    monkeypatch.setattr(bridge, "require_profile_client", bound_client)

    def submit(
        actual_client: RuntimeFrontendClient,
        request: BaseModel,
        **kwargs: object,
    ) -> RegisteredOperationCompletion[BaseModel]:
        requests.append(request)
        assert actual_client is client
        assert kwargs["definition_id"] == definition_id
        assert kwargs["subject_ref"] == profile_operation_subject(str(_PROFILE))
        assert kwargs["result_type"] is result_type
        assert kwargs["request_version"] == 1
        assert kwargs["result_version"] == _RESULT_VERSIONS[definition_id]
        assert kwargs["timeout"] == 120
        assert kwargs["allow_refusal_detail"] is True
        return completion

    monkeypatch.setattr(bridge, "run_registered_operation", submit)


def test_extract_bridge_submits_the_typed_request_and_correlates_consent_effect(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    projection = LedgerEvidenceExtractProjection.model_construct(
        profile_id=_PROFILE,
        evidence_id=_EVIDENCE_ID,
        attachment_id=None,
        source_sha256=_SOURCE_SHA256,
        draft_review_sha256=_DRAFT_SHA256,
        off_host_provider=None,
        consent_audit_effect=OperationEffect.NONE,
        draft=object(),
    )
    completion = RegisteredOperationCompletion[BaseModel](
        operation_id=_OPERATION_ID,
        projection=cast(BaseModel, projection),
        effect=OperationEffect.NONE,
    )
    requests: list[BaseModel] = []
    _bind(
        monkeypatch,
        definition_id=LEDGER_EVIDENCE_EXTRACT_OPERATION_DEFINITION_ID,
        result_type=LedgerEvidenceExtractProjection,
        completion=completion,
        requests=requests,
    )
    request = LedgerEvidenceExtractRequest(profile_id=_PROFILE, evidence_id=_EVIDENCE_ID)

    completed = bridge.submit_invoice_evidence_extract(
        cast(typer.Context, cast(object, None)),
        request,
    )

    assert completed is completion
    assert len(requests) == 1 and isinstance(requests[0], LedgerEvidenceExtractRequest)
    assert requests[0] == request


def test_confirm_bridge_requires_the_explicit_hashes_and_preserves_receipt_on_mismatch(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    request = LedgerEvidenceConfirmRequest(
        profile_id=_PROFILE,
        evidence_id=_EVIDENCE_ID,
        expected_source_sha256=_SOURCE_SHA256,
        expected_draft_review_sha256=_DRAFT_SHA256,
        kind=InvoiceKind.RECEIVED,
    )
    projection = LedgerEvidenceConfirmProjection.model_construct(
        profile_id=_PROFILE,
        evidence_id=_EVIDENCE_ID,
        attachment_id=None,
        source_sha256=_SOURCE_SHA256,
        reviewed_draft_sha256="c" * 64,
        confirmation=cast(InvoiceConfirmationProjectionV1, object()),
    )
    completion = RegisteredOperationCompletion[BaseModel](
        operation_id=_OPERATION_ID,
        projection=cast(BaseModel, projection),
        effect=OperationEffect.UPDATED,
    )
    requests: list[BaseModel] = []
    _bind(
        monkeypatch,
        definition_id=LEDGER_EVIDENCE_CONFIRM_OPERATION_DEFINITION_ID,
        result_type=LedgerEvidenceConfirmProjection,
        completion=completion,
        requests=requests,
    )

    with pytest.raises(CliRefusedBoundaryError) as refused:
        bridge.submit_invoice_evidence_confirm(
            cast(typer.Context, cast(object, None)),
            request,
        )

    assert len(requests) == 1 and requests[0] == request
    assert refused.value.context == {
        "operation_id": str(_OPERATION_ID),
        "reason": RuntimeRefusalCode.INVALID_FRAME.value,
        "effect": OperationEffect.UPDATED.value,
        "terminal_condition": "succeeded",
    }


def test_exact_profile_mismatch_refuses_before_submission(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(bridge, "active_bucket_id_or_refuse", lambda: str(_OTHER_PROFILE))

    def unexpected_submission(*_args: object, **_kwargs: object) -> None:
        pytest.fail("profile mismatch must refuse before operation submission")

    monkeypatch.setattr(bridge, "run_registered_operation", unexpected_submission)
    request = LedgerEvidenceExtractRequest(profile_id=_PROFILE, evidence_id=_EVIDENCE_ID)

    with pytest.raises(RuntimeRefusalError) as refused:
        bridge.submit_invoice_evidence_extract(cast(typer.Context, cast(object, None)), request)

    assert refused.value.reason is RuntimeRefusalCode.INVALID_FRAME

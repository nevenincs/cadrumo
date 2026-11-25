"""The invoice figures-preview executor answers inside the exact profile and records nothing it cannot answer."""

from __future__ import annotations

import asyncio
from collections.abc import Iterator
from types import SimpleNamespace
from typing import cast

import pytest

from ....core.operations import profile_operation_subject
from ....domain.calculations.registry.authority import PinnedAuthorityOperation
from ....domain.calculations.registry.tests.authority_lease_support import private_authority_lease
from ...operations.models import OperationIdentity, OperationRequest
from ...operations.owner import OperationExecutorContext
from .. import figures_preview_operation as preview_operation
from ..catalogue_creation_ports import CatalogueInvoiceRateError
from ..figures_preview_contracts import (
    INVOICE_FIGURES_PREVIEW_OPERATION_DEFINITION_ID,
    InvoiceFiguresPreviewExecutionResult,
    InvoiceFiguresPreviewRequest,
)
from ..figures_preview_operation import InvoiceFiguresPreviewExecutor, build_invoice_figures_preview_definition
from .figures_preview_support import PROFILE, NoRate, Unreachable, preview_draft

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]


@pytest.fixture
def operation() -> Iterator[PinnedAuthorityOperation]:
    with private_authority_lease() as leased:
        yield leased


class _Operands:
    def __init__(self) -> None:
        self.value: InvoiceFiguresPreviewExecutionResult | None = None

    async def put(self, operand: object, *, written_at: object) -> str:
        assert isinstance(operand, InvoiceFiguresPreviewExecutionResult)
        self.value = operand
        return "d" * 64


class _Events:
    def __init__(self) -> None:
        self.phases: list[str] = []

    async def phase(self, phase_code: str) -> None:
        self.phases.append(phase_code)


def _executor_context(authority: PinnedAuthorityOperation, subject: str) -> tuple[OperationExecutorContext, _Operands]:
    operands = _Operands()
    context = SimpleNamespace(
        identity=OperationIdentity(
            operation_id="a" * 64,
            definition_id=INVOICE_FIGURES_PREVIEW_OPERATION_DEFINITION_ID,
            subject_ref=subject,
        ),
        authority_operation=authority,
        events=_Events(),
        operands=operands,
    )
    return cast(OperationExecutorContext, context), operands


def test_the_executor_answers_inside_the_exact_profile(
    operation: PinnedAuthorityOperation,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(preview_operation, "require_active_bucket_id", lambda: str(PROFILE))
    subject = profile_operation_subject(str(PROFILE))
    context, operands = _executor_context(operation, subject)
    request = OperationRequest[InvoiceFiguresPreviewRequest](
        definition_id=INVOICE_FIGURES_PREVIEW_OPERATION_DEFINITION_ID,
        subject_ref=subject,
        payload=preview_draft(),
    )

    reference = asyncio.run(InvoiceFiguresPreviewExecutor(NoRate).execute(request, context))

    assert reference == "d" * 64
    assert operands.value is not None
    assert operands.value.result.verdict == "would_accept"


def test_the_executor_fails_on_an_unreachable_rate_source_and_records_no_answer(
    operation: PinnedAuthorityOperation,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(preview_operation, "require_active_bucket_id", lambda: str(PROFILE))
    subject = profile_operation_subject(str(PROFILE))
    context, operands = _executor_context(operation, subject)
    request = OperationRequest[InvoiceFiguresPreviewRequest](
        definition_id=INVOICE_FIGURES_PREVIEW_OPERATION_DEFINITION_ID,
        subject_ref=subject,
        payload=preview_draft(currency="USD"),
    )

    with pytest.raises(CatalogueInvoiceRateError):
        asyncio.run(InvoiceFiguresPreviewExecutor(Unreachable).execute(request, context))
    assert operands.value is None


def test_the_executor_refuses_a_foreign_active_profile(
    operation: PinnedAuthorityOperation,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from ...user_profile.access_errors import ProfileAccessRefusedError

    monkeypatch.setattr(preview_operation, "require_active_bucket_id", lambda: "another-profile")
    subject = profile_operation_subject(str(PROFILE))
    context, operands = _executor_context(operation, subject)
    request = OperationRequest[InvoiceFiguresPreviewRequest](
        definition_id=INVOICE_FIGURES_PREVIEW_OPERATION_DEFINITION_ID,
        subject_ref=subject,
        payload=preview_draft(),
    )

    with pytest.raises(ProfileAccessRefusedError):
        asyncio.run(InvoiceFiguresPreviewExecutor(NoRate).execute(request, context))
    assert operands.value is None


def test_the_definition_is_a_read_holding_its_input_in_secure_custody() -> None:
    definition = build_invoice_figures_preview_definition(NoRate)

    assert definition.capabilities.request_storage.value == "secure_reference"
    assert definition.capabilities.sensitive_input.value == "secure_reference"

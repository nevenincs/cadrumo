"""A single classify of a net-of-withholding invoice is refused as a typed fact, not as arithmetic.

The batch and the staged-work check already name the missing IRPF category. The
single classify runs through its own registered operation, so these cases run that
operation against real stored movements and read what it returns: a typed
refusal kind for a substrate above the cash, the bare input refusal for a gap no
category can explain, and the stored substrate once the category is supplied.
"""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path
from types import SimpleNamespace
from typing import cast

import pytest

from ....core.operations import OperationEffect, profile_operation_subject
from ....domain.calculations.registry.authority import PinnedAuthorityOperation
from ....domain.transactions.enums import BusinessClassification, TransactionDirection
from ....domain.transactions.models import Transaction
from ....domain.transactions.raw_transaction import RawProvenance, RawTransaction, SourceFormat
from ...operations.models import OperationRequest
from ...operations.owner import OperationExecutorContext
from ..classify_operation import LedgerClassifyExecutor
from ..classify_requests import (
    LEDGER_CLASSIFY_OPERATION_DEFINITION_ID,
    LedgerClassifyPatch,
    LedgerClassifyPatchField,
    LedgerClassifyRequest,
)
from ..classify_result_contracts import LedgerClassifyExecutionResult
from ..classify_validation import NEEDS_WITHHOLDING_CATEGORY_CONDITION, needs_withholding_category_verdict
from .bulk_classify_operation_support import PROFILE_ID, BulkClassifySubject

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_NOW = datetime(2026, 5, 4, 9, 30, tzinfo=UTC)
# A received invoice of 2000.00 plus 420.00 IVA, settled net of a 300.00 withholding.
_CASH = Decimal("2120.00")
_ACTIVITY_CATEGORY = "actividad_economica"


def _received(amount: Decimal) -> Transaction:
    """One stored movement of money received, not yet classified."""
    raw = RawTransaction(
        provider_transaction_id="withholding-row",
        booked_date=_NOW.date(),
        value_date=_NOW.date(),
        amount=amount,
        currency="EUR",
        counterparty="Cliente SL",
        description="FACTURA 2026-04",
        provenance=RawProvenance(
            source_path=Path(__file__),
            source_sha256="c" * 64,
            source_row_index=1,
            source_format=SourceFormat.MANUAL,
            ingested_at=_NOW,
            provider_name="test",
        ),
        raw_fields={},
    )
    return Transaction.model_validate(
        {
            "raw": raw,
            "direction": TransactionDirection.INCOMING,
            "business_classification": BusinessClassification.NOT_YET_PROCESSED,
            "source_jurisdiction": "ES",
            "group_label": None,
            "created_at": _NOW,
            "modified_at": _NOW,
        }
    )


@pytest.fixture
def subject(monkeypatch: pytest.MonkeyPatch, authority_operation: PinnedAuthorityOperation) -> BulkClassifySubject:
    """Revision-guarded classification ports around one stored received movement."""
    monkeypatch.setattr(
        "cadrumo.application.operations.profile_guard.require_active_bucket_id", lambda: str(PROFILE_ID)
    )
    return BulkClassifySubject(operation=authority_operation, transactions=(_received(_CASH),))


def _classify(
    subject: BulkClassifySubject, *, taxable_base: str, iva_amount: str, irpf_category: str | None = None
) -> LedgerClassifyExecutionResult:
    """Run the registered single classify and return the private result it stored."""
    stored = next(iter(subject.repository.current.transactions))
    fields = ["business_classification", "iva_amount", "iva_rate", "taxable_base"]
    patch = {
        "business_classification": "BUSINESS",
        "taxable_base": taxable_base,
        "iva_rate": "0.21",
        "iva_amount": iva_amount,
    }
    if irpf_category is not None:
        fields.insert(1, "irpf_category")
        patch["irpf_category"] = irpf_category
    request = OperationRequest[LedgerClassifyRequest](
        definition_id=LEDGER_CLASSIFY_OPERATION_DEFINITION_ID,
        subject_ref=profile_operation_subject(str(PROFILE_ID)),
        payload=LedgerClassifyRequest(
            profile_id=PROFILE_ID,
            transaction_id=stored[:12],
            patch=LedgerClassifyPatch.model_validate(patch),
            patch_fields=cast(tuple[LedgerClassifyPatchField, ...], tuple(sorted(fields))),
        ),
    )
    # The subject's context is identified as the batch operation; this one is the single classify.
    context = cast(
        OperationExecutorContext,
        SimpleNamespace(
            identity=SimpleNamespace(
                definition_id=LEDGER_CLASSIFY_OPERATION_DEFINITION_ID,
                subject_ref=profile_operation_subject(str(PROFILE_ID)),
            ),
            authority_operation=subject.operation,
            cancellation=subject.fence,
            events=subject.events,
            operands=subject.operands,
        ),
    )
    asyncio.run(LedgerClassifyExecutor(subject.compose).execute(request, context))
    return cast(LedgerClassifyExecutionResult, subject.operands.values[-1])


def test_a_substrate_above_the_cash_is_refused_as_a_missing_withholding_category(subject: BulkClassifySubject) -> None:
    """The refusal carries the typed kind the window's blocker is built from, and writes nothing."""
    result = _classify(subject, taxable_base="2000", iva_amount="420")

    assert result.outcome == "validation_error"
    assert result.validation_kind == "needs_withholding_category"
    assert subject.repository.committed_writes == 0
    assert subject.events.effects[-1] is OperationEffect.NONE


def test_a_gap_no_category_explains_stays_the_bare_input_refusal(subject: BulkClassifySubject) -> None:
    """A substrate below the cash is an unrecorded surcharge, which no IRPF category settles."""
    result = _classify(subject, taxable_base="1000", iva_amount="210")

    assert result.outcome == "validation_error"
    assert result.validation_kind == "input"
    assert subject.repository.committed_writes == 0


def test_the_same_substrate_is_stored_once_the_withholding_category_is_named(subject: BulkClassifySubject) -> None:
    """Named, the withholding accepts the gap and the substrate is stored."""
    result = _classify(subject, taxable_base="2000", iva_amount="420", irpf_category=_ACTIVITY_CATEGORY)

    assert result.outcome == "classified"
    assert result.validation_kind == "none"
    stored = next(iter(subject.repository.current.transactions.values()))
    assert (stored.taxable_base, stored.iva_amount, stored.irpf_category) == (
        Decimal("2000.00"),
        Decimal("420.00"),
        _ACTIVITY_CATEGORY,
    )


def test_the_verdict_names_the_irpf_category_as_the_one_input_left_to_the_person() -> None:
    """The remedy binds the movement and leaves only the category open."""
    verdict = needs_withholding_category_verdict(transaction_id="abcdef123456")

    assert verdict.failed_condition_id == NEEDS_WITHHOLDING_CATEGORY_CONDITION
    assert verdict.missing_argument_names == ("irpf_category",)
    bound = {item.argument_name: item.value for item in verdict.argument_bindings}
    assert bound == {"irpf_category": None, "transaction_id": "abcdef123456"}

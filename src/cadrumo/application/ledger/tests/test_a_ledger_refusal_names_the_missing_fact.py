"""A ledger refusal names the fact the person is missing, said in the person's language.

Two refusals used to reach a person as something else. A movement's amount typed
with a sign was reported as an amount nobody had filled in, although the direction
already says which way the money went. A received invoice whose declared base and
IVA stand above the cash was reported as Pydantic's own arithmetic sentence, with
its documentation URL, and said nothing about the withholding category that
accepts the gap.

Every case runs the real staged-work check or the real CSV batch service against
real stored movements, and the sentences are read from the catalogue the backend
serves rather than copied here.
"""

from __future__ import annotations

import asyncio
from datetime import UTC, date, datetime
from decimal import Decimal
from pathlib import Path
from typing import cast

import pytest

from cadrumo.domain.calculations.registry.tests.authored_editions import filing_year_envelope

from ....core.external_constants import OutputLanguage
from ....core.i18n.render import tr
from ....core.operations import profile_operation_subject
from ....domain.calculations.registry.authority import PinnedAuthorityOperation
from ....domain.transactions.enums import BusinessClassification, TransactionDirection
from ....domain.transactions.models import Transaction
from ....domain.transactions.raw_transaction import RawProvenance, RawTransaction, SourceFormat
from ...operations.models import OperationRequest
from ..bulk_classify_operation import (
    LEDGER_BULK_CLASSIFY_OPERATION_DEFINITION_ID,
    LedgerBulkClassifyExecutionResult,
    LedgerBulkClassifyExecutor,
    LedgerBulkClassifyRequest,
)
from ..models import BulkClassifyResult
from ..staged_check import check_staged_work
from ..staged_check_contracts import (
    LedgerStagedCell,
    LedgerStagedCheckRequest,
    LedgerStagedCheckResult,
    LedgerStagedDraft,
    LedgerStagedDraftField,
    LedgerStagedRow,
)
from ..staged_check_words import BLOCKER_FIX_LOCALE_KEYS, BLOCKER_WORDS_LOCALE_KEYS
from .bulk_classify_operation_support import PROFILE_ID, BulkClassifySubject

_YEAR = filing_year_envelope().horizon

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_NOW = datetime(_YEAR, 5, 4, 9, 30, tzinfo=UTC)
_PROFILE = PROFILE_ID
# A received invoice of 2000.00 plus 420.00 IVA, settled net of a 300.00 withholding.
_CASH = Decimal("2120.00")
_BASE = Decimal("2000.00")
_CUOTA = Decimal("420.00")
_ACTIVITY_CATEGORY = "actividad_economica"


def _received(amount: Decimal) -> Transaction:
    """One stored, classified movement of money received."""
    raw = RawTransaction(
        provider_transaction_id="withholding-row",
        booked_date=date(_YEAR, 5, 2),
        value_date=date(_YEAR, 5, 2),
        amount=amount,
        currency="EUR",
        counterparty="Cliente SL",
        description=f"FACTURA {_YEAR}-04",
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
            "business_classification": BusinessClassification.BUSINESS,
            "source_jurisdiction": "ES",
            "group_label": None,
            "created_at": _NOW,
            "modified_at": _NOW,
        }
    )


@pytest.fixture
def received(authority_operation: PinnedAuthorityOperation) -> Transaction:
    """The stored movement every case here stages work against."""
    assert authority_operation is not None
    return _received(_CASH)


def _check(
    *,
    operation: PinnedAuthorityOperation,
    rows: tuple[LedgerStagedRow, ...] = (),
    drafts: tuple[LedgerStagedDraft, ...] = (),
    held: tuple[Transaction, ...] = (),
    language: OutputLanguage = OutputLanguage.EN,
) -> LedgerStagedCheckResult:
    """Answer one staged request through the real check."""
    return check_staged_work(
        LedgerStagedCheckRequest(profile_id=_PROFILE, rows=rows, drafts=drafts, output_language=language),
        {transaction.transaction_id: transaction for transaction in held},
        operation=operation,
        profile_id=_PROFILE,
    )


def _draft(**fields: str) -> LedgerStagedDraft:
    return LedgerStagedDraft(
        key="d",
        fields=tuple(LedgerStagedDraftField.model_validate({"field": k, "value": v}) for k, v in fields.items()),
    )


def _substrate_cells(*, irpf_category: str | None = None) -> tuple[LedgerStagedCell, ...]:
    """The invoice substrate as it is typed into the IVA columns."""
    cells = [
        LedgerStagedCell(field="taxable_base", value=str(_BASE)),
        LedgerStagedCell(field="iva_rate", value="0.21"),
        LedgerStagedCell(field="iva_amount", value=str(_CUOTA)),
    ]
    if irpf_category is not None:
        cells.append(LedgerStagedCell(field="irpf_category", value=irpf_category))
    return tuple(cells)


# ---- A signed amount is a sign, not a missing amount ------------------------


def test_a_signed_draft_amount_is_held_back_as_a_sign_and_not_as_a_missing_amount(
    authority_operation: PinnedAuthorityOperation,
) -> None:
    """``-50,00`` with the direction already set to outflow is a signed amount."""
    answer = _check(
        operation=authority_operation,
        drafts=(
            _draft(
                booked_date=date(_YEAR, 5, 2).isoformat(),
                amount="-50.00",
                currency="EUR",
                direction=TransactionDirection.OUTGOING.value,
                description="SUMINISTRO",
            ),
        ),
    ).drafts[0]

    held = {blocker.kind: blocker for blocker in answer.blockers}
    assert "amount_signed" in held
    assert set(held["amount_signed"].fields) == {"amount", "direction"}
    # The amount was typed, so nothing reports it as a fact nobody filled in.
    assert "draft_incomplete" not in held


def test_the_same_amount_without_its_sign_is_not_held_back(
    authority_operation: PinnedAuthorityOperation,
) -> None:
    """The refusal is the sign, not the figure."""
    answer = _check(
        operation=authority_operation,
        drafts=(
            _draft(
                booked_date=date(_YEAR, 5, 2).isoformat(),
                amount="50.00",
                currency="EUR",
                direction=TransactionDirection.OUTGOING.value,
                description="SUMINISTRO",
            ),
        ),
    ).drafts[0]

    assert answer.blockers == ()


def test_a_signed_amount_staged_on_a_stored_movement_is_held_back_too(
    authority_operation: PinnedAuthorityOperation, received: Transaction
) -> None:
    """The amount/direction contract is the same whichever row the cell sits on."""
    row = LedgerStagedRow(
        transaction_id=received.transaction_id,
        cells=(LedgerStagedCell(field="amount", value="-50.00"),),
    )

    answer = _check(operation=authority_operation, rows=(row,), held=(received,)).rows[0]

    assert [blocker.kind for blocker in answer.blockers] == ["amount_signed"]


def test_a_stored_movement_nobody_edited_is_never_held_back_for_its_own_amount(
    authority_operation: PinnedAuthorityOperation, received: Transaction
) -> None:
    """What a store holds is the writer's business: no cell, no amount finding."""
    answer = _check(
        operation=authority_operation,
        rows=(LedgerStagedRow(transaction_id=received.transaction_id),),
        held=(received,),
    ).rows[0]

    assert answer.blockers == ()


# ---- A substrate above the cash names the withholding category --------------


def test_a_substrate_above_the_cash_names_the_withholding_category(
    authority_operation: PinnedAuthorityOperation, received: Transaction
) -> None:
    """The IVA columns alone do not say the gap is a withholding; the IRPF column does."""
    row = LedgerStagedRow(transaction_id=received.transaction_id, cells=_substrate_cells())

    answer = _check(operation=authority_operation, rows=(row,), held=(received,)).rows[0]

    held = {blocker.kind: blocker for blocker in answer.blockers}
    assert "needs_withholding_category" in held
    assert held["needs_withholding_category"].fields == ("irpf_category",)


def test_declaring_the_withholding_category_accepts_the_same_substrate(
    authority_operation: PinnedAuthorityOperation, received: Transaction
) -> None:
    """Named, the withholding explains the gap and the row is savable."""
    row = LedgerStagedRow(
        transaction_id=received.transaction_id,
        cells=_substrate_cells(irpf_category=_ACTIVITY_CATEGORY),
    )

    answer = _check(operation=authority_operation, rows=(row,), held=(received,)).rows[0]

    assert [blocker.kind for blocker in answer.blockers] == []


@pytest.mark.parametrize("language", [OutputLanguage.EN, OutputLanguage.ES])
def test_the_substrate_refusal_is_served_in_the_language_asked(
    language: OutputLanguage, authority_operation: PinnedAuthorityOperation, received: Transaction
) -> None:
    """The sentence and its fix are the catalogue's, in the language the request asked for."""
    row = LedgerStagedRow(transaction_id=received.transaction_id, cells=_substrate_cells())

    answer = _check(operation=authority_operation, rows=(row,), held=(received,), language=language).rows[0]
    blocker = next(found for found in answer.blockers if found.kind == "needs_withholding_category")

    assert blocker.words_language is language
    assert blocker.words == tr(BLOCKER_WORDS_LOCALE_KEYS["needs_withholding_category"], locale=language.value)
    assert blocker.fix_words == tr(BLOCKER_FIX_LOCALE_KEYS["needs_withholding_category"], locale=language.value)
    assert "pydantic" not in f"{blocker.words}{blocker.fix_words}".lower()


# ---- The same refusal through the real registered batch operation ----------


@pytest.fixture
def batch(monkeypatch: pytest.MonkeyPatch, authority_operation: PinnedAuthorityOperation) -> BulkClassifySubject:
    """Revision-guarded classification ports around one stored received movement."""
    monkeypatch.setattr(
        "cadrumo.application.operations.profile_guard.require_active_bucket_id", lambda: str(PROFILE_ID)
    )
    return BulkClassifySubject(operation=authority_operation, transactions=(_received(_CASH),))


def _table(columns: tuple[str, ...]) -> str:
    """The header line of one classification table."""
    return ",".join(columns) + "\n"


def _classify(subject: BulkClassifySubject, csv_text: str, *, language: OutputLanguage) -> BulkClassifyResult:
    """Run one table through the registered executor, in the language it asks for."""
    request = OperationRequest[LedgerBulkClassifyRequest](
        definition_id=LEDGER_BULK_CLASSIFY_OPERATION_DEFINITION_ID,
        subject_ref=profile_operation_subject(str(PROFILE_ID)),
        payload=LedgerBulkClassifyRequest(profile_id=PROFILE_ID, csv_text=csv_text, output_language=language),
    )
    asyncio.run(LedgerBulkClassifyExecutor(subject.compose).execute(request, subject.context))
    execution = cast(LedgerBulkClassifyExecutionResult, subject.operands.values[-1])
    result = execution.projection.result
    assert result is not None
    return result


@pytest.mark.parametrize("language", [OutputLanguage.EN, OutputLanguage.ES])
def test_the_batch_says_why_a_net_of_withholding_row_was_not_taken(
    language: OutputLanguage, batch: BulkClassifySubject
) -> None:
    """The row's reason is the registered refusal, not Pydantic's arithmetic report."""
    stored = next(iter(batch.repository.current.transactions))
    result = _classify(
        batch,
        _table(("transaction_id", "classification", "taxable_base", "iva_rate", "iva_amount"))
        + f"{stored},BUSINESS,{_BASE},0.21,{_CUOTA}\n",
        language=language,
    )

    assert result.applied == 0
    assert len(result.failures) == 1
    reason = result.failures[0].reason
    assert reason == tr("errors.error.ledger_gross_above_cash_needs_withholding_category", locale=language.value)
    for leaked in ("pydantic", "taxable_base", "iva_amount", "validation error"):
        assert leaked not in reason.lower()


def test_the_batch_takes_the_same_row_once_the_withholding_category_is_named(
    batch: BulkClassifySubject,
) -> None:
    """Named, the withholding is accepted and the substrate is stored."""
    stored = next(iter(batch.repository.current.transactions))
    result = _classify(
        batch,
        _table(("transaction_id", "classification", "taxable_base", "iva_rate", "iva_amount", "irpf_category"))
        + f"{stored},BUSINESS,{_BASE},0.21,{_CUOTA},{_ACTIVITY_CATEGORY}\n",
        language=OutputLanguage.ES,
    )

    assert result.failures == ()
    assert result.applied == 1
    saved = batch.repository.current.transactions[stored]
    assert (saved.taxable_base, saved.iva_amount, saved.irpf_category) == (_BASE, _CUOTA, _ACTIVITY_CATEGORY)


def test_the_currency_a_new_movement_carries_is_still_required_of_it(
    authority_operation: PinnedAuthorityOperation,
) -> None:
    """A new movement names its currency; nothing here guesses one for it.

    The window fills the visible field from the account's served currency, so
    the saved movement carries the currency explicitly rather than inheriting a
    silent default from a writer.
    """
    answer = _check(
        operation=authority_operation,
        drafts=(
            _draft(
                booked_date=date(_YEAR, 5, 2).isoformat(),
                amount="50.00",
                direction=TransactionDirection.OUTGOING.value,
                description="SUMINISTRO",
            ),
        ),
    ).drafts[0]

    held = {blocker.kind: blocker for blocker in answer.blockers}
    assert held["draft_incomplete"].fields == ("currency",)

"""Correcting a movement's amount keeps its tax split agreeing, or says why it does not.

A person changes the amount of a stored expense and leaves the base and the
IVA amount as they were. The split no longer adds up to the amount, so the
canonical writer refuses it. The refusal must reach the person as a sentence in
their language that names the figures, not as an arithmetic report, and the same
edit with an agreeing base and IVA amount must be written with its history.

Every case drives the real registered update executor against an in-memory
catalogue and event history.
"""

from __future__ import annotations

from datetime import UTC, date, datetime
from decimal import Decimal
from pathlib import Path
from types import SimpleNamespace
from typing import cast
from uuid import UUID

import pytest

from ....core.external_constants import OutputLanguage
from ....core.i18n.render import tr
from ....core.operations import OperationEffect, profile_operation_subject
from ....domain.buckets.event import BucketEventType
from ....domain.calculations.registry.authority import PinnedAuthorityOperation
from ....domain.transactions.enums import BusinessClassification, TransactionDirection
from ....domain.transactions.models import Transaction, TransactionCatalogue
from ....domain.transactions.raw_transaction import RawProvenance, RawTransaction, SourceFormat
from ...operations.models import OperationRequest
from ...operations.owner import OperationExecutorContext
from ...operations.refusal_evidence import OperationRefusalEvidence
from .. import update_contracts as contracts
from .. import update_operation
from ..action_ports import LedgerActionPorts, LedgerActionPortsFactory
from ..own_account_ports import OwnAccountRepositoryProtocol
from .ledger_input_rule_support import Cancellation, RecordingEvents, RecordingOperands
from .test_classification_rule_plan import BUCKET, ClassificationScenario

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_NOW = datetime(2026, 5, 4, 9, 30, tzinfo=UTC)
_PROFILE = UUID(BUCKET)


def _office_rent() -> Transaction:
    """A stored business expense of 800.00 split into 661.16 base and 138.84 IVA at 21 %."""
    raw = RawTransaction(
        provider_transaction_id="amount-correction-row",
        booked_date=date(2026, 5, 2),
        value_date=date(2026, 5, 2),
        amount=Decimal("800.00"),
        currency="EUR",
        counterparty="Landlord SL",
        description="Office rent",
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
            "direction": TransactionDirection.OUTGOING,
            "business_classification": BusinessClassification.BUSINESS,
            "taxable_base": Decimal("661.16"),
            "iva_rate": Decimal("0.21"),
            "iva_amount": Decimal("138.84"),
            "source_jurisdiction": "ES",
            "group_label": None,
            "created_at": _NOW,
            "modified_at": _NOW,
        }
    )


def _unused_own_accounts(*, bucket_id: str) -> OwnAccountRepositoryProtocol:
    raise AssertionError(f"unexpected own-account lookup for {bucket_id}")


class _Run:
    """One executor run and what it left behind."""

    def __init__(self, scenario: ClassificationScenario, stored: Transaction) -> None:
        self.scenario = scenario
        self.stored = stored
        self.events = RecordingEvents()
        self.operands = RecordingOperands()
        self.result: str | OperationRefusalEvidence | None = None

    @property
    def detail(self) -> contracts.LedgerUpdateExecutionResult:
        value = self.operands.value
        assert isinstance(value, contracts.LedgerUpdateExecutionResult)
        return value


async def _correct(
    operation: PinnedAuthorityOperation,
    monkeypatch: pytest.MonkeyPatch,
    *,
    language: OutputLanguage = OutputLanguage.EN,
    **patch: str,
) -> _Run:
    monkeypatch.setattr("cadrumo.application.operations.profile_guard.require_active_bucket_id", lambda: BUCKET)
    stored = _office_rent()
    scenario = ClassificationScenario(TransactionCatalogue.from_transactions((stored,)), operation=operation)
    run = _Run(scenario, stored)
    context = SimpleNamespace(
        identity=SimpleNamespace(
            definition_id=contracts.LEDGER_UPDATE_OPERATION_DEFINITION_ID,
            subject_ref=profile_operation_subject(BUCKET),
        ),
        authority_operation=operation,
        cancellation=Cancellation(),
        events=run.events,
        operands=run.operands,
    )
    ports: LedgerActionPorts = scenario.ports
    executor = update_operation.LedgerUpdateExecutor(
        cast(LedgerActionPortsFactory, lambda **_kwargs: ports),
        own_account_repository_factory=_unused_own_accounts,
    )
    request = OperationRequest[contracts.LedgerUpdateRequest](
        definition_id=contracts.LEDGER_UPDATE_OPERATION_DEFINITION_ID,
        subject_ref=context.identity.subject_ref,
        payload=contracts.LedgerUpdateRequest(
            profile_id=_PROFILE,
            transaction_id=stored.transaction_id[:12],
            patch=contracts.LedgerUpdatePatch.model_validate(patch),
            patch_fields=cast(tuple[contracts.LedgerUpdatePatchField, ...], tuple(sorted(patch))),
            output_language=language,
        ),
    )
    run.result = await executor.execute(request, cast(OperationExecutorContext, context))
    return run


@pytest.mark.asyncio
@pytest.mark.parametrize("language", [OutputLanguage.EN, OutputLanguage.ES])
async def test_a_new_amount_the_split_no_longer_matches_is_refused_with_a_sentence_naming_the_figures(
    language: OutputLanguage, operation: PinnedAuthorityOperation, monkeypatch: pytest.MonkeyPatch
) -> None:
    run = await _correct(operation, monkeypatch, language=language, amount="850")

    assert isinstance(run.result, OperationRefusalEvidence)
    assert run.result.refusal_code == contracts.LEDGER_UPDATE_VALIDATION_REFUSAL_CODE
    assert run.events.effects == [OperationEffect.UNKNOWN, OperationEffect.NONE]
    assert run.detail.outcome == "validation_error"
    (sentence,) = run.detail.validation_messages
    assert sentence == tr(
        "errors.error.ledger_gross_does_not_reconstitute",
        locale=language.value,
        reconstituted=Decimal("800.00"),
        expected=Decimal("850.00"),
    )
    assert "800.00" in sentence and "850.00" in sentence
    for developer_text in ("taxable_base", "iva_amount", "recargo_amount", "--recargo", "to the cent"):
        assert developer_text not in sentence
    assert run.scenario.ports.transaction_repository.load().transactions == {run.stored.transaction_id: run.stored}
    assert run.scenario.ports.bucket_event_repository.load().events == {}


class _Lines:
    """The log sink: the logger delivers on another thread, so the test reads what it was handed."""

    def __init__(self) -> None:
        self.lines: list[str] = []

    def info(self, template: str, *arguments: object) -> None:
        self.lines.append(template % arguments)


@pytest.mark.asyncio
async def test_the_refusal_is_logged_with_the_rule_that_refused_and_no_figure(
    operation: PinnedAuthorityOperation, monkeypatch: pytest.MonkeyPatch
) -> None:
    sink = _Lines()
    monkeypatch.setattr(update_operation, "_log", sink)

    await _correct(operation, monkeypatch, amount="850")

    (line,) = sink.lines
    assert line.startswith("ledger update refused ")
    assert "ERROR_TRANSACTION_VALIDATION:errors.error.ledger_gross_does_not_reconstitute" in line
    for figure in ("850", "800", "661", "138"):
        assert figure not in line


@pytest.mark.asyncio
async def test_a_new_amount_with_a_base_and_iva_amount_that_agree_is_written_with_its_history(
    operation: PinnedAuthorityOperation, monkeypatch: pytest.MonkeyPatch
) -> None:
    run = await _correct(operation, monkeypatch, amount="850", taxable_base="702.48", iva_amount="147.52")

    assert isinstance(run.result, str)
    assert run.events.effects == [OperationEffect.UNKNOWN, OperationEffect.UPDATED]
    assert run.detail.outcome == "updated"
    assert run.detail.result is not None and run.detail.result.bucket_event_ids
    (saved,) = run.scenario.ports.transaction_repository.load().transactions.values()
    assert (saved.raw.amount, saved.taxable_base, saved.iva_amount) == (
        Decimal("850.00"),
        Decimal("702.48"),
        Decimal("147.52"),
    )
    assert saved.edit_lineage[-1].previous_transaction_id == run.stored.transaction_id
    recorded = tuple(run.scenario.ports.bucket_event_repository.load().events.values())
    assert BucketEventType.LEDGER_TRANSACTION_UPDATED in {event.event_type for event in recorded}
    assert {event.event_id for event in recorded} == set(run.detail.result.bucket_event_ids)

"""The single classify is the door that states which LIVA art. 20.Uno exemption a row falls under.

Whether an exempt operation gives the right to deduct depends on its number in
art. 20.Uno, so the article is the operator's statement, never inferred. These
cases run the registered classify operation against a real stored movement and
read back what it stored and returned: a member of the registry vocabulary is
kept, an undeclared token and an article on a row that is not domestic exempt
are refused without a write, and a later classify that does not select the
article leaves it as stated.
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
from ....domain.calculations.registry.iva_legal_vocabulary import resolve_iva_exemption_article_catalogue
from ....domain.calculations.registry.tests.authored_editions import filing_year_envelope
from ....domain.iva.schema import IvaExemptionArticle
from ....domain.transactions.enums import BusinessClassification, TransactionDirection
from ....domain.transactions.models import Transaction
from ....domain.transactions.raw_transaction import RawProvenance, RawTransaction, SourceFormat
from ...operations.models import OperationRequest
from ...operations.owner import OperationExecutorContext
from ..classify_correlation import classification_selected_fields_match
from ..classify_operation import LedgerClassifyExecutor
from ..classify_requests import (
    LEDGER_CLASSIFY_OPERATION_DEFINITION_ID,
    LedgerClassifyPatch,
    LedgerClassifyPatchField,
    LedgerClassifyRequest,
)
from ..classify_result_contracts import LedgerClassifyExecutionResult
from .bulk_classify_operation_support import PROFILE_ID, BulkClassifySubject

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_NOW = datetime(filing_year_envelope().horizon, 5, 4, 9, 30, tzinfo=UTC)
_EDUCATION = "art_20_uno_9"


def _received() -> Transaction:
    """One stored movement of money received for a lesson, not yet classified."""
    raw = RawTransaction(
        provider_transaction_id="exempt-lesson",
        booked_date=_NOW.date(),
        value_date=_NOW.date(),
        amount=Decimal("300.00"),
        currency="EUR",
        counterparty="Academia SL",
        description="CURSO IDIOMAS",
        provenance=RawProvenance(
            source_path=Path(__file__),
            source_sha256="e" * 64,
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
    return BulkClassifySubject(operation=authority_operation, transactions=(_received(),))


def _classify(
    subject: BulkClassifySubject, patch: dict[str, str]
) -> tuple[LedgerClassifyPatch, LedgerClassifyExecutionResult]:
    """Run the registered single classify and return the private result it stored."""
    stored = next(iter(subject.repository.current.transactions))
    wire_patch = LedgerClassifyPatch.model_validate(patch)
    request = OperationRequest[LedgerClassifyRequest](
        definition_id=LEDGER_CLASSIFY_OPERATION_DEFINITION_ID,
        subject_ref=profile_operation_subject(str(PROFILE_ID)),
        payload=LedgerClassifyRequest(
            profile_id=PROFILE_ID,
            transaction_id=stored[:12],
            patch=wire_patch,
            patch_fields=cast(tuple[LedgerClassifyPatchField, ...], tuple(sorted(patch))),
        ),
    )
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
    return wire_patch, cast(LedgerClassifyExecutionResult, subject.operands.values[-1])


def _stored(subject: BulkClassifySubject) -> Transaction:
    return next(iter(subject.repository.current.transactions.values()))


def _exempt(article: str) -> dict[str, str]:
    return {"business_classification": "BUSINESS", "iva_category": "domestic_exempt", "exemption_article": article}


def test_a_declared_article_is_stored_and_returned_as_stated(subject: BulkClassifySubject) -> None:
    """The article reaches the stored row and the result, and the result correlates with the request."""
    patch, result = _classify(subject, _exempt(_EDUCATION))

    assert result.outcome == "classified"
    assert result.result is not None
    assert result.result.exemption_article == _EDUCATION
    assert _stored(subject).exemption_article == IvaExemptionArticle(_EDUCATION)
    assert subject.events.effects[-1] is OperationEffect.UPDATED
    assert classification_selected_fields_match(
        patch=patch, fields=tuple(sorted(_exempt(_EDUCATION))), m210=None, result=result.result
    )


def test_every_vocabulary_member_is_accepted_on_the_row_date(
    subject: BulkClassifySubject, authority_operation: PinnedAuthorityOperation
) -> None:
    """The door takes exactly what the registry declares for the row's date, the catch-all included."""
    members = resolve_iva_exemption_article_catalogue(effective_date=_NOW.date(), authority=authority_operation)
    for member in sorted(item.value for item in members.all_articles):
        _patch, result = _classify(subject, _exempt(member))
        assert result.outcome == "classified", member
        assert _stored(subject).exemption_article == IvaExemptionArticle(member)


def test_an_undeclared_article_is_refused_without_a_write(subject: BulkClassifySubject) -> None:
    """A token the registry does not declare is the classify input refusal, and nothing is stored."""
    _patch, result = _classify(subject, _exempt("art_20_uno_99"))

    assert result.outcome == "validation_error"
    assert result.validation_kind == "input"
    assert any("art_20_uno_99" in message for message in result.validation_messages)
    assert subject.repository.committed_writes == 0
    assert OperationEffect.UPDATED not in subject.events.effects
    assert _stored(subject).exemption_article is None


def test_an_article_on_a_row_that_is_not_domestic_exempt_is_refused(subject: BulkClassifySubject) -> None:
    """The article qualifies only a domestic exempt row, so it is refused beside another IVA category."""
    patch = {**_exempt(_EDUCATION), "iva_category": "domestic_general"}
    _patch, result = _classify(subject, patch)

    assert result.outcome == "validation_error"
    assert any("exemption_article" in message for message in result.validation_messages)
    assert subject.repository.committed_writes == 0


def test_a_later_classify_that_does_not_select_the_article_keeps_it(subject: BulkClassifySubject) -> None:
    """Omitting the article leaves the stated one in place rather than clearing it."""
    _classify(subject, _exempt(_EDUCATION))
    _patch, result = _classify(
        subject, {"business_classification": "BUSINESS", "iva_category": "domestic_exempt", "notes": "curso anual"}
    )

    assert result.outcome == "classified"
    assert _stored(subject).exemption_article == IvaExemptionArticle(_EDUCATION)

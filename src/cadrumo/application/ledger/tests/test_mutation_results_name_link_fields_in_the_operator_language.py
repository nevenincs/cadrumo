"""A ledger mutation's result names the transaction's link fields in the language its request carries.

``ledger view`` serves a row's link fields in the operator's language. A mutation that returns
the same row must name them in the same words, or one row reads in two languages.
"""

from __future__ import annotations

from collections.abc import Iterator
from datetime import UTC, date, datetime
from decimal import Decimal
from pathlib import Path
from uuid import UUID

import pytest

from ....core.external_constants import DEFAULT_OUTPUT_LANGUAGE, OutputLanguage
from ....domain.calculations.registry.authority import bundled_indexed_authority
from ....domain.transactions.enums import BusinessClassification, TransactionDirection, TransactionLifecycleState
from ....domain.transactions.models import Transaction
from ....domain.transactions.raw_transaction import RawProvenance, RawTransaction, SourceFormat
from ..actions_common import build_manual_ledger_result
from ..classify_requests import LedgerClassifyRequest
from ..classify_result_projection import classification_result_from_action
from ..lifecycle_contracts import LEDGER_ARCHIVE_OPERATION_DEFINITION_ID, LedgerLifecycleMutationRequest
from ..lifecycle_projections import project_lifecycle_mutation_from_action
from ..manual_read import ledger_transaction_payload
from ..transaction_projection import LedgerTransactionLinkFieldProjection, LedgerTransactionProjection

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_PROFILE = UUID("5aa00000-0000-4000-8000-0000000000aa")
_EVENT_ID = "e" * 64


@pytest.fixture
def pinned_authority() -> Iterator[None]:
    """Build domain transactions under the same governed-fact lease as production."""
    with bundled_indexed_authority().operation():
        yield


def _row(state: TransactionLifecycleState) -> Transaction:
    raw = RawTransaction(
        provider_transaction_id="language-projection-row",
        booked_date=date.today(),
        value_date=None,
        amount=Decimal("100.00"),
        currency="EUR",
        counterparty="Vendor SL",
        description="materials",
        provenance=RawProvenance(
            source_path=Path(__file__),
            source_sha256="c" * 64,
            source_row_index=1,
            source_format=SourceFormat.MANUAL,
            ingested_at=datetime.now(UTC),
            provider_name="test",
        ),
        raw_fields={"source": "test"},
    )
    return Transaction.model_validate(
        {
            "raw": raw,
            "direction": TransactionDirection.OUTGOING,
            "business_classification": BusinessClassification.BUSINESS,
            "classified_by": "manual",
            "lifecycle_state": state,
            "source_jurisdiction": "ES",
            "group_label": None,
        },
    )


def _view_link_fields(row: Transaction, language: OutputLanguage) -> tuple[LedgerTransactionLinkFieldProjection, ...]:
    return LedgerTransactionProjection.from_payload(ledger_transaction_payload(row), language=language).link_fields


def test_the_mutation_requests_carry_the_view_requests_language_default() -> None:
    assert LedgerClassifyRequest.model_fields["output_language"].default is DEFAULT_OUTPUT_LANGUAGE
    assert LedgerLifecycleMutationRequest.model_fields["output_language"].default is DEFAULT_OUTPUT_LANGUAGE


@pytest.mark.usefixtures("pinned_authority")
def test_a_classification_result_names_the_link_fields_in_the_language_the_view_serves() -> None:
    row = _row(TransactionLifecycleState.ACTIVE)
    result = build_manual_ledger_result(str(_PROFILE), row, (_EVENT_ID,))

    english = classification_result_from_action(_PROFILE, result, language=OutputLanguage.EN)
    spanish = classification_result_from_action(_PROFILE, result, language=OutputLanguage.ES)

    assert english.transaction is not None
    assert spanish.transaction is not None
    assert english.transaction.link_fields == _view_link_fields(row, OutputLanguage.EN)
    assert spanish.transaction.link_fields == _view_link_fields(row, OutputLanguage.ES)
    assert [item.field_words for item in english.transaction.link_fields] != [
        item.field_words for item in spanish.transaction.link_fields
    ]


@pytest.mark.usefixtures("pinned_authority")
def test_a_lifecycle_result_names_the_link_fields_in_the_language_the_view_serves() -> None:
    replaced = _row(TransactionLifecycleState.ACTIVE)
    written = replaced.model_copy(update={"lifecycle_state": TransactionLifecycleState.ARCHIVED})

    projection = project_lifecycle_mutation_from_action(
        _PROFILE,
        LEDGER_ARCHIVE_OPERATION_DEFINITION_ID,
        build_manual_ledger_result(str(_PROFILE), written, (_EVENT_ID,)),
        replaced,
        language=OutputLanguage.EN,
    )

    assert projection.transaction.link_fields == _view_link_fields(written, OutputLanguage.EN)

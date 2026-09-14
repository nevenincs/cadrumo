"""What constitutes one explicit Modelo 210 declaration, and what can carry it.

Two rules, both refusals, both previously decided inside a CLI option object.

The four declaration answers are answered together or not at all. A code with
no rate, or a rate with no gross amount, describes no filing position — and
persisting half of one would leave a classification the IRNR projection cannot
compute from, which is a worse outcome than being told to finish answering.

Modelo 210 declares non-resident INCOME, so an outgoing row cannot carry the
classification however complete the answers are. That is a fact about the
model, not about how the operator typed the command.
"""

from __future__ import annotations

from collections.abc import Iterable, Iterator
from contextlib import contextmanager
from datetime import UTC, date, datetime
from decimal import Decimal
from pathlib import Path
from typing import TypedDict

import pytest

from ....core.irnr import M210PayerMode
from ....domain.transactions.enums import BusinessClassification, TransactionDirection
from ....domain.transactions.errors import TransactionValidationError
from ....domain.transactions.models import (
    LedgerDatePartition,
    OutOfWindowTransactionIndexEntry,
    OutOfWindowTransactionSummary,
    Transaction,
    TransactionCatalogue,
)
from ....domain.transactions.protocols import TransactionCatalogueRepositoryProtocol
from ....domain.transactions.raw_transaction import RawProvenance, RawTransaction, SourceFormat
from ..m210_classification import resolve_m210_income_classification

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_BUCKET = "13131313-1313-4313-8313-131313131313"
_CODE = "01"


def _transaction(*, provider_id: str, direction: TransactionDirection) -> Transaction:
    raw = RawTransaction(
        provider_transaction_id=provider_id,
        booked_date=date(2026, 3, 10),
        value_date=None,
        amount=Decimal("1000.00"),
        currency="EUR",
        counterparty="Arrendatario SL",
        description="alquiler",
        provenance=RawProvenance(
            source_path=Path(__file__),
            source_sha256="c" * 64,
            source_row_index=1,
            source_format=SourceFormat.MANUAL,
            ingested_at=datetime(2026, 3, 10, 9, 30, tzinfo=UTC),
            provider_name="test",
        ),
        raw_fields={},
    )
    return Transaction.model_validate(
        {
            "raw": raw,
            "direction": direction,
            "business_classification": BusinessClassification.NOT_YET_PROCESSED,
            "source_jurisdiction": "ES",
            "group_label": None,
            "created_at": datetime(2026, 3, 10, 9, 30, tzinfo=UTC),
            "modified_at": datetime(2026, 3, 10, 9, 30, tzinfo=UTC),
        }
    )


@contextmanager
def _stored(*transactions: Transaction) -> Iterator[TransactionCatalogueRepositoryProtocol]:
    """Build a deterministic catalogue through the application read protocol."""
    yield _InMemoryTransactionRepository(
        bucket_id=_BUCKET,
        catalogue=TransactionCatalogue.from_transactions(transactions),
    )


class _InMemoryTransactionRepository(TransactionCatalogueRepositoryProtocol):
    """Deterministic inward fake for the transaction catalogue read port."""

    def __init__(self, *, bucket_id: str, catalogue: TransactionCatalogue) -> None:
        self._bucket_id = bucket_id
        self._catalogue = catalogue

    @property
    def bucket_id(self) -> str:
        return self._bucket_id

    def exists(self) -> bool:
        return bool(self._catalogue.transactions)

    def load(self) -> TransactionCatalogue:
        return self._catalogue

    def load_for_date_range(self, start: date, end: date) -> TransactionCatalogue:
        return TransactionCatalogue.from_transactions(
            transaction
            for transaction in self._catalogue
            if start <= (transaction.raw.value_date or transaction.raw.booked_date) <= end
        )

    def load_by_ids(self, transaction_ids: Iterable[str]) -> TransactionCatalogue:
        requested = frozenset(transaction_ids)
        return TransactionCatalogue.from_transactions(
            transaction for transaction in self._catalogue if transaction.transaction_id in requested
        )

    def partition_by_date_range(self, start: date, end: date) -> LedgerDatePartition:
        in_window: list[Transaction] = []
        out_of_window: list[OutOfWindowTransactionIndexEntry] = []
        for transaction in self._catalogue:
            filing_date = transaction.raw.value_date or transaction.raw.booked_date
            if start <= filing_date <= end:
                in_window.append(transaction)
            else:
                out_of_window.append(
                    OutOfWindowTransactionIndexEntry(
                        transaction_id=transaction.transaction_id,
                        filing_date=filing_date,
                    )
                )
        return LedgerDatePartition(
            in_window=TransactionCatalogue.from_transactions(in_window),
            out_of_window=tuple(out_of_window),
            out_of_window_summary=OutOfWindowTransactionSummary.from_index_entries(out_of_window),
            index_complete=True,
        )

    def save(self, catalogue: TransactionCatalogue) -> None:
        self._catalogue = catalogue


class _Answers(TypedDict, total=False):
    """The classification answers an operator supplies, keyed as the resolver takes them.

    A `dict[str, object]` cannot be unpacked into a typed signature: every
    value arrives as `object` and the checker reports one error per parameter
    per call site -- 29 of them here, silenced by five `type: ignore` comments
    that `ty` does not honour anyway. Declaring the shape types the unpack
    instead, so a case supplying the wrong type for a field is caught at the
    call rather than suppressed at it.

    `total=False` because every field is an override: the resolver defaults
    each to None, and the refusal cases below exist precisely to omit them.
    """

    tipo_renta_code: str | None
    gross_income_amount: Decimal | None
    applicable_rate: Decimal | None
    payer_mode: M210PayerMode | None
    payer_id: str | None
    asset_or_right_id: str | None


def _complete(**overrides: object) -> _Answers:
    payload: _Answers = {
        "tipo_renta_code": _CODE,
        "gross_income_amount": Decimal("1000.00"),
        "applicable_rate": Decimal("0.19"),
        "payer_mode": M210PayerMode.SINGLE_PAYER,
        # Required by the domain model: a non-35 income code declared under a
        # single payer must name that payer. Omitting it makes the "complete"
        # fixture incomplete and every refusal below untestable.
        "payer_id": "B12345674",
    }
    # `update` rather than a literal merge: the overrides arrive untyped from
    # `**overrides`, and a TypedDict rejects an unknown key at type level while
    # still accepting this call, which is the behaviour the cases want.
    payload.update(overrides)  # ty: ignore[invalid-argument-type]
    return payload


def test_supplying_no_answer_at_all_asks_for_nothing() -> None:
    """An operator not classifying under M210 must not be made to."""
    with _stored(_transaction(provider_id="a", direction=TransactionDirection.INCOMING)) as repository:
        transaction_id = next(iter(repository.load().transactions))
        result = resolve_m210_income_classification(
            bucket_id=_BUCKET,
            transaction_id=transaction_id,
            transaction_repository=repository,
        )

    assert result is None


def test_a_complete_declaration_on_an_incoming_row_is_built() -> None:
    """The supported path, so every refusal below is not vacuous."""
    with _stored(_transaction(provider_id="a", direction=TransactionDirection.INCOMING)) as repository:
        transaction_id = next(iter(repository.load().transactions))
        result = resolve_m210_income_classification(
            bucket_id=_BUCKET,
            transaction_id=transaction_id,
            transaction_repository=repository,
            **_complete(),
        )

    assert result is not None
    assert result.official_tipo_renta_code == _CODE
    assert result.gross_income_amount == Decimal("1000.00")
    assert result.payer_mode is M210PayerMode.SINGLE_PAYER


@pytest.mark.parametrize("omitted", ["tipo_renta_code", "gross_income_amount", "applicable_rate", "payer_mode"])
def test_omitting_any_single_answer_refuses(omitted: str) -> None:
    """Each of the four is load-bearing, so each is checked separately.

    A single case would pass while three of the four were silently optional.
    """
    # Overridden through the builder rather than subscripted afterwards: a
    # TypedDict cannot be indexed with a runtime key, and the builder already
    # takes overrides, so this states the same case without reaching past the
    # declared shape.
    answers = _complete(**{omitted: None})
    with _stored(_transaction(provider_id="a", direction=TransactionDirection.INCOMING)) as repository:
        transaction_id = next(iter(repository.load().transactions))
        with pytest.raises(TransactionValidationError) as excinfo:
            resolve_m210_income_classification(
                bucket_id=_BUCKET,
                transaction_id=transaction_id,
                transaction_repository=repository,
                **answers,
            )

    assert omitted in str(getattr(excinfo.value, "context", {}).get("missing", ""))


def test_an_outgoing_row_cannot_carry_the_declaration() -> None:
    """Modelo 210 declares income; a payment out is not income.

    Refused even though every answer is present, because completeness is not
    what makes a row eligible.
    """
    with _stored(_transaction(provider_id="a", direction=TransactionDirection.OUTGOING)) as repository:
        transaction_id = next(iter(repository.load().transactions))
        with pytest.raises(TransactionValidationError) as excinfo:
            resolve_m210_income_classification(
                bucket_id=_BUCKET,
                transaction_id=transaction_id,
                transaction_repository=repository,
                **_complete(),
            )

    context = getattr(excinfo.value, "context", {})
    assert context.get("required_direction") == TransactionDirection.INCOMING.value
    assert context.get("actual_direction") == TransactionDirection.OUTGOING.value


def test_an_absent_transaction_is_refused_and_named_as_absent() -> None:
    """A missing row is distinguishable from a wrongly-directed one."""
    with (
        _stored(_transaction(provider_id="a", direction=TransactionDirection.INCOMING)) as repository,
        pytest.raises(TransactionValidationError) as excinfo,
    ):
        resolve_m210_income_classification(
            bucket_id=_BUCKET,
            transaction_id="f" * 64,
            transaction_repository=repository,
            **_complete(),
        )

    assert getattr(excinfo.value, "context", {}).get("actual_direction") == "absent"


def test_the_direction_rule_is_checked_only_after_completeness() -> None:
    """An operator gets the answerable problem first.

    Told 'wrong direction' while three answers are also missing, they fix the
    row and meet a second refusal; the ordering means the message names what
    they can act on now.
    """
    answers = _complete()
    answers["applicable_rate"] = None
    with _stored(_transaction(provider_id="a", direction=TransactionDirection.OUTGOING)) as repository:
        transaction_id = next(iter(repository.load().transactions))
        with pytest.raises(TransactionValidationError) as excinfo:
            resolve_m210_income_classification(
                bucket_id=_BUCKET,
                transaction_id=transaction_id,
                transaction_repository=repository,
                **answers,
            )

    assert "missing" in getattr(excinfo.value, "context", {})

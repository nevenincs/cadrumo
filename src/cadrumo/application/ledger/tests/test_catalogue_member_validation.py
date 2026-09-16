"""Replacing a catalogue member proves the newcomer, not the whole ledger."""

from __future__ import annotations

from collections.abc import Iterator
from datetime import UTC, date, datetime
from decimal import Decimal
from pathlib import Path
from types import MappingProxyType
from typing import Any

import pytest
from pydantic import ValidationError

from ....domain.calculations.registry.authority import bundled_indexed_authority
from ....domain.iva.schema import IvaCashAccountingTreatment
from ....domain.transactions import models as transaction_models
from ....domain.transactions.enums import BusinessClassification, TransactionDirection
from ....domain.transactions.errors import TransactionValidationError
from ....domain.transactions.models import Transaction, TransactionCatalogue
from ....domain.transactions.raw_transaction import RawProvenance, RawTransaction, SourceFormat
from ..actions_common import remove_transaction, replace_transaction, upsert_transaction

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]


@pytest.fixture(autouse=True)
def _authority_operation() -> Iterator[None]:
    """Transactions resolve their IVA vocabulary inside a caller-held operation."""
    with bundled_indexed_authority().operation():
        yield


def _transaction(provider_id: str) -> Transaction:
    booked = date(2025, 3, 4)
    return Transaction.model_validate(
        {
            "raw": RawTransaction(
                provider_transaction_id=provider_id,
                booked_date=booked,
                value_date=booked,
                amount=Decimal("18.50"),
                currency="EUR",
                counterparty="Member Check SL",
                description=f"member check {provider_id}",
                provenance=RawProvenance(
                    source_path=Path(__file__),
                    source_sha256="c" * 64,
                    source_row_index=1,
                    source_format=SourceFormat.CSV,
                    ingested_at=datetime(2025, 3, 5, 9, 0, tzinfo=UTC),
                    provider_name="member check provider",
                ),
                raw_fields={"Concepto": provider_id},
            ),
            "direction": TransactionDirection.OUTGOING,
            "business_classification": BusinessClassification.BUSINESS,
            "source_jurisdiction": "ES",
            "group_label": None,
        },
    )


def _ledger(size: int) -> TransactionCatalogue:
    return TransactionCatalogue.from_transactions([_transaction(f"row-{index}") for index in range(size)])


def _relabelled(transaction: Transaction, label: str) -> Transaction:
    return Transaction.model_validate({**transaction.model_dump(), "group_label": label})


def test_each_replacement_proves_one_transaction(monkeypatch: pytest.MonkeyPatch) -> None:
    ledger = _ledger(40)
    replacements = [_relabelled(transaction, "Cierre 2025") for transaction in ledger.values()]
    derivations: list[str] = []
    derive = transaction_models.derive_transaction_id

    def counting(*args: Any, **kwargs: Any) -> str:
        derivations.append("derived")
        return derive(*args, **kwargs)

    monkeypatch.setattr(transaction_models, "derive_transaction_id", counting)
    for replacement in replacements:
        ledger = replace_transaction(ledger, old_transaction_id=replacement.transaction_id, replacement=replacement)

    assert len(derivations) == len(replacements)
    assert {transaction.group_label for transaction in ledger.values()} == {"Cierre 2025"}


def test_an_assembled_catalogue_equals_a_validated_one() -> None:
    ledger = _ledger(3)
    first = next(iter(ledger.values()))
    replaced = replace_transaction(
        ledger,
        old_transaction_id=first.transaction_id,
        replacement=_relabelled(first, "Q1"),
    )
    added = upsert_transaction(replaced, _transaction("row-new"))
    removed = remove_transaction(added, transaction_id=first.transaction_id)

    for assembled in (replaced, added, removed):
        assert isinstance(assembled.transactions, MappingProxyType)
        assert assembled == TransactionCatalogue.model_validate({"transactions": dict(assembled.transactions)})
    assert first.transaction_id not in removed


def test_a_replacement_with_a_forged_id_is_refused() -> None:
    """TEETH: a copy that skipped validation cannot enter the ledger under a false id."""
    ledger = _ledger(3)
    first = next(iter(ledger.values()))
    forged = first.model_copy(update={"transaction_id": "f" * 64})

    with pytest.raises((TransactionValidationError, ValidationError)):
        replace_transaction(ledger, old_transaction_id=first.transaction_id, replacement=forged)
    with pytest.raises((TransactionValidationError, ValidationError)):
        upsert_transaction(ledger, forged)


def test_a_replacement_breaking_the_cash_accounting_axis_is_refused() -> None:
    """TEETH: cross-field invariants are re-checked on the newcomer, not assumed."""
    ledger = _ledger(3)
    first = next(iter(ledger.values()))
    forged = first.model_copy(
        update={"cash_accounting_treatment": IvaCashAccountingTreatment("supplier_regime"), "operation_date": None},
    )

    with pytest.raises((TransactionValidationError, ValidationError), match="operation_date"):
        replace_transaction(ledger, old_transaction_id=first.transaction_id, replacement=forged)

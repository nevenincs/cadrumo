"""A split of a converted foreign row refuses a residual the rate cannot support.

Expected figures are worked by hand, half-up to the cent.

- 0.04 USD at 0.5 is 0.02 EUR. Each 0.01 USD child rounds 0.005 up to 0.01, so
  three children take 0.03 and the last child's residual would be 0.02 - 0.03 = -0.01.
- 20.20 USD at 0.925 is 18.685, which rounds to 18.69 EUR. Each 1.01 USD child is
  0.93425, so 0.93; nineteen children take 17.67 and the last child's residual
  would be 18.69 - 17.67 = 1.02, nine cents from its own 0.93.
- 100.00 USD at 0.9 is 90.00 EUR; children of 33.33, 33.33 and 33.34 convert to 29.997
  (30.00), 29.997 (30.00) and 30.006 (30.01). The first two take 60.00 and the last child
  absorbs the residual 30.00, one cent from its own 30.01, so that split is admitted.
"""

from __future__ import annotations

from datetime import UTC, date, datetime
from decimal import Decimal

import pytest

from cadrumo.adapters.persistence.profile.tests.ledger_action_create_support import ledger_ports_for_test
from cadrumo.adapters.persistence.storage.sql.secure_objects import SecureObjectRepository
from cadrumo.application.ledger.actions_split_merge import split_transaction
from cadrumo.application.ledger.models import ManualLedgerTransactionCommand, SplitChildCommand
from cadrumo.domain.currency.models import EurRateLookup, EurRateLookupStatus
from cadrumo.domain.currency.service import CurrencyNormalizationService
from cadrumo.domain.transactions.enums import TransactionDirection
from cadrumo.domain.transactions.errors import TransactionValidationError
from cadrumo.domain.transactions.models import Transaction

from .....application.ledger.tests.manual_transaction_support import create_manual_transaction
from .....application.ledger.tests.transaction_row_support import outgoing_manual_row
from .split_test_support import BUCKET_ID, repositories

pytestmark = [pytest.mark.unit, pytest.mark.hex_persistence_adapter]


class _Rate:
    rate_source_id = "synthetic-reference"

    def __init__(self, rate: str) -> None:
        self._rate = Decimal(rate)

    def lookup_eur_rate(self, currency: str, rate_date: date) -> EurRateLookup:
        return EurRateLookup(
            status=EurRateLookupStatus.FOUND,
            rate_date=rate_date,
            source=self.rate_source_id,
            rate=self._rate,
            observation_date=date(2026, 5, 1),
        )


def _split_usd_parent(
    secure_objects: SecureObjectRepository,
    *,
    parent_amount: str,
    rate: str,
    child_amounts: tuple[str, ...],
):
    transaction_repository, event_repository = repositories(secure_objects)
    command = ManualLedgerTransactionCommand(
        bucket_id=BUCKET_ID,
        booked_date=date(2026, 5, 2),
        amount=Decimal(parent_amount),
        currency="USD",
        direction=TransactionDirection.OUTGOING,
        counterparty="Vendor Inc",
        description="software",
        actor="operator-A",
    )
    with ledger_ports_for_test(
        bucket_id=BUCKET_ID,
        objects=secure_objects,
        transaction_repository=transaction_repository,
        bucket_event_repository=event_repository,
    ) as ports:
        parent = create_manual_transaction(
            command,
            ports=ports,
            occurred_at=datetime(2026, 5, 4, 9, 30, tzinfo=UTC),
            currency_normalizer=CurrencyNormalizationService(rate_provider=_Rate(rate)),
        )
        return (
            transaction_repository,
            split_transaction(
                bucket_id=BUCKET_ID,
                transaction_id=parent.ref.transaction_id,
                children=tuple(
                    SplitChildCommand(amount=Decimal(a), description=f"part {i}") for i, a in enumerate(child_amounts)
                ),
                actor="operator-A",
                ports=ports,
                occurred_at=datetime(2026, 5, 4, 10, 0, tzinfo=UTC),
            ),
            parent,
        )


def test_a_split_leaving_a_negative_last_child_is_refused_and_persists_nothing(
    secure_objects: SecureObjectRepository,
) -> None:
    with pytest.raises(TransactionValidationError, match="negative EUR value"):
        _split_usd_parent(secure_objects, parent_amount="0.04", rate="0.5", child_amounts=("0.01",) * 4)

    transaction_repository, _ = repositories(secure_objects)
    states = {t.lifecycle_state.name for t in transaction_repository.load().transactions.values()}
    assert states == {"ACTIVE"}, "the parent must stay ACTIVE and no child may be stored"
    assert len(transaction_repository.load().transactions) == 1


def test_a_split_whose_last_child_is_far_from_its_own_conversion_is_refused(
    secure_objects: SecureObjectRepository,
) -> None:
    with pytest.raises(TransactionValidationError, match="value_in_eur must equal amount"):
        _split_usd_parent(secure_objects, parent_amount="20.20", rate="0.925", child_amounts=("1.01",) * 20)


def test_a_valid_split_keeps_its_rounding_and_its_total(secure_objects: SecureObjectRepository) -> None:
    _, result, parent = _split_usd_parent(
        secure_objects, parent_amount="100.00", rate="0.9", child_amounts=("33.33", "33.33", "33.34")
    )

    assert parent.transaction.value_in_eur == Decimal("90.00")
    assert [child.value_in_eur for child in result.child_transactions] == [
        Decimal("30.00"),
        Decimal("30.00"),
        Decimal("30.00"),
    ]


def test_a_stored_split_child_with_an_off_residual_still_reads() -> None:
    row = outgoing_manual_row("c", amount=Decimal("1.01"), currency="USD", counterparty="V", description="d")
    stored = row.model_copy(update={"fx_rate": Decimal("0.925"), "value_in_eur": Decimal("1.02")})

    assert Transaction.model_validate_json(stored.model_dump_json()).value_in_eur == Decimal("1.02")

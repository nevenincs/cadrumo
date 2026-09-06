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

from collections.abc import Iterator
from contextlib import contextmanager
from datetime import UTC, date, datetime
from decimal import Decimal
from pathlib import Path
from tempfile import TemporaryDirectory

import pytest

from ....adapters.persistence.profile.transactions import TransactionCatalogueRepository
from ....core.irnr import M210PayerMode
from ....domain.transactions.enums import BusinessClassification, TransactionDirection
from ....domain.transactions.errors import TransactionValidationError
from ....domain.transactions.models import Transaction, TransactionCatalogue
from ....domain.transactions.raw_transaction import RawProvenance, RawTransaction, SourceFormat
from ....tests.secure_sql import isolated_runtime_profile
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
def _stored(*transactions: Transaction) -> Iterator[TransactionCatalogueRepository]:
    """The real catalogue: the direction rule reads a persisted row."""
    with TemporaryDirectory() as tmp, isolated_runtime_profile(tmp_path=Path(tmp), bucket_id=_BUCKET) as profile:
        repository = TransactionCatalogueRepository(bucket_id=profile.bucket_id)
        repository.save(TransactionCatalogue.from_transactions(transactions))
        yield TransactionCatalogueRepository(bucket_id=profile.bucket_id)


def _complete(**overrides: object) -> dict[str, object]:
    payload: dict[str, object] = {
        "tipo_renta_code": _CODE,
        "gross_income_amount": Decimal("1000.00"),
        "applicable_rate": Decimal("0.19"),
        "payer_mode": M210PayerMode.SINGLE_PAYER,
        # Required by the domain model: a non-35 income code declared under a
        # single payer must name that payer. Omitting it makes the "complete"
        # fixture incomplete and every refusal below untestable.
        "payer_id": "B12345674",
    }
    payload.update(overrides)
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
            **_complete(),  # type: ignore[arg-type]
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
    answers = _complete()
    answers[omitted] = None
    with _stored(_transaction(provider_id="a", direction=TransactionDirection.INCOMING)) as repository:
        transaction_id = next(iter(repository.load().transactions))
        with pytest.raises(TransactionValidationError) as excinfo:
            resolve_m210_income_classification(
                bucket_id=_BUCKET,
                transaction_id=transaction_id,
                transaction_repository=repository,
                **answers,  # type: ignore[arg-type]
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
                **_complete(),  # type: ignore[arg-type]
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
            **_complete(),  # type: ignore[arg-type]
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
                **answers,  # type: ignore[arg-type]
            )

    assert "missing" in getattr(excinfo.value, "context", {})

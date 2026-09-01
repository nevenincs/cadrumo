"""A cuota-less row with no base is refused at verify, and nothing else is.

A category in ``CUOTA_LESS_M303_IVA_CATEGORIES`` carries no cuota by law, so the
taxable base is the row's ONLY possible contribution to the return. A row
declaring such a category with no base contributes nothing while representing a
declared operation, and the base casilla is understated by exactly that amount.

That certainty is what earns the escalation from advisory to BLOCKING, and it is
also what bounds it: every neighbouring shape has a second measure or an
offsetting effect, so each is asserted to stay silent here. An escalation
without those controls is how a gate starts refusing lawful filings.
"""

from __future__ import annotations

from datetime import UTC, date, datetime
from decimal import Decimal
from pathlib import Path

import pytest

from ....domain.iva.schema import CUOTA_LESS_M303_IVA_CATEGORIES, IvaCategory
from ....domain.modelos.verification_report import ModeloVerificationFindingSeverity
from ....domain.transactions.enums import BusinessClassification, TransactionDirection
from ....domain.transactions.models import Transaction
from ....domain.transactions.raw_transaction import RawProvenance, RawTransaction, SourceFormat
from ..verification_actions import _cuota_less_without_base_findings

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_T0 = datetime(2026, 3, 1, tzinfo=UTC)
_AMOUNT = Decimal("1000.00")


def _transaction(
    provider_id: str,
    *,
    iva_category: IvaCategory | None,
    taxable_base: Decimal | None,
    iva_amount: Decimal | None = None,
) -> Transaction:
    payload: dict[str, object] = {
        "raw": RawTransaction(
            provider_transaction_id=provider_id,
            booked_date=date(2026, 2, 15),
            value_date=date(2026, 2, 15),
            amount=_AMOUNT,
            currency="EUR",
            counterparty="Cliente",
            description=f"operación declarada {provider_id}",
            provenance=RawProvenance(
                source_path=Path(__file__),
                source_sha256="e" * 64,
                source_row_index=1,
                source_format=SourceFormat.MANUAL,
                ingested_at=_T0,
                provider_name="manual-ledger",
            ),
            raw_fields={"source_kind": "ledger_transaction"},
        ),
        "direction": TransactionDirection.INCOMING,
        "group_label": None,
        "source_jurisdiction": "ES",
        "business_classification": BusinessClassification.BUSINESS,
        "category_id": "test_operation",
        "taxable_base": taxable_base,
        "iva_amount": iva_amount,
        "classified_at": _T0,
        "classified_by": "manual",
    }
    if iva_category is not None:
        payload["iva_category"] = iva_category
    return Transaction.model_validate(payload)


class _InMemoryCatalogue:
    def __init__(self, transactions: dict[str, Transaction]) -> None:
        self._transactions = transactions

    def get(self, transaction_id: str) -> Transaction | None:
        return self._transactions.get(transaction_id)


class _InMemoryRepository:
    """Minimal stand-in for the catalogue repository the gate loads from."""

    def __init__(self, transactions: dict[str, Transaction]) -> None:
        self._catalogue = _InMemoryCatalogue(transactions)

    def load(self) -> _InMemoryCatalogue:
        return self._catalogue


class _TargetRevision:
    def __init__(self, source_transaction_ids: tuple[str, ...]) -> None:
        self.source_transaction_ids = source_transaction_ids
        self.observations = ()


class _TargetWorkUnit:
    bucket_id = "bucket-under-test"


def _findings(transactions: dict[str, Transaction], *, consumed: tuple[str, ...] | None = None):
    ids = tuple(transactions) if consumed is None else consumed
    return _cuota_less_without_base_findings(
        target=_TargetRevision(ids),  # ty: ignore[invalid-argument-type]  # reason: the gate reads two fields
        work_unit=_TargetWorkUnit(),  # ty: ignore[invalid-argument-type]  # reason: the gate reads bucket_id
        transaction_repository=_InMemoryRepository(transactions),  # ty: ignore[invalid-argument-type]  # reason: load() only
    )


def test_a_cuota_less_row_with_no_base_blocks() -> None:
    """The subject: nothing to contribute, and no second measure to fall back on."""
    findings = _findings({"tx-1": _transaction("tx-1", iva_category=IvaCategory.DOMESTIC_EXEMPT, taxable_base=None)})

    assert len(findings) == 1
    finding = findings[0]
    assert finding.severity is ModeloVerificationFindingSeverity.BLOCKING
    assert finding.message_locale_key == "application.modelo.findings.cuota_less_ledger_row_base_missing"
    assert finding.message_facts["transaction_id"] == "tx-1"
    # The refusal must name the fix, not merely the fault.
    assert "next_action" not in finding.model_dump(mode="json")
    # Grounded in the duty to declare the operation, not in the deduction-evidence
    # statute the neighbouring gate cites -- different requirement, different refs.
    assert "ley-37-1992:art-164" in finding.legal_refs


def test_the_same_row_carrying_a_base_is_accepted() -> None:
    """The control that keeps this from refusing every exempt operation."""
    assert (
        _findings({"tx-1": _transaction("tx-1", iva_category=IvaCategory.DOMESTIC_EXEMPT, taxable_base=_AMOUNT)}) == []
    )


def test_a_cuota_bearing_row_with_no_base_is_not_this_gate_s_business() -> None:
    """Ambiguous direction: the quota still contributes, so refusing would over-block.

    This is the boundary the escalation was scoped to. A general-rate row missing
    its base is imprecise, not certainly understated -- the cuota reaches the
    return either way -- so it stays with the advisory rather than blocking here.
    """
    row = _transaction("tx-1", iva_category=IvaCategory.DOMESTIC_GENERAL, taxable_base=None, iva_amount=Decimal("210"))

    assert _findings({"tx-1": row}) == []


def test_a_row_with_no_declared_category_is_not_refused() -> None:
    """An undeclared category is not a declared cuota-less one.

    The IVA layer derives a domestic category for such a row from its stored
    rate and direction. Treating the absence as a cuota-less declaration would
    refuse rows the operator never claimed were exempt.
    """
    assert _findings({"tx-1": _transaction("tx-1", iva_category=None, taxable_base=None)}) == []


def test_a_row_the_revision_never_consumed_is_out_of_scope() -> None:
    """The gate judges what reached a casilla, not the whole ledger.

    A cuota-less row outside ``source_transaction_ids`` contributed to no casilla
    on this revision, so it understates nothing here.
    """
    transactions = {
        "consumed": _transaction("consumed", iva_category=IvaCategory.DOMESTIC_EXEMPT, taxable_base=_AMOUNT),
        "ignored": _transaction("ignored", iva_category=IvaCategory.DOMESTIC_EXEMPT, taxable_base=None),
    }

    assert _findings(transactions, consumed=("consumed",)) == []


def test_every_cuota_less_category_is_covered_rather_than_a_sampled_few() -> None:
    """Drive the whole declared set, so a new member cannot silently escape.

    Enumerating the canonical frozenset rather than listing categories here means
    an addition to it is covered the day it lands. Sampling would leave the new
    member unrefused and this test still green.
    """
    unrefused = [
        category.value
        for category in sorted(CUOTA_LESS_M303_IVA_CATEGORIES, key=lambda member: member.value)
        if not _findings({"tx-1": _transaction("tx-1", iva_category=category, taxable_base=None)})
    ]

    assert unrefused == [], f"cuota-less categories that escaped the gate: {unrefused}"

"""Real ledger source helpers for Modelo 130 CLI tests.

The seeded rows are bank movements linking no invoice, which only the cobros y
pagos criterion can place in a quarter (RIRPF art. 7.2): under devengo their
accrual is unknown, and with no criterion the box stays unresolved. Each seed
therefore declares that election for its year unless told not to.
"""

from __future__ import annotations

from datetime import UTC, date, datetime
from decimal import Decimal
from pathlib import Path
from uuid import UUID

from cadrumo.adapters.persistence.profile.transactions import TransactionCatalogueRepository
from cadrumo.adapters.persistence.storage.tests.profile_capsule_runtime import (
    bound_test_profile_record,
    open_test_profile_session,
    upsert_test_profile_facts,
)
from cadrumo.core.bucket_pointer import resolve_active_bucket_id
from cadrumo.domain.calculations.registry.authority import bundled_indexed_authority
from cadrumo.domain.transactions.enums import BusinessClassification, TransactionDirection
from cadrumo.domain.transactions.models import Transaction, TransactionCatalogue
from cadrumo.domain.transactions.raw_transaction import RawProvenance, RawTransaction, SourceFormat
from cadrumo.domain.user_profile.tests.imputation_criterion_facts import cash_criterion_facts
from cadrumo.domain.user_profile.values import UserProfileFact

_CRITERION_PATH = "irpf.activity_income_imputation_criterion"
_REGIME_PATH = "irpf.estimation_regime"


def _declare_cash_criterion(bucket_id: str, filing_year: int) -> None:
    """Extend the profile's cobros y pagos declaration over ``filing_year``, keeping a regime already in force."""
    with bound_test_profile_record(UUID(bucket_id)) as repository:
        existing = repository.load(UUID(bucket_id)).facts
    declared = next((fact for fact in existing if fact.path == _CRITERION_PATH), None)
    first = (
        filing_year if declared is None or declared.valid_from is None else min(declared.valid_from.year, filing_year)
    )
    last = filing_year if declared is None or declared.valid_to is None else max(declared.valid_to.year, filing_year)
    regime_in_force = any(fact.path == _REGIME_PATH and fact.valid_from is None for fact in existing)
    upsert_test_profile_facts(
        bucket_id,
        tuple(
            UserProfileFact.model_validate(
                {
                    "path": fact.path,
                    "value": fact.value,
                    "valid_from": date(first, 1, 1),
                    "valid_to": date(last, 12, 31),
                }
            )
            for fact in cash_criterion_facts(filing_year)
            if not (regime_in_force and fact.path == _REGIME_PATH)
        ),
    )


def seed_m130_income_transaction(
    *,
    amount: Decimal,
    filing_year: int,
    source_key: str,
    value_date: date | None = None,
    bucket_id: str | None = None,
    criterion_declared: bool = True,
) -> None:
    """Seed one real actividad-economica income row for source-bound M130 casilla 01.

    ``value_date`` defaults to 15 February of ``filing_year`` (a Q1 row). Pass an
    explicit date to place the income in a later quarter — useful for exercising
    the cumulative (year-to-date) M130 source window across quarters.
    ``bucket_id`` names the bucket to write; it defaults to the active one.
    """

    # Transactions validate against registry facts, as they do under a CLI invocation's lease.
    with bundled_indexed_authority().operation():
        bucket_id = bucket_id if bucket_id is not None else resolve_active_bucket_id()
        assert bucket_id is not None, "test profile must install an active bucket pointer"
        if criterion_declared:
            _declare_cash_criterion(bucket_id, filing_year)
        if value_date is None:
            value_date = date(filing_year, 2, 15)
        income = Transaction.model_validate(
            {
                "raw": RawTransaction(
                    provider_transaction_id=f"m130-income-{source_key}-{filing_year}",
                    booked_date=value_date,
                    value_date=value_date,
                    amount=amount,
                    currency="EUR",
                    counterparty="Cliente SA",
                    description=f"M130 oracle income {source_key}",
                    provenance=RawProvenance(
                        source_path=Path(__file__),
                        source_sha256="b" * 64,
                        source_row_index=1,
                        source_format=SourceFormat.MANUAL,
                        ingested_at=datetime(filing_year, 2, 16, 12, 0, tzinfo=UTC),
                        provider_name="manual-ledger",
                    ),
                    raw_fields={"source_kind": "m130_oracle_income", "source_key": source_key},
                ),
                "direction": TransactionDirection.INCOMING,
                "group_label": None,
                "business_classification": BusinessClassification.BUSINESS,
                "source_jurisdiction": "ES",
                "business_pct": None,
                "category_id": None,
                "taxable_base": amount,
                # A stated nil cuota is what lets cash equal base + cuota prove nothing was withheld.
                "iva_rate": Decimal("0"),
                "iva_amount": Decimal("0.00"),
                "irpf_category": "actividad_economica",
                "purchase_invoice_evidence_id": None,
                "classified_at": datetime(filing_year, 2, 16, 13, 0, tzinfo=UTC),
                "classified_by": "manual",
            },
        )
        with open_test_profile_session(bucket_id):
            existing = TransactionCatalogueRepository(bucket_id=bucket_id).load()
            transactions = (*tuple(existing.transactions.values()), income)
            TransactionCatalogueRepository(bucket_id=bucket_id).save(
                TransactionCatalogue.from_transactions(transactions),
            )


def seed_m130_expense_transaction(
    *,
    amount: Decimal,
    filing_year: int,
    source_key: str,
    value_date: date | None = None,
    bucket_id: str | None = None,
    criterion_declared: bool = True,
) -> None:
    """Seed one real deductible actividad-economica expense (gasto) row for casilla 02.

    The OUTGOING sibling of :func:`seed_m130_income_transaction`. Casilla 02 is a
    source-bound casilla aggregated from the ledger via
    ``ledger_renta_gastos_pago_fraccionado_aggregation``; a deductible gasto is an ACTIVE, EUR,
    OUTGOING, BUSINESS-classified row carrying an IVA-exclusive ``taxable_base``.
    ``amount`` is the (non-negative) magnitude; flow is carried by the direction.
    """

    # Transactions validate against registry facts, as they do under a CLI invocation's lease.
    with bundled_indexed_authority().operation():
        bucket_id = bucket_id if bucket_id is not None else resolve_active_bucket_id()
        assert bucket_id is not None, "test profile must install an active bucket pointer"
        if criterion_declared:
            _declare_cash_criterion(bucket_id, filing_year)
        if value_date is None:
            value_date = date(filing_year, 2, 15)
        expense = Transaction.model_validate(
            {
                "raw": RawTransaction(
                    provider_transaction_id=f"m130-expense-{source_key}-{filing_year}",
                    booked_date=value_date,
                    value_date=value_date,
                    amount=amount,
                    currency="EUR",
                    counterparty="Proveedor SA",
                    description=f"M130 oracle expense {source_key}",
                    provenance=RawProvenance(
                        source_path=Path(__file__),
                        source_sha256="c" * 64,
                        source_row_index=1,
                        source_format=SourceFormat.MANUAL,
                        ingested_at=datetime(filing_year, 2, 16, 12, 0, tzinfo=UTC),
                        provider_name="manual-ledger",
                    ),
                    raw_fields={"source_kind": "m130_oracle_expense", "source_key": source_key},
                ),
                "direction": TransactionDirection.OUTGOING,
                "group_label": None,
                "business_classification": BusinessClassification.BUSINESS,
                "source_jurisdiction": "ES",
                "business_pct": None,
                "category_id": "material_oficina",
                "taxable_base": amount,
                "iva_rate": None,
                "iva_amount": None,
                "irpf_category": "actividad_economica",
                "purchase_invoice_evidence_id": None,
                "classified_at": datetime(filing_year, 2, 16, 13, 0, tzinfo=UTC),
                "classified_by": "manual",
            },
        )
        with open_test_profile_session(bucket_id):
            existing = TransactionCatalogueRepository(bucket_id=bucket_id).load()
            transactions = (*tuple(existing.transactions.values()), expense)
            TransactionCatalogueRepository(bucket_id=bucket_id).save(
                TransactionCatalogue.from_transactions(transactions),
            )


__all__ = ["seed_m130_expense_transaction", "seed_m130_income_transaction"]

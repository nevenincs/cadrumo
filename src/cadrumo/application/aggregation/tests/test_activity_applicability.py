"""A filer the profile states has no economic activity reads the activity ledgers as not-applicable, not missing.

Both Modelo 100 activity-ledger resolvers run over the same real ledger rows: a
personal incoming movement, which is neither activity income nor an activity
expense. When the profile declares its income categories without actividad
economica, the rows' classification rejections are no finding and the
resolver's bindings are inapplicable; when it declares none, the rejections are
reported exactly as before. The binding values are the same either way.
"""

from __future__ import annotations

from datetime import UTC, date, datetime
from decimal import Decimal
from pathlib import Path

import pytest

from cadrumo.domain.calculations.registry.tests.authored_editions import newest_authored_edition
from cadrumo.domain.calculations.registry.tests.published_authority import published_snapshot

from ....domain.invoices.catalogue import InvoiceCatalogue
from ....domain.transactions.enums import BusinessClassification, TransactionDirection, TransactionLifecycleState
from ....domain.transactions.models import Transaction, TransactionCatalogue
from ....domain.transactions.raw_transaction import RawProvenance, RawTransaction, SourceFormat
from ....domain.user_profile.values import UserProfileFact
from ...actividad_asset.history import ActivityAssetHistory
from ...actividad_asset.tests.register_support import MemoryRepository
from ..modelo_bindings import LedgerRentaIncomeAggregationSourceResolver
from ..retencion_soportada_source import IRPF_INCOME_CATEGORIES_PROFILE_PATH
from ..source_mesh import CalculationSourceContext, CalculationSourceResolution
from .ledger_source_mesh_support import (
    BUCKET_ID,
    InMemoryTransactionCatalogueRepository,
    cash_criterion_profile,
    resolve_m100,
)
from .renta_income_aggregation_support import catalogue_read_ports, renta_income_aggregation_period

pytestmark = [pytest.mark.unit, pytest.mark.hex_application, pytest.mark.usefixtures("operation")]

_YEAR = newest_authored_edition("100")
#: Rental and pension income, which are not rendimientos de actividades economicas.
_NO_ACTIVITY = "capital_inmobiliario,pension"
_INCOME_REJECTION = "cannot feed Renta income"
_EXPENSE_REJECTION = "is not a Renta expense flow"


def _personal_receipt(provider_id: str) -> Transaction:
    booked = date(_YEAR, 6, 15)
    raw = RawTransaction(
        provider_transaction_id=provider_id,
        booked_date=booked,
        value_date=booked,
        amount=Decimal("850.00"),
        currency="EUR",
        counterparty="Inquilino",
        description="transferencia recibida",
        provenance=RawProvenance(
            source_path=Path(__file__),
            source_sha256="b" * 64,
            source_row_index=1,
            source_format=SourceFormat.CSV,
            ingested_at=datetime(_YEAR, 7, 1, 12, 0, tzinfo=UTC),
            provider_name="CSV provider",
        ),
        raw_fields={},
    )
    return Transaction.model_validate(
        {
            "raw": raw,
            "direction": TransactionDirection.INCOMING,
            "group_label": None,
            "source_jurisdiction": "ES",
            "business_classification": BusinessClassification.PERSONAL,
            "irpf_category": None,
            "lifecycle_state": TransactionLifecycleState.ACTIVE,
            "classified_at": datetime(_YEAR, 7, 1, 13, 0, tzinfo=UTC),
            "classified_by": "manual",
        },
    )


_ROW_COUNT = 2


def _rows() -> tuple[Transaction, ...]:
    return tuple(_personal_receipt(f"receipt-{index}") for index in range(_ROW_COUNT))


def _declared(categories: str | None) -> tuple[UserProfileFact, ...]:
    return () if categories is None else (UserProfileFact(path=IRPF_INCOME_CATEGORIES_PROFILE_PATH, value=categories),)


def _income(categories: str | None) -> CalculationSourceResolution:
    transactions = TransactionCatalogue.from_transactions(_rows())
    repository = InMemoryTransactionCatalogueRepository(bucket_id=BUCKET_ID)
    repository.save(transactions)
    resolver = LedgerRentaIncomeAggregationSourceResolver(
        activity_asset_history_repository=MemoryRepository(),
        transaction_repository=repository,
        ports=catalogue_read_ports(invoices=InvoiceCatalogue(), transactions=transactions),
    )
    return resolver.resolve(
        CalculationSourceContext(
            bucket_id=BUCKET_ID,
            modelo="100",
            filing_year=_YEAR,
            period=renta_income_aggregation_period(_YEAR, "0A"),
            revision=published_snapshot("100", filing_year=_YEAR, period="0A").revision,
            profile=cash_criterion_profile(_YEAR, extra_facts=_declared(categories)),
        )
    )


def _expenses(categories: str | None) -> CalculationSourceResolution:
    return resolve_m100(
        ActivityAssetHistory(),
        rows=_rows(),
        profile=cash_criterion_profile(_YEAR, extra_facts=_declared(categories)),
        year=_YEAR,
    )


def _rejections(resolution: CalculationSourceResolution, words: str) -> list[str]:
    return [
        diagnostic.message
        for diagnostic in resolution.diagnostics
        if diagnostic.reason == "source_issue" and words in diagnostic.message
    ]


def test_a_filer_without_an_activity_has_no_missing_activity_income_rows() -> None:
    stated = _income(_NO_ACTIVITY)
    unknown = _income(None)

    assert _rejections(stated, _INCOME_REJECTION) == []
    assert len(_rejections(unknown, _INCOME_REJECTION)) == _ROW_COUNT
    assert stated.binding_values == unknown.binding_values
    assert stated.binding_values
    assert set(stated.binding_values) <= set(stated.inapplicable_binding_ids)
    assert unknown.inapplicable_binding_ids == ()


def test_a_filer_without_an_activity_has_no_missing_activity_expense_rows() -> None:
    stated = _expenses(_NO_ACTIVITY)
    unknown = _expenses(None)

    assert _rejections(stated, _EXPENSE_REJECTION) == []
    assert len(_rejections(unknown, _EXPENSE_REJECTION)) == _ROW_COUNT
    assert stated.binding_values == unknown.binding_values
    assert stated.binding_values
    assert set(stated.binding_values) <= set(stated.inapplicable_binding_ids)
    assert not set(stated.binding_values) & set(unknown.inapplicable_binding_ids)

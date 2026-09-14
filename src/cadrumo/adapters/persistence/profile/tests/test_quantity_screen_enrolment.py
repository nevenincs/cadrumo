"""Every declared quantity screen must run on a live calculate path.

A family adapter can supply an alternative-measure classification and per-fact
readers, pass every partition check, and never be called by its resolver. The
screen is then dead capacity: correct, tested in isolation, and switched off for
every taxpayer. That is the shape ``no-dormant-source-resolvers`` forbids one
level up, where a resolver merged without mesh enrolment silently blanks its
declared source kind.

The gate has two halves and needs both. The inventory below drives each family's
real resolver end to end and asserts the advisory arrives; the equality check
against ``screened_quantity_families`` — the registry each adapter writes to
at import — is what stops a THIRD family being added with readers and no wiring.
Without that half the inventory is a hand-maintained list, and a hand-maintained
list of things to check cannot report the thing nobody added to it.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, date, datetime
from decimal import Decimal
from functools import cache
from pathlib import Path

import pytest
from dev.registry.compiler.authority import compiled_bundled_authority

from cadrumo.adapters.persistence.profile.prorrata_register import ProrrataRegisterRepository
from cadrumo.adapters.persistence.profile.transactions import TransactionCatalogueRepository
from cadrumo.adapters.persistence.tests.runtime_profile_fixture import (
    bucket_scoped_transaction_catalogue_fixture,
)
from cadrumo.application.aggregation.modelo_bindings import (
    LedgerIvaAggregationSourceResolver,
    LedgerRentaIncomeAggregationSourceResolver,
)
from cadrumo.application.aggregation.source_mesh import CalculationSourceContext, CalculationSourceResolution
from cadrumo.application.invoices.catalogue_reads_ports import InvoiceCatalogueReadPorts
from cadrumo.core.period import Period
from cadrumo.domain.bienes_inversion.register import BienesInversionIvaRegister
from cadrumo.domain.calculations.registry.schema import ModeloRevision
from cadrumo.domain.invoices.models import InvoiceCatalogue
from cadrumo.domain.iva.schema import IvaCategory
from cadrumo.domain.transactions.dates import transaction_eligible_date_span, transaction_filing_date
from cadrumo.domain.transactions.enums import BusinessClassification, TransactionDirection, TransactionLifecycleState
from cadrumo.domain.transactions.models import (
    LedgerDatePartition,
    OutOfWindowTransactionIndexEntry,
    OutOfWindowTransactionSummary,
    Transaction,
    TransactionCatalogue,
)
from cadrumo.domain.transactions.raw_transaction import RawProvenance, RawTransaction, SourceFormat


class _InvoiceCatalogueReader:
    """In-memory invoice reader for the resolver's application-owned port."""

    def __init__(self, catalogue: InvoiceCatalogue) -> None:
        self._catalogue = catalogue

    def load(self) -> InvoiceCatalogue:
        return self._catalogue


class _TransactionCatalogueReader:
    """In-memory transaction reader for the resolver's application-owned port."""

    def __init__(self, catalogue: TransactionCatalogue) -> None:
        self._catalogue = catalogue

    def load(self) -> TransactionCatalogue:
        return self._catalogue

    def partition_by_date_range(self, start: date, end: date) -> LedgerDatePartition:
        in_window: list[Transaction] = []
        out_of_window: list[OutOfWindowTransactionIndexEntry] = []
        for transaction in self._catalogue.values():
            earliest, latest = transaction_eligible_date_span(transaction)
            if earliest <= end and latest >= start:
                in_window.append(transaction)
                continue
            out_of_window.append(
                OutOfWindowTransactionIndexEntry(
                    transaction_id=transaction.transaction_id,
                    filing_date=transaction_filing_date(transaction),
                ),
            )
        return LedgerDatePartition(
            in_window=TransactionCatalogue.from_transactions(in_window),
            out_of_window=tuple(out_of_window),
            out_of_window_summary=OutOfWindowTransactionSummary.from_index_entries(out_of_window),
            index_complete=False,
        )


def _catalogue_read_ports(
    *, invoices: InvoiceCatalogue, transactions: TransactionCatalogue
) -> InvoiceCatalogueReadPorts:
    return InvoiceCatalogueReadPorts(
        invoice_reader=_InvoiceCatalogueReader(invoices),
        transaction_reader=_TransactionCatalogueReader(transactions),
    )


def _actividad_transaction(
    provider_id: str,
    *,
    value_date: date,
    amount: Decimal = Decimal("1000.00"),
    taxable_base: Decimal | None = None,
    iva_rate: Decimal | None = None,
    iva_amount: Decimal | None = None,
    irpf_category: str | None = "actividad_economica",
    business_classification: BusinessClassification = BusinessClassification.NOT_YET_PROCESSED,
    business_pct: Decimal | None = None,
) -> Transaction:
    return Transaction.model_validate(
        {
            "raw": RawTransaction(
                provider_transaction_id=provider_id,
                booked_date=value_date,
                value_date=value_date,
                amount=amount,
                currency="EUR",
                counterparty="Cliente SA",
                description=f"income row {provider_id}",
                provenance=RawProvenance(
                    source_path=Path(__file__),
                    source_sha256="a" * 64,
                    source_row_index=1,
                    source_format=SourceFormat.CSV,
                    ingested_at=datetime(2024, 4, 6, 12, 0, tzinfo=UTC),
                    provider_name="CSV provider",
                ),
                raw_fields={"Concepto": provider_id},
            ),
            "direction": TransactionDirection.INCOMING,
            "group_label": None,
            "source_jurisdiction": "ES",
            "business_classification": business_classification,
            "business_pct": business_pct,
            "purchase_invoice_evidence_id": None,
            "category_id": None,
            "taxable_base": taxable_base,
            "iva_rate": iva_rate,
            "iva_amount": iva_amount,
            "irpf_category": irpf_category,
            "lifecycle_state": TransactionLifecycleState.ACTIVE,
            "classified_at": datetime(2024, 4, 6, 13, 0, tzinfo=UTC),
            "classified_by": "manual",
        },
    )


pytestmark = [pytest.mark.unit, pytest.mark.hex_persistence_adapter]

_NOW = datetime(2026, 2, 10, 12, 0, tzinfo=UTC)
_BUCKET_ID = "28282828-2828-4828-8828-282828282828"


@dataclass(frozen=True)
class _EnrolledFamily:
    """One family's end-to-end drive of its declared quantity screen.

    ``family`` must equal the name the adapter registers at import, so the
    inventory and the registry can be compared as sets rather than trusted to
    agree.
    """

    family: str
    reason: str
    dropped_fact: str
    resolve: Callable[[TransactionCatalogueRepository], CalculationSourceResolution]


def _provenance(provider_id: str) -> RawProvenance:
    return RawProvenance(
        source_path=Path(__file__),
        source_sha256="b" * 64,
        source_row_index=1,
        source_format=SourceFormat.MANUAL,
        ingested_at=_NOW,
        provider_name="manual",
    )


@cache
def _m303_revision() -> ModeloRevision:
    return compiled_bundled_authority().snapshot("303", filing_year=2025, period="1T").revision


@cache
def _m130_revision() -> ModeloRevision:
    return compiled_bundled_authority().modelo("130").revisions["2019-y-siguientes"]


def _without_fact(revision: ModeloRevision, source: str, fact: str) -> ModeloRevision:
    kept = [
        binding
        for binding in revision.bindings
        if not (binding.source.value == source and getattr(binding.provider, "fact", None) == fact)
    ]
    return revision.model_copy(update={"bindings": tuple(kept)})


def _iva_sale() -> Transaction:
    raw = RawTransaction(
        provider_transaction_id="enrol-iva",
        booked_date=date(2026, 2, 10),
        value_date=date(2026, 2, 10),
        amount=Decimal("1210.00"),
        currency="EUR",
        counterparty="Cliente SL",
        description="venta",
        provenance=_provenance("enrol-iva"),
        raw_fields={"row": "enrol-iva"},
    )
    return Transaction.model_validate(
        {
            "raw": raw,
            "direction": TransactionDirection.INCOMING,
            "group_label": None,
            "source_jurisdiction": "ES",
            "business_classification": BusinessClassification.BUSINESS,
            "taxable_base": Decimal("1000.00"),
            "iva_rate": Decimal("0.21"),
            "iva_amount": Decimal("210.00"),
            "iva_category": IvaCategory("domestic_general"),
            "lifecycle_state": TransactionLifecycleState.ACTIVE,
            "classified_at": _NOW,
            "classified_by": "manual",
        },
    )


def _resolve_iva(repository: TransactionCatalogueRepository) -> CalculationSourceResolution:
    repository.save(TransactionCatalogue.from_transactions((_iva_sale(),)))
    return LedgerIvaAggregationSourceResolver(
        transaction_repository=repository,
        invoice_catalogue_read_ports=_catalogue_read_ports(
            invoices=InvoiceCatalogue(),
            transactions=TransactionCatalogue(),
        ),
        prorrata_register_repository=ProrrataRegisterRepository(bucket_id=_BUCKET_ID),
        investment_asset_register=BienesInversionIvaRegister(),
        investment_asset_profile_id=_BUCKET_ID,
    ).resolve(
        CalculationSourceContext(
            bucket_id=_BUCKET_ID,
            modelo="303",
            filing_year=2026,
            period=Period.from_year_and_code(2026, "1T"),
            revision=_without_fact(_m303_revision(), "ledger_iva_aggregation", "base_amount_sum"),
        ),
    )


def _renta_net_paid_invoice() -> Transaction:
    """A professional invoice paid net of a 15 % retención.

    Built through the shared actividad helper the renta tests already use, so
    this gate exercises the same substrate the family's own suite does rather
    than a second hand-rolled shape that could drift from it. The retención is
    not a stored field: the projection derives 300,00 from the shortfall between
    the 2.420,00 invoiced gross and the 2.120,00 cash received, which is why the
    drive starts at a transaction and never at an observation.
    """
    return _actividad_transaction(
        "enrol-renta",
        value_date=date(2026, 2, 10),
        amount=Decimal("2120.00"),
        taxable_base=Decimal("2000.00"),
        iva_rate=Decimal("0.21"),
        iva_amount=Decimal("420.00"),
        business_classification=BusinessClassification.BUSINESS,
    )


def _resolve_renta(repository: TransactionCatalogueRepository) -> CalculationSourceResolution:
    repository.save(TransactionCatalogue.from_transactions((_renta_net_paid_invoice(),)))
    return LedgerRentaIncomeAggregationSourceResolver(
        ports=_catalogue_read_ports(
            invoices=InvoiceCatalogue(),
            transactions=repository.load(),
        ),
    ).resolve(
        CalculationSourceContext(
            bucket_id=_BUCKET_ID,
            modelo="130",
            filing_year=2026,
            period=Period.from_year_and_code(2026, "1T"),
            revision=_without_fact(
                _m130_revision(),
                "ledger_renta_income_aggregation",
                "withheld_amount_sum",
            ),
        ),
    )


#: Every family whose adapter declares a quantity screen, paired with a drive of
#: its real resolver. Adding a family here without wiring its resolver fails the
#: drive; adding an adapter without an entry here fails the equality check below.
_ENROLLED: tuple[_EnrolledFamily, ...] = (
    _EnrolledFamily(
        family="ledger-IVA",
        reason="unrouted_declarable_quantity",
        dropped_fact="base_amount_sum",
        resolve=_resolve_iva,
    ),
    _EnrolledFamily(
        family="renta-income",
        reason="unrouted_declarable_quantity",
        dropped_fact="withheld_amount_sum",
        resolve=_resolve_renta,
    ),
)


repository = bucket_scoped_transaction_catalogue_fixture(_BUCKET_ID, name="repository")


@pytest.mark.parametrize("enrolled", _ENROLLED, ids=lambda entry: entry.family)
def test_the_declared_screen_reaches_the_resolver_envelope(
    enrolled: _EnrolledFamily,
    repository: TransactionCatalogueRepository,
) -> None:
    """Each family's screen runs on its live calculate path, not just in isolation."""
    resolution = enrolled.resolve(repository)

    advisories = [diagnostic for diagnostic in resolution.diagnostics if diagnostic.reason == enrolled.reason]
    assert advisories, (
        f"{enrolled.family} declares a quantity screen but its resolver raised no {enrolled.reason!r} "
        f"advisory for a revision drawing no {enrolled.dropped_fact!r} -- the screen is dead capacity"
    )
    assert enrolled.dropped_fact in advisories[0].message

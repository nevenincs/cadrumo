"""Profile-persistence integration coverage for the IVA quantity screen."""

from __future__ import annotations

from datetime import UTC, date, datetime
from decimal import Decimal
from functools import cache
from pathlib import Path

import pytest

from .....application.aggregation.modelo_bindings_iva import LedgerIvaAggregationSourceResolver
from .....application.aggregation.source_mesh import CalculationSourceContext
from .....application.invoices.catalogue_reads_ports import InvoiceCatalogueReadPorts
from .....core.casilla_id import validated_casilla_id
from .....core.iva_deduction_fact import IvaDeductionEvidenceAuthority, IvaDeductionFactKind
from .....core.period import Period
from .....domain.bienes_inversion.register import BienesInversionIvaRegister
from .....domain.calculations.registry.binding_targets import casillas_by_binding
from .....domain.calculations.registry.schema import ModeloRevision
from .....domain.calculations.registry.tests.authored_editions import filing_year_envelope
from .....domain.invoices.catalogue import InvoiceCatalogue
from .....domain.invoices.enums import IvaRate
from .....domain.invoices.models import Invoice
from .....domain.iva.deduction_facts import IvaDeductionClassificationProvenance
from .....domain.iva.schema import InvoiceKind, IvaCategory
from .....domain.modelos.calculation_revision_sources import CalculationNoteFact, CalculationNoteSentence
from .....domain.transactions.date_partition import LedgerDatePartition
from .....domain.transactions.enums import BusinessClassification, TransactionDirection, TransactionLifecycleState
from .....domain.transactions.models import Transaction, TransactionCatalogue
from .....domain.transactions.raw_transaction import RawProvenance, RawTransaction, SourceFormat
from ...storage.tests.secure_sql import isolated_runtime_profile
from ..prorrata_register import ProrrataRegisterRepository
from ..transactions import TransactionCatalogueRepository
from .published_authority_support import published_authority_operation

_YEAR = filing_year_envelope().horizon

pytestmark = [pytest.mark.integration, pytest.mark.hex_persistence_adapter]

_NOW = datetime(_YEAR, 2, 10, 12, 0, tzinfo=UTC)
_Q1 = Period.from_year_and_code(_YEAR, "1T")
_BUCKET_ID = "28282828-2828-4828-8828-282828282828"
_M303_IMPORT_BASE_BINDING = "modelo-303-iva-soportado-importaciones-base"
_M303_IMPORT_CUOTA_BINDING = "modelo-303-iva-soportado-importaciones-cuota"


class _EmptyInvoiceCatalogueReader:
    def load(self) -> InvoiceCatalogue:
        return InvoiceCatalogue()


class _EmptyTransactionCatalogueReader:
    def load(self) -> TransactionCatalogue:
        return TransactionCatalogue()

    def partition_by_date_range(self, start: date, end: date) -> LedgerDatePartition:
        return LedgerDatePartition(in_window=TransactionCatalogue(), index_complete=True)


def _resolver(repository: TransactionCatalogueRepository) -> LedgerIvaAggregationSourceResolver:
    return LedgerIvaAggregationSourceResolver(
        transaction_repository=repository,
        invoice_catalogue_read_ports=InvoiceCatalogueReadPorts(
            invoice_reader=_EmptyInvoiceCatalogueReader(),
            transaction_reader=_EmptyTransactionCatalogueReader(),
        ),
        prorrata_register_repository=ProrrataRegisterRepository(bucket_id=repository.bucket_id),
        investment_asset_register=BienesInversionIvaRegister(),
        investment_asset_profile_id=repository.bucket_id,
    )


@cache
def _revision(modelo_id: str) -> ModeloRevision:
    """The committed revision governing each modelo's IVA ledger bindings."""
    period = "1T" if modelo_id == "303" else "0A"
    return published_authority_operation().snapshot(modelo_id, filing_year=_Q1.filing_year, period=period).revision


def _revision_without_fact(revision: ModeloRevision, fact: str) -> ModeloRevision:
    """Return ``revision`` with every ``ledger_iva_aggregation`` binding drawing ``fact`` removed.

    Models a revision declaring no binding for the fact at all. Stripping the
    committed revision, rather than keying on a modelo that happens to lack the
    fact today, keeps the case true once every form models it correctly.
    """
    kept = [
        binding
        for binding in revision.bindings
        if not (binding.source.value == "ledger_iva_aggregation" and getattr(binding.provider, "fact", None) == fact)
    ]
    return revision.model_copy(update={"bindings": tuple(kept)})


def _revision_without_import_base(revision: ModeloRevision) -> ModeloRevision:
    """Return ``revision`` without the ``base_amount_sum`` bindings that reach an import row.

    The fact stays declared for the domestic, intra-community and export rows, so
    this is the partitioned shape: the import base alone reaches no binding. The
    committed Modelo 303 binds that base to box [32], so the gap is planted in a
    copy rather than read off a live residue.
    """
    import_third_country = IvaCategory("import_third_country")
    kept = [
        binding
        for binding in revision.bindings
        if not (
            binding.source.value == "ledger_iva_aggregation"
            and getattr(binding.provider, "fact", None) == "base_amount_sum"
            and import_third_country in getattr(binding.provider, "categories", ())
        )
    ]
    assert len(kept) < len(revision.bindings), "the revision declares no import base binding to strip"
    return revision.model_copy(update={"bindings": tuple(kept)})


def _sale(
    provider_id: str,
    *,
    base: str,
    iva: str,
    recargo: str | None = None,
) -> Transaction:
    """A domestic standard-rate sale carrying base, cuota and optional recargo."""
    recargo_amount = None if recargo is None else Decimal(recargo)
    gross = Decimal(base) + Decimal(iva) + (recargo_amount or Decimal("0"))
    raw = RawTransaction(
        provider_transaction_id=provider_id,
        booked_date=date(_YEAR, 2, 10),
        value_date=date(_YEAR, 2, 10),
        amount=gross,
        currency="EUR",
        counterparty="Minorista Recargo SL",
        description=f"venta {provider_id}",
        provenance=RawProvenance(
            source_path=Path(__file__),
            source_sha256="a" * 64,
            source_row_index=1,
            source_format=SourceFormat.MANUAL,
            ingested_at=_NOW,
            provider_name="manual",
        ),
        raw_fields={"row": provider_id},
    )
    return Transaction.model_validate(
        {
            "raw": raw,
            "direction": TransactionDirection.INCOMING,
            "group_label": None,
            "source_jurisdiction": "ES",
            "business_classification": BusinessClassification.BUSINESS,
            "taxable_base": Decimal(base),
            "iva_rate": Decimal("0.21"),
            "iva_amount": Decimal(iva),
            "iva_category": IvaCategory("domestic_general"),
            "lifecycle_state": TransactionLifecycleState.ACTIVE,
            "classified_at": _NOW,
            "classified_by": "manual",
        },
    )


def _third_country_import() -> Transaction:
    """A third-country import carrying a base that only the quantity screen sees."""
    raw = RawTransaction(
        provider_transaction_id="import-1",
        booked_date=date(_YEAR, 2, 10),
        value_date=date(_YEAR, 2, 10),
        amount=Decimal("1000.00"),
        currency="EUR",
        counterparty="Proveedor extracomunitario",
        description="importacion de bienes",
        provenance=RawProvenance(
            source_path=Path(__file__),
            source_sha256="d" * 64,
            source_row_index=2,
            source_format=SourceFormat.MANUAL,
            ingested_at=_NOW,
            provider_name="manual",
        ),
        raw_fields={"row": "import-1"},
    )
    return Transaction.model_validate(
        {
            "raw": raw,
            "direction": TransactionDirection.OUTGOING,
            "group_label": None,
            "source_jurisdiction": "ES",
            "business_classification": BusinessClassification.BUSINESS,
            "taxable_base": Decimal("1000.00"),
            "iva_rate": Decimal("0.21"),
            "iva_amount": Decimal("210.00"),
            "iva_category": IvaCategory("import_third_country"),
            "deduction_fact_kind": IvaDeductionFactKind.from_registry("import_current"),
            "deduction_provenance": IvaDeductionClassificationProvenance(
                authority=IvaDeductionEvidenceAuthority.from_registry("customs_declaration"),
                source_locator="customs:import-1",
                evidence_digest="e" * 64,
            ),
            "lifecycle_state": TransactionLifecycleState.ACTIVE,
            "classified_at": _NOW,
            "classified_by": "manual",
        },
    )


def test_the_advisory_reaches_the_resolver_envelope(tmp_path: Path) -> None:
    """The quantity screen is wired into the live resolver envelope."""
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=_BUCKET_ID) as profile:
        repository = TransactionCatalogueRepository(bucket_id=_BUCKET_ID, objects=profile.repository)
        repository.save(
            TransactionCatalogue.from_transactions((_sale("s-1", base="1000.00", iva="210.00"),)),
        )
        resolution = _resolver(repository).resolve(
            CalculationSourceContext(
                bucket_id=_BUCKET_ID,
                modelo="303",
                filing_year=_YEAR,
                period=_Q1,
                revision=_revision_without_fact(_revision("303"), "base_amount_sum"),
            ),
        )

    advisories = [
        diagnostic for diagnostic in resolution.diagnostics if diagnostic.reason == "unrouted_declarable_quantity"
    ]
    assert len(advisories) == 1, "a revision drawing no base must surface exactly one advisory"
    assert "base_amount_sum" in advisories[0].message
    assert "1000.00" in advisories[0].message, "the advisory must name the amount that goes undeclared"
    assert advisories[0].resolver_id == "ledger_iva_aggregation"


def test_the_committed_revision_raises_no_advisory_in_the_envelope(tmp_path: Path) -> None:
    """Against the committed revision, a covered row stays silent."""
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=_BUCKET_ID) as profile:
        repository = TransactionCatalogueRepository(bucket_id=_BUCKET_ID, objects=profile.repository)
        repository.save(
            TransactionCatalogue.from_transactions((_sale("s-1", base="1000.00", iva="210.00"),)),
        )
        resolution = _resolver(repository).resolve(
            CalculationSourceContext(
                bucket_id=_BUCKET_ID,
                modelo="303",
                filing_year=_YEAR,
                period=_Q1,
                revision=_revision("303"),
            ),
        )

    assert not [
        diagnostic for diagnostic in resolution.diagnostics if diagnostic.reason == "unrouted_declarable_quantity"
    ]


def test_the_import_base_lands_in_box_32_on_the_committed_revision(tmp_path: Path) -> None:
    """A third-country import's base reaches box [32] and raises no residue advisory.

    Box [32] is the base of "cuotas soportadas en las importaciones de bienes
    corrientes", whose cuota is box [33]; both read the same import rows.
    """
    revision = _revision("303")
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=_BUCKET_ID) as profile:
        repository = TransactionCatalogueRepository(bucket_id=_BUCKET_ID, objects=profile.repository)
        repository.save(TransactionCatalogue.from_transactions((_third_country_import(),)))
        resolution = _resolver(repository).resolve(
            CalculationSourceContext(
                bucket_id=_BUCKET_ID,
                modelo="303",
                filing_year=_YEAR,
                period=_Q1,
                revision=revision,
            ),
        )

    assert casillas_by_binding(revision)[_M303_IMPORT_BASE_BINDING] == (validated_casilla_id("32"),)
    assert resolution.binding_values[_M303_IMPORT_BASE_BINDING] == Decimal("1000.00")
    assert resolution.binding_values[_M303_IMPORT_CUOTA_BINDING] == Decimal("210.00")
    assert not [
        diagnostic for diagnostic in resolution.diagnostics if diagnostic.reason == "unrouted_declarable_quantity"
    ]


class _InvoiceCatalogueReader:
    def __init__(self, *invoices: Invoice) -> None:
        self._catalogue = InvoiceCatalogue(invoices={invoice.invoice_id: invoice for invoice in invoices})

    def load(self) -> InvoiceCatalogue:
        return self._catalogue


def _uncategorised_eu_service() -> Invoice:
    """A 0 % service invoiced to a German business, read from the Libro de facturas with no IVA category."""
    return Invoice.model_validate(
        {
            "bucket_id": _BUCKET_ID,
            "kind": InvoiceKind.ISSUED.value,
            "invoice_number": "2025-002",
            "issued_at": date(_YEAR, 1, 31).isoformat(),
            "counterparty_name": "Kunde GmbH",
            "counterparty_tax_id": "DE123456788",
            "counterparty_country": "DE",
            "base_total": "1500.00",
            "iva_total": "0.00",
            "grand_total": "1500.00",
            "currency": "EUR",
            "payment_status": "PENDING",
            "lines": [
                {
                    "description": "Servicio de consultoria",
                    "quantity": "1",
                    "unit_price": "1500.00",
                    "subtotal": "1500.00",
                    "iva_rate": IvaRate.from_registry("RATE_0").value,
                    "iva_amount": "0.00",
                },
            ],
        },
    )


def test_an_unrouted_invoice_base_is_named_by_its_invoice_date_and_amount(tmp_path: Path) -> None:
    """The note a blocked check rests on names the record, its date and the amount it leaves out.

    A base no box of the committed Modelo 303 draws still blocks; the note must
    tell the filer which invoice to correct, not only that some record is wrong.
    """
    invoice = _uncategorised_eu_service()
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=_BUCKET_ID) as profile:
        repository = TransactionCatalogueRepository(bucket_id=_BUCKET_ID, objects=profile.repository)
        resolver = LedgerIvaAggregationSourceResolver(
            transaction_repository=repository,
            invoice_catalogue_read_ports=InvoiceCatalogueReadPorts(
                invoice_reader=_InvoiceCatalogueReader(invoice),
                transaction_reader=_EmptyTransactionCatalogueReader(),
            ),
            prorrata_register_repository=ProrrataRegisterRepository(bucket_id=_BUCKET_ID),
            investment_asset_register=BienesInversionIvaRegister(),
            investment_asset_profile_id=_BUCKET_ID,
        )
        resolution = resolver.resolve(
            CalculationSourceContext(
                bucket_id=_BUCKET_ID,
                modelo="303",
                filing_year=_YEAR,
                period=_Q1,
                revision=_revision("303"),
            ),
        )

    (note,) = [
        diagnostic for diagnostic in resolution.diagnostics if diagnostic.reason == "unrouted_declarable_quantity"
    ]
    assert note.source_ref == f"invoice:{invoice.invoice_id}"
    assert note.fact == CalculationNoteFact.of(
        CalculationNoteSentence.UNROUTED_IVA_BASE,
        rows=(f"invoice:{invoice.invoice_id}:0",),
        row_date=date(_YEAR, 1, 31).isoformat(),
        row_amount=Decimal("1500.00"),
    )
    assert "base_amount_sum" in note.message
    assert "domestic_zero" in note.message


def test_the_advisory_names_the_categories_carrying_the_residue(tmp_path: Path) -> None:
    """A live residue advisory identifies the category carrying the amount, and only that one.

    The ledger holds a routed domestic sale beside a third-country import whose
    base the stripped revision leaves undrawn, so the advisory has to single out
    the import category rather than every category present.
    """
    revision = _revision_without_import_base(_revision("303"))
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=_BUCKET_ID) as profile:
        repository = TransactionCatalogueRepository(bucket_id=_BUCKET_ID, objects=profile.repository)
        repository.save(
            TransactionCatalogue.from_transactions(
                (_sale("s-1", base="500.00", iva="105.00"), _third_country_import()),
            ),
        )
        resolution = _resolver(repository).resolve(
            CalculationSourceContext(
                bucket_id=_BUCKET_ID,
                modelo="303",
                filing_year=_YEAR,
                period=_Q1,
                revision=revision,
            ),
        )

    advisories = [
        diagnostic for diagnostic in resolution.diagnostics if diagnostic.reason == "unrouted_declarable_quantity"
    ]
    assert len(advisories) == 1, "the import base residue must surface exactly one advisory"
    message = advisories[0].message
    assert "base_amount_sum" in message
    assert "import_third_country" in message
    assert "1000.00" in message, "the advisory must name the import base, not the routed sale base"
    for covered in (
        "domestic_general",
        "domestic_reduced",
        "domestic_super_reduced",
        "intra_community_acquisition_reverse_charge",
        "intra_community_service_acquisition_reverse_charge",
    ):
        assert covered not in message, f"{covered} draws base on this revision and must not be blamed"

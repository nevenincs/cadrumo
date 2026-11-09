"""A received invoice's stated retención reaches Modelo 111 and Modelo 115 the way a taxpayer records it.

APP-QA's first quarter of 2025 in miniature. The taxpayer keeps the Libro de
facturas and pays from the bank account; nothing is captured by hand.

- A gestoría run by a natural person bills 300.00 plus 21 per cent IVA and
  withholds 15 per cent, 45.00, paid net at 318.00. Hand-derived Modelo 111
  oracle (AEAT instructions, casillas 07 to 09 and 30; RIRPF arts. 95 and 101):
  one perceptor, base 300.00, retención 45.00, total 45.00.
- A landlord company bills the premises' rent of 1500.00 plus IVA and withholds
  19 per cent, 285.00. Hand-derived Modelo 115 oracle (AEAT instructions,
  casillas 01 to 03; RIRPF arts. 100 and 101, RIS arts. 60.1.e and 65): one
  perceptor, base 1500.00, retención 285.00.
- The same gestoría organised as an SLP bills a professional fee with the same
  15 per cent stated. RIS art. 60.1 lists no professional fee among an IS
  taxpayer's income subject to retención, so the invoice is a blocking finding
  and Modelo 111 is not completed without it.

None of the invoices declares an IVA treatment: the invoice book import sets none.
"""

from __future__ import annotations

from datetime import UTC, date, datetime
from decimal import Decimal
from pathlib import Path

import pytest

from cadrumo.domain.calculations.registry.tests.published_authority import (
    published_snapshot,
    published_supported_filing_years,
)
from cadrumo.domain.invoices.tests.catalogue_support import build_invoice_catalogue

from ....core.period import Period
from ....domain.calculations.registry.bindings import resolve_available_bound_inputs_by_casilla_id
from ....domain.calculations.registry.formula_runtime import calculate_registry_snapshot
from ....domain.calculations.registry.schema import RegistrySnapshot
from ....domain.invoices.catalogue import InvoiceCatalogue
from ....domain.invoices.enums import IvaRate, PaymentStatus
from ....domain.invoices.models import Invoice, InvoiceLine
from ....domain.iva.schema import InvoiceKind
from ....domain.modelos.calculation_revision_sources import CalculationNoteSentence
from ....domain.transactions.date_partition import LedgerDatePartition
from ....domain.transactions.enums import BusinessClassification, TransactionDirection, TransactionLifecycleState
from ....domain.transactions.models import Transaction, TransactionCatalogue
from ....domain.transactions.raw_transaction import RawProvenance, RawTransaction, SourceFormat
from ...invoices.catalogue_reads_ports import InvoiceCatalogueReadPorts
from ..errors import RetencionesWindowEmptyError
from ..modelo_bindings_retenciones import RetencionesAggregationSourceResolver
from ..received_invoice_withholding import ReceivedInvoiceWithholdingFindingKind, stored_invoice_withholding_findings
from ..retencion_observations_repository import RetencionObservationPorts
from ..retenciones import RetencionObservation
from ..source_mesh import CalculationSourceContext, CalculationSourceResolution

pytestmark = [pytest.mark.unit, pytest.mark.hex_application, pytest.mark.usefixtures("operation")]

BUCKET = "bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb"
_YEAR = 2025
_Q1 = Period.from_year_and_code(_YEAR, "1T")
_NATURAL_PERSON_NIF = "12345678Z"
_COMPANY_NIF = "B81000010"


class _EmptyStore:
    def load_observations(self, modelo: str, period: Period) -> tuple[RetencionObservation, ...]:
        del modelo, period
        return ()

    def load_annual_source_observations(self, source_modelo: str, filing_year: int) -> tuple[RetencionObservation, ...]:
        del source_modelo, filing_year
        return ()

    def load_source_observations_through_year(
        self, source_modelo: str, last_filing_year: int
    ) -> tuple[RetencionObservation, ...]:
        del source_modelo, last_filing_year
        return ()


class _Invoices:
    def __init__(self, catalogue: InvoiceCatalogue) -> None:
        self._catalogue = catalogue

    def load(self) -> InvoiceCatalogue:
        return self._catalogue


class _Movements:
    def __init__(self, catalogue: TransactionCatalogue) -> None:
        self._catalogue = catalogue

    def load(self) -> TransactionCatalogue:
        return self._catalogue

    def partition_by_date_range(self, start: date, end: date) -> LedgerDatePartition:
        raise AssertionError("the projection reads the whole catalogue")


def _payment(provider_id: str, day: date, *, cash: Decimal, irpf_category: str | None) -> Transaction:
    raw = RawTransaction(
        provider_transaction_id=provider_id,
        booked_date=day,
        value_date=day,
        amount=cash,
        currency="EUR",
        counterparty="Proveedor",
        description=f"TRANSF EMITIDA {provider_id}",
        provenance=RawProvenance(
            source_path=Path(__file__),
            source_sha256="e" * 64,
            source_row_index=1,
            source_format=SourceFormat.CSV,
            ingested_at=datetime(_YEAR, 4, 6, 12, 0, tzinfo=UTC),
            provider_name="CSV provider",
        ),
        raw_fields={},
    )
    return Transaction.model_validate(
        {
            "raw": raw,
            "direction": TransactionDirection.OUTGOING,
            "group_label": None,
            "source_jurisdiction": "ES",
            "business_classification": BusinessClassification.BUSINESS,
            "irpf_category": irpf_category,
            "lifecycle_state": TransactionLifecycleState.ACTIVE,
            "classified_at": datetime(_YEAR, 4, 6, 13, 0, tzinfo=UTC),
            "classified_by": "manual",
        },
    )


def _received(
    number: str,
    day: date,
    *,
    supplier: str,
    tax_id: str,
    base: Decimal,
    retencion: Decimal,
    rate: Decimal,
    linked: tuple[str, ...],
) -> Invoice:
    cuota = (base * Decimal("0.21")).quantize(Decimal("0.01"))
    line = InvoiceLine(
        description="Servicio",
        quantity=Decimal("1"),
        unit_price=base,
        subtotal=base,
        iva_rate=IvaRate.from_registry("RATE_21"),
        iva_amount=cuota,
    )
    return Invoice.model_validate(
        {
            "kind": InvoiceKind.RECEIVED,
            "invoice_number": number,
            "issued_at": day,
            "counterparty_name": supplier,
            "counterparty_tax_id": tax_id,
            "counterparty_country": "ES",
            "bucket_id": BUCKET,
            "base_total": base,
            "iva_total": cuota,
            "grand_total": base + cuota,
            "currency": "EUR",
            "lines": (line,),
            "payment_status": PaymentStatus.PAID,
            "iva_category": None,
            "retention_rate": rate,
            "retention_amount": retencion,
            "linked_transaction_ids": linked,
        },
    )


def _quarter(*, gestoria_nif: str) -> tuple[InvoiceCatalogue, TransactionCatalogue]:
    fee = _payment("GESTORIA-0125", date(_YEAR, 2, 10), cash=Decimal("318.00"), irpf_category="actividad_economica")
    rent = _payment("ALQUILER-0125", date(_YEAR, 1, 5), cash=Decimal("1530.00"), irpf_category="arrendamiento_local")
    gestoria = _received(
        "G-2025-014",
        date(_YEAR, 2, 3),
        supplier="Gestoría Ejemplo",
        tax_id=gestoria_nif,
        base=Decimal("300.00"),
        retencion=Decimal("45.00"),
        rate=Decimal("0.15"),
        linked=(fee.transaction_id,),
    )
    landlord = _received(
        "A-2025-001",
        date(_YEAR, 1, 2),
        supplier="Inmuebles Ejemplo SL",
        tax_id=_COMPANY_NIF,
        base=Decimal("1500.00"),
        retencion=Decimal("285.00"),
        rate=Decimal("0.19"),
        # Held on the movement alone, as the invoice book import leaves it.
        linked=(),
    )
    movements = (fee, rent.model_copy(update={"invoice_id": landlord.invoice_id}))
    return build_invoice_catalogue((gestoria, landlord)), TransactionCatalogue.from_transactions(movements)


def _resolve(
    modelo: str, *, gestoria_nif: str = _NATURAL_PERSON_NIF
) -> tuple[RegistrySnapshot, CalculationSourceResolution]:
    invoices, movements = _quarter(gestoria_nif=gestoria_nif)
    snapshot = published_snapshot(modelo, filing_year=_YEAR, period="1T")
    resolver = RetencionesAggregationSourceResolver(
        ports=RetencionObservationPorts(repository=_EmptyStore()),
        invoice_catalogue=InvoiceCatalogueReadPorts(
            invoice_reader=_Invoices(invoices),
            transaction_reader=_Movements(movements),
        ),
    )
    resolution = resolver.resolve(
        CalculationSourceContext(
            bucket_id=BUCKET, modelo=modelo, filing_year=_YEAR, period=_Q1, revision=snapshot.revision
        )
    )
    return snapshot, resolution


def _casillas(snapshot: RegistrySnapshot, resolution: CalculationSourceResolution) -> dict[str, Decimal]:
    result = calculate_registry_snapshot(
        snapshot,
        inputs=resolve_available_bound_inputs_by_casilla_id(snapshot.revision, resolution.binding_values),
        binding_values=resolution.binding_values,
        date_context={"filing_period": date(_YEAR, 3, 31)},
    )
    return {str(casilla): value for casilla, value in result.values.items()}


def test_a_natural_person_gestorias_retencion_fills_modelo_111_activity_boxes() -> None:
    snapshot, resolution = _resolve("111")

    casillas = _casillas(snapshot, resolution)

    assert resolution.diagnostics == ()
    assert casillas["07"] == Decimal("1")
    assert casillas["08"] == Decimal("300.00")
    assert casillas["09"] == Decimal("45.00")
    assert casillas["30"] == Decimal("45.00")


def test_a_landlord_companys_retencion_fills_modelo_115() -> None:
    snapshot, resolution = _resolve("115")

    casillas = _casillas(snapshot, resolution)

    assert resolution.diagnostics == ()
    assert casillas["01"] == Decimal("1")
    assert casillas["02"] == Decimal("1500.00")
    assert casillas["03"] == Decimal("285.00")


def test_an_slps_professional_fee_with_a_stated_retencion_holds_modelo_111_back() -> None:
    _, resolution = _resolve("111", gestoria_nif=_COMPANY_NIF)

    assert resolution.binding_values == {}
    assert resolution.unresolved_binding_ids
    assert [(item.reason, item.fact.sentence if item.fact else None) for item in resolution.diagnostics] == [
        ("source_domain_not_ready", CalculationNoteSentence.WITHHOLDING_INVOICE_ENTITY_PROFESSIONAL_FEE)
    ]
    fact = resolution.diagnostics[0].fact
    assert fact is not None
    assert dict(fact.values) == {"invoice": "G-2025-014", "counterparty": "Gestoría Ejemplo", "amount": "45.00"}


def test_the_slps_fee_does_not_disturb_modelo_115() -> None:
    _, resolution = _resolve("115", gestoria_nif=_COMPANY_NIF)

    assert resolution.diagnostics == ()


def test_an_unpaid_invoice_is_not_yet_a_retencion_for_a_natural_person() -> None:
    invoices, _ = _quarter(gestoria_nif=_NATURAL_PERSON_NIF)
    snapshot = published_snapshot("111", filing_year=_YEAR, period="1T")
    resolver = RetencionesAggregationSourceResolver(
        ports=RetencionObservationPorts(repository=_EmptyStore()),
        invoice_catalogue=InvoiceCatalogueReadPorts(
            invoice_reader=_Invoices(invoices),
            transaction_reader=_Movements(TransactionCatalogue.from_transactions(())),
        ),
    )

    with pytest.raises(RetencionesWindowEmptyError):
        resolver.resolve(
            CalculationSourceContext(
                bucket_id=BUCKET, modelo="111", filing_year=_YEAR, period=_Q1, revision=snapshot.revision
            )
        )


# APP-QA D42: an SLP's fee confirmed with its stated 15 per cent, before any payment.
_SLP_NIF = "B81000069"


def _slp_fee() -> Invoice:
    return _received(
        "AE-2026-007",
        date(2026, 2, 10),
        supplier="Asesores Ejemplo SLP",
        tax_id=_SLP_NIF,
        base=Decimal("300.00"),
        retencion=Decimal("45.00"),
        rate=Decimal("0.15"),
        linked=(),
    )


def test_an_slps_fee_carries_a_blocking_finding_on_the_invoice_itself() -> None:
    findings = stored_invoice_withholding_findings(_slp_fee(), TransactionCatalogue.from_transactions(()))

    assert [(item.kind, item.blocking, item.modelo, item.legal_refs) for item in findings] == [
        (ReceivedInvoiceWithholdingFindingKind.ENTITY_PROFESSIONAL_FEE, True, "111", ("rd-634-2015:art-60",))
    ]
    assert findings[0].kind.value == "received_invoice_entity_professional_fee"
    assert findings[0].retencion == Decimal("45.00")


def test_a_companys_rent_carries_no_finding_on_the_invoice() -> None:
    invoices, movements = _quarter(gestoria_nif=_NATURAL_PERSON_NIF)
    landlord = next(invoice for invoice in invoices.values() if invoice.invoice_number == "A-2025-001")
    gestoria = next(invoice for invoice in invoices.values() if invoice.invoice_number == "G-2025-014")

    assert stored_invoice_withholding_findings(landlord, movements) == ()
    assert stored_invoice_withholding_findings(gestoria, movements) == ()


def test_the_quarters_modelo_111_is_held_back_by_an_unpaid_slp_fee() -> None:
    snapshot = published_snapshot("111", filing_year=2026, period="1T")
    resolver = RetencionesAggregationSourceResolver(
        ports=RetencionObservationPorts(repository=_EmptyStore()),
        invoice_catalogue=InvoiceCatalogueReadPorts(
            invoice_reader=_Invoices(build_invoice_catalogue((_slp_fee(),))),
            transaction_reader=_Movements(TransactionCatalogue.from_transactions(())),
        ),
    )

    resolution = resolver.resolve(
        CalculationSourceContext(
            bucket_id=BUCKET,
            modelo="111",
            filing_year=2026,
            period=Period.from_year_and_code(2026, "1T"),
            revision=snapshot.revision,
        )
    )

    assert resolution.binding_values == {}
    assert [item.fact.sentence if item.fact else None for item in resolution.diagnostics] == [
        CalculationNoteSentence.WITHHOLDING_INVOICE_ENTITY_PROFESSIONAL_FEE
    ]


def test_another_quarters_modelo_111_is_not_held_back_by_it() -> None:
    snapshot = published_snapshot("111", filing_year=2026, period="2T")
    resolver = RetencionesAggregationSourceResolver(
        ports=RetencionObservationPorts(repository=_EmptyStore()),
        invoice_catalogue=InvoiceCatalogueReadPorts(
            invoice_reader=_Invoices(build_invoice_catalogue((_slp_fee(),))),
            transaction_reader=_Movements(TransactionCatalogue.from_transactions(())),
        ),
    )

    with pytest.raises(RetencionesWindowEmptyError):
        resolver.resolve(
            CalculationSourceContext(
                bucket_id=BUCKET,
                modelo="111",
                filing_year=2026,
                period=Period.from_year_and_code(2026, "2T"),
                revision=snapshot.revision,
            )
        )


# APP-QA row 17: Pedro Gestor Ejemplo, a natural-person professional, bills 300.00
# plus IVA on 28 February with 15 per cent retención, 45.00, paid net at 318.00
# the same day. Hand-derived Modelo 111 oracle (AEAT instructions, casillas 07 to
# 09, 28 and 30; RIRPF arts. 95 and 101): one perceptor, base 300.00, retención
# 45.00, total retenciones 45.00, resultado a ingresar 45.00.
_PROFESSIONAL_NIF = "51234567C"


def _professional_quarter(year: int, *, irpf_category: str | None) -> tuple[InvoiceCatalogue, TransactionCatalogue]:
    fee = _payment("GES-PAGO-0228", date(year, 2, 28), cash=Decimal("318.00"), irpf_category=irpf_category)
    invoice = _received(
        f"GES-{year}-001",
        date(year, 2, 28),
        supplier="Pedro Gestor Ejemplo",
        tax_id=_PROFESSIONAL_NIF,
        base=Decimal("300.00"),
        retencion=Decimal("45.00"),
        rate=Decimal("0.15"),
        linked=(fee.transaction_id,),
    )
    return build_invoice_catalogue((invoice,)), TransactionCatalogue.from_transactions((fee,))


def _resolve_professional(
    year: int, *, irpf_category: str | None
) -> tuple[RegistrySnapshot, CalculationSourceResolution]:
    invoices, movements = _professional_quarter(year, irpf_category=irpf_category)
    snapshot = published_snapshot("111", filing_year=year, period="1T")
    resolver = RetencionesAggregationSourceResolver(
        ports=RetencionObservationPorts(repository=_EmptyStore()),
        invoice_catalogue=InvoiceCatalogueReadPorts(
            invoice_reader=_Invoices(invoices),
            transaction_reader=_Movements(movements),
        ),
    )
    resolution = resolver.resolve(
        CalculationSourceContext(
            bucket_id=BUCKET,
            modelo="111",
            filing_year=year,
            period=Period.from_year_and_code(year, "1T"),
            revision=snapshot.revision,
        )
    )
    return snapshot, resolution


def _supported_years() -> tuple[int, ...]:
    support = published_supported_filing_years()
    assert support is not None
    return tuple(support.years)


def test_a_professionals_retencion_fills_modelo_111_in_every_supported_year() -> None:
    years = _supported_years()
    assert _YEAR in years

    for year in years:
        snapshot, resolution = _resolve_professional(year, irpf_category="actividad_economica")
        result = calculate_registry_snapshot(
            snapshot,
            inputs=resolve_available_bound_inputs_by_casilla_id(snapshot.revision, resolution.binding_values),
            binding_values=resolution.binding_values,
            date_context={"filing_period": date(year, 3, 31)},
        )
        casillas = {str(casilla): value for casilla, value in result.values.items()}

        assert resolution.diagnostics == (), year
        assert resolution.unresolved_binding_ids == (), year
        assert {box: casillas.get(box) for box in ("07", "08", "09", "28", "30")} == {
            "07": Decimal("1"),
            "08": Decimal("300.00"),
            "09": Decimal("45.00"),
            "28": Decimal("45.00"),
            "30": Decimal("45.00"),
        }, year


def test_an_unclassified_payment_holds_modelo_111_back_with_a_finding() -> None:
    _, resolution = _resolve_professional(_YEAR, irpf_category=None)

    assert resolution.binding_values == {}
    assert {"modelo-111-actividades-dinerario-retenciones", "modelo-111-actividades-dinerario-base"} <= {
        str(binding_id) for binding_id in resolution.unresolved_binding_ids
    }
    assert [
        (item.reason, item.fact.sentence if item.fact is not None else None) for item in resolution.diagnostics
    ] == [("source_domain_not_ready", CalculationNoteSentence.WITHHOLDING_INVOICE_KIND_UNDECLARED)]
    assert resolution.diagnostics[0].source_ref is not None
    assert resolution.diagnostics[0].message.endswith(
        ReceivedInvoiceWithholdingFindingKind.INCOME_KIND_UNDECLARED.value
    )

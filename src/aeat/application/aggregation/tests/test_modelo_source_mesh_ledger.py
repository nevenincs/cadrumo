"""Source mesh parity tests for existing ledger-backed modelo bindings."""

from __future__ import annotations

import logging
from collections.abc import Iterator
from datetime import UTC, date, datetime
from decimal import Decimal
from pathlib import Path

import pytest
from sqlalchemy import text

from ....adapters.persistence.storage.sql import SecureObjectRepository, session_scope
from ....core import Period
from ....core.classification import SensitivityClass
from ....core.resources import resources
from ....domain.calculations.registry import ModeloRevision
from ....domain.categories import SpendingCategory
from ....domain.invoices import (
    Invoice,
    InvoiceCatalogue,
    InvoiceCatalogueRepository,
    InvoiceLine,
    IvaRate,
    PaymentStatus,
)
from ....domain.iva import (
    EUMemberState,
    IvaCategory,
    IvaRateKind,
    OssIossRegime,
    TransactionKind,
)
from ....domain.iva import (
    InvoiceKind as CatalogueInvoiceKind,
)
from ....domain.iva import (
    InvoiceKind as IvaInvoiceKind,
)
from ....domain.transactions import (
    TX_BUCKET_NAMESPACE,
    BusinessClassification,
    RawProvenance,
    RawTransaction,
    SourceFormat,
    Transaction,
    TransactionCatalogue,
    TransactionCatalogueRepository,
    TransactionDirection,
)
from ....tests.secure_sql import isolated_runtime_profile
from .. import (
    AggregationValidationError,
    CalculationSourceContext,
    IvaLedgerAggregationIssueReason,
    LedgerIvaAggregationSourceResolver,
    LedgerRentaExpenseAggregationSourceResolver,
    OssIossLedgerCandidate,
    OssIossLedgerSourceResolver,
    aggregate_iva_ledger_observations,
    aggregate_oss_ioss_bindings,
    merge_source_resolutions,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_BUCKET_ID = "28282828-2828-4828-8828-282828282828"


@pytest.fixture
def secure_objects(tmp_path: Path) -> Iterator[SecureObjectRepository]:
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=_BUCKET_ID) as profile:
        yield profile.repository


def _revision(modelo: str, revision_id: str) -> ModeloRevision:
    modelo_definition = next(item for item in resources().modelos.all() if item.id == modelo)
    return modelo_definition.revisions[revision_id]


def _raw_transaction(
    provider_id: str,
    *,
    booked_date: date,
    amount: Decimal,
) -> RawTransaction:
    return RawTransaction(
        transaction_id=provider_id,
        booked_date=booked_date,
        value_date=booked_date,
        amount=amount,
        currency="EUR",
        counterparty="Cliente o proveedor",
        description=f"ledger row {provider_id}",
        provenance=RawProvenance(
            source_path=Path(__file__),
            source_sha256="e" * 64,
            source_row_index=1,
            source_format=SourceFormat.MANUAL,
            ingested_at=datetime(2026, 2, 11, 12, 0, tzinfo=UTC),
            provider_name="manual-ledger",
        ),
        raw_fields={"source_kind": "ledger_transaction"},
    )


def _iva_transaction(
    provider_id: str,
    *,
    direction: TransactionDirection,
    amount: Decimal,
    taxable_base: Decimal,
    iva_amount: Decimal,
    booked_date: date = date(2026, 2, 10),
    iva_category: IvaCategory | None = None,
    counterparty_eu_member_state: EUMemberState | None = None,
) -> Transaction:
    fields: dict[str, object] = {
        "raw": _raw_transaction(provider_id, booked_date=booked_date, amount=amount),
        "direction": direction,
        "business_classification": BusinessClassification.BUSINESS,
        "source_jurisdiction": "ES",
        "group_label": None,
        "category_id": "test_iva_operation",
        "taxable_base": taxable_base,
        "iva_rate": Decimal("0.21"),
        "iva_amount": iva_amount,
        "classified_at": datetime(2026, 2, 11, 13, 0, tzinfo=UTC),
        "classified_by": "manual",
    }
    if iva_category is not None:
        fields["iva_category"] = iva_category
    if counterparty_eu_member_state is not None:
        fields["counterparty_eu_member_state"] = counterparty_eu_member_state
    return Transaction.model_validate(fields)


def _renta_transaction(
    provider_id: str,
    *,
    purchase_invoice_evidence_id: str | None,
) -> Transaction:
    return Transaction.model_validate(
        {
            "raw": _raw_transaction(
                provider_id,
                booked_date=date(2025, 4, 5),
                amount=Decimal("121.00"),
            ),
            "direction": TransactionDirection.OUTGOING,
            "group_label": None,
            "business_classification": BusinessClassification.BUSINESS,
            "source_jurisdiction": "ES",
            "purchase_invoice_evidence_id": purchase_invoice_evidence_id,
            "category_id": SpendingCategory.ASESORIA_FISCAL.value,
            "classified_at": datetime(2025, 4, 6, 13, 0, tzinfo=UTC),
            "classified_by": "manual",
        },
    )


def _invoice(tx_id: str, *, bucket_id: str = _BUCKET_ID) -> Invoice:
    line = InvoiceLine(
        description="Asesoria fiscal",
        quantity=Decimal("1"),
        unit_price=Decimal("100.00"),
        subtotal=Decimal("100.00"),
        iva_rate=IvaRate.RATE_21,
        iva_amount=Decimal("21.00"),
    )
    return Invoice.model_validate(
        {
            "bucket_id": bucket_id,
            "kind": CatalogueInvoiceKind.RECEIVED,
            "invoice_number": f"INV-{tx_id}",
            "issued_at": date(2025, 4, 1),
            "counterparty_name": "Proveedor SL",
            "counterparty_tax_id": "B12345674",
            "counterparty_country": "ES",
            "base_total": Decimal("100.00"),
            "iva_total": Decimal("21.00"),
            "grand_total": Decimal("121.00"),
            "currency": "EUR",
            "lines": (line,),
            "payment_status": PaymentStatus.PAID,
            "linked_transaction_ids": (tx_id,),
        },
    )


def _domestic_iva_invoice(
    invoice_number: str,
    *,
    kind: CatalogueInvoiceKind,
    issued_at: date,
    taxable_base: Decimal,
    iva_amount: Decimal,
    bucket_id: str = _BUCKET_ID,
    linked_transaction_ids: tuple[str, ...] = (),
) -> Invoice:
    line = InvoiceLine(
        description="Operacion interior con IVA",
        quantity=Decimal("1"),
        unit_price=taxable_base,
        subtotal=taxable_base,
        iva_rate=IvaRate.RATE_21,
        iva_amount=iva_amount,
    )
    return Invoice.model_validate(
        {
            "bucket_id": bucket_id,
            "kind": kind,
            "invoice_number": invoice_number,
            "issued_at": issued_at,
            "counterparty_name": "Cliente ES" if kind is CatalogueInvoiceKind.ISSUED else "Proveedor ES",
            "counterparty_tax_id": "B12345674",
            "counterparty_country": "ES",
            "base_total": taxable_base,
            "iva_total": iva_amount,
            "grand_total": taxable_base + iva_amount,
            "currency": "EUR",
            "lines": (line,),
            "payment_status": PaymentStatus.PAID,
            "linked_transaction_ids": linked_transaction_ids,
        },
    )


def test_iva_source_mesh_resolver_resolves_general_sale_and_purchase(secure_objects: SecureObjectRepository) -> None:
    revision = _revision("303", "2009-y-siguientes")
    tx_repo = TransactionCatalogueRepository(
        bucket_id=_BUCKET_ID,
        objects=secure_objects,
    )
    incoming = _iva_transaction(
        "sale-general",
        direction=TransactionDirection.INCOMING,
        amount=Decimal("121.00"),
        taxable_base=Decimal("100.00"),
        iva_amount=Decimal("21.00"),
    )
    outgoing = _iva_transaction(
        "purchase-general",
        direction=TransactionDirection.OUTGOING,
        amount=Decimal("60.50"),
        taxable_base=Decimal("50.00"),
        iva_amount=Decimal("10.50"),
    )
    tx_repo.save(TransactionCatalogue.from_transactions((incoming, outgoing)))

    resolution = LedgerIvaAggregationSourceResolver(transaction_repository=tx_repo).resolve(
        CalculationSourceContext(
            bucket_id=_BUCKET_ID,
            modelo="303",
            filing_year=2026,
            period=Period.from_year_and_code(2026, "1T"),
            revision=revision,
        ),
    )

    assert resolution.binding_values  # non-empty: at least one IVA binding resolved
    assert set(resolution.source_transaction_ids) == {
        incoming.transaction_id,
        outgoing.transaction_id,
    }
    assert resolution.diagnostics == ()
    assert {item.source_ref for item in resolution.provenance} == {
        f"transaction:{incoming.transaction_id}",
        f"transaction:{outgoing.transaction_id}",
    }


def test_iva_source_mesh_resolver_refuses_m303_invoice_domestic_iva_without_transaction_ledger(
    secure_objects: SecureObjectRepository,
) -> None:
    revision = _revision("303", "2023-y-siguientes")
    tx_repo = TransactionCatalogueRepository(bucket_id=_BUCKET_ID, objects=secure_objects)
    invoice_repo = InvoiceCatalogueRepository(bucket_id=_BUCKET_ID, objects=secure_objects)
    invoice = _domestic_iva_invoice(
        "LAURA-1T-SALE",
        kind=CatalogueInvoiceKind.ISSUED,
        issued_at=date(2025, 2, 10),
        taxable_base=Decimal("10000.00"),
        iva_amount=Decimal("2100.00"),
    )
    invoice_repo.save(InvoiceCatalogue.from_invoices((invoice,)))

    with pytest.raises(AggregationValidationError) as exc_info:
        LedgerIvaAggregationSourceResolver(
            transaction_repository=tx_repo,
            invoice_repository=invoice_repo,
        ).resolve(
            CalculationSourceContext(
                bucket_id=_BUCKET_ID,
                modelo="303",
                filing_year=2025,
                period=Period.from_year_and_code(2025, "1T"),
                revision=revision,
            ),
        )

    assert exc_info.value.context["reason"] == "invoice_domestic_iva_not_in_transaction_ledger"
    assert exc_info.value.context["period"] == "1T"
    assert exc_info.value.context["invoice_count"] == "1"
    assert exc_info.value.context["invoice_domestic_iva_excess_by_binding"] == {
        "modelo-303-iva-repercutido-general-cuota": "2100.00",
    }


def test_iva_source_mesh_resolver_accepts_m303_invoice_domestic_iva_when_transaction_ledger_matches(
    secure_objects: SecureObjectRepository,
) -> None:
    revision = _revision("303", "2023-y-siguientes")
    tx_repo = TransactionCatalogueRepository(bucket_id=_BUCKET_ID, objects=secure_objects)
    invoice_repo = InvoiceCatalogueRepository(bucket_id=_BUCKET_ID, objects=secure_objects)
    transaction = _iva_transaction(
        "laura-1t-sale",
        direction=TransactionDirection.INCOMING,
        amount=Decimal("12100.00"),
        taxable_base=Decimal("10000.00"),
        iva_amount=Decimal("2100.00"),
        booked_date=date(2025, 2, 10),
    )
    invoice = _domestic_iva_invoice(
        "LAURA-1T-SALE",
        kind=CatalogueInvoiceKind.ISSUED,
        issued_at=date(2025, 2, 10),
        taxable_base=Decimal("10000.00"),
        iva_amount=Decimal("2100.00"),
        linked_transaction_ids=(transaction.transaction_id,),
    )
    tx_repo.save(TransactionCatalogue.from_transactions((transaction,)))
    invoice_repo.save(InvoiceCatalogue.from_invoices((invoice,)))

    resolution = LedgerIvaAggregationSourceResolver(
        transaction_repository=tx_repo,
        invoice_repository=invoice_repo,
    ).resolve(
        CalculationSourceContext(
            bucket_id=_BUCKET_ID,
            modelo="303",
            filing_year=2025,
            period=Period.from_year_and_code(2025, "1T"),
            revision=revision,
        ),
    )

    assert resolution.binding_values["modelo-303-iva-repercutido-general-cuota"] == Decimal("2100.00")
    assert resolution.source_transaction_ids == (transaction.transaction_id,)
    assert resolution.diagnostics == ()


def test_iva_source_mesh_resolver_routes_domestic_reverse_charge_to_box_13_and_37_net_zero(
    secure_objects: SecureObjectRepository,
) -> None:
    """A ``DOMESTIC_REVERSE_CHARGE`` operation is now CONSUMED, not surfaced as a gap.

    Inversión del sujeto pasivo interior (Ley 37/1992 art. 84.Uno.2): the
    recipient self-assesses both an IVA devengado entry (official casilla 13,
    ``modelo-303-iva-autorepercutido-interior-devengado-cuota``) AND a matching
    IVA deducible entry (official casilla 37,
    ``modelo-303-iva-autorepercutido-interior-deducible-cuota``). Before the
    flow-fix the application classifier left the observation on its
    direction-only ``SOPORTADO`` flow, no binding selected it, and the #64
    advisory surfaced it as an unrouted cuota-bearing gap. Now the classifier
    recomputes the flow via :func:`derive_flow_for_classification`, routing the
    reverse-charge category to ``INVERSION_SUJETO_PASIVO``; the two new bindings
    consume it (each resolves the 42.00 self-assessed cuota), so the pair nets
    to zero in the M303 resultado and the advisory no longer fires.
    """
    revision = _revision("303", "2009-y-siguientes")
    tx_repo = TransactionCatalogueRepository(
        bucket_id=_BUCKET_ID,
        objects=secure_objects,
    )
    # A consumed domestic sale (matches the repercutido-general binding) ...
    domestic_sale = _iva_transaction(
        "sale-general",
        direction=TransactionDirection.INCOMING,
        amount=Decimal("121.00"),
        taxable_base=Decimal("100.00"),
        iva_amount=Decimal("21.00"),
    )
    # ... plus a reverse-charge operation now routed to box 13 + 37.
    # Self-assessed IVA: the bank gross equals the base (no IVA charged on the
    # invoice); the cuota is self-assessed.
    reverse_charge = _iva_transaction(
        "domestic-reverse-charge",
        direction=TransactionDirection.INCOMING,
        amount=Decimal("200.00"),
        taxable_base=Decimal("200.00"),
        iva_amount=Decimal("42.00"),
        iva_category=IvaCategory.DOMESTIC_REVERSE_CHARGE,
    )
    tx_repo.save(TransactionCatalogue.from_transactions((domestic_sale, reverse_charge)))

    resolution = LedgerIvaAggregationSourceResolver(transaction_repository=tx_repo).resolve(
        CalculationSourceContext(
            bucket_id=_BUCKET_ID,
            modelo="303",
            filing_year=2026,
            period=Period.from_year_and_code(2026, "1T"),
            revision=revision,
        ),
    )

    # The reverse-charge observation is now CONSUMED: the #64 advisory no longer
    # flags it once the binding routes its self-assessed cuota.
    unconsumed_diagnostics = [
        diagnostic
        for diagnostic in resolution.diagnostics
        if diagnostic.source_kind == "ledger_iva_aggregation" and reverse_charge.transaction_id in diagnostic.message
    ]
    assert unconsumed_diagnostics == []
    # Both the devengado (box 13) and deducible (box 37) bindings carry the
    # self-assessed 42.00 cuota, so the pair nets to zero in the resultado.
    devengado = resolution.binding_values["modelo-303-iva-autorepercutido-interior-devengado-cuota"]
    deducible = resolution.binding_values["modelo-303-iva-autorepercutido-interior-deducible-cuota"]
    assert devengado == Decimal("42.00")
    assert deducible == Decimal("42.00")
    assert devengado - deducible == Decimal("0")
    # The reverse-charge transaction is recorded in the resolved provenance set,
    # not discarded as an unsupported observation.
    assert reverse_charge.transaction_id in resolution.source_transaction_ids


def test_iva_source_mesh_resolver_does_not_flag_cuota_less_by_law_observation(
    secure_objects: SecureObjectRepository,
) -> None:
    """#64 refinement: a cuota-less-by-law observation must NOT fire the advisory.

    An ``INTRA_COMMUNITY_SUPPLY`` repercutido operation is an entrega
    intracomunitaria exenta (Ley 37/1992 art. 25): it bears zero M303 cuota and
    correctly matches no ``ledger_iva_aggregation`` cuota binding. Before the
    refinement the advisory false-fired on it (any unconsumed declarable
    observation was flagged); after, it must be silent because the category is
    cuota-less by law. This guards against the false-positive that surfaced an
    unactionable "modelling gap" for a category that simply has no cuota.
    """
    revision = _revision("303", "2009-y-siguientes")
    tx_repo = TransactionCatalogueRepository(
        bucket_id=_BUCKET_ID,
        objects=secure_objects,
    )
    domestic_sale = _iva_transaction(
        "sale-general",
        direction=TransactionDirection.INCOMING,
        amount=Decimal("121.00"),
        taxable_base=Decimal("100.00"),
        iva_amount=Decimal("21.00"),
    )
    exempt_supply = _iva_transaction(
        "intra-community-supply",
        direction=TransactionDirection.INCOMING,
        amount=Decimal("242.00"),
        taxable_base=Decimal("200.00"),
        iva_amount=Decimal("42.00"),
        iva_category=IvaCategory.INTRA_COMMUNITY_SUPPLY,
        counterparty_eu_member_state=EUMemberState.DE,
    )
    tx_repo.save(TransactionCatalogue.from_transactions((domestic_sale, exempt_supply)))

    resolution = LedgerIvaAggregationSourceResolver(transaction_repository=tx_repo).resolve(
        CalculationSourceContext(
            bucket_id=_BUCKET_ID,
            modelo="303",
            filing_year=2026,
            period=Period.from_year_and_code(2026, "1T"),
            revision=revision,
        ),
    )

    assert resolution.binding_values
    cuota_less_diagnostics = [
        diagnostic
        for diagnostic in resolution.diagnostics
        if diagnostic.source_kind == "ledger_iva_aggregation" and exempt_supply.transaction_id in diagnostic.message
    ]
    assert cuota_less_diagnostics == []


def test_iva_source_mesh_resolver_surfaces_no_unconsumed_diagnostic_when_all_consumed(
    secure_objects: SecureObjectRepository,
) -> None:
    """#64 converse: an all-consumed IVA observation set surfaces ZERO unconsumed diagnostics.

    This is the anti-tautology guard for the advisory above: only observations no
    binding selects produce the diagnostic. A domestic sale matched by the
    repercutido-general binding must leave ``diagnostics`` empty.
    """
    revision = _revision("303", "2009-y-siguientes")
    tx_repo = TransactionCatalogueRepository(
        bucket_id=_BUCKET_ID,
        objects=secure_objects,
    )
    domestic_sale = _iva_transaction(
        "sale-general",
        direction=TransactionDirection.INCOMING,
        amount=Decimal("121.00"),
        taxable_base=Decimal("100.00"),
        iva_amount=Decimal("21.00"),
    )
    tx_repo.save(TransactionCatalogue.from_transactions((domestic_sale,)))

    resolution = LedgerIvaAggregationSourceResolver(transaction_repository=tx_repo).resolve(
        CalculationSourceContext(
            bucket_id=_BUCKET_ID,
            modelo="303",
            filing_year=2026,
            period=Period.from_year_and_code(2026, "1T"),
            revision=revision,
        ),
    )

    assert resolution.binding_values
    assert resolution.diagnostics == ()


def test_iva_source_mesh_resolver_suppresses_out_of_period_personal_source_diagnostic(
    secure_objects: SecureObjectRepository,
) -> None:
    revision = _revision("303", "2009-y-siguientes")
    tx_repo = TransactionCatalogueRepository(
        bucket_id=_BUCKET_ID,
        objects=secure_objects,
    )
    personal_q2 = _iva_transaction(
        "personal-q2",
        direction=TransactionDirection.OUTGOING,
        amount=Decimal("121.00"),
        taxable_base=Decimal("100.00"),
        iva_amount=Decimal("21.00"),
        booked_date=date(2026, 4, 10),
    ).model_copy(update={"business_classification": BusinessClassification.PERSONAL})
    catalogue = TransactionCatalogue.from_transactions((personal_q2,))
    tx_repo.save(catalogue)

    raw_aggregation = aggregate_iva_ledger_observations(catalogue, period=Period.from_year_and_code(2026, "1T"))
    assert [issue.reason for issue in raw_aggregation.issues] == [IvaLedgerAggregationIssueReason.OUTSIDE_PERIOD]

    resolution = LedgerIvaAggregationSourceResolver(transaction_repository=tx_repo).resolve(
        CalculationSourceContext(
            bucket_id=_BUCKET_ID,
            modelo="303",
            filing_year=2026,
            period=Period.from_year_and_code(2026, "1T"),
            revision=revision,
        ),
    )

    assert resolution.diagnostics == ()
    assert personal_q2.transaction_id not in resolution.source_transaction_ids


def test_iva_source_mesh_resolver_keeps_in_period_missing_fact_diagnostic(
    secure_objects: SecureObjectRepository,
) -> None:
    revision = _revision("303", "2009-y-siguientes")
    tx_repo = TransactionCatalogueRepository(
        bucket_id=_BUCKET_ID,
        objects=secure_objects,
    )
    missing_rate = _iva_transaction(
        "business-missing-rate",
        direction=TransactionDirection.OUTGOING,
        amount=Decimal("121.00"),
        taxable_base=Decimal("100.00"),
        iva_amount=Decimal("21.00"),
    ).model_copy(update={"iva_rate": None})
    catalogue = TransactionCatalogue.from_transactions((missing_rate,))
    tx_repo.save(catalogue)

    raw_aggregation = aggregate_iva_ledger_observations(catalogue, period=Period.from_year_and_code(2026, "1T"))
    assert [issue.reason for issue in raw_aggregation.issues] == [IvaLedgerAggregationIssueReason.MISSING_IVA_RATE]

    resolution = LedgerIvaAggregationSourceResolver(transaction_repository=tx_repo).resolve(
        CalculationSourceContext(
            bucket_id=_BUCKET_ID,
            modelo="303",
            filing_year=2026,
            period=Period.from_year_and_code(2026, "1T"),
            revision=revision,
        ),
    )

    assert [diagnostic.reason for diagnostic in resolution.diagnostics] == ["source_issue"]
    assert "transaction has no iva_rate fact" in resolution.diagnostics[0].message


def test_iva_source_mesh_resolver_degrades_on_unreadable_storage(
    secure_objects: SecureObjectRepository,
    caplog: pytest.LogCaptureFixture,
) -> None:
    revision = _revision("303", "2009-y-siguientes")
    tx_repo = TransactionCatalogueRepository(
        bucket_id=_BUCKET_ID,
        objects=secure_objects,
    )
    incoming = _iva_transaction(
        "sale-general",
        direction=TransactionDirection.INCOMING,
        amount=Decimal("121.00"),
        taxable_base=Decimal("100.00"),
        iva_amount=Decimal("21.00"),
    )
    tx_repo.save(TransactionCatalogue.from_transactions((incoming,)))
    with session_scope(secure_objects._engine) as session:
        session.execute(
            text("UPDATE secure_objects SET payload = X'00' WHERE namespace = :namespace"),
            {"namespace": TX_BUCKET_NAMESPACE},
        )

    with caplog.at_level(logging.DEBUG, logger="aeat.application.aggregation._source_mesh"):
        resolution = LedgerIvaAggregationSourceResolver(transaction_repository=tx_repo).resolve(
            CalculationSourceContext(
                bucket_id=_BUCKET_ID,
                modelo="303",
                filing_year=2026,
                period=Period.from_year_and_code(2026, "1T"),
                revision=revision,
            ),
        )
    merged = merge_source_resolutions((resolution,))

    assert resolution.binding_values == {}
    assert resolution.source_transaction_ids == ()
    assert [diagnostic.reason for diagnostic in merged.diagnostics] == ["storage_degraded"]
    assert merged.diagnostics[0].source_kind == "ledger_iva_aggregation"
    assert any("source mesh resolver storage degradation" in record.message for record in caplog.records)


def test_iva_source_mesh_resolver_degrades_on_transaction_catalogue_drift(
    secure_objects: SecureObjectRepository,
    caplog: pytest.LogCaptureFixture,
) -> None:
    from ....domain.transactions._repository import transaction_index_object_key

    revision = _revision("303", "2009-y-siguientes")
    # Per-row catalogue: a corrupt membership-index row makes load() fail closed
    # with StoredTransactionDriftError, the drift the resolver must degrade on.
    secure_objects.save(
        namespace=TX_BUCKET_NAMESPACE,
        object_key=transaction_index_object_key(_BUCKET_ID),
        classification=SensitivityClass.FINANCIAL,
        schema_version=1,
        written_at=datetime(2026, 6, 4, 12, 0, tzinfo=UTC),
        payload=b"{}",
    )
    tx_repo = TransactionCatalogueRepository(
        bucket_id=_BUCKET_ID,
        objects=secure_objects,
    )

    with caplog.at_level(logging.DEBUG, logger="aeat.application.aggregation._source_mesh"):
        resolution = LedgerIvaAggregationSourceResolver(transaction_repository=tx_repo).resolve(
            CalculationSourceContext(
                bucket_id=_BUCKET_ID,
                modelo="303",
                filing_year=2026,
                period=Period.from_year_and_code(2026, "1T"),
                revision=revision,
            ),
        )

    assert resolution.binding_values == {}
    assert resolution.source_transaction_ids == ()
    assert [diagnostic.reason for diagnostic in resolution.diagnostics] == ["storage_degraded"]
    assert resolution.diagnostics[0].source_kind == "ledger_iva_aggregation"
    assert any("source mesh resolver storage degradation" in record.message for record in caplog.records)


def test_renta_source_mesh_resolver_preserves_purchase_invoice_evidence_provenance(
    secure_objects: SecureObjectRepository,
) -> None:
    revision = _revision("100", "2025")
    tx_repo = TransactionCatalogueRepository(
        bucket_id=_BUCKET_ID,
        objects=secure_objects,
    )
    invoice_repo = InvoiceCatalogueRepository(bucket_id=_BUCKET_ID, objects=secure_objects)
    initial = _renta_transaction("renta-linked", purchase_invoice_evidence_id=None)
    invoice = _invoice(initial.transaction_id)
    linked = _renta_transaction("renta-linked", purchase_invoice_evidence_id=invoice.invoice_id)
    tx_repo.save(TransactionCatalogue.from_transactions((linked,)))
    invoice_repo.save(InvoiceCatalogue.from_invoices((invoice,)))

    resolution = LedgerRentaExpenseAggregationSourceResolver(
        transaction_repository=tx_repo,
        invoice_repository=invoice_repo,
    ).resolve(
        CalculationSourceContext(
            bucket_id=_BUCKET_ID,
            modelo="100",
            filing_year=2025,
            period=Period.from_year_and_code(2025, "0A"),
            revision=revision,
        ),
    )

    assert resolution.binding_values  # non-empty: renta expense binding resolved
    assert resolution.source_transaction_ids == (linked.transaction_id,)
    assert resolution.diagnostics == ()
    assert {item.source_ref for item in resolution.provenance} == {
        f"transaction:{linked.transaction_id}",
        f"purchase-invoice-evidence:{invoice.invoice_id}",
    }


def test_oss_source_mesh_resolver_matches_existing_candidate_binding_wrapper() -> None:
    revision = _revision("369", "esquema-union")
    candidates = (
        OssIossLedgerCandidate(
            ledger_id="oss-ledger-1",
            transaction_date=date(2025, 6, 15),
            regime=OssIossRegime.UNION_SCHEME,
            destination_member_state=EUMemberState.DE,
            rate_kind=IvaRateKind.GENERAL,
            invoice_direction=IvaInvoiceKind.ISSUED,
            transaction_kind=TransactionKind.OSS_UNION_SERVICES,
            base_amount=Decimal("100.00"),
            iva_amount=Decimal("19.00"),
        ),
    )

    legacy = aggregate_oss_ioss_bindings(revision, candidates)
    resolution = OssIossLedgerSourceResolver(candidates=candidates).resolve(
        CalculationSourceContext(
            bucket_id=_BUCKET_ID,
            modelo="369",
            filing_year=2025,
            period=Period.from_year_and_code(2025, "4T"),
            revision=revision,
        ),
    )

    assert resolution.binding_values == legacy
    assert resolution.source_transaction_ids == ("oss-ledger-1",)
    assert resolution.diagnostics == ()
    assert tuple(item.source_ref for item in resolution.provenance) == ("transaction:oss-ledger-1",)


def test_oss_source_mesh_resolver_surfaces_advisory_for_unrouted_observation() -> None:
    """A non-zero OSS line routed to no binding surfaces a non-blocking advisory.

    The esquema-union revision binds DE/FR union services and DE goods-distance;
    no binding selects an IT destination. An IT-destination candidate matches no
    binding; its base/cuota would otherwise silently vanish from the M369 form,
    so the resolver MUST emit an ``unrouted_observation`` advisory rather than
    dropping it (no-silent-under-declaration).
    """
    revision = _revision("369", "esquema-union")
    candidates = (
        OssIossLedgerCandidate(
            ledger_id="oss-it-unrouted",
            transaction_date=date(2025, 6, 15),
            regime=OssIossRegime.UNION_SCHEME,
            destination_member_state=EUMemberState.IT,
            rate_kind=IvaRateKind.GENERAL,
            invoice_direction=IvaInvoiceKind.ISSUED,
            transaction_kind=TransactionKind.OSS_UNION_SERVICES,
            base_amount=Decimal("100.00"),
            iva_amount=Decimal("22.00"),
        ),
    )

    resolution = OssIossLedgerSourceResolver(candidates=candidates).resolve(
        CalculationSourceContext(
            bucket_id=_BUCKET_ID,
            modelo="369",
            filing_year=2025,
            period=Period.from_year_and_code(2025, "4T"),
            revision=revision,
        ),
    )

    unrouted = [
        diagnostic
        for diagnostic in resolution.diagnostics
        if diagnostic.reason == "unrouted_observation"
        and diagnostic.source_kind == "ledger_oss_aggregation"
        and "oss-it-unrouted" in diagnostic.message
    ]
    assert len(unrouted) == 1, "an IT-destination OSS line routed to no binding must surface one advisory"
    # The advisory is non-blocking: the resolution still resolves the (zero) DE
    # binding value and records the candidate so calculate succeeds.
    assert resolution.binding_values.get("modelo-369-union-de-services-21pct") == Decimal("0")

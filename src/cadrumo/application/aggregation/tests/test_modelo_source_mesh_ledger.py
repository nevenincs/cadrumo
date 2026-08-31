"""Source mesh parity tests for existing ledger-backed modelo bindings."""

from __future__ import annotations

import logging
from datetime import UTC, date, datetime
from decimal import Decimal
from functools import cache
from pathlib import Path

import pytest
from sqlalchemy import text

from ....adapters.persistence.profile.invoices import InvoiceCatalogueRepository
from ....adapters.persistence.profile.prorrata_register import ProrrataRegisterRepository
from ....adapters.persistence.profile.transactions import TransactionCatalogueRepository
from ....adapters.persistence.storage.errors import EnvelopeVersionError
from ....adapters.persistence.storage.secure_object_namespaces import TRANSACTION_CATALOGUE_NAMESPACE
from ....adapters.persistence.storage.sql import SecureObjectRepository, session_scope
from ....core.aggregation import BindingSourceKind
from ....core.classification.policies import SensitivityClass
from ....core.iva_deduction_fact import IvaDeductionEvidenceAuthority, IvaDeductionFactKind
from ....core.operator_action_enums import NoRecoveryOutcome
from ....core.period import Period
from ....core.prorrata_register import ProrrataProvisionalProvenance, ProrrataRegisterRegime
from ....domain.bienes_inversion.register import BienesInversionIvaRegister
from ....domain.calculations.registry.authority import bundled_authority
from ....domain.calculations.registry.schema import ModeloRevision
from ....domain.categories.spending_category import SpendingCategory
from ....domain.invoices.enums import InvoiceOperationDateRole, IvaRate, PaymentStatus
from ....domain.invoices.models import Invoice, InvoiceCatalogue, InvoiceLine
from ....domain.iva.classification import InvoiceKind as CatalogueInvoiceKind
from ....domain.iva.classification import InvoiceKind as IvaInvoiceKind
from ....domain.iva.classification import TransactionKind
from ....domain.iva.deduction_facts import IvaDeductionClassificationProvenance
from ....domain.iva.oss import OssIossRegime
from ....domain.iva.schema import EUMemberState, IvaCategory, IvaRateKind
from ....domain.prorrata_register.register import ProrrataRegister, ProrrataRegisterEntry
from ....domain.transactions.enums import BusinessClassification, TransactionDirection
from ....domain.transactions.models import Transaction, TransactionCatalogue
from ....domain.transactions.raw_transaction import RawProvenance, RawTransaction, SourceFormat
from .. import (
    AggregationValidationError,
    CalculationSourceContext,
    IvaLedgerAggregationIssueReason,
    LedgerRentaGastosEstimacionDirectaAggregationSourceResolver,
    OssIossLedgerCandidate,
    OssIossLedgerSourceResolver,
    aggregate_oss_ioss_bindings,
)
from .. import (
    LedgerIvaAggregationSourceResolver as _LedgerIvaAggregationSourceResolver,
)
from .._preconditions import AggregationPreconditionCondition
from .._source_mesh import CalculationSourceResolution
from ..source_resolution_operations import merge_source_resolutions
from ._iva_authority_support import aggregate_iva_ledger_observations

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_BUCKET_ID = "28282828-2828-4828-8828-282828282828"


class LedgerIvaAggregationSourceResolver(_LedgerIvaAggregationSourceResolver):
    """Bind injected real repositories to an explicit empty Bienes authority."""

    def __init__(
        self,
        *,
        transaction_repository: TransactionCatalogueRepository | None = None,
        invoice_repository: InvoiceCatalogueRepository | None = None,
    ) -> None:
        super().__init__(
            transaction_repository=transaction_repository,
            invoice_repository=invoice_repository,
            prorrata_register_repository=ProrrataRegisterRepository(
                bucket_id=(transaction_repository.bucket_id if transaction_repository is not None else _BUCKET_ID),
            ),
            investment_asset_register=BienesInversionIvaRegister(),
            investment_asset_profile_id=(
                transaction_repository.bucket_id if transaction_repository is not None else _BUCKET_ID
            ),
        )


@cache
def _revision(modelo: str, revision_id: str) -> ModeloRevision:
    modelo_definition = bundled_authority().modelo(modelo)
    return modelo_definition.revisions[revision_id]


@cache
def _m303_revision() -> ModeloRevision:
    return bundled_authority().snapshot("303", filing_year=2025, period="1T").revision


def _raw_transaction(
    provider_id: str,
    *,
    booked_date: date,
    amount: Decimal,
) -> RawTransaction:
    return RawTransaction(
        provider_transaction_id=provider_id,
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
    counterparty_country: str | None = None,
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
    if counterparty_country is not None:
        fields["counterparty_country"] = counterparty_country
    if direction is TransactionDirection.OUTGOING:
        fields["deduction_fact_kind"] = IvaDeductionFactKind.DOMESTIC_CURRENT
        fields["deduction_provenance"] = IvaDeductionClassificationProvenance(
            authority=IvaDeductionEvidenceAuthority.INVOICE_EVIDENCE,
            source_locator=f"invoice:{provider_id}",
            evidence_digest="a" * 64,
        )
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
    operation_date: date | None = None,
    counterparty_country: str = "ES",
    counterparty_tax_id: str = "B12345674",
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
            "counterparty_tax_id": counterparty_tax_id,
            "counterparty_country": counterparty_country,
            "base_total": taxable_base,
            "iva_total": iva_amount,
            "grand_total": taxable_base + iva_amount,
            "currency": "EUR",
            "lines": (line,),
            "payment_status": PaymentStatus.PAID,
            "linked_transaction_ids": linked_transaction_ids,
            **(
                {}
                if operation_date is None
                else {
                    "operation_date": operation_date,
                    "operation_date_role": InvoiceOperationDateRole.OPERATION_PERFORMED,
                }
            ),
        },
    )


def _exempt_intracommunity_invoice(
    invoice_number: str,
    *,
    kind: CatalogueInvoiceKind,
    issued_at: date,
    taxable_base: Decimal,
) -> Invoice:
    """An entrega intracomunitaria exenta: a real base, and no cuota at all."""
    line = InvoiceLine(
        description="Entrega intracomunitaria exenta",
        quantity=Decimal("1"),
        unit_price=taxable_base,
        subtotal=taxable_base,
        iva_rate=IvaRate.RATE_0,
        iva_amount=Decimal("0"),
    )
    return Invoice.model_validate(
        {
            "bucket_id": _BUCKET_ID,
            "kind": kind,
            "invoice_number": invoice_number,
            "issued_at": issued_at,
            "counterparty_name": "Kunde GmbH",
            "counterparty_tax_id": "DE345678901",
            "counterparty_country": "DE",
            "base_total": taxable_base,
            "iva_total": Decimal("0"),
            "grand_total": taxable_base,
            "currency": "EUR",
            "lines": (line,),
            "payment_status": PaymentStatus.PAID,
        },
    )


def test_iva_source_mesh_resolver_resolves_general_sale_and_purchase(secure_objects: SecureObjectRepository) -> None:
    revision = _revision("303", "2022")
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


def test_iva_source_mesh_resolver_carries_prorrata_apportionment_provenance(
    secure_objects: SecureObjectRepository,
) -> None:
    revision = _revision("303", "2022")
    tx_repo = TransactionCatalogueRepository(bucket_id=_BUCKET_ID, objects=secure_objects)
    prorrata_repo = ProrrataRegisterRepository(bucket_id=_BUCKET_ID, objects=secure_objects)
    outgoing = _iva_transaction(
        "purchase-prorrata-general",
        direction=TransactionDirection.OUTGOING,
        amount=Decimal("60.50"),
        taxable_base=Decimal("50.00"),
        iva_amount=Decimal("10.50"),
    )
    tx_repo.save(TransactionCatalogue.from_transactions((outgoing,)))
    prorrata_repo.save(
        ProrrataRegister(
            entries=(
                ProrrataRegisterEntry(
                    ejercicio=2026,
                    regime=ProrrataRegisterRegime.GENERAL,
                    especial_transition=None,
                    provisional_percentage=Decimal("80"),
                    provisional_provenance=ProrrataProvisionalProvenance.CARRIED_PRIOR_DEFINITIVA,
                    source_observation_ref="303:2025:4T",
                ),
            ),
        ),
    )

    resolution = LedgerIvaAggregationSourceResolver(transaction_repository=tx_repo).resolve(
        CalculationSourceContext(
            bucket_id=_BUCKET_ID,
            modelo="303",
            filing_year=2026,
            period=Period.from_year_and_code(2026, "1T"),
            revision=revision,
        ),
    )

    prorrata_provenance = [
        item for item in resolution.provenance if item.source_ref.startswith("prorrata-apportionment:")
    ]
    assert len(prorrata_provenance) == 1
    provenance = prorrata_provenance[0]
    assert provenance.resolved_binding_source is BindingSourceKind.LEDGER_IVA_AGGREGATION
    assert provenance.source_ref == (
        "prorrata-apportionment:2026:general:"
        "percentage:80:provenance:carried_prior_definitiva:source-observation:303:2025:4T"
    )
    assert provenance.source_casilla_ids == ()
    assert provenance.legal_refs
    assert provenance.source_refs


def test_iva_source_mesh_resolver_refuses_m303_invoice_domestic_iva_without_transaction_ledger(
    secure_objects: SecureObjectRepository,
) -> None:
    revision = _m303_revision()
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

    assert exc_info.value.context is not None
    assert exc_info.value.context["reason"] == "invoice_domestic_iva_not_in_transaction_ledger"
    assert exc_info.value.context["period"] == "1T"
    verdict = exc_info.value.terminal_precondition_verdict
    assert verdict is not None
    assert verdict.failed_condition_id == AggregationPreconditionCondition.INVOICE_LEDGER_COMPLETE.value
    assert verdict.action is None
    assert verdict.no_recovery_outcome is NoRecoveryOutcome.OPERATOR_DECISION
    assert verdict.evidence[0].values["invoice_count"] == 1


def test_iva_source_mesh_withholds_received_invoice_without_deduction_authority(
    secure_objects: SecureObjectRepository,
) -> None:
    """A received invoice reaches no SOPORTADO row until classified authority exists."""
    revision = _m303_revision()
    tx_repo = TransactionCatalogueRepository(bucket_id=_BUCKET_ID, objects=secure_objects)
    invoice_repo = InvoiceCatalogueRepository(bucket_id=_BUCKET_ID, objects=secure_objects)
    invoice = _domestic_iva_invoice(
        "PURCHASE-WITHOUT-DEDUCTION-AUTHORITY",
        kind=CatalogueInvoiceKind.RECEIVED,
        issued_at=date(2025, 2, 10),
        taxable_base=Decimal("100.00"),
        iva_amount=Decimal("21.00"),
    )
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

    assert resolution.source_transaction_ids == ()
    assert resolution.binding_values.get("modelo-303-iva-soportado-interiores-cuota", Decimal("0")) == Decimal("0")
    assert len(resolution.diagnostics) == 1
    diagnostic = resolution.diagnostics[0]
    assert diagnostic.reason == "source_issue"
    assert diagnostic.source_ref == f"invoice:{invoice.invoice_id}"
    assert "no exact deduction fact kind" in diagnostic.message
    assert diagnostic.remedy is not None
    assert "classified ledger transaction" in diagnostic.remedy


def test_iva_source_mesh_resolver_attributes_a_q1_operation_invoiced_in_q2_to_q1(
    secure_objects: SecureObjectRepository,
) -> None:
    """Period attribution follows the art. 75 devengo date, not the issue date.

    RD 1619/2012 art. 11 lets this B2B invoice be issued on 10 April for an
    operation performed on 28 March, so the record is lawful. Its cuota is
    devengada in Q1: the domestic-IVA screen must see it while calculating Q1
    and must NOT see it while calculating Q2. Both quarters are asserted,
    because a change that moved every invoice one quarter earlier would satisfy
    the Q1 half alone.
    """
    revision = _m303_revision()
    tx_repo = TransactionCatalogueRepository(bucket_id=_BUCKET_ID, objects=secure_objects)
    invoice_repo = InvoiceCatalogueRepository(bucket_id=_BUCKET_ID, objects=secure_objects)
    invoice = _domestic_iva_invoice(
        "LAURA-Q1-OPERATION-INVOICED-IN-Q2",
        kind=CatalogueInvoiceKind.ISSUED,
        issued_at=date(2025, 4, 10),
        taxable_base=Decimal("10000.00"),
        iva_amount=Decimal("2100.00"),
        operation_date=date(2025, 3, 28),
    )
    invoice_repo.save(InvoiceCatalogue.from_invoices((invoice,)))

    def _resolve(code: str) -> CalculationSourceResolution:
        return LedgerIvaAggregationSourceResolver(
            transaction_repository=tx_repo,
            invoice_repository=invoice_repo,
        ).resolve(
            CalculationSourceContext(
                bucket_id=_BUCKET_ID,
                modelo="303",
                filing_year=2025,
                period=Period.from_year_and_code(2025, code),
                revision=revision,
            ),
        )

    with pytest.raises(AggregationValidationError) as exc_info:
        _resolve("1T")
    assert exc_info.value.context is not None
    assert exc_info.value.context["period"] == "1T"
    assert exc_info.value.context["invoice_ids"] == (invoice.invoice_id,)

    # Q2 holds the issue date and nothing else: the invoice already devengo'd.
    q2_resolution = _resolve("2T")
    assert q2_resolution.diagnostics == ()
    assert exc_info.value.context["invoice_count"] == "1"
    assert exc_info.value.context["invoice_domestic_iva_excess_by_binding"] == {
        "modelo-303-iva-repercutido-general-cuota": "2100.00",
    }


def test_iva_source_mesh_resolver_accepts_m303_invoice_domestic_iva_when_transaction_ledger_matches(
    secure_objects: SecureObjectRepository,
) -> None:
    revision = _m303_revision()
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
    # The invoice records no fecha de operacion, so its Q1 placement rests on
    # the issue date. LIVA art. 75.Uno binds devengo to the operation date, so
    # the substitution is disclosed rather than passed off as a determination.
    assert [diagnostic.reason for diagnostic in resolution.diagnostics] == ["devengo_date_proxy_attribution"]
    assert "LAURA-1T-SALE" in resolution.diagnostics[0].message


def test_iva_source_mesh_resolver_raises_no_devengo_advisory_when_the_operation_date_is_recorded(
    secure_objects: SecureObjectRepository,
) -> None:
    """The other direction of the proxy advisory, on the real resolve path.

    Same fixture as the accept case above with one field added. An advisory
    that fires on every invoice would be indistinguishable from one that fires
    correctly, so the declared-date case is asserted silent as explicitly as
    the proxy case is asserted noisy.
    """
    revision = _m303_revision()
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
        operation_date=date(2025, 2, 5),
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
    direction-only ``SOPORTADO`` flow, no binding selected it, and the
    unconsumed-declarable-IVA advisory surfaced it as an unrouted cuota-bearing
    gap. Now the classifier
    recomputes the flow via :func:`derive_flow_for_classification`, routing the
    reverse-charge category to ``INVERSION_SUJETO_PASIVO``; the two new bindings
    consume it (each resolves the 42.00 self-assessed cuota), so the pair nets
    to zero in the M303 resultado and the advisory no longer fires.
    """
    revision = _revision("303", "2022")
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
    #
    # OUTGOING, because boxes 13 and 37 belong to the RECIPIENT of an art.
    # 84.Uno.2 operation and this fixture is written for the recipient. It was
    # INCOMING -- a sale the taxpayer ISSUED -- which is the supplier's side and
    # contradicts the docstring above. The fixture passed anyway only because the
    # flow derivation discarded invoice direction for reverse-charge categories,
    # so both sides collapsed onto the recipient's treatment. Once direction is
    # honoured the two stop being interchangeable and the fixture has to name
    # which side it means.
    reverse_charge = _iva_transaction(
        "domestic-reverse-charge",
        direction=TransactionDirection.OUTGOING,
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

    # The reverse-charge observation is now CONSUMED: the unconsumed-declarable-IVA
    # advisory no longer flags it once the binding routes its self-assessed cuota.
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
    """A cuota-less-by-law observation must NOT fire the advisory.

    An ``INTRA_COMMUNITY_SUPPLY`` repercutido operation is an entrega
    intracomunitaria exenta (Ley 37/1992 art. 25): it bears zero M303 cuota and
    correctly matches no ``ledger_iva_aggregation`` cuota binding. Before the
    refinement the advisory false-fired on it (any unconsumed declarable
    observation was flagged); after, it must be silent because the category is
    cuota-less by law. This guards against the false-positive that surfaced an
    unactionable "modelling gap" for a category that simply has no cuota.
    """
    revision = _revision("303", "2022")
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
        counterparty_country="DE",
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
    """The converse case: an all-consumed IVA observation set surfaces ZERO unconsumed diagnostics.

    This is the anti-tautology guard for the advisory above: only observations no
    binding selects produce the diagnostic. A domestic sale matched by the
    repercutido-general binding must leave ``diagnostics`` empty.
    """
    revision = _revision("303", "2022")
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


def test_iva_source_mesh_resolver_summarizes_out_of_period_personal_source_diagnostic(
    secure_objects: SecureObjectRepository,
) -> None:
    revision = _revision("303", "2022")
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

    assert len(resolution.diagnostics) == 1
    diagnostic = resolution.diagnostics[0]
    assert diagnostic.reason == "source_issue"
    assert diagnostic.source_kind == "ledger_iva_aggregation"
    assert diagnostic.resolver_id == "ledger_iva_aggregation"
    assert diagnostic.out_of_window_count == 1
    assert diagnostic.out_of_window_min_filing_date == date(2026, 4, 10)
    assert diagnostic.out_of_window_max_filing_date == date(2026, 4, 10)
    assert "outside the requested period" in diagnostic.message
    assert personal_q2.transaction_id not in resolution.source_transaction_ids


def test_iva_source_mesh_resolver_keeps_in_period_missing_fact_diagnostic(
    secure_objects: SecureObjectRepository,
) -> None:
    revision = _revision("303", "2022")
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
    revision = _revision("303", "2022")
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
            {"namespace": TRANSACTION_CATALOGUE_NAMESPACE.namespace},
        )

    with caplog.at_level(logging.DEBUG, logger="cadrumo.application.aggregation._source_mesh"):
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


def test_transaction_catalogue_refuses_new_legacy_drift_fixture(
    secure_objects: SecureObjectRepository,
) -> None:
    from ....domain.transactions.repository import transaction_index_object_key

    with pytest.raises(EnvelopeVersionError):
        secure_objects.save(
            namespace=TRANSACTION_CATALOGUE_NAMESPACE.namespace,
            object_key=transaction_index_object_key(_BUCKET_ID),
            classification=SensitivityClass.FINANCIAL,
            schema_version=1,
            written_at=datetime(2026, 6, 4, 12, 0, tzinfo=UTC),
            payload=b"{}",
        )


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

    resolution = LedgerRentaGastosEstimacionDirectaAggregationSourceResolver(
        transaction_repository=tx_repo,
        invoice_repository=invoice_repo,
        prorrata_register_repository=ProrrataRegisterRepository(bucket_id=_BUCKET_ID, objects=secure_objects),
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


def test_oss_source_mesh_resolver_matches_candidate_binding_aggregation() -> None:
    revision = _revision("369", "esquema-union")
    candidates = (
        OssIossLedgerCandidate(
            ledger_id="oss-ledger-1",
            transaction_date=date(2025, 7, 15),
            regime=OssIossRegime.UNION_SCHEME,
            destination_member_state=EUMemberState.DE,
            rate_kind=IvaRateKind.GENERAL,
            invoice_direction=IvaInvoiceKind.ISSUED,
            transaction_kind=TransactionKind.OSS_UNION_SERVICES,
            base_amount=Decimal("100.00"),
            iva_amount=Decimal("19.00"),
        ),
    )

    aggregated = aggregate_oss_ioss_bindings(revision, candidates)
    resolution = OssIossLedgerSourceResolver(candidates=candidates).resolve(
        CalculationSourceContext(
            bucket_id=_BUCKET_ID,
            modelo="369",
            filing_year=2025,
            period=Period.from_year_and_code(2025, "4T"),
            revision=revision,
        ),
    )

    assert resolution.binding_values == aggregated
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
            transaction_date=date(2025, 7, 15),
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


def test_the_screen_now_catches_a_non_es_invoice_carrying_spanish_cuota(
    secure_objects: SecureObjectRepository,
) -> None:
    """A foreign counterparty does not mean the operation carried no Spanish IVA.

    The screen filtered on the counterparty's COUNTRY, which was standing in
    for "carries Spanish IVA" and is a poor proxy for it. An invoice to a
    foreign customer can carry ordinary domestic cuota -- goods that never
    leave the país, a service localised here, a non-established consumer --
    and every one of those was exempt from the screen, which is precisely the
    under-declaration the screen exists to catch.

    Same figures as the domestic refusal case above; only the counterparty's
    country differs. Before this, changing that one field was enough to walk
    the invoice past the guard.
    """
    revision = _m303_revision()
    tx_repo = TransactionCatalogueRepository(bucket_id=_BUCKET_ID, objects=secure_objects)
    invoice_repo = InvoiceCatalogueRepository(bucket_id=_BUCKET_ID, objects=secure_objects)
    invoice = _domestic_iva_invoice(
        "DE-1T-SALE",
        kind=CatalogueInvoiceKind.ISSUED,
        issued_at=date(2025, 2, 10),
        taxable_base=Decimal("10000.00"),
        iva_amount=Decimal("2100.00"),
        counterparty_country="DE",
        counterparty_tax_id="DE345678901",
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

    assert exc_info.value.context is not None
    assert exc_info.value.context["reason"] == "invoice_domestic_iva_not_in_transaction_ledger"


def test_an_exempt_intracommunity_invoice_does_not_trip_the_widened_screen(
    secure_objects: SecureObjectRepository,
) -> None:
    """Positive control: widening the screen must not refuse the ordinary EU case.

    An entrega intracomunitaria exenta is the commonest non-ES invoice there
    is, and it carries no cuota at all. Dropping the country filter must not
    start refusing those, or the widening would block correct filings far more
    often than it catches wrong ones.

    It passes for a structural reason rather than by luck: the screen compares
    only lines carrying a positive cuota, so a zero-cuota invoice contributes
    no observation whatever its counterparty's country. That is why removing
    the country proxy widens WHICH invoices are considered without widening
    what is actually compared.
    """
    revision = _m303_revision()
    tx_repo = TransactionCatalogueRepository(bucket_id=_BUCKET_ID, objects=secure_objects)
    invoice_repo = InvoiceCatalogueRepository(bucket_id=_BUCKET_ID, objects=secure_objects)
    exempt = _exempt_intracommunity_invoice(
        "DE-1T-EXEMPT",
        kind=CatalogueInvoiceKind.ISSUED,
        issued_at=date(2025, 2, 10),
        taxable_base=Decimal("10000.00"),
    )
    invoice_repo.save(InvoiceCatalogue.from_invoices((exempt,)))

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

    assert resolution.resolver_id == "ledger_iva_aggregation"

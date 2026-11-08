"""Persisted IVA ledger seed shared by the M303-to-M390 annual vertical.

Writes four quarters of issued and received IVA transactions plus the matching
purchase invoices through the real secure-object repositories, and returns the
IVA amounts actually stored so callers assert engine output against stored fields.
"""

from __future__ import annotations

from datetime import UTC, date, datetime
from decimal import Decimal
from pathlib import Path
from typing import Literal

from cadrumo.adapters.persistence.profile.catalogue_creation import build_catalogue_creation_ports
from cadrumo.adapters.persistence.profile.invoices import InvoiceCatalogueRepository
from cadrumo.adapters.persistence.profile.modelos_work_units import WorkUnitCatalogueRepository
from cadrumo.adapters.persistence.profile.transactions import TransactionCatalogueRepository
from cadrumo.adapters.persistence.storage.sql.secure_objects import SecureObjectRepository
from cadrumo.application.invoices.catalogue_creation import build_catalogue_invoice
from cadrumo.core.iva_deduction_fact import IvaDeductionEvidenceAuthority, IvaDeductionFactKind
from cadrumo.domain.filing.software_identity import AeatProductSoftwareEvidence, AeatProductSoftwareIdentity
from cadrumo.domain.invoices.tests.catalogue_support import build_invoice_catalogue
from cadrumo.domain.iva.deduction_facts import IvaDeductionClassificationProvenance
from cadrumo.domain.iva.schema import EUMemberState, InvoiceKind, IvaCategory, require_eu_member_state
from cadrumo.domain.transactions.enums import BusinessClassification, TransactionDirection
from cadrumo.domain.transactions.models import Transaction, TransactionCatalogue
from cadrumo.domain.transactions.raw_transaction import RawProvenance, RawTransaction, SourceFormat

BUCKET_ID = "30330303-3030-4303-8303-303303303303"
YEAR = 2025
T0 = datetime(2025, 1, 10, 10, 0, tzinfo=UTC)
_IVA_RATE = Decimal("0.21")
_QUARTER_MONTH: dict[str, int] = {"1T": 2, "2T": 5, "3T": 8, "4T": 11}
type StoredIvaAxis = Literal["devengada", "deducible", "casilla_59", "resultado"]
type StoredIvaByPeriod = dict[str, dict[StoredIvaAxis, Decimal]]


# Laura / Taller Sol annual IVA scenario. Domestic 21% issued and received
# invoice rows drive the normal M303 cuota totals. Q2 additionally carries an
# exempt intra-Community supply base into casilla 59, and Q3 carries a domestic
# reverse-charge operation that books the same self-assessed cuota on both
# devengada and deducible axes.
_LAURA_QUARTER_FACTS: dict[str, dict[str, Decimal]] = {
    "1T": {
        "issued_base": Decimal("10000.00"),
        "issued_iva": Decimal("2100.00"),
        "received_base": Decimal("3000.00"),
        "received_iva": Decimal("630.00"),
        "eu_supply_base": Decimal("0.00"),
        "reverse_charge_base": Decimal("0.00"),
        "reverse_charge_iva": Decimal("0.00"),
    },
    "2T": {
        "issued_base": Decimal("12000.00"),
        "issued_iva": Decimal("2520.00"),
        "received_base": Decimal("2500.00"),
        "received_iva": Decimal("525.00"),
        "eu_supply_base": Decimal("1500.00"),
        "reverse_charge_base": Decimal("0.00"),
        "reverse_charge_iva": Decimal("0.00"),
    },
    "3T": {
        "issued_base": Decimal("9000.00"),
        "issued_iva": Decimal("1890.00"),
        "received_base": Decimal("2200.00"),
        "received_iva": Decimal("462.00"),
        "eu_supply_base": Decimal("0.00"),
        "reverse_charge_base": Decimal("800.00"),
        "reverse_charge_iva": Decimal("168.00"),
    },
    "4T": {
        "issued_base": Decimal("15000.00"),
        "issued_iva": Decimal("3150.00"),
        "received_base": Decimal("1800.00"),
        "received_iva": Decimal("378.00"),
        "eu_supply_base": Decimal("0.00"),
        "reverse_charge_base": Decimal("0.00"),
        "reverse_charge_iva": Decimal("0.00"),
    },
}


LAURA_ANNUAL_EXPECTED = {
    "devengada": Decimal("9828.00"),
    "deducible": Decimal("2163.00"),
    "resultado": Decimal("7665.00"),
}
IRENE_QUARTER_FACTS: dict[str, dict[str, Decimal]] = {
    period: {
        "issued_base": Decimal("10000.00"),
        "issued_iva": Decimal("2100.00"),
        "received_base": Decimal("3000.00"),
        "received_iva": Decimal("630.00"),
        "eu_supply_base": Decimal("0.00"),
        "reverse_charge_base": Decimal("0.00"),
        "reverse_charge_iva": Decimal("0.00"),
    }
    for period in _QUARTER_MONTH
}
IRENE_ANNUAL_EXPECTED = {
    "devengada": Decimal("8400.00"),
    "deducible": Decimal("2520.00"),
    "resultado": Decimal("5880.00"),
}
# AEAT Manual practico IVA 2025, Capitulo 5, prorrata general example
# (`corpus/manuals/iva/2025/source.pdf#Pag.137-138`). The provisional percentage
# carried from the previous year is 73 %; the year's operations (locales
# 25.000 EUR con derecho, viviendas 20.000 EUR exentas) give a definitive
# 25.000 / 45.000 = 56 %. Quarterly cuotas soportadas 400 / 420 / 460 / 160 EUR
# arise from received invoices at 10 %. The issued 21 % sales split the year's
# con-derecho volume across the quarters.
PRORRATA_QUARTER_FACTS: dict[str, dict[str, Decimal]] = {
    period: {
        "issued_base": issued_base,
        "issued_iva": issued_base * Decimal("0.21"),
        "received_base": received_iva * 10,
        "received_iva": received_iva,
        "eu_supply_base": Decimal("0.00"),
        "reverse_charge_base": Decimal("0.00"),
        "reverse_charge_iva": Decimal("0.00"),
    }
    for period, issued_base, received_iva in (
        ("1T", Decimal("6000.00"), Decimal("400.00")),
        ("2T", Decimal("6000.00"), Decimal("420.00")),
        ("3T", Decimal("6000.00"), Decimal("460.00")),
        ("4T", Decimal("7000.00"), Decimal("160.00")),
    )
}


def product_software_identity() -> AeatProductSoftwareIdentity:
    """Test product identity supplied to every export in the M303-to-M390 vertical."""
    return AeatProductSoftwareIdentity(
        program_identifier="C303",
        developer_tax_id="Y0001006P",
        evidence=(
            AeatProductSoftwareEvidence(
                reference="aeat-software-registration:e2e-ledger-m303-m390",
                digest="a" * 64,
            ),
        ),
    )


def transaction_booked_date(period: str, *, filing_year: int = YEAR) -> date:
    """The date :func:`iva_transaction` books a row of ``period`` on: a quarter's middle month or the month itself."""
    month = _QUARTER_MONTH[period] if period in _QUARTER_MONTH else int(period)
    return date(filing_year, month, 10)


def iva_transaction(
    provider_id: str,
    *,
    direction: TransactionDirection,
    taxable_base: Decimal,
    iva_amount: Decimal,
    period: str,
    filing_year: int = YEAR,
    iva_rate: Decimal = _IVA_RATE,
    amount: Decimal | None = None,
    iva_category: IvaCategory | None = None,
    counterparty_country: str | None = None,
    counterparty_identification_state: EUMemberState | None = None,
    purchase_invoice_evidence_id: str | None = None,
    deduction_fact_kind: IvaDeductionFactKind | None = None,
    deduction_provenance: IvaDeductionClassificationProvenance | None = None,
    paid_invoice_id: str | None = None,
) -> Transaction:
    """Book one ledger movement of ``period``.

    With ``paid_invoice_id`` the movement is that invoice's payment: it pays
    base plus cuota and states no IVA figures of its own, because the invoice
    is the IVA source and the movement only its payment evidence. Its deduction
    classification stays, as the invoice's deduction authority.
    """
    booked = transaction_booked_date(period, filing_year=filing_year)
    payload: dict[str, object] = {
        "raw": RawTransaction(
            provider_transaction_id=provider_id,
            booked_date=booked,
            value_date=booked,
            amount=amount if amount is not None else taxable_base + iva_amount,
            currency="EUR",
            counterparty="Cliente o proveedor",
            description=f"factura IVA {provider_id}",
            provenance=RawProvenance(
                source_path=Path(__file__),
                source_sha256="c" * 64,
                source_row_index=1,
                source_format=SourceFormat.MANUAL,
                ingested_at=T0,
                provider_name="manual-ledger",
            ),
            raw_fields={"source_kind": "ledger_transaction"},
        ),
        "direction": direction,
        "business_classification": BusinessClassification.BUSINESS,
        "source_jurisdiction": "ES",
        "group_label": None,
        "category_id": "material_oficina",
        "classified_at": T0,
        "classified_by": "manual",
    }
    if paid_invoice_id is None:
        payload.update({"taxable_base": taxable_base, "iva_rate": iva_rate, "iva_amount": iva_amount})
    else:
        payload["invoice_id"] = paid_invoice_id
    if iva_category is not None:
        payload["iva_category"] = iva_category
    if counterparty_country is not None:
        payload["counterparty_country"] = counterparty_country
    if counterparty_identification_state is not None:
        payload["counterparty_identification_state"] = counterparty_identification_state
    if purchase_invoice_evidence_id is not None:
        payload["purchase_invoice_evidence_id"] = purchase_invoice_evidence_id
    if deduction_fact_kind is not None:
        payload["deduction_fact_kind"] = deduction_fact_kind
    if deduction_provenance is not None:
        payload["deduction_provenance"] = deduction_provenance
    return Transaction.model_validate(payload)


def persist_year_of_invoices(
    secure_objects: SecureObjectRepository,
    *,
    filing_year: int = YEAR,
    facts_by_period: dict[str, dict[str, Decimal]] = _LAURA_QUARTER_FACTS,
    received_rate_percent: Decimal = Decimal("21"),
) -> StoredIvaByPeriod:
    """Persist all four quarters' issued + received IVA operations once upfront.

    Each M303 quarter's bucket aggregation selects only its own period's
    operations by date (IVA is declared per period, not cumulative-YTD), so the
    whole year is persisted once and the per-quarter window does the slicing.

    Returns, per period, the IVA amounts actually STORED on the persisted
    transactions (``devengada`` = issued invoice's ``iva_amount``, ``deducible``
    = received invoice's ``iva_amount``). The caller asserts the engine-computed
    M303 totals against these stored field values — proving the aggregator
    transports the stored ``iva_amount`` rather than re-deriving base×rate, and
    avoiding a shared-literal between the seed and the expectation.
    """
    transactions: list[Transaction] = []
    purchase_invoices = []
    stored: StoredIvaByPeriod = {}
    catalogue_ports = build_catalogue_creation_ports(bucket_id=BUCKET_ID)
    for period, facts in facts_by_period.items():
        purchase_invoice = build_catalogue_invoice(
            bucket_id=BUCKET_ID,
            kind=InvoiceKind.RECEIVED,
            counterparty_name="Proveedor Taller SL",
            counterparty_tax_id="B00010157",
            counterparty_country="ES",
            invoice_number=f"REC-{filing_year}-{period}",
            issued_at=date(filing_year, _QUARTER_MONTH[period], 10),
            taxable_base=facts["received_base"],
            iva_rate=received_rate_percent,
            currency="EUR",
            rate_provider=catalogue_ports.rate_provider,
        )
        purchase_invoices.append(purchase_invoice)
        issued = iva_transaction(
            f"sale-{period}",
            direction=TransactionDirection.INCOMING,
            taxable_base=facts["issued_base"],
            iva_amount=facts["issued_iva"],
            period=period,
            filing_year=filing_year,
        )
        received = iva_transaction(
            f"purchase-{period}",
            direction=TransactionDirection.OUTGOING,
            taxable_base=facts["received_base"],
            iva_amount=facts["received_iva"],
            period=period,
            filing_year=filing_year,
            iva_rate=received_rate_percent / Decimal("100"),
            purchase_invoice_evidence_id=purchase_invoice.invoice_id,
            # The received invoice is the IVA source (LIVA art. 97, RIVA
            # art. 99); this movement is its payment, linked on both records.
            paid_invoice_id=purchase_invoice.invoice_id,
            # Domestic purchase from an ES supplier: cuota soportada established
            # by that supplier's invoice (LIVA art. 97.Uno.1).
            deduction_fact_kind=IvaDeductionFactKind.from_registry("domestic_current"),
            deduction_provenance=IvaDeductionClassificationProvenance(
                authority=IvaDeductionEvidenceAuthority.from_registry("invoice_evidence"),
                source_locator=f"invoice:{purchase_invoice.invoice_id}",
                evidence_digest="a" * 64,
            ),
        )
        purchase_invoices[-1] = purchase_invoice.model_copy(
            update={"linked_transaction_ids": (received.transaction_id,)}
        )
        transactions.extend((issued, received))
        devengada = facts["issued_iva"]
        deducible = facts["received_iva"]
        if facts["eu_supply_base"] > Decimal("0"):
            transactions.append(
                iva_transaction(
                    f"eu-supply-{period}",
                    direction=TransactionDirection.INCOMING,
                    taxable_base=facts["eu_supply_base"],
                    iva_amount=Decimal("0.00"),
                    iva_rate=Decimal("0.00"),
                    period=period,
                    filing_year=filing_year,
                    iva_category=IvaCategory("intra_community_supply"),
                    # Established in Germany AND IVA-identified there. Art. 25
                    # exempts an intra-community supply on the acquirer's
                    # IDENTIFICATION, not on establishment, so declaring only the
                    # country leaves the ledger preflight correctly refusing:
                    # "requiere el Estado miembro en el que la contraparte esta
                    # identificada a efectos del IVA". The two are separate facts
                    # and a real filer supplies the second via
                    # `aeat app ledger classify --counterparty-identification-state`.
                    counterparty_country="DE",
                    counterparty_identification_state=require_eu_member_state("DE"),
                ),
            )
        if facts["reverse_charge_base"] > Decimal("0"):
            transactions.append(
                iva_transaction(
                    f"reverse-charge-{period}",
                    direction=TransactionDirection.OUTGOING,
                    taxable_base=facts["reverse_charge_base"],
                    iva_amount=facts["reverse_charge_iva"],
                    amount=facts["reverse_charge_base"],
                    period=period,
                    filing_year=filing_year,
                    iva_category=IvaCategory("domestic_reverse_charge"),
                    # Inversion del sujeto pasivo on a DOMESTIC supply (LIVA
                    # art. 84.Uno.2): the recipient self-repercutes, but the
                    # deduction family stays domestic and the establishing
                    # evidence is the supplier's invoice, NOT an intra-EU
                    # self-assessment.
                    deduction_fact_kind=IvaDeductionFactKind.from_registry("domestic_current"),
                    deduction_provenance=IvaDeductionClassificationProvenance(
                        authority=IvaDeductionEvidenceAuthority.from_registry("invoice_evidence"),
                        source_locator=f"invoice:reverse-charge-{filing_year}-{period}",
                        evidence_digest="b" * 64,
                    ),
                ),
            )
            devengada += facts["reverse_charge_iva"]
            deducible += facts["reverse_charge_iva"]
        stored[period] = {
            "devengada": devengada,
            "deducible": deducible,
            "casilla_59": facts["eu_supply_base"],
            "resultado": devengada - deducible,
        }
    tx_repo = TransactionCatalogueRepository(bucket_id=BUCKET_ID, objects=secure_objects)
    tx_repo.save(TransactionCatalogue.from_transactions(tuple(transactions)))
    InvoiceCatalogueRepository(objects=secure_objects).save(build_invoice_catalogue(tuple(purchase_invoices)))
    return stored


#: A round cuota scenarios book; its 21 % base 4761.90 rounds back to it (4761.90 x 0.21 = 999.999).
M303_LEDGER_CUOTA = Decimal("1000.00")
_M303_PERIOD_CUOTA_RATE = Decimal("0.21")


def _m303_period_cuota_base(cuota: Decimal) -> Decimal:
    """The 21 % base, to the cent, whose cuota rounds to ``cuota``."""
    return (cuota / _M303_PERIOD_CUOTA_RATE).quantize(Decimal("0.01"))


def seed_m303_period_cuotas(
    work_unit_id: str,
    *,
    repercutido: Decimal = Decimal("0.00"),
    soportado: Decimal = Decimal("0.00"),
) -> None:
    """Record one domestic 21 % sale and/or purchase in the work unit's quarter.

    ``repercutido`` and ``soportado`` are 21 % cuotas, zero for no row. The
    purchase is the payment of its supplier invoice, which is the IVA source and
    the evidence a deduction needs (LIVA art. 97.Uno.1); the two records name
    each other. A quarter already holding its row is left as it is, so a
    recalculation reads the same ledger.
    """
    work_unit = WorkUnitCatalogueRepository().load().work_units[work_unit_id]
    quarter = work_unit.period.registry_token
    year = work_unit.filing_year
    ledger = TransactionCatalogueRepository(bucket_id=work_unit.bucket_id)
    stored = tuple(ledger.load().transactions.values())
    present = {transaction.raw.provider_transaction_id for transaction in stored}
    transactions = []
    if repercutido and f"wallet-sale-{year}-{quarter}" not in present:
        transactions.append(
            iva_transaction(
                f"wallet-sale-{year}-{quarter}",
                direction=TransactionDirection.INCOMING,
                taxable_base=_m303_period_cuota_base(repercutido),
                iva_amount=repercutido,
                period=quarter,
                filing_year=year,
            )
        )
    if soportado and f"wallet-purchase-{year}-{quarter}" not in present:
        catalogue_ports = build_catalogue_creation_ports(bucket_id=work_unit.bucket_id)
        purchase_invoice = build_catalogue_invoice(
            bucket_id=work_unit.bucket_id,
            kind=InvoiceKind.RECEIVED,
            counterparty_name="Proveedor Taller SL",
            counterparty_tax_id="B00010157",
            counterparty_country="ES",
            invoice_number=f"WALLET-REC-{year}-{quarter}",
            issued_at=transaction_booked_date(quarter, filing_year=year),
            taxable_base=_m303_period_cuota_base(soportado),
            iva_rate=Decimal("21"),
            currency="EUR",
            rate_provider=catalogue_ports.rate_provider,
        )
        purchase = iva_transaction(
            f"wallet-purchase-{year}-{quarter}",
            direction=TransactionDirection.OUTGOING,
            taxable_base=_m303_period_cuota_base(soportado),
            iva_amount=soportado,
            period=quarter,
            filing_year=year,
            purchase_invoice_evidence_id=purchase_invoice.invoice_id,
            paid_invoice_id=purchase_invoice.invoice_id,
            deduction_fact_kind=IvaDeductionFactKind.from_registry("domestic_current"),
            deduction_provenance=IvaDeductionClassificationProvenance(
                authority=IvaDeductionEvidenceAuthority.from_registry("invoice_evidence"),
                source_locator=f"invoice:{purchase_invoice.invoice_id}",
                evidence_digest="a" * 64,
            ),
        )
        invoices = InvoiceCatalogueRepository()
        invoices.save(
            build_invoice_catalogue(
                (
                    *invoices.load().invoices.values(),
                    purchase_invoice.model_copy(update={"linked_transaction_ids": (purchase.transaction_id,)}),
                )
            )
        )
        transactions.append(purchase)
    if transactions:
        ledger.save(TransactionCatalogue.from_transactions((*stored, *transactions)))

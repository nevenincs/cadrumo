"""One accumulative invoice life drives Modelo 303/390 and Modelo 130/100 together.

Two established e2e verticals each prove ONE modelo pair independently:
``test_e2e_ledger_m303_quarters_to_m390_annual`` (ledger IVA -> four M303
quarters -> M390 annual reconciliation) and
``test_e2e_ledger_m130_quarters_to_m100_annual`` (ledger income -> four M130
quarters -> M100 annual 0604 fold-in). Neither drives an actual persisted
:class:`~cadrumo.domain.invoices.Invoice` -- the IVA vertical uses bare ledger
transactions, and the income vertical uses transactions with no invoice
substrate at all. Neither proves that ONE real invoice's economic content
reaches BOTH modelo families from a single filed operation, or that the same
operation cannot leak into, or duplicate across, more than one period on
either side.

This module closes that joint: for each of four quarters, one issued invoice
(the taxpayer's own sale) is persisted and bidirectionally linked to one
ledger transaction dated in the same quarter. That single transaction is the
one substrate BOTH modelo families read: its ``iva_amount`` feeds the M303
cuota-devengada aggregation (``ledger_iva_aggregation``), and its
``taxable_base`` -- via the invoice link -- feeds the M130 casilla-01 income
aggregation (``ledger_renta_income_aggregation``). The four quarters are
calculated and filed for BOTH families, then M390 and M100 are calculated
annually.

Non-tautology argument, in two layers:

* Transport invariants (matching the two precedent verticals' own style): each
  quarter's engine-computed M303/M130 casillas equal the STORED transaction
  field values, never a re-derived base*rate; the annual M390/M100 fold equals
  the SUM of the four engine-computed quarterly values.
* An INDEPENDENT anti-duplication check the precedents do not perform: the
  annual totals are also compared against the sum of the INVOICES' OWN
  declared base/IVA figures -- data recorded before any calculation ran,
  entirely outside the engine. If an invoice's contribution ever leaked into
  two quarters, the per-quarter transport-invariant assertions would already
  fail for the inflated quarter; if it were duplicated identically (the
  harder case, mirroring ``test_the_cuota_is_declared_exactly_once_across_the_year``),
  the annual-vs-invoice-total check catches it even though the annual-vs-
  sum-of-quarters check alone would still (wrongly) agree.

Real-behaviour, real-adapter: real encrypted-SQLite secure store, the real
registry authority, the real calculation engine, and the real bidirectional
invoice/transaction link. No mocks, stubs, skips, or xfail.
"""

from __future__ import annotations

from datetime import UTC, date, datetime
from decimal import Decimal
from pathlib import Path

import pytest

from ....adapters.persistence.profile.invoices import InvoiceCatalogueRepository
from ....adapters.persistence.profile.modelos_calculation import CalculationRevisionCatalogueRepository
from ....adapters.persistence.profile.modelos_work_units import WorkUnitCatalogueRepository
from ....adapters.persistence.profile.transactions import TransactionCatalogueRepository
from ....adapters.persistence.storage.sql import SecureObjectRepository
from ....core.period import Period
from ....core.casilla_id import CasillaId, validated_casilla_id
from ....domain.calculations.registry.authority import bundled_authority
from ....domain.calculations.registry.bindings import RegistryModeloObservation
from ....domain.calculations.registry.ids import BindingId
from ....domain.invoices.models import InvoiceCatalogue
from ....domain.iva.classification import InvoiceKind
from ....domain.iva.schema import IvaCategory
from ....domain.iva_compensation.reconciliation import IvaCompensationReconciliationDecision
from ....domain.modelos.calculation_revision import CalculationRevision
from ....domain.transactions.enums import BusinessClassification, TransactionDirection
from ....domain.transactions.models import Transaction, TransactionCatalogue
from ....domain.transactions.raw_transaction import RawProvenance, RawTransaction, SourceFormat
from ....domain.user_profile.values import ProfileSetupState, UserProfileFact, UserProfileRecord
from ....tests import general_m303_filing_evidence
from ....tests.profile_capsule import seed_test_profile_record
from ....tests.registry_observations import registry_grounded_observations
from ...calculations import CalculationObservationRepository, IvaWalletDecisionRepository
from ...invoices import build_catalogue_invoice, link_invoice_transaction_catalogues
from ...modelo._calculation_actions import calculate_modelo_revision_from_bucket_aggregation
from ...modelo._filed_revision_observation import persist_filed_revision_observation
from ...modelo._m303_regimen_simplificado_scope import active_taxpayer_profile
from ...modelo._result_disposition_resolution import resolve_modelo_result_disposition
from ...modelo.work_lifecycle import create_work_unit

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_BUCKET_ID = "13049000-0000-4000-8000-000000000049"
_TAX_ID = "12345678Z"
_YEAR = 2024
_PRIOR_YEAR = _YEAR - 1
_T0 = datetime(_YEAR, 1, 10, 10, 0, tzinfo=UTC)
_FILE_AT = datetime(_YEAR, 4, 6, 12, 0, tzinfo=UTC)

_QUARTER_ORDER = ("1T", "2T", "3T", "4T")
_QUARTER_MONTH: dict[str, int] = {"1T": 2, "2T": 5, "3T": 8, "4T": 11}
_IVA_RATE = Decimal("0.21")

# One issued invoice per quarter, each a distinct base so a cross-quarter leak
# or duplication cannot hide behind a repeated figure.
_QUARTER_INVOICE_BASE: dict[str, Decimal] = {
    "1T": Decimal("5000.00"),
    "2T": Decimal("6000.00"),
    "3T": Decimal("4000.00"),
    "4T": Decimal("7000.00"),
}
_QUARTER_INVOICE_IVA: dict[str, Decimal] = {
    period: (base * _IVA_RATE).quantize(Decimal("0.01")) for period, base in _QUARTER_INVOICE_BASE.items()
}
# Independent (non-engine-derived) annual totals: the sum of what the
# invoices themselves declare, computed once here from the fixture data
# rather than re-read from any calculation output.
_EXPECTED_ANNUAL_BASE = sum(_QUARTER_INVOICE_BASE.values(), Decimal("0"))
_EXPECTED_ANNUAL_IVA = sum(_QUARTER_INVOICE_IVA.values(), Decimal("0"))
_EXPECTED_CUMULATIVE_BASE: dict[str, Decimal] = {
    "1T": Decimal("5000.00"),
    "2T": Decimal("11000.00"),
    "3T": Decimal("15000.00"),
    "4T": Decimal("22000.00"),
}

# High enough that the M130 casilla-13 minoración (bounded by the prior-year
# actividad-económica net income) resolves to zero, keeping each quarter's
# casilla 19 the clean incremental pago fraccionado -- the same device
# ``test_e2e_ledger_m130_quarters_to_m100_annual`` uses.
_PRIOR_YEAR_NET_INCOME = Decimal("50000")

_M303_DEVENGADA_TOTAL: CasillaId = validated_casilla_id("iva.cuota-devengada-total", surface="test casilla id")
_M303_RESULTADO: CasillaId = validated_casilla_id("iva.resultado-regimen-general", surface="test casilla id")
_M390_DEVENGADA: CasillaId = validated_casilla_id(
    "iva.anual.reconciliacion.devengada-303",
    surface="test casilla id",
)
_M390_RESULTADO: CasillaId = validated_casilla_id(
    "iva.anual.reconciliacion.resultado-303",
    surface="test casilla id",
)
_M130_INGRESOS_CASILLA: CasillaId = validated_casilla_id("01", surface="test casilla id")
_M130_RESULTADO_FINAL_CASILLA: CasillaId = validated_casilla_id("19", surface="test casilla id")
_M100_PAGOS_CASILLA: CasillaId = validated_casilla_id("0604", surface="test casilla id")
_M100_ACTIVITY_INCOME_CASILLA: CasillaId = validated_casilla_id("0171", surface="test casilla id")
_M100_ACTIVIDAD_ECONOMICA_NET_INCOME_CASILLA: CasillaId = validated_casilla_id("0224", surface="test casilla id")
_M100_RENDIMIENTO_SOURCE_1479_CASILLA: CasillaId = validated_casilla_id("1479", surface="test casilla id")
_M100_RENDIMIENTO_SOURCE_1553_CASILLA: CasillaId = validated_casilla_id("1553", surface="test casilla id")
_M100_RENDIMIENTO_SOURCE_1577_CASILLA: CasillaId = validated_casilla_id("1577", surface="test casilla id")
_M100_BASE_LIQUIDABLE_NEGATIVA_GENERAL_CASILLA: CasillaId = validated_casilla_id("1391", surface="test casilla id")
_M100_ESTIMACION_DIRECTA_NORMAL_BINDING: BindingId = f"renta-{_YEAR}-modelo-100-estimacion-directa-es-normal"

# M130 manual casillas (retenciones / agrarian / vivienda / prior
# autoliquidaciones). All zero: this persona files no other income and has no
# prior-year M130 result to net.
_M130_MANUAL_INPUTS: dict[CasillaId, Decimal] = {
    validated_casilla_id("06", surface="test casilla id"): Decimal("0"),
    validated_casilla_id("08", surface="test casilla id"): Decimal("0"),
    validated_casilla_id("10", surface="test casilla id"): Decimal("0"),
    validated_casilla_id("16", surface="test casilla id"): Decimal("0"),
    validated_casilla_id("18", surface="test casilla id"): Decimal("0"),
}

# Manual, formula-operand M303 "resultado" casillas the engine never
# auto-zero-fills (an unset manual input is simply absent from
# ``casilla_values``, not defaulted); mirrors the shared M303 export fixture's
# ``_MODELO_303_MANUAL_RESULTADO_CASILLA_ZEROS`` without a cross-package import
# into a sibling test package's private support module.
# Casilla 18 is NOT listed: the recargo de equivalencia super-reducido cuota
# is bound to the ledger IVA aggregation, which owns it on this path. A
# caller zero would override a source-derived liability, so the bucket
# aggregation refuses it. The scenario declares no recargo supply, so the
# resolver supplies the same zero from the ledger.
_M303_MANUAL_RESULTADO_CASILLA_ZEROS: dict[str, Decimal] = {
    "58": Decimal("0.00"),
    "68": Decimal("0.00"),
    "70": Decimal("0.00"),
    "76": Decimal("0.00"),
    "77": Decimal("0.00"),
    "109": Decimal("0.00"),
}


def _seed_taxpayer_profile() -> None:
    """Seed the one taxpayer profile both M303 and M100/M130 bindings read."""
    seed_test_profile_record(
        UserProfileRecord(
            setup_state=ProfileSetupState.COMPLETE,
            profile_id=_BUCKET_ID,
            facts=(
                UserProfileFact(path="identity.tax_id", value=_TAX_ID),
                UserProfileFact(path="identity.name", value="Marta"),
                UserProfileFact(path="identity.surnames", value="Invoice Life"),
                UserProfileFact(path="activities.description", value="design services"),
                UserProfileFact(path="tax_residence.ccaa", value="madrid"),
                UserProfileFact(path="tax_residence.jurisdiction_scope", value="common_regime"),
                UserProfileFact(path="iva.regime", value="GENERAL"),
                UserProfileFact(path="iva.m303_regime_composition", value="general"),
                UserProfileFact(path="iva.redeme_enrolled", value=False),
                UserProfileFact(path="iva.cash_accounting_regime_enrolled", value=False),
                UserProfileFact(path="iva.voluntary_sii_enrolled", value=False),
                UserProfileFact(path="iva.hydrocarbon_deposit_advance_payment_deduction_entitled", value=False),
                UserProfileFact(path="taxpayer_type.entity_type", value="natural_person"),
                UserProfileFact(path="taxpayer_type.irpf_income_categories", value="actividad_economica"),
                UserProfileFact(path="irpf.estimation_regime", value="directa_normal"),
                UserProfileFact(path="censo.activity_start_date", value=date(_YEAR, 1, 1)),
                UserProfileFact(path="renta_taxpayer.birth_date", value=date(1985, 6, 1)),
                UserProfileFact(path="renta_taxpayer.sex", value="M"),
                UserProfileFact(path="renta_taxpayer.marital_status", value="1"),
                UserProfileFact(path="renta_taxpayer.marriage_full_year", value=Decimal("0")),
                UserProfileFact(path="renta_taxpayer.marriage_month_start", value=Decimal("0")),
                UserProfileFact(path="renta_taxpayer.marriage_month_end", value=Decimal("0")),
                UserProfileFact(path="renta_filing.declaration_type", value="1"),
                UserProfileFact(path="renta_family.minor_children_in_unit", value=False),
                UserProfileFact(path="renta_family.descendientes_count", value=Decimal("0")),
                UserProfileFact(path="renta_family.cotizaciones_ss_madre_2024", value=Decimal("0")),
                UserProfileFact(path="renta_family.descendants_eu_eea_deduction", value=False),
            ),
            created_at=_T0,
            updated_at=_T0,
        ),
    )


def _income_transaction(period: str) -> Transaction:
    value_date = date(_YEAR, _QUARTER_MONTH[period], 15)
    base = _QUARTER_INVOICE_BASE[period]
    iva = _QUARTER_INVOICE_IVA[period]
    return Transaction.model_validate(
        {
            "raw": RawTransaction(
                provider_transaction_id=f"sale-{period}",
                booked_date=value_date,
                value_date=value_date,
                amount=base + iva,
                currency="EUR",
                counterparty="Cliente SA",
                description=f"factura {period}",
                provenance=RawProvenance(
                    source_path=Path(__file__),
                    source_sha256="d" * 64,
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
            "iva_category": IvaCategory.DOMESTIC_GENERAL,
            "taxable_base": base,
            "iva_rate": _IVA_RATE,
            "iva_amount": iva,
            "classified_at": _T0,
            "classified_by": "manual",
        },
    )


def _persist_invoice_life(secure_objects: SecureObjectRepository) -> None:
    """Persist and bidirectionally link one issued invoice to one transaction per quarter.

    The invoice and the transaction describe the SAME sale: same period, same
    base, same IVA. The transaction is what both `ledger_iva_aggregation` (IVA)
    and `ledger_renta_income_aggregation` (income) read; the invoice link is
    what lets the income pipeline ground the row as `SUBSTRATE_DECLARED`
    rather than falling back to raw cash, and what the M303 invoice-coherence
    guard cross-checks against the ledger.
    """
    invoices = InvoiceCatalogue()
    transactions = TransactionCatalogue()
    for period in _QUARTER_ORDER:
        base = _QUARTER_INVOICE_BASE[period]
        invoice = build_catalogue_invoice(
            bucket_id=_BUCKET_ID,
            kind=InvoiceKind.ISSUED,
            counterparty_name="Cliente SA",
            counterparty_tax_id="B58818501",
            counterparty_country="ES",
            invoice_number=f"FAC-{_YEAR}-{period}",
            issued_at=date(_YEAR, _QUARTER_MONTH[period], 15),
            taxable_base=base,
            iva_rate=Decimal("21"),
            currency="EUR",
            iva_category=IvaCategory.DOMESTIC_GENERAL,
        )
        invoices = InvoiceCatalogue.model_validate({"invoices": {**invoices.invoices, invoice.invoice_id: invoice}})
        transaction = _income_transaction(period)
        transactions = TransactionCatalogue.model_validate(
            {**{t.transaction_id: t for t in transactions.values()}, transaction.transaction_id: transaction},
        )
        linked = link_invoice_transaction_catalogues(
            invoices,
            transactions,
            invoice_id=invoice.invoice_id,
            transaction_id=transaction.transaction_id,
        )
        invoices = linked.invoices
        transactions = linked.transactions

    InvoiceCatalogueRepository(bucket_id=_BUCKET_ID, objects=secure_objects).save(invoices)
    TransactionCatalogueRepository(bucket_id=_BUCKET_ID, objects=secure_objects).save(transactions)


def _seed_prior_year_m100(secure_objects: SecureObjectRepository) -> None:
    """Observe the prior-year annual Renta net-income casillas M130's minoración reads."""
    CalculationObservationRepository(objects=secure_objects).save(
        CalculationObservationRepository(objects=secure_objects).prepare_observation_envelope(
            RegistryModeloObservation(
                modelo="100",
                filing_year=_PRIOR_YEAR,
                period="0A",
                observations=registry_grounded_observations(
                    modelo="100",
                    filing_year=_PRIOR_YEAR,
                    period="0A",
                    casilla_values={
                        _M100_ACTIVIDAD_ECONOMICA_NET_INCOME_CASILLA: _PRIOR_YEAR_NET_INCOME,
                        _M100_RENDIMIENTO_SOURCE_1479_CASILLA: Decimal("0"),
                        _M100_RENDIMIENTO_SOURCE_1553_CASILLA: Decimal("0"),
                        _M100_RENDIMIENTO_SOURCE_1577_CASILLA: Decimal("0"),
                        _M100_BASE_LIQUIDABLE_NEGATIVA_GENERAL_CASILLA: Decimal("0"),
                    },
                ),
            ),
            source_kind="app_filing",
            captured_at=_FILE_AT,
        )
    )


def _wallet_decision(*, period: str) -> IvaCompensationReconciliationDecision:
    """A neutral (zero, non-blocking) IVA-wallet decision for the quarter."""
    return IvaCompensationReconciliationDecision(
        taxpayer_nif=_TAX_ID,
        target_year=_YEAR,
        target_period=Period.from_year_and_code(_YEAR, period),
        selected_authority="aeat_wallet",
        selected_amount=Decimal("0.00"),
        wallet_amount=Decimal("0.00"),
        local_recurrence_amount=Decimal("0.00"),
        override_amount=None,
        divergence="match",
        blocked=False,
        stale_wallet=False,
        reason_identity="aeat_wallet_validated",
        wallet_captured_at=_FILE_AT,
        decided_at=_FILE_AT,
    )


def _calculate_and_file_m303_quarter(secure_objects: SecureObjectRepository, *, period: str) -> CalculationRevision:
    wu_repo = WorkUnitCatalogueRepository(objects=secure_objects)
    cr_repo = CalculationRevisionCatalogueRepository(objects=secure_objects)
    tx_repo = TransactionCatalogueRepository(bucket_id=_BUCKET_ID, objects=secure_objects)
    invoice_repo = InvoiceCatalogueRepository(bucket_id=_BUCKET_ID, objects=secure_objects)
    snapshot = bundled_authority().snapshot("303", filing_year=_YEAR, period=period)
    work_unit = create_work_unit(
        bucket_id=_BUCKET_ID,
        modelo="303",
        filing_year=_YEAR,
        period=Period.from_year_and_code(_YEAR, period),
        revision_id=snapshot.revision.id,
        repository=wu_repo,
        clock=_T0,
    )
    decision = _wallet_decision(period=period)
    IvaWalletDecisionRepository(objects=secure_objects).save_decision(decision)
    revision = calculate_modelo_revision_from_bucket_aggregation(
        work_unit.work_unit_id,
        casilla_inputs=dict(_M303_MANUAL_RESULTADO_CASILLA_ZEROS),
        binding_values={
            "modelo-303-compensacion-pendiente-anteriores": Decimal("0.00"),
            "modelo-303-autoconsumo-promotor-base": Decimal("0.00"),
        },
        iva_compensation_decision=decision,
        work_unit_repository=wu_repo,
        calculation_repository=cr_repo,
        transaction_repository=tx_repo,
        invoice_repository=invoice_repo,
        clock=_FILE_AT,
        filing_instance_evidence=general_m303_filing_evidence(
            work_unit.period, reference="test:invoice-accumulative-cross-modelo"
        ),
    )
    # A Modelo 303 filing carries a resolved result disposition. Resolve it
    # through the production boundary against the seeded profile rather than
    # asserting one here: the disposition is a regulated determination and a
    # second derivation in a test would be a second authority on it.
    persist_filed_revision_observation(
        revision=revision,
        work_unit=work_unit,
        repository=CalculationObservationRepository(objects=secure_objects),
        captured_at=_FILE_AT,
        result_disposition=resolve_modelo_result_disposition(
            work_unit=work_unit,
            revision=revision,
            workflow_profile=active_taxpayer_profile(work_unit),
            period=work_unit.period,
        ),
    )
    return revision


def _calculate_m390_annual(secure_objects: SecureObjectRepository) -> CalculationRevision:
    wu_repo = WorkUnitCatalogueRepository(objects=secure_objects)
    cr_repo = CalculationRevisionCatalogueRepository(objects=secure_objects)
    tx_repo = TransactionCatalogueRepository(bucket_id=_BUCKET_ID, objects=secure_objects)
    invoice_repo = InvoiceCatalogueRepository(bucket_id=_BUCKET_ID, objects=secure_objects)
    snapshot = bundled_authority().snapshot("390", filing_year=_YEAR, period="0A")
    work_unit = create_work_unit(
        bucket_id=_BUCKET_ID,
        modelo="390",
        filing_year=_YEAR,
        period=Period.from_year_and_code(_YEAR, "0A"),
        revision_id=snapshot.revision.id,
        repository=wu_repo,
        clock=_T0,
    )
    return calculate_modelo_revision_from_bucket_aggregation(
        work_unit.work_unit_id,
        binding_values={},
        work_unit_repository=wu_repo,
        calculation_repository=cr_repo,
        transaction_repository=tx_repo,
        invoice_repository=invoice_repo,
        clock=_FILE_AT,
    )


def _calculate_and_file_m130_quarter(secure_objects: SecureObjectRepository, *, period: str) -> CalculationRevision:
    wu_repo = WorkUnitCatalogueRepository(objects=secure_objects)
    cr_repo = CalculationRevisionCatalogueRepository(objects=secure_objects)
    tx_repo = TransactionCatalogueRepository(bucket_id=_BUCKET_ID, objects=secure_objects)
    invoice_repo = InvoiceCatalogueRepository(bucket_id=_BUCKET_ID, objects=secure_objects)
    snapshot = bundled_authority().snapshot("130", filing_year=_YEAR, period=period)
    work_unit = create_work_unit(
        bucket_id=_BUCKET_ID,
        modelo="130",
        filing_year=_YEAR,
        period=Period.from_year_and_code(_YEAR, period),
        revision_id=snapshot.revision.id,
        repository=wu_repo,
        clock=_T0,
    )
    revision = calculate_modelo_revision_from_bucket_aggregation(
        work_unit.work_unit_id,
        casilla_inputs=_M130_MANUAL_INPUTS,
        work_unit_repository=wu_repo,
        calculation_repository=cr_repo,
        transaction_repository=tx_repo,
        invoice_repository=invoice_repo,
        clock=_T0,
    )
    persist_filed_revision_observation(
        revision=revision,
        work_unit=work_unit,
        repository=CalculationObservationRepository(objects=secure_objects),
        captured_at=_FILE_AT,
    )
    return revision


def _m100_non_relation_zero_bindings(secure_objects: SecureObjectRepository) -> dict[BindingId, Decimal]:
    """Zero-default every M100 binding that is neither profile- nor relation-sourced."""
    del secure_objects
    snapshot = bundled_authority().snapshot("100", filing_year=_YEAR, period="0A")
    values = {
        binding.id: Decimal("0")
        for binding in snapshot.revision.bindings
        if binding.source
        not in (
            "profile",
            "relation_prefill",
            "ledger_renta_income_aggregation",
            "ledger_renta_gastos_estimacion_directa_aggregation",
            "ledger_iva_aggregation",
            "ledger_oss_aggregation",
            "collectible_invoice",
            "payable_invoice",
        )
    }
    values[_M100_ESTIMACION_DIRECTA_NORMAL_BINDING] = Decimal("1")
    return values


def _calculate_m100_annual(secure_objects: SecureObjectRepository) -> CalculationRevision:
    wu_repo = WorkUnitCatalogueRepository(objects=secure_objects)
    cr_repo = CalculationRevisionCatalogueRepository(objects=secure_objects)
    tx_repo = TransactionCatalogueRepository(bucket_id=_BUCKET_ID, objects=secure_objects)
    invoice_repo = InvoiceCatalogueRepository(bucket_id=_BUCKET_ID, objects=secure_objects)
    snapshot = bundled_authority().snapshot("100", filing_year=_YEAR, period="0A")
    work_unit = create_work_unit(
        bucket_id=_BUCKET_ID,
        modelo="100",
        filing_year=_YEAR,
        period=Period.from_year_and_code(_YEAR, "0A"),
        revision_id=snapshot.revision.id,
        repository=wu_repo,
        clock=_T0,
    )
    return calculate_modelo_revision_from_bucket_aggregation(
        work_unit.work_unit_id,
        binding_values=_m100_non_relation_zero_bindings(secure_objects),
        work_unit_repository=wu_repo,
        calculation_repository=cr_repo,
        transaction_repository=tx_repo,
        invoice_repository=invoice_repo,
        clock=_T0,
    )


def test_one_invoice_life_lands_in_one_period_on_both_modelo_pairs(
    secure_objects: SecureObjectRepository,
) -> None:
    """A quarterly invoice's IVA and income reach both M390 and M100 exactly once, in one period each."""
    _seed_taxpayer_profile()
    _persist_invoice_life(secure_objects)
    _seed_prior_year_m100(secure_objects)

    computed_m303: dict[str, Decimal] = {}
    computed_m130: dict[str, Decimal] = {}
    for period in _QUARTER_ORDER:
        m303_revision = _calculate_and_file_m303_quarter(secure_objects, period=period)
        # Transport invariant: the quarter's engine-computed cuota-devengada
        # equals THAT invoice/transaction's own stored IVA -- not a
        # neighbouring quarter's, and not a re-derived base*rate.
        assert Decimal(m303_revision.casilla_values[_M303_DEVENGADA_TOTAL]) == _QUARTER_INVOICE_IVA[period], (
            f"{period}: cuota-devengada-total must equal that quarter's invoice IVA "
            f"{_QUARTER_INVOICE_IVA[period]}; got {m303_revision.casilla_values.get(_M303_DEVENGADA_TOTAL)}"
        )
        assert Decimal(m303_revision.casilla_values[_M303_RESULTADO]) == _QUARTER_INVOICE_IVA[period]
        computed_m303[period] = Decimal(m303_revision.casilla_values[_M303_RESULTADO])

        m130_revision = _calculate_and_file_m130_quarter(secure_objects, period=period)
        # Transport invariant: casilla 01 is the CUMULATIVE-YTD sum of the
        # persisted invoices' own bases through this quarter.
        assert Decimal(m130_revision.casilla_values[_M130_INGRESOS_CASILLA]) == _EXPECTED_CUMULATIVE_BASE[period], (
            f"{period}: casilla 01 must equal cumulative invoice base "
            f"{_EXPECTED_CUMULATIVE_BASE[period]}; got {m130_revision.casilla_values.get(_M130_INGRESOS_CASILLA)}"
        )
        computed_m130[period] = Decimal(m130_revision.casilla_values[_M130_RESULTADO_FINAL_CASILLA])

    # Anti-duplication (matches the precedent verticals' own discipline): four
    # distinct, strictly positive per-quarter results. A row leaking into, or
    # repeating across, an adjacent quarter would collapse this set.
    assert len(set(computed_m303.values())) == 4, f"quarterly M303 resultado must be distinct: {computed_m303}"
    assert len(set(computed_m130.values())) == 4, f"quarterly M130 c19 must be distinct: {computed_m130}"
    assert all(value > Decimal("0") for value in computed_m130.values()), computed_m130

    annual_390 = _calculate_m390_annual(secure_objects)
    annual_100 = _calculate_m100_annual(secure_objects)

    # Transport invariant: M390's annual reconciliation folds the SUM of the
    # four engine-computed M303 quarters.
    expected_390 = sum(computed_m303.values(), Decimal("0"))
    assert Decimal(annual_390.casilla_values[_M390_DEVENGADA]) == expected_390
    assert Decimal(annual_390.casilla_values[_M390_RESULTADO]) == expected_390

    # INDEPENDENT anti-duplication check: the annual M390 total also equals
    # the sum of what the invoices themselves declared, computed BEFORE any
    # calculation ran and never re-read from an engine output. A defect that
    # duplicated one invoice identically across two quarters would still
    # satisfy "annual == sum(quarters)" (both sides double) but would NOT
    # satisfy this independent check.
    assert Decimal(annual_390.casilla_values[_M390_DEVENGADA]) == _EXPECTED_ANNUAL_IVA
    assert Decimal(annual_390.casilla_values[_M390_RESULTADO]) == _EXPECTED_ANNUAL_IVA

    # Transport invariant: M100's 0604 folds the SUM of the four
    # engine-computed M130 casilla-19 values.
    expected_0604 = sum(computed_m130.values(), Decimal("0"))
    assert Decimal(annual_100.casilla_values[_M100_PAGOS_CASILLA]) == expected_0604

    # INDEPENDENT anti-duplication check at the income-base level: the
    # annual activity-income casilla equals the invoices' own declared annual
    # base total, not a re-summed engine figure.
    assert Decimal(annual_100.casilla_values[_M100_ACTIVITY_INCOME_CASILLA]) == _EXPECTED_ANNUAL_BASE
    assert Decimal(annual_100.casilla_values[_M100_ACTIVIDAD_ECONOMICA_NET_INCOME_CASILLA]) == _EXPECTED_ANNUAL_BASE

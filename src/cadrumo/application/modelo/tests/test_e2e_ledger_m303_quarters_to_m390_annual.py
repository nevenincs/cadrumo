"""E2E vertical: real ledger → M303 1T-4T (computed) → M390 annual reconciliation.

The IVA counterpart of ``test_e2e_ledger_m130_quarters_to_m100_annual``. Two
segments are each covered in isolation today:

* ledger IVA transactions → M303 computed cuota
  (``test_bucket_aggregation_flow``, a single quarter).
* M303 quarter totals → M390 annual reconciliation fold-in
  (``test_modelo_390_303_fold_in_live``, but with **injected** M303 observations,
  not values the M303 calc actually computed).

Neither joins the two: no test drives *real persisted IVA ledger transactions*
through the live bucket-aggregation calculate action for four quarters, files
each through the production observation-persistence path, and proves the annual
M390 reconciliation casillas fold in the **engine-computed** quarterly IVA totals.
That full IVA vertical — the autónomo's real yearly IVA cadence — is what this
test verifies.

Real-behaviour, real-adapter: real encrypted-SQLite secure store via
:class:`SecureObjectRepository` + ``isolated_runtime_profile``, the real registry
authority, the real calculation engine, the real ``ledger_iva_aggregation``
resolver, and the real ``relation_prefill`` fold-in resolver. No mocks, stubs,
skips, or xfail.

Non-tautology argument: each quarter's IVA totals are **computed by the engine**
from the ledger transactions' ``iva_amount`` through the M303 formula chain
(repercutido/soportado casillas → cuota-devengada-total / cuota-deducible-total →
resultado-regimen-general); the test never hand-recomputes a registry formula.
The load-bearing assertions are *transport / wiring* invariants: each quarter's
computed cuota-devengada-total equals the persisted incoming IVA the operator
never re-keyed, and the annual M390 reconciliation casillas equal the **sum of
the four engine-computed quarterly totals** (distinct per quarter, so a coincidental
or off-by-one-quarter sum cannot satisfy them).

LIVA art. 88/92 (repercusión / deducción) and the M390 orden ground the
reconciliation; this test asserts the *wiring*, leaving rate currency to the
registry grounding gate.
"""

from __future__ import annotations

from datetime import UTC, date, datetime
from decimal import Decimal
from pathlib import Path
from typing import Literal

import pytest

from ....adapters.persistence.profile.buckets import BucketEventHistoryRepository
from ....adapters.persistence.profile.invoices import InvoiceCatalogueRepository
from ....adapters.persistence.profile.modelos_calculation import CalculationRevisionCatalogueRepository
from ....adapters.persistence.profile.modelos_filing import ModeloRecordCatalogueRepository
from ....adapters.persistence.profile.modelos_verification_reports import VerificationReportCatalogueRepository
from ....adapters.persistence.profile.modelos_work_units import WorkUnitCatalogueRepository
from ....adapters.persistence.profile.transactions import TransactionCatalogueRepository
from ....adapters.persistence.storage.sql import SecureObjectRepository
from ....core import (
    CasillaId,
    IvaDeductionEvidenceAuthority,
    IvaDeductionFactKind,
    Period,
    ResultDisposition,
    validated_casilla_id,
)
from ....core.errors import CadrumoError
from ....domain.calculations.registry.authority import bundled_authority
from ....domain.deadlines import EntityType, IVARegime, LegalEntityForm, TaxpayerProfile
from ....domain.invoices import InvoiceCatalogue
from ....domain.iva import (
    EUMemberState,
    InvoiceKind,
    IvaCategory,
    IvaDeductionClassificationProvenance,
)
from ....domain.iva_compensation import IvaCompensationReconciliationDecision
from ....domain.modelos import (
    CalculationRevision,
    VerificationCompletenessStatus,
    VerificationReport,
    WorkUnit,
)
from ....domain.transactions import (
    BusinessClassification,
    RawProvenance,
    RawTransaction,
    SourceFormat,
    Transaction,
    TransactionCatalogue,
    TransactionDirection,
)
from ....domain.user_profile.values import ProfileSetupState, UserProfileFact, UserProfileRecord
from ....tests.env_scope import ready_clave_settings
from ....tests.filing_evidence import general_m303_filing_evidence
from ....tests.profile_capsule import seed_test_profile_record
from ...calculations import CalculationObservationRepository, IvaWalletDecisionRepository
from ...invoices import build_catalogue_invoice
from .._action_errors import ModeloCrossPeriodCleanStateError
from .._calculation_actions import calculate_modelo_revision_from_bucket_aggregation
from .._export import (
    ModeloExportCommand,
    ModeloExportUnsupportedError,
    export_modelo_revision,
)
from .._filed_revision_observation import persist_filed_revision_observation
from .._filing_actions import file_modelo_revision
from .._verification_actions import verify_modelo_revision
from .._work_lifecycle import create_work_unit
from ._export_modelo_303_support import _MODELO_303_MANUAL_RESULTADO_CASILLA_ZEROS

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_BUCKET_ID = "30330303-3030-4303-8303-303303303303"
_YEAR = 2025
_TAX_ID = "12345678Z"
_IRENE_YEAR = 2024
_IRENE_TAX_ID = "B12345674"
_T0 = datetime(2025, 1, 10, 10, 0, tzinfo=UTC)
_FILE_AT = datetime(2025, 4, 10, 12, 0, tzinfo=UTC)
_IRENE_FILE_AT = datetime(2026, 7, 1, 12, 0, tzinfo=UTC)

_QUARTER_ORDER = ("1T", "2T", "3T", "4T")
_IVA_RATE = Decimal("0.21")
type StoredIvaAxis = Literal["devengada", "deducible", "casilla_59", "resultado"]
type StoredIvaByPeriod = dict[str, dict[StoredIvaAxis, Decimal]]
type ComputedM303CasillasByPeriod = dict[str, dict[CasillaId, Decimal]]


# M303 computed-output casillas the M390 reconciliation relations fold.
_DEVENGADA_TOTAL: CasillaId = validated_casilla_id("iva.cuota-devengada-total")
_DEDUCIBLE_TOTAL: CasillaId = validated_casilla_id("iva.cuota-deducible-total")
_RESULTADO: CasillaId = validated_casilla_id("iva.resultado-regimen-general")
_CASILLA_59: CasillaId = validated_casilla_id("59")

# M390 annual reconciliation casillas (folded from the four M303 quarters).
_M390_DEVENGADA: CasillaId = validated_casilla_id("iva.anual.reconciliacion.devengada-303")
_M390_DEDUCIBLE: CasillaId = validated_casilla_id("iva.anual.reconciliacion.deducible-303")
_M390_RESULTADO: CasillaId = validated_casilla_id("iva.anual.reconciliacion.resultado-303")

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
_LAURA_ANNUAL_EXPECTED = {
    "devengada": Decimal("9828.00"),
    "deducible": Decimal("2163.00"),
    "resultado": Decimal("7665.00"),
}
_IRENE_QUARTER_FACTS: dict[str, dict[str, Decimal]] = {
    period: {
        "issued_base": Decimal("10000.00"),
        "issued_iva": Decimal("2100.00"),
        "received_base": Decimal("3000.00"),
        "received_iva": Decimal("630.00"),
        "eu_supply_base": Decimal("0.00"),
        "reverse_charge_base": Decimal("0.00"),
        "reverse_charge_iva": Decimal("0.00"),
    }
    for period in _QUARTER_ORDER
}
_IRENE_ANNUAL_EXPECTED = {
    "devengada": Decimal("8400.00"),
    "deducible": Decimal("2520.00"),
    "resultado": Decimal("5880.00"),
}
_QUARTER_MONTH: dict[str, int] = {"1T": 2, "2T": 5, "3T": 8, "4T": 11}


def _iva_transaction(
    provider_id: str,
    *,
    direction: TransactionDirection,
    taxable_base: Decimal,
    iva_amount: Decimal,
    period: str,
    filing_year: int = _YEAR,
    iva_rate: Decimal = _IVA_RATE,
    amount: Decimal | None = None,
    iva_category: IvaCategory | None = None,
    counterparty_country: str | None = None,
    counterparty_identification_state: EUMemberState | None = None,
    purchase_invoice_evidence_id: str | None = None,
    deduction_fact_kind: IvaDeductionFactKind | None = None,
    deduction_provenance: IvaDeductionClassificationProvenance | None = None,
) -> Transaction:
    booked = date(filing_year, _QUARTER_MONTH[period], 10)
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
                ingested_at=_T0,
                provider_name="manual-ledger",
            ),
            raw_fields={"source_kind": "ledger_transaction"},
        ),
        "direction": direction,
        "business_classification": BusinessClassification.BUSINESS,
        "source_jurisdiction": "ES",
        "group_label": None,
        "category_id": "test_iva_operation",
        "taxable_base": taxable_base,
        "iva_rate": iva_rate,
        "iva_amount": iva_amount,
        "classified_at": _T0,
        "classified_by": "manual",
    }
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


def _persist_year_of_invoices(
    secure_objects: SecureObjectRepository,
    *,
    filing_year: int = _YEAR,
    facts_by_period: dict[str, dict[str, Decimal]] = _LAURA_QUARTER_FACTS,
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
    for period, facts in facts_by_period.items():
        purchase_invoice = build_catalogue_invoice(
            bucket_id=_BUCKET_ID,
            kind=InvoiceKind.RECEIVED,
            counterparty_name="Proveedor Taller SL",
            counterparty_tax_id="A58818501",
            counterparty_country="ES",
            invoice_number=f"REC-{filing_year}-{period}",
            issued_at=date(filing_year, _QUARTER_MONTH[period], 10),
            taxable_base=facts["received_base"],
            iva_rate=Decimal("21"),
            currency="EUR",
        )
        purchase_invoices.append(purchase_invoice)
        issued = _iva_transaction(
            f"sale-{period}",
            direction=TransactionDirection.INCOMING,
            taxable_base=facts["issued_base"],
            iva_amount=facts["issued_iva"],
            period=period,
            filing_year=filing_year,
        )
        received = _iva_transaction(
            f"purchase-{period}",
            direction=TransactionDirection.OUTGOING,
            taxable_base=facts["received_base"],
            iva_amount=facts["received_iva"],
            period=period,
            filing_year=filing_year,
            purchase_invoice_evidence_id=purchase_invoice.invoice_id,
            # Domestic purchase from an ES supplier: cuota soportada established
            # by that supplier's invoice (LIVA art. 97.Uno.1).
            deduction_fact_kind=IvaDeductionFactKind.DOMESTIC_CURRENT,
            deduction_provenance=IvaDeductionClassificationProvenance(
                authority=IvaDeductionEvidenceAuthority.INVOICE_EVIDENCE,
                source_locator=f"invoice:{purchase_invoice.invoice_id}",
                evidence_digest="a" * 64,
            ),
        )
        transactions.extend((issued, received))
        devengada = facts["issued_iva"]
        deducible = facts["received_iva"]
        if facts["eu_supply_base"] > Decimal("0"):
            transactions.append(
                _iva_transaction(
                    f"eu-supply-{period}",
                    direction=TransactionDirection.INCOMING,
                    taxable_base=facts["eu_supply_base"],
                    iva_amount=Decimal("0.00"),
                    iva_rate=Decimal("0.00"),
                    period=period,
                    filing_year=filing_year,
                    iva_category=IvaCategory.INTRA_COMMUNITY_SUPPLY,
                    # Established in Germany AND IVA-identified there. Art. 25
                    # exempts an intra-community supply on the acquirer's
                    # IDENTIFICATION, not on establishment, so declaring only the
                    # country leaves the ledger preflight correctly refusing:
                    # "requiere el Estado miembro en el que la contraparte esta
                    # identificada a efectos del IVA". The two are separate facts
                    # and a real filer supplies the second via
                    # `aeat app ledger classify --counterparty-identification-state`.
                    counterparty_country="DE",
                    counterparty_identification_state=EUMemberState.DE,
                ),
            )
        if facts["reverse_charge_base"] > Decimal("0"):
            transactions.append(
                _iva_transaction(
                    f"reverse-charge-{period}",
                    direction=TransactionDirection.OUTGOING,
                    taxable_base=facts["reverse_charge_base"],
                    iva_amount=facts["reverse_charge_iva"],
                    amount=facts["reverse_charge_base"],
                    period=period,
                    filing_year=filing_year,
                    iva_category=IvaCategory.DOMESTIC_REVERSE_CHARGE,
                    # Inversion del sujeto pasivo on a DOMESTIC supply (LIVA
                    # art. 84.Uno.2): the recipient self-repercutes, but the
                    # deduction family stays domestic and the establishing
                    # evidence is the supplier's invoice, NOT an intra-EU
                    # self-assessment.
                    deduction_fact_kind=IvaDeductionFactKind.DOMESTIC_CURRENT,
                    deduction_provenance=IvaDeductionClassificationProvenance(
                        authority=IvaDeductionEvidenceAuthority.INVOICE_EVIDENCE,
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
    tx_repo = TransactionCatalogueRepository(bucket_id=_BUCKET_ID, objects=secure_objects)
    tx_repo.save(TransactionCatalogue.from_transactions(tuple(transactions)))
    InvoiceCatalogueRepository(objects=secure_objects).save(InvoiceCatalogue.from_invoices(tuple(purchase_invoices)))
    return stored


def _wallet_decision(
    *,
    period: str,
    filing_year: int = _YEAR,
    taxpayer_nif: str = _TAX_ID,
    decided_at: datetime = _FILE_AT,
) -> IvaCompensationReconciliationDecision:
    """A neutral (zero, non-blocking) IVA-wallet decision for the quarter."""
    return IvaCompensationReconciliationDecision(
        taxpayer_nif=taxpayer_nif,
        target_year=filing_year,
        target_period=Period.from_year_and_code(filing_year, period),
        selected_authority="aeat_wallet",
        selected_amount=Decimal("0.00"),
        wallet_amount=Decimal("0.00"),
        local_recurrence_amount=Decimal("0.00"),
        override_amount=None,
        divergence="match",
        blocked=False,
        stale_wallet=False,
        reason_identity="aeat_wallet_validated",
        wallet_captured_at=decided_at,
        decided_at=decided_at,
    )


def _store_profile(secure_objects: SecureObjectRepository) -> None:
    """Seed the ready taxpayer profile the M303 gates read."""
    seed_test_profile_record(
        UserProfileRecord(
            setup_state=ProfileSetupState.COMPLETE,
            profile_id=_BUCKET_ID,
            facts=(
                UserProfileFact(path="identity.tax_id", value=_TAX_ID),
                UserProfileFact(path="identity.name", value="Laura"),
                UserProfileFact(path="identity.surnames", value="Taller Sol"),
                UserProfileFact(path="activities.description", value="taller"),
                UserProfileFact(path="tax_residence.ccaa", value="madrid"),
                UserProfileFact(path="tax_residence.jurisdiction_scope", value="common_regime"),
                UserProfileFact(path="iva.regime", value="GENERAL"),
                UserProfileFact(path="iva.m303_regime_composition", value="general"),
                UserProfileFact(path="iva.redeme_enrolled", value=False),
                UserProfileFact(path="iva.cash_accounting_regime_enrolled", value=False),
                UserProfileFact(path="iva.voluntary_sii_enrolled", value=False),
                UserProfileFact(
                    path="iva.hydrocarbon_deposit_advance_payment_deduction_entitled",
                    value=False,
                ),
                UserProfileFact(path="taxpayer_type.entity_type", value="natural_person"),
                UserProfileFact(path="taxpayer_type.irpf_income_categories", value="actividad_economica"),
                UserProfileFact(path="irpf.estimation_regime", value="directa_normal"),
                UserProfileFact(path="censo.activity_start_date", value=date(2020, 1, 1)),
            ),
            created_at=_T0,
            updated_at=_T0,
        ),
    )


def _store_irene_sl_profile(secure_objects: SecureObjectRepository) -> None:
    """Seed Irene SL's IVA profile for the late-local-file persona path."""
    seed_test_profile_record(
        UserProfileRecord(
            setup_state=ProfileSetupState.COMPLETE,
            profile_id=_BUCKET_ID,
            facts=(
                UserProfileFact(path="identity.tax_id", value=_IRENE_TAX_ID),
                UserProfileFact(path="identity.legal_name", value="Irene SL"),
                UserProfileFact(path="activities.description", value="consultoria IVA"),
                UserProfileFact(path="tax_residence.ccaa", value="madrid"),
                UserProfileFact(path="tax_residence.jurisdiction_scope", value="common_regime"),
                UserProfileFact(path="iva.regime", value="GENERAL"),
                UserProfileFact(path="iva.m303_regime_composition", value="general"),
                UserProfileFact(path="iva.redeme_enrolled", value=False),
                UserProfileFact(path="iva.cash_accounting_regime_enrolled", value=False),
                UserProfileFact(path="iva.voluntary_sii_enrolled", value=False),
                UserProfileFact(
                    path="iva.hydrocarbon_deposit_advance_payment_deduction_entitled",
                    value=False,
                ),
                UserProfileFact(path="taxpayer_type.entity_type", value="legal_entity"),
                UserProfileFact(path="taxpayer_type.legal_entity_form", value="sl"),
                UserProfileFact(path="provenance.source", value="manual_cli"),
                UserProfileFact(path="censo.activity_start_date", value=date(_IRENE_YEAR, 1, 1)),
            ),
            created_at=_T0,
            updated_at=_T0,
        ),
    )


def _workflow_profile() -> TaxpayerProfile:
    return TaxpayerProfile(
        tax_id=_TAX_ID,
        iva_regime=IVARegime.GENERAL,
        has_employees=False,
        pays_rent_with_retencion=False,
        does_intracomunitario=True,
        bienes_extranjero_above_threshold=False,
        activity_start_date=date(_YEAR, 1, 1),
    )


def _irene_workflow_profile() -> TaxpayerProfile:
    return TaxpayerProfile(
        tax_id=_IRENE_TAX_ID,
        entity_type=EntityType.LEGAL_ENTITY,
        legal_entity_form=LegalEntityForm.SL,
        iva_regime=IVARegime.GENERAL,
        has_employees=False,
        pays_rent_with_retencion=False,
        does_intracomunitario=False,
        bienes_extranjero_above_threshold=False,
        activity_start_date=date(_IRENE_YEAR, 1, 1),
    )


def _calculate_m303_quarter_revision(
    secure_objects: SecureObjectRepository,
    *,
    period: str,
    filing_year: int = _YEAR,
    taxpayer_nif: str = _TAX_ID,
    calculated_at: datetime = _FILE_AT,
) -> tuple[WorkUnit, CalculationRevision]:
    """Run the live bucket-aggregation M303 calc for one quarter without projecting filed observations."""
    wu_repo = WorkUnitCatalogueRepository(objects=secure_objects)
    cr_repo = CalculationRevisionCatalogueRepository(objects=secure_objects)
    event_repo = BucketEventHistoryRepository(objects=secure_objects)
    tx_repo = TransactionCatalogueRepository(bucket_id=_BUCKET_ID, objects=secure_objects)
    typed_period = Period.from_year_and_code(filing_year, period)
    work_unit = create_work_unit(
        bucket_id=_BUCKET_ID,
        modelo="303",
        filing_year=filing_year,
        period=typed_period,
        revision_id=bundled_authority()
        .snapshot("303", filing_year=filing_year, period=typed_period.registry_token)
        .revision.id,
        repository=wu_repo,
        clock=_T0,
    )
    decision = _wallet_decision(
        period=period, filing_year=filing_year, taxpayer_nif=taxpayer_nif, decided_at=calculated_at
    )
    IvaWalletDecisionRepository(objects=secure_objects).save_decision(decision)
    revision = calculate_modelo_revision_from_bucket_aggregation(
        work_unit.work_unit_id,
        actor="system",
        # Manual, formula-operand "resultado" casillas (58/68/70/76/77/109/18)
        # the fichero-BOE completeness manifest requires but the engine never
        # auto-zero-fills; see ``_MODELO_303_MANUAL_RESULTADO_CASILLA_ZEROS``.
        casilla_inputs=dict(_MODELO_303_MANUAL_RESULTADO_CASILLA_ZEROS),
        binding_values={
            # No prior-period compensación carry in this scenario (each quarter
            # is net-positive); autoconsumo del promotor is nil for this filer.
            "modelo-303-compensacion-pendiente-anteriores": Decimal("0.00"),
            "modelo-303-autoconsumo-promotor-base": Decimal("0.00"),
        },
        iva_compensation_decision=decision,
        filing_instance_evidence=general_m303_filing_evidence(
            typed_period,
            reference=f"test:e2e-ledger-m303:{period}",
        ),
        work_unit_repository=wu_repo,
        calculation_repository=cr_repo,
        bucket_event_repository=event_repo,
        transaction_repository=tx_repo,
        clock=calculated_at,
    )
    return work_unit, revision


def _calculate_and_file_m303_quarter(secure_objects: SecureObjectRepository, *, period: str) -> CalculationRevision:
    """Run the live bucket-aggregation M303 calc for one quarter and project its filed observation."""
    work_unit, revision = _calculate_m303_quarter_revision(secure_objects, period=period)
    persist_filed_revision_observation(
        revision=revision,
        work_unit=work_unit,
        repository=CalculationObservationRepository(objects=secure_objects),
        captured_at=_FILE_AT,
        result_disposition=ResultDisposition.INGRESO,
    )
    return revision


def test_persisted_m303_ledger_revision_verifies_and_refuses_withdrawn_export(
    secure_objects: SecureObjectRepository,
    tmp_path: Path,
) -> None:
    """Persona-like persisted ledger input verifies under the live revision and refuses its withdrawn export."""
    _store_profile(secure_objects)
    stored = _persist_year_of_invoices(secure_objects)
    wu_repo = WorkUnitCatalogueRepository(objects=secure_objects)
    cr_repo = CalculationRevisionCatalogueRepository(objects=secure_objects)
    filing_repo = ModeloRecordCatalogueRepository(objects=secure_objects)
    vr_repo = VerificationReportCatalogueRepository(objects=secure_objects)
    event_repo = BucketEventHistoryRepository(objects=secure_objects)
    tx_repo = TransactionCatalogueRepository(bucket_id=_BUCKET_ID, objects=secure_objects)

    _work_unit, revision = _calculate_m303_quarter_revision(secure_objects, period="1T")
    assert Decimal(revision.casilla_values[_DEVENGADA_TOTAL]) == stored["1T"]["devengada"]
    assert Decimal(revision.casilla_values[_DEDUCIBLE_TOTAL]) == stored["1T"]["deducible"]

    report = verify_modelo_revision(
        revision.calculation_revision_id,
        actor="operator",
        workflow_profile=_workflow_profile(),
        settings=ready_clave_settings(_TAX_ID),
        work_unit_repository=wu_repo,
        calculation_repository=cr_repo,
        filing_repository=filing_repo,
        transaction_repository=tx_repo,
        verification_repository=vr_repo,
        bucket_event_repository=event_repo,
        clock=_FILE_AT,
    )

    assert report.granted_verificado_completo is True
    assert report.completeness_status is VerificationCompletenessStatus.COMPLETE
    verified = cr_repo.load().get(revision.calculation_revision_id)
    assert verified is not None
    assert verified.ledger_filing_snapshot is not None
    assert verified.ledger_filing_evidence is not None

    output_path = tmp_path / f"modelo-303-{_YEAR}-1T.boe"
    with pytest.raises(ModeloExportUnsupportedError) as exc_info:
        export_modelo_revision(
            ModeloExportCommand(
                calculation_revision_id=revision.calculation_revision_id,
                output_path=output_path,
                actor="operator",
            ),
            workflow_profile=_workflow_profile(),
            work_unit_repository=wu_repo,
            calculation_repository=cr_repo,
            filing_repository=filing_repo,
            verification_repository=vr_repo,
            bucket_event_repository=event_repo,
            clock=_FILE_AT,
        )

    assert exc_info.value.context == {
        "modelo": "303",
        "reason": "the registry snapshot has no complete export_layouts definition",
    }
    assert not output_path.exists()


def _calculate_m390_annual(secure_objects: SecureObjectRepository, *, filing_year: int = _YEAR) -> CalculationRevision:
    """Run the live M390/annual calc, leaving the 303-reconciliation relations to fold."""
    wu_repo = WorkUnitCatalogueRepository(objects=secure_objects)
    cr_repo = CalculationRevisionCatalogueRepository(objects=secure_objects)
    tx_repo = TransactionCatalogueRepository(bucket_id=_BUCKET_ID, objects=secure_objects)
    invoice_repo = InvoiceCatalogueRepository(objects=secure_objects)
    snapshot = bundled_authority().snapshot("390", filing_year=filing_year, period="0A")
    work_unit = create_work_unit(
        bucket_id=_BUCKET_ID,
        modelo="390",
        filing_year=filing_year,
        period=Period.from_year_and_code(filing_year, "0A"),
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


def _non_official_local_chain_advisory_periods(report: VerificationReport) -> set[str]:
    periods: set[str] = set()
    for finding in report.findings:
        if finding.message_locale_key != "application.modelo.findings.cross_period_non_official_local_chain.message":
            continue
        facts = finding.message_facts
        if facts.get("source_modelo") != "303" or facts.get("origin_code") != "registry_relation":
            continue
        source_period = facts.get("source_period")
        if isinstance(source_period, str) and source_period in _QUARTER_ORDER:
            periods.add(source_period)
    return periods


def test_irene_sl_2024_local_m303_files_support_m390_verify_and_withdrawn_export_refusal(
    secure_objects: SecureObjectRepository,
    tmp_path: Path,
) -> None:
    """Irene SL: 2024 M303 late local FILE chain feeds M390 without claiming AEAT acceptance.

    This is the persona path that direct observation seeding did not cover:
    calculate -> verify -> withdrawn-export refusal -> local file for each
    closed/overdue M303 quarter, then calculate -> verify M390 from those local
    records and confirm its withdrawn export is refused too.
    The local filing records remain non-official (``aeat_accepted=False``);
    dependent periods surface the non-official-local-chain advisory.
    """
    _store_irene_sl_profile(secure_objects)
    stored = _persist_year_of_invoices(
        secure_objects,
        filing_year=_IRENE_YEAR,
        facts_by_period=_IRENE_QUARTER_FACTS,
    )
    workflow_profile = _irene_workflow_profile()
    wu_repo = WorkUnitCatalogueRepository(objects=secure_objects)
    cr_repo = CalculationRevisionCatalogueRepository(objects=secure_objects)
    filing_repo = ModeloRecordCatalogueRepository(objects=secure_objects)
    verification_repo = VerificationReportCatalogueRepository(objects=secure_objects)
    event_repo = BucketEventHistoryRepository(objects=secure_objects)
    observation_repo = CalculationObservationRepository(objects=secure_objects)
    wallet_repo = IvaWalletDecisionRepository(objects=secure_objects)
    tx_repo = TransactionCatalogueRepository(bucket_id=_BUCKET_ID, objects=secure_objects)

    computed: ComputedM303CasillasByPeriod = {}
    for period in _QUARTER_ORDER:
        _work_unit, revision = _calculate_m303_quarter_revision(
            secure_objects,
            period=period,
            filing_year=_IRENE_YEAR,
            taxpayer_nif=_IRENE_TAX_ID,
            calculated_at=_IRENE_FILE_AT,
        )
        assert Decimal(revision.casilla_values[_DEVENGADA_TOTAL]) == stored[period]["devengada"]
        assert Decimal(revision.casilla_values[_DEDUCIBLE_TOTAL]) == stored[period]["deducible"]
        assert Decimal(revision.casilla_values[_RESULTADO]) == stored[period]["resultado"]
        computed[period] = {
            _DEVENGADA_TOTAL: Decimal(revision.casilla_values[_DEVENGADA_TOTAL]),
            _DEDUCIBLE_TOTAL: Decimal(revision.casilla_values[_DEDUCIBLE_TOTAL]),
            _RESULTADO: Decimal(revision.casilla_values[_RESULTADO]),
        }

        report = verify_modelo_revision(
            revision.calculation_revision_id,
            actor="irene",
            workflow_profile=workflow_profile,
            settings=ready_clave_settings("12345678Z"),
            work_unit_repository=wu_repo,
            calculation_repository=cr_repo,
            filing_repository=filing_repo,
            transaction_repository=tx_repo,
            verification_repository=verification_repo,
            bucket_event_repository=event_repo,
            iva_compensation_decision_repository=wallet_repo,
            calculation_observation_repository=observation_repo,
            clock=_IRENE_FILE_AT,
        )
        assert report.granted_verificado_completo is True, report.findings

        quarter_output = tmp_path / f"modelo-303-{_IRENE_YEAR}-{period}.boe"
        with pytest.raises(ModeloExportUnsupportedError) as exc_info:
            export_modelo_revision(
                ModeloExportCommand(
                    calculation_revision_id=revision.calculation_revision_id,
                    output_path=quarter_output,
                    actor="irene",
                ),
                workflow_profile=workflow_profile,
                work_unit_repository=wu_repo,
                calculation_repository=cr_repo,
                filing_repository=filing_repo,
                verification_repository=verification_repo,
                bucket_event_repository=event_repo,
                iva_compensation_decision_repository=wallet_repo,
                calculation_observation_repository=observation_repo,
                clock=_IRENE_FILE_AT,
            )
        assert exc_info.value.context == {
            "modelo": "303",
            "reason": "the registry snapshot has no complete export_layouts definition",
        }
        assert not quarter_output.exists()

        filing = file_modelo_revision(
            revision.calculation_revision_id,
            actor="irene",
            workflow_profile=workflow_profile,
            work_unit_repository=wu_repo,
            calculation_repository=cr_repo,
            filing_repository=filing_repo,
            verification_repository=verification_repo,
            bucket_event_repository=event_repo,
            iva_compensation_decision_repository=wallet_repo,
            calculation_observation_repository=observation_repo,
            clock=_IRENE_FILE_AT,
        )
        assert filing.aeat_accepted is False
        assert filing.external_evidence is None
        stored_observation = observation_repo.load_observation("303", Period.from_year_and_code(_IRENE_YEAR, period))
        assert stored_observation is not None
        assert stored_observation.source_kind == "app_filing"

    annual = _calculate_m390_annual(secure_objects, filing_year=_IRENE_YEAR)
    for m390_casilla, m303_output in (
        (_M390_DEVENGADA, _DEVENGADA_TOTAL),
        (_M390_DEDUCIBLE, _DEDUCIBLE_TOTAL),
        (_M390_RESULTADO, _RESULTADO),
    ):
        expected = sum((computed[p][m303_output] for p in _QUARTER_ORDER), Decimal("0"))
        assert Decimal(annual.casilla_values[m390_casilla]) == expected
    assert Decimal(annual.casilla_values[_M390_DEVENGADA]) == _IRENE_ANNUAL_EXPECTED["devengada"]
    assert Decimal(annual.casilla_values[_M390_DEDUCIBLE]) == _IRENE_ANNUAL_EXPECTED["deducible"]
    assert Decimal(annual.casilla_values[_M390_RESULTADO]) == _IRENE_ANNUAL_EXPECTED["resultado"]

    annual_report = verify_modelo_revision(
        annual.calculation_revision_id,
        actor="irene",
        workflow_profile=workflow_profile,
        settings=ready_clave_settings("12345678Z"),
        work_unit_repository=wu_repo,
        calculation_repository=cr_repo,
        filing_repository=filing_repo,
        transaction_repository=tx_repo,
        verification_repository=verification_repo,
        bucket_event_repository=event_repo,
        calculation_observation_repository=observation_repo,
        clock=_IRENE_FILE_AT,
    )
    assert annual_report.granted_verificado_completo is True, annual_report.findings
    assert _non_official_local_chain_advisory_periods(annual_report) == set(_QUARTER_ORDER), annual_report.findings

    # The annual resumen still verifies from the locally filed quarters, but its
    # live revision also has no filing-grade fixed-width layout.
    annual_output = tmp_path / f"modelo-390-{_IRENE_YEAR}-0A.boe"
    with pytest.raises(ModeloExportUnsupportedError) as exc_info:
        export_modelo_revision(
            ModeloExportCommand(
                calculation_revision_id=annual.calculation_revision_id,
                output_path=annual_output,
                actor="irene",
            ),
            workflow_profile=workflow_profile,
            work_unit_repository=wu_repo,
            calculation_repository=cr_repo,
            filing_repository=filing_repo,
            verification_repository=verification_repo,
            bucket_event_repository=event_repo,
            calculation_observation_repository=observation_repo,
            clock=_IRENE_FILE_AT,
        )
    assert exc_info.value.context == {
        "modelo": "390",
        "reason": "the registry snapshot has no complete export_layouts definition",
    }
    assert not annual_output.exists()


def test_ledger_drives_m303_quarters_and_folds_into_m390_annual(
    secure_objects: SecureObjectRepository,
) -> None:
    """The full yearly IVA cadence: persisted ledger → 4×M303 → M390 reconciliation."""
    _store_profile(secure_objects)
    stored = _persist_year_of_invoices(secure_objects)

    computed: ComputedM303CasillasByPeriod = {}
    for period in _QUARTER_ORDER:
        revision = _calculate_and_file_m303_quarter(secure_objects, period=period)

        # Transport invariant #1: the computed cuota totals equal the IVA amounts
        # STORED on the persisted invoices (the aggregator sums the stored
        # iva_amount field — it does not re-derive base×rate, confirmed in
        # application/aggregation/_iva_ledger.py). Asserting against the stored
        # field, not a fresh base*rate, keeps the seed and the expectation from
        # sharing a literal.
        assert Decimal(revision.casilla_values[_DEVENGADA_TOTAL]) == stored[period]["devengada"], (
            f"{period}: cuota-devengada-total must equal the stored issued IVA {stored[period]['devengada']}; "
            f"got {revision.casilla_values.get(_DEVENGADA_TOTAL)}"
        )
        assert Decimal(revision.casilla_values[_DEDUCIBLE_TOTAL]) == stored[period]["deducible"], (
            f"{period}: cuota-deducible-total must equal the stored received IVA {stored[period]['deducible']}; "
            f"got {revision.casilla_values.get(_DEDUCIBLE_TOTAL)}"
        )
        assert Decimal(revision.casilla_values[_CASILLA_59]) == stored[period]["casilla_59"], (
            f"{period}: casilla 59 must equal the stored EU supply base {stored[period]['casilla_59']}; "
            f"got {revision.casilla_values.get(_CASILLA_59)}"
        )
        assert Decimal(revision.casilla_values[_RESULTADO]) == stored[period]["resultado"], (
            f"{period}: resultado-regimen-general must match Laura's expected quarterly result "
            f"{stored[period]['resultado']}; got {revision.casilla_values.get(_RESULTADO)}"
        )
        computed[period] = {
            _DEVENGADA_TOTAL: Decimal(revision.casilla_values[_DEVENGADA_TOTAL]),
            _DEDUCIBLE_TOTAL: Decimal(revision.casilla_values[_DEDUCIBLE_TOTAL]),
            _RESULTADO: Decimal(revision.casilla_values[_RESULTADO]),
        }

    # Laura's quarterly resultado values are distinct, so a stale or shifted
    # quarterly dependency cannot satisfy the annual result assertion below.
    result_values = [computed[p][_RESULTADO] for p in _QUARTER_ORDER]
    assert len(set(result_values)) == 4, f"quarterly resultado values must be distinct: {result_values}"

    annual = _calculate_m390_annual(secure_objects)
    casillas = annual.casilla_values

    # Transport invariant #2: M390 annual reconciliation folds the SUM of the four
    # engine-computed M303 quarterly totals.
    for m390_casilla, m303_output in (
        (_M390_DEVENGADA, _DEVENGADA_TOTAL),
        (_M390_DEDUCIBLE, _DEDUCIBLE_TOTAL),
        (_M390_RESULTADO, _RESULTADO),
    ):
        expected = sum((computed[p][m303_output] for p in _QUARTER_ORDER), Decimal("0"))
        assert Decimal(casillas[m390_casilla]) == expected, (
            f"M390 {m390_casilla} must fold sum(1T-4T {m303_output})={expected}; got {casillas.get(m390_casilla)}"
        )
    assert Decimal(casillas[_M390_DEVENGADA]) == _LAURA_ANNUAL_EXPECTED["devengada"]
    assert Decimal(casillas[_M390_DEDUCIBLE]) == _LAURA_ANNUAL_EXPECTED["deducible"]
    assert Decimal(casillas[_M390_RESULTADO]) == _LAURA_ANNUAL_EXPECTED["resultado"]


def test_m390_refuses_zero_reconciliation_when_m303_calculated_but_observations_missing(
    secure_objects: SecureObjectRepository,
) -> None:
    """Laura regression: calculated nonzero 303 quarters must not become zero M390 reconciliation slots."""
    _store_profile(secure_objects)
    _persist_year_of_invoices(secure_objects)

    computed: ComputedM303CasillasByPeriod = {}
    for period in _QUARTER_ORDER:
        _work_unit, revision = _calculate_m303_quarter_revision(secure_objects, period=period)
        computed[period] = {
            _DEVENGADA_TOTAL: Decimal(revision.casilla_values[_DEVENGADA_TOTAL]),
            _DEDUCIBLE_TOTAL: Decimal(revision.casilla_values[_DEDUCIBLE_TOTAL]),
            _RESULTADO: Decimal(revision.casilla_values[_RESULTADO]),
        }

    assert sum((computed[p][_DEVENGADA_TOTAL] for p in _QUARTER_ORDER), Decimal("0")) == Decimal("9828.00")
    assert sum((computed[p][_DEDUCIBLE_TOTAL] for p in _QUARTER_ORDER), Decimal("0")) == Decimal("2163.00")
    assert sum((computed[p][_RESULTADO] for p in _QUARTER_ORDER), Decimal("0")) == Decimal("7665.00")

    cr_repo = CalculationRevisionCatalogueRepository(objects=secure_objects)
    before_revision_ids = frozenset(cr_repo.load().revisions)
    with pytest.raises(ModeloCrossPeriodCleanStateError) as exc_info:
        _calculate_m390_annual(secure_objects)
    after_revision_ids = frozenset(cr_repo.load().revisions)

    assert after_revision_ids == before_revision_ids
    assert isinstance(exc_info.value, CadrumoError)
    assert exc_info.value.translated_message == "application.modelo.errors.cross_period_clean_state_incomplete"
    context = exc_info.value.context or {}
    assert context["reason"] == "missing_clean_cross_period_303_filings_or_observations"
    assert context["missing_303_periods"] == ("1T", "2T", "3T", "4T")
    assert context["zero_reconciliation_casillas_at_risk"] == (
        _M390_DEVENGADA,
        _M390_DEDUCIBLE,
        _M390_RESULTADO,
    )

"""E2E vertical: real ledger → M130 1T-4T (computed) → M100 annual 0604.

This module closes the one joint the existing chain-spine tests leave unproven.
Three segments are each covered in isolation today:

* ledger transactions → M130 casilla 01 (``test_renta_income_aggregation``,
  repository-backed aggregation).
* M130 quarter-to-quarter carry via the ``previous_filing`` resolver
  (``test_modelo_130_carry_forward_continuity``, but with **manual** casilla
  01 inputs, not ledger-derived).
* M130 casilla 19 → M100 0604 fold-in
  (``test_modelo_100_pagos_fraccionados_fold_in_live``, but with **injected**
  c19 filed observations, not values the M130 calc actually computed).

None of them joins the three: no test drives *real persisted ledger
transactions* through the live bucket-aggregation calculate action
(:func:`calculate_modelo_revision_from_bucket_aggregation`) for four cumulative
quarters, files each quarter through the production observation-persistence path
(:func:`persist_filed_revision_observation`), and then proves the annual M100
0604 folds in the **engine-computed** quarterly casilla-19 values. That full
vertical — the autónomo's real yearly cadence — is what this test verifies.

Real-behaviour, real-adapter: real encrypted-SQLite secure store via
:class:`SecureObjectRepository` + ``isolated_runtime_profile``, the real registry
authority, the real calculation engine, the real ledger income aggregation
resolver, the real ``previous_filing`` carry resolver, and the real
``relation_prefill`` fold-in resolver. No mocks, stubs, skips, or xfail.

Non-tautology argument: the per-quarter casilla 19 values are **computed by the
engine** from the ledger-derived casilla 01 through the whole M130 formula chain
(01→03→04→07→12→14→17→19); the test never hand-recomputes any registry formula.
The two load-bearing assertions are *transport / wiring* invariants:

* each quarter's casilla 01 equals the cumulative-YTD sum of the **persisted
  ledger** income the operator never re-keyed (proving the full calculate action,
  not just the aggregator, draws c01 from the ledger); and
* the annual M100 0604 equals the **sum of the four engine-computed c19** the
  four M130 filings persisted (proving the cross-period fold transports those
  specific computed values, not coincidental ones — the four are distinct).

The 20% estimación-directa pago-fraccionado rate that drives c04 is fixed by RD
439/2007 art. 110.4 and grounded in the registry parameter; this test asserts
the *wiring*, leaving the rate's legal currency to the registry grounding gate.
"""

from __future__ import annotations

from datetime import UTC, date, datetime
from decimal import Decimal
from pathlib import Path

import pytest

from ....adapters.persistence.profile.buckets import BucketEventHistoryRepository
from ....adapters.persistence.profile.invoices import InvoiceCatalogueRepository
from ....adapters.persistence.profile.modelos_calculation import CalculationRevisionCatalogueRepository
from ....adapters.persistence.profile.modelos_filing import ModeloRecordCatalogueRepository
from ....adapters.persistence.profile.modelos_work_units import WorkUnitCatalogueRepository
from ....adapters.persistence.profile.transactions import TransactionCatalogueRepository
from ....adapters.persistence.profile.usage_ratios import save_usage_ratios
from ....adapters.persistence.storage.sql import SecureObjectRepository
from ....core import CasillaId, Period, validated_casilla_id
from ....domain.calculations.registry.authority import bundled_authority
from ....domain.calculations.registry.bindings import RegistryModeloObservation
from ....domain.calculations.registry.ids import BindingId
from ....domain.categories import SpendingCategory
from ....domain.deadlines import EntityType, IrpfEstimationRegime, IrpfIncomeCategory, IVARegime, TaxpayerProfile
from ....domain.filing import FilingExportError
from ....domain.invoices import InvoiceCatalogue
from ....domain.modelos import CalculationRevision, ExternalEvidenceKind
from ....domain.transactions import (
    BusinessClassification,
    RawProvenance,
    RawTransaction,
    SourceFormat,
    Transaction,
    TransactionCatalogue,
    TransactionDirection,
    TransactionLifecycleState,
)
from ....domain.usage_ratios import UsageRatioProfile
from ....domain.user_profile.values import ProfileSetupState, UserProfileFact, UserProfileRecord
from ....tests.env_scope import ready_clave_settings
from ....tests.profile_capsule import seed_test_profile_record
from ....tests.registry_observations import registry_grounded_observations
from ...calculations import CalculationObservationRepository
from .._action_errors import ModeloAggregationBindingError
from .._calculation_actions import calculate_modelo_revision_from_bucket_aggregation
from .._export import (
    ModeloExportCommand,
    ModeloExportError,
    export_modelo_revision,
)
from .._filed_revision_observation import persist_filed_revision_observation
from .._verification_actions import verify_modelo_revision
from .._work_lifecycle import create_work_unit
from ..external_import_actions import import_external_filing_evidence
from .justificante_metadata import persist_justificante_metadata

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_BUCKET_ID = "13010000-0000-4000-8000-000000000100"
_TAX_ID = "12345678Z"
_YEAR = 2024
_T0 = datetime(2024, 1, 10, 10, 0, tzinfo=UTC)
_FILE_AT = datetime(2024, 4, 6, 12, 0, tzinfo=UTC)

_M130_REVISION = "2019-y-siguientes"
_M100_ANNUAL_PERIOD = "0A"
_RELATION_PREFILL_SOURCE = "relation_prefill"
_M100_ESTIMACION_DIRECTA_NORMAL_BINDING: BindingId = "renta-2024-modelo-100-estimacion-directa-es-normal"
_M100_SALARY_CERT_RETENCIONES_BINDING: BindingId = "renta-2024-certificado-trabajo-retenciones"


_M130_INGRESOS_CASILLA: CasillaId = validated_casilla_id("01")
_M130_RETENCIONES_CASILLA: CasillaId = validated_casilla_id("06")
_M130_AGRARIAN_VOLUME_CASILLA: CasillaId = validated_casilla_id("08")
_M130_AGRARIAN_WITHHELD_CASILLA: CasillaId = validated_casilla_id("10")
_M130_HOME_DEDUCTION_CASILLA: CasillaId = validated_casilla_id("16")
_M130_PRIOR_RETURN_RESULT_CASILLA: CasillaId = validated_casilla_id("18")
_M130_RESULTADO_FINAL_CASILLA: CasillaId = validated_casilla_id("19")
_M100_PAGOS_CASILLA: CasillaId = validated_casilla_id("0604")
_M100_RETENCIONES_TRABAJO_CASILLA: CasillaId = validated_casilla_id("0596")
_M100_TOTAL_PAGOS_CASILLA: CasillaId = validated_casilla_id("0609")
_M100_CUOTA_DIFERENCIAL_CASILLA: CasillaId = validated_casilla_id("0610")
_M100_ACTIVITY_INCOME_CASILLA: CasillaId = validated_casilla_id("0171")
_M100_ACTIVITY_EXPENSES_SUMMARY_CASILLA: CasillaId = validated_casilla_id("0199")
_M100_EXPENSES_PREVIOUS_SUM_CASILLA: CasillaId = validated_casilla_id("0218")
_M100_NORMAL_DEDUCTIBLE_EXPENSES_CASILLA: CasillaId = validated_casilla_id("0220")
_M100_ACTIVIDAD_ECONOMICA_NET_INCOME_CASILLA: CasillaId = validated_casilla_id("0224")
_M100_RENDIMIENTO_SOURCE_1479_CASILLA: CasillaId = validated_casilla_id("1479")
_M100_RENDIMIENTO_SOURCE_1553_CASILLA: CasillaId = validated_casilla_id("1553")
_M100_RENDIMIENTO_SOURCE_1577_CASILLA: CasillaId = validated_casilla_id("1577")
_M100_BASE_LIQUIDABLE_NEGATIVA_GENERAL_CASILLA: CasillaId = validated_casilla_id("1391")

# Prior-year (2023) actividad-económica net income. M130's casilla-13 minoración
# reads ``irpf.previous_year_economic_activity_net_income`` — a previous_filing
# binding summing the prior annual M100's net-income casillas. The bucket
# previous_filing resolver HARD-RAISES once any prior observation exists and the
# prior-year M100 is absent, so the prior annual filing must be observed (the
# caller channel does not pre-empt the resolver). Set well above the minoración
# income ceiling so the minoración resolves to zero and each quarter's casilla 19
# is the clean incremental pago fraccionado — keeps the four computed c19 distinct
# and positive without this test depending on the minoración schedule.
_PRIOR_YEAR = _YEAR - 1
_PRIOR_YEAR_NET_INCOME = Decimal("50000")

# One coherent year of business income, booked one distinct transaction per
# quarter. Cumulative-YTD (RD 439/2007 art. 110.2) windows then make each
# quarter's casilla 01 the running sum: 1T=4000, 2T=7500, 3T=9500, 4T=12000.
_QUARTER_INCOME: dict[str, tuple[date, Decimal]] = {
    "1T": (date(_YEAR, 2, 15), Decimal("4000.00")),
    "2T": (date(_YEAR, 5, 20), Decimal("3500.00")),
    "3T": (date(_YEAR, 8, 10), Decimal("2000.00")),
    "4T": (date(_YEAR, 11, 5), Decimal("2500.00")),
}
_QUARTER_ORDER = ("1T", "2T", "3T", "4T")
_EXPECTED_CUMULATIVE_C01: dict[str, Decimal] = {
    "1T": Decimal("4000.00"),
    "2T": Decimal("7500.00"),
    "3T": Decimal("9500.00"),
    "4T": Decimal("12000.00"),
}

_EXPECTED_M100_ACTIVITY_INCOME = Decimal("12000.00")
_EXPECTED_M100_ACTIVITY_EXPENSES = Decimal("2400.00")
_EXPECTED_M100_ACTIVITY_NET = Decimal("9600.00")
_AUTONOMA_M130_C19_BY_PERIOD: dict[str, Decimal] = {
    "1T": Decimal("300.00"),
    "2T": Decimal("360.00"),
    "3T": Decimal("400.00"),
    "4T": Decimal("460.00"),
}
_AUTONOMA_SALARY_GROSS = Decimal("30000.00")
_AUTONOMA_SALARY_WITHHOLDING = Decimal("4500.00")
_EXPENSE_ROWS: tuple[tuple[str, date, SpendingCategory, Decimal], ...] = (
    ("expense-office", date(_YEAR, 2, 20), SpendingCategory.MATERIAL_OFICINA, Decimal("500.00")),
    ("expense-software", date(_YEAR, 5, 22), SpendingCategory.SOFTWARE_SUSCRIPCION, Decimal("700.00")),
    ("expense-phone", date(_YEAR, 8, 12), SpendingCategory.TELEFONIA_MOVIL, Decimal("300.00")),
    ("expense-advisory", date(_YEAR, 11, 8), SpendingCategory.ASESORIA_FISCAL, Decimal("900.00")),
)

# M130 manual casillas (retenciones / agrarian / vivienda / prior
# autoliquidaciones). All zero for this pure-estimación-directa, no-retención
# persona. Casilla 02 (Gastos) is a source-owned bound casilla
# (ledger renta gasto aggregation) and is NOT supplied here: the persisted
# expense rows drive it through the live source resolver.
_M130_MANUAL_INPUTS: dict[CasillaId, Decimal] = {
    _M130_RETENCIONES_CASILLA: Decimal("0"),
    _M130_AGRARIAN_VOLUME_CASILLA: Decimal("0"),
    _M130_AGRARIAN_WITHHELD_CASILLA: Decimal("0"),
    _M130_HOME_DEDUCTION_CASILLA: Decimal("0"),
    _M130_PRIOR_RETURN_RESULT_CASILLA: Decimal("0"),
}

# The M100 0604 formula sums BOTH the M130 and M131 pagos relations; this persona
# files no estimacion objetiva, so the M131 leg resolves as not-applicable zero
# without any synthetic M131 filings.


def _income_transaction(period: str) -> Transaction:
    value_date, amount = _QUARTER_INCOME[period]
    return Transaction.model_validate(
        {
            "raw": RawTransaction(
                provider_transaction_id=f"income-{period}",
                booked_date=value_date,
                value_date=value_date,
                amount=amount,
                currency="EUR",
                counterparty="Cliente SA",
                description=f"factura {period}",
                provenance=RawProvenance(
                    source_path=Path(__file__),
                    source_sha256="a" * 64,
                    source_row_index=1,
                    source_format=SourceFormat.CSV,
                    ingested_at=_T0,
                    provider_name="CSV provider",
                ),
                raw_fields={"Concepto": f"factura {period}"},
            ),
            "direction": TransactionDirection.INCOMING,
            "group_label": None,
            "source_jurisdiction": "ES",
            "business_classification": BusinessClassification.BUSINESS,
            "business_pct": None,
            "purchase_invoice_evidence_id": None,
            "category_id": None,
            # The autonoma's activity receipts are IRPF-ready taxable-base rows. They
            # deliberately carry no IVA amount/rate facts: M130 already consumes
            # this base-only substrate and M100 must not demand IVA-only facts
            # unless its revision owns IVA ledger bindings.
            "taxable_base": amount,
            "lifecycle_state": TransactionLifecycleState.ACTIVE,
            "classified_at": _T0,
            "classified_by": "manual",
        },
    )


def _expense_transaction(
    transaction_id: str,
    *,
    value_date: date,
    category: SpendingCategory,
    taxable_base: Decimal,
) -> Transaction:
    return Transaction.model_validate(
        {
            "raw": RawTransaction(
                provider_transaction_id=transaction_id,
                booked_date=value_date,
                value_date=value_date,
                amount=taxable_base,
                currency="EUR",
                counterparty="Proveedor",
                description=f"gasto {category.value}",
                provenance=RawProvenance(
                    source_path=Path(__file__),
                    source_sha256="b" * 64,
                    source_row_index=1,
                    source_format=SourceFormat.CSV,
                    ingested_at=_T0,
                    provider_name="CSV provider",
                ),
                raw_fields={"Concepto": f"gasto {category.value}"},
            ),
            "direction": TransactionDirection.OUTGOING,
            "group_label": None,
            "source_jurisdiction": "ES",
            "business_classification": BusinessClassification.BUSINESS,
            "business_pct": None,
            "purchase_invoice_evidence_id": None,
            "attachment_ids": (f"receipt-{transaction_id}",),
            "category_id": category.value,
            "taxable_base": taxable_base,
            "lifecycle_state": TransactionLifecycleState.ACTIVE,
            "classified_at": _T0,
            "classified_by": "manual",
        },
    )


def _persist_autonoma_style_ledger(secure_objects: SecureObjectRepository) -> None:
    """Persist Autonoma-shaped annual activity income plus deductible expenses."""
    tx_repo = TransactionCatalogueRepository(bucket_id=_BUCKET_ID, objects=secure_objects)
    transactions = tuple(_income_transaction(period) for period in _QUARTER_ORDER) + tuple(
        _expense_transaction(transaction_id, value_date=value_date, category=category, taxable_base=taxable_base)
        for transaction_id, value_date, category, taxable_base in _EXPENSE_ROWS
    )
    tx_repo.save(
        TransactionCatalogue.from_transactions(transactions),
    )
    InvoiceCatalogueRepository(bucket_id=_BUCKET_ID, objects=secure_objects).save(InvoiceCatalogue())
    save_usage_ratios(
        UsageRatioProfile(ratios={SpendingCategory.TELEFONIA_MOVIL: Decimal("1")}),
        bucket_id=_BUCKET_ID,
        objects=secure_objects,
    )


def _calculate_and_file_m130_quarter(
    secure_objects: SecureObjectRepository,
    *,
    period: str,
) -> CalculationRevision:
    """Run the live bucket-aggregation M130 calc for one quarter and file it.

    Casilla 01 is drawn from the persisted ledger (cumulative YTD); casillas 05
    (pagos anteriores) and 15 (resultados negativos anteriores) auto-resolve from
    the prior filed quarters via the ``previous_filing`` resolver; the prior-year
    net-income minoración input is supplied through the caller channel. The
    computed revision is then persisted through the production filing-observation
    path so the next quarter (and the annual fold-in) can carry it.
    """
    wu_repo = WorkUnitCatalogueRepository(objects=secure_objects)
    cr_repo = CalculationRevisionCatalogueRepository(objects=secure_objects)
    tx_repo = TransactionCatalogueRepository(bucket_id=_BUCKET_ID, objects=secure_objects)
    invoice_repo = InvoiceCatalogueRepository(bucket_id=_BUCKET_ID, objects=secure_objects)
    work_unit = create_work_unit(
        bucket_id=_BUCKET_ID,
        modelo="130",
        filing_year=_YEAR,
        period=Period.from_year_and_code(_YEAR, period),
        revision_id=_M130_REVISION,
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


def _import_official_m130_result_observation(
    secure_objects: SecureObjectRepository,
    *,
    period: str,
    c19_value: Decimal,
) -> None:
    """Persist the autonoma's filed M130 result as AEAT-attested local evidence."""
    wu_repo = WorkUnitCatalogueRepository(objects=secure_objects)
    cr_repo = CalculationRevisionCatalogueRepository(objects=secure_objects)
    filing_repo = ModeloRecordCatalogueRepository(objects=secure_objects)
    bucket_events = BucketEventHistoryRepository(objects=secure_objects)
    observation_repo = CalculationObservationRepository(objects=secure_objects)
    snapshot = bundled_authority().snapshot("130", filing_year=_YEAR, period=period)
    work_unit = create_work_unit(
        bucket_id=_BUCKET_ID,
        modelo="130",
        filing_year=_YEAR,
        period=Period.from_year_and_code(_YEAR, period),
        revision_id=snapshot.revision.id,
        repository=wu_repo,
        clock=_FILE_AT,
    )
    casilla_values = {_M130_RESULTADO_FINAL_CASILLA: c19_value}
    evidence_reference_id = f"JUST-130-{_YEAR}-{period}-AUTONOMA-C19"
    persist_justificante_metadata(
        evidence_reference_id,
        modelo="130",
        filing_year=_YEAR,
        period=period,
        captured_at=_FILE_AT,
        tax_id=_TAX_ID,
    )
    import_external_filing_evidence(
        work_unit_id=work_unit.work_unit_id,
        casilla_values=casilla_values,
        evidence_kind=ExternalEvidenceKind.AEAT_JUSTIFICANTE_PDF,
        evidence_reference_id=evidence_reference_id,
        actor="aeat-import-test",
        work_unit_repository=wu_repo,
        calculation_repository=cr_repo,
        filing_repository=filing_repo,
        bucket_event_repository=bucket_events,
        expected_tax_id=_TAX_ID,
        clock=_FILE_AT,
    )
    observation_repo.save(
        observation_repo.prepare_observation_envelope(
            RegistryModeloObservation(
                modelo="130",
                filing_year=_YEAR,
                period=period,
                observations=registry_grounded_observations(
                    modelo="130",
                    filing_year=_YEAR,
                    period=period,
                    casilla_values=casilla_values,
                ),
            ),
            source_kind="aeat_sede_justificante",
            captured_at=_FILE_AT,
            stamped_revision_id=snapshot.revision.id,
            source_metadata={
                "aeat_register_status": "ALTA",
                "aeat_expediente_id": f"EXP-130-{_YEAR}-{period}",
                "aeat_justificante_csv": evidence_reference_id,
                "authenticated_identity": _TAX_ID,
            },
        )
    )


def _seed_prior_year_m100(secure_objects: SecureObjectRepository) -> None:
    """Observe the prior-year annual Renta (M100 2023) net-income casillas.

    Carries every prior-year casilla a 2024 ``previous_filing`` binding reads:
    M130's casilla-13 minoración sums M100 0224/1479/1553/1577 (net income in
    0224, the rest zero for a pure actividad-económica filer), and M100/2024's
    base-liquidable-negativa-general carry copies casilla 1391 (no prior BIN, so
    zero). Net income is set above the minoración ceiling so the minoración
    resolves to zero.
    """
    CalculationObservationRepository(objects=secure_objects).save(
        CalculationObservationRepository(objects=secure_objects).prepare_observation_envelope(
            RegistryModeloObservation(
                modelo="100",
                filing_year=_PRIOR_YEAR,
                period=_M100_ANNUAL_PERIOD,
                observations=registry_grounded_observations(
                    modelo="100",
                    filing_year=_PRIOR_YEAR,
                    period=_M100_ANNUAL_PERIOD,
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


def _seed_taxpayer_profile() -> None:
    """Seed the single-taxpayer profile M100's profile-sourced bindings consume."""
    # display_name MUST equal the manifest label isolated_runtime_profile created
    # ("Test runtime profile") — CommittedProfileView._validate_cross_store_agreement
    # rejects a label/display_name mismatch as a torn-rename inconsistency.
    record = UserProfileRecord(
        setup_state=ProfileSetupState.COMPLETE,
        profile_id=_BUCKET_ID,
        facts=(
            UserProfileFact(path="identity.tax_id", value=_TAX_ID),
            UserProfileFact(path="identity.name", value="Annual"),
            UserProfileFact(path="identity.surnames", value="Renta Tester"),
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
            UserProfileFact(path="censo.activity_start_date", value=date(2020, 1, 1)),
            UserProfileFact(path="renta_taxpayer.birth_date", value=date(1980, 3, 15)),
            UserProfileFact(path="renta_taxpayer.sex", value="H"),
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
    )
    seed_test_profile_record(record)


def _autonoma_workflow_profile() -> TaxpayerProfile:
    return TaxpayerProfile(
        tax_id=_TAX_ID,
        entity_type=EntityType.NATURAL_PERSON,
        irpf_income_categories=frozenset({IrpfIncomeCategory.ACTIVIDAD_ECONOMICA}),
        irpf_estimation_regime=IrpfEstimationRegime.DIRECTA_NORMAL,
        iva_regime=IVARegime.GENERAL,
        has_employees=False,
        pays_professionals_with_retencion=False,
        pays_rent_with_retencion=False,
        pays_capital_income_with_retencion=False,
        does_intracomunitario=False,
        third_party_transactions_above_347_threshold=False,
        bienes_extranjero_above_threshold=False,
        monedas_virtuales_extranjero_above_threshold=False,
    )


def _m100_non_relation_zero_bindings() -> dict[BindingId, Decimal]:
    """Zero-default every M100/2024 binding that is neither profile- nor relation-sourced."""
    snapshot = bundled_authority().snapshot("100", filing_year=_YEAR, period=_M100_ANNUAL_PERIOD)
    values = {
        binding.id: Decimal("0")
        for binding in snapshot.revision.bindings
        if binding.id != _M100_SALARY_CERT_RETENCIONES_BINDING
        if binding.source
        not in (
            "profile",
            _RELATION_PREFILL_SOURCE,
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


def _calculate_m100_annual(
    secure_objects: SecureObjectRepository,
    *,
    casilla_inputs: dict[CasillaId, Decimal] | None = None,
    binding_values: dict[BindingId, Decimal] | None = None,
) -> CalculationRevision:
    """Run the live M100/2024/0A annual calc, leaving the pagos relations to fold."""
    _seed_taxpayer_profile()
    wu_repo = WorkUnitCatalogueRepository(objects=secure_objects)
    cr_repo = CalculationRevisionCatalogueRepository(objects=secure_objects)
    tx_repo = TransactionCatalogueRepository(bucket_id=_BUCKET_ID, objects=secure_objects)
    invoice_repo = InvoiceCatalogueRepository(bucket_id=_BUCKET_ID, objects=secure_objects)
    snapshot = bundled_authority().snapshot("100", filing_year=_YEAR, period=_M100_ANNUAL_PERIOD)
    work_unit = create_work_unit(
        bucket_id=_BUCKET_ID,
        modelo="100",
        filing_year=_YEAR,
        period=Period.from_year_and_code(_YEAR, _M100_ANNUAL_PERIOD),
        revision_id=snapshot.revision.id,
        repository=wu_repo,
        clock=_T0,
    )
    return calculate_modelo_revision_from_bucket_aggregation(
        work_unit.work_unit_id,
        casilla_inputs=casilla_inputs,
        binding_values={**_m100_non_relation_zero_bindings(), **(binding_values or {})},
        work_unit_repository=wu_repo,
        calculation_repository=cr_repo,
        transaction_repository=tx_repo,
        invoice_repository=invoice_repo,
        clock=_T0,
    )


def test_ledger_drives_m130_quarters_and_folds_into_m100_annual(
    secure_objects: SecureObjectRepository,
) -> None:
    """The full yearly cadence: persisted ledger → 4×M130 → M100 0604 fold-in."""
    _seed_taxpayer_profile()
    _persist_autonoma_style_ledger(secure_objects)
    _seed_prior_year_m100(secure_objects)

    computed_c19: dict[str, Decimal] = {}
    for period in _QUARTER_ORDER:
        revision = _calculate_and_file_m130_quarter(secure_objects, period=period)

        # Transport invariant #1: the FULL bucket-aggregation calc action draws
        # casilla 01 from the persisted ledger (cumulative YTD), not from any
        # manual input — the operator never re-keyed income.
        assert Decimal(revision.casilla_values[_M130_INGRESOS_CASILLA]) == _EXPECTED_CUMULATIVE_C01[period], (
            f"{period}: casilla 01 must equal cumulative ledger income "
            f"{_EXPECTED_CUMULATIVE_C01[period]}; got {revision.casilla_values.get(_M130_INGRESOS_CASILLA)}"
        )
        computed_c19[period] = Decimal(revision.casilla_values[_M130_RESULTADO_FINAL_CASILLA])

    # The four engine-computed quarterly resultado-final values are distinct and
    # strictly positive — a coincidental sum or a single-quarter copy cannot then
    # satisfy the annual fold assertion below.
    assert len(set(computed_c19.values())) == 4, f"quarterly c19 must be distinct: {computed_c19}"
    assert all(value > Decimal("0") for value in computed_c19.values()), computed_c19

    annual = _calculate_m100_annual(secure_objects)

    assert Decimal(annual.casilla_values[_M100_ACTIVITY_INCOME_CASILLA]) == _EXPECTED_M100_ACTIVITY_INCOME
    assert Decimal(annual.casilla_values[_M100_EXPENSES_PREVIOUS_SUM_CASILLA]) == _EXPECTED_M100_ACTIVITY_EXPENSES
    assert Decimal(annual.casilla_values[_M100_NORMAL_DEDUCTIBLE_EXPENSES_CASILLA]) == _EXPECTED_M100_ACTIVITY_EXPENSES
    assert Decimal(annual.casilla_values[_M100_ACTIVIDAD_ECONOMICA_NET_INCOME_CASILLA]) == _EXPECTED_M100_ACTIVITY_NET

    # Transport invariant #2: the annual M100 0604 folds in the SUM of the four
    # engine-computed M130 casilla-19 values (M131 folds as not-applicable zero). This wires
    # the quarterly calculations the ledger produced through to the annual renta.
    expected_total = sum(computed_c19.values(), Decimal("0"))
    casilla_0604 = Decimal(annual.casilla_values[_M100_PAGOS_CASILLA])
    assert casilla_0604 == expected_total, (
        f"M100 0604 must fold in the four computed M130 c19 (sum {expected_total}); got {casilla_0604}"
    )


def test_verify_accepts_autonoma_m100_with_official_m130_observations(
    secure_objects: SecureObjectRepository,
) -> None:
    """An internally consistent M100/2024 draft passes verify replay.

    The annual activity values are produced from real persisted ledger rows,
    and 0604 is folded from four imported AEAT-attested M130 observations.
    Verify then rebuilds the filing draft from the stored calculation revision
    and must accept the computed 0224/0529/0531 formula traces instead of
    treating them as manual casillas.
    """
    _seed_taxpayer_profile()
    _persist_autonoma_style_ledger(secure_objects)
    _seed_prior_year_m100(secure_objects)

    for period, c19_value in _AUTONOMA_M130_C19_BY_PERIOD.items():
        _import_official_m130_result_observation(secure_objects, period=period, c19_value=c19_value)

    annual = _calculate_m100_annual(secure_objects)

    assert Decimal(annual.casilla_values[_M100_ACTIVITY_INCOME_CASILLA]) == Decimal("12000.00")
    assert Decimal(annual.casilla_values[_M100_ACTIVITY_EXPENSES_SUMMARY_CASILLA]) == Decimal("2400.00")
    assert Decimal(annual.casilla_values[_M100_EXPENSES_PREVIOUS_SUM_CASILLA]) == Decimal("2400.00")
    assert Decimal(annual.casilla_values[_M100_NORMAL_DEDUCTIBLE_EXPENSES_CASILLA]) == Decimal("2400.00")
    assert Decimal(annual.casilla_values[_M100_ACTIVIDAD_ECONOMICA_NET_INCOME_CASILLA]) == Decimal("9600.00")
    assert Decimal(annual.casilla_values[_M100_PAGOS_CASILLA]) == Decimal("1520.00")
    assert Decimal(annual.casilla_values[_M100_PAGOS_CASILLA]) == sum(
        _AUTONOMA_M130_C19_BY_PERIOD.values(),
        Decimal("0"),
    )

    report = verify_modelo_revision(
        annual.calculation_revision_id,
        actor="autonoma-cli-rerun",
        workflow_profile=_autonoma_workflow_profile(),
        settings=ready_clave_settings(_TAX_ID),
        work_unit_repository=WorkUnitCatalogueRepository(objects=secure_objects),
        calculation_repository=CalculationRevisionCatalogueRepository(objects=secure_objects),
        transaction_repository=TransactionCatalogueRepository(bucket_id=_BUCKET_ID, objects=secure_objects),
        calculation_observation_repository=CalculationObservationRepository(objects=secure_objects),
    )

    assert report.calculation_revision_id == annual.calculation_revision_id
    assert report.granted_verificado_completo is True, report.findings
    assert not [finding for finding in report.findings if finding.severity.value == "blocking"]


def test_autonoma_m100_salary_certificate_retenciones_export_replays_verified_total_pagos(
    secure_objects: SecureObjectRepository,
    tmp_path: Path,
) -> None:
    """Verified salary withholding replays through verify and XML export."""
    _seed_taxpayer_profile()
    _persist_autonoma_style_ledger(secure_objects)
    _seed_prior_year_m100(secure_objects)

    for period, c19_value in _AUTONOMA_M130_C19_BY_PERIOD.items():
        _import_official_m130_result_observation(secure_objects, period=period, c19_value=c19_value)

    annual = _calculate_m100_annual(
        secure_objects,
        casilla_inputs={validated_casilla_id("0003"): _AUTONOMA_SALARY_GROSS},
        binding_values={_M100_SALARY_CERT_RETENCIONES_BINDING: _AUTONOMA_SALARY_WITHHOLDING},
    )

    assert Decimal(annual.casilla_values[_M100_ACTIVITY_INCOME_CASILLA]) == Decimal("12000.00")
    assert Decimal(annual.casilla_values[_M100_EXPENSES_PREVIOUS_SUM_CASILLA]) == Decimal("2400.00")
    assert Decimal(annual.casilla_values[_M100_NORMAL_DEDUCTIBLE_EXPENSES_CASILLA]) == Decimal("2400.00")
    assert Decimal(annual.casilla_values[_M100_ACTIVIDAD_ECONOMICA_NET_INCOME_CASILLA]) == Decimal("9600.00")
    assert Decimal(annual.casilla_values[_M100_RETENCIONES_TRABAJO_CASILLA]) == _AUTONOMA_SALARY_WITHHOLDING
    assert Decimal(annual.casilla_values[_M100_PAGOS_CASILLA]) == Decimal("1520.00")
    assert Decimal(annual.casilla_values[_M100_TOTAL_PAGOS_CASILLA]) == Decimal("6020.00")

    report = verify_modelo_revision(
        annual.calculation_revision_id,
        actor="autonoma-cli-rerun",
        workflow_profile=_autonoma_workflow_profile(),
        settings=ready_clave_settings(_TAX_ID),
        work_unit_repository=WorkUnitCatalogueRepository(objects=secure_objects),
        calculation_repository=CalculationRevisionCatalogueRepository(objects=secure_objects),
        transaction_repository=TransactionCatalogueRepository(bucket_id=_BUCKET_ID, objects=secure_objects),
        calculation_observation_repository=CalculationObservationRepository(objects=secure_objects),
    )

    assert report.calculation_revision_id == annual.calculation_revision_id
    assert report.granted_verificado_completo is True, report.findings
    assert not [finding for finding in report.findings if finding.severity.value == "blocking"]

    # The operator reaches a verified revision and then cannot export it. Modelo
    # 100's XML layouts leave the declaration's mandatory Aux/VERSION undeclared,
    # because AEAT publishes no authoritative value for it, and the export refuses
    # rather than writing a document that fails at its own first element. The
    # calculation and verification above are unaffected -- which is the point of
    # keeping this replay end-to-end: it shows exactly how far the operator gets.
    output = tmp_path / "modelo-100-2024-0A.xml"
    with pytest.raises(ModeloExportError) as refusal:
        export_modelo_revision(
            ModeloExportCommand(
                calculation_revision_id=annual.calculation_revision_id,
                output_path=output,
                actor="autonoma-cli-rerun",
            ),
            workflow_profile=_autonoma_workflow_profile(),
            work_unit_repository=WorkUnitCatalogueRepository(objects=secure_objects),
            calculation_repository=CalculationRevisionCatalogueRepository(objects=secure_objects),
            filing_repository=ModeloRecordCatalogueRepository(objects=secure_objects),
            bucket_event_repository=BucketEventHistoryRepository(objects=secure_objects),
            calculation_observation_repository=CalculationObservationRepository(objects=secure_objects),
        )

    # The operator-facing wrapper carries a translated key, so the structural
    # cause is what names the undeclared field. Reading it here also proves the
    # wrapper preserves that cause rather than flattening it to a write failure.
    assert isinstance(refusal.value.__cause__, FilingExportError)
    assert "aux_version" in str(refusal.value.__cause__)
    assert not output.exists()


def test_m100_base_only_gate_still_blocks_missing_renta_taxable_base(
    secure_objects: SecureObjectRepository,
) -> None:
    """M100 does not demand IVA-only facts, but still blocks missing Renta base facts."""
    _seed_taxpayer_profile()
    _seed_prior_year_m100(secure_objects)
    transactions = (
        *(_income_transaction(period) for period in _QUARTER_ORDER),
        _expense_transaction(
            "expense-missing-base",
            value_date=date(_YEAR, 2, 20),
            category=SpendingCategory.MATERIAL_OFICINA,
            taxable_base=Decimal("500.00"),
        ).model_copy(update={"taxable_base": None}),
    )
    TransactionCatalogueRepository(bucket_id=_BUCKET_ID, objects=secure_objects).save(
        TransactionCatalogue.from_transactions(transactions),
    )
    InvoiceCatalogueRepository(bucket_id=_BUCKET_ID, objects=secure_objects).save(InvoiceCatalogue())

    with pytest.raises(ModeloAggregationBindingError) as exc_info:
        _calculate_m100_annual(secure_objects)

    assert exc_info.value.translated_message == "application.modelo.errors.ledger_preflight_blocked"
    assert exc_info.value.context is not None
    assert exc_info.value.context["reason"] == "missing_taxable_base"


def test_verify_gate_blocks_chain_carrying_non_official_prior_year(
    secure_objects: SecureObjectRepository,
) -> None:
    """The operator verify gate refuses verificado-completo on the ledger chain.

    Completes the operator flow calculate → VERIFY on the same vertical, and
    proves the cross-period clean-state safety invariant fires end-to-end: the
    M130 quarters and the prior-year M100/2023 carry were filed locally through
    ``persist_filed_revision_observation`` with the NON-official ``app_filing``
    source_kind. Filing a dependent period (M100/2024) whose upstream evidence is
    local-only — not an external AEAT justificante / CSV register / live capture —
    must NOT be granted verificado-completo. The verify gate therefore returns a
    BLOCKING ``cross_period_dependency_unclean`` finding naming the non-official
    prior-year filing (modelo 100 / 2023), per
    ``no-silent-under-declaration`` and
    ``sensitive-financial-data-secure-storage-only``. This is the correct refusal, not a defect: it
    proves the chain reaches the verify gate and the safety guard engages on a
    real ledger-derived multi-period chain.
    """
    _seed_taxpayer_profile()
    _persist_autonoma_style_ledger(secure_objects)
    _seed_prior_year_m100(secure_objects)
    for period in _QUARTER_ORDER:
        _calculate_and_file_m130_quarter(secure_objects, period=period)
    annual = _calculate_m100_annual(secure_objects)

    report = verify_modelo_revision(
        annual.calculation_revision_id,
        actor="system",
        workflow_profile=TaxpayerProfile(tax_id="X1234567L", iva_regime=IVARegime.GENERAL),
        settings=ready_clave_settings("X1234567L"),
        work_unit_repository=WorkUnitCatalogueRepository(objects=secure_objects),
        calculation_repository=CalculationRevisionCatalogueRepository(objects=secure_objects),
        transaction_repository=TransactionCatalogueRepository(bucket_id=_BUCKET_ID, objects=secure_objects),
        calculation_observation_repository=CalculationObservationRepository(objects=secure_objects),
    )

    assert report.calculation_revision_id == annual.calculation_revision_id
    # The chain carries non-official (app_filing) upstream evidence, so the gate
    # must NOT grant verificado-completo.
    assert report.granted_verificado_completo is False
    unclean = [
        finding
        for finding in report.findings
        if finding.kind.value == "cross_period_dependency_unclean" and finding.severity.value == "blocking"
    ]
    assert unclean, (
        f"verify gate must raise a BLOCKING cross_period_dependency_unclean finding "
        f"for the non-official prior-year carry; got {report.findings}"
    )
    assert any(
        finding.message_locale_key == "application.modelo.findings.cross_period_dependency_unclean"
        and finding.message_facts.get("source_modelo") == "130"
        and finding.message_facts.get("source_filing_year") == 2024
        and finding.message_facts.get("source_period") == "1T"
        and "missing_current_filing_record" in str(finding.message_facts.get("blocker_codes", "")).split("|")
        for finding in unclean
    ), f"the unclean finding must name the missing official M130 quarterly filing record; got {unclean}"

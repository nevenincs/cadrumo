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
(:func:`calculate_modelo_revision_from_bucket_aggregation_with_diagnostics`) for four cumulative
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

from datetime import date
from decimal import Decimal
from pathlib import Path

import pytest
from defusedxml import ElementTree as DefusedElementTree

from cadrumo.adapters.persistence.profile.buckets import BucketEventHistoryRepository
from cadrumo.adapters.persistence.profile.calculation_observations import CalculationObservationRepository
from cadrumo.adapters.persistence.profile.invoices import InvoiceCatalogueRepository
from cadrumo.adapters.persistence.profile.iva_compensation_history import IvaCompensationHistoryRepository
from cadrumo.adapters.persistence.profile.modelos_calculation import CalculationRevisionCatalogueRepository
from cadrumo.adapters.persistence.profile.modelos_work_units import WorkUnitCatalogueRepository
from cadrumo.adapters.persistence.profile.tests.modelo_export_ports_support import modelo_export_ports_for_test
from cadrumo.adapters.persistence.profile.tests.secure_objects_fixture import secure_objects
from cadrumo.adapters.persistence.profile.transactions import TransactionCatalogueRepository
from cadrumo.adapters.persistence.storage.sql.secure_objects import SecureObjectRepository
from cadrumo.adapters.persistence.storage.tests.profile_capsule_runtime import seed_test_profile_record
from cadrumo.application.calculations.observations_repository import observation_key
from cadrumo.application.modelo.action_errors import ModeloLedgerPreflightBlockedError
from cadrumo.application.modelo.export_contracts import ModeloExportCommand
from cadrumo.application.modelo.work_lifecycle import create_work_unit
from cadrumo.application.modelo.work_lifecycle_ports import WorkLifecyclePorts
from cadrumo.application.user_profile.tests.persona_profile_facts import persona_facts_beneath
from cadrumo.core.casilla_id import CasillaId, validated_casilla_id
from cadrumo.core.package_version import PACKAGE_VERSION
from cadrumo.core.period import Period
from cadrumo.domain.calculations.registry.authority import bundled_indexed_authority
from cadrumo.domain.calculations.registry.ids import BindingId
from cadrumo.domain.categories.spending_category import SpendingCategory
from cadrumo.domain.deadlines.models import IVARegime, TaxpayerProfile
from cadrumo.domain.invoices.catalogue import InvoiceCatalogue
from cadrumo.domain.modelos.calculation_revision import CalculationRevision
from cadrumo.domain.modelos.filing_kind_evidence import FilingKindEvidenceBasis
from cadrumo.domain.modelos.filing_record import FilingDeclarationKind
from cadrumo.domain.transactions.models import TransactionCatalogue
from cadrumo.domain.user_profile.tests.profile_creation_authority import profile_creation_context_for_test
from cadrumo.domain.user_profile.values import ProfileSetupState, UserProfileFact, create_user_profile_record
from cadrumo.entrypoints.tests.profile_persistence.verification_repository_support import (
    build_test_certificate_secret_backend_factory,
    build_test_verification_repository_bundle,
)
from cadrumo.tests.env_scope import ready_clave_settings

from ....adapters.persistence.profile.tests.published_authority_support import published_authority_operation
from ....adapters.persistence.profile.tests.retencion_soportada_seed import seed_payer_certificate
from ....application.modelo.tests.filed_observation_fixture import persist_filed_revision_observation
from ....core.retencion_soportada import RetencionSoportadaClase
from ....domain.user_profile.tests.imputation_criterion_facts import cash_criterion_facts
from .general_iva_profile_facts_support import renta_single_taxpayer_facts
from .m130_m100_annual_support import (
    BUCKET_ID,
    FILE_AT,
    M100_ACTIVIDAD_ECONOMICA_NET_INCOME_CASILLA,
    M100_ANNUAL_PERIOD,
    M130_PRIOR_RETURN_RESULT_CASILLA,
    M130_RESULTADO_FINAL_CASILLA,
    OPERATOR_SCOPE_PORTS,
    T0,
    TAX_ID,
    YEAR,
    autonomaworkflow_profile,
    calculate_revision_from_bucket_aggregation,
    expense_transaction,
    export_revision_for_test,
    import_official_m130_result_observation,
    income_transaction,
    m100_non_relation_zero_bindings,
    seed_prior_year_m100,
    verify_revision_for_test,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint]


__all__ = ["secure_objects"]


@pytest.fixture
def bucket_id() -> str:
    return BUCKET_ID


_M130_REVISION = "2019-y-siguientes"


M130_INGRESOS_CASILLA: CasillaId = validated_casilla_id("01")
_M130_RETENCIONES_CASILLA: CasillaId = validated_casilla_id("06")
_M130_AGRARIAN_VOLUME_CASILLA: CasillaId = validated_casilla_id("08")
_M130_AGRARIAN_WITHHELD_CASILLA: CasillaId = validated_casilla_id("10")
_M130_HOME_DEDUCTION_CASILLA: CasillaId = validated_casilla_id("16")
_M100_PAGOS_CASILLA: CasillaId = validated_casilla_id("0604")
_M100_RETENCIONES_TRABAJO_CASILLA: CasillaId = validated_casilla_id("0596")
_M100_TOTAL_PAGOS_CASILLA: CasillaId = validated_casilla_id("0609")
_M100_CUOTA_DIFERENCIAL_CASILLA: CasillaId = validated_casilla_id("0610")
M100_ACTIVITY_INCOME_CASILLA: CasillaId = validated_casilla_id("0171")
_M100_ACTIVITY_EXPENSES_SUMMARY_CASILLA: CasillaId = validated_casilla_id("0199")
_M100_EXPENSES_PREVIOUS_SUM_CASILLA: CasillaId = validated_casilla_id("0218")
M100_NORMAL_DEDUCTIBLE_EXPENSES_CASILLA: CasillaId = validated_casilla_id("0220")


_QUARTER_ORDER = ("1T", "2T", "3T", "4T")
_EXPECTED_CUMULATIVE_C01: dict[str, Decimal] = {
    "1T": Decimal("4000.00"),
    "2T": Decimal("7500.00"),
    "3T": Decimal("9500.00"),
    "4T": Decimal("12000.00"),
}

# Hand-derived quarterly casilla 19 for this persona (no retenciones, no
# agrarian income, no vivienda deduction, no minoracion, original filings). The
# persona keeps cobros y pagos, so its modality is the simplified one and box 02
# adds the RIRPF art. 30.2.4.ª provision: 5 per cent of the cumulative previo
# 3500 / 6300 / 8000 / 9600, which is 175 / 315 / 400 / 480, under the 2.000 cap.
# Casilla 03 is then 3325 / 5985 / 7600 / 9120, casilla 04 (20 per cent) is
# 665 / 1197 / 1520 / 1824, and casilla 05 subtracts the earlier positive
# casilla 07 values, leaving 665 / 532 / 323 / 304.
# oracle: AEAT-MODELO-130-INSTRUCCIONES casillas 02, 03, 04, 05, 07 y 19.
_EXPECTED_M130_C19_BY_PERIOD: dict[str, Decimal] = {
    "1T": Decimal("665.00"),
    "2T": Decimal("532.00"),
    "3T": Decimal("323.00"),
    "4T": Decimal("304.00"),
}
_EXPECTED_M100_ACTIVITY_INCOME = Decimal("12000.00")
_EXPECTED_M100_ACTIVITY_EXPENSES = Decimal("2400.00")
# Hand-derived annual rendimiento neto for the cobros y pagos persona in estimacion directa simplificada.
# Casilla 0180 (ingresos) 12000.00 less the casilla 0220 expenses 2400.00 leaves a rendimiento previo of
# 9600.00. RIRPF art. 30.2.4.a adds the provision for gastos de dificil justificacion, 5 per cent of that
# previo (7 per cent applies to 2023 only, Ley 35/2006 DA 56), capped at 2.000,00: 480.00. Casilla 0223 is
# therefore 2400.00 + 480.00 = 2880.00 and casilla 0224 is 12000.00 - 2880.00 = 9120.00.
# oracle: AEAT-RENTA-MANUAL, estimacion directa simplificada; RIRPF art. 30.2.4.a.
EXPECTED_M100_ACTIVITY_NET = Decimal("9120.00")
_AUTONOMA_M130_C19_BY_PERIOD: dict[str, Decimal] = {
    "1T": Decimal("300.00"),
    "2T": Decimal("360.00"),
    "3T": Decimal("400.00"),
    "4T": Decimal("460.00"),
}
_AUTONOMA_SALARY_GROSS = Decimal("30000.00")
_AUTONOMA_SALARY_WITHHOLDING = Decimal("4500.00")
_EXPENSE_ROWS: tuple[tuple[str, date, SpendingCategory, Decimal], ...] = (
    ("expense-office", date(YEAR, 2, 20), SpendingCategory.from_registry("material_oficina"), Decimal("500.00")),
    (
        "expense-software",
        date(YEAR, 5, 22),
        SpendingCategory.from_registry("software_suscripcion"),
        Decimal("700.00"),
    ),
    ("expense-phone", date(YEAR, 8, 12), SpendingCategory.from_registry("telefonia_movil"), Decimal("300.00")),
    ("expense-advisory", date(YEAR, 11, 8), SpendingCategory.from_registry("asesoria_fiscal"), Decimal("900.00")),
)

# M130 manual casillas (retenciones / agrarian / vivienda / prior
# autoliquidaciones). All zero for this pure-estimación-directa, no-retención
# persona. Casilla 02 (Gastos) is a source-owned bound casilla
# (ledger renta gasto aggregation) and is NOT supplied here: the persisted
# expense rows drive it through the live source resolver.
_M130_MANUAL_INPUTS: dict[CasillaId, Decimal] = {
    _M130_RETENCIONES_CASILLA: Decimal("0"),
    _M130_HOME_DEDUCTION_CASILLA: Decimal("0"),
    M130_PRIOR_RETURN_RESULT_CASILLA: Decimal("0"),
}

# The M100 0604 formula sums BOTH the M130 and M131 pagos relations; this persona
# files no estimacion objetiva, so the M131 leg resolves as not-applicable zero
# without any synthetic M131 filings.


def persist_autonoma_style_ledger(secure_objects: SecureObjectRepository) -> None:
    """Persist Autonoma-shaped annual activity income plus deductible expenses."""
    tx_repo = TransactionCatalogueRepository(bucket_id=BUCKET_ID, objects=secure_objects)
    transactions = tuple(income_transaction(period) for period in _QUARTER_ORDER) + tuple(
        expense_transaction(transaction_id, value_date=value_date, category=category, taxable_base=taxable_base)
        for transaction_id, value_date, category, taxable_base in _EXPENSE_ROWS
    )
    tx_repo.save(
        TransactionCatalogue.from_transactions(transactions),
    )
    InvoiceCatalogueRepository(bucket_id=BUCKET_ID, objects=secure_objects).save(InvoiceCatalogue())


def calculate_and_file_m130_quarter(
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
    wu_repo = WorkUnitCatalogueRepository(bucket_id=BUCKET_ID, objects=secure_objects)
    cr_repo = CalculationRevisionCatalogueRepository(objects=secure_objects)
    tx_repo = TransactionCatalogueRepository(bucket_id=BUCKET_ID, objects=secure_objects)
    invoice_repo = InvoiceCatalogueRepository(bucket_id=BUCKET_ID, objects=secure_objects)
    with bundled_indexed_authority().operation() as operation:
        work_unit = create_work_unit(
            bucket_id=BUCKET_ID,
            modelo="130",
            filing_year=YEAR,
            period=Period.from_year_and_code(YEAR, period),
            revision_id=_M130_REVISION,
            ports=WorkLifecyclePorts(
                work_unit_repository=wu_repo,
                bucket_event_repository=BucketEventHistoryRepository(objects=secure_objects),
            ),
            operation=operation,
            clock=T0,
        )
    revision = calculate_revision_from_bucket_aggregation(
        work_unit.work_unit_id,
        casilla_inputs=_M130_MANUAL_INPUTS,
        work_unit_repository=wu_repo,
        calculation_repository=cr_repo,
        transaction_repository=tx_repo,
        invoice_repository=invoice_repo,
        clock=T0,
    ).revision
    persist_filed_revision_observation(
        revision=revision,
        work_unit=work_unit,
        repository=CalculationObservationRepository(objects=secure_objects),
        captured_at=FILE_AT,
        iva_compensation_history_repository=IvaCompensationHistoryRepository(),
    )
    return revision


def _seed_taxpayer_profile() -> None:
    """Seed the single-taxpayer profile M100's profile-sourced bindings consume."""
    # display_name MUST equal the manifest label isolated_runtime_profile created
    # ("Test runtime profile") — CommittedProfileView._validate_cross_store_agreement
    # rejects a label/display_name mismatch as a torn-rename inconsistency.
    record = create_user_profile_record(
        context=profile_creation_context_for_test(),
        setup_state=ProfileSetupState.COMPLETE,
        profile_id=BUCKET_ID,
        facts=persona_facts_beneath(
            (
                UserProfileFact(path="identity.tax_id", value=TAX_ID),
                UserProfileFact(path="identity.name", value="Annual"),
                UserProfileFact(path="identity.surnames", value="Renta Tester"),
                UserProfileFact(path="activities.description", value="design services"),
                # An IAE epigraph outside group 861, so no urban rental is carried on as an activity.
                UserProfileFact(path="activities.iae_epigraph", value="844"),
                UserProfileFact(path="censo.activity_start_date", value=date(2020, 1, 1)),
                *renta_single_taxpayer_facts(birth_date=date(1980, 3, 15)),
                *cash_criterion_facts(YEAR),
            )
        ),
        created_at=T0,
        updated_at=T0,
    )
    seed_test_profile_record(record)


# The activity key an exported direct-estimation block requires and the operator states.
M100_ACTIVITY_KEY_CASILLA: CasillaId = validated_casilla_id("0166")
M100_ACTIVITY_KEY = "A05"


def calculate_m100_annual(
    secure_objects: SecureObjectRepository,
    *,
    casilla_inputs: dict[CasillaId, Decimal] | None = None,
    binding_values: dict[BindingId, Decimal] | None = None,
    text_casilla_inputs: dict[CasillaId, str] | None = None,
) -> CalculationRevision:
    """Run the live M100/2024/0A annual calc, leaving the pagos relations to fold."""
    _seed_taxpayer_profile()
    wu_repo = WorkUnitCatalogueRepository(bucket_id=BUCKET_ID, objects=secure_objects)
    cr_repo = CalculationRevisionCatalogueRepository(objects=secure_objects)
    tx_repo = TransactionCatalogueRepository(bucket_id=BUCKET_ID, objects=secure_objects)
    invoice_repo = InvoiceCatalogueRepository(bucket_id=BUCKET_ID, objects=secure_objects)
    snapshot = published_authority_operation().snapshot("100", filing_year=YEAR, period=M100_ANNUAL_PERIOD)
    with bundled_indexed_authority().operation() as operation:
        work_unit = create_work_unit(
            bucket_id=BUCKET_ID,
            modelo="100",
            filing_year=YEAR,
            period=Period.from_year_and_code(YEAR, M100_ANNUAL_PERIOD),
            revision_id=snapshot.revision.id,
            ports=WorkLifecyclePorts(
                work_unit_repository=wu_repo,
                bucket_event_repository=BucketEventHistoryRepository(objects=secure_objects),
            ),
            operation=operation,
            clock=T0,
        )
    return calculate_revision_from_bucket_aggregation(
        work_unit.work_unit_id,
        casilla_inputs=casilla_inputs,
        text_casilla_inputs=text_casilla_inputs,
        binding_values={**m100_non_relation_zero_bindings(), **(binding_values or {})},
        work_unit_repository=wu_repo,
        calculation_repository=cr_repo,
        transaction_repository=tx_repo,
        invoice_repository=invoice_repo,
        clock=T0,
    ).revision


def test_ledger_drives_m130_quarters_and_folds_into_m100_annual(
    secure_objects: SecureObjectRepository,
) -> None:
    """The full yearly cadence: persisted ledger → 4×M130 → M100 0604 fold-in."""
    _seed_taxpayer_profile()
    persist_autonoma_style_ledger(secure_objects)
    seed_prior_year_m100(secure_objects)

    computed_c19: dict[str, Decimal] = {}
    for period in _QUARTER_ORDER:
        revision = calculate_and_file_m130_quarter(secure_objects, period=period)

        # Transport invariant #1: the FULL bucket-aggregation calc action draws
        # casilla 01 from the persisted ledger (cumulative YTD), not from any
        # manual input — the operator never re-keyed income.
        assert Decimal(revision.casilla_values[M130_INGRESOS_CASILLA]) == _EXPECTED_CUMULATIVE_C01[period], (
            f"{period}: casilla 01 must equal cumulative ledger income "
            f"{_EXPECTED_CUMULATIVE_C01[period]}; got {revision.casilla_values.get(M130_INGRESOS_CASILLA)}"
        )
        computed_c19[period] = Decimal(revision.casilla_values[M130_RESULTADO_FINAL_CASILLA])

    # The four quarterly resultado-final values are hand-derived from the ledger,
    # distinct and strictly positive, so a coincidental sum or a single-quarter
    # copy cannot satisfy the annual fold assertion below.
    assert computed_c19 == _EXPECTED_M130_C19_BY_PERIOD, computed_c19

    annual = calculate_m100_annual(secure_objects)

    assert Decimal(annual.casilla_values[M100_ACTIVITY_INCOME_CASILLA]) == _EXPECTED_M100_ACTIVITY_INCOME
    assert Decimal(annual.casilla_values[_M100_EXPENSES_PREVIOUS_SUM_CASILLA]) == _EXPECTED_M100_ACTIVITY_EXPENSES
    assert Decimal(annual.casilla_values[M100_NORMAL_DEDUCTIBLE_EXPENSES_CASILLA]) == _EXPECTED_M100_ACTIVITY_EXPENSES
    assert Decimal(annual.casilla_values[M100_ACTIVIDAD_ECONOMICA_NET_INCOME_CASILLA]) == EXPECTED_M100_ACTIVITY_NET

    # Transport invariant #2: the annual M100 0604 credits what the four M130
    # quarters paid (M131 folds as not-applicable zero). Every quarter is an
    # original with a positive casilla 19, so each paid exactly its casilla 19.
    # oracle: AEAT-MODELO-130-INSTRUCCIONES casillas 18, 19 y (4) Ingreso; 665 + 532 + 323 + 304 = 1824.00,
    # which is also 20 per cent of the 9120.00 fourth-quarter casilla 03.
    casilla_0604 = Decimal(annual.casilla_values[_M100_PAGOS_CASILLA])
    assert casilla_0604 == Decimal("1824.00"), casilla_0604


def test_a_locally_filed_quarter_records_the_kind_its_revision_states(
    secure_objects: SecureObjectRepository,
) -> None:
    """A revision with no amendment identity is an original, stated by the local filing itself."""
    _seed_taxpayer_profile()
    persist_autonoma_style_ledger(secure_objects)
    seed_prior_year_m100(secure_objects)
    revision = calculate_and_file_m130_quarter(secure_objects, period="1T")
    assert revision.amendment_identity is None

    stored = CalculationObservationRepository(objects=secure_objects).load(
        observation_key("130", Period.from_year_and_code(YEAR, "1T"))
    )

    assert stored is not None
    assert stored.filing_kind is not None
    assert stored.filing_kind.basis is FilingKindEvidenceBasis.LOCAL_REVISION
    assert stored.filing_kind.admitted_kind is FilingDeclarationKind.ORIGINAL
    assert stored.filing_kind.source_locator is not None
    assert stored.filing_kind.source_locator.startswith("local-filing:")


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
    persist_autonoma_style_ledger(secure_objects)
    seed_prior_year_m100(secure_objects)

    for period, c19_value in _AUTONOMA_M130_C19_BY_PERIOD.items():
        import_official_m130_result_observation(secure_objects, period=period, c19_value=c19_value)

    annual = calculate_m100_annual(
        secure_objects,
        text_casilla_inputs={M100_ACTIVITY_KEY_CASILLA: M100_ACTIVITY_KEY},
    )

    assert Decimal(annual.casilla_values[M100_ACTIVITY_INCOME_CASILLA]) == Decimal("12000.00")
    assert Decimal(annual.casilla_values[_M100_ACTIVITY_EXPENSES_SUMMARY_CASILLA]) == Decimal("2400.00")
    assert Decimal(annual.casilla_values[_M100_EXPENSES_PREVIOUS_SUM_CASILLA]) == Decimal("2400.00")
    assert Decimal(annual.casilla_values[M100_NORMAL_DEDUCTIBLE_EXPENSES_CASILLA]) == Decimal("2400.00")
    # 12000.00 - (2400.00 + 5 per cent of the 9600.00 previo = 480.00) = 9120.00, as derived at the constant.
    assert Decimal(annual.casilla_values[M100_ACTIVIDAD_ECONOMICA_NET_INCOME_CASILLA]) == EXPECTED_M100_ACTIVITY_NET
    assert Decimal(annual.casilla_values[_M100_PAGOS_CASILLA]) == Decimal("1520.00")
    assert Decimal(annual.casilla_values[_M100_PAGOS_CASILLA]) == sum(
        _AUTONOMA_M130_C19_BY_PERIOD.values(),
        Decimal("0"),
    )

    report = verify_revision_for_test(
        annual.calculation_revision_id,
        certificate_secret_backend_factory=build_test_certificate_secret_backend_factory(),
        verification_repositories=build_test_verification_repository_bundle(),
        actor="autonoma-cli-rerun",
        workflow_profile=autonomaworkflow_profile(),
        settings=ready_clave_settings(TAX_ID),
        operator_scope_ports=OPERATOR_SCOPE_PORTS,
    )

    assert report.calculation_revision_id == annual.calculation_revision_id
    assert report.granted_verificado_completo is True, report.findings
    assert not [finding for finding in report.findings if finding.severity.value == "blocking"]


def test_autonoma_m100_salary_certificate_retenciones_export_replays_verified_total_pagos(
    secure_objects: SecureObjectRepository,
    tmp_path: Path,
) -> None:
    """Verified salary withholding from the payer's certificate replays through verify and XML export."""
    _seed_taxpayer_profile()
    persist_autonoma_style_ledger(secure_objects)
    seed_prior_year_m100(secure_objects)
    seed_payer_certificate(
        operation=published_authority_operation(),
        taxpayer_tax_id=TAX_ID,
        ejercicio=YEAR,
        payer_tax_id="B00010082",
        income_class=RetencionSoportadaClase.TRABAJO,
        retencion=_AUTONOMA_SALARY_WITHHOLDING,
        importe_integro_dinerario=_AUTONOMA_SALARY_GROSS,
    )

    for period, c19_value in _AUTONOMA_M130_C19_BY_PERIOD.items():
        import_official_m130_result_observation(secure_objects, period=period, c19_value=c19_value)

    annual = calculate_m100_annual(
        secure_objects,
        casilla_inputs={validated_casilla_id("0003"): _AUTONOMA_SALARY_GROSS},
        text_casilla_inputs={M100_ACTIVITY_KEY_CASILLA: M100_ACTIVITY_KEY},
    )

    assert Decimal(annual.casilla_values[M100_ACTIVITY_INCOME_CASILLA]) == Decimal("12000.00")
    assert Decimal(annual.casilla_values[_M100_EXPENSES_PREVIOUS_SUM_CASILLA]) == Decimal("2400.00")
    assert Decimal(annual.casilla_values[M100_NORMAL_DEDUCTIBLE_EXPENSES_CASILLA]) == Decimal("2400.00")
    # 12000.00 - (2400.00 + 5 per cent of the 9600.00 previo = 480.00) = 9120.00, as derived at the constant.
    assert Decimal(annual.casilla_values[M100_ACTIVIDAD_ECONOMICA_NET_INCOME_CASILLA]) == EXPECTED_M100_ACTIVITY_NET
    assert Decimal(annual.casilla_values[_M100_RETENCIONES_TRABAJO_CASILLA]) == _AUTONOMA_SALARY_WITHHOLDING
    assert Decimal(annual.casilla_values[_M100_PAGOS_CASILLA]) == Decimal("1520.00")
    assert Decimal(annual.casilla_values[_M100_TOTAL_PAGOS_CASILLA]) == Decimal("6020.00")

    report = verify_revision_for_test(
        annual.calculation_revision_id,
        certificate_secret_backend_factory=build_test_certificate_secret_backend_factory(),
        verification_repositories=build_test_verification_repository_bundle(),
        actor="autonoma-cli-rerun",
        workflow_profile=autonomaworkflow_profile(),
        settings=ready_clave_settings(TAX_ID),
        operator_scope_ports=OPERATOR_SCOPE_PORTS,
    )

    assert report.calculation_revision_id == annual.calculation_revision_id
    assert report.granted_verificado_completo is True, report.findings
    assert not [finding for finding in report.findings if finding.severity.value == "blocking"]

    # ``Aux/VERSION`` names this product build, not the selected authority.
    # The export boundary derives it from PACKAGE_VERSION and writes a complete
    # mandatory Aux block before dictionary-addressed financial meaning.
    output = tmp_path / "modelo-100-2024-0A.xml"
    receipt = export_revision_for_test(
        ModeloExportCommand(
            calculation_revision_id=annual.calculation_revision_id,
            output_path=output,
            actor="autonoma-cli-rerun",
        ),
        workflow_profile=autonomaworkflow_profile(),
        export_ports=modelo_export_ports_for_test(
            bucket_id=BUCKET_ID,
            taxpayer_tax_id=TAX_ID,
            secure_objects=secure_objects,
        ),
    )

    payload = output.read_bytes()
    root = DefusedElementTree.fromstring(payload)
    assert receipt.output_path == output
    assert receipt.byte_size == len(payload)
    assert root.findtext("./Aux/Idioma") == "E"
    assert root.findtext("./Aux/VERSION") == PACKAGE_VERSION.replace(".", "")


def test_m100_base_only_gate_still_blocks_missing_renta_taxable_base(
    secure_objects: SecureObjectRepository,
) -> None:
    """M100 does not demand IVA-only facts, but still blocks missing Renta base facts."""
    _seed_taxpayer_profile()
    seed_prior_year_m100(secure_objects)
    transactions = (
        *(income_transaction(period) for period in _QUARTER_ORDER),
        expense_transaction(
            "expense-missing-base",
            value_date=date(YEAR, 2, 20),
            category=SpendingCategory.from_registry("material_oficina"),
            taxable_base=Decimal("500.00"),
        ).model_copy(update={"taxable_base": None}),
    )
    TransactionCatalogueRepository(bucket_id=BUCKET_ID, objects=secure_objects).save(
        TransactionCatalogue.from_transactions(transactions),
    )
    InvoiceCatalogueRepository(bucket_id=BUCKET_ID, objects=secure_objects).save(InvoiceCatalogue())

    with pytest.raises(ModeloLedgerPreflightBlockedError) as exc_info:
        calculate_m100_annual(secure_objects)

    assert exc_info.value.translated_message == "application.modelo.errors.ledger_preflight_blocked_movement"
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
    persist_autonoma_style_ledger(secure_objects)
    seed_prior_year_m100(secure_objects)
    for period in _QUARTER_ORDER:
        calculate_and_file_m130_quarter(secure_objects, period=period)
    annual = calculate_m100_annual(secure_objects)

    report = verify_revision_for_test(
        annual.calculation_revision_id,
        certificate_secret_backend_factory=build_test_certificate_secret_backend_factory(),
        verification_repositories=build_test_verification_repository_bundle(),
        actor="system",
        workflow_profile=TaxpayerProfile(tax_id="X0001500M", iva_regime=IVARegime("GENERAL")),
        settings=ready_clave_settings("X0001500M"),
        operator_scope_ports=OPERATOR_SCOPE_PORTS,
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

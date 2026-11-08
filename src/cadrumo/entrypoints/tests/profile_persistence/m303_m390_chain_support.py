"""Shared fixtures, seeding and calculation helpers for the Modelo 303 to Modelo 390 end-to-end suites."""

from __future__ import annotations

from dataclasses import replace
from datetime import UTC, date, datetime
from decimal import Decimal
from pathlib import Path

import pytest

from cadrumo.adapters.persistence.profile.buckets import BucketEventHistoryRepository
from cadrumo.adapters.persistence.profile.calculation_observations import (
    CalculationObservationRepository,
    IvaWalletDecisionRepository,
)
from cadrumo.adapters.persistence.profile.invoices import InvoiceCatalogueRepository
from cadrumo.adapters.persistence.profile.iva_compensation_history import IvaCompensationHistoryRepository
from cadrumo.adapters.persistence.profile.modelos_calculation import CalculationRevisionCatalogueRepository
from cadrumo.adapters.persistence.profile.modelos_filing import ModeloRecordCatalogueRepository
from cadrumo.adapters.persistence.profile.modelos_verification_reports import VerificationReportCatalogueRepository
from cadrumo.adapters.persistence.profile.modelos_work_units import WorkUnitCatalogueRepository
from cadrumo.adapters.persistence.profile.prorrata_register import ProrrataRegisterRepository
from cadrumo.adapters.persistence.profile.tests.modelo_export_ports_support import modelo_export_ports_for_test
from cadrumo.adapters.persistence.profile.transactions import TransactionCatalogueRepository
from cadrumo.adapters.persistence.storage.operator_scope import build_operator_scope_ports
from cadrumo.adapters.persistence.storage.sql.secure_objects import SecureObjectRepository
from cadrumo.adapters.persistence.storage.tests.profile_capsule_runtime import seed_test_profile_record
from cadrumo.application.calculations.tests.filing_evidence import general_m303_filing_evidence
from cadrumo.application.modelo.action_errors import CalculationRevisionStateError
from cadrumo.application.modelo.calculation_bucket_actions import (
    BucketAggregationCalculationResult,
    calculate_modelo_revision_from_bucket_aggregation_with_diagnostics,
)
from cadrumo.application.modelo.calculation_note_gate import ModeloCalculationBlockedError
from cadrumo.application.modelo.export import export_modelo_revision
from cadrumo.application.modelo.export_contracts import ModeloExportCommand
from cadrumo.application.modelo.filing_action_ports import FilingActionPorts
from cadrumo.application.modelo.filing_actions import file_modelo_revision
from cadrumo.application.modelo.verification_actions import verify_modelo_revision_with_preconditions
from cadrumo.application.modelo.verification_repository_ports import VerificationRepositoryBundle
from cadrumo.application.modelo.work_form_models import ModeloFormOrigin, address_key
from cadrumo.application.modelo.work_form_service import load_modelo_work_form
from cadrumo.application.modelo.work_lifecycle import create_work_unit
from cadrumo.application.modelo.work_lifecycle_ports import WorkLifecyclePorts
from cadrumo.application.user_profile.tests.persona_profile_facts import persona_facts_beneath
from cadrumo.core.casilla_id import CasillaId, validated_casilla_id
from cadrumo.core.external_constants import OutputLanguage
from cadrumo.core.period import Period
from cadrumo.core.prior_domiciliation_election import PriorDomiciliationElection
from cadrumo.core.prorrata_register import ProrrataProvisionalProvenance, ProrrataRegisterRegime
from cadrumo.core.result_disposition import ResultDisposition
from cadrumo.domain.calculations.registry.authority import PinnedAuthorityOperation, bundled_indexed_authority
from cadrumo.domain.calculations.registry.schema_input_kind import InputKind
from cadrumo.domain.calculations.registry.tests.authored_editions import split_exercise_revisions
from cadrumo.domain.contribuyente.entity_type import EntityType, LegalEntityForm
from cadrumo.domain.deadlines.models import (
    IVARegime,
    M303RegimeComposition,
    M303TaxTerritory,
    ModeloEnrollment,
    ModeloIVAProfile,
    TaxpayerProfile,
)
from cadrumo.domain.iva_compensation.reconciliation import (
    IvaCompensationAuthoritySource,
    IvaCompensationReconciliationDecision,
)
from cadrumo.domain.modelos.calculation_revision import (
    CalculationRevision,
)
from cadrumo.domain.modelos.codes import ModeloCode
from cadrumo.domain.modelos.verification_report import VerificationReport
from cadrumo.domain.modelos.work_unit import WorkUnit
from cadrumo.domain.prorrata_register.register import ProrrataRegister, ProrrataRegisterEntry
from cadrumo.domain.user_profile.values import ProfileSetupState, UserProfileFact, create_user_profile_record
from cadrumo.entrypoints.adapter_composition_work_ports import (
    build_calculation_action_ports,
    build_filing_action_ports,
    build_verification_repository_bundle,
)
from cadrumo.entrypoints.tests.profile_persistence.m303_annual_ledger_support import (
    BUCKET_ID,
    T0,
    YEAR,
    product_software_identity,
)
from cadrumo.entrypoints.tests.profile_persistence.modelo_303_export_support import (
    MODELO_303_MANUAL_RESULTADO_CASILLA_ZEROS,
)
from cadrumo.entrypoints.tests.profile_persistence.verification_repository_support import (
    build_test_certificate_secret_backend_factory,
)
from cadrumo.tests.env_scope import ready_clave_settings

from ....adapters.persistence.profile.tests.published_authority_support import published_authority_operation
from ....application.modelo.tests.filed_observation_fixture import persist_filed_revision_observation

OPERATOR_SCOPE_PORTS = build_operator_scope_ports()


@pytest.fixture
def bucket_id() -> str:
    return BUCKET_ID


TAX_ID = "12345678Z"


# Irene SL files the exercise whose Modelo 303 design the registry splits mid-year, so
# the annual Modelo 390 folds quarters calculated under both designs.
IRENE_YEAR = split_exercise_revisions("303", early_period="2T", late_period="3T")[0].valid_from.year


IRENE_TAX_ID = "B00015016"


FILE_AT = datetime(2025, 4, 10, 12, 0, tzinfo=UTC)


# Her local filings land well after every quarter and the annual summary fell due.
IRENE_FILE_AT = datetime(IRENE_YEAR + 2, 7, 1, 12, 0, tzinfo=UTC)


QUARTER_ORDER = ("1T", "2T", "3T", "4T")


type ComputedM303CasillasByPeriod = dict[str, dict[CasillaId, Decimal]]


# M303 computed-output casillas the M390 reconciliation relations fold.
DEVENGADA_TOTAL: CasillaId = validated_casilla_id("iva.cuota-devengada-total")


DEDUCIBLE_TOTAL: CasillaId = validated_casilla_id("iva.cuota-deducible-total")


RESULTADO: CasillaId = validated_casilla_id("iva.resultado-regimen-general")


CASILLA_59: CasillaId = validated_casilla_id("59")


# M390 annual reconciliation casillas (folded from the four M303 quarters).
M390_DEVENGADA: CasillaId = validated_casilla_id("iva.anual.reconciliacion.devengada-303")


M390_DEDUCIBLE: CasillaId = validated_casilla_id("iva.anual.reconciliacion.deducible-303")


M390_RESULTADO: CasillaId = validated_casilla_id("iva.anual.reconciliacion.resultado-303")


def verification_ports(
    *,
    operation: PinnedAuthorityOperation,
    work_repo: WorkUnitCatalogueRepository,
    calc_repo: CalculationRevisionCatalogueRepository,
    filing_repo: ModeloRecordCatalogueRepository,
    verification_repo: VerificationReportCatalogueRepository,
    event_repo: BucketEventHistoryRepository,
    tx_repo: TransactionCatalogueRepository,
) -> VerificationRepositoryBundle:
    """Compose complete verification ports over the isolated repositories."""
    return replace(
        build_verification_repository_bundle(BUCKET_ID, operation=operation),
        work_unit=work_repo,
        calculation=calc_repo,
        filing=filing_repo,
        verification=verification_repo,
        bucket_event=event_repo,
        transaction=tx_repo,
    )


def filing_ports(
    *,
    work_repo: WorkUnitCatalogueRepository,
    calc_repo: CalculationRevisionCatalogueRepository,
    filing_repo: ModeloRecordCatalogueRepository,
    verification_repo: VerificationReportCatalogueRepository,
    event_repo: BucketEventHistoryRepository,
    wallet_repo: IvaWalletDecisionRepository,
    observation_repo: CalculationObservationRepository,
    operation: PinnedAuthorityOperation,
) -> FilingActionPorts:
    """Compose complete filing ports over the isolated repositories."""
    return replace(
        build_filing_action_ports(bucket_id=BUCKET_ID, operation=operation),
        work_unit_repository=work_repo,
        calculation_repository=calc_repo,
        filing_repository=filing_repo,
        verification_repository=verification_repo,
        bucket_event_repository=event_repo,
        iva_compensation_decision_repository=wallet_repo,
        observation_repository=observation_repo,
        # The observation and its compensation history commit in one backend transaction.
        iva_compensation_history_repository=IvaCompensationHistoryRepository(
            objects=observation_repo.secure_object_repository,
        ),
    )


def wallet_decision(
    *,
    period: str,
    filing_year: int = YEAR,
    taxpayer_nif: str = TAX_ID,
    decided_at: datetime = FILE_AT,
) -> IvaCompensationReconciliationDecision:
    """A neutral (zero, non-blocking) IVA-wallet decision for the quarter."""
    return IvaCompensationReconciliationDecision(
        taxpayer_nif=taxpayer_nif,
        target_year=filing_year,
        target_period=Period.from_year_and_code(filing_year, period),
        target_registry_snapshot_ref=published_authority_operation()
        .snapshot("303", filing_year=filing_year, period=period)
        .snapshot_ref,
        source_registry_snapshot_refs=(),
        selected_authority="aeat_wallet",
        selected_amount=Decimal("0.00"),
        wallet_amount=Decimal("0.00"),
        local_recurrence_amount=None,
        override_amount=None,
        divergence="match",
        blocked=False,
        stale_wallet=False,
        reason_identity="aeat_wallet_validated",
        wallet_captured_at=decided_at,
        authority_sources=(
            IvaCompensationAuthoritySource(
                source_kind="aeat_wallet",
                amount=Decimal("0.00"),
                source_locator=f"test://wallet/{filing_year}/{period}",
                captured_at=decided_at,
                registry_snapshot_refs=(),
            ),
        ),
        decided_at=decided_at,
    )


def store_profile(secure_objects: SecureObjectRepository, *, activity_start_date: date = date(2020, 1, 1)) -> None:
    """Seed the ready taxpayer profile the M303 gates read."""
    seed_test_profile_record(
        create_user_profile_record(
            context=published_authority_operation().profile_create_context(),
            setup_state=ProfileSetupState.COMPLETE,
            profile_id=BUCKET_ID,
            facts=persona_facts_beneath(
                (
                    UserProfileFact(path="identity.tax_id", value=TAX_ID),
                    UserProfileFact(path="identity.name", value="Laura"),
                    UserProfileFact(path="identity.surnames", value="Taller Sol"),
                    UserProfileFact(path="activities.description", value="taller"),
                    UserProfileFact(
                        path="iva.hydrocarbon_deposit_advance_payment_deduction_entitled",
                        value=False,
                    ),
                    UserProfileFact(path="censo.activity_start_date", value=activity_start_date),
                )
            ),
            created_at=T0,
            updated_at=T0,
        ),
    )


def store_irene_sl_profile(secure_objects: SecureObjectRepository) -> None:
    """Seed Irene SL's IVA profile for the late-local-file persona path."""
    seed_test_profile_record(
        create_user_profile_record(
            context=published_authority_operation().profile_create_context(),
            setup_state=ProfileSetupState.COMPLETE,
            profile_id=BUCKET_ID,
            facts=(
                UserProfileFact(path="identity.tax_id", value=IRENE_TAX_ID),
                UserProfileFact(path="identity.legal_name", value="Irene SL"),
                UserProfileFact(path="activities.description", value="consultoria IVA"),
                UserProfileFact(path="tax_residence.ccaa", value="madrid"),
                UserProfileFact(path="tax_residence.jurisdiction_scope", value="common_regime"),
                UserProfileFact(path="iva.regime", value="GENERAL"),
                UserProfileFact(path="iva.m303_regime_composition", value="general"),
                UserProfileFact(path="iva.redeme_enrolled", value=False),
                # Not a gran empresa, as her workflow profile states: the 303 is quarterly (RIVA art. 71.3).
                UserProfileFact(path="censo.large_company", value=False),
                UserProfileFact(path="iva.cash_accounting_regime_enrolled", value=False),
                UserProfileFact(path="iva.voluntary_sii_enrolled", value=False),
                UserProfileFact(
                    path="iva.hydrocarbon_deposit_advance_payment_deduction_entitled",
                    value=False,
                ),
                UserProfileFact(path="taxpayer_type.entity_type", value="legal_entity"),
                UserProfileFact(path="taxpayer_type.legal_entity_form", value="sl"),
                UserProfileFact(path="provenance.source", value="manual_cli"),
                UserProfileFact(path="censo.activity_start_date", value=date(IRENE_YEAR, 1, 1)),
                # The quarterly 303 schedule needs the condition stated as a no.
                UserProfileFact(path="censo.large_company", value=False),
            ),
            created_at=T0,
            updated_at=T0,
        ),
    )


def workflow_profile() -> TaxpayerProfile:
    return TaxpayerProfile(
        tax_id=TAX_ID,
        iva_regime=IVARegime("GENERAL"),
        has_employees=False,
        pays_rent_with_retencion=False,
        does_intracomunitario=True,
        bienes_extranjero_above_threshold=False,
        enrollment=ModeloEnrollment(large_company=False),
        activity_start_date=date(YEAR, 1, 1),
        iva=general_regime_iva_profile(),
    )


def general_regime_iva_profile() -> ModeloIVAProfile:
    """The declared IVA facts a common-territory general-regime filer carries."""
    return ModeloIVAProfile(
        tax_territory=M303TaxTerritory.from_registry("common_regime"),
        regime_composition=M303RegimeComposition.from_registry("general"),
        redeme_enrolled=False,
        cash_accounting_regime_enrolled=False,
        voluntary_sii_enrolled=False,
        hydrocarbon_deposit_advance_payment_deduction_entitled=False,
    )


def ireneworkflow_profile() -> TaxpayerProfile:
    return TaxpayerProfile(
        tax_id=IRENE_TAX_ID,
        entity_type=EntityType.from_registry("legal_entity"),
        legal_entity_form=LegalEntityForm.from_registry("sl"),
        iva_regime=IVARegime("GENERAL"),
        has_employees=False,
        pays_rent_with_retencion=False,
        does_intracomunitario=False,
        bienes_extranjero_above_threshold=False,
        enrollment=ModeloEnrollment(large_company=False),
        activity_start_date=date(IRENE_YEAR, 1, 1),
    )


def calculate_m303_quarter_revision(
    secure_objects: SecureObjectRepository,
    *,
    period: str,
    filing_year: int = YEAR,
    taxpayer_nif: str = TAX_ID,
    calculated_at: datetime = FILE_AT,
    extra_casilla_inputs: dict[CasillaId, Decimal] | None = None,
    operation: PinnedAuthorityOperation,
) -> tuple[WorkUnit, CalculationRevision]:
    """Run the live bucket-aggregation M303 calc for one quarter without projecting filed observations."""
    work_unit, result = calculate_m303_quarter(
        secure_objects,
        period=period,
        filing_year=filing_year,
        taxpayer_nif=taxpayer_nif,
        calculated_at=calculated_at,
        extra_casilla_inputs=extra_casilla_inputs,
        operation=operation,
    )
    return work_unit, result.revision


def calculate_m303_quarter(
    secure_objects: SecureObjectRepository,
    *,
    period: str,
    filing_year: int = YEAR,
    taxpayer_nif: str = TAX_ID,
    calculated_at: datetime = FILE_AT,
    extra_casilla_inputs: dict[CasillaId, Decimal] | None = None,
    extra_binding_values: dict[str, Decimal] | None = None,
    operation: PinnedAuthorityOperation,
) -> tuple[WorkUnit, BucketAggregationCalculationResult]:
    """Run the live bucket-aggregation M303 calc for one quarter and keep its source diagnostics."""
    wu_repo = WorkUnitCatalogueRepository(bucket_id=BUCKET_ID, objects=secure_objects)
    CalculationRevisionCatalogueRepository(objects=secure_objects)
    BucketEventHistoryRepository(objects=secure_objects)
    TransactionCatalogueRepository(bucket_id=BUCKET_ID, objects=secure_objects)
    typed_period = Period.from_year_and_code(filing_year, period)
    source_revision = (
        published_authority_operation().snapshot("303", filing_year=filing_year, period=typed_period.registry_token)
    ).revision
    # Only casillas the selected revision leaves manual take the fixture zeros;
    # a revision that binds one of them owns its value through the bucket.
    bound_casilla_ids = {casilla.id for casilla in source_revision.casillas if casilla.input_kind == InputKind.BOUND}
    manual_zeros = {
        casilla_id: value
        for casilla_id, value in MODELO_303_MANUAL_RESULTADO_CASILLA_ZEROS.items()
        if casilla_id not in bound_casilla_ids
    }
    work_unit = create_work_unit(
        bucket_id=BUCKET_ID,
        modelo="303",
        filing_year=filing_year,
        period=typed_period,
        revision_id=source_revision.id,
        ports=WorkLifecyclePorts(
            work_unit_repository=wu_repo, bucket_event_repository=BucketEventHistoryRepository(objects=secure_objects)
        ),
        clock=T0,
        operation=operation,
    )
    decision = wallet_decision(
        period=period, filing_year=filing_year, taxpayer_nif=taxpayer_nif, decided_at=calculated_at
    )
    IvaWalletDecisionRepository(objects=secure_objects).save_decision(decision)
    with bundled_indexed_authority().operation() as operation:
        result = calculate_modelo_revision_from_bucket_aggregation_with_diagnostics(
            work_unit.work_unit_id,
            ports=build_calculation_action_ports(bucket_id=BUCKET_ID, operation=operation),
            actor="system",
            # Manual, formula-operand "resultado" casillas (58/68/70/76/77/109/18)
            # the fichero-BOE completeness manifest requires but the engine never
            # auto-zero-fills; see ``_MODELO_303_MANUAL_RESULTADO_CASILLA_ZEROS``.
            casilla_inputs={**manual_zeros, **(extra_casilla_inputs or {})},
            binding_values={
                # No prior-period compensación carry in this scenario (each quarter
                # is net-positive); autoconsumo del promotor is nil for this filer.
                "modelo-303-compensacion-pendiente-anteriores": Decimal("0.00"),
                "modelo-303-autoconsumo-promotor-base": Decimal("0.00"),
                **(extra_binding_values or {}),
            },
            iva_compensation_decision=decision,
            filing_instance_evidence=general_m303_filing_evidence(
                typed_period,
                reference=f"test:e2e-ledger-m303:{period}",
                operation=operation,
            ),
            clock=calculated_at,
        )
    return work_unit, result


def calculate_and_file_m303_quarter(
    secure_objects: SecureObjectRepository,
    *,
    period: str,
    extra_casilla_inputs: dict[CasillaId, Decimal] | None = None,
    operation: PinnedAuthorityOperation,
) -> CalculationRevision:
    """Run the live bucket-aggregation M303 calc for one quarter and project its filed observation."""
    work_unit, revision = calculate_m303_quarter_revision(
        secure_objects, period=period, extra_casilla_inputs=extra_casilla_inputs, operation=operation
    )
    persist_filed_revision_observation(
        revision=revision,
        work_unit=work_unit,
        repository=CalculationObservationRepository(objects=secure_objects),
        captured_at=FILE_AT,
        result_disposition=ResultDisposition.INGRESO,
        iva_compensation_history_repository=IvaCompensationHistoryRepository(),
    )
    return revision


def calculate_m390_annual(
    secure_objects: SecureObjectRepository,
    *,
    filing_year: int = YEAR,
    operation: PinnedAuthorityOperation,
    binding_values: dict[str, Decimal] | None = None,
) -> CalculationRevision:
    """Run the live M390/annual calc, leaving the 303-reconciliation relations to fold."""
    wu_repo = WorkUnitCatalogueRepository(bucket_id=BUCKET_ID, objects=secure_objects)
    CalculationRevisionCatalogueRepository(objects=secure_objects)
    TransactionCatalogueRepository(bucket_id=BUCKET_ID, objects=secure_objects)
    InvoiceCatalogueRepository(objects=secure_objects)
    snapshot = published_authority_operation().snapshot("390", filing_year=filing_year, period="0A")
    work_unit = create_work_unit(
        bucket_id=BUCKET_ID,
        modelo="390",
        filing_year=filing_year,
        period=Period.from_year_and_code(filing_year, "0A"),
        revision_id=snapshot.revision.id,
        ports=WorkLifecyclePorts(
            work_unit_repository=wu_repo, bucket_event_repository=BucketEventHistoryRepository(objects=secure_objects)
        ),
        clock=T0,
        operation=operation,
    )
    with bundled_indexed_authority().operation() as operation:
        return calculate_modelo_revision_from_bucket_aggregation_with_diagnostics(
            work_unit.work_unit_id,
            ports=build_calculation_action_ports(bucket_id=BUCKET_ID, operation=operation),
            binding_values=binding_values or {},
            clock=FILE_AT,
        ).revision


def non_official_local_chain_advisory_periods(report: VerificationReport) -> set[str]:
    periods: set[str] = set()
    for finding in report.findings:
        if finding.message_locale_key != "application.modelo.findings.cross_period_non_official_local_chain.message":
            continue
        facts = finding.message_facts
        if facts.get("source_modelo") != "303" or facts.get("origin_code") != "registry_relation":
            continue
        source_period = facts.get("source_period")
        if isinstance(source_period, str) and source_period in QUARTER_ORDER:
            periods.add(source_period)
    return periods


# The seeded year is the AEAT prorrata general example (see PRORRATA_QUARTER_FACTS).
PRORRATA_PROVISIONAL_PERCENTAGE = Decimal("73")


PRORRATA_VOLUMEN_CON_DERECHO: CasillaId = validated_casilla_id("iva.prorrata-volumen-con-derecho")


PRORRATA_VOLUMEN_TOTAL: CasillaId = validated_casilla_id("iva.prorrata-volumen-total")


SOPORTADO_INTERIORES: CasillaId = validated_casilla_id("iva.soportado.interiores")


CASILLA_44: CasillaId = validated_casilla_id("44")


CASILLA_45: CasillaId = validated_casilla_id("45")


M390_PRORRATA_REGULARIZACION: CasillaId = validated_casilla_id("iva.anual.regularizacion-prorrata-definitiva")


M390_INTERIORES_CORRIENTES_CUOTA: CasillaId = validated_casilla_id(
    "iva.anual.deducible.interiores-corrientes.soportado.cuota"
)


# The manual's printed figures, independent of the engine.
MANUAL_PRACTISED_DEDUCTIONS_1T_3T = {"1T": Decimal("292.00"), "2T": Decimal("306.60"), "3T": Decimal("335.80")}


MANUAL_4T_DEFINITIVE_DEDUCTION = Decimal("89.60")


MANUAL_EXCESO_DE_DEDUCCION = Decimal("-217.60")


MANUAL_4T_CASILLA_45 = Decimal("-128.00")


MANUAL_YEAR_DEDUCTIONS = Decimal("806.40")


MANUAL_YEAR_INTERIORES_CORRIENTES_CUOTA = Decimal("1024.00")


def save_general_prorrata_register(secure_objects: SecureObjectRepository) -> None:
    """Declare the general prorrata with the provisional percentage carried from the prior year."""
    prior_year = YEAR - 1
    ProrrataRegisterRepository(bucket_id=BUCKET_ID, objects=secure_objects).save(
        ProrrataRegister(
            entries=(
                ProrrataRegisterEntry(
                    ejercicio=YEAR,
                    regime=ProrrataRegisterRegime.from_registry("general"),
                    especial_transition=None,
                    provisional_percentage=PRORRATA_PROVISIONAL_PERCENTAGE,
                    provisional_provenance=ProrrataProvisionalProvenance.from_registry("carried_prior_definitiva"),
                    source_observation_ref=f"303:{prior_year}:4T",
                    source_registry_snapshot_refs=(
                        published_authority_operation()
                        .snapshot("303", filing_year=prior_year, period="4T")
                        .snapshot_ref,
                    ),
                ),
            ),
        )
    )


def assert_form_states_no_figure(
    secure_objects: SecureObjectRepository,
    casilla_ids: tuple[CasillaId, ...],
    *,
    operation: PinnedAuthorityOperation,
) -> None:
    """The editor form shows each box as not worked out, with no value, rather than an imported or summed zero."""
    with bundled_indexed_authority().operation() as form_operation:
        form = load_modelo_work_form(
            BUCKET_ID,
            ModeloCode("303"),
            YEAR,
            Period.from_year_and_code(YEAR, "4T"),
            operation=form_operation,
            work_unit_repository=WorkUnitCatalogueRepository(bucket_id=BUCKET_ID, objects=secure_objects),
            calculation_repository=CalculationRevisionCatalogueRepository(objects=secure_objects),
            verification_repository=VerificationReportCatalogueRepository(objects=secure_objects),
            admission=None,
            language=OutputLanguage.EN,
        ).form
    fields = {address_key(field.address): field for field in form.fields()}
    for casilla_id in casilla_ids:
        field = fields[("casilla", casilla_id)]
        assert field.origin is ModeloFormOrigin.CALCULATION_FAILED
        assert field.value is None


def assert_verify_export_and_file_refused(
    secure_objects: SecureObjectRepository,
    revision: CalculationRevision,
    tmp_path: Path,
    *,
    operation: PinnedAuthorityOperation,
) -> None:
    """Verify refuses on the unresolved-binding note; export and local filing refuse the unverified draft."""
    wu_repo = WorkUnitCatalogueRepository(bucket_id=BUCKET_ID, objects=secure_objects)
    cr_repo = CalculationRevisionCatalogueRepository(objects=secure_objects)
    filing_repo = ModeloRecordCatalogueRepository(objects=secure_objects)
    vr_repo = VerificationReportCatalogueRepository(objects=secure_objects)
    event_repo = BucketEventHistoryRepository(objects=secure_objects)
    tx_repo = TransactionCatalogueRepository(bucket_id=BUCKET_ID, objects=secure_objects)

    with (
        bundled_indexed_authority().operation() as verify_operation,
        pytest.raises(ModeloCalculationBlockedError) as verify_refusal,
    ):
        verify_modelo_revision_with_preconditions(
            revision.calculation_revision_id,
            certificate_secret_backend_factory=build_test_certificate_secret_backend_factory(),
            verification_repositories=verification_ports(
                operation=verify_operation,
                work_repo=wu_repo,
                calc_repo=cr_repo,
                filing_repo=filing_repo,
                verification_repo=vr_repo,
                event_repo=event_repo,
                tx_repo=tx_repo,
            ),
            actor="operator",
            workflow_profile=workflow_profile(),
            settings=ready_clave_settings(TAX_ID),
            clock=FILE_AT,
            operator_scope_ports=OPERATOR_SCOPE_PORTS,
            operation=verify_operation,
        )
    assert (verify_refusal.value.context or {})["reason"] == "unresolved_binding"

    # The refused check leaves the draft unverified, so export and local filing
    # refuse it on state before their own calculation-note gates are reached.
    output_path = tmp_path / f"modelo-303-{YEAR}-4T.boe"
    with (
        bundled_indexed_authority().operation() as export_operation,
        pytest.raises(CalculationRevisionStateError) as export_refusal,
    ):
        export_modelo_revision(
            ModeloExportCommand(
                calculation_revision_id=revision.calculation_revision_id,
                output_path=output_path,
                actor="operator",
                prior_domiciliation_election=PriorDomiciliationElection.KEEP,
            ),
            workflow_profile=workflow_profile(),
            export_ports=modelo_export_ports_for_test(
                product_software_identity=product_software_identity(),
                bucket_id=BUCKET_ID,
                taxpayer_tax_id=TAX_ID,
                secure_objects=secure_objects,
                work_unit=wu_repo,
                calculation=cr_repo,
                filing=filing_repo,
                verification=vr_repo,
                bucket_event=event_repo,
            ),
            operation=export_operation,
            clock=FILE_AT,
        )
    assert export_refusal.value.translated_message == "application.modelo.errors.export_revision_state_refused"
    assert not output_path.exists()

    with bundled_indexed_authority().operation() as file_operation, pytest.raises(CalculationRevisionStateError):
        file_modelo_revision(
            revision.calculation_revision_id,
            approved_verification_report_id="verification-report-never-granted",
            certificate_secret_backend_factory=build_test_certificate_secret_backend_factory(),
            actor="operator",
            workflow_profile=workflow_profile(),
            ports=filing_ports(
                work_repo=wu_repo,
                calc_repo=cr_repo,
                filing_repo=filing_repo,
                verification_repo=vr_repo,
                event_repo=event_repo,
                wallet_repo=IvaWalletDecisionRepository(objects=secure_objects),
                observation_repo=CalculationObservationRepository(objects=secure_objects),
                operation=file_operation,
            ),
            clock=FILE_AT,
            operator_scope_ports=OPERATOR_SCOPE_PORTS,
            operation=file_operation,
        )
    assert not filing_repo.load().records


TIER_SCREEN_REASONS = frozenset(
    {"precedence_tier_divergence", "precedence_tier_divergence_advisory", "operator_override_diverges_from_computed"}
)


CASILLA_44_BINDING = "modelo-303-prorrata-regularizacion-casilla-44"


def tier_screen_reasons(result: BucketAggregationCalculationResult) -> set[str]:
    """Every tier-screen reason the calculation raised, persisted or shown."""
    persisted = {str(issue.reason) for issue in result.revision.source_issues}
    shown = {str(diagnostic.reason) for diagnostic in result.source_diagnostics}
    return (persisted | shown) & TIER_SCREEN_REASONS

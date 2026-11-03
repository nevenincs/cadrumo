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
from cadrumo.adapters.persistence.profile.catalogue_creation import build_catalogue_creation_ports
from cadrumo.adapters.persistence.profile.invoices import InvoiceCatalogueRepository
from cadrumo.adapters.persistence.profile.iva_compensation_history import IvaCompensationHistoryRepository
from cadrumo.adapters.persistence.profile.modelos_calculation import CalculationRevisionCatalogueRepository
from cadrumo.adapters.persistence.profile.modelos_filing import ModeloRecordCatalogueRepository
from cadrumo.adapters.persistence.profile.modelos_verification_reports import VerificationReportCatalogueRepository
from cadrumo.adapters.persistence.profile.modelos_work_units import WorkUnitCatalogueRepository
from cadrumo.adapters.persistence.profile.prorrata_register import ProrrataRegisterRepository
from cadrumo.adapters.persistence.profile.tests.modelo_export_ports_support import modelo_export_ports_for_test
from cadrumo.adapters.persistence.profile.tests.secure_objects_fixture import secure_objects
from cadrumo.adapters.persistence.profile.transactions import TransactionCatalogueRepository
from cadrumo.adapters.persistence.storage.operator_scope import build_operator_scope_ports
from cadrumo.adapters.persistence.storage.sql.secure_objects import SecureObjectRepository
from cadrumo.adapters.persistence.storage.tests.profile_capsule_runtime import seed_test_profile_record
from cadrumo.application.calculations.tests.filing_evidence import general_m303_filing_evidence
from cadrumo.application.invoices.catalogue_creation import build_catalogue_invoice
from cadrumo.application.modelo.action_errors import CalculationRevisionStateError, ModeloCrossPeriodCleanStateError
from cadrumo.application.modelo.calculate_input import WorkCalculateInputBundle, calculate_modelo_work_revision
from cadrumo.application.modelo.calculation_actions import calculate_modelo_revision_with_trusted_mesh_sources
from cadrumo.application.modelo.calculation_bucket_actions import (
    calculate_modelo_revision_from_bucket_aggregation_with_diagnostics,
)
from cadrumo.application.modelo.calculation_note_gate import (
    ModeloCalculationBlockedError,
    require_no_blocking_calculation_notes,
)
from cadrumo.application.modelo.calculation_operation import calculation_public_result
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
from cadrumo.core.casilla_id import CasillaId, validated_casilla_id
from cadrumo.core.errors.hierarchy import CadrumoError
from cadrumo.core.external_constants import OutputLanguage
from cadrumo.core.i18n.render import tr as render_tr
from cadrumo.core.period import Period
from cadrumo.core.prior_domiciliation_election import PriorDomiciliationElection
from cadrumo.core.prorrata_register import ProrrataProvisionalProvenance, ProrrataRegisterRegime
from cadrumo.core.result_disposition import ResultDisposition
from cadrumo.domain.calculations.registry.authority import PinnedAuthorityOperation, bundled_indexed_authority
from cadrumo.domain.calculations.registry.bindings import CasillaObservation
from cadrumo.domain.calculations.registry.schema_input_kind import InputKind
from cadrumo.domain.calculations.registry.tests.authored_editions import split_exercise_revisions
from cadrumo.domain.contribuyente.entity_type import EntityType, LegalEntityForm
from cadrumo.domain.deadlines.models import (
    IVARegime,
    M303RegimeComposition,
    M303TaxTerritory,
    ModeloIVAProfile,
    TaxpayerProfile,
)
from cadrumo.domain.invoices.tests.catalogue_support import build_invoice_catalogue
from cadrumo.domain.iva.schema import InvoiceKind
from cadrumo.domain.iva_compensation.reconciliation import (
    IvaCompensationAuthoritySource,
    IvaCompensationReconciliationDecision,
)
from cadrumo.domain.modelos.calculation_revision import (
    CalculationRevision,
    derive_calculation_revision_id_from_revision,
)
from cadrumo.domain.modelos.codes import ModeloCode
from cadrumo.domain.modelos.repository import upsert_work_unit
from cadrumo.domain.modelos.source_disagreement import DisagreementDecimalValue, SourceDisagreementRole
from cadrumo.domain.modelos.verification_report import VerificationCompletenessStatus, VerificationReport
from cadrumo.domain.modelos.work_unit import WorkUnit
from cadrumo.domain.prorrata_register.register import ProrrataRegister, ProrrataRegisterEntry
from cadrumo.domain.transactions.enums import TransactionDirection
from cadrumo.domain.transactions.models import TransactionCatalogue
from cadrumo.domain.user_profile.values import ProfileSetupState, UserProfileFact
from cadrumo.domain.user_profile.values import create_user_profile_record as _create_profile_record_for_test
from cadrumo.entrypoints.adapter_composition_work_ports import (
    build_calculation_action_ports,
    build_filing_action_ports,
    build_verification_repository_bundle,
)
from cadrumo.entrypoints.tests.profile_persistence.m303_annual_ledger_support import (
    _BUCKET_ID,
    _T0,
    _YEAR,
    IRENE_ANNUAL_EXPECTED,
    IRENE_QUARTER_FACTS,
    LAURA_ANNUAL_EXPECTED,
    PRORRATA_QUARTER_FACTS,
    persist_year_of_invoices,
    product_software_identity,
)
from cadrumo.entrypoints.tests.profile_persistence.modelo_303_export_support import (
    _MODELO_303_MANUAL_RESULTADO_CASILLA_ZEROS,
)
from cadrumo.entrypoints.tests.profile_persistence.verification_repository_support import (
    build_test_certificate_secret_backend_factory,
)
from cadrumo.tests.env_scope import ready_clave_settings

from ....adapters.persistence.profile.tests.published_authority_support import published_authority_operation
from ....application.modelo.tests.filed_observation_fixture import persist_filed_revision_observation

_OPERATOR_SCOPE_PORTS = build_operator_scope_ports()


pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint]


__all__ = ["secure_objects"]


@pytest.fixture
def bucket_id() -> str:
    return _BUCKET_ID


_TAX_ID = "12345678Z"
# Irene SL files the exercise whose Modelo 303 design the registry splits mid-year, so
# the annual Modelo 390 folds quarters calculated under both designs.
_IRENE_YEAR = split_exercise_revisions("303", early_period="2T", late_period="3T")[0].valid_from.year
_IRENE_TAX_ID = "B12345674"
_FILE_AT = datetime(2025, 4, 10, 12, 0, tzinfo=UTC)
# Her local filings land well after every quarter and the annual summary fell due.
_IRENE_FILE_AT = datetime(_IRENE_YEAR + 2, 7, 1, 12, 0, tzinfo=UTC)

_QUARTER_ORDER = ("1T", "2T", "3T", "4T")
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


def _verification_ports(
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
        build_verification_repository_bundle(_BUCKET_ID, operation=operation),
        work_unit=work_repo,
        calculation=calc_repo,
        filing=filing_repo,
        verification=verification_repo,
        bucket_event=event_repo,
        transaction=tx_repo,
    )


def _filing_ports(
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
        build_filing_action_ports(bucket_id=_BUCKET_ID, operation=operation),
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


def _store_profile(secure_objects: SecureObjectRepository, *, activity_start_date: date = date(2020, 1, 1)) -> None:
    """Seed the ready taxpayer profile the M303 gates read."""
    seed_test_profile_record(
        _create_profile_record_for_test(
            context=published_authority_operation().profile_create_context(),
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
                UserProfileFact(path="censo.activity_start_date", value=activity_start_date),
            ),
            created_at=_T0,
            updated_at=_T0,
        ),
    )


def _store_irene_sl_profile(secure_objects: SecureObjectRepository) -> None:
    """Seed Irene SL's IVA profile for the late-local-file persona path."""
    seed_test_profile_record(
        _create_profile_record_for_test(
            context=published_authority_operation().profile_create_context(),
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


def workflow_profile() -> TaxpayerProfile:
    return TaxpayerProfile(
        tax_id=_TAX_ID,
        iva_regime=IVARegime("GENERAL"),
        has_employees=False,
        pays_rent_with_retencion=False,
        does_intracomunitario=True,
        bienes_extranjero_above_threshold=False,
        activity_start_date=date(_YEAR, 1, 1),
        iva=_general_regime_iva_profile(),
    )


def _general_regime_iva_profile() -> ModeloIVAProfile:
    """The declared IVA facts a common-territory general-regime filer carries."""
    return ModeloIVAProfile(
        tax_territory=M303TaxTerritory.from_registry("common_regime"),
        regime_composition=M303RegimeComposition.from_registry("general"),
        redeme_enrolled=False,
        cash_accounting_regime_enrolled=False,
        voluntary_sii_enrolled=False,
        hydrocarbon_deposit_advance_payment_deduction_entitled=False,
    )


def _ireneworkflow_profile() -> TaxpayerProfile:
    return TaxpayerProfile(
        tax_id=_IRENE_TAX_ID,
        entity_type=EntityType.from_registry("legal_entity"),
        legal_entity_form=LegalEntityForm.from_registry("sl"),
        iva_regime=IVARegime("GENERAL"),
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
    extra_casilla_inputs: dict[CasillaId, Decimal] | None = None,
    operation: PinnedAuthorityOperation,
) -> tuple[WorkUnit, CalculationRevision]:
    """Run the live bucket-aggregation M303 calc for one quarter without projecting filed observations."""
    wu_repo = WorkUnitCatalogueRepository(bucket_id=_BUCKET_ID, objects=secure_objects)
    CalculationRevisionCatalogueRepository(objects=secure_objects)
    BucketEventHistoryRepository(objects=secure_objects)
    TransactionCatalogueRepository(bucket_id=_BUCKET_ID, objects=secure_objects)
    typed_period = Period.from_year_and_code(filing_year, period)
    source_revision = (
        published_authority_operation().snapshot("303", filing_year=filing_year, period=typed_period.registry_token)
    ).revision
    # Only casillas the selected revision leaves manual take the fixture zeros;
    # a revision that binds one of them owns its value through the bucket.
    bound_casilla_ids = {casilla.id for casilla in source_revision.casillas if casilla.input_kind == InputKind.BOUND}
    manual_zeros = {
        casilla_id: value
        for casilla_id, value in _MODELO_303_MANUAL_RESULTADO_CASILLA_ZEROS.items()
        if casilla_id not in bound_casilla_ids
    }
    work_unit = create_work_unit(
        bucket_id=_BUCKET_ID,
        modelo="303",
        filing_year=filing_year,
        period=typed_period,
        revision_id=source_revision.id,
        ports=WorkLifecyclePorts(
            work_unit_repository=wu_repo, bucket_event_repository=BucketEventHistoryRepository(objects=secure_objects)
        ),
        clock=_T0,
        operation=operation,
    )
    decision = _wallet_decision(
        period=period, filing_year=filing_year, taxpayer_nif=taxpayer_nif, decided_at=calculated_at
    )
    IvaWalletDecisionRepository(objects=secure_objects).save_decision(decision)
    with bundled_indexed_authority().operation() as operation:
        revision = calculate_modelo_revision_from_bucket_aggregation_with_diagnostics(
            work_unit.work_unit_id,
            ports=build_calculation_action_ports(bucket_id=_BUCKET_ID, operation=operation),
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
            },
            iva_compensation_decision=decision,
            filing_instance_evidence=general_m303_filing_evidence(
                typed_period,
                reference=f"test:e2e-ledger-m303:{period}",
                operation=operation,
            ),
            clock=calculated_at,
        ).revision
    return work_unit, revision


def _calculate_and_file_m303_quarter(
    secure_objects: SecureObjectRepository,
    *,
    period: str,
    extra_casilla_inputs: dict[CasillaId, Decimal] | None = None,
    operation: PinnedAuthorityOperation,
) -> CalculationRevision:
    """Run the live bucket-aggregation M303 calc for one quarter and project its filed observation."""
    work_unit, revision = _calculate_m303_quarter_revision(
        secure_objects, period=period, extra_casilla_inputs=extra_casilla_inputs, operation=operation
    )
    persist_filed_revision_observation(
        revision=revision,
        work_unit=work_unit,
        repository=CalculationObservationRepository(objects=secure_objects),
        captured_at=_FILE_AT,
        result_disposition=ResultDisposition.INGRESO,
        iva_compensation_history_repository=IvaCompensationHistoryRepository(),
    )
    return revision


def test_first_activity_2026_m303_calculates_linked_invoices_without_joint_return(
    secure_objects: SecureObjectRepository, *, operation: PinnedAuthorityOperation
) -> None:
    """The desktop's first calculation reaches persistence and its public projection with real ledger sources."""
    _store_profile(secure_objects, activity_start_date=date(2026, 1, 1))
    persist_year_of_invoices(
        secure_objects,
        filing_year=2026,
        facts_by_period={
            "1T": {
                "issued_base": Decimal("11428.57"),
                "issued_iva": Decimal("2400.00"),
                "received_base": Decimal("4761.90"),
                "received_iva": Decimal("1000.00"),
                "eu_supply_base": Decimal("0.00"),
                "reverse_charge_base": Decimal("0.00"),
                "reverse_charge_iva": Decimal("0.00"),
            }
        },
    )
    invoice_ports = build_catalogue_creation_ports(bucket_id=_BUCKET_ID)
    issued = build_catalogue_invoice(
        bucket_id=_BUCKET_ID,
        kind=InvoiceKind.ISSUED,
        counterparty_name="Cliente de prueba SL",
        counterparty_tax_id="A58818501",
        counterparty_country="ES",
        invoice_number="EMI-2026-1T",
        issued_at=date(2026, 2, 10),
        taxable_base=Decimal("11428.57"),
        iva_rate=Decimal("21"),
        currency="EUR",
        rate_provider=invoice_ports.rate_provider,
    )
    invoices = InvoiceCatalogueRepository(objects=secure_objects)
    invoices.save(build_invoice_catalogue((*invoices.load().invoices.values(), issued)))
    ledger = TransactionCatalogueRepository(bucket_id=_BUCKET_ID, objects=secure_objects)
    ledger.save(
        TransactionCatalogue.from_transactions(
            tuple(
                transaction.model_copy(update={"invoice_id": issued.invoice_id})
                if transaction.direction is TransactionDirection.INCOMING
                else transaction
                for transaction in ledger.load().transactions.values()
            )
        )
    )
    period = Period.from_year_and_code(2026, "1T")
    snapshot = operation.snapshot("303", filing_year=2026, period="1T")
    work = create_work_unit(
        bucket_id=_BUCKET_ID,
        modelo="303",
        filing_year=2026,
        period=period,
        revision_id=snapshot.revision.id,
        ports=WorkLifecyclePorts(
            work_unit_repository=WorkUnitCatalogueRepository(bucket_id=_BUCKET_ID, objects=secure_objects),
            bucket_event_repository=BucketEventHistoryRepository(objects=secure_objects),
        ),
        clock=datetime(2026, 4, 1, tzinfo=UTC),
        operation=operation,
    )
    evidence = general_m303_filing_evidence(period, reference="test:first-2026", operation=operation)
    assert evidence.m303 is not None and evidence.m303.joint_return_elected is False
    result = calculate_modelo_work_revision(
        work_unit_id=work.work_unit_id,
        actor="operator",
        inputs=WorkCalculateInputBundle.build(
            casilla_inputs={},
            binding_values={},
            enum_binding_values={},
            relation_values={},
            detail_rows=(),
            borrador_snapshot_id=None,
            filing_instance_evidence=evidence,
        ),
        ports=build_calculation_action_ports(bucket_id=_BUCKET_ID, operation=operation),
    )
    public = calculation_public_result(result, operation=operation)
    assert result.revision_published is True
    assert Decimal(result.revision.casilla_values[_DEVENGADA_TOTAL]) == Decimal("2400.00")
    assert Decimal(result.revision.casilla_values[_DEDUCIBLE_TOTAL]) == Decimal("1000.00")
    assert Decimal(result.revision.casilla_values[_RESULTADO]) == Decimal("1400.00")
    assert public.calculation_revision_id == result.revision.calculation_revision_id
    assert len(result.revision.source_transaction_ids) == 2
    assert (
        CalculationRevisionCatalogueRepository(objects=secure_objects)
        .load()
        .get(result.revision.calculation_revision_id)
        == result.revision
    )


@pytest.mark.parametrize(
    ("binding", "caller_value", "expected_reason"),
    [
        ("modelo-303-prorrata-regularizacion-casilla-44", "120", "precedence_tier_divergence"),
        ("modelo-303-autoconsumo-promotor-base", "120", "precedence_tier_divergence_advisory"),
        ("modelo-303-prorrata-regularizacion-casilla-44", "100", None),
    ],
    ids=["filed-disagreement", "working-disagreement", "equal-values"],
)
def test_calculation_persists_the_selected_precedence_value_and_its_disagreement(
    secure_objects: SecureObjectRepository,
    binding: str,
    caller_value: str,
    expected_reason: str | None,
    *,
    operation: PinnedAuthorityOperation,
) -> None:
    """An allowed higher-tier value wins, but its contested filing figure still withholds filing after reload."""
    _store_profile(secure_objects)
    persist_year_of_invoices(secure_objects)
    work, _revision = _calculate_m303_quarter_revision(secure_objects, period="1T", operation=operation)
    calculation = calculate_modelo_revision_with_trusted_mesh_sources(
        work.work_unit_id,
        ports=build_calculation_action_ports(bucket_id=_BUCKET_ID, operation=operation),
        actor="operator",
        casilla_inputs={},
        backend_binding_values={binding: Decimal("100.00")},
        binding_values={binding: Decimal(caller_value)},
        source_provenance=(),
        filing_instance_evidence=general_m303_filing_evidence(
            work.period, reference="test:contested-carry", operation=operation
        ),
        profile=None,
        clock=_FILE_AT,
    )
    publication = calculation.publication
    assert publication.revision.binding_overrides[binding] == caller_value
    if expected_reason is None:
        assert calculation.precedence_diagnostics == ()
        assert publication.revision.source_issues == ()
        return
    (diagnostic,) = calculation.precedence_diagnostics
    assert diagnostic.reason == expected_reason
    assert diagnostic.disagreement is not None
    assert diagnostic.disagreement.selected_role is SourceDisagreementRole.CALLER
    amounts = []
    for source in diagnostic.disagreement.sources:
        assert isinstance(source.value, DisagreementDecimalValue)
        amounts.append(source.value.decimal)
    assert amounts == [Decimal("100.00"), Decimal("120.00")]
    stored = (
        CalculationRevisionCatalogueRepository(objects=secure_objects)
        .load()
        .get(publication.revision.calculation_revision_id)
    )
    assert stored is not None
    if expected_reason == "precedence_tier_divergence":
        (issue,) = tuple(issue for issue in stored.source_issues if issue.reason == "precedence_tier_divergence")
        assert issue.disagreement == diagnostic.disagreement
        with pytest.raises(ModeloCalculationBlockedError):
            require_no_blocking_calculation_notes(stored, action="file")
    else:
        assert stored.source_issues == ()
        require_no_blocking_calculation_notes(stored, action="file")


def test_persisted_m303_ledger_revision_verifies_and_exports(
    secure_objects: SecureObjectRepository, tmp_path: Path, *, operation: PinnedAuthorityOperation
) -> None:
    """Persona-like persisted ledger input verifies under the live revision and exports its fichero."""
    _store_profile(secure_objects)
    stored = persist_year_of_invoices(secure_objects)
    wu_repo = WorkUnitCatalogueRepository(bucket_id=_BUCKET_ID, objects=secure_objects)
    cr_repo = CalculationRevisionCatalogueRepository(objects=secure_objects)
    filing_repo = ModeloRecordCatalogueRepository(objects=secure_objects)
    vr_repo = VerificationReportCatalogueRepository(objects=secure_objects)
    event_repo = BucketEventHistoryRepository(objects=secure_objects)
    tx_repo = TransactionCatalogueRepository(bucket_id=_BUCKET_ID, objects=secure_objects)

    _work_unit, revision = _calculate_m303_quarter_revision(secure_objects, period="1T", operation=operation)
    assert Decimal(revision.casilla_values[_DEVENGADA_TOTAL]) == stored["1T"]["devengada"]
    assert Decimal(revision.casilla_values[_DEDUCIBLE_TOTAL]) == stored["1T"]["deducible"]

    with bundled_indexed_authority().operation() as operation:
        report = verify_modelo_revision_with_preconditions(
            revision.calculation_revision_id,
            certificate_secret_backend_factory=build_test_certificate_secret_backend_factory(),
            verification_repositories=_verification_ports(
                operation=operation,
                work_repo=wu_repo,
                calc_repo=cr_repo,
                filing_repo=filing_repo,
                verification_repo=vr_repo,
                event_repo=event_repo,
                tx_repo=tx_repo,
            ),
            actor="operator",
            workflow_profile=workflow_profile(),
            settings=ready_clave_settings(_TAX_ID),
            clock=_FILE_AT,
            operator_scope_ports=_OPERATOR_SCOPE_PORTS,
            operation=operation,
        ).report

    assert report.granted_verificado_completo is True
    assert report.completeness_status is VerificationCompletenessStatus.COMPLETE
    verified = cr_repo.load().get(revision.calculation_revision_id)
    assert verified is not None
    assert verified.ledger_filing_snapshot is not None
    assert verified.ledger_filing_evidence is not None

    output_path = tmp_path / f"modelo-303-{_YEAR}-1T.boe"
    with bundled_indexed_authority().operation() as operation:
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
                bucket_id=_BUCKET_ID,
                taxpayer_tax_id=_TAX_ID,
                secure_objects=secure_objects,
                work_unit=wu_repo,
                calculation=cr_repo,
                filing=filing_repo,
                verification=vr_repo,
                bucket_event=event_repo,
            ),
            operation=operation,
            clock=_FILE_AT,
        )

    assert output_path.read_bytes().startswith(b"<T3030")


def _calculate_m390_annual(
    secure_objects: SecureObjectRepository,
    *,
    filing_year: int = _YEAR,
    operation: PinnedAuthorityOperation,
    binding_values: dict[str, Decimal] | None = None,
) -> CalculationRevision:
    """Run the live M390/annual calc, leaving the 303-reconciliation relations to fold."""
    wu_repo = WorkUnitCatalogueRepository(bucket_id=_BUCKET_ID, objects=secure_objects)
    CalculationRevisionCatalogueRepository(objects=secure_objects)
    TransactionCatalogueRepository(bucket_id=_BUCKET_ID, objects=secure_objects)
    InvoiceCatalogueRepository(objects=secure_objects)
    snapshot = published_authority_operation().snapshot("390", filing_year=filing_year, period="0A")
    work_unit = create_work_unit(
        bucket_id=_BUCKET_ID,
        modelo="390",
        filing_year=filing_year,
        period=Period.from_year_and_code(filing_year, "0A"),
        revision_id=snapshot.revision.id,
        ports=WorkLifecyclePorts(
            work_unit_repository=wu_repo, bucket_event_repository=BucketEventHistoryRepository(objects=secure_objects)
        ),
        clock=_T0,
        operation=operation,
    )
    with bundled_indexed_authority().operation() as operation:
        return calculate_modelo_revision_from_bucket_aggregation_with_diagnostics(
            work_unit.work_unit_id,
            ports=build_calculation_action_ports(bucket_id=_BUCKET_ID, operation=operation),
            binding_values=binding_values or {},
            clock=_FILE_AT,
        ).revision


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


def test_irene_sl_local_m303_files_support_m390_verify_and_annual_export(
    secure_objects: SecureObjectRepository, tmp_path: Path, *, operation: PinnedAuthorityOperation
) -> None:
    """Irene SL: a late local M303 FILE chain feeds M390 without claiming AEAT acceptance.

    This is the persona path that direct observation seeding did not cover:
    calculate -> verify -> local file for each closed/overdue M303 quarter,
    then calculate -> verify -> export M390 from those local records.
    The local filing records remain non-official (``aeat_accepted=False``);
    dependent periods surface the non-official-local-chain advisory.
    """
    _store_irene_sl_profile(secure_objects)
    stored = persist_year_of_invoices(
        secure_objects,
        filing_year=_IRENE_YEAR,
        facts_by_period=IRENE_QUARTER_FACTS,
    )
    workflow_profile = _ireneworkflow_profile()
    wu_repo = WorkUnitCatalogueRepository(bucket_id=_BUCKET_ID, objects=secure_objects)
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
            operation=operation,
        )
        assert Decimal(revision.casilla_values[_DEVENGADA_TOTAL]) == stored[period]["devengada"]
        assert Decimal(revision.casilla_values[_DEDUCIBLE_TOTAL]) == stored[period]["deducible"]
        assert Decimal(revision.casilla_values[_RESULTADO]) == stored[period]["resultado"]
        computed[period] = {
            _DEVENGADA_TOTAL: Decimal(revision.casilla_values[_DEVENGADA_TOTAL]),
            _DEDUCIBLE_TOTAL: Decimal(revision.casilla_values[_DEDUCIBLE_TOTAL]),
            _RESULTADO: Decimal(revision.casilla_values[_RESULTADO]),
        }

        with bundled_indexed_authority().operation() as operation:
            report = verify_modelo_revision_with_preconditions(
                revision.calculation_revision_id,
                certificate_secret_backend_factory=build_test_certificate_secret_backend_factory(),
                verification_repositories=_verification_ports(
                    operation=operation,
                    work_repo=wu_repo,
                    calc_repo=cr_repo,
                    filing_repo=filing_repo,
                    verification_repo=verification_repo,
                    event_repo=event_repo,
                    tx_repo=tx_repo,
                ),
                actor="irene",
                workflow_profile=workflow_profile,
                settings=ready_clave_settings("12345678Z"),
                clock=_IRENE_FILE_AT,
                operator_scope_ports=_OPERATOR_SCOPE_PORTS,
                operation=operation,
            ).report
        assert report.granted_verificado_completo is True, report.findings

        with bundled_indexed_authority().operation() as operation:
            filing = file_modelo_revision(
                revision.calculation_revision_id,
                approved_verification_report_id=report.verification_report_id,
                certificate_secret_backend_factory=build_test_certificate_secret_backend_factory(),
                actor="irene",
                workflow_profile=workflow_profile,
                ports=_filing_ports(
                    work_repo=wu_repo,
                    calc_repo=cr_repo,
                    filing_repo=filing_repo,
                    verification_repo=verification_repo,
                    event_repo=event_repo,
                    wallet_repo=wallet_repo,
                    observation_repo=observation_repo,
                    operation=operation,
                ),
                clock=_IRENE_FILE_AT,
                operator_scope_ports=_OPERATOR_SCOPE_PORTS,
                operation=operation,
            ).record
        assert filing.aeat_accepted is False
        assert filing.external_evidence is None
        stored_observation = observation_repo.load_observation("303", Period.from_year_and_code(_IRENE_YEAR, period))
        assert stored_observation is not None
        assert stored_observation.source_kind == "app_filing"

    annual = _calculate_m390_annual(secure_objects, filing_year=_IRENE_YEAR, operation=operation)
    for m390_casilla, m303_output in (
        (_M390_DEVENGADA, _DEVENGADA_TOTAL),
        (_M390_DEDUCIBLE, _DEDUCIBLE_TOTAL),
        (_M390_RESULTADO, _RESULTADO),
    ):
        expected = sum((computed[p][m303_output] for p in _QUARTER_ORDER), Decimal("0"))
        assert Decimal(annual.casilla_values[m390_casilla]) == expected
    assert Decimal(annual.casilla_values[_M390_DEVENGADA]) == IRENE_ANNUAL_EXPECTED["devengada"]
    assert Decimal(annual.casilla_values[_M390_DEDUCIBLE]) == IRENE_ANNUAL_EXPECTED["deducible"]
    assert Decimal(annual.casilla_values[_M390_RESULTADO]) == IRENE_ANNUAL_EXPECTED["resultado"]

    with bundled_indexed_authority().operation() as operation:
        annual_report = verify_modelo_revision_with_preconditions(
            annual.calculation_revision_id,
            certificate_secret_backend_factory=build_test_certificate_secret_backend_factory(),
            verification_repositories=_verification_ports(
                operation=operation,
                work_repo=wu_repo,
                calc_repo=cr_repo,
                filing_repo=filing_repo,
                verification_repo=verification_repo,
                event_repo=event_repo,
                tx_repo=tx_repo,
            ),
            actor="irene",
            workflow_profile=workflow_profile,
            settings=ready_clave_settings("12345678Z"),
            clock=_IRENE_FILE_AT,
            operator_scope_ports=_OPERATOR_SCOPE_PORTS,
            operation=operation,
        ).report
    assert annual_report.granted_verificado_completo is True, annual_report.findings
    assert _non_official_local_chain_advisory_periods(annual_report) == set(_QUARTER_ORDER), annual_report.findings

    # The annual resumen verifies from the locally filed quarters and exports.
    annual_output = tmp_path / f"modelo-390-{_IRENE_YEAR}-0A.boe"
    with bundled_indexed_authority().operation() as operation:
        export_modelo_revision(
            ModeloExportCommand(
                calculation_revision_id=annual.calculation_revision_id,
                output_path=annual_output,
                actor="irene",
            ),
            workflow_profile=workflow_profile,
            export_ports=modelo_export_ports_for_test(
                product_software_identity=product_software_identity(),
                bucket_id=_BUCKET_ID,
                taxpayer_tax_id=_IRENE_TAX_ID,
                secure_objects=secure_objects,
                work_unit=wu_repo,
                calculation=cr_repo,
                filing=filing_repo,
                verification=verification_repo,
                bucket_event=event_repo,
                observation=observation_repo,
            ),
            operation=operation,
            clock=_IRENE_FILE_AT,
        )
    assert annual_output.read_bytes().startswith(b"<T3900")


def test_ledger_drives_m303_quarters_and_folds_into_m390_annual(
    secure_objects: SecureObjectRepository, *, operation: PinnedAuthorityOperation
) -> None:
    """The full yearly IVA cadence: persisted ledger → 4×M303 → M390 reconciliation."""
    _store_profile(secure_objects)
    stored = persist_year_of_invoices(secure_objects)

    computed: ComputedM303CasillasByPeriod = {}
    for period in _QUARTER_ORDER:
        revision = _calculate_and_file_m303_quarter(secure_objects, period=period, operation=operation)

        # Transport invariant #1: the computed cuota totals equal the IVA amounts
        # STORED on the persisted invoices (the aggregator sums the stored
        # iva_amount field — it does not re-derive base×rate, confirmed in
        # application/aggregation/iva_ledger.py). Asserting against the stored
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

    annual = _calculate_m390_annual(secure_objects, operation=operation)
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
    assert Decimal(casillas[_M390_DEVENGADA]) == LAURA_ANNUAL_EXPECTED["devengada"]
    assert Decimal(casillas[_M390_DEDUCIBLE]) == LAURA_ANNUAL_EXPECTED["deducible"]
    assert Decimal(casillas[_M390_RESULTADO]) == LAURA_ANNUAL_EXPECTED["resultado"]


def test_m390_refuses_zero_reconciliation_when_m303_calculated_but_observations_missing(
    secure_objects: SecureObjectRepository, *, operation: PinnedAuthorityOperation
) -> None:
    """Laura regression: calculated nonzero 303 quarters must not become zero M390 reconciliation slots."""
    _store_profile(secure_objects)
    persist_year_of_invoices(secure_objects)

    computed: ComputedM303CasillasByPeriod = {}
    for period in _QUARTER_ORDER:
        _work_unit, revision = _calculate_m303_quarter_revision(secure_objects, period=period, operation=operation)
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
        _calculate_m390_annual(secure_objects, operation=operation)
    after_revision_ids = frozenset(cr_repo.load().revisions)

    assert after_revision_ids == before_revision_ids
    assert isinstance(exc_info.value, CadrumoError)
    assert exc_info.value.translated_message == "application.modelo.errors.cross_period_clean_state_incomplete"
    context = exc_info.value.context or {}
    assert context["reason"] == "missing_clean_cross_period_303_filings_or_observations"
    assert context["missing_303_periods"] == ("1T", "2T", "3T", "4T")
    # Without a filed fourth quarter the annual prorrata regularisation is
    # unresolved, so the annual deduction total and result that sum it are
    # unknown, which proves no zero slot; the output-IVA total refuses as well.
    assert context["zero_reconciliation_casillas_at_risk"] == (
        _M390_DEVENGADA,
        _M390_DEDUCIBLE,
        _M390_RESULTADO,
    )


def test_m390_refuses_annual_zeros_no_source_or_operator_ever_stated(
    secure_objects: SecureObjectRepository, *, operation: PinnedAuthorityOperation
) -> None:
    """An empty ledger and no M303 quarters leave every annual box unknown, not a proven zero.

    The operator states only the annual prorrata regularisation, so the deduction
    totals no longer wait on a filed fourth quarter. Every other box the annual
    totals sum was never supplied, and the engine reads such a box as zero; that
    zero proves nothing, so no reconciliation slot may be saved as zero.
    """
    _store_profile(secure_objects)

    cr_repo = CalculationRevisionCatalogueRepository(objects=secure_objects)
    before_revision_ids = frozenset(cr_repo.load().revisions)
    with pytest.raises(ModeloCrossPeriodCleanStateError) as exc_info:
        _calculate_m390_annual(
            secure_objects,
            operation=operation,
            binding_values={"modelo-390-prorrata-regularizacion-anual": Decimal("0.00")},
        )

    assert frozenset(cr_repo.load().revisions) == before_revision_ids
    context = exc_info.value.context or {}
    assert context["reason"] == "missing_clean_cross_period_303_filings_or_observations"
    assert context["missing_303_periods"] == _QUARTER_ORDER
    assert context["zero_reconciliation_casillas_at_risk"] == (_M390_DEVENGADA, _M390_DEDUCIBLE, _M390_RESULTADO)
    assert context["annual_casillas_not_proven_zero"] == (
        validated_casilla_id("iva.anual.cuota-devengada-total"),
        validated_casilla_id("iva.anual.cuota-deducible-total"),
        validated_casilla_id("iva.anual.resultado-regimen-general"),
    )


# The seeded year is the AEAT prorrata general example (see PRORRATA_QUARTER_FACTS).
_PRORRATA_PROVISIONAL_PERCENTAGE = Decimal("73")
_PRORRATA_VOLUMEN_CON_DERECHO: CasillaId = validated_casilla_id("iva.prorrata-volumen-con-derecho")
_PRORRATA_VOLUMEN_TOTAL: CasillaId = validated_casilla_id("iva.prorrata-volumen-total")
_SOPORTADO_INTERIORES: CasillaId = validated_casilla_id("iva.soportado.interiores")
_CASILLA_44: CasillaId = validated_casilla_id("44")
_CASILLA_45: CasillaId = validated_casilla_id("45")
_M390_PRORRATA_REGULARIZACION: CasillaId = validated_casilla_id("iva.anual.regularizacion-prorrata-definitiva")
_M390_INTERIORES_CORRIENTES_CUOTA: CasillaId = validated_casilla_id(
    "iva.anual.deducible.interiores-corrientes.soportado.cuota"
)
# The manual's printed figures, independent of the engine.
_MANUAL_PRACTISED_DEDUCTIONS_1T_3T = {"1T": Decimal("292.00"), "2T": Decimal("306.60"), "3T": Decimal("335.80")}
_MANUAL_4T_DEFINITIVE_DEDUCTION = Decimal("89.60")
_MANUAL_EXCESO_DE_DEDUCCION = Decimal("-217.60")
_MANUAL_4T_CASILLA_45 = Decimal("-128.00")
_MANUAL_YEAR_DEDUCTIONS = Decimal("806.40")
_MANUAL_YEAR_INTERIORES_CORRIENTES_CUOTA = Decimal("1024.00")


def _save_general_prorrata_register(secure_objects: SecureObjectRepository) -> None:
    """Declare the general prorrata with the provisional percentage carried from the prior year."""
    prior_year = _YEAR - 1
    ProrrataRegisterRepository(bucket_id=_BUCKET_ID, objects=secure_objects).save(
        ProrrataRegister(
            entries=(
                ProrrataRegisterEntry(
                    ejercicio=_YEAR,
                    regime=ProrrataRegisterRegime.from_registry("general"),
                    especial_transition=None,
                    provisional_percentage=_PRORRATA_PROVISIONAL_PERCENTAGE,
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


def test_general_prorrata_settles_in_the_fourth_quarter_and_folds_into_m390(
    secure_objects: SecureObjectRepository, *, operation: PinnedAuthorityOperation
) -> None:
    """Ledger to M303 to M390 reproduces the AEAT manual's general prorrata regularisation.

    The first three quarters deduct at the provisional 73 %; the fourth quarter
    deducts its own cuotas at the definitive 56 % and regularises only the
    earlier quarters in casilla 44 (LIVA art. 105.Seis). The annual summary
    restates the settlement box and sums the per-period deductions.
    """
    _store_profile(secure_objects)
    _save_general_prorrata_register(secure_objects)
    persist_year_of_invoices(
        secure_objects,
        facts_by_period=PRORRATA_QUARTER_FACTS,
        received_rate_percent=Decimal("10"),
    )

    filed: dict[str, CalculationRevision] = {}
    for period in ("1T", "2T", "3T"):
        filed[period] = _calculate_and_file_m303_quarter(secure_objects, period=period, operation=operation)
        casillas = filed[period].casilla_values
        assert Decimal(casillas[_SOPORTADO_INTERIORES]) == _MANUAL_PRACTISED_DEDUCTIONS_1T_3T[period]
        assert Decimal(casillas[_CASILLA_44]) == Decimal("0.00")
    filed["4T"] = _calculate_and_file_m303_quarter(
        secure_objects,
        period="4T",
        extra_casilla_inputs={
            _PRORRATA_VOLUMEN_CON_DERECHO: Decimal("25000.00"),
            _PRORRATA_VOLUMEN_TOTAL: Decimal("45000.00"),
        },
        operation=operation,
    )
    settlement = filed["4T"].casilla_values
    assert Decimal(settlement[_SOPORTADO_INTERIORES]) == _MANUAL_4T_DEFINITIVE_DEDUCTION
    assert Decimal(settlement[_CASILLA_44]) == _MANUAL_EXCESO_DE_DEDUCCION
    assert Decimal(settlement[_CASILLA_45]) == _MANUAL_4T_CASILLA_45

    year_deductions = sum((Decimal(filed[p].casilla_values[_CASILLA_45]) for p in _QUARTER_ORDER), Decimal("0"))
    assert year_deductions == _MANUAL_YEAR_DEDUCTIONS

    annual = _calculate_m390_annual(secure_objects, operation=operation)
    assert Decimal(annual.casilla_values[_M390_PRORRATA_REGULARIZACION]) == _MANUAL_EXCESO_DE_DEDUCCION
    assert Decimal(annual.casilla_values[_M390_INTERIORES_CORRIENTES_CUOTA]) == (
        _MANUAL_YEAR_INTERIORES_CORRIENTES_CUOTA
    )
    assert Decimal(annual.casilla_values[_M390_DEDUCIBLE]) == _MANUAL_YEAR_DEDUCTIONS


def test_settlement_quarter_without_filed_earlier_quarter_leaves_casilla_44_unresolved(
    secure_objects: SecureObjectRepository, tmp_path: Path, *, operation: PinnedAuthorityOperation
) -> None:
    """A missing first-quarter liquidation keeps the regularisation unresolved, never zero.

    The saved revision holds no figure for 44, nor for the deduction total [45]
    and the general-regime result [46] that sum it, and the unresolved-binding
    note refuses checking, exporting and recording the declaration.
    """
    _store_profile(secure_objects)
    _save_general_prorrata_register(secure_objects)
    persist_year_of_invoices(
        secure_objects,
        facts_by_period=PRORRATA_QUARTER_FACTS,
        received_rate_percent=Decimal("10"),
    )
    for period in ("2T", "3T"):
        _calculate_and_file_m303_quarter(secure_objects, period=period, operation=operation)

    _work_unit, revision = _calculate_m303_quarter_revision(
        secure_objects,
        period="4T",
        extra_casilla_inputs={
            _PRORRATA_VOLUMEN_CON_DERECHO: Decimal("25000.00"),
            _PRORRATA_VOLUMEN_TOTAL: Decimal("45000.00"),
        },
        operation=operation,
    )

    # The persisted unresolved-binding issue is what blocks verification and
    # filing of the box until a recalculation clears it.
    casilla_44_issues = tuple(
        issue
        for issue in revision.source_issues
        if issue.reason == "unresolved_binding" and issue.casilla_id == _CASILLA_44
    )
    assert tuple(issue.message for issue in casilla_44_issues) == (
        render_tr("application.calculations.prorrata_regularizacion.unresolved.source_periods_missing", periods="1T"),
    )

    stored = CalculationRevisionCatalogueRepository(objects=secure_objects).load().get(revision.calculation_revision_id)
    assert stored is not None
    observed = {observation.casilla_id for observation in stored.observations}
    for casilla_id in (_CASILLA_44, _CASILLA_45, _DEDUCIBLE_TOTAL, _RESULTADO):
        assert casilla_id not in stored.casilla_values
        assert casilla_id not in observed
    # The quarter's own deduction is still worked out at the definitive 56 %.
    assert Decimal(stored.casilla_values[_SOPORTADO_INTERIORES]) == _MANUAL_4T_DEFINITIVE_DEDUCTION
    _assert_form_states_no_figure(secure_objects, (_CASILLA_44, _CASILLA_45), operation=operation)
    _assert_verify_export_and_file_refused(secure_objects, revision, tmp_path, operation=operation)


def test_a_revision_saved_with_the_unresolved_44_as_zero_still_loads_unchanged(
    secure_objects: SecureObjectRepository, *, operation: PinnedAuthorityOperation
) -> None:
    """A draft saved before unresolved bound boxes were left absent keeps its stored zero and still opens.

    Such a draft holds 44 as an ordinary zero beside its unresolved-binding
    note. Loading neither rejects nor rewrites it, its note still refuses the
    check, and the form still reads the box as not worked out.
    """
    _store_profile(secure_objects)
    _save_general_prorrata_register(secure_objects)
    persist_year_of_invoices(
        secure_objects,
        facts_by_period=PRORRATA_QUARTER_FACTS,
        received_rate_percent=Decimal("10"),
    )
    for period in ("2T", "3T"):
        _calculate_and_file_m303_quarter(secure_objects, period=period, operation=operation)
    work_unit, current = _calculate_m303_quarter_revision(
        secure_objects,
        period="4T",
        extra_casilla_inputs={
            _PRORRATA_VOLUMEN_CON_DERECHO: Decimal("25000.00"),
            _PRORRATA_VOLUMEN_TOTAL: Decimal("45000.00"),
        },
        operation=operation,
    )
    snapshot = published_authority_operation().snapshot("303", filing_year=_YEAR, period="4T")
    casilla_44 = next(casilla for casilla in snapshot.revision.casillas if casilla.id == _CASILLA_44)
    stored_zero = current.model_copy(
        update={
            "casilla_values": {**current.casilla_values, _CASILLA_44: Decimal("0.00")},
            "observations": (
                *current.observations,
                CasillaObservation(
                    casilla_id=_CASILLA_44,
                    value=Decimal("0.00"),
                    legal_refs=casilla_44.legal_refs,
                    source_refs=casilla_44.source_refs,
                ),
            ),
        }
    )
    legacy = stored_zero.model_copy(
        update={"calculation_revision_id": derive_calculation_revision_id_from_revision(stored_zero)}
    )
    cr_repo = CalculationRevisionCatalogueRepository(objects=secure_objects)
    catalogue = cr_repo.load()
    cr_repo.save(
        catalogue.model_copy(update={"revisions": {**catalogue.revisions, legacy.calculation_revision_id: legacy}})
    )
    wu_repo = WorkUnitCatalogueRepository(bucket_id=_BUCKET_ID, objects=secure_objects)
    current_unit = wu_repo.load().get(work_unit.work_unit_id)
    assert current_unit is not None
    wu_repo.save(
        upsert_work_unit(
            wu_repo.load(),
            current_unit.model_copy(update={"current_calculation_revision_id": legacy.calculation_revision_id}),
        )
    )

    reloaded = CalculationRevisionCatalogueRepository(objects=secure_objects).load().get(legacy.calculation_revision_id)
    assert reloaded is not None
    assert reloaded.casilla_values[_CASILLA_44] == Decimal("0.00")
    assert reloaded.source_issues == current.source_issues
    _assert_form_states_no_figure(secure_objects, (_CASILLA_44,), operation=operation)
    with (
        bundled_indexed_authority().operation() as verify_operation,
        pytest.raises(ModeloCalculationBlockedError) as refusal,
    ):
        verify_modelo_revision_with_preconditions(
            legacy.calculation_revision_id,
            certificate_secret_backend_factory=build_test_certificate_secret_backend_factory(),
            verification_repositories=_verification_ports(
                operation=verify_operation,
                work_repo=wu_repo,
                calc_repo=CalculationRevisionCatalogueRepository(objects=secure_objects),
                filing_repo=ModeloRecordCatalogueRepository(objects=secure_objects),
                verification_repo=VerificationReportCatalogueRepository(objects=secure_objects),
                event_repo=BucketEventHistoryRepository(objects=secure_objects),
                tx_repo=TransactionCatalogueRepository(bucket_id=_BUCKET_ID, objects=secure_objects),
            ),
            actor="operator",
            workflow_profile=workflow_profile(),
            settings=ready_clave_settings(_TAX_ID),
            clock=_FILE_AT,
            operator_scope_ports=_OPERATOR_SCOPE_PORTS,
            operation=verify_operation,
        )
    assert (refusal.value.context or {})["reason"] == "unresolved_binding"


def _assert_form_states_no_figure(
    secure_objects: SecureObjectRepository,
    casilla_ids: tuple[CasillaId, ...],
    *,
    operation: PinnedAuthorityOperation,
) -> None:
    """The editor form shows each box as not worked out, with no value, rather than an imported or summed zero."""
    with bundled_indexed_authority().operation() as form_operation:
        form = load_modelo_work_form(
            _BUCKET_ID,
            ModeloCode("303"),
            _YEAR,
            Period.from_year_and_code(_YEAR, "4T"),
            operation=form_operation,
            work_unit_repository=WorkUnitCatalogueRepository(bucket_id=_BUCKET_ID, objects=secure_objects),
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


def _assert_verify_export_and_file_refused(
    secure_objects: SecureObjectRepository,
    revision: CalculationRevision,
    tmp_path: Path,
    *,
    operation: PinnedAuthorityOperation,
) -> None:
    """Verify refuses on the unresolved-binding note; export and local filing refuse the unverified draft."""
    wu_repo = WorkUnitCatalogueRepository(bucket_id=_BUCKET_ID, objects=secure_objects)
    cr_repo = CalculationRevisionCatalogueRepository(objects=secure_objects)
    filing_repo = ModeloRecordCatalogueRepository(objects=secure_objects)
    vr_repo = VerificationReportCatalogueRepository(objects=secure_objects)
    event_repo = BucketEventHistoryRepository(objects=secure_objects)
    tx_repo = TransactionCatalogueRepository(bucket_id=_BUCKET_ID, objects=secure_objects)

    with (
        bundled_indexed_authority().operation() as verify_operation,
        pytest.raises(ModeloCalculationBlockedError) as verify_refusal,
    ):
        verify_modelo_revision_with_preconditions(
            revision.calculation_revision_id,
            certificate_secret_backend_factory=build_test_certificate_secret_backend_factory(),
            verification_repositories=_verification_ports(
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
            settings=ready_clave_settings(_TAX_ID),
            clock=_FILE_AT,
            operator_scope_ports=_OPERATOR_SCOPE_PORTS,
            operation=verify_operation,
        )
    assert (verify_refusal.value.context or {})["reason"] == "unresolved_binding"

    # The refused check leaves the draft unverified, so export and local filing
    # refuse it on state before their own calculation-note gates are reached.
    output_path = tmp_path / f"modelo-303-{_YEAR}-4T.boe"
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
                bucket_id=_BUCKET_ID,
                taxpayer_tax_id=_TAX_ID,
                secure_objects=secure_objects,
                work_unit=wu_repo,
                calculation=cr_repo,
                filing=filing_repo,
                verification=vr_repo,
                bucket_event=event_repo,
            ),
            operation=export_operation,
            clock=_FILE_AT,
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
            ports=_filing_ports(
                work_repo=wu_repo,
                calc_repo=cr_repo,
                filing_repo=filing_repo,
                verification_repo=vr_repo,
                event_repo=event_repo,
                wallet_repo=IvaWalletDecisionRepository(objects=secure_objects),
                observation_repo=CalculationObservationRepository(objects=secure_objects),
                operation=file_operation,
            ),
            clock=_FILE_AT,
            operator_scope_ports=_OPERATOR_SCOPE_PORTS,
            operation=file_operation,
        )
    assert not filing_repo.load().records

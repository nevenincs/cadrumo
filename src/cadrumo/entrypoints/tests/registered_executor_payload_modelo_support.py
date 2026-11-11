"""Build the exact requests of the Modelo work, filing, wallet, workflow and overview operations."""

from __future__ import annotations

import hashlib
from datetime import UTC, date, datetime
from decimal import Decimal

from cadrumo.adapters.persistence.profile.tests.taxpayer_persona_support import seed_modelo_ready_profile
from cadrumo.adapters.persistence.storage.tests.profile_capsule_runtime import (
    upsert_test_profile_facts,
)

from ...adapters.persistence.profile.iva_compensation_history import IvaCompensationHistoryRepository
from ...adapters.persistence.profile.modelos_calculation import CalculationRevisionCatalogueRepository
from ...adapters.persistence.profile.modelos_filing import ModeloRecordCatalogueRepository
from ...adapters.persistence.profile.modelos_work_units import WorkUnitCatalogueRepository
from ...adapters.persistence.profile.tests.cross_period_seeding import SEEDED_SOURCE_TAX_ID
from ...adapters.persistence.profile.tests.justificante_metadata import persist_justificante_metadata
from ...application.calculations.iva_compensation_history import seed_iva_compensation_period
from ...application.filing.producer_snapshot_m360 import (
    M360AmbitoEstablecimiento,
    M360CausaPresentacion,
    M360NivelCalidadDatos,
    M360TitularEnCalidadDe,
    Modelo360CuentaTitularFacts,
    Modelo360EstablecimientoFacts,
    Modelo360ProfileFacts,
    Modelo360RepresentanteFacts,
    Modelo360SolicitanteFacts,
    Modelo360SolicitudFacts,
)
from ...application.ledger.models import ManualLedgerTransactionCommand
from ...application.ledger.tests.manual_transaction_support import create_manual_transaction
from ...application.modelo.edit_operator_input import ModeloEditOperatorInputV2
from ...application.modelo.local_observation_contracts import ModeloLocalObservationCasillaValue
from ...application.modelo.m360_solicitud_operation import Modelo360RepresentanteAccountInput
from ...application.modelo.reconciliation_evidence_kind import ModeloReconciliationEvidenceKind
from ...application.modelo.work_calculation_contracts import ModeloWorkCalculateRequest
from ...application.operations.public_period import PublicPeriod
from ...application.overview.read_request import OVERVIEW_READ_DEFINITION_IDS, OverviewReadKind
from ...application.workflow.abort import WorkflowAbortReason
from ...application.workflow.persistence import WorkflowRunRepository
from ...core.external_constants import OutputLanguage
from ...core.period import Period
from ...core.time.clock import now
from ...domain.calculations.registry.tests.authored_editions import revision_covering
from ...domain.calculations.registry.tests.cross_period_seeding import resolved_revision
from ...domain.modelos.filing_record import ExternalEvidenceKind, FilingDeclarationKind
from ...domain.transactions.enums import BusinessClassification, TransactionDirection
from ...domain.user_profile.values import UserProfileFact
from ..ledger_action_composition import compose_ledger_action_ports
from . import modelo_operation_test_support
from .registered_executor_payload_context import PayloadBuilder, PayloadContext, PayloadResult
from .registered_executor_scenario_constants import OWN_ACCOUNT_SYNTHETIC_IBAN
from .registered_executor_seeding_support import (
    CONFORMANCE_EARLIER_YEAR,
    CONFORMANCE_PRIOR_YEAR,
    CONFORMANCE_YEAR,
    seeded_modelo_edit_submission,
    seeded_modelo_filing_record,
    workflow_result,
)


def _seed_wallet_period(ctx: PayloadContext, period: Period) -> None:
    """Give the wallet a prior compensation period for the seeded taxpayer."""
    seed_modelo_ready_profile(bucket_id=str(ctx.profile_id), at=now(), tax_id=SEEDED_SOURCE_TAX_ID)
    seed_iva_compensation_period(
        taxpayer_nif=SEEDED_SOURCE_TAX_ID,
        period=period,
        amount=Decimal("500.00"),
        repository=IvaCompensationHistoryRepository(bucket_id=str(ctx.profile_id)),
        operation=ctx.operation,
    )


def _modelo_iva_wallet_correct(ctx: PayloadContext) -> PayloadResult:
    period = Period.from_year_and_code(CONFORMANCE_EARLIER_YEAR, "4T")
    _seed_wallet_period(ctx, period)
    return ctx.request(
        ctx.profile_subject,
        {
            "profile_id": ctx.profile_id,
            "period": PublicPeriod.from_period(period),
            "amount": "1200.50",
            "reason": "corrected opening balance",
        },
    )


def _modelo_iva_wallet_balance(ctx: PayloadContext) -> PayloadResult:
    _seed_wallet_period(ctx, Period.from_year_and_code(CONFORMANCE_EARLIER_YEAR, "4T"))
    return ctx.request(ctx.profile_subject, {"profile_id": ctx.profile_id, "as_of_year": CONFORMANCE_EARLIER_YEAR})


def _modelo_iva_wallet_seed(ctx: PayloadContext) -> PayloadResult:
    seed_modelo_ready_profile(bucket_id=str(ctx.profile_id), at=now(), tax_id=SEEDED_SOURCE_TAX_ID)
    return ctx.request(
        ctx.profile_subject,
        {
            "profile_id": ctx.profile_id,
            "period": PublicPeriod.from_period(Period.from_year_and_code(CONFORMANCE_EARLIER_YEAR, "4T")),
            "amount": "500.00",
        },
    )


def _modelo_iva_wallet_override(ctx: PayloadContext) -> PayloadResult:
    seed_modelo_ready_profile(bucket_id=str(ctx.profile_id), at=now(), tax_id=SEEDED_SOURCE_TAX_ID)
    return ctx.request(
        ctx.profile_subject,
        {
            "profile_id": ctx.profile_id,
            "period": PublicPeriod.from_period(Period.from_year_and_code(CONFORMANCE_PRIOR_YEAR, "1T")),
            "amount": "450.00",
            "reason": "operator asserted prior compensation",
            "evidence_locator": "synthetic:conformance:prior-compensation",
        },
    )


def _modelo_reconcile_import(ctx: PayloadContext) -> PayloadResult:
    unit = modelo_operation_test_support.seeded_modelo_work_unit(ctx.profile_id, operation=ctx.operation)
    return ctx.request(
        ctx.profile_subject,
        {
            "profile_id": ctx.profile_id,
            "work_unit_id": unit.work_unit_id,
            "source_kind": ModeloReconciliationEvidenceKind.JUSTIFICANTE,
            "source_path": str(ctx.tmp_path / "missing-evidence.pdf"),
        },
    )


def _modelo_reconcile_pull(ctx: PayloadContext) -> PayloadResult:
    unit = modelo_operation_test_support.seeded_modelo_work_unit(ctx.profile_id, operation=ctx.operation)
    return ctx.request(
        ctx.profile_subject,
        {"profile_id": ctx.profile_id, "work_unit_id": unit.work_unit_id, "snapshot_id": "a" * 64},
    )


def _modelo_reconcile_list(ctx: PayloadContext) -> PayloadResult:
    return ctx.request(ctx.profile_subject, {"profile_id": ctx.profile_id, "work_unit_id": None})


def _modelo_work_rename(ctx: PayloadContext) -> PayloadResult:
    unit = modelo_operation_test_support.seeded_modelo_work_unit(ctx.profile_id, operation=ctx.operation)
    return ctx.request(
        unit.work_unit_id,
        {
            "work_unit_id": unit.work_unit_id,
            "new_name": "Conformance renamed unit",
            "observed_name": unit.name,
            "observed_updated_at": unit.updated_at,
            "actor": modelo_operation_test_support.MODELO_OPERATION_TEST_ACTOR,
        },
    )


def _modelo_work_metadata(ctx: PayloadContext) -> PayloadResult:
    unit = modelo_operation_test_support.seeded_modelo_work_unit(ctx.profile_id, operation=ctx.operation)
    return ctx.request(ctx.raw_profile_subject, {"profile_id": ctx.profile_id, "work_unit_id": unit.work_unit_id})


def _modelo_work_create(ctx: PayloadContext) -> PayloadResult:
    upsert_test_profile_facts(
        ctx.profile_id,
        (
            UserProfileFact(path="taxpayer_type.entity_type", value="natural_person"),
            UserProfileFact(path="identity.name", value="Conformance"),
            UserProfileFact(path="identity.surnames", value="Natural Person"),
            UserProfileFact(path="activities.description", value="professional services"),
            UserProfileFact(path="censo.activity_start_date", value=date(CONFORMANCE_PRIOR_YEAR, 1, 1).isoformat()),
            UserProfileFact(path="tax_residence.jurisdiction_scope", value="common_regime"),
            UserProfileFact(path="iva.regime", value="GENERAL"),
            UserProfileFact(path="iva.m303_regime_composition", value="general"),
            UserProfileFact(path="iva.redeme_enrolled", value=False),
            UserProfileFact(path="iva.cash_accounting_regime_enrolled", value=False),
            UserProfileFact(path="iva.voluntary_sii_enrolled", value=False),
            UserProfileFact(path="iva.hydrocarbon_deposit_advance_payment_deduction_entitled", value=False),
        ),
    )
    return ctx.request(
        ctx.profile_subject,
        {
            "profile_id": ctx.profile_id,
            "modelo": "202",
            "period": PublicPeriod.from_period(Period.from_year_and_code(CONFORMANCE_PRIOR_YEAR, "1P")),
            "revision_id": str(revision_covering("202", CONFORMANCE_PRIOR_YEAR).id),
            "actor": modelo_operation_test_support.MODELO_OPERATION_TEST_ACTOR,
        },
    )


def _modelo_work_list(ctx: PayloadContext) -> PayloadResult:
    modelo_operation_test_support.seeded_modelo_work_unit(ctx.profile_id, operation=ctx.operation)
    return ctx.request(ctx.profile_subject, {"profile_id": ctx.profile_id, "include_discarded": False})


def _modelo_declarations_list(ctx: PayloadContext) -> PayloadResult:
    modelo_operation_test_support.seeded_modelo_work_unit(ctx.profile_id, operation=ctx.operation)
    return ctx.request(ctx.profile_subject, {"profile_id": ctx.profile_id, "output_language": OutputLanguage.ES})


def _modelo_declarations_search(ctx: PayloadContext) -> PayloadResult:
    modelo_operation_test_support.seeded_modelo_work_unit(ctx.profile_id, operation=ctx.operation)
    return ctx.request(
        ctx.profile_subject,
        {"profile_id": ctx.profile_id, "output_language": OutputLanguage.ES, "query": "modelo", "limit": 20},
    )


def _modelo_work_history(ctx: PayloadContext) -> PayloadResult:
    unit = modelo_operation_test_support.seeded_modelo_work_unit(ctx.profile_id, operation=ctx.operation)
    return ctx.request(
        unit.work_unit_id,
        {"profile_id": ctx.profile_id, "work_unit_id": unit.work_unit_id, "output_language": OutputLanguage.ES},
    )


def _modelo_work_review(ctx: PayloadContext) -> PayloadResult:
    unit = modelo_operation_test_support.seeded_modelo_work_unit(ctx.profile_id, operation=ctx.operation)
    return ctx.request(unit.work_unit_id, {"profile_id": ctx.profile_id, "work_unit_id": unit.work_unit_id})


def _modelo_work_form(ctx: PayloadContext) -> PayloadResult:
    unit = modelo_operation_test_support.seeded_modelo_work_unit(ctx.profile_id, operation=ctx.operation)
    return ctx.request(
        unit.work_unit_id,
        {"profile_id": ctx.profile_id, "work_unit_id": unit.work_unit_id, "output_language": OutputLanguage.ES},
    )


def _modelo_work_casilla_help(ctx: PayloadContext) -> PayloadResult:
    unit = modelo_operation_test_support.seeded_modelo_work_unit(ctx.profile_id, operation=ctx.operation)
    return ctx.request(
        unit.work_unit_id,
        {
            "profile_id": ctx.profile_id,
            "work_unit_id": unit.work_unit_id,
            "casilla_id": "06",
            "registry_revision_id": str(unit.revision_id),
            "calculation_revision_id": None,
            "output_language": OutputLanguage.ES,
        },
    )


def _modelo_edit_renew(ctx: PayloadContext) -> PayloadResult:
    work_unit_id, wire_submission = seeded_modelo_edit_submission(ctx.profile_id, operation=ctx.operation)
    return ctx.request(
        work_unit_id,
        {
            "profile_id": ctx.profile_id,
            "baseline": wire_submission.baseline,
            "output_language": OutputLanguage.EN,
        },
    )


def _modelo_edit_submission(ctx: PayloadContext) -> PayloadResult:
    work_unit_id, wire_submission = seeded_modelo_edit_submission(ctx.profile_id, operation=ctx.operation)
    return (
        work_unit_id,
        ModeloEditOperatorInputV2(submission=wire_submission, output_language=OutputLanguage.EN),
        None,
    )


def _modelo_edit_apply_prerequisite(ctx: PayloadContext) -> PayloadResult:
    work_unit_id, wire_submission = seeded_modelo_edit_submission(ctx.profile_id, operation=ctx.operation)
    return ctx.request(
        work_unit_id,
        {
            "profile_id": ctx.profile_id,
            "work_unit_id": work_unit_id,
            "apply_operation_id": "e" * 64,
            "baseline_id": wire_submission.baseline.baseline_id,
            "calculation_revision_id": wire_submission.baseline.current_calculation_revision_id,
            "registry_revision_id": wire_submission.baseline.law_selected_revision_id,
        },
    )


def _modelo_filing_record_reader(ctx: PayloadContext) -> PayloadResult:
    filing_record_id, _casilla_id = seeded_modelo_filing_record(ctx.profile_id, operation=ctx.operation)
    return ctx.request(ctx.profile_subject, {"profile_id": ctx.profile_id, "filing_record_id": filing_record_id})


def _modelo_filing_record_list(ctx: PayloadContext) -> PayloadResult:
    seeded_modelo_filing_record(ctx.profile_id, operation=ctx.operation)
    return ctx.request(ctx.profile_subject, {"profile_id": ctx.profile_id})


def _modelo_verification_report_list(ctx: PayloadContext) -> PayloadResult:
    modelo_operation_test_support.seeded_modelo_verification_report(ctx.profile_id, operation=ctx.operation)
    return ctx.request(ctx.profile_subject, {"profile_id": ctx.profile_id})


def _modelo_verification_report_view(ctx: PayloadContext) -> PayloadResult:
    _revision_id, report_id = modelo_operation_test_support.seeded_modelo_verification_report(
        ctx.profile_id, operation=ctx.operation
    )
    return ctx.request(ctx.profile_subject, {"profile_id": ctx.profile_id, "verification_report_id": report_id})


def _modelo_observation_local(ctx: PayloadContext) -> PayloadResult:
    modelo_operation_test_support.seeded_modelo_work_unit(ctx.profile_id, operation=ctx.operation)
    revision = resolved_revision(
        modelo=modelo_operation_test_support.MODELO,
        filing_year=modelo_operation_test_support.MODELO_FILING_YEAR,
        period=modelo_operation_test_support.MODELO_PERIOD,
    )
    casilla_id = sorted(casilla.id for casilla in revision.casillas)[0]
    return ctx.request(
        ctx.profile_subject,
        {
            "profile_id": ctx.profile_id,
            "action": "record",
            "modelo": modelo_operation_test_support.MODELO,
            "period": PublicPeriod.from_period(
                Period.from_year_and_code(
                    modelo_operation_test_support.MODELO_FILING_YEAR,
                    modelo_operation_test_support.MODELO_PERIOD,
                )
            ),
            "casilla_values": (ModeloLocalObservationCasillaValue(casilla_id=casilla_id, value="100"),),
            "actor": None,
            "reason": "conformance observation",
        },
    )


def _modelo_filing_record_import(ctx: PayloadContext) -> PayloadResult:
    seed_modelo_ready_profile(bucket_id=str(ctx.profile_id), at=now(), tax_id=SEEDED_SOURCE_TAX_ID)
    unit = modelo_operation_test_support.seeded_modelo_work_unit(ctx.profile_id, operation=ctx.operation)
    revision = resolved_revision(
        modelo=modelo_operation_test_support.MODELO,
        filing_year=modelo_operation_test_support.MODELO_FILING_YEAR,
        period=modelo_operation_test_support.MODELO_PERIOD,
    )
    casilla_id = sorted(casilla.id for casilla in revision.casillas)[0]
    evidence_reference_id = f"CSV{modelo_operation_test_support.MODELO}{modelo_operation_test_support.MODELO_FILING_YEAR}{modelo_operation_test_support.MODELO_PERIOD}".upper()
    persist_justificante_metadata(
        evidence_reference_id,
        modelo=modelo_operation_test_support.MODELO,
        filing_year=modelo_operation_test_support.MODELO_FILING_YEAR,
        period=modelo_operation_test_support.MODELO_PERIOD,
        captured_at=now(),
        tax_id=SEEDED_SOURCE_TAX_ID,
    )
    return ctx.request(
        ctx.profile_subject,
        {
            "profile_id": ctx.profile_id,
            "work_unit_id": unit.work_unit_id,
            "evidence_kind": ExternalEvidenceKind.AEAT_JUSTIFICANTE_PDF,
            "evidence_reference_id": evidence_reference_id,
            "actor": modelo_operation_test_support.MODELO_OPERATION_TEST_ACTOR,
            "casilla_values": ((casilla_id, "100"),),
        },
    )


def _modelo_work_dependencies(ctx: PayloadContext) -> PayloadResult:
    unit = modelo_operation_test_support.seeded_modelo_work_unit(ctx.profile_id, operation=ctx.operation)
    return ctx.request(
        ctx.profile_subject,
        {
            "profile_id": ctx.profile_id,
            "filing_year": unit.filing_year,
            "modelo": unit.modelo,
            "period": PublicPeriod.from_period(unit.period),
        },
    )


def _workflow_run_read(ctx: PayloadContext) -> PayloadResult:
    run_id = "a" * 16
    period = Period.from_year_and_code(CONFORMANCE_PRIOR_YEAR, "1T")
    WorkflowRunRepository().save(
        workflow_result(
            run_id,
            modelo="303",
            period=period,
            started_at=datetime(CONFORMANCE_PRIOR_YEAR, 5, 1, tzinfo=UTC),
        )
    )
    return ctx.request(
        run_id,
        {
            "profile_id": ctx.profile_id,
            "run_id": run_id,
            "expected_period": PublicPeriod.from_period(period),
        },
    )


def _overview_read(ctx: PayloadContext) -> PayloadResult:
    kind = OverviewReadKind(ctx.definition_id.removeprefix("overview."))
    values: dict[str, object] = {"profile_id": ctx.profile_id, "kind": kind, "output_language": OutputLanguage.ES}
    if kind is OverviewReadKind.CALENDAR:
        values.update(
            {"from_date": date(CONFORMANCE_PRIOR_YEAR, 1, 1), "to_date": date(CONFORMANCE_PRIOR_YEAR, 12, 31)}
        )
    elif kind is OverviewReadKind.AGENDA:
        values.update({"as_of": date(CONFORMANCE_PRIOR_YEAR, 1, 1), "horizon_days": 30})
    elif kind is OverviewReadKind.BACKLOG:
        values.update(
            {"from_date": date(CONFORMANCE_PRIOR_YEAR, 1, 1), "to_date": date(CONFORMANCE_PRIOR_YEAR, 12, 31)}
        )
    elif kind is OverviewReadKind.EXPLAIN:
        values.update({"modelo": "303", "year": CONFORMANCE_PRIOR_YEAR})
    elif kind is OverviewReadKind.PREPARE:
        values.update(
            {
                "modelo": "303",
                "period": PublicPeriod.from_period(Period.from_year_and_code(CONFORMANCE_PRIOR_YEAR, "1T")),
            }
        )
    return ctx.request(ctx.profile_subject, values)


def _overview_pipeline(ctx: PayloadContext) -> PayloadResult:
    ports = compose_ledger_action_ports(bucket_id=str(ctx.profile_id), operation=ctx.operation)
    for booked_date, description in (
        (date(CONFORMANCE_PRIOR_YEAR, 1, 15), "conformance overview selected-period seed"),
        (date(CONFORMANCE_PRIOR_YEAR, 4, 15), "conformance overview other-period seed"),
    ):
        create_manual_transaction(
            ManualLedgerTransactionCommand(
                bucket_id=str(ctx.profile_id),
                booked_date=booked_date,
                amount=Decimal("12.00"),
                direction=TransactionDirection.INCOMING,
                description=description,
                business_classification=BusinessClassification.NOT_YET_PROCESSED,
                actor=modelo_operation_test_support.MODELO_OPERATION_TEST_ACTOR,
            ),
            ports=ports,
            occurred_at=now(),
        )
    return ctx.request(
        ctx.profile_subject,
        {
            "profile_id": ctx.profile_id,
            "period": PublicPeriod.from_period(Period.from_year_and_code(CONFORMANCE_PRIOR_YEAR, "1T")),
            "output_language": OutputLanguage.ES,
        },
    )


def _workflow_run_list(ctx: PayloadContext) -> PayloadResult:
    first_period = Period.from_year_and_code(CONFORMANCE_PRIOR_YEAR, "1T")
    second_period = Period.from_year_and_code(CONFORMANCE_PRIOR_YEAR, "2T")
    WorkflowRunRepository().save(
        workflow_result(
            "a" * 16,
            modelo="303",
            period=first_period,
            started_at=datetime(CONFORMANCE_PRIOR_YEAR, 5, 1, tzinfo=UTC),
        )
    )
    WorkflowRunRepository().save(
        workflow_result(
            "b" * 16,
            modelo="130",
            period=second_period,
            started_at=datetime(CONFORMANCE_PRIOR_YEAR, 8, 1, tzinfo=UTC),
        )
    )
    return ctx.request(ctx.profile_subject, {"profile_id": ctx.profile_id})


def _workflow_resume_context(ctx: PayloadContext) -> PayloadResult:
    revision_id = modelo_operation_test_support.seeded_modelo_calculation_revision(
        ctx.profile_id, operation=ctx.operation
    )
    revision = CalculationRevisionCatalogueRepository().load(operation=ctx.operation).get(revision_id)
    assert revision is not None
    unit = WorkUnitCatalogueRepository().load().get(revision.work_unit_id)
    assert unit is not None
    run_id = "c" * 16
    WorkflowRunRepository().save(
        workflow_result(
            run_id,
            modelo=unit.modelo,
            period=unit.period,
            started_at=datetime(CONFORMANCE_YEAR, 1, 1, tzinfo=UTC),
            aborted_reason=WorkflowAbortReason.SITE_UNAVAILABLE,
        )
    )
    return ctx.request(ctx.profile_subject, {"profile_id": ctx.profile_id, "calculation_revision_id": revision_id})


def _modelo_work_wizard_context(ctx: PayloadContext) -> PayloadResult:
    unit = modelo_operation_test_support.seeded_modelo_work_unit(ctx.profile_id, operation=ctx.operation)
    return ctx.request(
        unit.work_unit_id,
        {
            "profile_id": ctx.profile_id,
            "work_unit_id": unit.work_unit_id,
            "output_language": OutputLanguage.ES,
        },
    )


def _modelo_work_revision(ctx: PayloadContext) -> PayloadResult:
    revision_id = modelo_operation_test_support.seeded_modelo_calculation_revision(
        ctx.profile_id, operation=ctx.operation
    )
    return ctx.request(ctx.raw_profile_subject, {"profile_id": ctx.profile_id, "calculation_revision_id": revision_id})


def _modelo_work_revision_snapshot(ctx: PayloadContext) -> PayloadResult:
    revision_id = modelo_operation_test_support.seeded_modelo_calculation_revision(
        ctx.profile_id, operation=ctx.operation
    )
    revision = CalculationRevisionCatalogueRepository().load().get(revision_id)
    assert revision is not None
    return ctx.request(revision.work_unit_id, {"profile_id": ctx.profile_id, "calculation_revision_id": revision_id})


def _modelo_work_revisions(ctx: PayloadContext) -> PayloadResult:
    modelo_operation_test_support.seeded_modelo_calculation_revision(ctx.profile_id, operation=ctx.operation)
    return ctx.request(ctx.profile_subject, {"profile_id": ctx.profile_id, "work_unit_id": None})


def _modelo_work_compare_taxation(ctx: PayloadContext) -> PayloadResult:
    unit = modelo_operation_test_support.seeded_modelo_work_unit(ctx.profile_id, operation=ctx.operation)
    return ctx.request(ctx.profile_subject, {"profile_id": ctx.profile_id, "work_unit_id": unit.work_unit_id})


def _modelo_review_package_build(ctx: PayloadContext) -> PayloadResult:
    revision_id, _report_id = modelo_operation_test_support.seeded_modelo_verification_report(
        ctx.profile_id, operation=ctx.operation
    )
    revision = CalculationRevisionCatalogueRepository().load().get(revision_id)
    assert revision is not None
    output_path = (ctx.tmp_path / "review-package.zip").resolve()
    return ctx.request(
        revision.work_unit_id,
        {
            "profile_id": ctx.profile_id,
            "calculation_revision_id": revision_id,
            "output_path": str(output_path),
            "actor": modelo_operation_test_support.MODELO_OPERATION_TEST_ACTOR,
        },
    )


def _modelo_work_m303_attestation(ctx: PayloadContext) -> PayloadResult:
    seed_modelo_ready_profile(bucket_id=str(ctx.profile_id), at=now(), tax_id=SEEDED_SOURCE_TAX_ID)
    upsert_test_profile_facts(
        str(ctx.profile_id),
        (UserProfileFact(path="censo.activity_start_date", value=date(CONFORMANCE_PRIOR_YEAR, 1, 1).isoformat()),),
    )
    return ctx.request(
        ctx.profile_subject,
        {
            "profile_id": ctx.profile_id,
            "work_unit_id": None,
            "period": PublicPeriod.from_period(Period.from_year_and_code(CONFORMANCE_PRIOR_YEAR, "4T")),
            "observed_at": now(),
            "actor": modelo_operation_test_support.MODELO_OPERATION_TEST_ACTOR,
        },
    )


def _modelo_m360_solicitud(ctx: PayloadContext) -> PayloadResult:
    return ctx.request(
        ctx.profile_subject,
        {
            "profile_id": ctx.profile_id,
            "action": "declare",
            "filing_year": CONFORMANCE_PRIOR_YEAR,
            "facts": Modelo360ProfileFacts(
                solicitud=Modelo360SolicitudFacts(
                    nivel_calidad_datos=M360NivelCalidadDatos.MAXIMA,
                    pais_destino="FR",
                    causa_presentacion=M360CausaPresentacion.INICIAL,
                ),
                solicitante=Modelo360SolicitanteFacts(
                    email="solicitante@example.es",
                    establecimiento=Modelo360EstablecimientoFacts(ambito=M360AmbitoEstablecimiento.TERRITORIO_COMUN),
                ),
                representante=Modelo360RepresentanteFacts(tax_id="00000000T", full_name="ASESORES PRUEBA SL"),
                cuenta=Modelo360CuentaTitularFacts(
                    titular_nombre="ASESORES PRUEBA SL",
                    titular_en_calidad_de=M360TitularEnCalidadDe.REPRESENTANTE,
                    divisa="EUR",
                ),
            ).model_dump(),
            "representante_account": Modelo360RepresentanteAccountInput(
                iban=OWN_ACCOUNT_SYNTHETIC_IBAN, swift_bic="CAIXESBBXXX"
            ),
        },
    )


def _modelo_work_report_verify(ctx: PayloadContext) -> PayloadResult:
    ctx.tmp_path.mkdir(parents=True, exist_ok=True)
    source = (ctx.tmp_path / "malformed-calculation-summary.pdf").resolve()
    source_bytes = b"synthetic malformed calculation summary PDF"
    source.write_bytes(source_bytes)
    return ctx.request(
        ctx.profile_subject,
        {
            "profile_id": ctx.profile_id,
            "source_path": str(source),
            "source_sha256": hashlib.sha256(source_bytes).hexdigest(),
        },
    )


def _modelo_export(ctx: PayloadContext) -> PayloadResult:
    # A DRAFT revision is not exportable. `_require_exportable_revision_state`
    # admits only SEALED states (VERIFICADO_COMPLETO, PRESENTADO,
    # PRESENTADO_SUPERSEDIDO), because a fichero is a filing-grade
    # artefact and a return still being edited has no business becoming
    # one. So this seeds through verification rather than calculation.
    revision_id, _report_id = modelo_operation_test_support.seeded_modelo_verification_report(
        ctx.profile_id, operation=ctx.operation
    )
    export_revision = CalculationRevisionCatalogueRepository().load(operation=ctx.operation).get(revision_id)
    assert export_revision is not None
    return ctx.request(
        export_revision.work_unit_id,
        {
            "calculation_revision_id": revision_id,
            "output_path": str(ctx.tmp_path / f"modelo-130-{CONFORMANCE_PRIOR_YEAR}-1T.txt"),
            "actor": modelo_operation_test_support.MODELO_OPERATION_TEST_ACTOR,
        },
    )


def _modelo_work_file(ctx: PayloadContext) -> PayloadResult:
    revision_id, report_id = modelo_operation_test_support.seeded_modelo_verification_report(
        ctx.profile_id, operation=ctx.operation
    )
    revision = CalculationRevisionCatalogueRepository().load().get(revision_id)
    assert revision is not None
    return ctx.request(
        revision.work_unit_id,
        {
            "approval": {
                "calculation_revision_id": revision_id,
                "verification_report_id": report_id,
            },
            "actor": modelo_operation_test_support.MODELO_OPERATION_TEST_ACTOR,
        },
    )


def _modelo_work_amend(ctx: PayloadContext) -> PayloadResult:
    filing_record_id, casilla_id = seeded_modelo_filing_record(ctx.profile_id, operation=ctx.operation)
    # The subject is the work unit that owns the filed record: the
    # access resolver reads that unit from the stored filing and
    # refuses any other subject.
    filed = ModeloRecordCatalogueRepository().load().get(filing_record_id)
    assert filed is not None
    return ctx.request(
        filed.work_unit_id,
        {
            "baseline": {"from_filing_record_id": filing_record_id},
            # The request model is strict: the enum instance and a tuple,
            # not their loose equivalents. A `.value` string and a list both
            # round-trip through JSON but are refused at the boundary, which
            # is the point of declaring the schema strict.
            "amendment_kind": FilingDeclarationKind.COMPLEMENTARIA,
            "overrides": ({"casilla_id": casilla_id, "value": "150.00"},),
            "reason": "corrected the declared base for the conformance matrix",
            "actor": modelo_operation_test_support.MODELO_OPERATION_TEST_ACTOR,
        },
    )


def _modelo_work_calculate(ctx: PayloadContext) -> PayloadResult:
    unit = modelo_operation_test_support.seeded_modelo_work_unit(ctx.profile_id, operation=ctx.operation)
    return ctx.request(
        unit.work_unit_id,
        {
            "work_unit_id": unit.work_unit_id,
            "actor": modelo_operation_test_support.MODELO_OPERATION_TEST_ACTOR,
        },
    )


def _modelo_work_wizard_attempt(ctx: PayloadContext) -> PayloadResult:
    unit = modelo_operation_test_support.seeded_modelo_work_unit(ctx.profile_id, operation=ctx.operation)
    return ctx.request(
        unit.work_unit_id,
        {
            "profile_id": ctx.profile_id,
            "output_language": OutputLanguage.ES,
            "calculation": ModeloWorkCalculateRequest(
                work_unit_id=unit.work_unit_id,
                actor=modelo_operation_test_support.MODELO_OPERATION_TEST_ACTOR,
            ),
        },
    )


def _modelo_work_verify(ctx: PayloadContext) -> PayloadResult:
    revision_id = modelo_operation_test_support.seeded_modelo_calculation_revision(
        ctx.profile_id, operation=ctx.operation
    )
    revision = CalculationRevisionCatalogueRepository().load().get(revision_id)
    assert revision is not None
    return ctx.request(
        revision.work_unit_id,
        {
            "calculation_revision_id": revision_id,
            "actor": modelo_operation_test_support.MODELO_OPERATION_TEST_ACTOR,
        },
    )


def _credit_resolution_request(ctx: PayloadContext, **fields: object) -> PayloadResult:
    """A request about a seeded calculation, which holds no disagreement for the finding id it names."""
    revision_id = modelo_operation_test_support.seeded_modelo_calculation_revision(
        ctx.profile_id, operation=ctx.operation
    )
    revision = CalculationRevisionCatalogueRepository().load().get(revision_id)
    assert revision is not None
    return ctx.request(
        revision.work_unit_id,
        {
            "profile_id": ctx.profile_id,
            "calculation_revision_id": revision_id,
            "output_language": OutputLanguage.ES,
            **fields,
        },
    )


def _modelo_work_disagreements(ctx: PayloadContext) -> PayloadResult:
    return _credit_resolution_request(ctx)


def _modelo_work_accept_disagreement(ctx: PayloadContext) -> PayloadResult:
    return _credit_resolution_request(
        ctx, finding_id="0" * 16, reason="accepted by the registered-executor conformance matrix"
    )


def _modelo_work_revoke_disagreement(ctx: PayloadContext) -> PayloadResult:
    return _credit_resolution_request(ctx, finding_id="0" * 16, expected_revision_id="0" * 64)


def _modelo_work_discard(ctx: PayloadContext) -> PayloadResult:
    # The baseline is the operator's EXACT APPROVAL, so it carries the
    # unit's state as observed rather than as re-read: name and
    # updated_at come off the seeded unit itself. A baseline resolved
    # inside the executor would match by construction and the
    # compare-and-swap this operation declares would never refuse.
    unit = modelo_operation_test_support.seeded_modelo_work_unit(ctx.profile_id, operation=ctx.operation)
    return ctx.request(
        unit.work_unit_id,
        {
            "baseline": {
                "work_unit_id": unit.work_unit_id,
                "name": unit.name,
                "observed_updated_at": unit.updated_at,
            },
            "reason": "discarded by the registered-executor conformance matrix",
            "actor": modelo_operation_test_support.MODELO_OPERATION_TEST_ACTOR,
        },
    )


MODELO_BUILDERS: dict[str, PayloadBuilder] = {
    "modelo.iva-wallet.correct": _modelo_iva_wallet_correct,
    "modelo.iva-wallet.balance": _modelo_iva_wallet_balance,
    "modelo.iva-wallet.seed": _modelo_iva_wallet_seed,
    "modelo.iva-wallet.override": _modelo_iva_wallet_override,
    "modelo.reconcile.import": _modelo_reconcile_import,
    "modelo.reconcile.pull": _modelo_reconcile_pull,
    "modelo.reconcile.list": _modelo_reconcile_list,
    "modelo.work.rename": _modelo_work_rename,
    "modelo.work.metadata": _modelo_work_metadata,
    "modelo.work.create": _modelo_work_create,
    "modelo.work.list": _modelo_work_list,
    "modelo.declarations.list": _modelo_declarations_list,
    "modelo.declarations.search": _modelo_declarations_search,
    "modelo.work.history": _modelo_work_history,
    "modelo.work.review": _modelo_work_review,
    "modelo.work.form": _modelo_work_form,
    "modelo.work.casilla_help": _modelo_work_casilla_help,
    "modelo.edit.renew": _modelo_edit_renew,
    "modelo.edit.preflight": _modelo_edit_submission,
    "modelo.edit.apply_prerequisite": _modelo_edit_apply_prerequisite,
    "modelo.work.filing_record": _modelo_filing_record_reader,
    "modelo.filing_record.view": _modelo_filing_record_reader,
    "modelo.filing_record.list": _modelo_filing_record_list,
    "modelo.verification_report.list": _modelo_verification_report_list,
    "modelo.verification_report.view": _modelo_verification_report_view,
    "modelo.observation.local": _modelo_observation_local,
    "modelo.filing_record.import": _modelo_filing_record_import,
    "modelo.work.amendment_context": _modelo_filing_record_reader,
    "modelo.work.dependencies": _modelo_work_dependencies,
    "workflow.run.read": _workflow_run_read,
    **{definition_id: _overview_read for definition_id in OVERVIEW_READ_DEFINITION_IDS.values()},
    "overview.pipeline": _overview_pipeline,
    "workflow.run.list": _workflow_run_list,
    "workflow.resume.context": _workflow_resume_context,
    "modelo.work.wizard_context": _modelo_work_wizard_context,
    "modelo.work.revision": _modelo_work_revision,
    "modelo.work.revision_snapshot": _modelo_work_revision_snapshot,
    "modelo.work.revisions": _modelo_work_revisions,
    "modelo.work.compare_taxation": _modelo_work_compare_taxation,
    "modelo.review_package.build": _modelo_review_package_build,
    "modelo.work.m303_attestation": _modelo_work_m303_attestation,
    "modelo.m360_solicitud": _modelo_m360_solicitud,
    "modelo.work.report_verify": _modelo_work_report_verify,
    "modelo.export": _modelo_export,
    "modelo.edit.apply": _modelo_edit_submission,
    "modelo.work.file": _modelo_work_file,
    "modelo.work.amend": _modelo_work_amend,
    "modelo.work.calculate": _modelo_work_calculate,
    "modelo.work.wizard_attempt": _modelo_work_wizard_attempt,
    "modelo.work.verify": _modelo_work_verify,
    "modelo.work.discard": _modelo_work_discard,
    "modelo.work.disagreements": _modelo_work_disagreements,
    "modelo.work.accept_disagreement": _modelo_work_accept_disagreement,
    "modelo.work.revoke_disagreement": _modelo_work_revoke_disagreement,
}

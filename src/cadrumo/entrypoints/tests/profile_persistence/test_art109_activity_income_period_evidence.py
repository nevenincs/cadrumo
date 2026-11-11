"""Art. 109 current-period activity-income coverage tests.

The advisory is built by the verification finding collector from the quarter's
persisted ledger rows. The rows are bank movements linking no invoice, which only
the cobros y pagos criterion places in a quarter (RIRPF art. 7.2), so the profile
declares that election for 2026 under its directa normal regime. That grounds
boxes 01, 02 and the activity withholding of box 06, so verify passes the
calculation-note gate on every quarter, each holding a withheld receipt, and builds its advisories.
"""

from __future__ import annotations

from collections.abc import Iterator
from datetime import UTC, date, datetime
from decimal import Decimal
from pathlib import Path

import pytest

from cadrumo.adapters.persistence.profile.buckets import BucketEventHistoryRepository
from cadrumo.adapters.persistence.profile.invoices import InvoiceCatalogueRepository
from cadrumo.adapters.persistence.profile.modelos_calculation import CalculationRevisionCatalogueRepository
from cadrumo.adapters.persistence.profile.modelos_work_units import WorkUnitCatalogueRepository
from cadrumo.adapters.persistence.profile.transactions import TransactionCatalogueRepository
from cadrumo.adapters.persistence.storage.operator_scope import build_operator_scope_ports
from cadrumo.adapters.persistence.storage.sql.secure_objects import SecureObjectRepository
from cadrumo.adapters.persistence.storage.tests.profile_capsule_runtime import upsert_test_profile_facts
from cadrumo.adapters.persistence.storage.tests.secure_sql import isolated_runtime_profile
from cadrumo.application.modelo.calculation_bucket_actions import (
    calculate_modelo_revision_from_bucket_aggregation_with_diagnostics,
)
from cadrumo.application.modelo.verification_actions import verify_modelo_revision_with_preconditions
from cadrumo.application.modelo.verification_revision_findings import collect_revision_verification_findings
from cadrumo.application.modelo.work_lifecycle import create_work_unit
from cadrumo.application.modelo.work_lifecycle_ports import WorkLifecyclePorts
from cadrumo.core.period import Period
from cadrumo.core.tipos_actividad import TipoActividad
from cadrumo.domain.calculations.registry.authority import PinnedAuthorityOperation, bundled_indexed_authority
from cadrumo.domain.calculations.registry.tests.authored_editions import filing_year_envelope, open_ended_revision
from cadrumo.domain.modelos.calculation_revision import CalculationRevision
from cadrumo.domain.modelos.verification_report import (
    ModeloVerificationFinding,
    ModeloVerificationFindingKind,
    ModeloVerificationFindingSeverity,
)
from cadrumo.domain.modelos.work_unit import WorkUnit
from cadrumo.domain.transactions.enums import BusinessClassification, TransactionDirection, TransactionLifecycleState
from cadrumo.domain.transactions.models import Transaction, TransactionCatalogue
from cadrumo.domain.transactions.raw_transaction import RawProvenance, RawTransaction, SourceFormat
from cadrumo.domain.user_profile.tests.imputation_criterion_facts import cash_criterion_facts
from cadrumo.entrypoints.tests.profile_persistence.file_flow_test_support import calculation_ports_for_test
from cadrumo.entrypoints.tests.profile_persistence.verification_repository_support import (
    build_test_certificate_secret_backend_factory,
    build_test_verification_repository_bundle,
)
from cadrumo.entrypoints.tests.profile_persistence.verification_substance_support import (
    CASILLA_05,
    CASILLA_06,
    CASILLA_16,
    CASILLA_18,
    T0,
    T1,
    T2,
    seed_ready_profile,
    workflow_profile,
)

_YEAR = filing_year_envelope().horizon

_OPERATOR_SCOPE_PORTS = build_operator_scope_ports()

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint]

_BUCKET_ID = "13000000-0000-4000-8000-000000000408"
_Q1 = Period.from_year_and_code(_YEAR, "1T")
_ADVISORY_BINDING_VALUE = "advisory_binding_value"


def _raw_transaction(provider_id: str, *, value_date: date, amount: Decimal) -> RawTransaction:
    return RawTransaction(
        provider_transaction_id=provider_id,
        booked_date=value_date,
        value_date=value_date,
        amount=amount,
        currency="EUR",
        counterparty="Cliente SA",
        description=f"activity income {provider_id}",
        provenance=RawProvenance(
            source_path=Path(__file__),
            source_sha256="a" * 64,
            source_row_index=1,
            source_format=SourceFormat.CSV,
            ingested_at=datetime(_YEAR, 4, 6, 12, 0, tzinfo=UTC),
            provider_name="CSV provider",
        ),
        raw_fields={"Concepto": provider_id},
    )


def _activity_invoice(
    provider_id: str,
    *,
    value_date: date = date(_YEAR, 2, 15),
    base: Decimal,
    iva: Decimal,
    withholding: Decimal,
) -> Transaction:
    return Transaction.model_validate(
        {
            "raw": _raw_transaction(
                provider_id,
                value_date=value_date,
                amount=base + iva - withholding,
            ),
            "direction": TransactionDirection.INCOMING,
            "group_label": None,
            "source_jurisdiction": "ES",
            "business_classification": BusinessClassification.NOT_YET_PROCESSED,
            "business_pct": None,
            "purchase_invoice_evidence_id": None,
            "category_id": None,
            "taxable_base": base,
            "iva_rate": Decimal("0.21"),
            "iva_amount": iva,
            "irpf_category": "actividad_economica",
            "tipo_actividad": TipoActividad.A05_PROFESIONALES,
            "lifecycle_state": TransactionLifecycleState.ACTIVE,
            "classified_at": datetime(_YEAR, 4, 6, 13, 0, tzinfo=UTC),
            "classified_by": "manual",
        },
    )


def _gross_only_activity_receipt(provider_id: str, *, amount: Decimal) -> Transaction:
    return Transaction.model_validate(
        {
            "raw": _raw_transaction(provider_id, value_date=date(_YEAR, 2, 20), amount=amount),
            "direction": TransactionDirection.INCOMING,
            "group_label": None,
            "source_jurisdiction": "ES",
            "business_classification": BusinessClassification.NOT_YET_PROCESSED,
            "business_pct": None,
            "purchase_invoice_evidence_id": None,
            "category_id": None,
            "taxable_base": None,
            "iva_rate": None,
            "iva_amount": None,
            "irpf_category": "actividad_economica",
            "tipo_actividad": TipoActividad.A05_PROFESIONALES,
            "lifecycle_state": TransactionLifecycleState.ACTIVE,
            "classified_at": datetime(_YEAR, 4, 6, 13, 0, tzinfo=UTC),
            "classified_by": "manual",
        },
    )


def _positive_threshold_transactions() -> tuple[Transaction, ...]:
    return (
        _activity_invoice(
            "withheld-70",
            base=Decimal("700.00"),
            iva=Decimal("147.00"),
            withholding=Decimal("105.00"),
        ),
        _activity_invoice(
            "not-withheld-30",
            base=Decimal("300.00"),
            iva=Decimal("63.00"),
            withholding=Decimal("0.00"),
        ),
    )


def _below_threshold_transactions() -> tuple[Transaction, ...]:
    return (
        _activity_invoice(
            "withheld-60",
            base=Decimal("600.00"),
            iva=Decimal("126.00"),
            withholding=Decimal("90.00"),
        ),
        _activity_invoice(
            "not-withheld-40",
            base=Decimal("400.00"),
            iva=Decimal("84.00"),
            withholding=Decimal("0.00"),
        ),
    )


def _insufficient_transactions() -> tuple[Transaction, ...]:
    return (
        _activity_invoice(
            "withheld-70",
            base=Decimal("700.00"),
            iva=Decimal("147.00"),
            withholding=Decimal("105.00"),
        ),
        _gross_only_activity_receipt("gross-only-30", amount=Decimal("300.00")),
    )


def test_art109_period_evidence_derives_true_at_70_percent_from_current_period_rows(
    objects: SecureObjectRepository, *, operation: PinnedAuthorityOperation
) -> None:
    findings = _art109_findings(
        objects,
        transactions=_positive_threshold_transactions(),
        profile_flag=False,
        operation=operation,
    )

    assert len(findings) == 1


def test_art109_period_evidence_derives_false_below_70_percent(
    objects: SecureObjectRepository, *, operation: PinnedAuthorityOperation
) -> None:
    findings = _art109_findings(
        objects,
        transactions=_below_threshold_transactions(),
        profile_flag=True,
        operation=operation,
    )

    assert findings == []


def test_art109_period_evidence_fails_closed_when_gross_only_receipt_cannot_prove_denominator(
    objects: SecureObjectRepository, *, operation: PinnedAuthorityOperation
) -> None:
    findings = _art109_findings(
        objects,
        transactions=_insufficient_transactions(),
        profile_flag=True,
        operation=operation,
    )

    assert len(findings) == 1


@pytest.fixture
def objects(tmp_path: Path) -> Iterator[SecureObjectRepository]:
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=_BUCKET_ID) as profile:
        seed_ready_profile(bucket_id=_BUCKET_ID)
        upsert_test_profile_facts(
            _BUCKET_ID, (fact for fact in cash_criterion_facts(2026) if fact.path != "irpf.estimation_regime")
        )
        yield profile.repository


def _calculate_m130_draft(
    objects: SecureObjectRepository, *, operation: PinnedAuthorityOperation
) -> tuple[WorkUnit, CalculationRevision]:
    wu_repo = WorkUnitCatalogueRepository(objects=objects)
    cr_repo = CalculationRevisionCatalogueRepository(objects=objects)
    bv_repo = BucketEventHistoryRepository(objects=objects)
    work_unit = create_work_unit(
        bucket_id=_BUCKET_ID,
        modelo="130",
        filing_year=_YEAR,
        period=_Q1,
        revision_id=str(open_ended_revision("130").id),
        ports=WorkLifecyclePorts(
            work_unit_repository=wu_repo, bucket_event_repository=BucketEventHistoryRepository(objects=objects)
        ),
        clock=T0,
        operation=operation,
    )
    with calculation_ports_for_test(
        bucket_id=_BUCKET_ID,
        work_unit_repository=wu_repo,
        calculation_repository=cr_repo,
        bucket_event_repository=bv_repo,
    ) as _calculation_ports_255:
        revision = calculate_modelo_revision_from_bucket_aggregation_with_diagnostics(
            work_unit.work_unit_id,
            casilla_inputs={
                CASILLA_05: Decimal("0.00"),
                CASILLA_06: Decimal("0.00"),
                CASILLA_16: Decimal("0.00"),
                CASILLA_18: Decimal("0.00"),
            },
            binding_values={
                "irpf.previous_year_economic_activity_net_income": Decimal("20000.00"),
                "modelo-130-resultados-negativos-anteriores": Decimal("0.00"),
            },
            ports=_calculation_ports_255,
            clock=T1,
        ).revision
    return work_unit, revision


def _art109_findings(
    objects: SecureObjectRepository,
    *,
    transactions: tuple[Transaction, ...],
    profile_flag: bool,
    operation: PinnedAuthorityOperation,
) -> list[ModeloVerificationFinding]:
    """Collect the Art. 109 advisories the verification builds for the persisted calculation."""
    _, revision = _calculate_over_quarter_ledger(objects, transactions=transactions, operation=operation)
    return _collect_art109_findings(objects, revision=revision, profile_flag=profile_flag)


def _calculate_over_quarter_ledger(
    objects: SecureObjectRepository,
    *,
    transactions: tuple[Transaction, ...],
    operation: PinnedAuthorityOperation,
) -> tuple[WorkUnit, CalculationRevision]:
    # The quarter's activity rows are the ledger the calculation sources casillas 01 and 02 from.
    tx_repo = TransactionCatalogueRepository(bucket_id=_BUCKET_ID, objects=objects)
    tx_repo.save(TransactionCatalogue.from_transactions(transactions))
    return _calculate_m130_draft(objects, operation=operation)


def _collect_art109_findings(
    objects: SecureObjectRepository,
    *,
    revision: CalculationRevision,
    profile_flag: bool,
) -> list[ModeloVerificationFinding]:
    work_unit = WorkUnitCatalogueRepository(objects=objects).load().work_units[revision.work_unit_id]
    with bundled_indexed_authority().operation() as verify_operation:
        findings, _resolved, _missing, _failures = collect_revision_verification_findings(
            work_unit=work_unit,
            target=revision,
            profile=workflow_profile().model_copy(
                update={"art109_activity_income_withholding_ge_70pct": profile_flag},
            ),
            transaction_repository=TransactionCatalogueRepository(bucket_id=_BUCKET_ID, objects=objects),
            invoice_repository=InvoiceCatalogueRepository(bucket_id=_BUCKET_ID, objects=objects),
            operation=verify_operation,
            work_profile=None,
        )
    return [
        finding
        for finding in findings
        if finding.kind is ModeloVerificationFindingKind.ADVISORY and "rd-439-2007:art-109" in finding.legal_refs
    ]


def _verify_art109_findings(
    objects: SecureObjectRepository,
    *,
    transactions: tuple[Transaction, ...],
    profile_flag: bool,
    operation: PinnedAuthorityOperation,
) -> list[ModeloVerificationFinding]:
    """Verify the quarter past the calculation-note gate, and return the Art. 109 advisories it built."""
    _, revision = _calculate_over_quarter_ledger(objects, transactions=transactions, operation=operation)
    assert not [issue for issue in revision.source_issues if issue.reason == _ADVISORY_BINDING_VALUE]
    with bundled_indexed_authority().operation() as verify_operation:
        result = verify_modelo_revision_with_preconditions(
            revision.calculation_revision_id,
            certificate_secret_backend_factory=build_test_certificate_secret_backend_factory(),
            verification_repositories=build_test_verification_repository_bundle(),
            actor="operator-test",
            workflow_profile=workflow_profile().model_copy(
                update={"art109_activity_income_withholding_ge_70pct": profile_flag},
            ),
            clock=T2,
            operator_scope_ports=_OPERATOR_SCOPE_PORTS,
            operation=verify_operation,
        )
    # The quarter has no prior-year return on record, so the report holds cross-period blockers; box 06 holds none.
    assert not [
        finding
        for finding in result.report.findings
        if finding.casilla_id == CASILLA_06 and finding.severity is ModeloVerificationFindingSeverity.BLOCKING
    ], result.report.findings
    return _collect_art109_findings(objects, revision=revision, profile_flag=profile_flag)


def test_verify_art109_advisory_uses_proven_period_evidence_when_profile_flag_is_false(
    objects: SecureObjectRepository, *, operation: PinnedAuthorityOperation
) -> None:
    findings = _verify_art109_findings(
        objects,
        transactions=_positive_threshold_transactions(),
        profile_flag=False,
        operation=operation,
    )

    assert len(findings) == 1


def test_verify_art109_advisory_proven_below_threshold_overrides_declared_profile_flag(
    objects: SecureObjectRepository, *, operation: PinnedAuthorityOperation
) -> None:
    findings = _verify_art109_findings(
        objects,
        transactions=_below_threshold_transactions(),
        profile_flag=True,
        operation=operation,
    )

    assert findings == []


def test_verify_art109_advisory_keeps_declared_profile_fact_when_period_evidence_is_insufficient(
    objects: SecureObjectRepository, *, operation: PinnedAuthorityOperation
) -> None:
    findings = _verify_art109_findings(
        objects,
        transactions=_insufficient_transactions(),
        profile_flag=True,
        operation=operation,
    )

    assert len(findings) == 1

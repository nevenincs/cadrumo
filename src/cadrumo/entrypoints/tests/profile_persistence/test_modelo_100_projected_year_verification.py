"""Verifying a Modelo 100 return refuses a year no edition authors and still verifies an authored one.

A year above the newest authored edition calculates through the registry's nearest
edition, which is a projection and not the reviewed design of that year. Each case runs
the real calculation and the real verification over encrypted profile storage. The
newest authored exercise and an earlier authored one verify as before; the first
exercise past the newest is refused with a blocking finding that names the edition it
is carried from, persists a report that grants nothing, and leaves the revision a draft.
Every year derives from the published authority.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, date, datetime
from decimal import Decimal
from pathlib import Path

import pytest

from cadrumo.application.user_profile.tests.persona_profile_facts import persona_facts_beneath
from cadrumo.domain.user_profile.tests.profile_creation_authority import profile_creation_context_for_test

from ....adapters.persistence.profile.buckets import BucketEventHistoryRepository
from ....adapters.persistence.profile.modelos_calculation import CalculationRevisionCatalogueRepository
from ....adapters.persistence.profile.modelos_verification_reports import VerificationReportCatalogueRepository
from ....adapters.persistence.profile.modelos_work_units import WorkUnitCatalogueRepository
from ....adapters.persistence.storage.operator_scope import build_operator_scope_ports
from ....adapters.persistence.storage.tests.profile_capsule_runtime import seed_test_profile_record
from ....adapters.persistence.storage.tests.secure_sql import isolated_runtime_profile
from ....application.modelo.calculation_bucket_actions import (
    calculate_modelo_revision_from_bucket_aggregation_with_diagnostics,
)
from ....application.modelo.calculation_source_policy import BUCKET_AGGREGATION_LOCK_SOURCES
from ....application.modelo.operation_shared import resolve_active_workflow_profile
from ....application.modelo.verification_actions import verify_modelo_revision_with_preconditions
from ....application.modelo.work_addressing import law_selected_revision_for_work_target
from ....application.modelo.work_lifecycle import create_work_unit
from ....core.authority_grade import RegistryAuthorityGrade
from ....core.identity.hex_ids import WorkUnitId
from ....core.period import Period
from ....domain.calculations.registry.authority import bundled_indexed_authority
from ....domain.calculations.registry.ids import BindingId, RelationId
from ....domain.calculations.registry.relations import relation_prefill_bindings_for_period
from ....domain.calculations.registry.tests.authored_editions import (
    newest_authored_edition,
    newest_authored_editions,
    projected_exercise,
)
from ....domain.modelos.calculation_revision import CalculationRevision, CalculationRevisionState
from ....domain.modelos.verification_report import (
    ModeloVerificationFinding,
    ModeloVerificationFindingKind,
    ModeloVerificationFindingSeverity,
    VerificationReport,
)
from ....domain.user_profile.values import ProfileSetupState, UserProfileFact, create_user_profile_record
from ...adapter_composition_work_ports import build_work_lifecycle_ports
from .file_flow_test_support import calculation_ports_for_test
from .general_iva_profile_facts_support import renta_single_taxpayer_facts
from .verification_repository_support import (
    build_test_certificate_secret_backend_factory,
    build_test_verification_repository_bundle,
)
from .work_income_support import record_work_income

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint]

_MODELO = "100"
_PERIOD = "0A"
_PROJECTED_KEY = "application.modelo.findings.registry_filing_year_projected"
_WORK_INCOME = Decimal("40000.00")
_TAXPAYER_TAX_ID = "12345678Z"
_PROFILE_ID = "10010000-0000-4100-8100-000000000504"
_CLOCK = datetime(2026, 6, 30, 9, 0, 0, tzinfo=UTC)
_NO_PENDING_NEGATIVE_BASES: dict[BindingId, Decimal] = {
    **{
        f"renta-base-liquidable-negativa-general-{origin}": Decimal("0")
        for origin in ("em4-pendiente-inicio", "em3-pendiente-inicio", "em2-pendiente-inicio", "anterior")
    },
    **{
        f"renta-saldo-negativo-{kind}-ahorro-{origin}-pendiente-inicio": Decimal("0")
        for kind in ("rcm", "gyp")
        for origin in ("em1", "em2", "em3", "em4")
    },
}
"""The pending negative general bases (LIRPF art. 50.3) and savings balances (art. 49) a single employee states as none."""


def _seed_profile(filing_year: int) -> None:
    """Seed a complete single employee who states no dependants and records that no payer withheld."""
    record = create_user_profile_record(
        setup_state=ProfileSetupState.COMPLETE,
        profile_id=_PROFILE_ID,
        facts=persona_facts_beneath(
            (
                UserProfileFact(path="identity.tax_id", value=_TAXPAYER_TAX_ID),
                UserProfileFact(path="identity.name", value="Test"),
                UserProfileFact(path="identity.surnames", value="Operator"),
                UserProfileFact(path="taxpayer_type.irpf_income_categories", value="trabajo"),
                *renta_single_taxpayer_facts(birth_date=date(1980, 3, 15)),
            ),
            without=("irpf.estimation_regime", "activities.", "censo.activity_start_date"),
        ),
        created_at=_CLOCK,
        updated_at=_CLOCK,
        context=profile_creation_context_for_test(),
    )
    seed_test_profile_record(record)
    with bundled_indexed_authority().operation() as operation:
        record_work_income(
            operation=operation, taxpayer_tax_id=_TAXPAYER_TAX_ID, filing_year=filing_year, gross=_WORK_INCOME
        )


@dataclass(frozen=True)
class _Verified:
    revision: CalculationRevision
    stored: CalculationRevision | None
    report: VerificationReport
    stored_reports: tuple[VerificationReport, ...]


def _operator_answers(filing_year: int) -> tuple[dict[BindingId, Decimal], dict[RelationId, Decimal]]:
    """Zero the money and manual answers no profile fact, record or ledger owns, and state no pending stock."""
    with bundled_indexed_authority().operation() as operation:
        snapshot = operation.reading_snapshot(_MODELO, filing_year=filing_year, period=_PERIOD)
    answers = {
        binding.id: Decimal("0")
        for binding in snapshot.revision.bindings
        if binding.source != "profile"
        and binding.source not in BUCKET_AGGREGATION_LOCK_SOURCES
        and binding.provider.kind not in {"retencion_soportada", "previous_filing"}
        and (binding.value.data_type == "money" or binding.source == "manual_input")
    }
    answers.update(_NO_PENDING_NEGATIVE_BASES)
    relations = {
        binding.id: Decimal("0")
        for binding, _provider in relation_prefill_bindings_for_period(snapshot.revision, period=snapshot.period)
    }
    return answers, relations


def _create_work_unit(filing_year: int) -> WorkUnitId:
    period = Period.from_year_and_code(filing_year, _PERIOD)
    with bundled_indexed_authority().operation() as operation:
        return create_work_unit(
            bucket_id=_PROFILE_ID,
            modelo=_MODELO,
            filing_year=filing_year,
            period=period,
            revision_id=law_selected_revision_for_work_target(
                modelo=_MODELO, filing_year=filing_year, period=period, operation=operation
            ),
            ports=build_work_lifecycle_ports(bucket_id=_PROFILE_ID),
            operation=operation,
            clock=_CLOCK,
        ).work_unit_id


def _calculate(filing_year: int, work_unit_id: WorkUnitId) -> CalculationRevision:
    binding_values, relation_values = _operator_answers(filing_year)
    with calculation_ports_for_test(
        bucket_id=_PROFILE_ID,
        work_unit_repository=WorkUnitCatalogueRepository(),
        calculation_repository=CalculationRevisionCatalogueRepository(),
        bucket_event_repository=BucketEventHistoryRepository(),
    ) as ports:
        return calculate_modelo_revision_from_bucket_aggregation_with_diagnostics(
            work_unit_id,
            actor=_PROFILE_ID,
            casilla_inputs={},
            binding_values=binding_values,
            relation_values=relation_values,
            ports=ports,
            clock=_CLOCK,
        ).revision


def _verify(tmp_path: Path, filing_year: int) -> _Verified:
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=_PROFILE_ID):
        _seed_profile(filing_year)
        revision = _calculate(filing_year, _create_work_unit(filing_year))
        with bundled_indexed_authority().operation() as operation:
            report = verify_modelo_revision_with_preconditions(
                str(revision.calculation_revision_id),
                certificate_secret_backend_factory=build_test_certificate_secret_backend_factory(),
                operator_scope_ports=build_operator_scope_ports(),
                actor="projected-year-verification",
                workflow_profile=resolve_active_workflow_profile(operation),
                verification_repositories=build_test_verification_repository_bundle(),
                clock=_CLOCK,
                operation=operation,
            ).report
        stored = CalculationRevisionCatalogueRepository().load().get(revision.calculation_revision_id)
        stored_reports = tuple(VerificationReportCatalogueRepository().load().reports.values())
    return _Verified(revision=revision, stored=stored, report=report, stored_reports=stored_reports)


def _blocking(report: VerificationReport) -> list[ModeloVerificationFinding]:
    return [
        finding
        for finding in report.findings
        if finding.kind is ModeloVerificationFindingKind.BLOCKING_RULE
        and finding.severity is ModeloVerificationFindingSeverity.BLOCKING
    ]


@pytest.mark.parametrize("filing_year", newest_authored_editions(_MODELO, 2))
def test_an_authored_year_verifies_as_filing_grade(tmp_path: Path, filing_year: int) -> None:
    verified = _verify(tmp_path, filing_year)

    assert verified.report.granted_verificado_completo is True, verified.report.findings
    assert _blocking(verified.report) == []
    assert all(finding.message_locale_key != _PROJECTED_KEY for finding in verified.report.findings)
    assert verified.stored is not None
    assert verified.stored.state is CalculationRevisionState.VERIFICADO_COMPLETO


def test_a_projected_year_calculates_but_is_refused_as_a_filing_claim(tmp_path: Path) -> None:
    projected = projected_exercise(_MODELO)

    verified = _verify(tmp_path, projected)

    assert verified.revision.registry_snapshot_ref.modelo_year == projected
    assert verified.revision.registry_snapshot_ref.revision_id == str(newest_authored_edition(_MODELO))
    assert verified.report.granted_verificado_completo is False
    assert verified.report.resolved_casilla_ids == ()
    (finding,) = _blocking(verified.report)
    assert finding.message_locale_key == _PROJECTED_KEY
    assert dict(finding.message_facts) == {
        "modelo": _MODELO,
        "filing_year": projected,
        "period": _PERIOD,
        "authored_filing_year": newest_authored_edition(_MODELO),
    }
    assert verified.stored_reports == (verified.report,)
    assert verified.stored is not None
    assert verified.stored.state is CalculationRevisionState.BORRADOR
    assert verified.stored.verified_at is None


def test_the_projected_year_still_reads_at_calculation_grade() -> None:
    projected = projected_exercise(_MODELO)

    with bundled_indexed_authority().operation() as operation:
        snapshot = operation.reading_snapshot(_MODELO, filing_year=projected, period=_PERIOD)

    assert snapshot.filing_year == projected
    assert snapshot.effective_authority_grade is RegistryAuthorityGrade.CALCULATION

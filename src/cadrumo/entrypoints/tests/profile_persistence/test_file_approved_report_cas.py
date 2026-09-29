"""Encrypted filing tests for exact review consent and atomic catalogue guards."""

from __future__ import annotations

from dataclasses import replace
from decimal import Decimal
from typing import override

import pytest

from cadrumo.adapters.persistence.profile.modelos_calculation import CalculationRevisionCatalogueRepository
from cadrumo.adapters.persistence.profile.modelos_filing import ModeloRecordCatalogueRepository
from cadrumo.adapters.persistence.profile.modelos_verification_reports import VerificationReportCatalogueRepository
from cadrumo.adapters.persistence.profile.modelos_work_units import WorkUnitCatalogueRepository
from cadrumo.adapters.persistence.profile.tests.cross_period_seeding import seed_clean_cross_period_sources
from cadrumo.adapters.persistence.storage.errors import SecureObjectRevisionConflictError
from cadrumo.adapters.persistence.storage.operator_scope import build_operator_scope_ports
from cadrumo.adapters.persistence.storage.runtime_repository import secure_object_repository_for_bucket
from cadrumo.application.modelo.action_errors import CalculationRevisionStateError, VerificationReportNotFoundError
from cadrumo.application.modelo.calculation_actions import calculate_modelo_revision
from cadrumo.application.modelo.filing_actions import ModeloFilingResult, file_modelo_revision
from cadrumo.core.secure_object_write import SecureObjectWrite
from cadrumo.domain.buckets.event import BucketEventType
from cadrumo.domain.calculations.registry.authority import PinnedAuthorityOperation, bundled_indexed_authority
from cadrumo.domain.modelos.calculation_revision import CalculationRevisionCatalogue, CalculationRevisionState
from cadrumo.domain.modelos.filing_record import ModeloRecordCatalogue
from cadrumo.domain.modelos.verification_report import (
    VerificationReport,
    VerificationReportCatalogue,
    derive_verification_report_id,
)
from cadrumo.domain.modelos.verification_repository import upsert_verification_report
from cadrumo.domain.modelos.work_unit import WorkUnitCatalogue
from cadrumo.entrypoints.adapter_composition import build_filing_action_ports
from cadrumo.entrypoints.tests.profile_persistence.file_flow_test_support import (
    DEFAULT_130_BASELINE_INPUTS,
    DEFAULT_130_BINDING_VALUES,
    M130_INCOME_CASILLA,
    T1,
    T2,
    T3,
    T4,
    Repos,
    calculation_ports_for_test,
    seed_work_unit,
    verify_revision,
    workflow_gate,
)
from cadrumo.entrypoints.tests.profile_persistence.verification_repository_support import (
    build_test_certificate_secret_backend_factory,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint]


class _ReportRevisionChangedBeforeCommit(VerificationReportCatalogueRepository):
    """Advance only the real encrypted report row after filing captures its CAS."""

    @override
    def to_secure_object_write(
        self,
        catalogue: VerificationReportCatalogue,
        *,
        expected_revision_id: str,
        operation: PinnedAuthorityOperation | None = None,
    ) -> SecureObjectWrite:
        write = super().to_secure_object_write(
            catalogue, expected_revision_id=expected_revision_id, operation=operation
        )
        self.save(catalogue, operation=operation)
        return write


class _CalculationRevisionChangedBeforeCommit(CalculationRevisionCatalogueRepository):
    """Advance the current encrypted calculation row before its guarded batch."""

    @override
    def to_secure_object_write(
        self,
        catalogue: CalculationRevisionCatalogue,
        *,
        expected_revision_id: str | None = None,
    ) -> SecureObjectWrite:
        """Keep the old row but change its persistence revision after the read."""
        write = super().to_secure_object_write(catalogue, expected_revision_id=expected_revision_id)
        self.save(self.load())
        return write


class _WorkUnitRevisionChangedBeforeCommit(WorkUnitCatalogueRepository):
    """Advance the current encrypted work-unit row before its guarded batch."""

    @override
    def to_secure_object_write(
        self,
        catalogue: WorkUnitCatalogue,
        *,
        expected_revision_id: str | None = None,
    ) -> SecureObjectWrite:
        """Keep the old row but change its persistence revision after the read."""
        write = super().to_secure_object_write(catalogue, expected_revision_id=expected_revision_id)
        self.save(self.load())
        return write


class _FilingRevisionChangedBeforeCommit(ModeloRecordCatalogueRepository):
    """Advance the encrypted filing row just before the guarded batch."""

    @override
    def save_with_secure_object_writes(
        self,
        catalogue: ModeloRecordCatalogue,
        extra_writes: tuple[SecureObjectWrite, ...],
        *,
        expected_revision_id: str | None = None,
    ) -> None:
        """Keep the old row but change its persistence revision before commit."""
        self.save(self.load())
        super().save_with_secure_object_writes(
            catalogue,
            extra_writes,
            expected_revision_id=expected_revision_id,
        )


class _FilingRevisionChangedBeforePersistenceRead(ModeloRecordCatalogueRepository):
    """Change the encrypted filing lineage between preflight and persistence."""

    @override
    def load_revisioned(self) -> tuple[ModeloRecordCatalogue, str]:
        """Advance lineage on each read while retaining the same safe content."""
        self.save(self.load())
        return super().load_revisioned()


def _verified_target(repos: Repos):
    work_units, calculations, filings, reports, events = repos
    work_unit = seed_work_unit(work_units)
    with calculation_ports_for_test(
        bucket_id=work_unit.bucket_id,
        work_unit_repository=work_units,
        calculation_repository=calculations,
        bucket_event_repository=events,
    ) as ports:
        draft = calculate_modelo_revision(
            work_unit.work_unit_id,
            casilla_inputs={**DEFAULT_130_BASELINE_INPUTS, M130_INCOME_CASILLA: Decimal("1000")},
            binding_values=DEFAULT_130_BINDING_VALUES,
            ports=ports,
            clock=T1,
        )
    verify_revision(
        draft.calculation_revision_id,
        revision=draft,
        work_unit=work_unit,
        actor="operator-A",
        work_unit_repository=work_units,
        calculation_repository=calculations,
        verification_repository=reports,
        filing_repository=filings,
        bucket_event_repository=events,
        clock=T2,
    )
    granting = tuple(
        report
        for report in reports.load().reports.values()
        if report.calculation_revision_id == draft.calculation_revision_id and report.granted_verificado_completo
    )
    assert len(granting) == 1
    return work_unit, draft, granting[0].verification_report_id


def _file(repos: Repos, work_unit, draft, report_id: str, *, race: str | None = None, clock=T3) -> ModeloFilingResult:
    work_units, calculations, filings, _reports, events = repos
    with bundled_indexed_authority().operation() as operation:
        seed_clean_cross_period_sources(
            work_unit,
            work_unit_repository=work_units,
            calculation_repository=calculations,
            filing_repository=filings,
            bucket_event_repository=events,
            operation=operation,
        )
        gate = workflow_gate(revision=draft, work_unit=work_unit, clock=clock, operation=operation)
        ports = build_filing_action_ports(bucket_id=work_unit.bucket_id)
        objects = secure_object_repository_for_bucket(work_unit.bucket_id)
        if race == "report":
            ports = replace(
                ports,
                verification_repository=_ReportRevisionChangedBeforeCommit(objects=objects),
            )
        elif race == "calculation":
            ports = replace(ports, calculation_repository=_CalculationRevisionChangedBeforeCommit(objects=objects))
        elif race == "work_unit":
            ports = replace(ports, work_unit_repository=_WorkUnitRevisionChangedBeforeCommit(objects=objects))
        elif race == "filing":
            ports = replace(ports, filing_repository=_FilingRevisionChangedBeforeCommit(objects=objects))
        elif race == "filing_preflight":
            ports = replace(ports, filing_repository=_FilingRevisionChangedBeforePersistenceRead(objects=objects))
        return file_modelo_revision(
            draft.calculation_revision_id,
            approved_verification_report_id=report_id,
            certificate_secret_backend_factory=build_test_certificate_secret_backend_factory(),
            operator_scope_ports=build_operator_scope_ports(),
            ports=ports,
            actor="operator-A",
            workflow_profile=gate.profile,
            workflow_engine=gate.engine,
            operation=operation,
            clock=clock,
        )


def test_filing_requires_exact_grant_and_reports_actual_noop(repos: Repos) -> None:
    """A wrong reviewed ID never publishes; a completed retry retains its witness."""
    work_units, calculations, filings, _reports, events = repos
    work_unit, draft, report_id = _verified_target(repos)

    with pytest.raises(VerificationReportNotFoundError):
        _file(repos, work_unit, draft, "f" * 64)
    retained_revision = calculations.load().get(draft.calculation_revision_id)
    assert retained_revision is not None
    assert retained_revision.state is CalculationRevisionState.VERIFICADO_COMPLETO
    assert all(
        record.calculation_revision_id != draft.calculation_revision_id for record in filings.load().records.values()
    )

    published = _file(repos, work_unit, draft, report_id)
    assert published.published is True
    assert published.record.calculation_revision_id == draft.calculation_revision_id
    first_events = events.load().for_bucket(work_unit.bucket_id, event_types=(BucketEventType.MODELO_FILED,))
    assert len(first_events) == 1

    with pytest.raises(VerificationReportNotFoundError):
        _file(repos, work_unit, draft, "f" * 64, clock=T4)
    repeated = _file(repos, work_unit, draft, report_id, clock=T4)
    assert repeated.published is False
    assert repeated.record == published.record
    assert len(events.load().for_bucket(work_unit.bucket_id, event_types=(BucketEventType.MODELO_FILED,))) == 1
    retained_unit = work_units.load().get(work_unit.work_unit_id)
    assert retained_unit is not None
    assert retained_unit.current_filing_record_id == published.record.filing_record_id


@pytest.mark.parametrize("changed_witness", ["second_grant", "retimed_grant"])
def test_filing_refuses_a_grant_without_unique_current_verification_witness(
    repos: Repos,
    changed_witness: str,
) -> None:
    """An old or ambiguous granting report cannot authorize a fresh filing."""
    _work_units, calculations, filings, reports, _events = repos
    work_unit, draft, report_id = _verified_target(repos)
    catalogue = reports.load()
    grant = catalogue.get(report_id)
    assert grant is not None
    if changed_witness == "second_grant":
        second = VerificationReport.model_validate(
            {
                **grant.model_dump(mode="python"),
                "verified_by": "operator-B",
                "verification_report_id": derive_verification_report_id(
                    calculation_revision_id=grant.calculation_revision_id,
                    completeness_status=grant.completeness_status,
                    findings=grant.findings,
                    verified_by="operator-B",
                ),
            },
            strict=True,
        )
        reports.save(upsert_verification_report(catalogue, second))
    else:
        retimed = VerificationReport.model_validate(
            {**grant.model_dump(mode="python"), "run_at": T3},
            strict=True,
        )
        reports.save(upsert_verification_report(catalogue, retimed))

    with pytest.raises(VerificationReportNotFoundError):
        _file(repos, work_unit, draft, report_id)
    retained_revision = calculations.load().get(draft.calculation_revision_id)
    assert retained_revision is not None
    assert retained_revision.state is CalculationRevisionState.VERIFICADO_COMPLETO
    assert all(
        record.calculation_revision_id != draft.calculation_revision_id for record in filings.load().records.values()
    )


@pytest.mark.parametrize("race", ["report", "calculation", "work_unit", "filing"])
def test_changed_catalogue_rolls_back_entire_filing_batch(repos: Repos, race: str) -> None:
    """An intervening encrypted catalogue write cannot publish any part of filing."""
    work_units, calculations, filings, _reports, events = repos
    work_unit, draft, report_id = _verified_target(repos)
    before_work_unit = work_units.load().get(work_unit.work_unit_id)

    with pytest.raises(SecureObjectRevisionConflictError):
        _file(repos, work_unit, draft, report_id, race=race)

    assert all(
        record.calculation_revision_id != draft.calculation_revision_id for record in filings.load().records.values()
    )
    retained_revision = calculations.load().get(draft.calculation_revision_id)
    assert retained_revision is not None
    assert retained_revision.state is CalculationRevisionState.VERIFICADO_COMPLETO
    assert work_units.load().get(work_unit.work_unit_id) == before_work_unit
    assert events.load().for_bucket(work_unit.bucket_id, event_types=(BucketEventType.MODELO_FILED,)) == ()


def test_filing_refuses_when_preflight_filing_snapshot_changes(repos: Repos) -> None:
    """A new filing lineage after the election preflight cannot be silently adopted."""
    work_units, calculations, filings, _reports, events = repos
    work_unit, draft, report_id = _verified_target(repos)
    before_work_unit = work_units.load().get(work_unit.work_unit_id)

    with pytest.raises(CalculationRevisionStateError) as raised:
        _file(repos, work_unit, draft, report_id, race="filing_preflight")
    assert raised.value.context is not None
    assert raised.value.context["reason"] == "filing_baseline_stale"
    retained_revision = calculations.load().get(draft.calculation_revision_id)
    assert retained_revision is not None
    assert retained_revision.state is CalculationRevisionState.VERIFICADO_COMPLETO
    assert all(
        record.calculation_revision_id != draft.calculation_revision_id for record in filings.load().records.values()
    )
    assert work_units.load().get(work_unit.work_unit_id) == before_work_unit
    assert events.load().for_bucket(work_unit.bucket_id, event_types=(BucketEventType.MODELO_FILED,)) == ()

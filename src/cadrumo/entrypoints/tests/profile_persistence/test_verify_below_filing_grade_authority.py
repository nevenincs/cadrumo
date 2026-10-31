"""Verifying a revision whose registry authority is below filing grade reports it instead of crashing.

Modelo 128 is published at calculation grade and, unlike an annual modelo such
as the 200, declares no cross-period dependencies, so the grade refusal is the
only finding the real verifier can legitimately produce for an empty draft.
"""

from __future__ import annotations

from collections.abc import Generator
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import UTC, date, datetime
from pathlib import Path

import pytest

from cadrumo.adapters.persistence.profile.buckets import BucketEventHistoryRepository
from cadrumo.adapters.persistence.profile.modelos_calculation import CalculationRevisionCatalogueRepository
from cadrumo.adapters.persistence.profile.modelos_verification_reports import VerificationReportCatalogueRepository
from cadrumo.adapters.persistence.profile.modelos_work_units import WorkUnitCatalogueRepository
from cadrumo.adapters.persistence.storage.operator_scope import build_operator_scope_ports
from cadrumo.adapters.persistence.storage.sql.secure_objects import SecureObjectRepository
from cadrumo.adapters.persistence.storage.tests.secure_sql import isolated_runtime_profile
from cadrumo.application.modelo.verification_actions import verify_modelo_revision_with_preconditions
from cadrumo.application.modelo.work_lifecycle import create_work_unit
from cadrumo.application.modelo.work_lifecycle_ports import WorkLifecyclePorts
from cadrumo.core.authority_grade import RegistryAuthorityGrade
from cadrumo.core.identity.hex_ids import CalculationRevisionId
from cadrumo.core.period import Period
from cadrumo.domain.calculations.registry.authority import PinnedAuthorityOperation
from cadrumo.domain.calculations.registry.errors import RegistryValidationError
from cadrumo.domain.deadlines.models import IVARegime, TaxpayerProfile
from cadrumo.domain.modelos.calculation_revision import CalculationRevisionState
from cadrumo.domain.modelos.verification_report import ModeloVerificationFindingSeverity
from cadrumo.domain.modelos.work_unit import WorkUnit
from cadrumo.entrypoints.tests.profile_persistence.verification_repository_support import (
    build_test_certificate_secret_backend_factory,
    build_test_verification_repository_bundle,
)

from ..modelo_gate_bucket_support import (
    calculate_without_inputs,
    seed_ready_capital_payer_profile,
)

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint]

_BUCKET_ID = "00000000-0000-4000-8000-000000000128"
_TAX_ID = "12345678Z"
_T0 = datetime(2026, 2, 1, 9, 0, tzinfo=UTC)
_MODELO = "128"
_FILING_YEAR = 2025
_PERIOD_CODE = "1T"


@dataclass(frozen=True, slots=True)
class _Bucket:
    objects: SecureObjectRepository
    work_unit: WorkUnit


@contextmanager
def _calculation_grade_bucket(tmp_path: Path, *, operation: PinnedAuthorityOperation) -> Generator[_Bucket]:
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=_BUCKET_ID, label="below filing grade") as profile:
        objects: SecureObjectRepository = profile.repository
        seed_ready_capital_payer_profile(bucket_id=_BUCKET_ID, at=_T0, tax_id=_TAX_ID)
        snapshot = operation.snapshot(
            _MODELO,
            filing_year=_FILING_YEAR,
            period=_PERIOD_CODE,
            grade=RegistryAuthorityGrade.CALCULATION,
        )
        work_unit = create_work_unit(
            bucket_id=_BUCKET_ID,
            modelo=_MODELO,
            filing_year=_FILING_YEAR,
            period=Period.from_year_and_code(_FILING_YEAR, _PERIOD_CODE),
            revision_id=snapshot.revision.id,
            ports=WorkLifecyclePorts(
                work_unit_repository=WorkUnitCatalogueRepository(objects=objects),
                bucket_event_repository=BucketEventHistoryRepository(objects=objects),
            ),
            clock=_T0,
            operation=operation,
        )
        yield _Bucket(objects=objects, work_unit=work_unit)


def _calculate(bucket: _Bucket) -> CalculationRevisionId:
    return calculate_without_inputs(
        bucket_id=_BUCKET_ID, objects=bucket.objects, work_unit_id=bucket.work_unit.work_unit_id
    )


def _workflow_profile() -> TaxpayerProfile:
    return TaxpayerProfile(
        tax_id=_TAX_ID,
        iva_regime=IVARegime("GENERAL"),
        activity_start_date=date(2020, 1, 1),
        has_employees=False,
        pays_rent_with_retencion=False,
        does_intracomunitario=False,
        bienes_extranjero_above_threshold=False,
    )


def test_the_revision_under_test_is_published_below_filing_grade(*, operation: PinnedAuthorityOperation) -> None:
    """The published authority resolves the revision for calculation and refuses it for filing."""
    calculation = operation.snapshot(
        _MODELO,
        filing_year=_FILING_YEAR,
        period=_PERIOD_CODE,
        grade=RegistryAuthorityGrade.CALCULATION,
    )
    assert calculation.revision.id == "2019-y-siguientes"

    with pytest.raises(RegistryValidationError):
        operation.snapshot(_MODELO, filing_year=_FILING_YEAR, period=_PERIOD_CODE)


def test_verifying_a_calculation_grade_revision_reports_the_grade_refusal_as_its_only_finding(
    tmp_path: Path, *, operation: PinnedAuthorityOperation
) -> None:
    """The grade refusal is the blocking finding; nothing downstream re-requests the refused snapshot."""
    with _calculation_grade_bucket(tmp_path, operation=operation) as bucket:
        revision_id = _calculate(bucket)

        report = verify_modelo_revision_with_preconditions(
            revision_id,
            certificate_secret_backend_factory=build_test_certificate_secret_backend_factory(),
            operator_scope_ports=build_operator_scope_ports(),
            actor="test",
            workflow_profile=_workflow_profile(),
            verification_repositories=build_test_verification_repository_bundle(),
            operation=operation,
        ).report

        revision = (
            CalculationRevisionCatalogueRepository(bucket_id=_BUCKET_ID, objects=bucket.objects).load().get(revision_id)
        )
        reports = VerificationReportCatalogueRepository(bucket_id=_BUCKET_ID, objects=bucket.objects).load().reports

    (finding,) = report.findings
    assert finding.message_locale_key == "application.modelo.findings.registry_authority_grade_insufficient"
    assert finding.severity is ModeloVerificationFindingSeverity.BLOCKING
    assert finding.message_facts["declared_grade"] == "calculation"
    assert finding.message_facts["requested_grade"] == "filing"
    assert report.granted_verificado_completo is False
    assert report.resolved_casilla_ids == ()
    assert set(reports) == {report.verification_report_id}
    assert revision is not None
    assert revision.state is CalculationRevisionState.BORRADOR
    assert revision.verified_at is None

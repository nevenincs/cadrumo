"""Real Modelo fixtures shared by registered-operation integration tests."""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path
from typing import Final
from uuid import UUID

from cadrumo.adapters.persistence.profile.buckets import BucketEventHistoryRepository
from cadrumo.adapters.persistence.profile.modelos_calculation import CalculationRevisionCatalogueRepository
from cadrumo.adapters.persistence.profile.modelos_filing import ModeloRecordCatalogueRepository
from cadrumo.adapters.persistence.profile.modelos_work_units import WorkUnitCatalogueRepository
from cadrumo.adapters.persistence.profile.tests.cross_period_seeding import (
    SEEDED_SOURCE_TAX_ID,
    seed_clean_cross_period_sources,
)
from cadrumo.adapters.persistence.profile.tests.taxpayer_persona_support import seed_modelo_ready_profile
from cadrumo.adapters.persistence.storage.operator_scope import build_operator_scope_ports
from cadrumo.application.live.justificante import JustificanteCaptureSnapshot
from cadrumo.application.modelo.calculation_bucket_actions import (
    calculate_modelo_revision_from_bucket_aggregation_with_diagnostics,
)
from cadrumo.application.modelo.operation_shared import resolve_active_workflow_profile
from cadrumo.application.modelo.verification_actions import verify_modelo_revision_with_preconditions
from cadrumo.application.modelo.work_lifecycle import create_work_unit
from cadrumo.core.hashing import sha256_hex
from cadrumo.core.period import Period
from cadrumo.domain.calculations.registry.authority import PinnedAuthorityOperation, bundled_indexed_authority
from cadrumo.domain.calculations.registry.tests.cross_period_seeding import resolved_revision
from cadrumo.domain.modelos.verification_report import VerificationCompletenessStatus
from cadrumo.domain.modelos.work_unit import WorkUnit
from cadrumo.entrypoints.adapter_composition_work_ports import (
    build_calculation_action_ports,
    build_verification_repository_bundle,
    build_work_lifecycle_ports,
)
from cadrumo.entrypoints.justificante_composition import build_justificante_capture_service
from cadrumo.entrypoints.tests.profile_persistence.verification_repository_support import (
    build_test_certificate_secret_backend_factory,
)

from ...domain.calculations.registry.tests.authored_editions import filing_year_envelope

_YEAR = filing_year_envelope().horizon


MODELO_OPERATION_TEST_ACTOR: Final = "operator:s45"
MODELO: Final = "130"
# The compare operation needs two consecutive supported exercises: the one filed here and the horizon one.
MODELO_FILING_YEAR: Final = _YEAR - 1
MODELO_PERIOD: Final = "1T"
_PROFILE_CLOCK = datetime(_YEAR, 8, 24, 18, tzinfo=UTC)

FIRST_QUARTER_PRIOR_PERIOD_BINDINGS: Final[dict[str, Decimal]] = {
    "irpf.previous_year_economic_activity_net_income": Decimal("0"),
    "modelo-130-resultados-negativos-anteriores": Decimal("0"),
    "modelo-130-pagos-fraccionados-anteriores": Decimal("0"),
}
"""Grounded zeros for the first-quarter M130 test work unit."""

_PREVIOUS_YEAR_INCOME_BINDING: Final = "irpf.previous_year_economic_activity_net_income"
_BINDINGS_BESIDE_SEEDED_PRIOR_YEAR: Final[dict[str, Decimal]] = {
    binding_id: value
    for binding_id, value in FIRST_QUARTER_PRIOR_PERIOD_BINDINGS.items()
    if binding_id != _PREVIOUS_YEAR_INCOME_BINDING
}
"""The prior-period zeros that leave the previous year's income to the prior-year return the seeding files.

A typed value that differs from that filed figure is a contested figure the note gate refuses, so a
calculation made after the seeding states only the bindings no seeded return supplies.
"""

_OPERATOR_SCOPE_PORTS = build_operator_scope_ports()


def _seed_modelo_ready_profile(profile_id: UUID) -> None:
    """Seed the taxpayer facts required by Modelo work through the canonical helper."""
    seed_modelo_ready_profile(bucket_id=str(profile_id), at=_PROFILE_CLOCK, tax_id=SEEDED_SOURCE_TAX_ID)


def seeded_modelo_work_unit(profile_id: UUID, *, operation: PinnedAuthorityOperation) -> WorkUnit:
    """Create a real Modelo work unit through the production lifecycle door."""
    _seed_modelo_ready_profile(profile_id)
    revision = resolved_revision(modelo=MODELO, filing_year=MODELO_FILING_YEAR, period=MODELO_PERIOD)
    return create_work_unit(
        bucket_id=str(profile_id),
        modelo=MODELO,
        filing_year=MODELO_FILING_YEAR,
        period=Period.from_year_and_code(MODELO_FILING_YEAR, MODELO_PERIOD),
        revision_id=revision.id,
        actor=MODELO_OPERATION_TEST_ACTOR,
        ports=build_work_lifecycle_ports(bucket_id=str(profile_id)),
        operation=operation,
    )


def seeded_modelo_calculation_revision(profile_id: UUID, *, operation: PinnedAuthorityOperation) -> str:
    """Calculate one real revision for the seeded unit, and return its id."""
    unit = seeded_modelo_work_unit(profile_id, operation=operation)
    with bundled_indexed_authority().operation() as calculation_operation:
        revision = calculate_modelo_revision_from_bucket_aggregation_with_diagnostics(
            unit.work_unit_id,
            ports=build_calculation_action_ports(bucket_id=unit.bucket_id, operation=calculation_operation),
            actor=MODELO_OPERATION_TEST_ACTOR,
            casilla_inputs={},
            binding_values=FIRST_QUARTER_PRIOR_PERIOD_BINDINGS,
        ).revision
    return str(revision.calculation_revision_id)


def seeded_modelo_verification_report(profile_id: UUID, *, operation: PinnedAuthorityOperation) -> tuple[str, str]:
    """Calculate a revision and verify it, returning both ids."""
    unit = seeded_modelo_work_unit(profile_id, operation=operation)
    seed_clean_cross_period_sources(
        unit,
        work_unit_repository=WorkUnitCatalogueRepository(),
        calculation_repository=CalculationRevisionCatalogueRepository(),
        filing_repository=ModeloRecordCatalogueRepository(),
        bucket_event_repository=BucketEventHistoryRepository(),
        operation=operation,
    )
    with bundled_indexed_authority().operation() as verification_operation:
        revision = calculate_modelo_revision_from_bucket_aggregation_with_diagnostics(
            unit.work_unit_id,
            ports=build_calculation_action_ports(bucket_id=unit.bucket_id, operation=verification_operation),
            actor=MODELO_OPERATION_TEST_ACTOR,
            casilla_inputs={},
            binding_values=_BINDINGS_BESIDE_SEEDED_PRIOR_YEAR,
        ).revision
        revision_id = str(revision.calculation_revision_id)
        report = verify_modelo_revision_with_preconditions(
            revision_id,
            certificate_secret_backend_factory=build_test_certificate_secret_backend_factory(),
            verification_repositories=build_verification_repository_bundle(
                unit.bucket_id, operation=verification_operation
            ),
            actor=MODELO_OPERATION_TEST_ACTOR,
            workflow_profile=resolve_active_workflow_profile(verification_operation),
            operator_scope_ports=_OPERATOR_SCOPE_PORTS,
            operation=verification_operation,
        ).report
    if report.completeness_status is not VerificationCompletenessStatus.COMPLETE:
        findings = (
            "; ".join(
                sorted(
                    f"{finding.kind.value}/{finding.severity.value} {dict(finding.message_facts)}"
                    for finding in report.findings
                )
            )
            or "no findings reported"
        )
        raise AssertionError(
            f"verification did not grant completeness on the seeded revision "
            f"(status={report.completeness_status.value}); filing cannot be exercised until it does: {findings}"
        )
    return revision_id, str(report.verification_report_id)


def captured_justificante_snapshot(profile_id: UUID, unit: WorkUnit) -> JustificanteCaptureSnapshot:
    """Capture the synthetic receipt for ``unit`` through the production service and return its active snapshot."""
    pdf = (
        Path(__file__).resolve().parents[2] / "tests" / "fixtures" / "justificantes" / "130" / "2024-1T.pdf"
    ).read_bytes()
    return build_justificante_capture_service(str(profile_id)).capture(
        modelo=str(unit.modelo),
        filing_year=unit.filing_year,
        period=unit.period,
        expediente_id="202413000000001Z",
        csv="ABCD1234EFGH",
        pdf_bytes=pdf,
        pdf_sha256=sha256_hex(pdf),
        captured_at=datetime(_YEAR, 9, 29, tzinfo=UTC),
    )

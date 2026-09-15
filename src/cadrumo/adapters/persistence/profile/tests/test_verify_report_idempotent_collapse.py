"""Verify-report idempotent-collapse application tests.

The content-pinned verification report id keys on the verification *outcome*
(calculation revision, completeness status, findings, actor) rather than the
wall-clock ``run_at``. This makes a non-granting ``modelo verify`` retry-safe
for the autonomous-agent operator: re-running an identical verify collapses
onto one persisted report instead of accumulating a fresh time-stamped report
per attempt, while a genuinely distinct outcome (here a different actor) still
produces a distinct report. Exercises the real ``verify_modelo_revision`` path
against the real registry and the encrypted report catalogue - no mocks.
"""

from __future__ import annotations

from dataclasses import replace
from decimal import Decimal

import pytest

from cadrumo.adapters.persistence.profile.tests._file_flow_support import (
    DEFAULT_180_BINDING_VALUES,
    DEFAULT_180_RELATION_VALUES,
    T1,
    T2,
    T3,
    Repos,
    calculation_ports_for_test,
    registry_required_manual_casillas,
    seed_modelo_180_work_unit,
    workflow_profile,
)
from cadrumo.adapters.persistence.profile.tests.cross_period_seeding import seed_clean_cross_period_sources
from cadrumo.adapters.persistence.profile.tests.verification_repository_support import (
    build_test_certificate_secret_backend_factory,
    build_test_verification_repository_bundle,
)
from cadrumo.adapters.persistence.storage.operator_scope import build_operator_scope_ports
from cadrumo.application.modelo.calculation_actions import calculate_modelo_revision
from cadrumo.application.modelo.filing_actions import list_verification_reports
from cadrumo.application.modelo.verification_actions import verify_modelo_revision
from cadrumo.domain.calculations.registry.authority import PinnedAuthorityOperation
from cadrumo.domain.calculations.registry.authority import bundled_indexed_authority as _indexed_authority_for_test
from cadrumo.domain.modelos.verification_report import VerificationCompletenessStatus
from cadrumo.entrypoints.adapter_composition import build_filing_action_ports

_OPERATOR_SCOPE_PORTS = build_operator_scope_ports()

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]


def _verification_repositories_for_test(repos: Repos):
    wu_repo, cr_repo, fr_repo, vr_repo, bv_repo = repos
    return replace(
        build_test_verification_repository_bundle(),
        calculation=cr_repo,
        work_unit=wu_repo,
        filing=fr_repo,
        verification=vr_repo,
        bucket_event=bv_repo,
    )


def _filing_ports_for_test(repos: Repos):
    wu_repo, cr_repo, fr_repo, vr_repo, bv_repo = repos
    bucket_id = wu_repo.bucket_id
    assert bucket_id is not None
    return replace(
        build_filing_action_ports(bucket_id=bucket_id),
        work_unit_repository=wu_repo,
        calculation_repository=cr_repo,
        filing_repository=fr_repo,
        verification_repository=vr_repo,
        bucket_event_repository=bv_repo,
    )


def _seed_nongranting_revision(repos: Repos, *, operation: PinnedAuthorityOperation):
    """Seed an M180 draft that omits one required casilla, so verify refuses.

    Returns ``(revision, repos-tuple)``. A non-granting verify leaves the
    revision in ``BORRADOR``, so it can be re-verified - the precondition the
    collapse contract needs.
    """
    wu_repo, cr_repo, fr_repo, _vr_repo, bv_repo = repos
    required = registry_required_manual_casillas()
    assert len(required) >= 2
    # Omit required[0]; supply the rest. The verifier emits a blocking
    # MISSING_REQUIRED_CASILLA finding and does not grant.
    supplied = {cid: Decimal("1") for cid in required[1:]}
    work_unit = seed_modelo_180_work_unit(wu_repo)
    with calculation_ports_for_test(
        bucket_id=work_unit.bucket_id,
        work_unit_repository=wu_repo,
        calculation_repository=cr_repo,
        bucket_event_repository=bv_repo,
    ) as _calculation_ports_95:
        revision = calculate_modelo_revision(
            work_unit.work_unit_id,
            casilla_inputs=supplied,
            binding_values=DEFAULT_180_BINDING_VALUES,
            relation_values=DEFAULT_180_RELATION_VALUES,
            ports=_calculation_ports_95,
            clock=T1,
        )
    seed_clean_cross_period_sources(
        work_unit,
        work_unit_repository=wu_repo,
        calculation_repository=cr_repo,
        filing_repository=fr_repo,
        bucket_event_repository=bv_repo,
        operation=operation,
    )
    return revision


def test_identical_nongranting_verify_retry_collapses_to_one_report(
    repos: Repos, *, operation: PinnedAuthorityOperation
) -> None:
    """Two identical-outcome non-granting verifies at different clocks → one report."""
    with _indexed_authority_for_test().operation() as _authority_operation_for_test:
        wu_repo, cr_repo, _, vr_repo, bv_repo = repos
        revision = _seed_nongranting_revision(repos, operation=operation)

        first = verify_modelo_revision(
            revision.calculation_revision_id,
            actor="operator-A",
            workflow_profile=workflow_profile(),
            certificate_secret_backend_factory=build_test_certificate_secret_backend_factory(),
            verification_repositories=_verification_repositories_for_test(repos),
            clock=T2,
            operator_scope_ports=_OPERATOR_SCOPE_PORTS,
            operation=_authority_operation_for_test,
        )
        second = verify_modelo_revision(
            revision.calculation_revision_id,
            actor="operator-A",
            workflow_profile=workflow_profile(),
            certificate_secret_backend_factory=build_test_certificate_secret_backend_factory(),
            verification_repositories=_verification_repositories_for_test(repos),
            clock=T3,
            operator_scope_ports=_OPERATOR_SCOPE_PORTS,
            operation=_authority_operation_for_test,
        )

        # Both refused, identical outcome.
        assert first.granted_verificado_completo is False
        assert second.granted_verificado_completo is False
        assert first.completeness_status is second.completeness_status
        assert first.findings == second.findings
        # The wall clock differs but the identity does not (run_at is excluded).
        assert first.run_at == T2
        assert second.run_at == T3
        assert second.verification_report_id == first.verification_report_id

        # The catalogue collapsed: exactly ONE report for this revision, carrying
        # the last-seen run_at (T3 from the upsert), not two accumulated rows.
        stored = list_verification_reports(
            calculation_revision_id=revision.calculation_revision_id,
            ports=_filing_ports_for_test(repos),
            operation=_authority_operation_for_test,
        )
        assert len(stored) == 1
        assert stored[0].verification_report_id == first.verification_report_id
        assert stored[0].run_at == T3
        assert stored[0].completeness_status is VerificationCompletenessStatus.INCOMPLETE


def test_distinct_outcome_verify_produces_a_distinct_report(
    repos: Repos, *, operation: PinnedAuthorityOperation
) -> None:
    """A verify whose outcome differs (different actor) → a distinct report, not a collapse."""
    with _indexed_authority_for_test().operation() as _authority_operation_for_test:
        wu_repo, cr_repo, _, vr_repo, bv_repo = repos
        revision = _seed_nongranting_revision(repos, operation=operation)

        by_a = verify_modelo_revision(
            revision.calculation_revision_id,
            actor="operator-A",
            workflow_profile=workflow_profile(),
            certificate_secret_backend_factory=build_test_certificate_secret_backend_factory(),
            verification_repositories=_verification_repositories_for_test(repos),
            clock=T2,
            operator_scope_ports=_OPERATOR_SCOPE_PORTS,
            operation=_authority_operation_for_test,
        )
        by_b = verify_modelo_revision(
            revision.calculation_revision_id,
            actor="operator-B",
            workflow_profile=workflow_profile(),
            certificate_secret_backend_factory=build_test_certificate_secret_backend_factory(),
            verification_repositories=_verification_repositories_for_test(repos),
            clock=T3,
            operator_scope_ports=_OPERATOR_SCOPE_PORTS,
            operation=_authority_operation_for_test,
        )

        # verified_by is part of the outcome identity, so the two reports do NOT
        # collapse: distinct ids, both retained.
        assert by_b.verification_report_id != by_a.verification_report_id
        stored = list_verification_reports(
            calculation_revision_id=revision.calculation_revision_id,
            ports=_filing_ports_for_test(repos),
            operation=_authority_operation_for_test,
        )
        assert len(stored) == 2
        assert {r.verification_report_id for r in stored} == {
            by_a.verification_report_id,
            by_b.verification_report_id,
        }

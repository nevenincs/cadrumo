"""Idempotent re-file application tests.

A re-file of a revision already in PRESENTADO state is a guarded-idempotent
no-op: ``file_modelo_revision`` returns the existing VIGENTE filing record
without minting a duplicate record, re-stamping ``filed_at``, or emitting a
second ``MODELO_FILED`` event, and a not-yet-verified revision still hard-refuses
with ``CalculationRevisionStateError``. Real repositories, real registry, no
mocks. The no-op short-circuits before the workflow gate, so the re-file needs no
auth provider.
"""

from __future__ import annotations

from decimal import Decimal

import pytest

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
    file_revision,
    seed_work_unit,
    verify_revision,
    workflow_profile,
)
from cadrumo.entrypoints.tests.profile_persistence.verification_repository_support import (
    build_test_certificate_secret_backend_factory,
)
from cadrumo.adapters.persistence.storage.operator_scope import build_operator_scope_ports
from cadrumo.application.modelo.action_errors import CalculationRevisionStateError
from cadrumo.application.modelo.calculation_actions import calculate_modelo_revision, get_calculation_revision
from cadrumo.application.modelo.filing_actions import file_modelo_revision
from cadrumo.domain.buckets.event import BucketEventType
from cadrumo.domain.calculations.registry.authority import bundled_indexed_authority
from cadrumo.domain.modelos.calculation_revision import CalculationRevisionState
from cadrumo.domain.modelos.filing_record import ModeloRecordStatus
from cadrumo.entrypoints.adapter_composition import build_filing_action_ports

_OPERATOR_SCOPE_PORTS = build_operator_scope_ports()

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint]


def _verified_revision(repos: Repos):
    """Seed a work unit, calculate, and verify so the revision is filing-eligible."""
    wu_repo, cr_repo, fr_repo, vr_repo, bv_repo = repos
    work_unit = seed_work_unit(wu_repo)
    with calculation_ports_for_test(
        bucket_id=work_unit.bucket_id,
        work_unit_repository=wu_repo,
        calculation_repository=cr_repo,
        bucket_event_repository=bv_repo,
    ) as _calculation_ports_59:
        revision = calculate_modelo_revision(
            work_unit.work_unit_id,
            casilla_inputs={**DEFAULT_130_BASELINE_INPUTS, M130_INCOME_CASILLA: Decimal("1000")},
            binding_values=DEFAULT_130_BINDING_VALUES,
            ports=_calculation_ports_59,
            clock=T1,
        )
    verify_revision(
        revision.calculation_revision_id,
        revision=revision,
        work_unit=work_unit,
        actor="operator-A",
        work_unit_repository=wu_repo,
        calculation_repository=cr_repo,
        verification_repository=vr_repo,
        filing_repository=fr_repo,
        bucket_event_repository=bv_repo,
        clock=T2,
    )
    return work_unit, revision


def test_refile_of_presentado_revision_is_idempotent_noop(repos: Repos) -> None:
    """A second file of an already-filed revision returns the existing record unchanged."""
    wu_repo, cr_repo, fr_repo, _, bv_repo = repos
    work_unit, revision = _verified_revision(repos)

    first = file_revision(
        revision.calculation_revision_id,
        revision=revision,
        work_unit=work_unit,
        actor="operator-A",
        notes="Q1 IVA",
        work_unit_repository=wu_repo,
        calculation_repository=cr_repo,
        filing_repository=fr_repo,
        bucket_event_repository=bv_repo,
        clock=T3,
    )
    records_after_first = dict(fr_repo.load().records)
    filed_after_first = bv_repo.load().for_bucket(
        work_unit.bucket_id,
        event_types=(BucketEventType.MODELO_FILED,),
    )
    assert len(filed_after_first) == 1

    # Re-file the same revision at a LATER clock. The revision is PRESENTADO, so
    # file_modelo_revision short-circuits to the existing record (no workflow gate,
    # no auth provider needed).
    with bundled_indexed_authority().operation() as operation:
        second = file_modelo_revision(
            revision.calculation_revision_id,
            actor="operator-A",
            workflow_profile=workflow_profile(),
            certificate_secret_backend_factory=build_test_certificate_secret_backend_factory(),
            ports=build_filing_action_ports(bucket_id=work_unit.bucket_id),
            clock=T4,
            operator_scope_ports=_OPERATOR_SCOPE_PORTS,
            operation=operation,
        )

    # Same record returned, unchanged - no re-stamp of filed_at to T4.
    assert second.filing_record_id == first.filing_record_id
    assert second.status is ModeloRecordStatus.VIGENTE
    assert second.filed_at == T3
    assert second.filed_at != T4

    # No duplicate filing record and no second MODELO_FILED event.
    assert dict(fr_repo.load().records) == records_after_first
    filed_after_second = bv_repo.load().for_bucket(
        work_unit.bucket_id,
        event_types=(BucketEventType.MODELO_FILED,),
    )
    assert len(filed_after_second) == 1
    with calculation_ports_for_test(
        bucket_id=work_unit.bucket_id,
        calculation_repository=cr_repo,
    ) as _calculation_ports_133:
        # The revision stays PRESENTADO.
        refreshed = get_calculation_revision(
            revision.calculation_revision_id,
            ports=_calculation_ports_133,
        )
    assert refreshed.state is CalculationRevisionState.PRESENTADO


def test_file_of_unverified_revision_still_hard_refuses(repos: Repos) -> None:
    """A BORRADOR (not VERIFICADO_COMPLETO) revision still raises - the no-op is scoped to PRESENTADO."""
    wu_repo, cr_repo, _fr_repo, _, bv_repo = repos
    work_unit = seed_work_unit(wu_repo)
    with calculation_ports_for_test(
        bucket_id=work_unit.bucket_id,
        work_unit_repository=wu_repo,
        calculation_repository=cr_repo,
        bucket_event_repository=bv_repo,
    ) as _calculation_ports_146:
        revision = calculate_modelo_revision(
            work_unit.work_unit_id,
            casilla_inputs={M130_INCOME_CASILLA: Decimal("1000")},
            binding_values=DEFAULT_130_BINDING_VALUES,
            ports=_calculation_ports_146,
            clock=T1,
        )
    with (
        pytest.raises(CalculationRevisionStateError, match=r"state|VERIFICADO_COMPLETO"),
        bundled_indexed_authority().operation() as operation,
    ):
        file_modelo_revision(
            revision.calculation_revision_id,
            actor="operator-A",
            workflow_profile=workflow_profile(),
            certificate_secret_backend_factory=build_test_certificate_secret_backend_factory(),
            ports=build_filing_action_ports(bucket_id=work_unit.bucket_id),
            clock=T2,
            operator_scope_ports=_OPERATOR_SCOPE_PORTS,
            operation=operation,
        )

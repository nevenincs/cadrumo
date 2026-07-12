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

import pytest

from ._file_flow_support import (
    DEFAULT_130_BASELINE_INPUTS,
    DEFAULT_130_BINDING_VALUES,
    M130_INCOME_CASILLA,
    T1,
    T2,
    T3,
    T4,
    BucketEventType,
    CalculationRevisionState,
    CalculationRevisionStateError,
    Decimal,
    ModeloRecordStatus,
    Repos,
    calculate_modelo_revision,
    file_modelo_revision,
    file_revision,
    get_calculation_revision,
    seed_work_unit,
    verify_revision,
    workflow_profile,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]


def _verified_revision(repos: Repos):
    """Seed a work unit, calculate, and verify so the revision is filing-eligible."""
    wu_repo, cr_repo, fr_repo, vr_repo, bv_repo = repos
    work_unit = seed_work_unit(wu_repo)
    revision = calculate_modelo_revision(
        work_unit.work_unit_id,
        casilla_inputs={**DEFAULT_130_BASELINE_INPUTS, M130_INCOME_CASILLA: Decimal("1000")},
        binding_values=DEFAULT_130_BINDING_VALUES,
        work_unit_repository=wu_repo,
        calculation_repository=cr_repo,
        bucket_event_repository=bv_repo,
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
    second = file_modelo_revision(
        revision.calculation_revision_id,
        actor="operator-A",
        workflow_profile=workflow_profile(),
        work_unit_repository=wu_repo,
        calculation_repository=cr_repo,
        filing_repository=fr_repo,
        bucket_event_repository=bv_repo,
        clock=T4,
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

    # The revision stays PRESENTADO.
    refreshed = get_calculation_revision(
        revision.calculation_revision_id,
        calculation_repository=cr_repo,
    )
    assert refreshed.state is CalculationRevisionState.PRESENTADO


def test_file_of_unverified_revision_still_hard_refuses(repos: Repos) -> None:
    """A BORRADOR (not VERIFICADO_COMPLETO) revision still raises - the no-op is scoped to PRESENTADO."""
    wu_repo, cr_repo, fr_repo, _, bv_repo = repos
    work_unit = seed_work_unit(wu_repo)
    revision = calculate_modelo_revision(
        work_unit.work_unit_id,
        casilla_inputs={M130_INCOME_CASILLA: Decimal("1000")},
        binding_values=DEFAULT_130_BINDING_VALUES,
        work_unit_repository=wu_repo,
        calculation_repository=cr_repo,
        bucket_event_repository=bv_repo,
        clock=T1,
    )
    with pytest.raises(CalculationRevisionStateError, match=r"state|VERIFICADO_COMPLETO"):
        file_modelo_revision(
            revision.calculation_revision_id,
            actor="operator-A",
            workflow_profile=workflow_profile(),
            work_unit_repository=wu_repo,
            calculation_repository=cr_repo,
            filing_repository=fr_repo,
            bucket_event_repository=bv_repo,
            clock=T2,
        )

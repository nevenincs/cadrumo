"""The approved filing draft a verify run produces is durably stored.

Approval used to happen entirely in memory: the workflow gate built the draft,
approved it, handed it to preflight and dropped it. Nothing else in the
application wrote the encrypted filing-draft namespace, so every reader of that
store -- the review queue's draft rows, the workspace summary's draft count,
the CLI's draft lookup -- read an empty store and reported zero permanently.
An operator reads that as having no drafts, not as the application declining to
keep them, which is the absent-versus-zero collapse the filing surfaces exist
to keep distinguishable.

The control matters as much as the assertion: the store must be empty before
the run, or a passing test proves only that something, sometime, wrote a draft.
"""

from __future__ import annotations

import pytest

from ....adapters.persistence.profile.filing_drafts import ModeloDraftRepository
from ....domain.submission.models import ModeloDraftStatus
from ._file_flow_support import (
    DEFAULT_130_BASELINE_INPUTS,
    DEFAULT_130_BINDING_VALUES,
    T1,
    T2,
    Repos,
    calculate_modelo_revision,
    seed_work_unit,
    verify_revision,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]


def test_a_verified_revision_leaves_its_approved_draft_in_the_store(repos: Repos) -> None:
    wu_repo, cr_repo, _, vr_repo, bv_repo = repos
    work_unit = seed_work_unit(wu_repo, filing_year=2024)
    drafts = ModeloDraftRepository(bucket_id=work_unit.bucket_id)

    assert tuple(drafts.iter_drafts()) == ()

    revision = calculate_modelo_revision(
        work_unit.work_unit_id,
        casilla_inputs=DEFAULT_130_BASELINE_INPUTS,
        binding_values=DEFAULT_130_BINDING_VALUES,
        work_unit_repository=wu_repo,
        calculation_repository=cr_repo,
        bucket_event_repository=bv_repo,
        clock=T1,
    )
    report = verify_revision(
        revision.calculation_revision_id,
        revision=revision,
        work_unit=work_unit,
        work_unit_repository=wu_repo,
        calculation_repository=cr_repo,
        verification_repository=vr_repo,
        bucket_event_repository=bv_repo,
        clock=T2,
    )
    assert report.granted_verificado_completo is True

    stored = tuple(drafts.iter_drafts())
    assert len(stored) == 1
    assert stored[0].status is ModeloDraftStatus.APROBADO
    assert stored[0].modelo == work_unit.modelo
    # the approval basis is what stale detection later compares against, so a
    # draft stored without one is stored in a state that can never go stale
    assert stored[0].approval_basis is not None


def test_re_verifying_the_same_revision_rewrites_one_row(repos: Repos) -> None:
    """``draft_id`` is a content address, so an unchanged draft is idempotent."""
    wu_repo, cr_repo, _, vr_repo, bv_repo = repos
    work_unit = seed_work_unit(wu_repo, filing_year=2024)
    drafts = ModeloDraftRepository(bucket_id=work_unit.bucket_id)

    revision = calculate_modelo_revision(
        work_unit.work_unit_id,
        casilla_inputs=DEFAULT_130_BASELINE_INPUTS,
        binding_values=DEFAULT_130_BINDING_VALUES,
        work_unit_repository=wu_repo,
        calculation_repository=cr_repo,
        bucket_event_repository=bv_repo,
        clock=T1,
    )
    for clock in (T1, T2):
        verify_revision(
            revision.calculation_revision_id,
            revision=revision,
            work_unit=work_unit,
            work_unit_repository=wu_repo,
            calculation_repository=cr_repo,
            verification_repository=vr_repo,
            bucket_event_repository=bv_repo,
            clock=clock,
        )

    stored = tuple(drafts.iter_drafts())
    assert len(stored) == 1

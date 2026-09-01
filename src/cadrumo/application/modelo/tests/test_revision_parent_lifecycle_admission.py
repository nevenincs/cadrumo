"""Direct application proof that verify/file refuse revisions of discarded work."""

from __future__ import annotations

import pytest

from ....core.operator_action_enums import NoRecoveryOutcome
from ....domain.modelos.calculation_revision import CalculationRevisionState
from ..action_errors import CalculationRevisionNotFoundError
from ..filing_actions import file_modelo_revision
from ..verification_actions import verify_modelo_revision_with_preconditions
from ..work_lifecycle import discard_work_unit
from ._file_flow_support import (
    DEFAULT_130_BASELINE_INPUTS,
    DEFAULT_130_BINDING_VALUES,
    T1,
    T2,
    T3,
    T4,
    Repos,
    calculate_modelo_revision,
    seed_work_unit,
    verify_revision,
    workflow_profile,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]


def _calculated_target(repos: Repos):
    work_unit_repository, calculation_repository, _, _, bucket_event_repository = repos
    work_unit = seed_work_unit(work_unit_repository)
    revision = calculate_modelo_revision(
        work_unit.work_unit_id,
        actor="operator-A",
        casilla_inputs=DEFAULT_130_BASELINE_INPUTS,
        binding_values=DEFAULT_130_BINDING_VALUES,
        work_unit_repository=work_unit_repository,
        calculation_repository=calculation_repository,
        bucket_event_repository=bucket_event_repository,
        clock=T1,
    )
    return work_unit, revision


def _verified_target(repos: Repos):
    """Create a real granting report with the shared clean-source fixture."""
    work_unit, revision = _calculated_target(repos)
    (
        work_unit_repository,
        calculation_repository,
        filing_repository,
        verification_repository,
        bucket_event_repository,
    ) = repos
    report = verify_revision(
        revision.calculation_revision_id,
        revision=revision,
        work_unit=work_unit,
        actor="operator-A",
        work_unit_repository=work_unit_repository,
        calculation_repository=calculation_repository,
        filing_repository=filing_repository,
        verification_repository=verification_repository,
        bucket_event_repository=bucket_event_repository,
        clock=T2,
    )
    assert report.granted_verificado_completo is True
    stored = calculation_repository.load().get(revision.calculation_revision_id)
    assert stored is not None
    assert stored.state is CalculationRevisionState.VERIFICADO_COMPLETO
    return work_unit, revision


def _discard_target(*, work_unit, repos: Repos) -> None:
    work_unit_repository, _, _, _, bucket_event_repository = repos
    discard_work_unit(
        work_unit.work_unit_id,
        actor="operator-A",
        repository=work_unit_repository,
        bucket_event_repository=bucket_event_repository,
        clock=T3,
    )


def _catalogue_snapshot(repos: Repos) -> tuple[object, object, object, object, object]:
    (
        work_unit_repository,
        calculation_repository,
        filing_repository,
        verification_repository,
        bucket_event_repository,
    ) = repos
    return (
        work_unit_repository.load(),
        calculation_repository.load(),
        filing_repository.load(),
        verification_repository.load(),
        bucket_event_repository.load(),
    )


def _assert_terminal_parent_refusal(
    raised: pytest.ExceptionInfo[CalculationRevisionNotFoundError],
    *,
    verb: str,
    calculation_revision_id: str,
    work_unit_id: str,
) -> None:
    error = raised.value
    assert error.translated_message == "application.modelo.errors.calculation_revision_parent_work_unit_discarded"
    assert error.context is not None
    assert error.context["calculation_revision_id"] == calculation_revision_id
    assert error.context["work_unit_id"] == work_unit_id
    assert error.context["work_unit_state"] == "descartado"
    failure = error.precondition_failure
    assert failure is not None
    assert failure.identity == (
        f"modelo.work.{verb}",
        f"modelo.work.{verb}.calculation_revision.addresses_calculation",
        f"modelo.work.{verb}.calculation_revision.work_unit_target_discarded",
    )
    assert failure.verdict.action is None
    assert failure.verdict.no_recovery_outcome is NoRecoveryOutcome.TERMINAL


def test_direct_verify_rejects_discarded_draft_without_creating_a_report_or_event(repos: Repos) -> None:
    """The application service refuses before draft verification can persist anything."""
    work_unit, revision = _calculated_target(repos)
    _discard_target(work_unit=work_unit, repos=repos)
    before = _catalogue_snapshot(repos)
    (
        work_unit_repository,
        calculation_repository,
        filing_repository,
        verification_repository,
        bucket_event_repository,
    ) = repos

    with pytest.raises(CalculationRevisionNotFoundError) as raised:
        verify_modelo_revision_with_preconditions(
            revision.calculation_revision_id,
            actor="operator-A",
            workflow_profile=workflow_profile(),
            work_unit_repository=work_unit_repository,
            calculation_repository=calculation_repository,
            filing_repository=filing_repository,
            verification_repository=verification_repository,
            bucket_event_repository=bucket_event_repository,
            clock=T4,
        )

    _assert_terminal_parent_refusal(
        raised,
        verb="verify",
        calculation_revision_id=revision.calculation_revision_id,
        work_unit_id=work_unit.work_unit_id,
    )
    assert _catalogue_snapshot(repos) == before


def test_direct_verify_rejects_discarded_verified_revision_before_idempotent_return(repos: Repos) -> None:
    """A discarded parent beats the verified-revision no-op and leaves its report untouched."""
    work_unit, revision = _verified_target(repos)
    (
        work_unit_repository,
        calculation_repository,
        filing_repository,
        verification_repository,
        bucket_event_repository,
    ) = repos
    _discard_target(work_unit=work_unit, repos=repos)
    before = _catalogue_snapshot(repos)

    with pytest.raises(CalculationRevisionNotFoundError) as raised:
        verify_modelo_revision_with_preconditions(
            revision.calculation_revision_id,
            actor="operator-A",
            workflow_profile=workflow_profile(),
            work_unit_repository=work_unit_repository,
            calculation_repository=calculation_repository,
            filing_repository=filing_repository,
            verification_repository=verification_repository,
            bucket_event_repository=bucket_event_repository,
            clock=T4,
        )

    _assert_terminal_parent_refusal(
        raised,
        verb="verify",
        calculation_revision_id=revision.calculation_revision_id,
        work_unit_id=work_unit.work_unit_id,
    )
    assert _catalogue_snapshot(repos) == before


def test_direct_file_rejects_discarded_verified_revision_without_a_filing(repos: Repos) -> None:
    """The file service reads the same lifecycle authority before creating a record."""
    work_unit, revision = _verified_target(repos)
    (
        work_unit_repository,
        calculation_repository,
        filing_repository,
        verification_repository,
        bucket_event_repository,
    ) = repos
    _discard_target(work_unit=work_unit, repos=repos)
    before = _catalogue_snapshot(repos)

    with pytest.raises(CalculationRevisionNotFoundError) as raised:
        file_modelo_revision(
            revision.calculation_revision_id,
            actor="operator-A",
            workflow_profile=workflow_profile(),
            work_unit_repository=work_unit_repository,
            calculation_repository=calculation_repository,
            filing_repository=filing_repository,
            verification_repository=verification_repository,
            bucket_event_repository=bucket_event_repository,
            clock=T4,
        )

    _assert_terminal_parent_refusal(
        raised,
        verb="file",
        calculation_revision_id=revision.calculation_revision_id,
        work_unit_id=work_unit.work_unit_id,
    )
    assert _catalogue_snapshot(repos) == before

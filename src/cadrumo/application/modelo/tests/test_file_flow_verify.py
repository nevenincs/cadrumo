"""Modelo file-flow application tests split by workflow."""

from __future__ import annotations

import pytest

from ....core.casilla_id import CasillaId
from ....tests.cross_period_seeding import seed_clean_cross_period_sources
from ...workflow.run_models import WorkflowDeadlineContextDetails
from ._file_flow_support import (
    DEFAULT_130_BASELINE_INPUTS,
    DEFAULT_130_BINDING_VALUES,
    DEFAULT_180_BINDING_VALUES,
    DEFAULT_180_RELATION_VALUES,
    M111_ACTIVITY_AMOUNT_CASILLA,
    M111_ACTIVITY_COUNT_CASILLA,
    M111_ACTIVITY_WITHHELD_CASILLA,
    M111_EMPLOYMENT_WITHHELD_CASILLA,
    M111_FORESTRY_WITHHELD_CASILLA,
    M111_IMAGE_RIGHTS_WITHHELD_CASILLA,
    M111_IMPUTED_INCOME_WITHHELD_CASILLA,
    M111_PRIZE_WITHHELD_CASILLA,
    M111_PROFESSIONAL_WITHHELD_CASILLA,
    M111_TOTAL_WITHHELD_CASILLA,
    M130_CARRY_FORWARD_CASILLA,
    M130_INCOME_CASILLA,
    M180_PERCEPTOR_BASE_CASILLA,
    T1,
    T2,
    T3,
    VERIFY_MODELO,
    VERIFY_PERIOD,
    VERIFY_REVISION,
    BucketEventType,
    CalculationRevisionNotFoundError,
    CalculationRevisionState,
    CalculationRevisionStateError,
    Decimal,
    ModeloVerificationFindingKind,
    ModeloVerificationFindingSeverity,
    Repos,
    VerificationCompletenessStatus,
    VerificationReportNotFoundError,
    WorkflowPurpose,
    WorkflowStage,
    asyncio,
    calculate_modelo_revision,
    canonical_work_unit_period,
    get_calculation_revision,
    get_verification_report,
    get_work_unit,
    list_verification_reports,
    mark_revision_verificado_completo,
    registry_required_manual_casillas,
    registry_required_manual_casillas_for,
    seed_modelo_180_work_unit,
    seed_work_unit,
    upsert_work_unit,
    verify_modelo_revision,
    verify_revision,
    workflow_gate,
    workflow_profile,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]


def test_mark_verificado_completo_requires_borrador_state(repos: Repos) -> None:
    """A revision in any state other than BORRADOR cannot be marked
    verificado-completo."""

    wu_repo, cr_repo, _, _, bv_repo = repos
    work_unit = seed_work_unit(
        wu_repo,
        modelo="111",
        filing_year=2026,
        period="1T",
        revision_id="2019-y-siguientes",
    )
    revision = calculate_modelo_revision(
        work_unit.work_unit_id,
        casilla_inputs={
            M111_EMPLOYMENT_WITHHELD_CASILLA: Decimal("180.25"),
            M111_PROFESSIONAL_WITHHELD_CASILLA: Decimal("12.10"),
            M111_PRIZE_WITHHELD_CASILLA: Decimal("300.00"),
            M111_IMAGE_RIGHTS_WITHHELD_CASILLA: Decimal("14.40"),
            M111_FORESTRY_WITHHELD_CASILLA: Decimal("25.00"),
            M111_IMPUTED_INCOME_WITHHELD_CASILLA: Decimal("0.50"),
            M111_ACTIVITY_COUNT_CASILLA: Decimal("7.00"),
            M111_ACTIVITY_AMOUNT_CASILLA: Decimal("8.00"),
            M111_ACTIVITY_WITHHELD_CASILLA: Decimal("9.00"),
            M111_TOTAL_WITHHELD_CASILLA: Decimal("40.00"),
        },
        work_unit_repository=wu_repo,
        calculation_repository=cr_repo,
        bucket_event_repository=bv_repo,
        clock=T1,
    )
    verified = mark_revision_verificado_completo(
        revision.calculation_revision_id,
        actor="operator-A",
        calculation_repository=cr_repo,
        clock=T2,
    )
    assert verified.state is CalculationRevisionState.VERIFICADO_COMPLETO

    # Second attempt against the now-verified revision must fail.
    with pytest.raises(CalculationRevisionStateError, match=r"state|verified|already|complete"):
        mark_revision_verificado_completo(
            revision.calculation_revision_id,
            actor="operator-A",
            calculation_repository=cr_repo,
            clock=T3,
        )


def test_verify_grants_for_a_closed_past_period_real_registry(repos: Repos) -> None:
    """``work verify`` is independent of the AEAT filing calendar.

    A modelo 130 calculation for 2024 Q1 — whose filing window closed
    in April 2024 — is verified at a 2026 clock. ``compute_obligation``
    derives the schedule from ``today.year`` (2026), so no obligation
    exists for the 2024 period at all. The pre-deadline-independence
    behaviour aborted here with ``NO_PENDING_OBLIGATION``; verify must
    now still grant ``VERIFICADO_COMPLETO`` because the calculation is
    sound and verification does not depend on the filing window.
    """

    wu_repo, cr_repo, _, vr_repo, bv_repo = repos
    work_unit = seed_work_unit(wu_repo, filing_year=2024)

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
        actor="operator-A",
        work_unit_repository=wu_repo,
        calculation_repository=cr_repo,
        verification_repository=vr_repo,
        bucket_event_repository=bv_repo,
        clock=T2,
    )

    assert report.granted_verificado_completo is True
    assert report.completeness_status is VerificationCompletenessStatus.COMPLETE

    refreshed = get_calculation_revision(
        revision.calculation_revision_id,
        calculation_repository=cr_repo,
    )
    assert refreshed.state is CalculationRevisionState.VERIFICADO_COMPLETO


def test_verify_repairs_missing_current_revision_pointer(repos: Repos) -> None:
    wu_repo, cr_repo, _, vr_repo, bv_repo = repos
    work_unit = seed_work_unit(wu_repo)
    baseline_inputs = dict(DEFAULT_130_BASELINE_INPUTS)
    baseline_inputs.pop(M130_CARRY_FORWARD_CASILLA, None)
    revision = calculate_modelo_revision(
        work_unit.work_unit_id,
        casilla_inputs=baseline_inputs,
        binding_values=DEFAULT_130_BINDING_VALUES,
        work_unit_repository=wu_repo,
        calculation_repository=cr_repo,
        bucket_event_repository=bv_repo,
        clock=T1,
    )
    calculated_work_unit = get_work_unit(work_unit.work_unit_id, repository=wu_repo)
    assert calculated_work_unit.current_calculation_revision_id == revision.calculation_revision_id
    wu_repo.save(
        upsert_work_unit(
            wu_repo.load(),
            calculated_work_unit.model_copy(update={"current_calculation_revision_id": None}),
        ),
    )

    report = verify_revision(
        revision.calculation_revision_id,
        revision=revision,
        work_unit=work_unit,
        actor="operator-A",
        work_unit_repository=wu_repo,
        calculation_repository=cr_repo,
        verification_repository=vr_repo,
        bucket_event_repository=bv_repo,
        clock=T2,
    )

    assert report.granted_verificado_completo is True
    repaired = get_work_unit(work_unit.work_unit_id, repository=wu_repo)
    assert repaired.current_calculation_revision_id == revision.calculation_revision_id


def test_verify_does_not_overwrite_different_current_revision(repos: Repos) -> None:
    wu_repo, cr_repo, _, vr_repo, bv_repo = repos
    work_unit = seed_work_unit(wu_repo)
    baseline_inputs = dict(DEFAULT_130_BASELINE_INPUTS)
    baseline_inputs.pop(M130_CARRY_FORWARD_CASILLA, None)
    first = calculate_modelo_revision(
        work_unit.work_unit_id,
        casilla_inputs=baseline_inputs,
        binding_values=DEFAULT_130_BINDING_VALUES,
        work_unit_repository=wu_repo,
        calculation_repository=cr_repo,
        bucket_event_repository=bv_repo,
        clock=T1,
    )
    second_inputs = dict(baseline_inputs)
    second_inputs[M130_INCOME_CASILLA] = second_inputs[M130_INCOME_CASILLA] + Decimal("1")
    second = calculate_modelo_revision(
        work_unit.work_unit_id,
        casilla_inputs=second_inputs,
        binding_values=DEFAULT_130_BINDING_VALUES,
        work_unit_repository=wu_repo,
        calculation_repository=cr_repo,
        bucket_event_repository=bv_repo,
        clock=T2,
    )
    assert first.calculation_revision_id != second.calculation_revision_id
    current_work_unit = get_work_unit(work_unit.work_unit_id, repository=wu_repo)
    assert current_work_unit.current_calculation_revision_id == second.calculation_revision_id

    report = verify_revision(
        first.calculation_revision_id,
        revision=first,
        work_unit=work_unit,
        actor="operator-A",
        work_unit_repository=wu_repo,
        calculation_repository=cr_repo,
        verification_repository=vr_repo,
        bucket_event_repository=bv_repo,
        clock=T3,
    )

    assert report.granted_verificado_completo is True
    preserved = get_work_unit(work_unit.work_unit_id, repository=wu_repo)
    assert preserved.current_calculation_revision_id == second.calculation_revision_id


def test_verify_records_deadline_state_as_informational_not_abort(repos: Repos) -> None:
    """The verify run's ``COMPUTING_DEADLINES`` step never aborts.

    For a closed past period it records the filing-window state as an
    informational success step, so ``readiness`` and ``verify`` agree:
    a readiness-ready modelo stays reachable by verify.
    """

    wu_repo, cr_repo, _, _, bv_repo = repos
    work_unit = seed_work_unit(wu_repo, filing_year=2024)
    revision = calculate_modelo_revision(
        work_unit.work_unit_id,
        casilla_inputs=DEFAULT_130_BASELINE_INPUTS,
        binding_values=DEFAULT_130_BINDING_VALUES,
        work_unit_repository=wu_repo,
        calculation_repository=cr_repo,
        bucket_event_repository=bv_repo,
        clock=T1,
    )

    gate = workflow_gate(revision=revision, work_unit=work_unit, clock=T2)
    result = asyncio.run(
        gate.engine.run_for_period(
            gate.profile,
            work_unit.modelo,
            canonical_work_unit_period(work_unit),
            today=T2.date(),
            purpose=WorkflowPurpose.VERIFY,
        ),
    )

    assert result.final_stage is WorkflowStage.DONE
    assert result.aborted_reason is None
    deadline_steps = [s for s in result.steps if s.stage is WorkflowStage.COMPUTING_DEADLINES]
    assert len(deadline_steps) == 1
    deadline_step = deadline_steps[0]
    assert deadline_step.success is True
    assert isinstance(deadline_step.details, WorkflowDeadlineContextDetails)
    assert deadline_step.details.deadline_role is not None
    assert deadline_step.details.deadline_role.value == "informational"


def test_get_calculation_revision_raises_on_missing_id(repos: Repos) -> None:
    _, cr_repo, _, _, _ = repos
    with pytest.raises(CalculationRevisionNotFoundError):
        get_calculation_revision(
            "0" * 64,
            calculation_repository=cr_repo,
        )


def test_verify_grants_when_all_required_casillas_present_real_registry(
    repos: Repos,
) -> None:
    """Real e2e: registry resolves modelo 180 (2024, 0A); every required
    manual casilla is supplied; the verifier persists a granted report
    in encrypted storage; the calculation revision transitions
    DRAFT → VERIFICADO_COMPLETO. No mocks, no in-memory fakes — the
    SQL repository encrypts on save and decrypts on load."""

    wu_repo, cr_repo, _, vr_repo, bv_repo = repos
    work_unit = seed_work_unit(wu_repo)
    required = registry_required_manual_casillas_for(
        modelo=work_unit.modelo,
        filing_year=work_unit.filing_year,
        period=work_unit.period.registry_token,
    )

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
        actor="operator-A",
        work_unit_repository=wu_repo,
        calculation_repository=cr_repo,
        verification_repository=vr_repo,
        bucket_event_repository=bv_repo,
        clock=T2,
    )

    assert report.granted_verificado_completo is True
    assert report.completeness_status is VerificationCompletenessStatus.COMPLETE
    # The report carries no BLOCKING finding. Other non-blocking advisory findings
    # may be present, but source-revision re-confirmation failures are blockers.
    assert not any(f.severity is ModeloVerificationFindingSeverity.BLOCKING for f in report.findings)
    assert all(f.kind is ModeloVerificationFindingKind.ADVISORY for f in report.findings)
    assert set(report.resolved_casilla_ids) == set(required)
    assert report.missing_required_casilla_ids == ()

    refreshed = get_calculation_revision(
        revision.calculation_revision_id,
        calculation_repository=cr_repo,
    )
    assert refreshed.state is CalculationRevisionState.VERIFICADO_COMPLETO
    assert refreshed.verified_at == T2
    assert refreshed.verified_by == "operator-A"

    # Round-trip through encrypted storage.
    persisted = get_verification_report(
        report.verification_report_id,
        verification_repository=vr_repo,
    )
    assert persisted.granted_verificado_completo is True
    assert persisted.completeness_status is VerificationCompletenessStatus.COMPLETE


def test_verify_refuses_when_required_casilla_missing_real_registry(
    repos: Repos,
) -> None:
    """Real e2e: omit one required casilla; the verifier emits a
    BLOCKING ``MISSING_REQUIRED_CASILLA`` finding for it; the
    revision stays DRAFT; the refused report is still persisted so
    the audit trail records the refusal."""

    wu_repo, cr_repo, fr_repo, vr_repo, bv_repo = repos
    required = registry_required_manual_casillas()
    assert len(required) >= 2

    omitted = required[0]
    supplied = {cid: Decimal("1") for cid in required[1:]}

    work_unit = seed_modelo_180_work_unit(wu_repo)
    revision = calculate_modelo_revision(
        work_unit.work_unit_id,
        casilla_inputs=supplied,
        binding_values=DEFAULT_180_BINDING_VALUES,
        relation_values=DEFAULT_180_RELATION_VALUES,
        work_unit_repository=wu_repo,
        calculation_repository=cr_repo,
        bucket_event_repository=bv_repo,
        clock=T1,
    )
    seed_clean_cross_period_sources(
        work_unit,
        work_unit_repository=wu_repo,
        calculation_repository=cr_repo,
        filing_repository=fr_repo,
        bucket_event_repository=bv_repo,
    )

    report = verify_modelo_revision(
        revision.calculation_revision_id,
        actor="operator-A",
        workflow_profile=workflow_profile(),
        work_unit_repository=wu_repo,
        calculation_repository=cr_repo,
        verification_repository=vr_repo,
        bucket_event_repository=bv_repo,
        clock=T2,
    )

    assert report.granted_verificado_completo is False
    assert report.completeness_status is VerificationCompletenessStatus.INCOMPLETE
    assert any(
        f.kind is ModeloVerificationFindingKind.MISSING_REQUIRED_CASILLA
        and f.severity is ModeloVerificationFindingSeverity.BLOCKING
        and f.casilla_id == omitted
        for f in report.findings
    )
    assert omitted in report.missing_required_casilla_ids

    refreshed = get_calculation_revision(
        revision.calculation_revision_id,
        calculation_repository=cr_repo,
    )
    assert refreshed.state is CalculationRevisionState.BORRADOR

    persisted = get_verification_report(
        report.verification_report_id,
        verification_repository=vr_repo,
    )
    assert persisted.granted_verificado_completo is False


def test_verify_emits_blocking_rule_when_registry_unresolved_real_registry(
    repos: Repos,
) -> None:
    """Real e2e: a work unit anchored to a year that predates modelo
    180's earliest revision (``valid_from=2019``) cannot resolve a
    registry snapshot. The verifier surfaces a BLOCKING_RULE finding
    and refuses the transition. The revision stays DRAFT."""

    wu_repo, cr_repo, _, vr_repo, bv_repo = repos

    work_unit = seed_work_unit(
        wu_repo,
        modelo=VERIFY_MODELO,
        filing_year=2010,
        period=VERIFY_PERIOD,
        revision_id=VERIFY_REVISION,
    )
    # Direct-seed a DRAFT revision because ``calculate_modelo_revision``
    # now runs the formula engine and would refuse the unresolvable
    # snapshot at calculate time. This test exercises verify's
    # BLOCKING_RULE path explicitly: the work unit was anchored at a
    # year that predates the modelo's earliest revision, so verify's
    # registry-snapshot resolution still fails.
    from ....domain.calculations.registry.bindings import CasillaObservation
    from ....domain.modelos.calculation_repository import upsert_calculation_revision
    from ....domain.modelos.calculation_revision import CalculationRevision, derive_calculation_revision_id

    inputs: dict[CasillaId, str] = {M180_PERCEPTOR_BASE_CASILLA: "1"}
    overrides_map: dict[str, str] = {}
    casillas: dict[CasillaId, Decimal] = {M180_PERCEPTOR_BASE_CASILLA: Decimal("1")}
    rid = derive_calculation_revision_id(
        work_unit_id=work_unit.work_unit_id,
        input_values_by_casilla_id=inputs,
        binding_overrides=overrides_map,
        casilla_values=casillas,
        filing_instance_evidence=None,
        source_provenance=(),
    )
    revision = CalculationRevision(
        calculation_revision_id=rid,
        work_unit_id=work_unit.work_unit_id,
        state=CalculationRevisionState.BORRADOR,
        input_values_by_casilla_id=inputs,
        binding_overrides=overrides_map,
        casilla_values=casillas,
        observations=(
            CasillaObservation(
                casilla_id=M180_PERCEPTOR_BASE_CASILLA,
                value=Decimal("1"),
                legal_refs=("ley-58-2003:art-93",),
                source_refs=("verify-unresolved-registry-test",),
            ),
        ),
        created_at=T1,
        updated_at=T1,
        filing_instance_evidence=None,
        source_provenance=(),
    )
    cr_repo.save(upsert_calculation_revision(cr_repo.load(), revision))

    report = verify_modelo_revision(
        revision.calculation_revision_id,
        actor="operator-A",
        workflow_profile=workflow_profile(),
        work_unit_repository=wu_repo,
        calculation_repository=cr_repo,
        verification_repository=vr_repo,
        bucket_event_repository=bv_repo,
        clock=T2,
    )

    assert report.granted_verificado_completo is False
    assert report.completeness_status is VerificationCompletenessStatus.BLOCKED
    assert any(f.kind is ModeloVerificationFindingKind.BLOCKING_RULE for f in report.findings)

    refreshed = get_calculation_revision(
        revision.calculation_revision_id,
        calculation_repository=cr_repo,
    )
    assert refreshed.state is CalculationRevisionState.BORRADOR


def test_verify_reverify_collapses_to_existing_report_real_registry(repos: Repos) -> None:
    """Real e2e: re-verifying an already-verified revision is a guarded no-op.

    Per aeat-cli-contract, verify is a creating
    mutation keyed on the clock-free derived report id
    (``derive_verification_report_id`` folds the outcome, not ``run_at``). A retry
    against a locked ``VERIFICADO_COMPLETO`` revision — whose content, and thus
    verification outcome, cannot change — collapses to the EXISTING granting
    report: same report id, ``run_at`` unchanged (NOT re-stamped to the retry
    clock), no second verification lifecycle event, revision still verified. It
    must never refuse. Mirrors the re-file no-op.
    """

    wu_repo, cr_repo, fr_repo, vr_repo, bv_repo = repos
    work_unit = seed_work_unit(wu_repo)
    revision = calculate_modelo_revision(
        work_unit.work_unit_id,
        casilla_inputs=DEFAULT_130_BASELINE_INPUTS,
        binding_values=DEFAULT_130_BINDING_VALUES,
        work_unit_repository=wu_repo,
        calculation_repository=cr_repo,
        bucket_event_repository=bv_repo,
        clock=T1,
    )
    seed_clean_cross_period_sources(
        work_unit,
        work_unit_repository=wu_repo,
        calculation_repository=cr_repo,
        filing_repository=fr_repo,
        bucket_event_repository=bv_repo,
    )
    first = verify_modelo_revision(
        revision.calculation_revision_id,
        actor="operator-A",
        workflow_profile=workflow_profile(),
        work_unit_repository=wu_repo,
        calculation_repository=cr_repo,
        verification_repository=vr_repo,
        bucket_event_repository=bv_repo,
        clock=T2,
    )
    assert first.granted_verificado_completo is True
    assert (
        get_calculation_revision(revision.calculation_revision_id, calculation_repository=cr_repo).state
        is CalculationRevisionState.VERIFICADO_COMPLETO
    )

    def _verification_event_ids() -> tuple[str, ...]:
        events = bv_repo.load().for_bucket(
            work_unit.bucket_id,
            event_types=(
                BucketEventType.MODELO_VERIFICATION_PASSED,
                BucketEventType.MODELO_VERIFICATION_REFUSED,
            ),
        )
        return tuple(event.event_id for event in events)

    event_ids_after_first = _verification_event_ids()
    reports_after_first = tuple(
        r.verification_report_id
        for r in list_verification_reports(
            calculation_revision_id=revision.calculation_revision_id,
            verification_repository=vr_repo,
        )
    )

    # Re-verify at a LATER clock (T3): must collapse, not refuse.
    second = verify_modelo_revision(
        revision.calculation_revision_id,
        actor="operator-A",
        workflow_profile=workflow_profile(),
        work_unit_repository=wu_repo,
        calculation_repository=cr_repo,
        verification_repository=vr_repo,
        bucket_event_repository=bv_repo,
        clock=T3,
    )

    # Same content-addressed report; anti-tautology — run_at stays T2, NOT re-stamped to T3.
    assert second.verification_report_id == first.verification_report_id
    assert second.run_at == first.run_at == T2
    assert second.granted_verificado_completo is True
    # No second lifecycle event, and the report catalogue is unchanged.
    assert _verification_event_ids() == event_ids_after_first
    reports_after_second = tuple(
        r.verification_report_id
        for r in list_verification_reports(
            calculation_revision_id=revision.calculation_revision_id,
            verification_repository=vr_repo,
        )
    )
    assert reports_after_second == reports_after_first
    assert (
        get_calculation_revision(revision.calculation_revision_id, calculation_repository=cr_repo).state
        is CalculationRevisionState.VERIFICADO_COMPLETO
    )


def test_verify_refuses_non_draft_revision_with_no_granting_report(repos: Repos) -> None:
    """The idempotent collapse stays guarded: a non-draft revision with NO granting
    report is an inconsistent state that still refuses.

    This is the anti-tautology proof for the collapse — the fix does not blanket-
    accept every non-draft revision; it collapses ONLY when a granting report
    actually exists, and otherwise keeps the hard state refusal.
    """

    wu_repo, cr_repo, _, vr_repo, bv_repo = repos
    # Modelo 111 has no cross-period dependencies, so mark can transition it to
    # VERIFICADO_COMPLETO without seeding cross-period evidence.
    work_unit = seed_work_unit(
        wu_repo,
        modelo="111",
        filing_year=2026,
        period="1T",
        revision_id="2019-y-siguientes",
    )
    revision = calculate_modelo_revision(
        work_unit.work_unit_id,
        casilla_inputs={
            M111_EMPLOYMENT_WITHHELD_CASILLA: Decimal("180.25"),
            M111_PROFESSIONAL_WITHHELD_CASILLA: Decimal("12.10"),
            M111_PRIZE_WITHHELD_CASILLA: Decimal("300.00"),
            M111_IMAGE_RIGHTS_WITHHELD_CASILLA: Decimal("14.40"),
            M111_FORESTRY_WITHHELD_CASILLA: Decimal("25.00"),
            M111_IMPUTED_INCOME_WITHHELD_CASILLA: Decimal("0.50"),
            M111_ACTIVITY_COUNT_CASILLA: Decimal("7.00"),
            M111_ACTIVITY_AMOUNT_CASILLA: Decimal("8.00"),
            M111_ACTIVITY_WITHHELD_CASILLA: Decimal("9.00"),
            M111_TOTAL_WITHHELD_CASILLA: Decimal("40.00"),
        },
        work_unit_repository=wu_repo,
        calculation_repository=cr_repo,
        bucket_event_repository=bv_repo,
        clock=T1,
    )
    # Transition the revision to VERIFICADO_COMPLETO WITHOUT persisting a report,
    # producing the inconsistent state the guard must refuse.
    verified = mark_revision_verificado_completo(
        revision.calculation_revision_id,
        actor="operator-A",
        calculation_repository=cr_repo,
        clock=T2,
    )
    assert verified.state is CalculationRevisionState.VERIFICADO_COMPLETO

    with pytest.raises(CalculationRevisionStateError, match=r"state|DRAFT|draft"):
        verify_modelo_revision(
            revision.calculation_revision_id,
            actor="operator-A",
            workflow_profile=workflow_profile(),
            work_unit_repository=wu_repo,
            calculation_repository=cr_repo,
            verification_repository=vr_repo,
            bucket_event_repository=bv_repo,
            clock=T3,
        )


def test_list_and_get_verification_reports_real_registry(repos: Repos) -> None:
    """Real e2e: reports persist through the encrypted catalogue and
    are indexable by id and by calculation_revision_id."""

    wu_repo, cr_repo, _, vr_repo, bv_repo = repos
    work_unit = seed_work_unit(wu_repo)
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
        actor="operator-A",
        work_unit_repository=wu_repo,
        calculation_repository=cr_repo,
        verification_repository=vr_repo,
        bucket_event_repository=bv_repo,
        clock=T2,
    )

    listed = list_verification_reports(
        calculation_revision_id=revision.calculation_revision_id,
        verification_repository=vr_repo,
    )
    assert tuple(r.verification_report_id for r in listed) == (report.verification_report_id,)

    fetched = get_verification_report(
        report.verification_report_id,
        verification_repository=vr_repo,
    )
    assert fetched.verification_report_id == report.verification_report_id

    with pytest.raises(VerificationReportNotFoundError) as excinfo:
        get_verification_report(
            "0" * 64,
            verification_repository=vr_repo,
        )
    assert excinfo.value.translated_message == "application.modelo.errors.verification_report_not_found"


def test_mark_verificado_completo_refuses_a_ledger_derived_revision(repos: Repos) -> None:
    """A revision carrying ledger contributors must go through verify.

    A ledger-derived revision owes a bundled evidence record pegged to its
    snapshot fingerprint, and that bundle is built inside verify's granted
    branch. This transition does not run verify, so promoting through it
    produced a VERIFICADO_COMPLETO revision indistinguishable from a granted
    one while skipping the evidence bundle, the ledger-drift check and the
    clean-state gates -- and export then accepts it on the snapshot alone,
    a reference to a bundle that was never written.

    The refusal keys on the contributor set rather than the state, so it
    leaves every non-ledger caller of this transition untouched.
    """
    wu_repo, cr_repo, _, _, bv_repo = repos
    work_unit = seed_work_unit(
        wu_repo,
        modelo="111",
        filing_year=2026,
        period="1T",
        revision_id="2019-y-siguientes",
    )
    revision = calculate_modelo_revision(
        work_unit.work_unit_id,
        casilla_inputs={
            M111_EMPLOYMENT_WITHHELD_CASILLA: Decimal("180.25"),
            M111_PROFESSIONAL_WITHHELD_CASILLA: Decimal("12.10"),
            M111_PRIZE_WITHHELD_CASILLA: Decimal("300.00"),
            M111_IMAGE_RIGHTS_WITHHELD_CASILLA: Decimal("14.40"),
            M111_FORESTRY_WITHHELD_CASILLA: Decimal("25.00"),
            M111_IMPUTED_INCOME_WITHHELD_CASILLA: Decimal("0.50"),
            M111_ACTIVITY_COUNT_CASILLA: Decimal("7.00"),
            M111_ACTIVITY_AMOUNT_CASILLA: Decimal("8.00"),
            M111_ACTIVITY_WITHHELD_CASILLA: Decimal("9.00"),
            M111_TOTAL_WITHHELD_CASILLA: Decimal("40.00"),
        },
        work_unit_repository=wu_repo,
        calculation_repository=cr_repo,
        bucket_event_repository=bv_repo,
        clock=T1,
    )
    # Anti-tautology control: the identical calculation WITHOUT contributors
    # promotes cleanly, so the refusal below is the contributor set and not
    # some other property of the revision.
    assert revision.source_transaction_ids == ()
    promoted = mark_revision_verificado_completo(
        revision.calculation_revision_id,
        actor="operator-A",
        calculation_repository=cr_repo,
        work_unit_repository=wu_repo,
        clock=T2,
    )
    assert promoted.state is CalculationRevisionState.VERIFICADO_COMPLETO

    # The same inputs WITH ledger contributors. Built through calculate rather
    # than model_copy: contributors are part of the content-addressed id, so a
    # copied revision fails its own self-validation.
    ledger_derived = calculate_modelo_revision(
        work_unit.work_unit_id,
        casilla_inputs={
            M111_EMPLOYMENT_WITHHELD_CASILLA: Decimal("180.25"),
            M111_PROFESSIONAL_WITHHELD_CASILLA: Decimal("12.10"),
            M111_PRIZE_WITHHELD_CASILLA: Decimal("300.00"),
            M111_IMAGE_RIGHTS_WITHHELD_CASILLA: Decimal("14.40"),
            M111_FORESTRY_WITHHELD_CASILLA: Decimal("25.00"),
            M111_IMPUTED_INCOME_WITHHELD_CASILLA: Decimal("0.50"),
            M111_ACTIVITY_COUNT_CASILLA: Decimal("7.00"),
            M111_ACTIVITY_AMOUNT_CASILLA: Decimal("8.00"),
            M111_ACTIVITY_WITHHELD_CASILLA: Decimal("9.00"),
            M111_TOTAL_WITHHELD_CASILLA: Decimal("40.00"),
        },
        source_transaction_ids=("a" * 64, "b" * 64),
        work_unit_repository=wu_repo,
        calculation_repository=cr_repo,
        bucket_event_repository=bv_repo,
        clock=T3,
    )
    assert ledger_derived.source_transaction_ids == ("a" * 64, "b" * 64)

    with pytest.raises(CalculationRevisionStateError) as refusal:
        mark_revision_verificado_completo(
            ledger_derived.calculation_revision_id,
            actor="operator-A",
            calculation_repository=cr_repo,
            work_unit_repository=wu_repo,
            clock=T3,
        )

    assert "2" in str(refusal.value)
    reloaded = cr_repo.load().get(ledger_derived.calculation_revision_id)
    assert reloaded is not None
    assert reloaded.state is CalculationRevisionState.BORRADOR

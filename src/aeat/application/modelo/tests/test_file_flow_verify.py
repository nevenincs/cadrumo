"""Modelo file-flow application tests split by workflow."""

from __future__ import annotations

import pytest

from ....core import Period
from ....domain.calculations.registry import CasillaId
from ._file_flow_support import (
    _DEFAULT_130_BASELINE_INPUTS,
    _DEFAULT_130_BINDING_VALUES,
    _DEFAULT_180_BINDING_VALUES,
    _DEFAULT_180_RELATION_VALUES,
    _M111_ACTIVITY_AMOUNT_CASILLA,
    _M111_ACTIVITY_COUNT_CASILLA,
    _M111_ACTIVITY_WITHHELD_CASILLA,
    _M111_EMPLOYMENT_WITHHELD_CASILLA,
    _M111_FORESTRY_WITHHELD_CASILLA,
    _M111_IMAGE_RIGHTS_WITHHELD_CASILLA,
    _M111_IMPUTED_INCOME_WITHHELD_CASILLA,
    _M111_PRIZE_WITHHELD_CASILLA,
    _M111_PROFESSIONAL_WITHHELD_CASILLA,
    _M111_TOTAL_WITHHELD_CASILLA,
    _M180_PERCEPTOR_BASE_CASILLA,
    _T0,
    _T1,
    _T2,
    _T3,
    _VERIFY_MODELO,
    _VERIFY_PERIOD,
    _VERIFY_REVISION,
    BucketEventType,
    CalculationRevisionNotFoundError,
    CalculationRevisionState,
    CalculationRevisionStateError,
    Decimal,
    ModeloVerificationFindingKind,
    ModeloVerificationFindingSeverity,
    ModeloWorkflowGateError,
    VerificationCompletenessStatus,
    VerificationReportNotFoundError,
    WorkflowPurpose,
    WorkflowStage,
    _AuthProvider,
    _canonical_work_unit_period,
    _registry_required_manual_casillas,
    _registry_required_manual_casillas_for,
    _Repos,
    _seed_clean_cross_period_sources,
    _seed_modelo_180_work_unit,
    _seed_work_unit,
    _verify_revision,
    _workflow_gate,
    _workflow_profile,
    asyncio,
    calculate_modelo_revision,
    create_work_unit,
    get_calculation_revision,
    get_verification_report,
    list_verification_reports,
    mark_revision_verificado_completo,
    verify_modelo_revision,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]


def test_mark_verificado_completo_requires_borrador_state(repos: _Repos) -> None:
    """A revision in any state other than BORRADOR cannot be marked
    verificado-completo."""

    wu_repo, cr_repo, _, _, bv_repo = repos
    work_unit = _seed_work_unit(
        wu_repo,
        modelo="111",
        filing_year=2026,
        period="1T",
        revision_id="2019-y-siguientes",
    )
    revision = calculate_modelo_revision(
        work_unit.work_unit_id,
        casilla_inputs={
            _M111_EMPLOYMENT_WITHHELD_CASILLA: Decimal("180.25"),
            _M111_PROFESSIONAL_WITHHELD_CASILLA: Decimal("12.10"),
            _M111_PRIZE_WITHHELD_CASILLA: Decimal("300.00"),
            _M111_IMAGE_RIGHTS_WITHHELD_CASILLA: Decimal("14.40"),
            _M111_FORESTRY_WITHHELD_CASILLA: Decimal("25.00"),
            _M111_IMPUTED_INCOME_WITHHELD_CASILLA: Decimal("0.50"),
            _M111_ACTIVITY_COUNT_CASILLA: Decimal("7.00"),
            _M111_ACTIVITY_AMOUNT_CASILLA: Decimal("8.00"),
            _M111_ACTIVITY_WITHHELD_CASILLA: Decimal("9.00"),
            _M111_TOTAL_WITHHELD_CASILLA: Decimal("40.00"),
        },
        work_unit_repository=wu_repo,
        calculation_repository=cr_repo,
        bucket_event_repository=bv_repo,
        clock=_T1,
    )
    verified = mark_revision_verificado_completo(
        revision.calculation_revision_id,
        actor="operator-A",
        calculation_repository=cr_repo,
        clock=_T2,
    )
    assert verified.state is CalculationRevisionState.VERIFICADO_COMPLETO

    # Second attempt against the now-verified revision must fail.
    with pytest.raises(CalculationRevisionStateError, match=r"state|verified|already|complete"):
        mark_revision_verificado_completo(
            revision.calculation_revision_id,
            actor="operator-A",
            calculation_repository=cr_repo,
            clock=_T3,
        )


def test_verify_runs_workflow_gate_and_refuses_before_verified_state_write(repos: _Repos) -> None:
    """A granted verification must still pass the WorkflowEngine gate.

    Auth/preflight blockers abort before the verified-complete state,
    verification report, or verification bucket event is persisted.
    """

    wu_repo, cr_repo, _, vr_repo, bv_repo = repos
    work_unit = _seed_work_unit(wu_repo)
    revision = calculate_modelo_revision(
        work_unit.work_unit_id,
        casilla_inputs=_DEFAULT_130_BASELINE_INPUTS,
        binding_values=_DEFAULT_130_BINDING_VALUES,
        work_unit_repository=wu_repo,
        calculation_repository=cr_repo,
        bucket_event_repository=bv_repo,
        clock=_T1,
    )

    unavailable_provider = _AuthProvider(available=False)
    with pytest.raises(ModeloWorkflowGateError) as gate_error:
        _verify_revision(
            revision.calculation_revision_id,
            revision=revision,
            work_unit=work_unit,
            actor="operator-A",
            work_unit_repository=wu_repo,
            calculation_repository=cr_repo,
            verification_repository=vr_repo,
            bucket_event_repository=bv_repo,
            clock=_T2,
            auth_provider=unavailable_provider,
        )
    assert gate_error.value.result.final_stage is WorkflowStage.ABORTED
    assert gate_error.value.context is not None
    assert gate_error.value.context["stage"] == WorkflowStage.ABORTED.value

    assert unavailable_provider.describe_calls == 1
    refreshed_revision = get_calculation_revision(
        revision.calculation_revision_id,
        calculation_repository=cr_repo,
    )
    assert refreshed_revision.state is CalculationRevisionState.BORRADOR
    assert (
        list_verification_reports(
            calculation_revision_id=revision.calculation_revision_id,
            verification_repository=vr_repo,
        )
        == ()
    )
    verification_events = bv_repo.load().for_bucket(
        work_unit.bucket_id,
        event_types=(
            BucketEventType.MODELO_VERIFICATION_PASSED,
            BucketEventType.MODELO_VERIFICATION_REFUSED,
        ),
    )
    assert verification_events == ()


def test_verify_grants_for_a_closed_past_period_real_registry(repos: _Repos) -> None:
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
    work_unit = _seed_work_unit(wu_repo, filing_year=2024)

    revision = calculate_modelo_revision(
        work_unit.work_unit_id,
        casilla_inputs=_DEFAULT_130_BASELINE_INPUTS,
        binding_values=_DEFAULT_130_BINDING_VALUES,
        work_unit_repository=wu_repo,
        calculation_repository=cr_repo,
        bucket_event_repository=bv_repo,
        clock=_T1,
    )

    report = _verify_revision(
        revision.calculation_revision_id,
        revision=revision,
        work_unit=work_unit,
        actor="operator-A",
        work_unit_repository=wu_repo,
        calculation_repository=cr_repo,
        verification_repository=vr_repo,
        bucket_event_repository=bv_repo,
        clock=_T2,
    )

    assert report.granted_verificado_completo is True
    assert report.completeness_status is VerificationCompletenessStatus.COMPLETE

    refreshed = get_calculation_revision(
        revision.calculation_revision_id,
        calculation_repository=cr_repo,
    )
    assert refreshed.state is CalculationRevisionState.VERIFICADO_COMPLETO


def test_verify_records_deadline_state_as_informational_not_abort(repos: _Repos) -> None:
    """The verify run's ``COMPUTING_DEADLINES`` step never aborts.

    For a closed past period it records the filing-window state as an
    informational success step, so ``readiness`` and ``verify`` agree:
    a readiness-ready modelo stays reachable by verify.
    """

    wu_repo, cr_repo, _, _, bv_repo = repos
    work_unit = _seed_work_unit(wu_repo, filing_year=2024)
    revision = calculate_modelo_revision(
        work_unit.work_unit_id,
        casilla_inputs=_DEFAULT_130_BASELINE_INPUTS,
        binding_values=_DEFAULT_130_BINDING_VALUES,
        work_unit_repository=wu_repo,
        calculation_repository=cr_repo,
        bucket_event_repository=bv_repo,
        clock=_T1,
    )

    gate = _workflow_gate(revision=revision, work_unit=work_unit, clock=_T2)
    result = asyncio.run(
        gate.engine.run_for_period(
            gate.profile,
            work_unit.modelo,
            _canonical_work_unit_period(work_unit),
            today=_T2.date(),
            purpose=WorkflowPurpose.VERIFY,
        ),
    )

    assert result.final_stage is WorkflowStage.DONE
    assert result.aborted_reason is None
    deadline_steps = [s for s in result.steps if s.stage is WorkflowStage.COMPUTING_DEADLINES]
    assert len(deadline_steps) == 1
    deadline_step = deadline_steps[0]
    assert deadline_step.success is True
    assert deadline_step.details is not None
    assert deadline_step.details["deadline_role"] == "informational"


def test_get_calculation_revision_raises_on_missing_id(repos: _Repos) -> None:
    _, cr_repo, _, _, _ = repos
    with pytest.raises(CalculationRevisionNotFoundError):
        get_calculation_revision(
            "0" * 64,
            calculation_repository=cr_repo,
        )


def test_verify_grants_when_all_required_casillas_present_real_registry(
    repos: _Repos,
) -> None:
    """Real e2e: registry resolves modelo 180 (2024, 0A); every required
    manual casilla is supplied; the verifier persists a granted report
    in encrypted storage; the calculation revision transitions
    DRAFT → VERIFICADO_COMPLETO. No mocks, no in-memory fakes — the
    SQL repository encrypts on save and decrypts on load."""

    wu_repo, cr_repo, _, vr_repo, bv_repo = repos
    work_unit = _seed_work_unit(wu_repo)
    required = _registry_required_manual_casillas_for(
        modelo=work_unit.modelo,
        filing_year=work_unit.filing_year,
        period=work_unit.period.registry_token,
    )

    revision = calculate_modelo_revision(
        work_unit.work_unit_id,
        casilla_inputs=_DEFAULT_130_BASELINE_INPUTS,
        binding_values=_DEFAULT_130_BINDING_VALUES,
        work_unit_repository=wu_repo,
        calculation_repository=cr_repo,
        bucket_event_repository=bv_repo,
        clock=_T1,
    )

    report = _verify_revision(
        revision.calculation_revision_id,
        revision=revision,
        work_unit=work_unit,
        actor="operator-A",
        work_unit_repository=wu_repo,
        calculation_repository=cr_repo,
        verification_repository=vr_repo,
        bucket_event_repository=bv_repo,
        clock=_T2,
    )

    assert report.granted_verificado_completo is True
    assert report.completeness_status is VerificationCompletenessStatus.COMPLETE
    # The report carries no BLOCKING finding. A NON-BLOCKING revision-stamp ADVISORY
    # (WARNING) may be present when a cross-period carry source observation has no
    # re-confirmable registry revision stamp (period-revision-resolution decision,
    # Ruling 3 / R2) — it surfaces the carry to the operator without blocking the grant.
    assert not any(f.severity is ModeloVerificationFindingSeverity.BLOCKING for f in report.findings)
    assert all(f.kind is ModeloVerificationFindingKind.ADVISORY for f in report.findings)
    assert set(report.resolved_casilla_ids) == set(required)
    assert report.missing_required_casilla_ids == ()

    refreshed = get_calculation_revision(
        revision.calculation_revision_id,
        calculation_repository=cr_repo,
    )
    assert refreshed.state is CalculationRevisionState.VERIFICADO_COMPLETO
    assert refreshed.verified_at == _T2
    assert refreshed.verified_by == "operator-A"

    # Round-trip through encrypted storage.
    persisted = get_verification_report(
        report.verification_report_id,
        verification_repository=vr_repo,
    )
    assert persisted.granted_verificado_completo is True
    assert persisted.completeness_status is VerificationCompletenessStatus.COMPLETE


def test_verify_refuses_when_required_casilla_missing_real_registry(
    repos: _Repos,
) -> None:
    """Real e2e: omit one required casilla; the verifier emits a
    BLOCKING ``MISSING_REQUIRED_CASILLA`` finding for it; the
    revision stays DRAFT; the refused report is still persisted so
    the audit trail records the refusal."""

    wu_repo, cr_repo, fr_repo, vr_repo, bv_repo = repos
    required = _registry_required_manual_casillas()
    assert len(required) >= 2

    omitted = required[0]
    supplied = {cid: Decimal("1") for cid in required[1:]}

    work_unit = _seed_modelo_180_work_unit(wu_repo)
    revision = calculate_modelo_revision(
        work_unit.work_unit_id,
        casilla_inputs=supplied,
        binding_values=_DEFAULT_180_BINDING_VALUES,
        relation_values=_DEFAULT_180_RELATION_VALUES,
        work_unit_repository=wu_repo,
        calculation_repository=cr_repo,
        bucket_event_repository=bv_repo,
        clock=_T1,
    )
    _seed_clean_cross_period_sources(
        work_unit,
        work_unit_repository=wu_repo,
        calculation_repository=cr_repo,
        filing_repository=fr_repo,
        bucket_event_repository=bv_repo,
    )

    report = verify_modelo_revision(
        revision.calculation_revision_id,
        actor="operator-A",
        workflow_profile=_workflow_profile(),
        work_unit_repository=wu_repo,
        calculation_repository=cr_repo,
        verification_repository=vr_repo,
        bucket_event_repository=bv_repo,
        clock=_T2,
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
    repos: _Repos,
) -> None:
    """Real e2e: a work unit anchored to a year that predates modelo
    180's earliest revision (``valid_from=2019``) cannot resolve a
    registry snapshot. The verifier surfaces a BLOCKING_RULE finding
    and refuses the transition. The revision stays DRAFT."""

    wu_repo, cr_repo, _, vr_repo, bv_repo = repos

    work_unit = create_work_unit(
        bucket_id="default",
        modelo=_VERIFY_MODELO,
        filing_year=2010,
        period=Period.from_year_and_code(2010, _VERIFY_PERIOD),
        revision_id=_VERIFY_REVISION,
        repository=wu_repo,
        clock=_T0,
    )
    # Direct-seed a DRAFT revision because ``calculate_modelo_revision``
    # now runs the formula engine and would refuse the unresolvable
    # snapshot at calculate time. This test exercises verify's
    # BLOCKING_RULE path explicitly: the work unit was anchored at a
    # year that predates the modelo's earliest revision, so verify's
    # registry-snapshot resolution still fails.
    from ....domain.calculations.registry import CasillaObservation
    from ....domain.modelos._calculation_repository import (
        upsert_calculation_revision,
    )
    from ....domain.modelos._calculation_revision import (
        CalculationRevision,
        derive_calculation_revision_id,
    )

    inputs: dict[CasillaId, str] = {_M180_PERCEPTOR_BASE_CASILLA: "1"}
    overrides_map: dict[str, str] = {}
    casillas: dict[CasillaId, Decimal] = {_M180_PERCEPTOR_BASE_CASILLA: Decimal("1")}
    rid = derive_calculation_revision_id(
        work_unit_id=work_unit.work_unit_id,
        input_values_by_casilla_id=inputs,
        binding_overrides=overrides_map,
        casilla_values=casillas,
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
                casilla_id=_M180_PERCEPTOR_BASE_CASILLA,
                value=Decimal("1"),
                legal_refs=("ley-58-2003:art-93",),
                source_refs=("verify-unresolved-registry-test",),
            ),
        ),
        created_at=_T1,
        updated_at=_T1,
    )
    cr_repo.save(upsert_calculation_revision(cr_repo.load(), revision))

    report = verify_modelo_revision(
        revision.calculation_revision_id,
        actor="operator-A",
        workflow_profile=_workflow_profile(),
        work_unit_repository=wu_repo,
        calculation_repository=cr_repo,
        verification_repository=vr_repo,
        bucket_event_repository=bv_repo,
        clock=_T2,
    )

    assert report.granted_verificado_completo is False
    assert report.completeness_status is VerificationCompletenessStatus.BLOCKED
    assert any(f.kind is ModeloVerificationFindingKind.BLOCKING_RULE for f in report.findings)

    refreshed = get_calculation_revision(
        revision.calculation_revision_id,
        calculation_repository=cr_repo,
    )
    assert refreshed.state is CalculationRevisionState.BORRADOR


def test_verify_rejects_non_borrador_revision_real_registry(repos: _Repos) -> None:
    """Real e2e: a verificado-completo revision cannot be re-verified.
    The operator must produce a fresh draft (which lands as BORRADOR)
    to verify again."""

    wu_repo, cr_repo, _, vr_repo, bv_repo = repos
    work_unit = _seed_work_unit(wu_repo)
    revision = calculate_modelo_revision(
        work_unit.work_unit_id,
        casilla_inputs=_DEFAULT_130_BASELINE_INPUTS,
        binding_values=_DEFAULT_130_BINDING_VALUES,
        work_unit_repository=wu_repo,
        calculation_repository=cr_repo,
        bucket_event_repository=bv_repo,
        clock=_T1,
    )
    _verify_revision(
        revision.calculation_revision_id,
        revision=revision,
        work_unit=work_unit,
        actor="operator-A",
        work_unit_repository=wu_repo,
        calculation_repository=cr_repo,
        verification_repository=vr_repo,
        bucket_event_repository=bv_repo,
        clock=_T2,
    )

    with pytest.raises(CalculationRevisionStateError, match=r"state|verify|verified|already"):
        verify_modelo_revision(
            revision.calculation_revision_id,
            actor="operator-A",
            workflow_profile=_workflow_profile(),
            work_unit_repository=wu_repo,
            calculation_repository=cr_repo,
            verification_repository=vr_repo,
            bucket_event_repository=bv_repo,
            clock=_T3,
        )


def test_list_and_get_verification_reports_real_registry(repos: _Repos) -> None:
    """Real e2e: reports persist through the encrypted catalogue and
    are indexable by id and by calculation_revision_id."""

    wu_repo, cr_repo, _, vr_repo, bv_repo = repos
    work_unit = _seed_work_unit(wu_repo)
    revision = calculate_modelo_revision(
        work_unit.work_unit_id,
        casilla_inputs=_DEFAULT_130_BASELINE_INPUTS,
        binding_values=_DEFAULT_130_BINDING_VALUES,
        work_unit_repository=wu_repo,
        calculation_repository=cr_repo,
        bucket_event_repository=bv_repo,
        clock=_T1,
    )
    report = _verify_revision(
        revision.calculation_revision_id,
        revision=revision,
        work_unit=work_unit,
        actor="operator-A",
        work_unit_repository=wu_repo,
        calculation_repository=cr_repo,
        verification_repository=vr_repo,
        bucket_event_repository=bv_repo,
        clock=_T2,
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

"""Modelo file-flow application tests split by workflow."""

from __future__ import annotations

import pytest

from ....tests.cross_period_seeding import seed_clean_cross_period_sources
from ._file_flow_support import (
    DEFAULT_130_BASELINE_INPUTS,
    DEFAULT_130_BINDING_VALUES,
    DEFAULT_180_BINDING_VALUES,
    DEFAULT_180_RELATION_VALUES,
    M130_EXPENSE_CASILLA,
    M130_INCOME_CASILLA,
    T1,
    T2,
    T3,
    T4,
    T5,
    BucketEventObjectType,
    BucketEventType,
    Decimal,
    Repos,
    calculate_modelo_revision,
    file_revision,
    registry_required_manual_casillas,
    seed_modelo_180_work_unit,
    seed_work_unit,
    verify_modelo_revision,
    verify_revision,
    workflow_profile,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]


def test_calculate_emits_modelo_calculation_created_event(repos: Repos) -> None:
    """calculate_modelo_revision appends a ``modelo.calculation.created``
    event with the new revision id as object_id and the work unit's
    (modelo, year, period) carried in the payload."""

    wu_repo, cr_repo, _, _, bv_repo = repos
    work_unit = seed_work_unit(wu_repo)

    revision = calculate_modelo_revision(
        work_unit.work_unit_id,
        actor="operator-A",
        casilla_inputs={M130_INCOME_CASILLA: Decimal("1000")},
        binding_values=DEFAULT_130_BINDING_VALUES,
        work_unit_repository=wu_repo,
        calculation_repository=cr_repo,
        bucket_event_repository=bv_repo,
        clock=T1,
    )

    catalogue = bv_repo.load()
    events = [
        event
        for event in catalogue.for_bucket(work_unit.bucket_id)
        if event.event_type is BucketEventType.MODELO_CALCULATION_CREATED
    ]
    assert len(events) == 1
    event = events[0]
    assert event.object_type is BucketEventObjectType.CALCULATION_REVISION
    assert event.object_id == revision.calculation_revision_id
    assert event.actor == "operator-A"
    assert event.occurred_at == T1
    assert event.payload["work_unit_id"] == work_unit.work_unit_id
    assert event.payload["modelo"] == work_unit.modelo
    assert event.payload["filing_year"] == str(work_unit.filing_year)
    assert event.payload["period"] == work_unit.period.registry_token
    assert event.payload["borrador_snapshot_id"] == ""
    assert event.payload["borrador_binding_count"] == "0"


def test_verify_emits_passed_event_on_success(repos: Repos) -> None:
    """verify_modelo_revision emits ``modelo.verification.passed``
    when the verifier grants verified-complete; the event id matches
    the persisted verification report."""

    wu_repo, cr_repo, _, vr_repo, bv_repo = repos
    work_unit = seed_work_unit(wu_repo)
    revision = calculate_modelo_revision(
        work_unit.work_unit_id,
        actor="operator-A",
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

    catalogue = bv_repo.load()
    verification_events = catalogue.for_bucket(
        work_unit.bucket_id,
        event_types=(
            BucketEventType.MODELO_VERIFICATION_PASSED,
            BucketEventType.MODELO_VERIFICATION_REFUSED,
        ),
    )
    assert len(verification_events) == 1
    event = verification_events[0]
    assert event.event_type is BucketEventType.MODELO_VERIFICATION_PASSED
    assert event.object_type is BucketEventObjectType.VERIFICATION_REPORT
    assert event.object_id == report.verification_report_id
    assert event.payload["calculation_revision_id"] == revision.calculation_revision_id
    assert event.payload["completeness_status"] == "complete"


def test_verify_emits_refused_event_on_missing_casilla(repos: Repos) -> None:
    """verify_modelo_revision emits ``modelo.verification.refused``
    when a required casilla is missing; the calculation revision
    stays DRAFT and the refusal lands in the bucket event log."""

    wu_repo, cr_repo, fr_repo, vr_repo, bv_repo = repos
    required = registry_required_manual_casillas()
    omitted = required[0]
    supplied = {cid: Decimal("1") for cid in required[1:]}

    work_unit = seed_modelo_180_work_unit(wu_repo)
    revision = calculate_modelo_revision(
        work_unit.work_unit_id,
        actor="operator-A",
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

    catalogue = bv_repo.load()
    refused = catalogue.for_bucket(
        work_unit.bucket_id,
        event_types=(BucketEventType.MODELO_VERIFICATION_REFUSED,),
    )
    assert len(refused) == 1
    event = refused[0]
    assert event.event_type is BucketEventType.MODELO_VERIFICATION_REFUSED
    assert event.payload["completeness_status"] == "incomplete"
    assert int(event.payload["missing_required_count"]) >= 1
    assert omitted not in event.payload  # omitted casilla id stays in the report, not the event payload


def test_file_emits_modelo_filed_event(repos: Repos) -> None:
    """file_modelo_revision appends a ``modelo.filed`` event
    referencing the new filing record id and carrying the modelo /
    year / period plus the underlying revision id."""

    wu_repo, cr_repo, fr_repo, vr_repo, bv_repo = repos
    work_unit = seed_work_unit(wu_repo)
    revision = calculate_modelo_revision(
        work_unit.work_unit_id,
        actor="operator-A",
        casilla_inputs={**DEFAULT_130_BASELINE_INPUTS, M130_INCOME_CASILLA: Decimal("1000")},
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
        filing_repository=fr_repo,
        verification_repository=vr_repo,
        bucket_event_repository=bv_repo,
        clock=T2,
    )
    assert report.granted_verificado_completo is True
    filing = file_revision(
        revision.calculation_revision_id,
        revision=revision,
        work_unit=work_unit,
        actor="operator-A",
        work_unit_repository=wu_repo,
        calculation_repository=cr_repo,
        filing_repository=fr_repo,
        bucket_event_repository=bv_repo,
        clock=T3,
    )

    catalogue = bv_repo.load()
    filed_events = catalogue.for_bucket(
        work_unit.bucket_id,
        event_types=(BucketEventType.MODELO_FILED,),
    )
    assert len(filed_events) == 1
    event = filed_events[0]
    assert event.object_id == filing.filing_record_id
    assert event.payload["calculation_revision_id"] == revision.calculation_revision_id
    assert event.payload["modelo"] == work_unit.modelo
    # No prior filing was superseded — payload carries empty string.
    assert event.payload["supersedes_filing_record_id"] == ""


def test_file_supersession_emits_both_filed_and_superseded_events(repos: Repos) -> None:
    """A second filing supersedes the prior one. The bucket-event
    log carries one ``modelo.filed_superseded`` event for the prior
    record (object_id = prior filing record id) and one new
    ``modelo.filed`` event for the new record (with the prior id in
    the ``supersedes_filing_record_id`` payload key)."""

    wu_repo, cr_repo, fr_repo, vr_repo, bv_repo = repos
    work_unit = seed_work_unit(wu_repo)

    revision_one = calculate_modelo_revision(
        work_unit.work_unit_id,
        actor="operator-A",
        casilla_inputs={**DEFAULT_130_BASELINE_INPUTS, M130_INCOME_CASILLA: Decimal("1000")},
        binding_values=DEFAULT_130_BINDING_VALUES,
        work_unit_repository=wu_repo,
        calculation_repository=cr_repo,
        bucket_event_repository=bv_repo,
        clock=T1,
    )
    report_one = verify_revision(
        revision_one.calculation_revision_id,
        revision=revision_one,
        work_unit=work_unit,
        actor="operator-A",
        work_unit_repository=wu_repo,
        calculation_repository=cr_repo,
        filing_repository=fr_repo,
        verification_repository=vr_repo,
        bucket_event_repository=bv_repo,
        clock=T2,
    )
    assert report_one.granted_verificado_completo is True
    filing_one = file_revision(
        revision_one.calculation_revision_id,
        revision=revision_one,
        work_unit=work_unit,
        actor="operator-A",
        work_unit_repository=wu_repo,
        calculation_repository=cr_repo,
        filing_repository=fr_repo,
        bucket_event_repository=bv_repo,
        clock=T3,
    )

    revision_two = calculate_modelo_revision(
        work_unit.work_unit_id,
        actor="operator-A",
        casilla_inputs={
            **DEFAULT_130_BASELINE_INPUTS,
            M130_INCOME_CASILLA: Decimal("1200"),
            M130_EXPENSE_CASILLA: Decimal("100"),
        },
        binding_values=DEFAULT_130_BINDING_VALUES,
        work_unit_repository=wu_repo,
        calculation_repository=cr_repo,
        bucket_event_repository=bv_repo,
        clock=T4,
    )
    report_two = verify_revision(
        revision_two.calculation_revision_id,
        revision=revision_two,
        work_unit=work_unit,
        actor="operator-A",
        work_unit_repository=wu_repo,
        calculation_repository=cr_repo,
        filing_repository=fr_repo,
        verification_repository=vr_repo,
        bucket_event_repository=bv_repo,
        clock=T4,
    )
    assert report_two.granted_verificado_completo is True
    filing_two = file_revision(
        revision_two.calculation_revision_id,
        revision=revision_two,
        work_unit=work_unit,
        actor="operator-A",
        work_unit_repository=wu_repo,
        calculation_repository=cr_repo,
        filing_repository=fr_repo,
        bucket_event_repository=bv_repo,
        clock=T5,
    )

    catalogue = bv_repo.load()
    superseded_events = catalogue.for_object(
        object_type=BucketEventObjectType.FILING_RECORD,
        object_id=filing_one.filing_record_id,
    )
    types = tuple(e.event_type for e in superseded_events)
    assert BucketEventType.MODELO_FILED in types
    assert BucketEventType.MODELO_FILED_SUPERSEDED in types

    # The new filing.filed event references the prior record id.
    new_filed_events = catalogue.for_object(
        object_type=BucketEventObjectType.FILING_RECORD,
        object_id=filing_two.filing_record_id,
    )
    assert len(new_filed_events) == 1
    assert new_filed_events[0].event_type is BucketEventType.MODELO_FILED
    assert new_filed_events[0].payload["supersedes_filing_record_id"] == filing_one.filing_record_id

    # Whole calculation/file chain in chronological order for the bucket.
    # Work-unit creation is also persisted in this catalogue by the
    # shared runtime path.
    all_events = catalogue.for_bucket(work_unit.bucket_id)
    type_chain = tuple(
        e.event_type
        for e in all_events
        if e.event_type
        in {
            BucketEventType.MODELO_CALCULATION_CREATED,
            BucketEventType.MODELO_FILED,
            BucketEventType.MODELO_FILED_SUPERSEDED,
        }
    )
    assert type_chain == (
        BucketEventType.MODELO_CALCULATION_CREATED,
        BucketEventType.MODELO_FILED,
        BucketEventType.MODELO_CALCULATION_CREATED,
        BucketEventType.MODELO_FILED_SUPERSEDED,
        BucketEventType.MODELO_FILED,
    )

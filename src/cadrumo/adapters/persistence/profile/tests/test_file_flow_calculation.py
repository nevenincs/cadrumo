"""Modelo file-flow application tests split by workflow."""

from __future__ import annotations

from decimal import Decimal
from pathlib import Path

import pytest

from cadrumo.adapters.persistence.profile.tests.cross_period_seeding import seed_clean_cross_period_sources
from cadrumo.adapters.persistence.profile.tests.file_flow_test_support import (
    DEFAULT_130_BASELINE_INPUTS,
    DEFAULT_130_BINDING_VALUES,
    M130_EXPENSE_CASILLA,
    M130_INCOME_CASILLA,
    M130_NET_RESULT_CASILLA,
    T1,
    T2,
    T3,
    FileFlowRuntime,
    Repos,
    calculation_ports_for_test,
    seed_work_unit,
    verify_revision,
    workflow_gate,
)
from cadrumo.adapters.persistence.profile.tests.verification_repository_support import (
    build_test_certificate_secret_backend_factory,
)
from cadrumo.adapters.persistence.storage.operator_scope import build_operator_scope_ports
from cadrumo.application.modelo.calculation_actions import calculate_modelo_revision, list_calculation_revisions
from cadrumo.application.modelo.filing_actions import file_modelo_revision
from cadrumo.application.modelo.work_lifecycle import get_work_unit
from cadrumo.application.modelo.work_lifecycle_ports import WorkLifecyclePorts
from cadrumo.domain.buckets.event import BucketEventType
from cadrumo.domain.calculations.registry.authority import bundled_indexed_authority
from cadrumo.domain.modelos.calculation_revision import CalculationRevisionState
from cadrumo.domain.modelos.repository import upsert_work_unit
from cadrumo.entrypoints.adapter_composition import build_filing_action_ports
from cadrumo.tests.write_unit_recorder import WriteUnitRecorder

_OPERATOR_SCOPE_PORTS = build_operator_scope_ports()

pytestmark = [pytest.mark.unit, pytest.mark.hex_application, pytest.mark.usefixtures("authority_operation")]


def test_two_calculates_under_one_work_unit_produce_two_revisions(repos: Repos) -> None:
    """The toilet-break scenario. Operator calculates, walks away,
    comes back, calculates again with different inputs. Two
    ``CalculationRevision`` records exist; the work unit's
    ``current_calculation_revision_id`` advances to the second."""

    wu_repo, cr_repo, _, _, bv_repo = repos
    work_unit = seed_work_unit(wu_repo)
    with calculation_ports_for_test(
        bucket_id=work_unit.bucket_id,
        work_unit_repository=wu_repo,
        calculation_repository=cr_repo,
        bucket_event_repository=bv_repo,
    ) as _calculation_ports_60:
        first = calculate_modelo_revision(
            work_unit.work_unit_id,
            casilla_inputs={M130_INCOME_CASILLA: Decimal("1000")},
            binding_values=DEFAULT_130_BINDING_VALUES,
            ports=_calculation_ports_60,
            clock=T1,
        )
    with calculation_ports_for_test(
        bucket_id=work_unit.bucket_id,
        work_unit_repository=wu_repo,
        calculation_repository=cr_repo,
        bucket_event_repository=bv_repo,
    ) as _calculation_ports_70:
        second = calculate_modelo_revision(
            work_unit.work_unit_id,
            casilla_inputs={M130_INCOME_CASILLA: Decimal("2000"), M130_EXPENSE_CASILLA: Decimal("500")},
            binding_values=DEFAULT_130_BINDING_VALUES,
            ports=_calculation_ports_70,
            clock=T2,
        )

    assert first.calculation_revision_id != second.calculation_revision_id
    with calculation_ports_for_test(
        bucket_id=work_unit.bucket_id,
        calculation_repository=cr_repo,
    ) as _calculation_ports_80:
        revisions = list_calculation_revisions(
            work_unit_id=work_unit.work_unit_id,
            ports=_calculation_ports_80,
        )
    assert len(revisions) == 2
    assert {r.calculation_revision_id for r in revisions} == {
        first.calculation_revision_id,
        second.calculation_revision_id,
    }
    assert all(r.state is CalculationRevisionState.BORRADOR for r in revisions)

    # Current pointer follows most-recent calculate.
    refreshed_work_unit = get_work_unit(
        work_unit.work_unit_id,
        ports=WorkLifecyclePorts(work_unit_repository=wu_repo, bucket_event_repository=bv_repo),
    )
    assert refreshed_work_unit.current_calculation_revision_id == second.calculation_revision_id
    assert refreshed_work_unit.filed_calculation_revision_id is None
    assert refreshed_work_unit.current_filing_record_id is None


def test_calculate_is_idempotent_on_identical_inputs(repos: Repos) -> None:
    """Re-running calculate with identical inputs / outputs returns
    the existing revision (content-addressed id collides) without
    creating a duplicate."""

    wu_repo, cr_repo, _, _, bv_repo = repos
    work_unit = seed_work_unit(wu_repo)
    with calculation_ports_for_test(
        bucket_id=work_unit.bucket_id,
        work_unit_repository=wu_repo,
        calculation_repository=cr_repo,
        bucket_event_repository=bv_repo,
    ) as _calculation_ports_111:
        first = calculate_modelo_revision(
            work_unit.work_unit_id,
            casilla_inputs={M130_INCOME_CASILLA: Decimal("1000")},
            binding_values=DEFAULT_130_BINDING_VALUES,
            ports=_calculation_ports_111,
            clock=T1,
        )
    with calculation_ports_for_test(
        bucket_id=work_unit.bucket_id,
        work_unit_repository=wu_repo,
        calculation_repository=cr_repo,
        bucket_event_repository=bv_repo,
    ) as _calculation_ports_120:
        second = calculate_modelo_revision(
            work_unit.work_unit_id,
            casilla_inputs={M130_INCOME_CASILLA: Decimal("1000")},
            binding_values=DEFAULT_130_BINDING_VALUES,
            ports=_calculation_ports_120,
            clock=T2,
        )
    assert first.calculation_revision_id == second.calculation_revision_id
    with calculation_ports_for_test(
        bucket_id=work_unit.bucket_id,
        calculation_repository=cr_repo,
    ) as _calculation_ports_128:
        revisions = list_calculation_revisions(
            work_unit_id=work_unit.work_unit_id,
            ports=_calculation_ports_128,
        )
    assert len(revisions) == 1


def test_duplicate_draft_calculation_reuse_advances_current_pointer(repos: Repos) -> None:
    """Reusing an existing draft revision still restores it as current."""

    wu_repo, cr_repo, _, _, bv_repo = repos
    work_unit = seed_work_unit(wu_repo)
    with calculation_ports_for_test(
        bucket_id=work_unit.bucket_id,
        work_unit_repository=wu_repo,
        calculation_repository=cr_repo,
        bucket_event_repository=bv_repo,
    ) as _calculation_ports_143:
        first = calculate_modelo_revision(
            work_unit.work_unit_id,
            casilla_inputs={M130_INCOME_CASILLA: Decimal("1000")},
            binding_values=DEFAULT_130_BINDING_VALUES,
            ports=_calculation_ports_143,
            clock=T1,
        )
    stale_work_unit = get_work_unit(
        work_unit.work_unit_id,
        ports=WorkLifecyclePorts(work_unit_repository=wu_repo, bucket_event_repository=bv_repo),
    ).model_copy(
        update={"current_calculation_revision_id": None},
    )
    wu_repo.save(upsert_work_unit(wu_repo.load(), stale_work_unit))
    with calculation_ports_for_test(
        bucket_id=work_unit.bucket_id,
        work_unit_repository=wu_repo,
        calculation_repository=cr_repo,
        bucket_event_repository=bv_repo,
    ) as _calculation_ports_160:
        duplicate = calculate_modelo_revision(
            work_unit.work_unit_id,
            casilla_inputs={M130_INCOME_CASILLA: Decimal("1000")},
            binding_values=DEFAULT_130_BINDING_VALUES,
            ports=_calculation_ports_160,
            clock=T2,
        )

    assert duplicate.calculation_revision_id == first.calculation_revision_id
    refreshed = get_work_unit(
        work_unit.work_unit_id,
        ports=WorkLifecyclePorts(work_unit_repository=wu_repo, bucket_event_repository=bv_repo),
    )
    assert refreshed.current_calculation_revision_id == first.calculation_revision_id
    assert refreshed.filed_calculation_revision_id is None
    assert refreshed.current_filing_record_id is None


def test_calculate_refused_on_discarded_work_unit(repos: Repos) -> None:
    """A discarded work unit refuses further calculation. The
    operator must create a fresh work unit to continue."""

    from cadrumo.application.modelo.action_errors import WorkUnitMutationRefusedError
    from cadrumo.application.modelo.work_lifecycle import discard_work_unit

    wu_repo, cr_repo, _, _, bv_repo = repos
    work_unit = seed_work_unit(wu_repo)
    discard_work_unit(
        work_unit.work_unit_id,
        actor="operator-A",
        ports=WorkLifecyclePorts(work_unit_repository=wu_repo, bucket_event_repository=bv_repo),
        clock=T1,
    )
    with (
        pytest.raises(WorkUnitMutationRefusedError),
        calculation_ports_for_test(
            bucket_id=work_unit.bucket_id,
            work_unit_repository=wu_repo,
            calculation_repository=cr_repo,
            bucket_event_repository=bv_repo,
        ) as _calculation_ports_196,
    ):
        calculate_modelo_revision(
            work_unit.work_unit_id,
            casilla_inputs={M130_INCOME_CASILLA: Decimal("1000")},
            binding_values=DEFAULT_130_BINDING_VALUES,
            ports=_calculation_ports_196,
            clock=T2,
        )


def test_discard_emits_modelo_work_unit_discarded_event(repos: Repos) -> None:
    """``discard_work_unit`` emits a ``modelo.work_unit.discarded``
    bucket event with actor + reason payload."""

    from cadrumo.application.modelo.work_lifecycle import discard_work_unit
    from cadrumo.domain.buckets.event import BucketEventObjectType, BucketEventType

    wu_repo, _, _, _, bv_repo = repos
    work_unit = seed_work_unit(wu_repo)
    discarded = discard_work_unit(
        work_unit.work_unit_id,
        actor="operator-A",
        reason="superseded by new work unit",
        ports=WorkLifecyclePorts(work_unit_repository=wu_repo, bucket_event_repository=bv_repo),
        clock=T1,
    )
    history = bv_repo.load().for_bucket(discarded.bucket_id)
    discard_events = [event for event in history if event.event_type is BucketEventType.MODELO_WORK_UNIT_DISCARDED]
    assert len(discard_events) == 1
    event = discard_events[0]
    assert event.object_type is BucketEventObjectType.WORK_UNIT
    assert event.object_id == discarded.work_unit_id
    assert event.actor == "operator-A"
    assert event.payload["reason"] == "superseded by new work unit"


def test_calculate_runs_registry_formula_engine(repos: Repos) -> None:
    """``calculate_modelo_revision`` runs the registry's formula engine
    over the operator-supplied inputs and persists the FULL computed
    casilla map. Modelo 130 1T 2026 declares 9 manual casillas plus
    10 computed formulas; given inputs for casilla 01 and 02, the
    engine derives casilla 03 = 01 - 02 (subtract).

    The persisted revision carries the operator inputs in
    ``input_values_by_casilla_id`` (canonical decimal strings) and the full
    engine output, inputs plus formula targets, in ``casilla_values``.
    The bucket event payload reports the formula count from the
    engine result."""

    wu_repo, cr_repo, _, _, bv_repo = repos
    work_unit = seed_work_unit(wu_repo)
    casilla_inputs = {M130_INCOME_CASILLA: Decimal("10000"), M130_EXPENSE_CASILLA: Decimal("3000")}
    with calculation_ports_for_test(
        bucket_id=work_unit.bucket_id,
        work_unit_repository=wu_repo,
        calculation_repository=cr_repo,
        bucket_event_repository=bv_repo,
    ) as _calculation_ports_251:
        revision = calculate_modelo_revision(
            work_unit.work_unit_id,
            actor="operator-A",
            casilla_inputs=casilla_inputs,
            binding_values=DEFAULT_130_BINDING_VALUES,
            ports=_calculation_ports_251,
            clock=T1,
        )

    # Operator inputs surface in ``input_values_by_casilla_id``.
    assert revision.input_values_by_casilla_id[M130_INCOME_CASILLA] == "10000"
    assert revision.input_values_by_casilla_id[M130_EXPENSE_CASILLA] == "3000"
    assert M130_NET_RESULT_CASILLA not in revision.input_values_by_casilla_id  # 03 is a formula target, not an input

    # Calculation output contains BOTH the operator inputs AND every
    # formula target; domain-level registry tests own arithmetic parity.
    assert revision.casilla_values[M130_INCOME_CASILLA] == casilla_inputs[M130_INCOME_CASILLA]
    assert revision.casilla_values[M130_EXPENSE_CASILLA] == casilla_inputs[M130_EXPENSE_CASILLA]
    assert M130_NET_RESULT_CASILLA in revision.casilla_values
    assert revision.casilla_values[M130_NET_RESULT_CASILLA] < revision.casilla_values[M130_INCOME_CASILLA]
    # Every casilla declared in the 130 1T 2026 revision is now in
    # the output — 9 manual + 10 formula targets = 19 entries.
    assert len(revision.casilla_values) >= 19

    # Bucket-event payload reports the formula count from the engine.
    catalogue = bv_repo.load()
    created_events = catalogue.for_bucket(
        work_unit.bucket_id,
        event_types=(BucketEventType.MODELO_CALCULATION_CREATED,),
    )
    assert len(created_events) == 1
    assert int(created_events[0].payload["formula_count"]) >= 1
    assert int(created_events[0].payload["casilla_count"]) >= 19


def test_calculate_works_when_cwd_is_not_the_repo_root(
    repos: Repos,
    tmp_path: Path,
) -> None:
    """The registry root resolves via ``PROJECT_ROOT`` from
    ``cadrumo.core.config``, not via a CWD-relative ``"registry/aeat"``
    string. Running the action from any other directory must still
    work — production deploys, background daemons, and wheel
    installs all run from non-repo CWDs.

    Uses ``contextlib.chdir`` (stdlib, live-tests-friendly) through a
    scoped context manager rather than pytest fixture state mutation.
    """

    import contextlib
    import os as _os

    alien_cwd = tmp_path / "alien-working-dir"
    alien_cwd.mkdir()

    with contextlib.chdir(alien_cwd):
        assert _os.getcwd() == str(alien_cwd)

        wu_repo, cr_repo, _, _, bv_repo = repos
        work_unit = seed_work_unit(wu_repo)
        with calculation_ports_for_test(
            bucket_id=work_unit.bucket_id,
            work_unit_repository=wu_repo,
            calculation_repository=cr_repo,
            bucket_event_repository=bv_repo,
        ) as _calculation_ports_313:
            revision = calculate_modelo_revision(
                work_unit.work_unit_id,
                actor="operator-A",
                casilla_inputs={M130_INCOME_CASILLA: Decimal("10000"), M130_EXPENSE_CASILLA: Decimal("3000")},
                binding_values=DEFAULT_130_BINDING_VALUES,
                ports=_calculation_ports_313,
                clock=T1,
            )

    # Sanity: engine ran (formula casilla 03 computed = 01 - 02).
    assert revision.casilla_values[M130_NET_RESULT_CASILLA] == Decimal("7000.00")


def test_work_unit_creation_refuses_unresolvable_registry_snapshot(repos: Repos) -> None:
    """An unsupported filing coordinate is rejected before calculation state exists."""

    from cadrumo.domain.calculations.registry.errors import FilingYearOutsideSupportEnvelopeError

    wu_repo, _, _, _, _ = repos
    # Modelo 130 at year 2010 sits below the support floor, so the envelope
    # turns the request away before the corpus is consulted -- which is also
    # true of it: the earliest revision is ``2019-y-siguientes``. The refusal
    # names the gate that actually fired, and reports the second fact too.
    with pytest.raises(FilingYearOutsideSupportEnvelopeError):
        seed_work_unit(wu_repo, filing_year=2010)


def test_draft_calculation_commits_revision_pointer_and_event_together(
    file_flow_runtime: FileFlowRuntime,
) -> None:
    """The draft revision, current pointer, and its event share one transaction.

    Emitted through a separate write, an event-storage failure left the draft
    durable and pointed at as current while history stayed unchanged, with no
    recovery marker or retry contract naming the missing entry.
    """
    wu_repo, cr_repo, _, _, bv_repo = file_flow_runtime.repos
    work_unit = seed_work_unit(wu_repo)
    recorder = WriteUnitRecorder(file_flow_runtime.engine)

    with (
        recorder.recording(),
        calculation_ports_for_test(
            bucket_id=work_unit.bucket_id,
            work_unit_repository=wu_repo,
            calculation_repository=cr_repo,
            bucket_event_repository=bv_repo,
        ) as _calculation_ports_353,
    ):
        calculate_modelo_revision(
            work_unit.work_unit_id,
            casilla_inputs={M130_INCOME_CASILLA: Decimal("1000")},
            binding_values=DEFAULT_130_BINDING_VALUES,
            ports=_calculation_ports_353,
            clock=T1,
        )

    assert recorder.commits_between_writes() == 0


def test_split_draft_write_shape_commits_between_catalogues(
    file_flow_runtime: FileFlowRuntime,
) -> None:
    """Anti-tautology: the recorder does report a seam when one exists."""
    wu_repo, cr_repo, _, _, bv_repo = file_flow_runtime.repos
    work_unit = seed_work_unit(wu_repo)
    with calculation_ports_for_test(
        bucket_id=work_unit.bucket_id,
        work_unit_repository=wu_repo,
        calculation_repository=cr_repo,
        bucket_event_repository=bv_repo,
    ) as _calculation_ports_372:
        calculate_modelo_revision(
            work_unit.work_unit_id,
            casilla_inputs={M130_INCOME_CASILLA: Decimal("1000")},
            binding_values=DEFAULT_130_BINDING_VALUES,
            ports=_calculation_ports_372,
            clock=T1,
        )
    revisions = cr_repo.load()
    work_units = wu_repo.load()
    events = bv_repo.load()
    recorder = WriteUnitRecorder(file_flow_runtime.engine)

    with recorder.recording():
        cr_repo.save(revisions)
        wu_repo.save(work_units)
        bv_repo.save(events)

    assert recorder.commits_between_writes() >= 1


def test_draft_calculation_records_its_created_event(
    file_flow_runtime: FileFlowRuntime,
) -> None:
    """Parity: co-committing the event does not change what a calculate records."""
    wu_repo, cr_repo, _, _, bv_repo = file_flow_runtime.repos
    work_unit = seed_work_unit(wu_repo)
    with calculation_ports_for_test(
        bucket_id=work_unit.bucket_id,
        work_unit_repository=wu_repo,
        calculation_repository=cr_repo,
        bucket_event_repository=bv_repo,
    ) as _calculation_ports_401:
        revision = calculate_modelo_revision(
            work_unit.work_unit_id,
            casilla_inputs={M130_INCOME_CASILLA: Decimal("1000")},
            binding_values=DEFAULT_130_BINDING_VALUES,
            ports=_calculation_ports_401,
            clock=T1,
        )

    assert revision.state is CalculationRevisionState.BORRADOR
    refreshed = get_work_unit(
        work_unit.work_unit_id,
        ports=WorkLifecyclePorts(work_unit_repository=wu_repo, bucket_event_repository=bv_repo),
    )
    assert refreshed.current_calculation_revision_id == revision.calculation_revision_id
    created = [
        event
        for event in bv_repo.load().events.values()
        if event.event_type is BucketEventType.MODELO_CALCULATION_CREATED
    ]
    assert len(created) == 1
    assert created[0].object_id == revision.calculation_revision_id


def test_local_filing_commits_state_pointer_and_filed_event_together(
    file_flow_runtime: FileFlowRuntime,
) -> None:
    """The filed revision, filing record, pointer, and MODELO_FILED share one transaction.

    A failure at event storage previously left a VIGENTE filing and an advanced
    filed pointer with no matching history event and no durable
    incomplete-filing state.

    The filing flow has exactly ONE deliberate second boundary: the cross-period
    carry projection runs after the catalogue writes commit, by design, so a
    failed filing never leaves a carry row behind. The assertion is therefore on
    the transaction SHAPE -- two groups, the filing state and its events sharing
    the first -- rather than on a bare "no commit between writes", which the
    intentional projection boundary would fail even when the seam is closed.
    """
    wu_repo, cr_repo, fr_repo, vr_repo, bv_repo = file_flow_runtime.repos
    work_unit = seed_work_unit(wu_repo)
    with calculation_ports_for_test(
        bucket_id=work_unit.bucket_id,
        work_unit_repository=wu_repo,
        calculation_repository=cr_repo,
        bucket_event_repository=bv_repo,
    ) as _calculation_ports_444:
        revision = calculate_modelo_revision(
            work_unit.work_unit_id,
            casilla_inputs={**DEFAULT_130_BASELINE_INPUTS, M130_INCOME_CASILLA: Decimal("1000")},
            binding_values=DEFAULT_130_BINDING_VALUES,
            ports=_calculation_ports_444,
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
    # Seed the cross-period sources OUTSIDE the recorded window: they are test
    # setup, and their writes would otherwise dominate the observed shape.
    with bundled_indexed_authority().operation() as seed_operation:
        seed_clean_cross_period_sources(
            work_unit,
            work_unit_repository=wu_repo,
            calculation_repository=cr_repo,
            filing_repository=fr_repo,
            bucket_event_repository=bv_repo,
            operation=seed_operation,
        )
    recorder = WriteUnitRecorder(file_flow_runtime.engine)

    with recorder.recording(), bundled_indexed_authority().operation() as operation:
        gate = workflow_gate(revision=revision, work_unit=work_unit, clock=T3, operation=operation)
        file_modelo_revision(
            revision.calculation_revision_id,
            actor="operator-A",
            workflow_profile=gate.profile,
            certificate_secret_backend_factory=build_test_certificate_secret_backend_factory(),
            ports=build_filing_action_ports(bucket_id=work_unit.bucket_id),
            workflow_engine=gate.engine,
            clock=T3,
            operator_scope_ports=_OPERATOR_SCOPE_PORTS,
            operation=operation,
        )

    # One group holds the filing catalogue, the filed revision, the advanced
    # WorkUnit pointer, and the MODELO_FILED event together. Written as
    # independent saves the pointer and the event each formed their own
    # single-write group and no group reached four, so the bound discriminates
    # the closed seam from the open one without pinning the exact write count of
    # the surrounding workflow and carry-projection transactions.
    groups = recorder.write_groups()
    assert max(groups) >= 4, groups

    filed_events = [
        event for event in bv_repo.load().events.values() if event.event_type is BucketEventType.MODELO_FILED
    ]
    assert len(filed_events) == 1
    refreshed = get_work_unit(
        work_unit.work_unit_id,
        ports=WorkLifecyclePorts(work_unit_repository=wu_repo, bucket_event_repository=bv_repo),
    )
    assert refreshed.filed_calculation_revision_id == revision.calculation_revision_id

    # Negative control for the bound above: the same four catalogues persisted
    # through independent saves -- the shape the filing path replaced -- put each
    # catalogue in its own transaction, so no group can reach four. Without this
    # the `>= 4` bound could be a threshold every shape happens to clear.
    split_recorder = WriteUnitRecorder(file_flow_runtime.engine)
    filings, revisions, work_units, events = fr_repo.load(), cr_repo.load(), wu_repo.load(), bv_repo.load()
    with split_recorder.recording():
        fr_repo.save(filings)
        cr_repo.save(revisions)
        wu_repo.save(work_units)
        bv_repo.save(events)

    split_groups = split_recorder.write_groups()
    assert len(split_groups) == 4, split_groups
    assert max(split_groups) < 4, split_groups

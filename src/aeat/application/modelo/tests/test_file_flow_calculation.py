"""Modelo file-flow application tests split by workflow."""

from __future__ import annotations

from pathlib import Path

import pytest

from ._file_flow_support import (
    DEFAULT_130_BINDING_VALUES,
    M130_EXPENSE_CASILLA,
    M130_INCOME_CASILLA,
    M130_NET_RESULT_CASILLA,
    T1,
    T2,
    BucketEventType,
    CalculationRevisionState,
    Decimal,
    Repos,
    calculate_modelo_revision,
    get_work_unit,
    list_calculation_revisions,
    seed_work_unit,
    upsert_work_unit,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]


def test_two_calculates_under_one_work_unit_produce_two_revisions(repos: Repos) -> None:
    """The toilet-break scenario. Operator calculates, walks away,
    comes back, calculates again with different inputs. Two
    ``CalculationRevision`` records exist; the work unit's
    ``current_calculation_revision_id`` advances to the second."""

    wu_repo, cr_repo, _, _, bv_repo = repos
    work_unit = seed_work_unit(wu_repo)

    first = calculate_modelo_revision(
        work_unit.work_unit_id,
        casilla_inputs={M130_INCOME_CASILLA: Decimal("1000")},
        binding_values=DEFAULT_130_BINDING_VALUES,
        work_unit_repository=wu_repo,
        calculation_repository=cr_repo,
        bucket_event_repository=bv_repo,
        clock=T1,
    )

    second = calculate_modelo_revision(
        work_unit.work_unit_id,
        casilla_inputs={M130_INCOME_CASILLA: Decimal("2000"), M130_EXPENSE_CASILLA: Decimal("500")},
        binding_values=DEFAULT_130_BINDING_VALUES,
        work_unit_repository=wu_repo,
        calculation_repository=cr_repo,
        bucket_event_repository=bv_repo,
        clock=T2,
    )

    assert first.calculation_revision_id != second.calculation_revision_id

    revisions = list_calculation_revisions(
        work_unit_id=work_unit.work_unit_id,
        calculation_repository=cr_repo,
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
        repository=wu_repo,
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

    first = calculate_modelo_revision(
        work_unit.work_unit_id,
        casilla_inputs={M130_INCOME_CASILLA: Decimal("1000")},
        binding_values=DEFAULT_130_BINDING_VALUES,
        work_unit_repository=wu_repo,
        calculation_repository=cr_repo,
        bucket_event_repository=bv_repo,
        clock=T1,
    )
    second = calculate_modelo_revision(
        work_unit.work_unit_id,
        casilla_inputs={M130_INCOME_CASILLA: Decimal("1000")},
        binding_values=DEFAULT_130_BINDING_VALUES,
        work_unit_repository=wu_repo,
        calculation_repository=cr_repo,
        bucket_event_repository=bv_repo,
        clock=T2,
    )
    assert first.calculation_revision_id == second.calculation_revision_id
    revisions = list_calculation_revisions(
        work_unit_id=work_unit.work_unit_id,
        calculation_repository=cr_repo,
    )
    assert len(revisions) == 1


def test_duplicate_draft_calculation_reuse_advances_current_pointer(repos: Repos) -> None:
    """Reusing an existing draft revision still restores it as current."""

    wu_repo, cr_repo, _, _, bv_repo = repos
    work_unit = seed_work_unit(wu_repo)

    first = calculate_modelo_revision(
        work_unit.work_unit_id,
        casilla_inputs={M130_INCOME_CASILLA: Decimal("1000")},
        binding_values=DEFAULT_130_BINDING_VALUES,
        work_unit_repository=wu_repo,
        calculation_repository=cr_repo,
        bucket_event_repository=bv_repo,
        clock=T1,
    )
    stale_work_unit = get_work_unit(work_unit.work_unit_id, repository=wu_repo).model_copy(
        update={"current_calculation_revision_id": None},
    )
    wu_repo.save(upsert_work_unit(wu_repo.load(), stale_work_unit))

    duplicate = calculate_modelo_revision(
        work_unit.work_unit_id,
        casilla_inputs={M130_INCOME_CASILLA: Decimal("1000")},
        binding_values=DEFAULT_130_BINDING_VALUES,
        work_unit_repository=wu_repo,
        calculation_repository=cr_repo,
        bucket_event_repository=bv_repo,
        clock=T2,
    )

    assert duplicate.calculation_revision_id == first.calculation_revision_id
    refreshed = get_work_unit(work_unit.work_unit_id, repository=wu_repo)
    assert refreshed.current_calculation_revision_id == first.calculation_revision_id
    assert refreshed.filed_calculation_revision_id is None
    assert refreshed.current_filing_record_id is None


def test_calculate_refused_on_discarded_work_unit(repos: Repos) -> None:
    """A discarded work unit refuses further calculation. The
    operator must create a fresh work unit to continue."""

    from .. import (
        WorkUnitMutationRefusedError,
        discard_work_unit,
    )

    wu_repo, cr_repo, _, _, bv_repo = repos
    work_unit = seed_work_unit(wu_repo)
    discard_work_unit(
        work_unit.work_unit_id,
        actor="operator-A",
        repository=wu_repo,
        bucket_event_repository=bv_repo,
        clock=T1,
    )
    with pytest.raises(WorkUnitMutationRefusedError):
        calculate_modelo_revision(
            work_unit.work_unit_id,
            casilla_inputs={M130_INCOME_CASILLA: Decimal("1000")},
            binding_values=DEFAULT_130_BINDING_VALUES,
            work_unit_repository=wu_repo,
            calculation_repository=cr_repo,
            bucket_event_repository=bv_repo,
            clock=T2,
        )


def test_discard_emits_modelo_work_unit_discarded_event(repos: Repos) -> None:
    """``discard_work_unit`` emits a ``modelo.work_unit.discarded``
    bucket event with actor + reason payload."""

    from ....domain.buckets import BucketEventObjectType, BucketEventType
    from .. import discard_work_unit

    wu_repo, _, _, _, bv_repo = repos
    work_unit = seed_work_unit(wu_repo)
    discarded = discard_work_unit(
        work_unit.work_unit_id,
        actor="operator-A",
        reason="superseded by new work unit",
        repository=wu_repo,
        bucket_event_repository=bv_repo,
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

    revision = calculate_modelo_revision(
        work_unit.work_unit_id,
        actor="operator-A",
        casilla_inputs=casilla_inputs,
        binding_values=DEFAULT_130_BINDING_VALUES,
        work_unit_repository=wu_repo,
        calculation_repository=cr_repo,
        bucket_event_repository=bv_repo,
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
    ``aeat.core.config``, not via a CWD-relative ``"registry/aeat"``
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
        revision = calculate_modelo_revision(
            work_unit.work_unit_id,
            actor="operator-A",
            casilla_inputs={M130_INCOME_CASILLA: Decimal("10000"), M130_EXPENSE_CASILLA: Decimal("3000")},
            binding_values=DEFAULT_130_BINDING_VALUES,
            work_unit_repository=wu_repo,
            calculation_repository=cr_repo,
            bucket_event_repository=bv_repo,
            clock=T1,
        )

    # Sanity: engine ran (formula casilla 03 computed = 01 - 02).
    assert revision.casilla_values[M130_NET_RESULT_CASILLA] == Decimal("7000.00")


def test_calculate_refuses_when_registry_snapshot_unresolvable(repos: Repos) -> None:
    """``calculate_modelo_revision`` runs the formula engine, so it
    cannot operate on a work unit whose (modelo, year, period) tuple
    does not resolve a registry snapshot. The action raises
    ``CalculationRegistryUnavailableError`` rather than persisting a
    revision that bypasses the engine."""

    from .. import CalculationRegistryUnavailableError

    wu_repo, cr_repo, _, _, bv_repo = repos
    # Modelo 130 at year 2010 predates the registry's earliest
    # revision (``2019-y-siguientes``), so the snapshot lookup fails.
    work_unit = seed_work_unit(wu_repo, filing_year=2010)

    with pytest.raises(CalculationRegistryUnavailableError) as exc_info:
        calculate_modelo_revision(
            work_unit.work_unit_id,
            actor="operator-A",
            casilla_inputs={M130_INCOME_CASILLA: Decimal("1000")},
            binding_values=DEFAULT_130_BINDING_VALUES,
            work_unit_repository=wu_repo,
            calculation_repository=cr_repo,
            bucket_event_repository=bv_repo,
            clock=T1,
        )
    assert exc_info.value.translated_message == "application.modelo.errors.calculation_registry_snapshot_unresolved"

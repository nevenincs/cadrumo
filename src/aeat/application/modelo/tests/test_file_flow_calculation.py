"""Modelo file-flow application tests split by workflow."""

from __future__ import annotations

from pathlib import Path

import pytest

from ._file_flow_support import (
    _DEFAULT_130_BINDING_VALUES,
    _T0,
    _T1,
    _T2,
    BucketEventType,
    CalculationRevisionState,
    Decimal,
    _Repos,
    _seed_work_unit,
    calculate_modelo_revision,
    create_work_unit,
    get_work_unit,
    list_calculation_revisions,
    upsert_work_unit,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]


def test_two_calculates_under_one_work_unit_produce_two_revisions(repos: _Repos) -> None:
    """The toilet-break scenario. Operator calculates, walks away,
    comes back, calculates again with different inputs. Two
    ``CalculationRevision`` records exist; the work unit's
    ``current_calculation_revision_id`` advances to the second."""

    wu_repo, cr_repo, _, _, bv_repo = repos
    work_unit = _seed_work_unit(wu_repo)

    first = calculate_modelo_revision(
        work_unit.work_unit_id,
        casilla_inputs={"01": Decimal("1000")},
        binding_values=_DEFAULT_130_BINDING_VALUES,
        work_unit_repository=wu_repo,
        calculation_repository=cr_repo,
        bucket_event_repository=bv_repo,
        clock=_T1,
    )

    second = calculate_modelo_revision(
        work_unit.work_unit_id,
        casilla_inputs={"01": Decimal("2000"), "02": Decimal("500")},
        binding_values=_DEFAULT_130_BINDING_VALUES,
        work_unit_repository=wu_repo,
        calculation_repository=cr_repo,
        bucket_event_repository=bv_repo,
        clock=_T2,
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


def test_calculate_is_idempotent_on_identical_inputs(repos: _Repos) -> None:
    """Re-running calculate with identical inputs / outputs returns
    the existing revision (content-addressed id collides) without
    creating a duplicate."""

    wu_repo, cr_repo, _, _, bv_repo = repos
    work_unit = _seed_work_unit(wu_repo)

    first = calculate_modelo_revision(
        work_unit.work_unit_id,
        casilla_inputs={"01": Decimal("1000")},
        binding_values=_DEFAULT_130_BINDING_VALUES,
        work_unit_repository=wu_repo,
        calculation_repository=cr_repo,
        bucket_event_repository=bv_repo,
        clock=_T1,
    )
    second = calculate_modelo_revision(
        work_unit.work_unit_id,
        casilla_inputs={"01": Decimal("1000")},
        binding_values=_DEFAULT_130_BINDING_VALUES,
        work_unit_repository=wu_repo,
        calculation_repository=cr_repo,
        bucket_event_repository=bv_repo,
        clock=_T2,
    )
    assert first.calculation_revision_id == second.calculation_revision_id
    revisions = list_calculation_revisions(
        work_unit_id=work_unit.work_unit_id,
        calculation_repository=cr_repo,
    )
    assert len(revisions) == 1


def test_duplicate_draft_calculation_reuse_advances_current_pointer(repos: _Repos) -> None:
    """Reusing an existing draft revision still restores it as current."""

    wu_repo, cr_repo, _, _, bv_repo = repos
    work_unit = _seed_work_unit(wu_repo)

    first = calculate_modelo_revision(
        work_unit.work_unit_id,
        casilla_inputs={"01": Decimal("1000")},
        binding_values=_DEFAULT_130_BINDING_VALUES,
        work_unit_repository=wu_repo,
        calculation_repository=cr_repo,
        bucket_event_repository=bv_repo,
        clock=_T1,
    )
    stale_work_unit = get_work_unit(work_unit.work_unit_id, repository=wu_repo).model_copy(
        update={"current_calculation_revision_id": None},
    )
    wu_repo.save(upsert_work_unit(wu_repo.load(), stale_work_unit))

    duplicate = calculate_modelo_revision(
        work_unit.work_unit_id,
        casilla_inputs={"01": Decimal("1000")},
        binding_values=_DEFAULT_130_BINDING_VALUES,
        work_unit_repository=wu_repo,
        calculation_repository=cr_repo,
        bucket_event_repository=bv_repo,
        clock=_T2,
    )

    assert duplicate.calculation_revision_id == first.calculation_revision_id
    refreshed = get_work_unit(work_unit.work_unit_id, repository=wu_repo)
    assert refreshed.current_calculation_revision_id == first.calculation_revision_id
    assert refreshed.filed_calculation_revision_id is None
    assert refreshed.current_filing_record_id is None


def test_calculate_refused_on_discarded_work_unit(repos: _Repos) -> None:
    """A discarded work unit refuses further calculation. The
    operator must create a fresh work unit to continue."""

    from .. import (
        WorkUnitMutationRefusedError,
        discard_work_unit,
    )

    wu_repo, cr_repo, _, _, bv_repo = repos
    work_unit = _seed_work_unit(wu_repo)
    discard_work_unit(
        work_unit.work_unit_id,
        actor="operator-A",
        repository=wu_repo,
        bucket_event_repository=bv_repo,
        clock=_T1,
    )
    with pytest.raises(WorkUnitMutationRefusedError):
        calculate_modelo_revision(
            work_unit.work_unit_id,
            casilla_inputs={"01": Decimal("1000")},
            binding_values=_DEFAULT_130_BINDING_VALUES,
            work_unit_repository=wu_repo,
            calculation_repository=cr_repo,
            bucket_event_repository=bv_repo,
            clock=_T2,
        )


def test_discard_emits_modelo_work_unit_discarded_event(repos: _Repos) -> None:
    """``discard_work_unit`` emits a ``modelo.work_unit.discarded``
    bucket event with actor + reason payload."""

    from ....domain.buckets._event import BucketEventObjectType, BucketEventType
    from .. import discard_work_unit

    wu_repo, _, _, _, bv_repo = repos
    work_unit = _seed_work_unit(wu_repo)
    discarded = discard_work_unit(
        work_unit.work_unit_id,
        actor="operator-A",
        reason="superseded by new work unit",
        repository=wu_repo,
        bucket_event_repository=bv_repo,
        clock=_T1,
    )
    history = bv_repo.load().for_bucket(discarded.bucket_id)
    discard_events = [event for event in history if event.event_type is BucketEventType.MODELO_WORK_UNIT_DISCARDED]
    assert len(discard_events) == 1
    event = discard_events[0]
    assert event.object_type is BucketEventObjectType.WORK_UNIT
    assert event.object_id == discarded.work_unit_id
    assert event.actor == "operator-A"
    assert event.payload["reason"] == "superseded by new work unit"


def test_calculate_runs_registry_formula_engine(repos: _Repos) -> None:
    """``calculate_modelo_revision`` runs the registry's formula engine
    over the operator-supplied inputs and persists the FULL computed
    casilla map. Modelo 130 1T 2026 declares 9 manual casillas plus
    10 computed formulas; given inputs for casilla 01 and 02, the
    engine derives casilla 03 = 01 - 02 (subtract).

    The persisted revision carries the operator inputs in
    ``inputs_snapshot`` (canonical decimal strings) and the full
    engine output, inputs plus formula targets, in ``casilla_values``.
    The bucket event payload reports the formula count from the
    engine result."""

    wu_repo, cr_repo, _, _, bv_repo = repos
    work_unit = _seed_work_unit(wu_repo)
    casilla_inputs = {"01": Decimal("10000"), "02": Decimal("3000")}

    revision = calculate_modelo_revision(
        work_unit.work_unit_id,
        actor="operator-A",
        casilla_inputs=casilla_inputs,
        binding_values=_DEFAULT_130_BINDING_VALUES,
        work_unit_repository=wu_repo,
        calculation_repository=cr_repo,
        bucket_event_repository=bv_repo,
        clock=_T1,
    )

    # Operator inputs surface in ``inputs_snapshot``.
    assert revision.inputs_snapshot["01"] == "10000"
    assert revision.inputs_snapshot["02"] == "3000"
    assert "03" not in revision.inputs_snapshot  # 03 is a formula target, not an input

    # Calculation output contains BOTH the operator inputs AND every
    # formula target; domain-level registry tests own arithmetic parity.
    assert revision.casilla_values["01"] == casilla_inputs["01"]
    assert revision.casilla_values["02"] == casilla_inputs["02"]
    assert "03" in revision.casilla_values
    assert revision.casilla_values["03"] < revision.casilla_values["01"]
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
    repos: _Repos,
    tmp_path: Path,
) -> None:
    """The registry root resolves via ``PROJECT_ROOT`` from
    ``aeat.core.config``, not via a CWD-relative ``"registry/aeat"``
    string. Running the action from any other directory must still
    work — production deploys, background daemons, and wheel
    installs all run from non-repo CWDs.

    Uses ``contextlib.chdir`` (stdlib, live-tests-friendly) instead of
    monkeypatch.chdir per the project no-monkeypatch mandate (CLAUDE.md).
    """

    import contextlib
    import os as _os

    alien_cwd = tmp_path / "alien-working-dir"
    alien_cwd.mkdir()

    with contextlib.chdir(alien_cwd):
        assert _os.getcwd() == str(alien_cwd)

        wu_repo, cr_repo, _, _, bv_repo = repos
        work_unit = _seed_work_unit(wu_repo)
        revision = calculate_modelo_revision(
            work_unit.work_unit_id,
            actor="operator-A",
            casilla_inputs={"01": Decimal("10000"), "02": Decimal("3000")},
            binding_values=_DEFAULT_130_BINDING_VALUES,
            work_unit_repository=wu_repo,
            calculation_repository=cr_repo,
            bucket_event_repository=bv_repo,
            clock=_T1,
        )

    # Sanity: engine ran (formula casilla 03 computed = 01 - 02).
    assert revision.casilla_values["03"] == Decimal("7000.00")


def test_calculate_refuses_when_registry_snapshot_unresolvable(repos: _Repos) -> None:
    """``calculate_modelo_revision`` runs the formula engine, so it
    cannot operate on a work unit whose (modelo, year, period) tuple
    does not resolve a registry snapshot. The action raises
    ``CalculationRegistryUnavailableError`` rather than persisting a
    revision that bypasses the engine."""

    from .. import CalculationRegistryUnavailableError

    wu_repo, cr_repo, _, _, bv_repo = repos
    # Modelo 130 at year 2010 predates the registry's earliest
    # revision (``2019-y-siguientes``), so the snapshot lookup fails.
    work_unit = create_work_unit(
        bucket_id="default",
        modelo="130",
        filing_year=2010,
        period="1T",
        revision_id="2019-y-siguientes",
        repository=wu_repo,
        clock=_T0,
    )

    with pytest.raises(CalculationRegistryUnavailableError) as exc_info:
        calculate_modelo_revision(
            work_unit.work_unit_id,
            actor="operator-A",
            casilla_inputs={"01": Decimal("1000")},
            binding_values=_DEFAULT_130_BINDING_VALUES,
            work_unit_repository=wu_repo,
            calculation_repository=cr_repo,
            bucket_event_repository=bv_repo,
            clock=_T1,
        )
    assert exc_info.value.translated_message == "application.modelo.errors.calculation_registry_snapshot_unresolved"

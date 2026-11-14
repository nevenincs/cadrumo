"""The persona world tool prepares the returns the table plans, in a profile that outlives the run."""

from __future__ import annotations

import json
import os
from collections.abc import Iterator
from pathlib import Path
from types import SimpleNamespace
from typing import cast
from uuid import UUID

import pytest

from cadrumo.adapters.persistence.profile.modelos_work_units import WorkUnitCatalogueRepository
from cadrumo.adapters.persistence.storage.custody.tests.portable_password_custody import portable_password_custody
from cadrumo.adapters.persistence.storage.master_key.active_session import close_active_bucket_session
from cadrumo.adapters.persistence.storage.tests.profile_session_setup import reset_test_profile_session
from cadrumo.adapters.persistence.storage.tests.secure_sql import isolated_profile_storage_root
from cadrumo.application.user_profile.login_session import authenticate_profile_for_invocation
from cadrumo.application.user_profile.profile_record_repository import ProfileRecordRepository
from cadrumo.core.authority_grade import RegistryAuthorityGrade
from cadrumo.domain.calculations.registry.authority import bundled_indexed_authority
from cadrumo.domain.calculations.registry.binding_targets import casillas_by_binding
from cadrumo.domain.user_profile.values import ProfileSetupState
from cadrumo.entrypoints.adapter_composition import profile_adapter_composition
from cadrumo.entrypoints.tests.persona_materialisation import (
    PERSONA_PROFILE_CREDENTIAL,
    MaterialisedPersona,
    year_envelope,
)

from .. import desktop_persona_world
from ..acceptance.persona_table.cli_column import statements as table_statements
from ..acceptance.persona_table.cli_column.world_report import Phase, Statement, StatementKind
from ..acceptance.persona_table.rows import PlannedRow
from ..desktop_agent_live.disposable_root import create_root, remove_root, temporary_parent
from ..paths import STORAGE_ROOT_ENV

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint]

PERSONA = "asalariada-familia"


@pytest.fixture
def disposable_root() -> Iterator[Path]:
    """A fresh ``cadrumo-e2e-*`` root in the account's temporary folder, outside every Git project."""
    parent = temporary_parent(os.environ)
    root = create_root(parent)
    try:
        yield root
    finally:
        assert remove_root(root, parent) == []


def _registry_horizon() -> int:
    with bundled_indexed_authority().operation() as operation:
        return year_envelope(operation).horizon


def _stored_profile(storage_root: Path, profile_id: str) -> tuple[str, ProfileSetupState, dict[str, bool]]:
    """Sign in to the stored profile with the materialiser's passphrase and read its record and work units back.

    The work units map each stored work unit id to whether it holds a calculation.
    """
    identity = UUID(profile_id)
    with (
        bundled_indexed_authority().operation() as operation,
        profile_adapter_composition(),
        isolated_profile_storage_root(tmp_path=storage_root.parent),
        portable_password_custody(),
    ):
        decode = operation.profile_decode_context()
        try:
            authenticate_profile_for_invocation(
                name=profile_id, passphrase_callback=lambda: PERSONA_PROFILE_CREDENTIAL, profile_decode_context=decode
            )
            record = ProfileRecordRepository.for_current_session(identity, profile_decode_context=decode).load(identity)
            catalogue = WorkUnitCatalogueRepository(bucket_id=profile_id).load()
        finally:
            close_active_bucket_session()
            reset_test_profile_session()
    held = {unit_id: unit.current_calculation_revision_id is not None for unit_id, unit in catalogue.work_units.items()}
    return str(record.profile_id), record.setup_state, held


@pytest.mark.parametrize(
    ("persona", "entered_kinds", "recorded_kinds"),
    [
        ("asalariada-familia", {"prior_carries", "work_income_none"}, set()),
        ("traductora-profesional", {"prior_carries"}, set()),
        ("sociedad-limitada", {"prior_value", "work_input"}, set()),
    ],
    ids=["asalariada", "traductora", "sociedad"],
)
def test_world_holds_the_rows_the_table_plans_and_a_profile_that_signs_in(
    disposable_root: Path,
    capsys: pytest.CaptureFixture[str],
    persona: str,
    entered_kinds: set[str],
    recorded_kinds: set[str],
) -> None:
    horizon = _registry_horizon()
    ambient = os.environ.get(STORAGE_ROOT_ENV)

    status = desktop_persona_world.main(
        ["--persona", persona, "--horizon", str(horizon), "--storage-root", str(disposable_root / "world")]
    )

    assert status == 0
    assert os.environ.get(STORAGE_ROOT_ENV) == ambient
    report = json.loads(capsys.readouterr().out)

    from ..acceptance.persona_table import sweep

    plans, _emitted = sweep.plan_rows(persona, horizon)
    assert [(row["modelo"], row["year"], row["period"]) for row in report["rows"]] == [
        (plan.modelo, plan.year, plan.period) for plan in plans
    ]
    assert report["persona"] == persona
    assert report["horizon"] == horizon
    assert report["passphrase_source"] == desktop_persona_world.CREDENTIAL_SOURCE
    assert PERSONA_PROFILE_CREDENTIAL not in json.dumps(report)
    assert any(row["prepared"] for row in report["rows"])
    assert {item["kind"] for row in report["rows"] for item in row["window_statements"]} == entered_kinds
    assert {item["kind"] for row in report["rows"] for item in row["no_window_door"]} == recorded_kinds
    for row in report["rows"]:
        assert "m303_evidence" in row
        if row["prepared"] and row["modelo"] == "303":
            assert isinstance(row["m303_evidence"]["joint_return_elected"], bool), row
            assert ("attachment_id" in row["m303_evidence"]) == ("m303_attestation" in row["stages"]), row
        elif row["modelo"] != "303":
            assert row["m303_evidence"] is None, row
        if row["prepared"]:
            assert row["work_unit_id"], row
            assert row["pre_calculate_outcome"] is None
            assert row["stages"][0] == "create"
            assert "calculate" not in row["stages"] or row["calculate_inherited_reason"], row
            assert row["driver_calculate"] in {desktop_persona_world.NOT_RUN, "calculated", "refused"}
            assert (row["driver_calculate"] == desktop_persona_world.NOT_RUN) == (
                row["calculate_inherited_reason"] is None and row["driver_calculate"] != "refused"
            ), row
            # A kind the window cannot enter is recorded and named; a row without one is left to the window.
            if row["no_window_door"]:
                assert row["driver_calculate"] != desktop_persona_world.NOT_RUN, row
                assert all(item["kind"] in row["calculate_inherited_reason"] for item in row["no_window_door"]), row
            else:
                assert row["driver_calculate"] == desktop_persona_world.NOT_RUN, row
        else:
            assert row["pre_calculate_outcome"], row
            assert row["stages"] == []
            assert row["driver_calculate"] is None
            assert row["calculate_inherited_reason"] is None
    assert PERSONA_PROFILE_CREDENTIAL not in json.dumps(report)

    storage_root = Path(report["storage_root"])
    assert storage_root.is_dir()
    assert storage_root.name == "cadrumo-storage"
    assert storage_root.is_relative_to(disposable_root)
    assert (storage_root / "buckets" / report["profile_id"]).is_dir()
    stored_id, setup_state, held = _stored_profile(storage_root, report["profile_id"])
    assert stored_id == report["profile_id"]
    assert setup_state is ProfileSetupState.COMPLETE
    prepared = [row for row in report["rows"] if row["prepared"]]
    # A row reported not run holds no calculation in the stored profile; one reported calculated holds one.
    assert any(row["driver_calculate"] == desktop_persona_world.NOT_RUN for row in prepared)
    for row in prepared:
        assert held[row["work_unit_id"]] is (row["driver_calculate"] != desktop_persona_world.NOT_RUN), row


def test_a_root_that_holds_files_is_refused(tmp_path: Path) -> None:
    (tmp_path / "held.txt").write_text("held", encoding="utf-8")

    assert desktop_persona_world.refuse_storage_root(tmp_path) is not None
    with pytest.raises(SystemExit) as refusal:
        desktop_persona_world.main(["--persona", PERSONA, "--horizon", "1", "--storage-root", str(tmp_path)])
    assert refusal.value.code == 2


def test_a_relative_root_is_refused() -> None:
    assert desktop_persona_world.refuse_storage_root(Path("world")) is not None


def test_a_root_inside_a_git_project_is_refused(disposable_root: Path) -> None:
    project = disposable_root / "project"
    (project / ".git").mkdir(parents=True)

    assert desktop_persona_world.refuse_storage_root(project / "world") is not None
    assert desktop_persona_world.refuse_storage_root(disposable_root / "world") is None


def test_an_unknown_persona_is_refused(disposable_root: Path) -> None:
    with pytest.raises(SystemExit) as refusal:
        desktop_persona_world.main(
            ["--persona", "no-such-persona", "--horizon", "1", "--storage-root", str(disposable_root / "world")]
        )
    assert refusal.value.code == 2


def _statement(
    kind: StatementKind,
    phase: Phase,
    *,
    target: str = "",
    value: str = "",
    row: str | None = None,
    families: tuple[str, ...] = (),
    amounts: tuple[tuple[str, str], ...] = (),
    gap: str | None = None,
    refusal: str | None = None,
) -> Statement:
    return Statement(
        kind, phase, target=target, value=value, row=row, families=families, amounts=amounts, gap=gap, refusal=refusal
    )


def _split(monkeypatch: pytest.MonkeyPatch, made: tuple[Statement, ...]) -> desktop_persona_world.WindowSplit:
    """Split ``made`` as the world does; the statements the table makes are the only thing replaced."""
    monkeypatch.setattr(table_statements, "statements_for", lambda _materialised, _plan: made)
    plan = cast(PlannedRow, SimpleNamespace(modelo="100", year=1, period="0A"))
    return desktop_persona_world.window_split(cast(MaterialisedPersona, SimpleNamespace()), plan)


def test_a_carry_a_prior_figure_the_work_income_statement_a_work_input_and_a_rental_carry_have_a_window_door() -> None:
    door = desktop_persona_world._has_window_door
    assert door(_statement(StatementKind.PRIOR_CARRIES, Phase.BEFORE_EVIDENCE, families=("f",)))
    assert door(_statement(StatementKind.PRIOR_VALUE, Phase.BEFORE_EVIDENCE, target="b", value="1"))
    assert door(_statement(StatementKind.WORK_INCOME_NONE, Phase.AFTER_CALCULATION))
    assert door(_statement(StatementKind.PRIOR_CARRIES, Phase.BEFORE_EVIDENCE, amounts=(("1380", "5"),)))
    assert door(_statement(StatementKind.WORK_INPUT, Phase.AT_CALCULATION, target="c", value="1"))
    assert not door(_statement(StatementKind.PRIOR_CARRIES, Phase.BEFORE_EVIDENCE, gap="not sayable"))
    assert not door(_statement(StatementKind.WORK_INPUT, Phase.AT_CALCULATION, refusal="no"))
    assert door(_statement(StatementKind.RENTAL_CARRY, Phase.AFTER_RECALCULATION, target="b", row="r"))
    assert not door(_statement(StatementKind.RENTAL_CARRY, Phase.AFTER_RECALCULATION, refusal="one total"))
    assert not door(_statement(StatementKind.WORK_INCOME_NONE, Phase.AFTER_CALCULATION, refusal="no"))


def test_the_world_records_up_to_the_last_statement_no_window_door_enters_and_leaves_the_rest(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    carries = _statement(StatementKind.PRIOR_CARRIES, Phase.BEFORE_EVIDENCE, families=("f",))
    figure = _statement(StatementKind.PRIOR_VALUE, Phase.BEFORE_EVIDENCE, target="b", value="1")
    figure_again = _statement(StatementKind.PRIOR_VALUE, Phase.AFTER_CALCULATION, target="b", value="1")
    work_input = _statement(StatementKind.WORK_INPUT, Phase.AT_CALCULATION, target="c", value="2")
    income = _statement(StatementKind.WORK_INCOME_NONE, Phase.AFTER_CALCULATION)
    rental = _statement(StatementKind.RENTAL_CARRY, Phase.AFTER_RECALCULATION, target="b", row="r")
    other_rental = _statement(StatementKind.RENTAL_CARRY, Phase.AFTER_RECALCULATION, target="b", row="s")
    refused_rental = _statement(StatementKind.RENTAL_CARRY, Phase.AFTER_RECALCULATION, refusal="one total")

    everything = _split(monkeypatch, (carries, figure, figure_again, income))
    assert everything.left == {StatementKind.PRIOR_CARRIES, StatementKind.PRIOR_VALUE, StatementKind.WORK_INCOME_NONE}
    assert [item.kind for item in everything.entered] == [
        StatementKind.PRIOR_CARRIES,
        StatementKind.PRIOR_VALUE,
        StatementKind.WORK_INCOME_NONE,
    ]
    assert everything.without_door == ()

    with_input = _split(monkeypatch, (carries, work_input, income))
    assert with_input.left == {StatementKind.PRIOR_CARRIES, StatementKind.WORK_INPUT, StatementKind.WORK_INCOME_NONE}
    assert with_input.without_door == ()

    with_rentals = _split(monkeypatch, (carries, income, rental, other_rental))
    assert StatementKind.RENTAL_CARRY in with_rentals.left
    assert [item.row for item in with_rentals.entered if item.kind is StatementKind.RENTAL_CARRY] == ["r", "s"]
    assert with_rentals.without_door == ()

    behind_refusal = _split(monkeypatch, (carries, figure, income, refused_rental))
    assert behind_refusal.left == frozenset()
    assert behind_refusal.entered == ()
    assert behind_refusal.without_door == (refused_rental,)

    nothing = _split(monkeypatch, ())
    assert nothing == desktop_persona_world.WindowSplit()


def test_a_carry_stated_as_an_amount_is_entered_on_each_binding_its_box_feeds() -> None:
    family = "renta_negative_general_bases_pending"
    statement = _statement(
        StatementKind.PRIOR_CARRIES, Phase.BEFORE_EVIDENCE, families=(family,), amounts=(("1380", "5.5"),)
    )
    with bundled_indexed_authority().operation() as operation:
        revision = operation.snapshot(
            "100", filing_year=_registry_horizon(), period="0A", grade=RegistryAuthorityGrade.CALCULATION
        ).revision
        world = SimpleNamespace(operation=operation)
        plan = cast(PlannedRow, SimpleNamespace(modelo="100", year=_registry_horizon(), period="0A"))
        figures = desktop_persona_world._carry_figures(
            cast(MaterialisedPersona, SimpleNamespace(world=world)), plan, statement
        )
        fed = casillas_by_binding(revision)
    assert figures
    assert {item["value"] for item in figures} == {"5.5"}
    for item in figures:
        assert "1380" in {
            str(box) for binding, boxes in fed.items() if str(binding) == item["binding"] for box in boxes
        }

"""The CLI column's sweep takes its cases from the table's planner, resumes from its lines and reuses one build."""

from __future__ import annotations

import json
import secrets
import tempfile
from collections.abc import Iterator
from pathlib import Path

import pytest

from dev.packaging.acquire_common import venv_executable
from dev.runtime_lifecycle.caller_owned_root import AcceptanceError

from ..cli_column.case import NOT_DRIVEN, CasePlace, CaseSpec, finish_case, seeding_reason
from ..cli_column.driver import CaseSummary, Selection
from ..cli_column.hygiene import Redactor
from ..cli_column.intake import LineWriter, persona_line
from ..cli_column.runtime import RuntimeSetupError, e2e_parent
from ..cli_column.sweep import (
    HorizonPlan,
    Progress,
    SweepSettings,
    TreeVenv,
    horizon_plans,
    is_complete,
    read_progress,
    run_sweep,
    venv_inside,
    written_keys,
)
from ..cli_column.world_report import ReturnKey, WorldReport
from ..planner import registry_envelope

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint]

_PERSONA = "autonomo-alta-reciente"
_TREE = "t"
_LEAK = "synthetic-persona-passphrase"


def _redactor() -> Redactor:
    return Redactor([_LEAK])


def _envelope_horizons() -> list[int]:
    envelope = registry_envelope()
    return list(range(envelope.horizon, envelope.floor - 1, -1))


def _years() -> tuple[int, int, int]:
    """Three consecutive horizons of the envelope, newest first."""
    newest, middle, oldest = _envelope_horizons()[:3]
    return newest, middle, oldest


def _line(modelo: str | None, year: int | None, period: str | None, *, tree: str = _TREE, **more: object) -> str:
    line: dict[str, object] = {
        "surface": "cli",
        "tree": tree,
        "persona": _PERSONA,
        "modelo": modelo,
        "year": year,
        "period": period,
        "loads": True,
    }
    return json.dumps(line | more)


def _lines_file(tmp_path: Path, *lines: str) -> Path:
    path = tmp_path / "cli-t.jsonl"
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return path


def _report(horizon: int) -> WorldReport:
    return WorldReport(_PERSONA, horizon, "root", "id", "gen", "instant", "full", "actor", False, ())


def test_the_horizons_and_returns_come_from_the_planner() -> None:
    plans = horizon_plans([_PERSONA])

    assert [plan.horizon for plan in plans] == _envelope_horizons()
    for plan in plans:
        assert plan.persona == _PERSONA
        assert plan.keys == {("130", plan.horizon, "1T"), ("303", plan.horizon, "1T")}


def test_horizon_modelo_and_period_filters_narrow_the_cases_and_a_foreign_horizon_is_refused() -> None:
    horizons = _envelope_horizons()

    narrowed = horizon_plans([_PERSONA], horizons=[horizons[1]], modelos=["303"])
    assert [(plan.horizon, plan.keys) for plan in narrowed] == [(horizons[1], {("303", horizons[1], "1T")})]
    assert horizon_plans([_PERSONA], periods=["4T"]) == []
    with pytest.raises(ValueError, match="outside the registry envelope"):
        horizon_plans([_PERSONA], horizons=[horizons[0] + 1])


def test_progress_holds_only_the_trees_return_lines_and_skips_damaged_ones(tmp_path: Path) -> None:
    newest, middle, _oldest = _years()
    path = _lines_file(
        tmp_path,
        _line("130", newest, "1T"),
        _line("303", newest, "1T", tree="other"),
        "not json",
        "[1, 2]",
        "",
        _line(None, None, None, reason=f"horizon {middle}: no returns named here"),
    )

    progress = read_progress(path, _TREE)

    assert progress.written == {(_PERSONA, ("130", newest, "1T"))}
    assert progress.not_driven == frozenset()
    assert read_progress(tmp_path / "absent.jsonl", _TREE) == Progress()


def test_the_returns_a_persona_line_names_undriven_are_read_back_from_the_line_the_writer_wrote(tmp_path: Path) -> None:
    _newest, middle, _oldest = _years()
    skipped = (
        (("130", middle, "1T"), "stated not owed"),
        (("100", middle, "0A"), "no CLI door for modelo.edit.apply (prior_carries)"),
    )
    reason = seeding_reason(_report(middle), "persona", "gen", Selection((), frozenset(), skipped))
    assert NOT_DRIVEN in reason
    writer = LineWriter(tmp_path / "cli-t.jsonl", _redactor())
    writer.write(persona_line(tree=_TREE, persona=_PERSONA, loads=True, reason=reason, log="case.log"))

    progress = read_progress(writer.path, _TREE)

    assert progress.not_driven == {(_PERSONA, middle, ("130", middle, "1T")), (_PERSONA, middle, ("100", middle, "0A"))}
    assert progress.written == frozenset()


def test_a_horizon_is_complete_when_every_row_is_written_or_named_undriven_for_that_horizon() -> None:
    _newest, middle, oldest = _years()
    keys: frozenset[ReturnKey] = frozenset({("130", middle, "1T"), ("303", middle, "1T")})
    plan = HorizonPlan(_PERSONA, middle, keys)
    written = Progress(written=frozenset({(_PERSONA, ("130", middle, "1T"))}))
    named = Progress(not_driven=frozenset({(_PERSONA, middle, ("303", middle, "1T"))}))
    both = Progress(written=written.written, not_driven=named.not_driven)
    other_horizon = Progress(written=written.written, not_driven=frozenset({(_PERSONA, oldest, ("303", middle, "1T"))}))

    assert not is_complete(plan, Progress())
    assert not is_complete(plan, written)
    assert not is_complete(plan, other_horizon)
    assert is_complete(plan, both)
    assert written_keys(plan, written) == {("130", middle, "1T")}


def _launcher(snapshot: Path, name: str) -> Path:
    venv = snapshot / ".tmp" / "client-venv" / name
    launcher = venv_executable(venv, "aeat")
    launcher.parent.mkdir(parents=True, exist_ok=True)
    launcher.write_text("launcher", encoding="utf-8")
    return venv


def test_the_tree_venv_is_built_once_and_again_only_when_its_launcher_is_gone(tmp_path: Path) -> None:
    snapshot = tmp_path / "snap-t"
    names = iter(["first", "second"])
    venv = TreeVenv(snapshot, lambda: _launcher(snapshot, next(names)))

    first = venv.path()
    assert venv.path() == first
    assert venv.builds == 1

    venv_executable(first, "aeat").unlink()
    second = venv.path()
    assert second != first
    assert venv.builds == 2


def test_a_venv_outside_the_snapshot_is_refused(tmp_path: Path) -> None:
    snapshot = tmp_path / "snap-t"
    snapshot.mkdir()
    outside = tmp_path / "elsewhere" / ".venv"

    with pytest.raises(RuntimeSetupError, match="outside the snapshot"):
        venv_inside(snapshot, outside)
    assert venv_inside(snapshot, snapshot / ".tmp" / ".venv") == (snapshot / ".tmp" / ".venv").resolve()


class _Driver:
    """Stands in for the live case: records what it was given and ends as scripted."""

    def __init__(self, stop_at: tuple[str, int] | None = None) -> None:
        self.calls: list[tuple[int, frozenset[ReturnKey], Path, bool]] = []
        self._stop_at = stop_at

    def __call__(
        self,
        spec: CaseSpec,
        template: Path,
        writer: LineWriter,
        redactor: Redactor,
        place: CasePlace,
        done: frozenset[ReturnKey],
    ) -> CaseSummary:
        del writer, redactor
        self.calls.append((spec.horizon, done, template, place.root.is_dir()))
        if self._stop_at is not None and self._stop_at[1] == spec.horizon:
            return CaseSummary(stopped_at=("130", spec.horizon, self._stop_at[0]))
        return CaseSummary()


@pytest.fixture
def outside_git() -> Iterator[Path]:
    """A folder in the account's temporary folder: a disposable root may not be made inside a Git project."""
    with tempfile.TemporaryDirectory(dir=e2e_parent(), prefix="sweep-test-") as folder:
        yield Path(folder)


def _settings(tmp_path: Path, parent: Path) -> SweepSettings:
    return SweepSettings(
        _TREE,
        tmp_path / "snap-t",
        tmp_path / "authority-t",
        tmp_path / "cli-t.jsonl",
        None,
        True,
        (_PERSONA,),
        root_parent=parent,
    )


def _plans(*horizons: int) -> list[HorizonPlan]:
    return [HorizonPlan(_PERSONA, h, frozenset({("130", h, "1T"), ("303", h, "1T")})) for h in horizons]


def test_a_sweep_skips_complete_horizons_and_runs_the_rest_on_one_build(tmp_path: Path, outside_git: Path) -> None:
    settings = _settings(tmp_path, outside_git)
    newest, middle, oldest = _years()
    _lines_file(tmp_path, _line("130", newest, "1T"), _line("303", newest, "1T"), _line("130", middle, "1T"))
    snapshot = settings.snapshot
    venv = TreeVenv(snapshot, lambda: _launcher(snapshot, "only"))
    driver = _Driver()

    result = run_sweep(
        settings, _plans(newest, middle, oldest), venv, (LineWriter(settings.out, _redactor()), _redactor()), driver
    )

    assert result.complete == [f"{_PERSONA}@{newest}"]
    assert result.driven == [f"{_PERSONA}@{middle}", f"{_PERSONA}@{oldest}"]
    assert result.stopped_at is None
    assert venv.builds == 1
    assert [call[0] for call in driver.calls] == [middle, oldest]
    assert driver.calls[0][1] == {("130", middle, "1T")}
    assert driver.calls[1][1] == frozenset()
    assert {call[2] for call in driver.calls} == {venv.path()}
    assert all(call[3] for call in driver.calls)
    assert settings.root_parent is not None
    assert list(settings.root_parent.iterdir()) == []


def test_a_sweep_stops_at_the_first_unsettled_case_and_keeps_its_root(tmp_path: Path, outside_git: Path) -> None:
    settings = _settings(tmp_path, outside_git)
    newest, middle, oldest = _years()
    snapshot = settings.snapshot
    venv = TreeVenv(snapshot, lambda: _launcher(snapshot, "only"))
    driver = _Driver(stop_at=("1T", middle))

    result = run_sweep(
        settings, _plans(newest, middle, oldest), venv, (LineWriter(settings.out, _redactor()), _redactor()), driver
    )

    assert [call[0] for call in driver.calls] == [newest, middle]
    assert result.driven == [f"{_PERSONA}@{newest}", f"{_PERSONA}@{middle}"]
    assert result.stopped_at == f"{_PERSONA}@{middle} at 130/{middle}/1T"
    assert settings.root_parent is not None
    (kept,) = settings.root_parent.iterdir()
    assert kept.name.startswith("cadrumo-e2e-")
    assert any("root kept for evidence" in note for note in result.notes)


def _root_name() -> str:
    return f"cadrumo-e2e-{secrets.token_hex(16)}"


def test_a_finished_case_removes_its_root_and_a_stopped_one_keeps_it(tmp_path: Path) -> None:
    removed = CasePlace(tmp_path / _root_name(), tmp_path / "logs-a")
    kept = CasePlace(tmp_path / _root_name(), tmp_path / "logs-b")
    for place in (removed, kept):
        (place.root / "runtime").mkdir(parents=True)

    assert finish_case(removed, _redactor(), keep_root=False, parent=tmp_path) == []
    notes = finish_case(kept, _redactor(), keep_root=True, parent=tmp_path)

    assert not removed.root.exists()
    assert kept.root.is_dir()
    assert notes == [f"root kept for evidence: {kept.root}"]


def test_a_root_that_is_not_a_disposable_one_below_the_parent_is_never_removed(tmp_path: Path) -> None:
    profile = tmp_path / "profile-data"
    (profile / "keep").mkdir(parents=True)
    nested = tmp_path / "inner" / _root_name()
    nested.mkdir(parents=True)

    for root in (profile, nested):
        with pytest.raises(AcceptanceError):
            finish_case(CasePlace(root, tmp_path / "logs"), _redactor(), keep_root=False, parent=tmp_path)

    assert (profile / "keep").is_dir()
    assert nested.is_dir()


def test_a_case_log_that_holds_a_secret_is_removed_when_the_case_finishes(tmp_path: Path) -> None:
    place = CasePlace(tmp_path / _root_name(), tmp_path / "logs")
    place.root.mkdir()
    place.log_dir.mkdir()
    (place.log_dir / "clean.log").write_text("fine", encoding="utf-8")
    (place.log_dir / "leak.log").write_text(f"x {_LEAK} y", encoding="utf-8")

    notes = finish_case(place, _redactor(), keep_root=False, parent=tmp_path)

    assert not (place.log_dir / "leak.log").exists()
    assert (place.log_dir / "clean.log").is_file()
    assert notes == ["a secret appeared in leak.log, which was removed"]


def test_an_oauth_client_read_after_the_redactor_was_made_is_redacted_whole_and_by_its_leaves() -> None:
    client = json.dumps({"installed": {"client_id": "id-1234567.apps", "client_secret": "s3cr3t-value-9", "x": 1}})
    redactor = _redactor().with_client(client)

    text = redactor.text(f"{client} id-1234567.apps s3cr3t-value-9 {_LEAK} plain")

    assert text == "[redacted] [redacted] [redacted] [redacted] plain"
    assert _redactor().text("s3cr3t-value-9") == "s3cr3t-value-9"

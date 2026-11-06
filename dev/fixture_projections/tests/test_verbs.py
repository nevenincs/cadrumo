"""Seed, check, clean and status act on an isolated checkout with real producer processes.

Each case builds its own checkout under ``tmp_path`` with a small producer
script, so every verb is proven against a planted defect: a failing producer,
an absent prerequisite, a stale or unstamped output, a nondeterministic build,
an output root outside the checkout, a link, or a leftover recording switch.
"""

from __future__ import annotations

import os
import sys
from dataclasses import replace
from pathlib import Path

import pytest

from ..cli import (
    DETERMINISM_UNDECLARED,
    FixtureProjectionError,
    Workspace,
    check,
    child_environment,
    clean,
    removable_targets,
    seed,
    status,
)
from ..location import window_projections
from ..registry import OUTPUT, PYTHON, RECORDING_SWITCHES, Command, FixtureFamily, InputGroup, Prerequisite
from ..stamps import FixtureState, InputDigests, family_inputs, family_status, stamp_path

pytestmark = [pytest.mark.integration, pytest.mark.hex_core]

_AUTHORITY = {"database_sha256": "a" * 64, "logical_generation": "b" * 64}

#: Renders ``out/fixture.json`` from ``inputs/source.txt``; logs every write to ``writes.log``.
_PRODUCER = """\
import os, sys
from pathlib import Path

rendered = Path("inputs/source.txt").read_text(encoding="utf-8").upper()
if "--random" in sys.argv:
    rendered += os.urandom(8).hex()
if "--fail" in sys.argv:
    sys.exit(3)
target = Path("out/fixture.json")
if "--into" in sys.argv:
    target = Path(sys.argv[sys.argv.index("--into") + 1]) / "fixture.json"
    target.parent.mkdir(parents=True, exist_ok=True)
if "--output" in sys.argv:
    target = Path(sys.argv[sys.argv.index("--output") + 1]) / "fixture.json"
# A leftover recording switch made an old recorder write even when checking.
if "--check" in sys.argv and not os.environ.get("CADRUMO_STAGED_CHECK_UNRECORDED"):
    sys.exit(0 if target.is_file() and target.read_text(encoding="utf-8") == rendered else 1)
target.write_text(rendered, encoding="utf-8")
with Path("writes.log").open("a", encoding="utf-8") as log:
    log.write(" ".join(sys.argv[1:]) + "\\n")
"""


def _family(
    *,
    committed: bool = False,
    proves: bool = True,
    determinism: tuple[str, ...] | None = ("--output", OUTPUT),
    producer: tuple[str, ...] = (),
    prerequisites: tuple[Prerequisite, ...] = (),
    output_root: str = "out",
    outputs: tuple[str, ...] = ("*.json",),
) -> FixtureFamily:
    script = (PYTHON, "tools/produce.py")
    return FixtureFamily(
        name="sample",
        summary="A sample projection.",
        inputs=(InputGroup("producer", ("tools/produce.py",)), InputGroup("source", ("inputs",))),
        check=(Command((*script, "--check")),),
        producer=Command((*script, *producer)),
        output_root=output_root,
        outputs=outputs,
        committed=committed,
        determinism=None if determinism is None else Command((*script, *determinism)),
        prerequisites=prerequisites,
        check_proves_outputs=proves,
    )


def _checkout(root: Path) -> Path:
    (root / "tools").mkdir(parents=True)
    (root / "tools" / "produce.py").write_text(_PRODUCER, encoding="utf-8")
    (root / "inputs").mkdir()
    (root / "inputs" / "source.txt").write_text("hello", encoding="utf-8")
    (root / "out").mkdir()
    return root


def _workspace(root: Path, *families: FixtureFamily) -> Workspace:
    return Workspace(
        root=root,
        families=families or (_family(),),
        authority=lambda: _AUTHORITY,
        persona_check=lambda: (),
        cache_directory=root.parent / "cache",
        scratch_root=root.parent / "scratch",
    )


def _writes(root: Path) -> list[str]:
    log = root / "writes.log"
    return log.read_text(encoding="utf-8").splitlines() if log.exists() else []


def _state(workspace: Workspace, family: FixtureFamily) -> FixtureState:
    inputs = family_inputs(family, InputDigests(workspace.root), _AUTHORITY)
    return family_status(family, workspace.root, inputs, cache_directory=workspace.cache_directory).state


def test_seed_produces_a_missing_family_once_and_then_finds_it_fresh(tmp_path: Path) -> None:
    root = _checkout(tmp_path / "repo")
    workspace = _workspace(root)

    assert seed([], force=False, workspace=workspace) == 0
    assert (root / "out" / "fixture.json").read_text(encoding="utf-8") == "HELLO"
    assert _state(workspace, workspace.families[0]) is FixtureState.FRESH

    assert seed([], force=False, workspace=workspace) == 0
    assert _writes(root) == [""]


def test_seed_force_produces_a_fresh_family_again(tmp_path: Path) -> None:
    root = _checkout(tmp_path / "repo")
    workspace = _workspace(root)
    seed([], force=False, workspace=workspace)

    assert seed([], force=True, workspace=workspace) == 0
    assert _writes(root) == ["", ""]


def test_a_failing_producer_fails_the_seed_and_leaves_no_stamp(tmp_path: Path) -> None:
    root = _checkout(tmp_path / "repo")
    family = _family(producer=("--fail",))
    workspace = _workspace(root, family)

    assert seed([], force=False, workspace=workspace) == 1
    assert not stamp_path(family, root).exists()
    assert _state(workspace, family) is FixtureState.MISSING


def test_an_absent_prerequisite_refuses_seed_and_check_without_running_anything(tmp_path: Path) -> None:
    root = _checkout(tmp_path / "repo")
    family = _family(prerequisites=(Prerequisite("node_modules", "just setup-desktop-frontend"),))
    workspace = _workspace(root, family)

    assert seed([], force=False, workspace=workspace) == 1
    assert check([], determinism=False, workspace=workspace) == 1
    assert _writes(root) == []

    (root / "node_modules").mkdir()
    assert seed([], force=False, workspace=workspace) == 0
    assert check([], determinism=False, workspace=workspace) == 0


def test_seed_window_produces_only_the_generated_window_projections(tmp_path: Path) -> None:
    root = _checkout(tmp_path / "repo")
    projections = window_projections()
    elsewhere = replace(_family(), name="elsewhere")
    committed = replace(
        _family(producer=("--into", projections), committed=True), name="committed", output_root=projections
    )
    window = replace(_family(producer=("--into", projections)), name="window", output_root=projections)
    workspace = _workspace(root, elsewhere, committed, window)

    assert seed([], force=False, window=True, workspace=workspace) == 0
    assert _writes(root) == [f"--into {projections}"]
    assert (root / projections / "fixture.json").read_text(encoding="utf-8") == "HELLO"
    assert not (root / "out" / "fixture.json").exists()
    assert _state(workspace, window) is FixtureState.FRESH


def test_seed_window_refuses_when_no_family_writes_the_window_projections(tmp_path: Path) -> None:
    root = _checkout(tmp_path / "repo")
    workspace = _workspace(root, _family())

    with pytest.raises(FixtureProjectionError, match="No generated family writes the window projections"):
        seed([], force=False, window=True, workspace=workspace)
    assert _writes(root) == []


def test_seed_window_refuses_named_families_beside_it(tmp_path: Path) -> None:
    root = _checkout(tmp_path / "repo")
    projections = window_projections()
    window = replace(_family(producer=("--into", projections)), name="window", output_root=projections)

    with pytest.raises(FixtureProjectionError, match="not both"):
        seed(["window"], force=False, window=True, workspace=_workspace(root, window))
    assert _writes(root) == []


def test_seed_adopts_unstamped_outputs_its_check_proves_without_producing(tmp_path: Path) -> None:
    root = _checkout(tmp_path / "repo")
    (root / "out" / "fixture.json").write_text("HELLO", encoding="utf-8")
    family = _family()
    workspace = _workspace(root, family)
    assert _state(workspace, family) is FixtureState.UNSTAMPED

    assert seed([], force=False, workspace=workspace) == 0

    assert _writes(root) == []
    assert _state(workspace, family) is FixtureState.FRESH


def test_seed_produces_unstamped_outputs_the_check_refuses(tmp_path: Path) -> None:
    root = _checkout(tmp_path / "repo")
    (root / "out" / "fixture.json").write_text("stale", encoding="utf-8")
    workspace = _workspace(root)

    assert seed([], force=False, workspace=workspace) == 0

    assert _writes(root) == [""]
    assert (root / "out" / "fixture.json").read_text(encoding="utf-8") == "HELLO"


def test_seed_never_adopts_for_a_family_whose_check_does_not_prove_its_bytes(tmp_path: Path) -> None:
    root = _checkout(tmp_path / "repo")
    (root / "out" / "fixture.json").write_text("HELLO", encoding="utf-8")
    workspace = _workspace(root, _family(proves=False))

    assert seed([], force=False, workspace=workspace) == 0
    assert _writes(root) == [""]


def test_check_passes_on_current_outputs_fails_on_stale_ones_and_never_writes(tmp_path: Path) -> None:
    root = _checkout(tmp_path / "repo")
    workspace = _workspace(root)
    seed([], force=False, workspace=workspace)
    assert check([], determinism=False, workspace=workspace) == 0

    (root / "inputs" / "source.txt").write_text("changed", encoding="utf-8")
    assert check([], determinism=False, workspace=workspace) == 1
    assert (root / "out" / "fixture.json").read_text(encoding="utf-8") == "HELLO"
    assert _writes(root) == [""]


def test_check_strips_a_leftover_recording_switch_so_it_cannot_write(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = _checkout(tmp_path / "repo")
    workspace = _workspace(root)
    seed([], force=False, workspace=workspace)
    (root / "inputs" / "source.txt").write_text("changed", encoding="utf-8")
    monkeypatch.setenv("CADRUMO_STAGED_CHECK_UNRECORDED", "all")

    assert check([], determinism=False, workspace=workspace) == 1
    assert _writes(root) == [""]


def test_a_failing_persona_check_fails_the_check(tmp_path: Path) -> None:
    root = _checkout(tmp_path / "repo")
    workspace = _workspace(root)
    seed([], force=False, workspace=workspace)
    failing = Workspace(
        root=root,
        families=workspace.families,
        authority=workspace.authority,
        persona_check=lambda: ("one/persona.toml: unknown role",),
        cache_directory=workspace.cache_directory,
        scratch_root=workspace.scratch_root,
    )

    assert check([], determinism=False, workspace=failing) == 1


def test_determinism_passes_for_repeatable_bytes_and_writes_only_to_scratch(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    root = _checkout(tmp_path / "repo")
    workspace = _workspace(root)
    seed([], force=False, workspace=workspace)

    assert check([], determinism=True, workspace=workspace) == 0
    assert "sample: ok" in capsys.readouterr().out
    assert (root / "out" / "fixture.json").read_text(encoding="utf-8") == "HELLO"
    assert list((tmp_path / "scratch").iterdir()) == []


def test_determinism_reports_differing_bytes_as_nondeterministic(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    root = _checkout(tmp_path / "repo")
    workspace = _workspace(root, _family(determinism=("--random", "--output", OUTPUT)))
    seed([], force=False, workspace=workspace)

    assert check([], determinism=True, workspace=workspace) == 1
    assert "sample: nondeterministic" in capsys.readouterr().out


def test_a_family_without_a_determinism_build_is_undeclared_never_ok(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    root = _checkout(tmp_path / "repo")
    workspace = _workspace(root, _family(determinism=None))
    seed([], force=False, workspace=workspace)

    assert check([], determinism=True, workspace=workspace) == 1
    assert f"sample: {DETERMINISM_UNDECLARED}" in capsys.readouterr().out
    assert check([], determinism=False, workspace=workspace) == 0


def test_clean_removes_generated_outputs_with_their_stamp(tmp_path: Path) -> None:
    root = _checkout(tmp_path / "repo")
    family = _family()
    workspace = _workspace(root, family)
    seed([], force=False, workspace=workspace)
    assert stamp_path(family, root).exists()

    assert clean(["sample"], workspace=workspace) == 0
    assert list((root / "out").iterdir()) == []


def test_clean_refuses_committed_outputs_and_deletes_nothing(tmp_path: Path) -> None:
    root = _checkout(tmp_path / "repo")
    workspace = _workspace(root, _family(committed=True))
    seed([], force=False, workspace=workspace)

    assert clean(["sample"], workspace=workspace) == 1
    assert clean([], workspace=workspace) == 0
    assert (root / "out" / "fixture.json").exists()


def test_an_output_root_outside_the_checkout_is_refused(tmp_path: Path) -> None:
    root = _checkout(tmp_path / "repo")
    (tmp_path / "elsewhere").mkdir()
    (tmp_path / "elsewhere" / "kept.json").write_text("{}", encoding="utf-8")

    with pytest.raises(FixtureProjectionError, match="not inside the checkout"):
        removable_targets(_family(output_root="../elsewhere"), root)
    with pytest.raises(FixtureProjectionError, match="not inside the checkout"):
        removable_targets(_family(output_root="."), root)
    assert (tmp_path / "elsewhere" / "kept.json").exists()


def test_an_output_pattern_reaching_outside_its_root_is_refused(tmp_path: Path) -> None:
    root = _checkout(tmp_path / "repo")
    (root / "inputs" / "kept.json").write_text("{}", encoding="utf-8")

    with pytest.raises(FixtureProjectionError, match="outside its output root"):
        removable_targets(_family(outputs=("*.json", "../inputs/*.json")), root)


def test_a_linked_target_is_refused_rather_than_followed(tmp_path: Path) -> None:
    root = _checkout(tmp_path / "repo")
    family = _family()
    outside = tmp_path / "outside"
    outside.mkdir()
    link = stamp_path(family, root)
    if sys.platform == "win32":
        import _winapi

        _winapi.CreateJunction(str(outside), str(link))
    else:
        link.symlink_to(outside, target_is_directory=True)

    with pytest.raises(FixtureProjectionError, match="refusing to follow the link"):
        removable_targets(family, root)
    assert outside.is_dir()


def test_status_refuses_a_declared_input_that_does_not_exist(tmp_path: Path) -> None:
    root = _checkout(tmp_path / "repo")
    family = _family()
    missing = FixtureFamily(
        name=family.name,
        summary=family.summary,
        inputs=(*family.inputs, InputGroup("typo", ("inputz",))),
        check=family.check,
        producer=family.producer,
        output_root=family.output_root,
        outputs=family.outputs,
        committed=family.committed,
    )

    with pytest.raises(FixtureProjectionError, match="inputz"):
        status([], workspace=_workspace(root, missing))


def test_status_names_an_unknown_family(tmp_path: Path) -> None:
    root = _checkout(tmp_path / "repo")

    with pytest.raises(FixtureProjectionError, match="No fixture family 'other'"):
        status(["other"], workspace=_workspace(root))


def test_the_child_environment_drops_every_recording_switch() -> None:
    inherited = {name: "all" for name in RECORDING_SWITCHES} | {"KEPT": "1"}

    environment = child_environment(Command(("x",), environment=(("ADDED", "2"),)), Path(os.getcwd()), inherited)

    assert not set(RECORDING_SWITCHES) & set(environment)
    assert environment["KEPT"] == "1"
    assert environment["ADDED"] == "2"

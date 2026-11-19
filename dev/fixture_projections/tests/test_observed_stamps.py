"""A family's observed product source keys it on what its real producer processes read.

Each case builds an isolated checkout under ``tmp_path`` with a small ``src/pkg``
package and a real producer script that ``seed`` runs, so the key is proven from
the files the producer's processes actually opened: an imported module keys the
family, an unimported one does not, a child process the observer cannot cover
falls back to the whole product source, and a failed run never stamps.
"""

from __future__ import annotations

import json
from dataclasses import replace
from pathlib import Path
from typing import Any

import pytest

from ..cli import Workspace, seed
from ..registry import PYTHON, Command, FixtureFamily, InputGroup
from ..stamps import CLOSURE_MODE, OBSERVED_MODE, FixtureState, InputDigests, family_inputs, family_status, stamp_path

pytestmark = [pytest.mark.integration, pytest.mark.hex_core]

_AUTHORITY = {"database_sha256": "a" * 64, "logical_generation": "b" * 64}

#: Imports ``pkg.used``, writes ``out/fixture.json`` from it and logs each run to ``writes.log``.
_PRODUCER = """\
import os, subprocess, sys
from pathlib import Path

from pkg import used

options = sys.argv[1:]
target = Path("out/fixture.json")
if "--read-output" in options and target.exists():
    target.read_text(encoding="utf-8")
if "--child-c" in options:
    subprocess.run([sys.executable, "-c", "import pkg.child"], check=True)
if "--child-script" in options:
    subprocess.run([sys.executable, "tools/child_script.py"], check=True)
if "--child-module-without-site" in options:
    subprocess.run([sys.executable, "-S", "-m", "pkg.child"], check=True)
if "--scratch-child" in options:
    import tempfile

    with tempfile.TemporaryDirectory(dir="var/tmp") as scratch:
        subprocess.run([sys.executable, "-S", "-m", "pkg.child"], cwd=scratch, check=True)
if "--isolated-child" in options:
    subprocess.run([sys.executable, "-I", "-c", "pass"], check=True)
if "--native-child" in options:
    command = ["cmd", "/c", "exit", "0"] if os.name == "nt" else ["sh", "-c", "true"]
    subprocess.run(command, check=True)
target.write_text(used.VALUE, encoding="utf-8")
with Path("writes.log").open("a", encoding="utf-8") as log:
    log.write(" ".join(options) + "\\n")
"""

_USED = 'VALUE = "one"\n'
_UNUSED = 'OTHER = "one"\n'
_CHILD = 'CHILD = "one"\n'


def _family(*producer: str) -> FixtureFamily:
    script = (PYTHON, "tools/produce.py")
    return FixtureFamily(
        name="sample",
        summary="A sample projection.",
        inputs=(
            InputGroup("producer", ("tools/produce.py", "tools/child_script.py")),
            InputGroup("product", ("src",), observed=True),
        ),
        check=(Command(script),),
        producer=Command((*script, *producer)),
        output_root="out",
        outputs=("*.json",),
        committed=False,
    )


def _checkout(root: Path) -> Path:
    (root / "tools").mkdir(parents=True)
    (root / "tools" / "produce.py").write_text(_PRODUCER, encoding="utf-8")
    (root / "tools" / "child_script.py").write_text("import pkg.child\n", encoding="utf-8")
    (root / "src" / "pkg").mkdir(parents=True)
    for name, text in (("__init__", ""), ("used", _USED), ("unused", _UNUSED), ("child", _CHILD)):
        (root / "src" / "pkg" / f"{name}.py").write_text(text, encoding="utf-8")
    (root / ".gitignore").write_text("__pycache__/\n", encoding="utf-8")
    (root / "out").mkdir()
    (root / "var" / "tmp").mkdir(parents=True)
    (root / "authority.json").write_text("{}", encoding="utf-8")
    return root


def _workspace(root: Path, family: FixtureFamily) -> Workspace:
    return Workspace(
        root=root,
        families=(family,),
        authority=lambda: _AUTHORITY,
        authority_source=lambda: root / "authority.json",
        persona_check=lambda: (),
        cache_directory=root.parent / "cache",
        scratch_root=root.parent / "scratch",
    )


def _edit(root: Path, member: str, text: str) -> None:
    (root / member).write_text(text, encoding="utf-8")


def _writes(root: Path) -> list[str]:
    log = root / "writes.log"
    return log.read_text(encoding="utf-8").splitlines() if log.exists() else []


def _status(workspace: Workspace):
    family = workspace.families[0]
    inputs = family_inputs(family, InputDigests(workspace.root), workspace.authority())
    return family_status(family, workspace.root, inputs, cache_directory=workspace.cache_directory)


def _stamp(workspace: Workspace) -> dict[str, Any]:
    path = stamp_path(workspace.families[0], workspace.root, cache_directory=workspace.cache_directory)
    return json.loads(path.read_text(encoding="utf-8"))


def _seeded(tmp_path: Path, *producer: str) -> tuple[Path, Workspace]:
    root = _checkout(tmp_path / "repo")
    workspace = _workspace(root, _family(*producer))
    assert seed([], force=False, workspace=workspace) == 0
    return root, workspace


def test_a_change_to_an_input_the_producer_imported_makes_the_family_stale_and_seed_reproduces_it(
    tmp_path: Path,
) -> None:
    root, workspace = _seeded(tmp_path)
    observation = _stamp(workspace)["observation"]
    assert observation["mode"] == OBSERVED_MODE
    assert "src/pkg/used.py" in observation["files"]
    assert _status(workspace).state is FixtureState.FRESH

    _edit(root, "src/pkg/used.py", 'VALUE = "two"\n')

    result = _status(workspace)
    assert result.state is FixtureState.STALE
    assert "observed: src/pkg/used.py changed" in result.reasons
    assert seed([], force=False, workspace=workspace) == 0
    assert _writes(root) == ["", ""]
    assert (root / "out" / "fixture.json").read_text(encoding="utf-8") == "two"
    assert _status(workspace).state is FixtureState.FRESH


def test_a_product_change_the_producer_never_read_leaves_the_family_fresh(tmp_path: Path) -> None:
    root, workspace = _seeded(tmp_path)

    _edit(root, "src/pkg/unused.py", 'OTHER = "two"\n')

    assert _status(workspace).state is FixtureState.FRESH
    assert seed([], force=False, workspace=workspace) == 0
    assert _writes(root) == [""]
    assert "src/pkg/unused.py" not in _stamp(workspace)["observation"]["files"]


@pytest.mark.parametrize(
    ("option", "reason"),
    [
        pytest.param("--isolated-child", "isolated from the inherited observer", id="isolated-python-child"),
        pytest.param("--native-child", "unobserved child process", id="non-python-child"),
    ],
)
def test_a_child_the_observer_cannot_cover_keys_the_family_on_its_whole_product_source(
    tmp_path: Path, option: str, reason: str
) -> None:
    root, workspace = _seeded(tmp_path, option)

    observation = _stamp(workspace)["observation"]
    assert observation["mode"] == CLOSURE_MODE
    assert any(reason in recorded for recorded in observation["reasons"]), observation["reasons"]
    assert "src/pkg/unused.py" in observation["groups"]["product"]
    assert _status(workspace).state is FixtureState.FRESH

    _edit(root, "src/pkg/unused.py", 'OTHER = "two"\n')

    result = _status(workspace)
    assert result.state is FixtureState.STALE
    assert "product: src/pkg/unused.py changed" in result.reasons
    assert seed([], force=False, workspace=workspace) == 0
    assert _writes(root) == [option, option]


@pytest.mark.parametrize("option", ["--child-c", "--child-script", "--child-module-without-site"])
def test_a_python_child_started_with_the_inherited_environment_is_covered(tmp_path: Path, option: str) -> None:
    root, workspace = _seeded(tmp_path, option)

    observation = _stamp(workspace)["observation"]
    assert observation["mode"] == OBSERVED_MODE, observation
    assert "src/pkg/child.py" in observation["files"]

    _edit(root, "src/pkg/unused.py", 'OTHER = "two"\n')
    assert _status(workspace).state is FixtureState.FRESH

    _edit(root, "src/pkg/child.py", 'CHILD = "two"\n')
    result = _status(workspace)
    assert result.state is FixtureState.STALE
    assert "observed: src/pkg/child.py changed" in result.reasons
    assert seed([], force=False, workspace=workspace) == 0
    assert _writes(root) == [option, option]


def test_a_changed_authority_identity_is_stale_in_observed_mode(tmp_path: Path) -> None:
    root, workspace = _seeded(tmp_path)
    republished = replace(workspace, authority=lambda: {**_AUTHORITY, "database_sha256": "c" * 64})

    result = _status(republished)

    assert result.state is FixtureState.STALE
    assert result.reasons == ("authority: database_sha256 changed",)
    assert seed([], force=False, workspace=republished) == 0
    assert _writes(root) == ["", ""]
    assert _status(republished).state is FixtureState.FRESH


def test_a_changed_declaration_is_stale_in_observed_mode(tmp_path: Path) -> None:
    root, workspace = _seeded(tmp_path)
    redeclared = replace(workspace, families=(_family("--variant"),))

    result = _status(redeclared)

    assert result.state is FixtureState.STALE
    assert "declaration changed" in result.reasons
    assert seed([], force=False, workspace=redeclared) == 0
    assert _writes(root) == ["", "--variant"]
    assert _status(redeclared).state is FixtureState.FRESH


def test_a_failed_producer_never_replaces_a_fresh_stamp(tmp_path: Path) -> None:
    root, workspace = _seeded(tmp_path)
    stamp = stamp_path(workspace.families[0], root, cache_directory=workspace.cache_directory)
    recorded = stamp.read_bytes()

    _edit(root, "src/pkg/used.py", 'import sys\nsys.exit(3)\nVALUE = "two"\n')

    assert seed([], force=False, workspace=workspace) == 1
    assert stamp.read_bytes() == recorded
    assert _status(workspace).state is FixtureState.STALE
    assert (root / "out" / "fixture.json").read_text(encoding="utf-8") == "one"
    assert _writes(root) == [""]


def test_a_failed_first_run_leaves_no_stamp(tmp_path: Path) -> None:
    root = _checkout(tmp_path / "repo")
    workspace = _workspace(root, _family())
    _edit(root, "src/pkg/used.py", 'import sys\nsys.exit(3)\nVALUE = "two"\n')

    assert seed([], force=False, workspace=workspace) == 1

    assert not stamp_path(workspace.families[0], root, cache_directory=workspace.cache_directory).exists()
    assert _status(workspace).state is FixtureState.MISSING
    assert _writes(root) == []


def test_the_familys_own_outputs_read_back_by_the_producer_are_not_inputs(tmp_path: Path) -> None:
    root, workspace = _seeded(tmp_path, "--read-output")
    # The forced run reads the output the first run left, then rewrites it.
    assert seed([], force=True, workspace=workspace) == 0
    assert _writes(root) == ["--read-output", "--read-output"]

    observation = _stamp(workspace)["observation"]
    assert observation["mode"] == OBSERVED_MODE
    members = [*observation["files"], *observation["listings"]]
    assert not [member for member in members if member == "out" or member.startswith("out/")], members
    assert _status(workspace).state is FixtureState.FRESH
    assert seed([], force=False, workspace=workspace) == 0
    assert _writes(root) == ["--read-output", "--read-output"]


def test_a_file_added_beside_an_imported_module_makes_the_family_stale(tmp_path: Path) -> None:
    root, workspace = _seeded(tmp_path)
    assert "src/pkg" in _stamp(workspace)["observation"]["listings"]

    _edit(root, "src/pkg/sibling.py", 'ADDED = "one"\n')

    result = _status(workspace)
    assert result.state is FixtureState.STALE
    assert "observed: listing of src/pkg changed" in result.reasons
    assert seed([], force=False, workspace=workspace) == 0
    assert _writes(root) == ["", ""]


def test_run_scratch_made_under_the_checkout_and_read_by_a_child_is_not_an_input(tmp_path: Path) -> None:
    root, workspace = _seeded(tmp_path, "--scratch-child")

    observation = _stamp(workspace)["observation"]
    assert observation["mode"] == OBSERVED_MODE, observation
    assert "src/pkg/child.py" in observation["files"]
    members = [*observation["files"], *observation["listings"]]
    assert not [member for member in members if member.startswith("var/tmp/")], members
    assert list((root / "var" / "tmp").iterdir()) == []
    assert _status(workspace).state is FixtureState.FRESH
    assert seed([], force=False, workspace=workspace) == 0
    assert _writes(root) == ["--scratch-child"]

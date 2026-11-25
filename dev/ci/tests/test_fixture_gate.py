"""The hosted fixture gate: it produces what a bare checkout lacks and still fails every real defect.

Each case builds an isolated checkout under ``tmp_path`` with a real producer
process, so the gate is proven against planted defects: a stale committed
output, a failing producer and a producer whose two renderings differ.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from dev.fixture_projections.cli import Workspace, check
from dev.fixture_projections.registry import FAMILIES, PYTHON, Command, FixtureFamily, InputGroup
from dev.paths import REPO_ROOT

from ..fixture_gate import run, stored_comparison_families

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint]

_AUTHORITY = {"database_sha256": "a" * 64, "logical_generation": "b" * 64}

#: Renders ``<folder>/fixture.json`` from ``inputs/source.txt``; ``--check`` compares and writes nothing.
_PRODUCER = """\
import os, sys
from pathlib import Path

rendered = Path("inputs/source.txt").read_text(encoding="utf-8").upper()
if "--random" in sys.argv:
    rendered += os.urandom(8).hex()
if "--fail" in sys.argv:
    sys.exit(3)
target = Path(sys.argv[1]) / "fixture.json"
if "--check" in sys.argv:
    sys.exit(0 if target.is_file() and target.read_text(encoding="utf-8") == rendered else 1)
target.write_text(rendered, encoding="utf-8")
"""


def _family(name: str, *, committed: bool, proves: bool = True, flags: tuple[str, ...] = ()) -> FixtureFamily:
    script = (PYTHON, "tools/produce.py", name, *flags)
    return FixtureFamily(
        name=name,
        summary="A sample projection.",
        inputs=(InputGroup("producer", ("tools/produce.py",)), InputGroup("source", ("inputs",))),
        check=(Command((*script, "--check")),),
        producer=Command(script),
        output_root=name,
        outputs=("*.json",),
        committed=committed,
        check_proves_outputs=proves,
    )


def _workspace(root: Path, *families: FixtureFamily) -> Workspace:
    (root / "tools").mkdir(parents=True)
    (root / "tools" / "produce.py").write_text(_PRODUCER, encoding="utf-8")
    (root / "inputs").mkdir()
    (root / "inputs" / "source.txt").write_text("hello", encoding="utf-8")
    for family in families:
        (root / family.name).mkdir()
    (root / "authority.json").write_text("{}", encoding="utf-8")
    return Workspace(
        root=root,
        families=families,
        authority=lambda: _AUTHORITY,
        authority_source=lambda: root / "authority.json",
        persona_check=lambda: (),
        cache_directory=root.parent / "cache",
        scratch_root=root.parent / "scratch",
    )


def test_a_bare_checkout_fails_the_plain_check_and_passes_the_gate(tmp_path: Path) -> None:
    workspace = _workspace(tmp_path / "repo", _family("generated", committed=False))

    assert check((), determinism=False, workspace=workspace) == 1
    assert run(workspace) == 0
    assert (workspace.root / "generated" / "fixture.json").read_text(encoding="utf-8") == "HELLO"


def test_a_stale_committed_output_still_fails_and_is_not_rewritten(tmp_path: Path) -> None:
    workspace = _workspace(
        tmp_path / "repo", _family("generated", committed=False), _family("committed", committed=True)
    )
    stored = workspace.root / "committed" / "fixture.json"
    stored.write_text("OLD", encoding="utf-8")

    assert run(workspace) == 1
    assert stored.read_text(encoding="utf-8") == "OLD"


def test_a_failing_producer_fails_the_gate(tmp_path: Path) -> None:
    workspace = _workspace(tmp_path / "repo", _family("generated", committed=False, flags=("--fail",)))

    assert run(workspace) != 0


def test_a_producer_whose_second_rendering_differs_fails_the_gate(tmp_path: Path) -> None:
    workspace = _workspace(tmp_path / "repo", _family("generated", committed=False, flags=("--random",)))

    assert run(workspace) == 1
    assert (workspace.root / "generated" / "fixture.json").is_file()


def test_only_generated_families_whose_check_compares_stored_output_are_produced() -> None:
    families = (
        _family("generated", committed=False),
        _family("committed", committed=True),
        _family("unproven", committed=False, proves=False),
    )

    assert stored_comparison_families(families) == ("generated",)


def test_the_declared_families_give_the_gate_something_to_produce_and_nothing_committed() -> None:
    declared = {family.name: family for family in FAMILIES}
    selected = stored_comparison_families(FAMILIES)

    assert selected
    assert all(not declared[name].committed for name in selected)


def test_the_merge_gate_runs_the_fixture_gate_recipe() -> None:
    workflow = (REPO_ROOT / ".github" / "workflows" / "merge-gate.yml").read_text(encoding="utf-8")
    justfile = (REPO_ROOT / "justfile").read_text(encoding="utf-8")

    assert "run: just fixtures-gate\n" in workflow
    assert "run: just fixtures-check\n" not in workflow
    assert f"fixtures-gate:\n    @uv run --no-sync python -m {run.__module__}\n" in justfile

"""A `just <name>` a reachability walk trusts must name a recipe that exists.

`ci_invoked_recipe_triggers` closes over recipe-to-recipe calls through
``bodies.get(name, "")``. That default is load-bearing and must stay: the
callee regex matches the word after any `just`, and a justfile body can contain
that word without calling anything -- `workstation-tools` iterates
``for tool in uv just node npx``, from which the walk harvests `node`. Raising
instead of defaulting would crash the walk on that shell word list.

What the default cannot distinguish is the other population: a workflow, or a
recipe body, naming a recipe that has been RENAMED. The walk reads it as
invoking nothing, every lane behind it drops out of the reached set, and the
module that answers which tests a lane runs answers "none" without a word. The
default is the right behaviour for the traversal and the wrong answer to leave
unmeasured, so resolution is asserted here rather than enforced there.
"""

from __future__ import annotations

from pathlib import Path
from typing import Final

import pytest

from ..._paths import REPO_ROOT
from ..lane_reachability import _recipe_bodies, _recipes_invoked_by, _workflow_run_steps

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint]

_UTF_8: Final = "utf-8"

#: The callee matches that are not calls, keyed by the recipe they appear in.
#:
#: Keyed by the PAIR, not by the bare word: the exemption is the context, not
#: the name. `workstation-tools` runs ``for tool in uv just node npx``, so the
#: word after `just` is a loop element. Were `node` ever declared as a recipe
#: the pair would stop being unresolved and would simply resolve; were a second
#: shell word list added, it would be named here rather than absorbed.
_NOT_CALLS: Final = frozenset({("workstation-tools", "node")})


def _declared_recipes(root: Path) -> frozenset[str]:
    """Return every recipe name the justfile declares.

    Read from raw text rather than resolved text on purpose: `{{...}}`
    substitution changes command arguments, never recipe headers, and asking
    `just --evaluate` would make a name-resolution gate depend on an external
    tool being installed.
    """
    justfile = root / "justfile"
    return frozenset(_recipe_bodies(justfile.read_text(encoding=_UTF_8))) if justfile.exists() else frozenset()


def _workflow_callees(root: Path) -> dict[str, set[str]]:
    """Return each recipe name a workflow `run:` step invokes, mapped to the lanes naming it.

    Both suffixes Actions reads are swept. The walk under test globs "*.yml"
    alone, so a lane filed as .yaml would be invisible to it AND to a gate that
    copied the same glob -- the failure would look exactly like a clean sweep.
    """
    callees: dict[str, set[str]] = {}
    workflow_dir = root / ".github" / "workflows"
    if not workflow_dir.is_dir():
        return callees
    for workflow in sorted(path for path in workflow_dir.iterdir() if path.suffix in (".yml", ".yaml")):
        for step in _workflow_run_steps(workflow.read_text(encoding=_UTF_8), ()):
            for name in _recipes_invoked_by(step.command):
                callees.setdefault(name, set()).add(workflow.name)
    return callees


def _body_callees(root: Path) -> dict[str, set[str]]:
    """Return each recipe name a recipe body invokes, mapped to the calling recipes."""
    justfile = root / "justfile"
    bodies = _recipe_bodies(justfile.read_text(encoding=_UTF_8)) if justfile.exists() else {}
    callees: dict[str, set[str]] = {}
    for caller, text in bodies.items():
        for name in _recipes_invoked_by(text):
            callees.setdefault(name, set()).add(caller)
    return callees


def _unresolved_workflow_callees(root: Path) -> list[str]:
    """Return every workflow `just` call naming no declared recipe."""
    declared = _declared_recipes(root)
    return [
        f"{workflow} runs `just {name}`, which no justfile recipe declares"
        for name, workflows in sorted(_workflow_callees(root).items())
        if name not in declared
        for workflow in sorted(workflows)
    ]


def test_every_workflow_just_call_names_a_declared_recipe() -> None:
    """No lane invokes a recipe that has been renamed out from under it."""
    callees = _workflow_callees(REPO_ROOT)

    assert callees, "no workflow `just` call was found at all; the sweep, not the repository, is empty"
    assert _declared_recipes(REPO_ROOT), "no justfile recipe was parsed; every name would read as unresolved"
    assert _unresolved_workflow_callees(REPO_ROOT) == []


def test_every_recipe_body_callee_resolves_or_is_a_named_shell_word_list() -> None:
    """A recipe-to-recipe call resolves, or is one of the matches classified as not a call."""
    declared = _declared_recipes(REPO_ROOT)
    unresolved = {
        (caller, name)
        for name, callers in _body_callees(REPO_ROOT).items()
        if name not in declared
        for caller in callers
    }

    assert unresolved == set(_NOT_CALLS)


def test_a_renamed_recipe_is_named_rather_than_read_as_invoking_nothing(tmp_path: Path) -> None:
    """The check detects the defect it exists for, and stays silent without it.

    Both directions in one test because either alone is worthless: a check that
    never fires and a check that always fires read the same on a healthy tree.
    """
    workflows = tmp_path / ".github" / "workflows"
    workflows.mkdir(parents=True)
    workflows.joinpath("lane.yml").write_text(
        "name: t\non: [push]\njobs:\n  j:\n    runs-on: ubuntu-latest\n"
        "    steps:\n      - name: run the lane\n        run: just lint\n",
        encoding=_UTF_8,
    )
    justfile = tmp_path / "justfile"

    justfile.write_text("lint:\n    echo linting\n", encoding=_UTF_8)
    assert _unresolved_workflow_callees(tmp_path) == []

    justfile.write_text("lint-all:\n    echo linting\n", encoding=_UTF_8)
    assert _unresolved_workflow_callees(tmp_path) == ["lane.yml runs `just lint`, which no justfile recipe declares"]


def test_a_recipe_named_only_in_a_comment_is_not_read_as_invoked() -> None:
    """A recipe body is a script with prose in it, and prose invokes nothing.

    Six comment lines in this repository's justfile name a real recipe inside an
    explanatory sentence -- "Verify the result with `just playwright-doctor`" --
    and reading the raw body counted every one as a call. Five of those recipes
    were invoked for real elsewhere, so they cost nothing. ``check-rag`` was
    reached by nothing else and was reported CI-invoked on the strength of a
    sentence mentioning it.

    The direction is what makes it worth a test. A phantom call ADDS a recipe to
    the reached set, so the lanes behind it read as covered by CI when no
    workflow runs them -- the walk goes quiet about a real hole instead of
    naming one. Both directions are asserted, because a reader that resolved
    nothing would satisfy the negative half on its own.
    """
    body = "    echo building\n    # Verify the result with `just playwright-doctor`.\n    just lint\n"

    assert _recipes_invoked_by(body) == {"lint"}
    assert _recipes_invoked_by("    # just playwright-doctor\n") == set()
    assert _recipes_invoked_by("    just playwright-doctor\n") == {"playwright-doctor"}

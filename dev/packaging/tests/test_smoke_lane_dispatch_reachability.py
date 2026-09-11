"""Every packaging smoke lane module must be reachable from some dispatch surface.

A lane module is only a proof if something runs it. ``smoke_absent_llm`` shipped
complete -- guards derived from the production call sites, a positive control, an
uninstall step -- and was invoked by nothing: not the campaign registry, not a
justfile recipe, not a workflow. Every assertion it makes was true and none of
them was ever evaluated, which is indistinguishable from a passing lane in every
report anyone reads.

The check is deliberately a REACHABILITY property rather than an enrolment one.
A lane may dispatch through the campaign lane registry, straight from a justfile
recipe, or from a workflow step. Today every lane but one reaches the registry
and ``smoke_homebrew`` is dispatched from its own workflow, while no lane uses
the justfile route at all -- so demanding registry enrolment would red one
correctly wired lane, which is why the property stays reachability rather than
enrolment. What cannot be legitimate is a lane module reachable from none of the
three.

No tally is pinned. The gate derives both sides at read time: the module set from
the directory, the dispatched set from the dispatch surfaces. Adding a lane and
wiring it passes; adding a lane and forgetting to wire it fails, which is the one
outcome that matters.

BOTH SIDES WERE ONCE NARROWER THAN THE QUESTION, in the same way the gate exists
to catch, so both are stated rather than left to the reader.

The module set was globbed ``smoke_*.py``. ``all_extra_smoke`` is a registered
core form and a smoke lane by every other measure, and its name puts the word at
the END, so the population the gate quantified over held eight of the nine lanes
and the one it could not see was the oddly-named one -- the member a naming
convention is least likely to keep and a reader is least likely to miss twice.
It was wired, so the gate was green and would have stayed green had it been
unwired. Both spellings are read now.

The dispatch set was the RAW text of each surface, so a lane named in a comment
counted as dispatched: a commented-out invocation, or a module named in a
rationale note above the command that replaced it, satisfies a substring test
while nothing runs it. That is precisely the defect
:mod:`dev.ci.workflow_run_text` was written to remove, and this gate -- the one
whose whole subject is a lane that looks dispatched and is not -- was reading
the surfaces the way that module exists to forbid. The surfaces are filtered
through it now.
"""

from __future__ import annotations

from pathlib import Path
from typing import Final

import pytest

from cadrumo.core.directory_scan import iter_directory, scan_directory
from dev._paths import REPO_ROOT as _REPO_ROOT
from dev.ci.workflow_run_text import executed_text

from ..campaign import _LANES

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint]

_PACKAGING = Path(__file__).resolve().parents[1]
_WORKFLOWS = _REPO_ROOT / ".github" / "workflows"


#: Both spellings a lane module in this package uses. A single ``smoke_*.py``
#: glob held eight of the nine lanes and silently dropped ``all_extra_smoke``.
_LANE_PATTERNS: Final = ("smoke_*.py", "*_smoke.py")


def _lane_module_stems() -> frozenset[str]:
    """Return the stem of every packaging smoke-lane module in the tree.

    Reads both name orders. The word ``smoke`` leads in eight of the lane
    modules and trails in one, and a population defined by the majority
    spelling cannot see the minority one -- which is the member most likely to
    be forgotten when it is wired, and the member whose absence from the
    population is hardest to notice, because the gate stays green either way.
    """
    return frozenset(path.stem for pattern in _LANE_PATTERNS for path in iter_directory(_PACKAGING, pattern=pattern))


def _dispatch_sources() -> dict[str, str]:
    """Return the EXECUTED text of every surface that can invoke a lane.

    Read as text on purpose. A workflow step and a justfile recipe both invoke a
    lane as a shell word, so there is no structure to walk; what matters is that
    the module is NAMED somewhere a runner will execute.

    "Will execute" is the whole load-bearing word, and reading the file raw does
    not carry it. A whole-line comment is prose in both formats -- ``#`` opens
    one in YAML and in a justfile alike -- so a commented-out invocation names
    the module without running it, and a substring test over raw text calls that
    dispatch. :func:`~dev.ci.workflow_run_text.executed_text` drops exactly
    those lines and nothing else.
    """
    sources = {"justfile": executed_text((_REPO_ROOT / "justfile").read_text(encoding="utf-8"))}
    for workflow in scan_directory(_WORKFLOWS, pattern="*.yml"):
        sources[f"workflow:{workflow.name}"] = executed_text(workflow.read_text(encoding="utf-8"))
    return sources


def _campaign_registered_stems() -> frozenset[str]:
    """Return the module stems the campaign lane registry dispatches."""
    return frozenset(form.module.rsplit(".", 1)[-1] for lane in _LANES.values() for form in lane.forms)


def unreachable_lane_modules(
    stems: frozenset[str],
    registered: frozenset[str],
    sources: dict[str, str],
) -> frozenset[str]:
    """Return the lane stems no dispatch surface names.

    Takes its inputs rather than reading them, so the detector can be driven with
    a constructed case and shown to report a genuinely unreachable module. A gate
    that only ever sees a healthy tree cannot demonstrate it is able to say no.

    Both spellings a runner uses are accepted: the ``-m dev.packaging.<stem>``
    module form and the ``dev/packaging/<stem>.py`` path form, which the Homebrew
    workflow uses because it runs with ``--no-project``.
    """
    unreachable: set[str] = set()
    for stem in stems:
        if stem in registered:
            continue
        module_form = f"dev.packaging.{stem}"
        path_form = f"dev/packaging/{stem}.py"
        if any(module_form in text or path_form in text for text in sources.values()):
            continue
        unreachable.add(stem)
    return frozenset(unreachable)


def test_the_tree_actually_has_lane_modules_and_dispatch_surfaces_to_read() -> None:
    """Anti-vacuity: an empty module set or an unreadable surface would pass silently.

    The reachability assertion below quantifies over the discovered module set,
    so a glob that stopped matching would make it hold over nothing and read as a
    pass. The same is true of the dispatch surfaces: if the justfile moved and
    every read came back empty, the gate would flip to reporting every lane
    unreachable rather than passing -- but an empty workflow directory would
    silently narrow what counts as dispatched.
    """
    stems = _lane_module_stems()
    assert stems, f"no {' / '.join(_LANE_PATTERNS)} lane modules found under {_PACKAGING}; every check below is vacuous"
    sources = _dispatch_sources()
    assert sources, "no dispatch surfaces were read"
    assert any(name.startswith("workflow:") for name in sources), (
        f"no workflows were read from {_WORKFLOWS}; lanes dispatched only from CI would read as unreachable"
    )
    assert all(text.strip() for text in sources.values()), (
        f"empty dispatch surfaces: {sorted(name for name, text in sources.items() if not text.strip())}"
    )
    assert _campaign_registered_stems(), "the campaign lane registry dispatches no module"


def test_every_smoke_lane_module_is_reachable_from_some_dispatch_surface() -> None:
    """A lane nothing invokes proves nothing, however complete its assertions are."""
    unreachable = unreachable_lane_modules(
        _lane_module_stems(),
        _campaign_registered_stems(),
        _dispatch_sources(),
    )
    assert not unreachable, (
        "these packaging smoke lanes are invoked by nothing -- not the campaign lane registry, not a "
        f"justfile recipe, not a workflow: {sorted(unreachable)}. Each is dead capacity whose assertions "
        "are never evaluated, which is indistinguishable from a lane that passes. Register the lane in "
        "dev/packaging/campaign.py so a profile runs it, or give it a justfile recipe or a workflow step."
    )


def test_the_detector_reports_a_module_no_surface_names() -> None:
    """Positive control: the check must be able to return a non-empty answer.

    Without this, the assertion above is satisfied by a detector that returns the
    empty set unconditionally -- a broken glob, an over-broad substring match, or
    a helper that swallowed its own loop would all pass while proving nothing.
    The constructed module name cannot appear in any real surface, so its absence
    is guaranteed while the two dispatched neighbours in the same call establish
    that the detector is not simply reporting everything.
    """
    stems = frozenset({"smoke_registered_one", "smoke_recipe_one", "smoke_orphan_one"})
    sources = {"justfile": "uv run python -m dev.packaging.smoke_recipe_one --cohort-dir x"}
    unreachable = unreachable_lane_modules(stems, frozenset({"smoke_registered_one"}), sources)
    assert unreachable == frozenset({"smoke_orphan_one"}), (
        f"the detector must report exactly the module no surface names; it returned {sorted(unreachable)}"
    )


def test_the_detector_accepts_the_path_spelling_a_no_project_workflow_uses() -> None:
    """The path form is a real dispatch spelling, not a courtesy.

    The Homebrew workflow runs its lane with ``uv run --no-project python
    dev/packaging/smoke_homebrew.py``, so a detector that only recognised the
    ``-m`` module form would report a correctly-wired lane as an orphan and the
    gate would be fixed by breaking the workflow.
    """
    sources = {"workflow:x.yml": "uv run --no-project python dev/packaging/smoke_path_one.py --cleanup"}
    assert unreachable_lane_modules(frozenset({"smoke_path_one"}), frozenset(), sources) == frozenset()


def test_the_population_holds_the_lane_whose_name_puts_smoke_last() -> None:
    """The gate's own population had the blind spot the gate exists to report.

    ``all_extra_smoke`` is a registered core form -- the campaign dispatches it
    -- and a ``smoke_*.py`` glob does not match it. So the module set the
    reachability assertion quantified over was one short, and short by exactly
    the lane whose name breaks the convention: unwiring it would have left this
    file green, which is the outcome it was written to make impossible.

    Pinned to the module rather than to a tally, so adding or deleting a lane
    never edits this, and re-narrowing the glob fails here rather than passing
    quietly with a smaller population.
    """
    stems = _lane_module_stems()

    assert "all_extra_smoke" in stems, (
        f"the lane population {sorted(stems)} omits `all_extra_smoke`, a campaign-registered core "
        "form. A population defined by the majority name order cannot see the minority one, and the "
        "gate reads as passing whether or not that lane is dispatched."
    )
    assert not "all_extra_smoke".startswith("smoke_"), (
        "this case is only meaningful while the lane's name still trails `smoke`"
    )


def test_a_lane_named_only_in_a_comment_does_not_count_as_dispatched() -> None:
    """Teeth for the executed-lines discipline, on both surface formats.

    A commented-out invocation is the exact shape of the defect: the module is
    named, a reader scanning the file sees it, and nothing runs it. Driven with
    constructed surfaces, so the proof does not depend on the tree happening to
    contain a commented-out lane -- it does not, which is why the blindness was
    latent rather than firing.
    """
    commented = {
        "justfile": executed_text("# uv run python -m dev.packaging.smoke_ghost_one --cohort-dir x\n"),
        "workflow:x.yml": executed_text("        # run: uv run python dev/packaging/smoke_ghost_two.py\n"),
    }
    stems = frozenset({"smoke_ghost_one", "smoke_ghost_two"})

    assert unreachable_lane_modules(stems, frozenset(), commented) == stems, (
        "a lane whose only mention sits behind a `#` is not dispatched by anything; counting it "
        "as reachable is the substring defect dev.ci.workflow_run_text exists to remove"
    )


def test_the_live_dispatch_surfaces_survive_the_comment_filter() -> None:
    """The filter must not be strong enough to unwire a real lane.

    The Homebrew workflow is the one lane dispatched by text rather than by the
    campaign registry, so it is the surface a comment filter could break. If
    stripping comments dropped its invocation, the gate would go red and the
    "fix" would be to break the workflow.
    """
    sources = _dispatch_sources()

    assert any("dev/packaging/smoke_homebrew.py" in text for text in sources.values()), (
        "the executed text of no dispatch surface names the Homebrew lane; the comment filter has "
        f"removed a real invocation. Surfaces read: {sorted(sources)}"
    )

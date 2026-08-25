"""Every packaging smoke lane module must be reachable from some dispatch surface.

A lane module is only a proof if something runs it. ``smoke_absent_llm`` shipped
complete -- guards derived from the production call sites, a positive control, an
uninstall step -- and was invoked by nothing: not the campaign registry, not a
justfile recipe, not a workflow. Every assertion it makes was true and none of
them was ever evaluated, which is indistinguishable from a passing lane in every
report anyone reads.

The check is deliberately a REACHABILITY property rather than an enrolment one.
Lanes legitimately dispatch three different ways -- through the campaign lane
registry, straight from a justfile recipe, or from a workflow step -- and
demanding one of those would red the four lanes that correctly use another. What
cannot be legitimate is a lane module reachable from none of them.

No tally is pinned. The gate derives both sides at read time: the module set from
the directory, the dispatched set from the dispatch surfaces. Adding a lane and
wiring it passes; adding a lane and forgetting to wire it fails, which is the one
outcome that matters.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from cadrumo.core import iter_directory, scan_directory

from ..._paths import REPO_ROOT as _REPO_ROOT
from ..campaign import _LANES

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint]

_PACKAGING = Path(__file__).resolve().parents[1]
_WORKFLOWS = _REPO_ROOT / ".github" / "workflows"


def _lane_module_stems() -> frozenset[str]:
    """Return the stem of every packaging smoke-lane module in the tree."""
    return frozenset(path.stem for path in iter_directory(_PACKAGING, pattern="smoke_*.py"))


def _dispatch_sources() -> dict[str, str]:
    """Return the text of every surface that can invoke a lane, keyed by a label.

    Read as text on purpose. A workflow step and a justfile recipe both invoke a
    lane as a shell word, so there is no structure to walk; what matters is that
    the module is NAMED somewhere a runner will execute.
    """
    sources = {"justfile": (_REPO_ROOT / "justfile").read_text(encoding="utf-8")}
    for workflow in scan_directory(_WORKFLOWS, pattern="*.yml"):
        sources[f"workflow:{workflow.name}"] = workflow.read_text(encoding="utf-8")
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
    assert stems, f"no smoke_*.py lane modules found under {_PACKAGING}; every check below is vacuous"
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

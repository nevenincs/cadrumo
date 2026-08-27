"""Resolving a command must not load the capabilities executing it will need.

Distinct from ``test_capability_family_isolation``, and the difference is the
whole point. That gate asks whether a node loads families its spec does not
DECLARE. This one asks whether it loads them at RESOLUTION at all -- including
families it is perfectly entitled to use once an operator actually runs it.

``app/live/verify/list`` is the worked example: it declares ``encrypted-facts``,
which entitles it to the persistence families, so the declaration gate passes
while it loads 179 storage modules merely being resolved. Nothing has been
asked for at that point. Resolution happens on the way to every sibling and on
every ``--help``, so work done there is paid by operators who never invoke the
command.

**Cost.** The expectation for a compliant node is *nothing*, and that makes the
sweep cheap: every node expected to be clean is resolved in ONE child process
and the union of what it loaded must be empty. An empty union means no
individual node loaded anything, so one process settles 351 nodes. The
exceptions are then probed one at a time, because there the claim is about each
node specifically.

Fourteen nodes do not defer yet. Each is named with what it loads and why, and
a stale case deletes an entry the moment the node stops loading -- so the list
cannot outlive the problem and start excusing a regression.
"""

from __future__ import annotations

import pytest

from .. import command_graph
from .test_capability_family_isolation import _loaded_families

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint]

#: Nodes whose resolution still loads capability families, with the cause.
#:
#: The causes are shared, not fourteen separate defects: a CommandSpec parameter
#: ANNOTATION is a deferred target, so building a node's Typer signature imports
#: whatever module owns each annotated type -- and several of those are package
#: roots that import heavy siblings eagerly.
_RESOLUTION_LOADERS: dict[str, str] = {
    "app/registry/manuals/list": "annotation resolves through application.registry -> application.filing root",
    "app/registry/manuals/rules": "annotation resolves through application.registry -> application.filing root",
    "app/registry/manuals/verify": "annotation resolves through application.registry -> application.filing root",
    "app/registry/manuals/view": "annotation resolves through application.registry -> application.filing root",
    "app/ledger/export": "annotation resolves through ledger.actions_common -> domain.modelos protocols",
    "app/ledger/import": "annotation resolves through ledger.actions_common -> domain.modelos protocols",
    "app/live/verify/latest": "annotation pulls the persistence families it may use only at execution",
    "app/live/verify/list": "annotation pulls the persistence families it may use only at execution",
    "config/auth/diagnostics/report": "annotation pulls the persistence families it may use only at execution",
    "app/modelo/work/verify": "annotation pulls registry and persistence it may use only at execution",
    "app/modelo/work/amend": "annotation pulls the registry it may use only at execution",
    "app/modelo/casillas": "annotation pulls the registry package root",
    "app/modelo/reconcile/import": "annotation pulls the registry package root",
    "app/review/queue": "annotation resolves through application.review -> domain.calculations",
}


def _all_paths() -> list[list[str]]:
    return [list(node.path[1:]) for node in command_graph.nodes()]


def _deferring_paths() -> list[list[str]]:
    return [path for path in _all_paths() if "/".join(path) not in _RESOLUTION_LOADERS]


def test_the_exception_list_names_only_live_nodes() -> None:
    """FIXTURE ANCHOR: an entry naming no live node would exempt nothing and hide nothing.

    A renamed or deleted command would leave its row matching no path, and the
    sweep below would quietly start covering it again -- or, worse, a typo would
    silently exempt a node that was never checked.
    """
    live = {"/".join(path) for path in _all_paths()}
    unknown = sorted(name for name in _RESOLUTION_LOADERS if name not in live)

    assert unknown == [], f"these exception rows name no live command: {unknown}"


def test_resolving_every_other_node_loads_no_capability_family() -> None:
    """DISCRIMINATING: the whole compliant surface resolves without loading anything.

    One child process resolves them all. The union being empty is exactly the
    claim that each of them loaded nothing.
    """
    paths = _deferring_paths()
    loaded = _loaded_families(paths)

    assert loaded == {}, (
        f"resolving the {len(paths)} nodes expected to defer loaded {loaded}. "
        "One of them gained an eager import on its resolution path; probe them "
        "individually to find which, because a union names the set and not the member."
    )


@pytest.mark.parametrize("name", sorted(_RESOLUTION_LOADERS))
def test_a_listed_node_that_now_defers_must_be_removed(name: str) -> None:
    """STALE-ENTRY: an exception that stopped applying must be deleted."""
    loaded = _loaded_families([name.split("/")])

    assert loaded != {}, (
        f"`aeat {name.replace('/', ' ')}` now resolves without loading any capability family, "
        f"so its _RESOLUTION_LOADERS entry is stale and must be removed: {_RESOLUTION_LOADERS[name]}"
    )

"""The Declarations workspace refuses a read action wired to another command.

The route factory and the controller each carried this check, in two copies
that were byte-identical and so looked safe. The Ledger workspace held exactly
that shape until its copies drifted — the factory refusing a non-canonical
review action while the controller checked nothing, so every caller building
the controller directly skipped the refusal. This suite pins the consolidated
guard and, structurally, that both paths reach it.

What the refusal prevents is not a crash: an action wired elsewhere gives the
workspace an affordance labelled for one operation that dispatches another, so
an operator reading their declarations runs a different application door than
the screen names.
"""

from __future__ import annotations

import ast
import inspect

import pytest

from .....application.operator_actions.models import ActionReference
from .. import controller as controller_module
from .. import routes as routes_module
from ..action_guards import REQUIRED_DECLARATIONS_TARGETS, require_canonical_declarations_actions

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint]

_WORK = ActionReference(action_id="operator.modelo.work.list")
_REVISIONS = ActionReference(action_id="operator.modelo.work.revisions")
_FILING = ActionReference(action_id="operator.modelo.filing_record.list")

_CANONICAL = {"work_action": _WORK, "revisions_action": _REVISIONS, "filing_action": _FILING}

#: Each slot paired with an action belonging to a different slot.
_MISWIRINGS = [
    pytest.param("work_action", _REVISIONS, id="work-wired-to-revisions"),
    pytest.param("revisions_action", _FILING, id="revisions-wired-to-filing"),
    pytest.param("filing_action", _WORK, id="filing-wired-to-work"),
]


def test_the_canonical_wiring_is_accepted() -> None:
    """The supported path, so the refusals below are not vacuous."""
    require_canonical_declarations_actions(**_CANONICAL)


@pytest.mark.parametrize(("slot", "wrong_action"), _MISWIRINGS)
def test_each_slot_refuses_another_slots_action(slot: str, wrong_action: ActionReference) -> None:
    """All three slots are mandatory, and each is checked separately.

    One case would pass while the other two accepted anything — the shape the
    split guard had before consolidation.
    """
    wiring = {**_CANONICAL, slot: wrong_action}

    with pytest.raises(ValueError, match="another application door"):
        require_canonical_declarations_actions(**wiring)


def test_every_declared_slot_is_actually_enforced() -> None:
    """A table entry the function never reads would look enforced and refuse nothing."""
    enforced = {attribute for attribute, _command_key in REQUIRED_DECLARATIONS_TARGETS}

    assert enforced == set(_CANONICAL)


def test_each_slot_names_a_distinct_command() -> None:
    """Two slots sharing a command key would let one accept the other's action."""
    command_keys = [command_key for _attribute, command_key in REQUIRED_DECLARATIONS_TARGETS]

    assert len(command_keys) == len(set(command_keys))


@pytest.mark.parametrize(
    ("module", "function"),
    [
        pytest.param(controller_module, "DeclarationsWorkspaceController", id="controller"),
        pytest.param(routes_module, "declarations_screen_factory", id="route-factory"),
    ],
)
def test_both_construction_paths_reach_the_shared_guard(module: object, function: str) -> None:
    """Structural, because two agreeing copies pass every behavioural test.

    That is exactly why the duplication survived here: the copies were
    identical, so nothing failed until one of them changed.
    """
    source = inspect.getsource(getattr(module, function))
    tree = ast.parse(source.lstrip())
    called = {node.func.id for node in ast.walk(tree) if isinstance(node, ast.Call) and isinstance(node.func, ast.Name)}

    assert "require_canonical_declarations_actions" in called


def test_no_construction_path_reimplements_the_check() -> None:
    """Proof the copies were removed rather than a third added.

    Matches the literal comparison both copies used, so a reintroduced inline
    check fails here even if it also calls the shared guard.
    """
    inline = [
        name
        for module, name in (
            (controller_module, "DeclarationsWorkspaceController"),
            (routes_module, "declarations_screen_factory"),
        )
        if "target_command_key" in inspect.getsource(getattr(module, name))
    ]

    assert inline == []

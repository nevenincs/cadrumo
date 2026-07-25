"""Routing proofs for the profile manager frontend seam.

``create`` and ``edit`` serve two audiences through one verb: an operator
at a terminal, who gets the manager, and a script or agent passing flags,
which gets the wizard and a JSON envelope. Getting that split wrong is
expensive in both directions — a script that opens a full-screen app
hangs forever, and an operator who wanted the manager silently gets a
wizard instead.

The decision is a pure function precisely so it can be exercised here
against real inputs rather than only through a terminal a headless test
host cannot provide. Every combination that matters is enumerated.
"""

from __future__ import annotations

import pytest

from .._manager_frontend import manager_is_the_right_frontend

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint]


def _route(**overrides: object) -> bool:
    """Evaluate the rule from the bare-interactive baseline."""
    call = {
        "mode": "edit",
        "scripted": False,
        "explicit_fields": False,
        "full_screen": True,
    }
    call.update(overrides)
    return manager_is_the_right_frontend(**call)  # type: ignore[arg-type]


def test_a_bare_interactive_invocation_opens_the_manager() -> None:
    assert _route(mode="edit")
    assert _route(mode="create")


@pytest.mark.parametrize("blocking", ["scripted", "explicit_fields"])
def test_a_scripted_or_flag_carrying_invocation_keeps_the_wizard(blocking: str) -> None:
    """Flags and --quiet both mean the caller wants no screen at all.

    An invocation carrying field values especially must not divert: the
    manager would open with those values unapplied and strand them.
    """
    assert not _route(mode="edit", **{blocking: True})
    assert not _route(mode="create", **{blocking: True})


def test_a_host_that_cannot_go_full_screen_keeps_the_wizard() -> None:
    """No capable terminal, no manager — this is what stops a CI hang."""
    assert not _route(mode="edit", full_screen=False)
    assert not _route(mode="create", full_screen=False)


def test_a_name_on_the_command_line_never_diverts_either_verb() -> None:
    """The rule takes no name at all, and that is the point.

    Routing ``create NAME`` to the wizard was the defect that made the
    registration screen unreachable: a name is the documented create
    shape, so an operator met the retired flow every time. A name now
    prefills the screen's name field instead of deciding which surface
    they get, which is why it is absent from the signature — a routing
    input that cannot be passed cannot be honoured by mistake.
    """
    import inspect

    parameters = set(inspect.signature(manager_is_the_right_frontend).parameters)
    assert "named" not in parameters, f"routing must not read a supplied name; takes {sorted(parameters)}"
    assert _route(mode="create")
    assert _route(mode="edit")

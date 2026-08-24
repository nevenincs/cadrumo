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

import inspect

import pytest
import typer

from .....application.wizard import build_wizard_command
from .....core.wizard_catalogue import get_setup_flow
from .._manager_dispatch import with_manager_frontend
from .._manager_frontend import has_explicit_profile_fields, manager_is_the_right_frontend

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


def test_explicit_tui_request_overrides_terminal_detection() -> None:
    assert _route(mode="create", full_screen=False, tui_requested=True)


def test_a_name_on_the_command_line_never_diverts_either_verb() -> None:
    """The rule takes no name at all, and that is the point.

    Routing ``create NAME`` to the wizard was the defect that made the
    registration screen unreachable: a name is the documented create
    shape, so an operator met the retired flow every time. A name now
    prefills the screen's name field instead of deciding which surface
    they get, which is why it is absent from the signature — a routing
    input that cannot be passed cannot be honoured by mistake.
    """
    parameters = set(inspect.signature(manager_is_the_right_frontend).parameters)
    assert "named" not in parameters, f"routing must not read a supplied name; takes {sorted(parameters)}"
    assert _route(mode="create")
    assert _route(mode="edit")


def test_empty_repeated_option_default_does_not_block_bare_manager() -> None:
    """Typer's empty checkbox default is not an explicit field value."""
    parsed_defaults = {
        "profile_name": "Primer Contacto",
        "quiet": False,
        "accept_defaults": False,
        "tui": True,
        "irpf_income_categories": [],
    }

    assert not has_explicit_profile_fields(parsed_defaults)
    assert has_explicit_profile_fields(
        {**parsed_defaults, "irpf_income_categories": ["actividad_economica"]},
    )


def test_create_profile_name_is_optional_for_registration_dispatch() -> None:
    """The registration TUI must be reachable before a name is supplied."""
    command = build_wizard_command(get_setup_flow(), mode="create")
    parameter = inspect.signature(command).parameters["profile_name"]

    assert parameter.default is None


def test_edit_profile_name_is_optional_for_active_profile_dispatch() -> None:
    """Typer must reach the manager before demanding an optional subject."""
    command = build_wizard_command(get_setup_flow(), mode="edit")
    parameter = inspect.signature(command).parameters["profile_name"]

    assert parameter.default is None


def test_manager_dispatch_callback_exposes_typer_context() -> None:
    """The manager branch must receive the context it uses for its envelope."""
    command = with_manager_frontend(build_wizard_command(get_setup_flow(), mode="create"), mode="create")
    parameter = inspect.signature(command).parameters["ctx"]

    assert parameter.kind is inspect.Parameter.POSITIONAL_OR_KEYWORD
    assert parameter.annotation is typer.Context

    app = typer.Typer()
    app.command()(command)
    click_command = typer.main.get_command(app)

    assert "ctx" not in {parameter.name for parameter in click_command.params}

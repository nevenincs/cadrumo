"""Which frontend ``aeat config login`` opens, and when it opens none.

The routing rule is the whole safety property of the login screen: an
operator at a terminal gets a page, and every other caller — a script, an
agent, a CI job, a ``--format json`` reader, a piped host — reaches the
existing prompt-and-envelope path untouched and never blocks on a screen
it cannot type into.

The rule is exercised directly as the pure predicate it is, because the
alternative is asking one test host to be six different terminals. The
resolved form is then exercised against the real host this suite runs
on, which is genuinely non-interactive — that is the CI case — and the
positive control beside it is what shows the refusal came from the host
rather than from a predicate that refuses everything.
"""

from __future__ import annotations

from typing import TypedDict

import pytest
import typer
from typer.core import TyperCommand

from .....tests.secure_sql import isolated_profile_storage_root
from .._login_frontend import login_screen_is_available, login_tui_is_the_right_frontend

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint]


class _RoutingInputs(TypedDict):
    """The exact keyword set :func:`login_tui_is_the_right_frontend` accepts."""

    named: bool
    secrets_stdin: bool
    headless_secret: bool
    json_format: bool
    full_screen: bool
    profile_count: int


def _interactive_operator(
    *,
    named: bool = False,
    secrets_stdin: bool = False,
    headless_secret: bool = False,
    json_format: bool = False,
    full_screen: bool = True,
    profile_count: int = 1,
) -> _RoutingInputs:
    """The one shape that gets a screen, with any single condition overridden.

    Defaults describe a bare ``aeat config login`` typed at a capable terminal
    on a machine that has a profile to open. Overrides are named parameters
    rather than a ``str``-keyed merge, so a typo in a case below is a type
    error instead of a silently-ignored extra key that would leave the case
    asserting the untouched interactive shape and passing for the wrong reason.
    """
    return {
        "named": named,
        "secrets_stdin": secrets_stdin,
        "headless_secret": headless_secret,
        "json_format": json_format,
        "full_screen": full_screen,
        "profile_count": profile_count,
    }


def test_a_bare_interactive_login_on_a_capable_host_opens_the_screen() -> None:
    """The positive control: without this, every case below proves nothing."""
    assert login_tui_is_the_right_frontend(**_interactive_operator()) is True


@pytest.mark.parametrize(
    "inputs",
    [
        pytest.param(_interactive_operator(named=True), id="named"),
        pytest.param(_interactive_operator(secrets_stdin=True), id="secrets_stdin"),
        pytest.param(_interactive_operator(headless_secret=True), id="headless_secret"),
        pytest.param(_interactive_operator(json_format=True), id="json_format"),
        pytest.param(_interactive_operator(full_screen=False), id="full_screen"),
        pytest.param(_interactive_operator(profile_count=0), id="profile_count"),
    ],
)
def test_each_condition_alone_sends_login_back_to_the_prompt(inputs: _RoutingInputs) -> None:
    """Any one condition is enough to fall through, with the others clear.

    Parametrised one at a time rather than in combination on purpose: a
    rule that only refused when several conditions coincided would still
    pass a combined case, and would open a screen on the CI host that
    happened to trip just one of them.
    """
    assert login_tui_is_the_right_frontend(**inputs) is False


def _context(*, output_format: str) -> typer.Context:
    """A real Typer context carrying the format the operator asked for.

    The command is a ``TyperCommand`` rather than a bare ``click.Command``:
    typer's ``Context`` declares typer's own ``Command``, and in this version
    that class does not subclass click's, so passing the click one worked only
    incidentally.
    """
    return typer.Context(TyperCommand("login"), obj={"format": output_format})


def test_this_non_interactive_host_never_reaches_the_screen(tmp_path) -> None:
    """The resolved rule fails closed on the host a CI job actually has.

    This suite runs with its output captured, so the capability probe
    classifies the host as non-interactive — the same classification a
    piped shell, a dumb terminal, and a CI runner get. Resolving the rule
    here is therefore the real scripted case, not a described one.
    """
    with isolated_profile_storage_root(tmp_path=tmp_path):
        assert login_screen_is_available(_context(output_format="text"), name=None, secrets_stdin=False) is False


def test_a_json_caller_never_reaches_the_screen(tmp_path) -> None:
    """A machine reading the envelope must not have a screen written over it."""
    with isolated_profile_storage_root(tmp_path=tmp_path):
        assert login_screen_is_available(_context(output_format="json"), name=None, secrets_stdin=False) is False


def test_a_named_profile_and_a_piped_secret_both_stay_on_the_prompt(tmp_path) -> None:
    """The two argument-shaped opt-outs resolve the same way as the pure rule."""
    with isolated_profile_storage_root(tmp_path=tmp_path):
        ctx = _context(output_format="text")
        assert login_screen_is_available(ctx, name="some-profile", secrets_stdin=False) is False
        assert login_screen_is_available(ctx, name=None, secrets_stdin=True) is False

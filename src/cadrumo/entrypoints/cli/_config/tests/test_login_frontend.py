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

import click
import pytest
import typer

from .....tests.secure_sql import isolated_profile_storage_root
from .._login_frontend import login_screen_is_available, login_tui_is_the_right_frontend

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint]


_INTERACTIVE_OPERATOR = {
    "named": False,
    "secrets_stdin": False,
    "headless_secret": False,
    "json_format": False,
    "full_screen": True,
    "profile_count": 1,
}
"""The one shape that gets a screen: a bare ``aeat config login`` typed at
a capable terminal on a machine that has a profile to open."""


def test_a_bare_interactive_login_on_a_capable_host_opens_the_screen() -> None:
    """The positive control: without this, every case below proves nothing."""
    assert login_tui_is_the_right_frontend(**_INTERACTIVE_OPERATOR) is True


@pytest.mark.parametrize(
    ("condition", "value"),
    [
        ("named", True),
        ("secrets_stdin", True),
        ("headless_secret", True),
        ("json_format", True),
        ("full_screen", False),
        ("profile_count", 0),
    ],
)
def test_each_condition_alone_sends_login_back_to_the_prompt(condition: str, value: object) -> None:
    """Any one condition is enough to fall through, with the others clear.

    Parametrised one at a time rather than in combination on purpose: a
    rule that only refused when several conditions coincided would still
    pass a combined case, and would open a screen on the CI host that
    happened to trip just one of them.
    """
    assert login_tui_is_the_right_frontend(**{**_INTERACTIVE_OPERATOR, condition: value}) is False


def _context(*, output_format: str) -> typer.Context:
    """A real Typer context carrying the format the operator asked for."""
    return typer.Context(click.Command("login"), obj={"format": output_format})


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

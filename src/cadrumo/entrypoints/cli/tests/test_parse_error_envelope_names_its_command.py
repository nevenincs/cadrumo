"""A parse-time refusal names the command when click already resolved one.

The shared envelope spine carries ``command`` so an operator -- which for this
CLI is an autonomous agent reading JSON -- can tell what failed from the
document alone. Runtime refusals populated it; argv-parse refusals did not, on
the reasoning that no command has resolved yet at parse time.

That reasoning holds for only half the cases. ``aeat frobnicate`` resolves
nothing and a null command is the honest answer. ``aeat config profile
preflight --bogus`` resolved the command and THEN rejected an option, and click
carries that resolution on the exception's own context -- so the spine reported
null while the answer was in hand.

Both directions are asserted together, because a fix that simply always named
something would be worse than the gap: it would invent a command for the case
that genuinely has none.
"""

from __future__ import annotations

import json

import pytest

from ....tests.cli_runner import invoke_cached_cli

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint]


def _envelope(*arguments: str) -> dict[str, object]:
    """Invoke the CLI in JSON mode and return the parsed error envelope."""
    result = invoke_cached_cli(["--format", "json", *arguments])
    document = (result.stdout or "").strip() or (result.output or "").strip()
    return json.loads(document.splitlines()[-1])


def test_an_unknown_option_names_the_command_it_was_given_to() -> None:
    """DISCRIMINATING: the command resolved, so the spine must say which.

    This is the shape an agent hits constantly -- a real command with one wrong
    flag -- and it was the shape reporting null.
    """
    envelope = _envelope("config", "profile", "preflight", "--modelo", "303", "--year", "2026")

    assert envelope["command"] == "config.profile.preflight"
    assert envelope["status"] == "error"


def test_an_unknown_command_still_reports_no_command() -> None:
    """ANTI-TAUTOLOGY: nothing resolved, so nothing may be named.

    Without this, naming the command could be satisfied by inventing one from
    the argv tokens, which would report a command that does not exist as the
    one that failed.
    """
    envelope = _envelope("frobnicate")

    assert envelope["command"] is None
    assert envelope["status"] == "error"

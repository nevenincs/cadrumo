"""A parse-time refusal names the command when click already resolved one.

The shared envelope spine carries ``command`` so an operator -- which for this
CLI is an autonomous agent reading JSON -- can tell what failed from the
document alone. Runtime refusals populated it; argv-parse refusals did not, on
the reasoning that no command has resolved yet at parse time.

That reasoning holds for only half the cases. ``aeat frobnicate`` resolves
nothing and a null command is the honest answer. ``aeat config profile status
--bogus`` resolved the command and THEN rejected an option, and click carries
that resolution on the exception's own context -- so the spine reported null
while the answer was in hand.

Both directions are asserted together, because a fix that simply always named
something would be worse than the gap: it would invent a command for the case
that genuinely has none.
"""

from __future__ import annotations

import pytest

from ....entrypoints.cli.command_specs import COMMAND_SPECS
from ....tests.cli_envelope import parse_json_object
from ....tests.cli_runner import invoke_cached_cli

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint]


def _envelope(*arguments: str) -> dict[str, object]:
    """Invoke the CLI in JSON mode and return the parsed error envelope."""
    result = invoke_cached_cli(["--format", "json", *arguments])
    document = (result.stdout or "").strip() or (result.output or "").strip()
    return parse_json_object(document.splitlines()[-1])


def _command_is_live(dotted: str) -> bool:
    """Return whether ``dotted`` names a command the registry actually declares."""
    return dotted.replace(".", "_") in {specification.key for specification in COMMAND_SPECS}


def test_an_unknown_option_names_the_command_it_was_given_to() -> None:
    """DISCRIMINATING: the command resolved, so the spine must say which.

    This is the shape an agent hits constantly -- a real command with one wrong
    flag -- and it was the shape reporting null.

    THE COMMAND HAS TO EXIST FOR THIS TO BE THAT SHAPE. The case previously
    invoked ``config profile preflight``, which this CLI has no such command
    for: click resolved the ``config profile`` GROUP, refused ``preflight`` as
    an unknown command, and reported ``config.profile`` -- correctly. So the
    case had quietly stopped discriminating and become a second copy of the
    unknown-command test below, which is the failure mode a stale fixture
    produces: not a red test, a test of something else.

    The liveness guard is what keeps that from recurring. A rename now fails
    here naming the fixture, rather than silently changing what is measured.
    """
    assert _command_is_live("config.profile.status"), (
        "this case needs a command that resolves; a renamed one turns it into the unknown-command case"
    )

    envelope = _envelope("config", "profile", "status", "--bogus")

    assert envelope["command"] == "config.profile.status"
    assert envelope["status"] == "error"


def test_an_unknown_command_still_reports_no_command() -> None:
    """ANTI-TAUTOLOGY: nothing resolved, so nothing may be named.

    Without this, naming the command could be satisfied by inventing one from
    the argv tokens, which would report a command that does not exist as the
    one that failed.
    """
    assert not _command_is_live("frobnicate"), "this case needs a name nothing resolves"

    envelope = _envelope("frobnicate")

    assert envelope["command"] is None
    assert envelope["status"] == "error"

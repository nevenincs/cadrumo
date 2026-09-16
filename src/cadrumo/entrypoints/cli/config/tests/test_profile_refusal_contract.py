"""One mistake, one answer: the typed refusal contract of the profile leaves.

An automated operator recovers from the envelope, not the prose: the error
code says what went wrong and the action channel says what to run next. These
cases pin the answers that were inconsistent or missing across verbs.
"""

from __future__ import annotations

import json

import pytest
from click.testing import Result

from ...tests.cli_runner import invoke_cached_cli
from .isolated_storage_fixture import CREDENTIAL_INPUT, profile_cli
from .isolated_storage_fixture import live_cli_profile as live_cli_profile

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint, pytest.mark.usefixtures("live_cli_profile")]

_UNKNOWN = "Nobody"


def _error(result: Result) -> dict[str, object]:
    assert result.exit_code == 2, result.output
    error = json.loads(result.stderr)["error"]
    assert isinstance(error, dict)
    return error


def _action_id(error: dict[str, object]) -> str | None:
    action = error["action"]
    assert isinstance(action, dict)
    reference = action["action"]
    return None if reference is None else str(reference["action_id"])


def _unknown_profile_refusals() -> dict[str, Result]:
    return {
        "view": profile_cli("view", _UNKNOWN),
        "history": profile_cli("history", _UNKNOWN),
        "delete": profile_cli("delete", _UNKNOWN, "--yes"),
        "login": invoke_cached_cli(
            ("--format", "json", "config", "login", _UNKNOWN, "--secrets-stdin"),
            input=json.dumps({"passphrase": CREDENTIAL_INPUT}),
        ),
        "archive_export": profile_cli("archive", "export", _UNKNOWN, "--output", "backup.cadrumo-bucket.tar.gz"),
    }


def test_every_verb_answers_an_unknown_profile_the_same_way() -> None:
    """One label that names no profile, one code and one recovery action.

    Reproduction: the same unknown label was REFUSED_PROFILE_NOT_FOUND with
    the listing action from ``view`` and ``history``, the same code with no
    action at all from ``login``, and a generic REFUSED_CLI_BOUNDARY from
    ``delete`` -- so an automation keyed on either field handled some verbs
    and not others.
    """
    errors = {verb: _error(result) for verb, result in _unknown_profile_refusals().items()}

    assert {verb: error["code"] for verb, error in errors.items()} == dict.fromkeys(errors, "REFUSED_PROFILE_NOT_FOUND")
    assert {verb: _action_id(error) for verb, error in errors.items()} == dict.fromkeys(errors, "operator.profile.list")
    assert all(error["context"] == {"name": _UNKNOWN} for error in errors.values())


def test_deleting_the_selected_profile_names_the_command_that_unblocks_it() -> None:
    """Closing the session is a real next step, so it rides the action channel.

    Reproduction: the refusal explained in prose that the operator must run
    ``config logout`` first, while the action channel carried nothing, so an
    automated operator had only the sentence to parse.
    """
    error = _error(profile_cli("delete", "Editor", "--yes"))

    assert _action_id(error) == "operator.profile.logout"


@pytest.mark.parametrize(
    ("flag", "key"),
    [
        ("NACIMIENTO=soon", "NACIMIENTO"),
        ("NACIMIENTO=2020-01-01,DISCAPACIDAD=high", "DISCAPACIDAD"),
        ("NACIMIENTO=2020-01-01,CONVIVENCIA=quizas", "CONVIVENCIA"),
    ],
)
def test_an_unreadable_descendant_value_names_the_key_it_came_from(flag: str, key: str) -> None:
    """The refusal lists every accepted key, which does not identify the mistake.

    Reproduction: ``--descendiente NACIMIENTO=soon`` first exited 6 as an
    internal error; once typed, its envelope still named no key, so the
    operator was told the whole vocabulary and left to find which of their
    own values was unreadable.
    """
    error = _error(profile_cli("descendiente", "add", "--descendiente", flag))

    assert error["context"] == {"key": key}

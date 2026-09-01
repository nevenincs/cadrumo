"""Parse-time CLI refusals render in the operator's output language.

An argv parse failure fires before any per-command output-language handling, so
the JSON error document historically embedded click's English
``format_message()`` verbatim even under ``--language ca``. The terminal handler
now re-keys the click-generated parse failures (invalid Choice value, unknown
option, unknown command, missing argument) to localised refusals that carry the
parse failure's structured facts in ``context`` and render in the language
knowable at parse time (the ``--language`` argv token, else the i18n chain).

Real-behavior only: a genuine parse failure is driven through the real cached
``cadrumo`` app over the shared CLI runner, and the rendered message is compared
against the i18n API's own rendering of the same key with the same context —
never a hardcoded prose string.
"""

from __future__ import annotations

import pytest

from ....core.i18n.render import tr
from ....tests.cli_envelope import require_error_document
from ....tests.cli_runner import invoke_cached_cli

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint]

_PARSE_INVALID_CHOICE_KEY = "cli.common.errors.parse_invalid_choice"
_PARSE_MISSING_ARGUMENT_KEY = "cli.common.errors.parse_missing_argument"
_PARSE_UNKNOWN_COMMAND_KEY = "cli.common.errors.parse_unknown_command"
_PARSE_UNKNOWN_OPTION_KEY = "cli.common.errors.parse_unknown_option"


def _error_member(output: str) -> dict[str, object]:
    """Return the ``error`` member of the shared-spine document."""
    document = require_error_document(output)
    assert document["status"] == "error"
    assert document["notices"] == []
    error = document["error"]
    assert isinstance(error, dict)
    return {str(name): value for name, value in error.items()}


def _context(error: dict[str, object]) -> dict[str, object]:
    context = error["context"]
    assert isinstance(context, dict), f"context is not an object: {context!r}"
    return {str(name): value for name, value in context.items()}


@pytest.mark.parametrize("locale", ["ca", "hu", "es", "en"])
def test_invalid_choice_refusal_renders_in_requested_locale(locale: str) -> None:
    """A bad Choice value renders the keyed refusal in the ``--language`` locale.

    The accepted-value set rides in ``context`` (the CLI-boundary rule requires a
    refusal to name the accepted set), and the rendered message equals the i18n
    rendering of the parse-invalid-choice key with the same structured facts.
    """
    result = invoke_cached_cli(
        ["--format", "json", "--language", locale, "config", "profile", "create", "--taxation-type", "9"],
    )
    assert result.exit_code == 2, result.output
    error = _error_member(result.output)
    assert error["code"] == "REFUSED_CLI_BOUNDARY"
    assert error["category"] == "REFUSED"

    context = _context(error)
    assert context["value"] == "9"
    accepted = context["accepted"]
    assert isinstance(accepted, str)
    assert "1" in accepted and "2" in accepted

    expected = tr(_PARSE_INVALID_CHOICE_KEY, locale=locale, value=context["value"], accepted=accepted)
    assert error["message"] == expected
    assert "is not one of" not in str(error["message"])  # the English click phrasing is gone


@pytest.mark.parametrize("locale", ["ca", "hu"])
def test_unknown_option_refusal_names_option_and_localises(locale: str) -> None:
    """An unknown option renders the keyed refusal and names the offending option."""
    result = invoke_cached_cli(
        ["--format", "json", "--language", locale, "config", "--no-such-opt"],
    )
    assert result.exit_code == 2, result.output
    error = _error_member(result.output)

    context = _context(error)
    assert context["option"] == "--no-such-opt"

    expected = tr(_PARSE_UNKNOWN_OPTION_KEY, locale=locale, option="--no-such-opt")
    assert error["message"] == expected


def test_unknown_command_refusal_names_command_and_localises() -> None:
    """An unknown command renders the keyed refusal naming the offending command."""
    result = invoke_cached_cli(["--format", "json", "--language", "ca", "config", "nosuchcmd"])
    assert result.exit_code == 2, result.output
    error = _error_member(result.output)

    context = _context(error)
    assert context["command"] == "nosuchcmd"

    expected = tr(_PARSE_UNKNOWN_COMMAND_KEY, locale="ca", command="nosuchcmd")
    assert error["message"] == expected
    assert "nosuchcmd" in str(error["message"])


def test_missing_argument_refusal_names_parameter_and_localises() -> None:
    """A missing required argument renders the keyed refusal naming the parameter.

    ``config profile create`` has no genuine click-level required argument (its
    ``--profile`` is optional, resolved by the wizard), so it never reaches
    click's ``MissingParameter`` path -- it hits a different, unrelated
    refusal instead. ``config profile rename`` has a real required positional
    (``source``), so it is the fixture that actually exercises this path.
    """
    result = invoke_cached_cli(
        ["--format", "json", "--language", "hu", "config", "profile", "rename"],
    )
    assert result.exit_code == 2, result.output
    error = _error_member(result.output)

    context = _context(error)
    parameter = context["parameter"]
    assert isinstance(parameter, str) and parameter

    expected = tr(_PARSE_MISSING_ARGUMENT_KEY, locale="hu", parameter=parameter)
    assert error["message"] == expected


def test_output_language_token_is_honoured_at_parse_time() -> None:
    """The ``--output-language`` argv token localises even its own refusal.

    ``--output-language`` is not a registered option, so click refuses it as an
    unknown option; the refusal is still rendered in the language the operator
    asked for, because the parse-time resolver reads the token from the raw argv
    before any command context exists.
    """
    result = invoke_cached_cli(
        ["--format", "json", "--output-language", "ca", "config", "profile", "create", "--taxation-type", "9"],
    )
    assert result.exit_code == 2, result.output
    error = _error_member(result.output)

    context = _context(error)
    assert context["option"] == "--output-language"

    expected = tr(_PARSE_UNKNOWN_OPTION_KEY, locale="ca", option="--output-language")
    assert error["message"] == expected

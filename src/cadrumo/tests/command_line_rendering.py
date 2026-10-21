"""Run a command in the test's process and compare what it prints with a reply or a result.

An installation act's reply and an operation's result carry real values. A
command hides profile and bucket identifiers when it prints, unless the
installation reveals them. So a command and its act or operation agree when
the command run with identifiers revealed prints the other side's document
exactly, and the default run prints that document after the command's own
output redaction.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

import click
from click.testing import Result
from pydantic import BaseModel, TypeAdapter

from cadrumo.core.config import override_settings
from cadrumo.core.json_contract import OutputSchema
from cadrumo.core.output_rendering import jsonable_output_payload
from cadrumo.core.redaction.rules import redact_structured_for_cli_output

_JSON_OBJECT: TypeAdapter[dict[str, object]] = TypeAdapter(dict[str, object])


@dataclass(frozen=True, slots=True)
class Printed:
    """The result document one command printed, by default and with identifiers revealed."""

    default: dict[str, object]
    revealed: dict[str, object]


def json_document(model: BaseModel, *, exclude: set[str] | None = None) -> dict[str, object]:
    """Return the JSON document a model serialises to, as a frontend shows it."""
    return _JSON_OBJECT.validate_json(model.model_dump_json(exclude=exclude))


def command_result(
    *arguments: str,
    invoke_cli: Callable[..., Result],
    stdin: str | None = None,
    reveal_identifiers: bool = False,
) -> dict[str, object]:
    """Run one command and return the ``result`` of its JSON envelope."""
    with override_settings(cadrumo_cli_reveal_identifiers=reveal_identifiers):
        result = invoke_cli(["--format", "json", *arguments], input=stdin)
    assert result.exit_code == 0, click.unstyle(result.output)
    return _JSON_OBJECT.validate_python(_JSON_OBJECT.validate_json(result.stdout)["result"])


def command_printed(*arguments: str, invoke_cli: Callable[..., Result], stdin: str | None = None) -> Printed:
    """Run one repeatable command twice: as it prints by default, and with identifiers revealed."""
    return Printed(
        default=command_result(*arguments, invoke_cli=invoke_cli, stdin=stdin),
        revealed=command_result(*arguments, invoke_cli=invoke_cli, stdin=stdin, reveal_identifiers=True),
    )


def command_error(*arguments: str, invoke_cli: Callable[..., Result], stdin: str | None = None) -> dict[str, object]:
    """Run one command that must refuse and return the ``error`` of its JSON document."""
    result = invoke_cli(["--format", "json", *arguments], input=stdin)
    assert result.exit_code != 0, click.unstyle(result.output)
    for line in result.stderr.splitlines():
        if line.strip().startswith("{"):
            return _JSON_OBJECT.validate_python(_JSON_OBJECT.validate_json(line)["error"])
    raise AssertionError(f"no JSON error document: {result.stderr[:400]!r}")


def redacted_as_printed(document: dict[str, object], *, reveal_identifiers: bool = False) -> dict[str, object]:
    """Apply the command's own output redaction to a document of real values."""
    return _JSON_OBJECT.validate_python(
        redact_structured_for_cli_output(document, reveal_identifiers=reveal_identifiers)
    )


def assert_prints(document: dict[str, object], printed: Printed) -> None:
    """The command prints ``document``: whole when identifiers are revealed, redacted as it always is otherwise."""
    assert printed.revealed == document
    assert printed.default == redacted_as_printed(document)


def as_the_command_line_renders(result: OutputSchema, *, reveal_identifiers: bool = False) -> dict[str, object]:
    """Serialise and redact a result model exactly as a command's JSON envelope does.

    For a command that cannot be run to a result in a test. Every other
    comparison reads the document the command itself printed.
    """
    return redacted_as_printed(
        _JSON_OBJECT.validate_python(jsonable_output_payload(result)), reveal_identifiers=reveal_identifiers
    )

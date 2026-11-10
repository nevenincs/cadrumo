"""Empty and blank identifier arguments are refused at the parse boundary by name."""

from __future__ import annotations

import json
from collections.abc import Sequence

import pytest
from typer.core import TyperCommand

from .cli_runner import invoke_cached_cli
from .registry_cli_support import _command_path

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint]

_TRANSACTION = "0123456789ab"


def _link_command() -> TyperCommand:
    command = _command_path("app", "ledger", "link")
    assert isinstance(command, TyperCommand)
    return command


@pytest.mark.parametrize(
    ("args", "parameter"),
    [
        (["app", "ledger", "link", _TRANSACTION, "--invoice-id", ""], "--invoice-id"),
        (["app", "ledger", "link", _TRANSACTION, "--invoice-id", "   "], "--invoice-id"),
        (["app", "ledger", "link", "", "--invoice-id", "abcdef"], "transaction_id"),
        (["app", "ledger", "remove", "  "], "transaction_id"),
        (["app", "ledger", "view", " "], "transaction_id"),
        (["app", "ledger", "review", " "], "record_id"),
        (["app", "ledger", "attach", _TRANSACTION, "--attachment-id", ""], "--attachment-id"),
        (["app", "ledger", "invoice", "match", "--invoice-id", " "], "--invoice-id"),
        (["app", "ledger", "invoice", "match", "--transaction-id", ""], "--transaction-id"),
        (["app", "ledger", "rule", "trial", "--transaction-id", ""], "--transaction-id"),
    ],
)
def test_blank_identifier_is_a_usage_refusal_naming_the_parameter(args: Sequence[str], parameter: str) -> None:
    """The real command tree refuses the blank value before any request model sees it."""
    result = invoke_cached_cli(args)

    assert result.exit_code == 2, result.output
    assert f"'{parameter}'" in result.output, result.output
    assert "string_too_short" not in result.output
    assert "Violations" not in result.output


def test_blank_identifier_refusal_is_a_json_usage_error_naming_the_option() -> None:
    """Under ``--format json`` the refusal is the shared error document, not a crash envelope."""
    result = invoke_cached_cli(["--format", "json", "app", "ledger", "link", _TRANSACTION, "--invoice-id", ""])

    assert result.exit_code == 2, result.output
    document = json.loads(result.output)
    assert document["status"] == "error"
    assert document["command"] == "app.ledger.link"
    assert document["error"]["code"] == "REFUSED_CLI_BOUNDARY"
    assert "'--invoice-id'" in document["error"]["message"]


def test_identifier_is_normalised_at_the_boundary() -> None:
    """A padded identifier reaches the handler stripped, exactly as a bare one would."""
    command = _link_command()
    context = command.make_context("link", ["  0123456789ab ", "--invoice-id", "\tabcdef\n"], resilient_parsing=False)

    assert context.params["transaction_id"] == _TRANSACTION
    assert context.params["invoice_id"] == "abcdef"


def test_a_free_text_option_still_admits_a_blank_value() -> None:
    """Only declared identifiers are constrained; a free-text option keeps its own contract."""
    command = _link_command()
    context = command.make_context(
        "link", [_TRANSACTION, "--invoice-id", "abcdef", "--by", ""], resilient_parsing=False
    )

    assert context.params["actor"] == ""

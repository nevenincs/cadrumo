"""The ledger LLM commands take no model option.

A role reads with the model the agent service derives for it, so a command that named
a model would offer a choice the service does not honour. The real command
parser must not know the option on either command that once carried it.
"""

from __future__ import annotations

import pytest

from ....tests.cli_envelope import require_error_document
from .cli_runner import invoke_cached_cli

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint]


@pytest.mark.parametrize(
    "command",
    [
        ("app", "ledger", "classify", "abcdef123456", "--llm", "--read-evidence"),
        ("app", "ledger", "split", "abcdef123456", "--llm", "--read-evidence"),
    ],
    ids=["classify", "split"],
)
def test_a_vision_model_option_is_an_unknown_option(command: tuple[str, ...]) -> None:
    result = invoke_cached_cli(["--format", "json", *command, "--vision-model", "synthetic-vision:2"])

    assert result.exit_code == 2, result.output
    error = require_error_document(result.output)["error"]
    assert isinstance(error, dict)
    context = error["context"]
    assert isinstance(context, dict)
    assert context["option"] == "--vision-model"

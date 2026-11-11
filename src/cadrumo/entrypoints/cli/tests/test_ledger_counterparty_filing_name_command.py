"""The counterparty filing-name command is mounted under the counterparty family and parses its parts.

``aeat app ledger counterparty filing-name`` takes the counterparty as its
subject, the party kind as a required closed choice, and each name part as its
own option; a rendering that names no width is a usage error at the parse boundary.
"""

from __future__ import annotations

import pytest

from .cli_runner import invoke_unbound_cli, semantic_cli_output

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint]

_COMMAND = ("app", "ledger", "counterparty", "filing-name")


def test_the_command_is_mounted_with_one_option_per_stated_part() -> None:
    result = invoke_unbound_cli([*_COMMAND, "--help"])

    assert result.exit_code == 0, result.output
    output = semantic_cli_output(result)
    for option in (
        "--kind",
        "--primer-apellido",
        "--segundo-apellido",
        "--no-second-surname",
        "--nombre",
        "--razon-social",
        "--rendering",
        "--country-code",
        "--actor",
    ):
        assert option in output
    assert "natural_person" in output
    assert "entity" in output


@pytest.mark.parametrize(
    "arguments",
    [
        ("B00015016", "--razon-social", "Ficticia, S.L."),
        ("B00015016", "--kind", "sole_trader", "--razon-social", "Ficticia, S.L."),
        ("--kind", "entity", "--razon-social", "Ficticia, S.L."),
    ],
    ids=["kind_missing", "kind_outside_the_choice", "subject_missing"],
)
def test_a_statement_without_its_subject_or_a_known_kind_is_a_usage_error(arguments: tuple[str, ...]) -> None:
    result = invoke_unbound_cli([*_COMMAND, *arguments])

    assert result.exit_code == 2, result.output


@pytest.mark.parametrize("rendering", ["40", "=Ficticia", "0=Ficticia", "forty=Ficticia", "40="])
def test_a_rendering_that_names_no_width_is_refused_before_anything_is_sent(rendering: str) -> None:
    result = invoke_unbound_cli(
        [*_COMMAND, "B00015016", "--kind", "entity", "--razon-social", "Ficticia, S.L.", "--rendering", rendering]
    )

    assert result.exit_code == 2, result.output
    assert "'--rendering'" in semantic_cli_output(result)

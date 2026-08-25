"""Parser-boundary tests for Modelo 145 communication CLI arguments.

See Also:
    :mod:`~entrypoints.cli._modelo_m145_parsing`
        CLI-only parser boundary under test.
    :mod:`~entrypoints.cli._modelo_m145_cli`
        Typer command group that delegates raw option values to these helpers.
    :class:`~application.modelo.M145CommunicationCreateCommand`
        Backend DTO constructed from parsed CLI arguments.
    :class:`~application.modelo.M145CommunicationPeriod`
        Closed period-token type accepted by the CLI option.
    :func:`~entrypoints.cli._modelo_cli_support.parse_casilla_override`
        Shared registry-field assignment parser reused by the M145 helpers.
"""

from __future__ import annotations

import pytest
import typer

from ....application.modelo._m145_communication_records import M145CommunicationPeriod
from .._modelo_cli_support import parse_casilla_override, resolve_default_actor
from .._modelo_m145_parsing import m145_actor_from_cli, m145_create_command_from_cli, m145_field_values_from_cli

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint]


def test_m145_create_command_from_cli_parses_create_arguments() -> None:
    command = m145_create_command_from_cli(
        year=2026,
        period=M145CommunicationPeriod.COMMUNICATION,
        casilla_specs=[
            "perceptor.nif=12345678Z",
            "perceptor.nombre=Ana",
        ],
        note="operator note",
        parse_casilla_override=parse_casilla_override,
    )

    assert command.communication_year == 2026
    assert command.period_token is M145CommunicationPeriod.COMMUNICATION
    assert command.field_values == {
        "perceptor.nif": "12345678Z",
        "perceptor.nombre": "Ana",
    }
    assert command.note == "operator note"


def test_m145_field_values_from_cli_requires_casilla_argument() -> None:
    with pytest.raises(typer.BadParameter) as raised:
        m145_field_values_from_cli([], parse_casilla_override=parse_casilla_override)

    assert "--casilla" in str(raised.value)


def test_m145_actor_from_cli_uses_trimmed_operator_label() -> None:
    actor = m145_actor_from_cli("  payroll desk  ", resolve_default_actor=resolve_default_actor)

    assert actor == "payroll desk"


def test_m145_actor_from_cli_uses_real_default_actor_for_blank_input() -> None:
    actor = m145_actor_from_cli("  ", resolve_default_actor=resolve_default_actor)

    assert actor

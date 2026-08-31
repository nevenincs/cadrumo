"""Command-spec checks for the calc-pull observation assembly flag."""

from __future__ import annotations

import pytest

from ....core.i18n._render import tr
from .._command_spec import DefaultKind
from .._modelo_spreadsheet_command_specs import MODELO_SPREADSHEET_COMMAND_SPECS

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint]


def _parameter():
    pull = next(spec for spec in MODELO_SPREADSHEET_COMMAND_SPECS if spec.key == "app_modelo_spreadsheet_pull")
    return next(parameter for parameter in pull.parameters if parameter.name == "assemble_observations")


def test_assemble_observations_flag_is_registered_on_pull_command() -> None:
    parameter = _parameter()
    assert parameter.declarations == ("--assemble-observations/--no-assemble-observations",)
    assert parameter.is_flag is True


def test_assemble_observations_flag_defaults_to_false() -> None:
    default = _parameter().default
    assert default.kind is DefaultKind.LITERAL
    assert default.literal is False


def test_assemble_observations_flag_help_resolves_through_tr() -> None:
    parameter = _parameter()
    help_text = tr(parameter.help_key.value)
    assert help_text, "--assemble-observations help text must be non-empty"
    assert parameter.help_key.value not in help_text

"""Registered projection failures retain operation custody and local guidance."""

from __future__ import annotations

from typing import cast
from uuid import UUID

import pytest
import typer

from cadrumo.core.config import override_settings
from cadrumo.core.i18n.render import tr
from cadrumo.domain.calculations.registry.tests.authored_editions import filing_year_envelope
from cadrumo_client.commands.errors import CliRefusedBoundaryError
from cadrumo_client.commands.shared_contracts import DefaultKind

from .. import modelo_projection_commands
from ..modelo_projection_command_specs import MODELO_PROJECTION_COMMAND_SPECS

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint]

_YEAR = filing_year_envelope().horizon
_PRIOR_YEAR = _YEAR - 1
_PROFILE = UUID("5aa00000-0000-4000-8000-0000000000aa")
_OPERATION_ID = "a" * 64


def _failed(code: str, *, effect: str = "none") -> CliRefusedBoundaryError:
    return CliRefusedBoundaryError(
        code,
        context={
            "reason": code,
            "operation_id": _OPERATION_ID,
            "terminal_condition": "failed",
            "effect": effect,
        },
    )


@pytest.mark.parametrize(
    ("code", "key"),
    [
        ("ERROR_MODELO_PROJECT_NO_M130_UNITS", "cli.app.modelo.project.no_m130_units"),
        ("ERROR_MODELO_PROJECT_NO_M130_REVISIONS", "cli.app.modelo.project.no_m130_revisions"),
    ],
)
def test_project_recovery_uses_admitted_year_and_retains_write_effect(
    monkeypatch: pytest.MonkeyPatch, code: str, key: str
) -> None:
    calls = 0

    def refuse(_ctx: typer.Context, _request: object) -> None:
        nonlocal calls
        calls += 1
        raise _failed(code, effect="updated")

    monkeypatch.setattr(modelo_projection_commands, "active_bucket_id_or_refuse", lambda: str(_PROFILE))
    monkeypatch.setattr(modelo_projection_commands, "run_modelo_project", refuse)
    with pytest.raises(CliRefusedBoundaryError) as caught:
        modelo_projection_commands.modelo_project(cast(typer.Context, object()), year=_YEAR, ccaa="madrid")
    assert calls == 1
    assert str(caught.value) == tr(key, year=_YEAR)
    assert caught.value.context == {
        "reason": code,
        "operation_id": _OPERATION_ID,
        "terminal_condition": "failed",
        "effect": "updated",
        "year": _YEAR,
    }


def test_compare_does_not_invent_which_of_two_years_failed(monkeypatch: pytest.MonkeyPatch) -> None:
    code = "ERROR_MODELO_COMPARE_NO_WORK_UNITS"
    calls = 0

    def refuse(_ctx: typer.Context, _request: object) -> None:
        nonlocal calls
        calls += 1
        raise _failed(code)

    monkeypatch.setattr(modelo_projection_commands, "active_bucket_id_or_refuse", lambda: str(_PROFILE))
    monkeypatch.setattr(modelo_projection_commands, "run_modelo_compare", refuse)
    with pytest.raises(CliRefusedBoundaryError) as caught:
        modelo_projection_commands.modelo_compare(
            cast(typer.Context, object()), year=[_YEAR, _PRIOR_YEAR], modelo="100"
        )
    assert calls == 1
    assert str(caught.value) == tr(
        "cli.app.modelo.compare.recover_no_work_units", modelo="100", year_a=_PRIOR_YEAR, year_b=_YEAR
    )
    assert caught.value.context == {
        "reason": code,
        "operation_id": _OPERATION_ID,
        "terminal_condition": "failed",
        "effect": "none",
        "modelo": "100",
        "year_a": _PRIOR_YEAR,
        "year_b": _YEAR,
    }


@pytest.mark.parametrize("language", ("en", "es", "ca", "hu"))
@pytest.mark.parametrize(
    "key",
    (
        "cli.app.modelo.compare.recover_no_work_units",
        "cli.app.modelo.compare.recover_no_revisions",
        "cli.app.modelo.compare.recover_no_usable_revisions",
    ),
)
def test_compare_recovery_catalogue_is_complete_in_each_language(language: str, key: str) -> None:
    with override_settings(cadrumo_output_language=language):
        message = tr(key, modelo="130", year_a=_PRIOR_YEAR, year_b=_YEAR)
    assert message != key
    assert "130" in message and str(_PRIOR_YEAR) in message and str(_YEAR) in message
    assert "{" not in message and "}" not in message


def test_compare_requires_the_modelo_instead_of_assuming_one() -> None:
    compare = next(spec for spec in MODELO_PROJECTION_COMMAND_SPECS if spec.key == "app_modelo_compare")
    modelo = next(parameter for parameter in compare.parameters if parameter.name == "modelo")

    assert modelo.default.kind is DefaultKind.REQUIRED

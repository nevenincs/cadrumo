"""Boundary proofs for the profile CLI projection.

The profile commands are line-mode entrypoints. Full-screen composition lives
under the dedicated TUI root, so this suite pins the only selection behavior
that remains here: distinguishing explicit wizard facts from parser metadata.
"""

from __future__ import annotations

import ast
import inspect
from pathlib import Path

import pytest
import typer

from .....application.wizard import build_wizard_command
from .....core.wizard_catalogue import get_setup_flow
from .._manager_dispatch import with_profile_cli_projection
from .._manager_frontend import has_explicit_profile_fields

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint]


def test_empty_repeated_option_default_is_not_an_explicit_profile_fact() -> None:
    parsed_defaults = {
        "ctx": object(),
        "profile_name": "Primer Contacto",
        "quiet": False,
        "accept_defaults": False,
        "tui": False,
        "irpf_income_categories": [],
    }

    assert not has_explicit_profile_fields(parsed_defaults)
    assert has_explicit_profile_fields(
        {**parsed_defaults, "irpf_income_categories": ["actividad_economica"]},
    )


@pytest.mark.parametrize("value", [False, 0, ""])
def test_scalar_values_are_explicit_even_when_falsy(value: object) -> None:
    assert has_explicit_profile_fields({"declared_field": value})


def test_profile_names_remain_transport_metadata() -> None:
    assert not has_explicit_profile_fields({"profile_name": "Named Subject"})


@pytest.mark.parametrize("mode", ["create", "edit"])
def test_profile_name_is_optional_at_the_line_mode_door(mode: str) -> None:
    command = build_wizard_command(get_setup_flow(), mode=mode)  # type: ignore[arg-type]
    assert inspect.signature(command).parameters["profile_name"].default is None


def test_profile_cli_projection_preserves_the_typer_context_contract() -> None:
    command = with_profile_cli_projection(
        build_wizard_command(get_setup_flow(), mode="create"),
        mode="create",
    )
    parameter = inspect.signature(command).parameters["ctx"]

    assert parameter.kind is inspect.Parameter.POSITIONAL_OR_KEYWORD
    assert parameter.annotation is typer.Context

    app = typer.Typer()
    app.command()(command)
    click_command = typer.main.get_command(app)
    assert "ctx" not in {item.name for item in click_command.params}


def test_cli_profile_modules_do_not_import_or_construct_the_tui() -> None:
    config_root = Path(__file__).parents[1]
    modules = (
        "_manager_frontend.py",
        "_manager_dispatch.py",
        "_descendiente.py",
        "_apoderado.py",
    )
    for module_name in modules:
        source = (config_root / module_name).read_text(encoding="utf-8")
        tree = ast.parse(source)
        imported_modules = {
            alias.name
            for node in ast.walk(tree)
            if isinstance(node, ast.Import)
            for alias in node.names
        } | {
            node.module or ""
            for node in ast.walk(tree)
            if isinstance(node, ast.ImportFrom)
        }
        assert not any("entrypoints.tui" in module for module in imported_modules), module_name


def test_interactive_cli_doors_use_the_application_line_frontend() -> None:
    config_root = Path(__file__).parents[1]
    descendant = (config_root / "_descendiente.py").read_text(encoding="utf-8")
    apoderado = (config_root / "_apoderado.py").read_text(encoding="utf-8")

    assert "LineFlowFrontend(definition).run" in descendant
    assert "build_descendant_door(record)" in descendant
    assert "persist_descendant_door_answers(state.answers)" in descendant
    assert "LineFlowFrontend(definition).run" in apoderado
    assert "build_apoderado_flow_definition(catalogue)" in apoderado
    assert "apoderado_answers_from_state(state)" in apoderado


def test_retired_manager_frontend_symbols_are_not_redeclared() -> None:
    from .. import _manager_frontend

    retired = {
        "attempt_registration",
        "build_active_profile_overview",
        "host_can_run_full_screen",
        "manager_is_the_right_frontend",
        "persist_active_profile_field",
        "present_form",
        "present_profile_manager",
        "present_registration",
        "profile_field_value_refusal",
    }
    assert retired.isdisjoint(vars(_manager_frontend))

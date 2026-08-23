"""Structural authority checks for the import-light Google command family."""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

from ..._command_spec import BindingState, SchemaState
from .._google_command_specs import GOOGLE_COMMAND_SPECS

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint]


def test_google_specs_declare_the_complete_operator_subtree() -> None:
    by_key = {spec.key: spec for spec in GOOGLE_COMMAND_SPECS}

    assert set(by_key) == {
        "config_google",
        "config_google_register",
        "config_google_login",
        "config_google_status",
        "config_google_logout",
        "config_google_credential_source",
        "config_google_credential_source_set",
        "config_google_credential_source_show",
        "config_google_folder",
        "config_google_folder_set",
        "config_google_folder_get",
        "config_google_sync",
        "config_google_sync_probe",
        "config_google_sync_push",
        "config_google_sync_calc",
        "config_google_sync_calc_export",
        "config_google_sync_calc_verify",
        "config_google_sync_calc_pull",
        "config_google_sync_calc_compute",
    }
    leaves = [spec for spec in GOOGLE_COMMAND_SPECS if spec.kind == "leaf"]
    assert all(spec.handler is not None and spec.handler.state is BindingState.TARGET for spec in leaves)
    assert all(spec.result_schema.state is SchemaState.TARGET for spec in leaves)
    assert all(spec.result_schema.identity == spec.key.replace("_", ".") for spec in leaves)


def test_google_handler_modules_hold_no_typer_structural_authority() -> None:
    package = Path(__file__).parents[1]
    modules = (
        "_google.py",
        "_google_credential_source_cli.py",
        "_google_folder.py",
        "_google_sync_calc.py",
    )

    for module in modules:
        tree = ast.parse((package / module).read_text(encoding="utf-8"))
        assert not any(
            isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.decorator_list for node in ast.walk(tree)
        ), module
        assert not any(
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Attribute)
            and node.func.attr in {"Typer", "Argument", "Option", "command", "add_typer"}
            for node in ast.walk(tree)
        ), module


def test_google_parameters_retain_aliases_flags_multiplicity_and_bounds() -> None:
    by_key = {spec.key: spec for spec in GOOGLE_COMMAND_SPECS}
    credential_set = {
        parameter.name: parameter for parameter in by_key["config_google_credential_source_set"].parameters
    }
    assert credential_set["scopes"].declarations == ("--scope",)
    assert credential_set["scopes"].multiple is True
    assert credential_set["delegates"].multiple is True

    probe = {parameter.name: parameter for parameter in by_key["config_google_sync_probe"].parameters}
    assert probe["read_only"].declarations == ("--read-only/--no-read-only",)
    assert probe["read_only"].is_flag is True

    export = {parameter.name: parameter for parameter in by_key["config_google_sync_calc_export"].parameters}
    assert export["year"].constraint.minimum == 2000
    assert export["year"].constraint.maximum == 2099
    assert export["prefill_relations"].declarations == ("--prefill-relations/--no-prefill-relations",)

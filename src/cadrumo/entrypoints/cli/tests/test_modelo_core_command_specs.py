from __future__ import annotations

import ast
from pathlib import Path

import pytest

from cadrumo.entrypoints.cli._command_runtime import resolve_deferred_target
from cadrumo.entrypoints.cli._modelo_core_command_specs import MODELO_CORE_COMMAND_SPECS

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint]


def test_modelo_core_specs_are_the_exact_authored_set() -> None:
    assert {spec.key for spec in MODELO_CORE_COMMAND_SPECS} == {
        "app_modelo_history",
        "app_modelo_work",
        "app_modelo_work_amend",
        "app_modelo_work_compare_taxation",
        "app_modelo_work_history",
    }
    assert [spec.token for spec in MODELO_CORE_COMMAND_SPECS] == [
        "work",
        "compare-taxation",
        "history",
        "amend",
        "history",
    ]


def test_modelo_core_value_and_schema_targets_are_public_and_resolvable() -> None:
    for spec in MODELO_CORE_COMMAND_SPECS:
        for parameter in spec.parameters:
            resolve_deferred_target(parameter.value.annotation)
            if parameter.value.click_type is not None:
                resolve_deferred_target(parameter.value.click_type)
        if spec.result_schema.target is not None:
            resolve_deferred_target(spec.result_schema.target)


def test_modelo_core_handlers_have_no_attached_cli_authority() -> None:
    module_path = Path(__file__).parents[1] / "_modelo.py"
    tree = ast.parse(module_path.read_text(encoding="utf-8"))
    expected = {"modelo_history", "work_amend", "work_compare_taxation", "work_history"}
    functions = {
        node.name: node
        for node in tree.body
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name in expected
    }
    assert functions.keys() == expected
    assert all(not node.decorator_list for node in functions.values())
    assert all("typer.Option" not in ast.unparse(node.args) for node in functions.values())
    assert all("typer.Argument" not in ast.unparse(node.args) for node in functions.values())

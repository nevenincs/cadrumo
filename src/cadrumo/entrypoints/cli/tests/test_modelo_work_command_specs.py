"""Exact authority, runtime, and legacy-absence gates for Modelo work."""

from __future__ import annotations

import ast
import importlib
import inspect
import sys
import types
from collections.abc import Callable
from enum import Enum
from pathlib import Path
from typing import cast, get_args, get_origin, get_type_hints

import pytest
from typer.main import get_command

from .._command_runtime import build_command_subtree
from .._command_spec import BindingState, CommandSpecGraph, DefaultKind, SchemaState
from .._modelo_audit_command_specs import MODELO_ROOT_COMMAND_SPEC
from .._modelo_core_command_specs import MODELO_CORE_COMMAND_SPECS
from .._modelo_work_command_specs import MODELO_WORK_COMMAND_SPECS
from .._root_command_specs import ROOT_COMMAND_SPECS

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint]

EXPECTED_TOKENS = {
    "calculate",
    "create",
    "dependencies",
    "discard",
    "file",
    "list",
    "observations",
    "rename",
    "resume",
    "review",
    "run",
    "run-details",
    "revision",
    "revisions",
    "runs",
    "status",
    "verify",
    "wizard",
}


def _graph() -> CommandSpecGraph:
    return CommandSpecGraph(
        (*ROOT_COMMAND_SPECS, MODELO_ROOT_COMMAND_SPEC, *MODELO_CORE_COMMAND_SPECS, *MODELO_WORK_COMMAND_SPECS)
    )


def _resolve(module_name: str, qualname: str) -> object:
    value: object = importlib.import_module(module_name)
    for part in qualname.split("."):
        value = getattr(value, part)
    return value


def _semantic_annotation(annotation: object) -> object:
    origin = get_origin(annotation)
    if origin is types.UnionType:
        annotation = next(item for item in get_args(annotation) if item is not type(None))
        origin = get_origin(annotation)
    if origin in {list, tuple}:
        return get_args(annotation)[0]
    return annotation


def test_modelo_work_specs_are_the_exact_owned_leaf_set() -> None:
    assert len(MODELO_WORK_COMMAND_SPECS) == 18
    assert {spec.token for spec in MODELO_WORK_COMMAND_SPECS} == EXPECTED_TOKENS
    assert {spec.parent_key for spec in MODELO_WORK_COMMAND_SPECS} == {"app_modelo_work"}
    assert {spec.key for spec in MODELO_WORK_COMMAND_SPECS} == {
        f"app_modelo_work_{token.replace('-', '_')}" for token in EXPECTED_TOKENS
    }


def test_modelo_work_specs_match_public_handler_signatures_and_resolve_targets() -> None:
    for spec in MODELO_WORK_COMMAND_SPECS:
        assert spec.handler is not None
        assert spec.handler.state is BindingState.TARGET
        assert spec.handler.target is not None
        assert not spec.handler.target.qualname.startswith("_")
        assert "<locals>" not in spec.handler.target.qualname
        handler = _resolve(spec.handler.target.module, spec.handler.target.qualname)
        assert callable(handler)
        expected = (spec.invocation.context_parameter, *(parameter.name for parameter in spec.parameters))
        assert tuple(inspect.signature(cast(Callable[..., object], handler)).parameters) == expected
        assert spec.result_schema.state is SchemaState.TARGET
        assert spec.result_schema.target is not None
        assert _resolve(spec.result_schema.target.module, spec.result_schema.target.qualname) is not None
        assert spec.result_schema.identity == f"modelo.work.{spec.token.replace('-', '_')}"


def test_modelo_work_parameter_types_and_defaults_match_behavior_contracts() -> None:
    for spec in MODELO_WORK_COMMAND_SPECS:
        assert spec.handler is not None and spec.handler.target is not None
        handler = cast(
            Callable[..., object],
            _resolve(spec.handler.target.module, spec.handler.target.qualname),
        )
        signature = inspect.signature(handler)
        hints = get_type_hints(handler)
        for parameter in spec.parameters:
            behavior_parameter = signature.parameters[parameter.name]
            expected_type = _resolve(parameter.value.annotation.module, parameter.value.annotation.qualname)
            assert _semantic_annotation(hints[parameter.name]) is expected_type
            if parameter.default.kind is DefaultKind.REQUIRED:
                assert behavior_parameter.default is inspect.Parameter.empty
                continue
            behavior_default = behavior_parameter.default
            if isinstance(behavior_default, Enum):
                behavior_default = behavior_default.value
            declared_default = parameter.default.literal
            if getattr(parameter, "multiple", False) and behavior_default is None:
                behavior_default = ()
            assert declared_default == behavior_default


def test_every_modelo_work_subtree_compiles_from_specs() -> None:
    graph = _graph()
    for key in ("app_modelo_work", *(spec.key for spec in MODELO_WORK_COMMAND_SPECS)):
        assert get_command(build_command_subtree(graph, key)) is not None


def test_importing_modelo_work_specs_does_not_import_behavior() -> None:
    behavior_modules = {
        spec.handler.target.module for spec in MODELO_WORK_COMMAND_SPECS if spec.handler and spec.handler.target
    }
    for module_name in behavior_modules:
        sys.modules.pop(module_name, None)
    importlib.reload(importlib.import_module("cadrumo.entrypoints.cli._modelo_work_command_specs"))
    assert behavior_modules.isdisjoint(sys.modules)


def test_modelo_work_package_has_no_legacy_structural_authority() -> None:
    cli_root = Path(__file__).parents[1]
    paths = sorted(cli_root.glob("_modelo_work*.py"))
    assert not (cli_root / "_modelo_work.py").exists()
    assert not (cli_root / "_modelo_work_options.py").exists()
    forbidden_names = {"command_execution_policy", "declare_metadata_group", "register_schema"}
    for path in paths:
        source = path.read_text(encoding="utf-8")
        tree = ast.parse(source)
        assert "Typer(" not in source
        assert "typer.Option(" not in source
        assert "typer.Argument(" not in source
        assert not any(
            isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name.startswith("register_work_")
            for node in ast.walk(tree)
        )
        assert not any(isinstance(node, ast.Name) and node.id in forbidden_names for node in ast.walk(tree))
        assert not any(
            isinstance(node, ast.Attribute) and node.attr in {"command", "callback", "add_typer"}
            for node in ast.walk(tree)
        )

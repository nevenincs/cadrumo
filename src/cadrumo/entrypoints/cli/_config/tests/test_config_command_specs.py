"""Universal config command-spec authority and behavior parity gates."""

from __future__ import annotations

import ast
import importlib
import inspect
from pathlib import Path

import pytest

from ..._root_command_specs import ROOT_COMMAND_SPECS
from ...command_spec import CommandSpecGraph, DefaultKind, SchemaState
from ..command_specs import CONFIG_COMMAND_SPECS

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint]


def test_complete_config_graph_is_unique_connected_and_runtime_derived() -> None:
    graph = CommandSpecGraph((*ROOT_COMMAND_SPECS, *CONFIG_COMMAND_SPECS))
    config_nodes = tuple(node for node in graph.nodes() if node.path[:2] == ("aeat", "config"))

    assert config_nodes
    assert len(config_nodes) == len(CONFIG_COMMAND_SPECS) + 1
    assert len({node.path for node in config_nodes}) == len(config_nodes)
    assert {node.spec.key for node in config_nodes} == {"config", *(spec.key for spec in CONFIG_COMMAND_SPECS)}


def test_every_config_handler_and_schema_target_resolves() -> None:
    for spec in CONFIG_COMMAND_SPECS:
        if spec.handler is None:
            assert spec.kind == "group"
            assert spec.result_schema.state is SchemaState.NOT_SUPPORTED
            continue
        assert spec.handler.target is not None
        handler = getattr(importlib.import_module(spec.handler.target.module), spec.handler.target.qualname)
        assert callable(handler)
        assert not handler.__name__.startswith("_")
        assert spec.result_schema.state is SchemaState.TARGET
        assert spec.result_schema.target is not None
        assert spec.result_schema.identity is not None
        schema = getattr(
            importlib.import_module(spec.result_schema.target.module),
            spec.result_schema.target.qualname,
        )
        assert inspect.isclass(schema)


def test_plain_handler_defaults_match_specs_except_variadic_wizard_boundary() -> None:
    for spec in CONFIG_COMMAND_SPECS:
        if spec.handler is None or spec.handler.target is None:
            continue
        handler = getattr(importlib.import_module(spec.handler.target.module), spec.handler.target.qualname)
        signature = inspect.signature(handler)
        if any(parameter.kind is inspect.Parameter.VAR_KEYWORD for parameter in signature.parameters.values()):
            assert spec.key in {"config_profile_create", "config_profile_edit"}
            continue
        context_name = spec.invocation.context_parameter
        runtime_parameters = tuple(name for name in signature.parameters if name != context_name)
        assert runtime_parameters == tuple(parameter.name for parameter in spec.parameters), spec.key
        for parameter in spec.parameters:
            runtime_default = signature.parameters[parameter.name].default
            if parameter.default.kind is DefaultKind.REQUIRED:
                assert runtime_default is inspect.Parameter.empty, spec.key
            else:
                assert runtime_default == parameter.default.literal, spec.key


def test_handler_modules_carry_no_typer_structural_authority() -> None:
    modules = {
        spec.handler.target.module
        for spec in CONFIG_COMMAND_SPECS
        if spec.handler is not None and spec.handler.target is not None
    }
    for module_name in modules:
        module = importlib.import_module(module_name)
        module_file = Path(inspect.getfile(module))
        source = module_file.read_text(encoding="utf-8")
        tree = ast.parse(source)
        forbidden_calls = [
            node
            for node in ast.walk(tree)
            if isinstance(node, ast.Call)
            and (
                (isinstance(node.func, ast.Attribute) and node.func.attr in {"command", "callback", "add_typer"})
                or (isinstance(node.func, ast.Attribute) and node.func.attr in {"Option", "Argument", "Typer"})
            )
        ]
        assert not forbidden_calls, module_name
        assert "command_execution_policy" not in source, module_name

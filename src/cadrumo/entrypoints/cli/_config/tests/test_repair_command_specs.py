"""Repair behavior and CLI structure share the production spec authority."""

from __future__ import annotations

import importlib
import inspect

import pytest

from ...command_spec import DefaultKind, SchemaState
from .._repair_command_specs import CONFIG_REPAIR_COMMAND_SPECS

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint]


def test_repair_specs_cover_the_executable_group_and_every_leaf() -> None:
    assert len(CONFIG_REPAIR_COMMAND_SPECS) == 9
    assert {spec.token for spec in CONFIG_REPAIR_COMMAND_SPECS} == {
        "repair",
        "integrity",
        "logs",
        "quarantine",
        "reset-progress",
        "objects",
        "registry",
        "connectivity",
        "profile",
    }
    root = CONFIG_REPAIR_COMMAND_SPECS[0]
    assert root.invocation.invoke_without_command
    assert root.handler is not None
    assert root.result_schema.identity == "config.repair"


def test_repair_handlers_and_schema_targets_resolve_with_exact_defaults() -> None:
    for spec in CONFIG_REPAIR_COMMAND_SPECS:
        if spec.handler is None:
            assert spec.result_schema.state is SchemaState.NOT_SUPPORTED
            continue
        assert spec.handler.target is not None
        handler = getattr(importlib.import_module(spec.handler.target.module), spec.handler.target.qualname)
        signature = inspect.signature(handler)
        runtime_parameters = tuple(name for name in signature.parameters if name != spec.invocation.context_parameter)
        assert runtime_parameters == tuple(parameter.name for parameter in spec.parameters)
        for parameter in spec.parameters:
            runtime_default = signature.parameters[parameter.name].default
            if parameter.default.kind is DefaultKind.REQUIRED:
                assert runtime_default is inspect.Parameter.empty
            else:
                assert runtime_default == parameter.default.literal
        assert spec.result_schema.state is SchemaState.TARGET
        assert spec.result_schema.target is not None
        assert spec.result_schema.identity is not None
        schema = getattr(
            importlib.import_module(spec.result_schema.target.module),
            spec.result_schema.target.qualname,
        )
        assert inspect.isclass(schema)

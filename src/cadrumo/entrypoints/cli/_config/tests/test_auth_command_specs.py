"""CommandSpec authority proofs for the config authentication family."""

from __future__ import annotations

import importlib
import inspect

import pytest

from ..._command_spec import BindingState, DefaultKind, SchemaState
from .._auth_command_specs import AUTH_COMMAND_SPECS

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint]


def test_auth_specs_are_complete_and_resolve_public_targets() -> None:
    assert len(AUTH_COMMAND_SPECS) == 28
    assert len({spec.key for spec in AUTH_COMMAND_SPECS}) == len(AUTH_COMMAND_SPECS)
    assert {spec.token for spec in AUTH_COMMAND_SPECS if spec.parent_key == "config_auth"} == {
        "apoderado",
        "certificate",
        "configure",
        "diagnostics",
        "login",
        "logout",
        "providers",
        "reset",
        "status",
        "test",
    }

    for spec in AUTH_COMMAND_SPECS:
        if spec.kind != "leaf":
            assert spec.handler is None
            assert spec.result_schema.state is SchemaState.NOT_SUPPORTED
            continue
        assert spec.handler is not None
        assert spec.handler.state is BindingState.TARGET
        assert spec.handler.target is not None
        handler_module = importlib.import_module(spec.handler.target.module)
        handler = getattr(handler_module, spec.handler.target.qualname)
        assert callable(handler)
        assert not handler.__name__.startswith("_")
        assert spec.result_schema.state is SchemaState.TARGET
        assert spec.result_schema.target is not None
        schema_module = importlib.import_module(spec.result_schema.target.module)
        assert inspect.isclass(getattr(schema_module, spec.result_schema.target.qualname))


def test_auth_handler_defaults_match_the_parameter_contract() -> None:
    for spec in AUTH_COMMAND_SPECS:
        if spec.kind != "leaf" or spec.handler is None or spec.handler.target is None:
            continue
        module = importlib.import_module(spec.handler.target.module)
        signature = inspect.signature(getattr(module, spec.handler.target.qualname))
        assert tuple(signature.parameters)[1:] == tuple(parameter.name for parameter in spec.parameters)
        for parameter in spec.parameters:
            runtime_default = signature.parameters[parameter.name].default
            if parameter.default.kind is DefaultKind.REQUIRED:
                assert runtime_default is inspect.Parameter.empty
            else:
                assert runtime_default == parameter.default.literal

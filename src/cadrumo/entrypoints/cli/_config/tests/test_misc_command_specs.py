"""Command-spec parity for the smaller config command families."""

from __future__ import annotations

import importlib
import inspect

import pytest

from ..._command_spec import DefaultKind, SchemaState
from .._check_command_specs import CONFIG_CHECK_COMMAND_SPECS
from .._collab_command_specs import CONFIG_COLLAB_COMMAND_SPECS
from .._custody_command_specs import CONFIG_CUSTODY_COMMAND_SPECS
from .._profile_inventory_specs import PROFILE_INVENTORY_COMMAND_SPECS
from .._provision_command_specs import CONFIG_PROVISION_COMMAND_SPECS
from .._reset_command_specs import CONFIG_RESET_COMMAND_SPECS
from .._storage_command_specs import CONFIG_STORAGE_COMMAND_SPECS

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint]

_SPECS = (
    *CONFIG_CHECK_COMMAND_SPECS,
    *CONFIG_COLLAB_COMMAND_SPECS,
    *CONFIG_CUSTODY_COMMAND_SPECS,
    *PROFILE_INVENTORY_COMMAND_SPECS,
    *CONFIG_PROVISION_COMMAND_SPECS,
    *CONFIG_RESET_COMMAND_SPECS,
    *CONFIG_STORAGE_COMMAND_SPECS,
)


def test_misc_config_leaf_handlers_match_spec_parameters_and_defaults() -> None:
    for spec in _SPECS:
        if spec.kind != "leaf":
            assert spec.handler is None
            assert spec.result_schema.state is SchemaState.NOT_SUPPORTED
            continue
        assert spec.handler is not None
        assert spec.handler.target is not None
        handler = getattr(importlib.import_module(spec.handler.target.module), spec.handler.target.qualname)
        signature = inspect.signature(handler)
        context_name = spec.invocation.context_parameter
        runtime_parameters = tuple(name for name in signature.parameters if name != context_name)
        assert runtime_parameters == tuple(parameter.name for parameter in spec.parameters)
        for parameter in spec.parameters:
            runtime_default = signature.parameters[parameter.name].default
            if parameter.default.kind is DefaultKind.REQUIRED:
                assert runtime_default is inspect.Parameter.empty
            else:
                assert runtime_default == parameter.default.literal


def test_misc_config_target_schemas_resolve_and_own_canonical_identities() -> None:
    for spec in _SPECS:
        if spec.kind != "leaf":
            continue
        schema = spec.result_schema
        assert schema.state is SchemaState.TARGET
        assert schema.target is not None
        assert schema.identity is not None
        assert schema.identity.replace(".", "_") == spec.key
        assert inspect.isclass(getattr(importlib.import_module(schema.target.module), schema.target.qualname))

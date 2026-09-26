"""Universal config command-spec authority and behavior parity gates."""

from __future__ import annotations

import ast
import importlib
import inspect
from pathlib import Path
from typing import Any

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


def test_profile_schema_identities_preserve_compound_command_tokens() -> None:
    """A profile leaf's schema identity is its live command path, one segment per token.

    A hyphenated token -- a leaf such as ``complete-setup`` or a group such as
    ``plantilla-media`` -- stays one segment with ``_`` in place of ``-``. The
    spec key cannot stand in for the path: it joins every level with ``_``, so
    splitting it on ``_`` would break a compound group into two segments.
    """
    from ..profile_command_specs import PROFILE_COMMAND_SPECS

    graph = CommandSpecGraph((*ROOT_COMMAND_SPECS, *CONFIG_COMMAND_SPECS))
    leaf_keys = {spec.key for spec in PROFILE_COMMAND_SPECS if spec.result_schema.identity is not None}
    identities = {
        node.spec.key: (node.path, node.spec.result_schema.identity)
        for node in graph.nodes()
        if node.spec.key in leaf_keys
    }

    assert identities.keys() == leaf_keys
    offenders = {
        path: identity
        for path, identity in identities.values()
        if identity != ".".join(token.replace("-", "_") for token in path[1:])
    }
    assert not offenders, offenders
    assert identities["config_profile_complete_setup"][1] == "config.profile.complete_setup"
    assert identities["config_profile_plantilla_media_set"][1] == "config.profile.plantilla_media.set"


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


@pytest.mark.parametrize("token", ["resident_irpf", "non_resident_irnr"])
def test_fiscal_residency_reaches_the_handler_as_the_documented_token(token: str) -> None:
    """The live parser must pass the flag's documented tokens through untouched.

    ``--fiscal-residency`` once declared its value contract as the domain
    ``FiscalResidency`` type, which accepts only registry-validated input. Click
    therefore called that constructor during parsing: ``edit --fiscal-residency
    resident_irpf`` -- the exact value the flag's own help names -- was refused
    before any handler ran, and ``--help`` showed the leaked metavar
    ``<function>``. Registry validation belongs to the wizard, which runs it
    inside an authority operation; the parser must only carry the string.
    """
    from typer._click.core import Context
    from typer._click.types import StringParamType

    from ...tests.cli_runner import cadrumo_click_command

    # The runner is annotated against upstream Click while Typer builds the
    # tree from its vendored copy, so the walked node is typed by what it does.
    command: Any = cadrumo_click_command()
    context = Context(command)
    for name in ("config", "profile", "edit"):
        child = command.get_command(context, name)
        assert child is not None, name
        context = Context(child, parent=context, info_name=name)
        command = child
    parameter = next(parameter for parameter in command.params if parameter.name == "fiscal_residency")

    assert isinstance(parameter.type, StringParamType)
    assert parameter.type.convert(token, parameter, context) == token


@pytest.mark.parametrize(
    ("token", "parameters", "identity"),
    [
        ("load", ("model", "role"), "config.provision.load"),
        ("setup", ("confirm",), "config.provision.setup"),
    ],
)
def test_provision_load_and_setup_extend_the_provision_cluster(
    token: str, parameters: tuple[str, ...], identity: str
) -> None:
    from .._provision_command_specs import CONFIG_PROVISION_COMMAND_SPECS
    from .._spec_policies import NETWORK_WRITE

    graph = CommandSpecGraph((*ROOT_COMMAND_SPECS, *CONFIG_COMMAND_SPECS))
    (node,) = (node for node in graph.nodes() if node.path == ("aeat", "config", "provision", token))
    spec = node.spec

    assert spec in CONFIG_PROVISION_COMMAND_SPECS
    assert spec.parent_key == "config_provision"
    assert tuple(parameter.name for parameter in spec.parameters) == parameters
    assert spec.policy == NETWORK_WRITE
    assert spec.result_schema.identity == identity
    assert not any(path[:3] == ("aeat", "config", "llm") for path in (n.path for n in graph.nodes()))


def test_setup_installs_only_with_an_explicit_confirm_flag() -> None:
    from typer._click.core import Context

    from ...tests.cli_runner import cadrumo_click_command

    command: Any = cadrumo_click_command()
    context = Context(command)
    for name in ("config", "provision", "setup"):
        child = command.get_command(context, name)
        assert child is not None, name
        context = Context(child, parent=context, info_name=name)
        command = child
    confirm = next(parameter for parameter in command.params if parameter.name == "confirm")

    assert confirm.is_flag
    assert confirm.default is False
    assert confirm.opts == ["--confirm"]

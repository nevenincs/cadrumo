"""Authority and import-boundary tests for modelo audit CommandSpecs."""

from __future__ import annotations

import importlib
import inspect
import sys

import pytest

from .._command_spec import CommandSpecGraph, SchemaState
from .._modelo_audit_command_specs import MODELO_AUDIT_COMMAND_SPECS, MODELO_ROOT_COMMAND_SPEC
from .._modelo_readiness_command_specs import MODELO_READINESS_COMMAND_SPECS
from .._root_command_specs import ROOT_COMMAND_SPECS

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint]


def test_modelo_audit_specs_declare_the_exact_family() -> None:
    graph = CommandSpecGraph(
        (*ROOT_COMMAND_SPECS, MODELO_ROOT_COMMAND_SPEC, *MODELO_AUDIT_COMMAND_SPECS, *MODELO_READINESS_COMMAND_SPECS)
    )
    assert {node.path for node in graph.nodes() if "modelo" in node.path} == {
        ("aeat", "app", "modelo"),
        ("aeat", "app", "modelo", "audit"),
        ("aeat", "app", "modelo", "audit", "check"),
        ("aeat", "app", "modelo", "audit", "export"),
        ("aeat", "app", "modelo", "audit", "view"),
        ("aeat", "app", "modelo", "readiness"),
    }


def test_modelo_audit_specs_own_public_handlers_and_schema_identities() -> None:
    leaves = [spec for spec in MODELO_AUDIT_COMMAND_SPECS if spec.kind == "leaf"]
    assert {spec.result_schema.identity for spec in leaves} == {
        "modelo.audit.check",
        "modelo.audit.export",
        "modelo.audit.view",
    }
    assert all(spec.result_schema.state is SchemaState.TARGET for spec in leaves)
    for spec in leaves:
        assert spec.handler is not None and spec.handler.target is not None
        assert not spec.handler.target.qualname.startswith("_")


def test_importing_modelo_audit_specs_does_not_import_behavior() -> None:
    sys.modules.pop("cadrumo.entrypoints.cli._modelo_audit_cli", None)
    importlib.reload(importlib.import_module("cadrumo.entrypoints.cli._modelo_audit_command_specs"))
    assert "cadrumo.entrypoints.cli._modelo_audit_cli" not in sys.modules


def test_modelo_audit_and_readiness_parameter_contracts_match_public_handlers() -> None:
    leaves = (*MODELO_AUDIT_COMMAND_SPECS[1:], *MODELO_READINESS_COMMAND_SPECS)
    for spec in leaves:
        assert spec.handler is not None and spec.handler.target is not None
        module = importlib.import_module(spec.handler.target.module)
        handler = getattr(module, spec.handler.target.qualname)
        signature = inspect.signature(handler)
        expected = ((spec.invocation.context_parameter,) if spec.invocation.context_parameter else ()) + tuple(
            parameter.name for parameter in spec.parameters
        )
        assert tuple(signature.parameters) == expected

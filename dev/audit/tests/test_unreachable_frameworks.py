"""Framework contracts clear actual declarations while retaining ordinary dead members."""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

from dev._paths import REPO_ROOT

from ..unreachable_definitions import _definitions
from ..unreachable_frameworks import framework_contracts
from ..unreachable_models import ShippedModule

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]


def _module(name: str, source: str) -> ShippedModule:
    return ShippedModule(name, Path(name + ".py"), False, ast.parse(source))


def test_framework_contracts_follow_aliases_and_local_generic_bases() -> None:
    base = _module(
        "pkg.base", "from textual.screen import ModalScreen as Modal\nclass Parent(Modal[str]): pass\nAlias = Parent"
    )
    child = _module(
        "pkg.child",
        """
from .base import Alias as Base
class Dialog(Base):
    DEFAULT_CSS = ''
    UNUSED_CSS = ''
    def on_mount(self): pass
    def unused(self): pass
class Plain:
    DEFAULT_CSS = ''
    def on_mount(self): pass
    def render(self): pass
raise RuntimeError('product modules must never execute')
""",
    )
    contracts = framework_contracts({base.name: base, child.name: child})
    definitions = {definition.qualname for definition in _definitions(child.tree, contracts[child.name])}

    assert definitions == {
        "Dialog",
        "Dialog.UNUSED_CSS",
        "Dialog.unused",
        "Plain",
        "Plain.DEFAULT_CSS",
        "Plain.on_mount",
        "Plain.render",
    }


def test_live_logging_override_is_bound_but_an_unrelated_method_is_reported() -> None:
    path = REPO_ROOT / "src/cadrumo/core/diagnostic_log.py"
    tree = ast.parse(path.read_bytes())
    module = ShippedModule("cadrumo.core.diagnostic_log", path, False, tree)
    contracts = framework_contracts({module.name: module})
    definitions = {definition.qualname for definition in _definitions(tree, contracts[module.name])}
    assert "DiagnosticFormatter.formatTime" not in definitions
    formatter = next(
        node for node in tree.body if isinstance(node, ast.ClassDef) and node.name == "DiagnosticFormatter"
    )
    method = next(node for node in formatter.body if isinstance(node, ast.FunctionDef) and node.name == "formatTime")
    method.name = "orphan_time"
    definitions = {definition.qualname for definition in _definitions(tree, contracts[module.name])}
    assert "DiagnosticFormatter.orphan_time" in definitions


def test_installed_sqlalchemy_contract_includes_annotated_configuration() -> None:
    module = _module(
        "pkg.columns",
        """
from sqlalchemy.types import TypeDecorator as ColumnType
class Lookup(ColumnType[bytes]):
    impl = bytes
    cache_ok = True
    UNUSED = True
    def process_result_value(self, value, dialect): return value
    def unused(self): pass
""",
    )
    contracts = framework_contracts({module.name: module})

    definitions = {definition.qualname for definition in _definitions(module.tree, contracts[module.name])}

    assert definitions == {"Lookup", "Lookup.UNUSED", "Lookup.unused"}


@pytest.mark.parametrize("dependency", ["textual", "pydantic"])
def test_undeclared_dependency_module_refuses_instead_of_silently_dropping_its_contract(dependency: str) -> None:
    module = _module("pkg.unknown", f"from {dependency}.unknown import Base\nclass Child(Base): pass")
    with pytest.raises(ValueError, match=rf"explicitly declared installed module: {dependency}\.unknown"):
        framework_contracts({module.name: module})


def test_schema_generator_override_is_bound_without_model_validator_registration() -> None:
    module = _module(
        "pkg.schemas",
        """
from pydantic.json_schema import GenerateJsonSchema as SchemaGenerator
from pydantic import field_validator
class Generator(SchemaGenerator):
    def _build_definitions_remapping(self): pass
    @field_validator('value')
    def validate_value(self): pass
    def unused(self): pass
class Plain:
    def _build_definitions_remapping(self): pass
raise RuntimeError('product modules must never execute')
""",
    )
    contracts = framework_contracts({module.name: module})
    contract = contracts[module.name]["Generator"]
    definitions = {definition.qualname for definition in _definitions(module.tree, contracts[module.name])}

    assert "_build_definitions_remapping" in contract.members
    assert not contract.pydantic
    assert definitions == {
        "Generator",
        "Generator.validate_value",
        "Generator.unused",
        "Plain",
        "Plain._build_definitions_remapping",
    }


def test_live_schema_generator_override_uses_the_installed_framework_contract() -> None:
    path = REPO_ROOT / "src/cadrumo/application/operations/registry_schema_validation.py"
    tree = ast.parse(path.read_bytes())
    module = ShippedModule("cadrumo.application.operations.registry_schema_validation", path, False, tree)
    contracts = framework_contracts({module.name: module})
    definitions = {definition.qualname for definition in _definitions(tree, contracts[module.name])}

    assert not contracts[module.name]["_UnambiguousDefinitionsSchemaGenerator"].pydantic
    assert "_UnambiguousDefinitionsSchemaGenerator._build_definitions_remapping" not in definitions


def test_live_checkbox_override_is_bound_and_a_renamed_member_is_reported() -> None:
    path = REPO_ROOT / "src/cadrumo/entrypoints/tui/modelo/workbench/bulk_confirm.py"
    tree = ast.parse(path.read_bytes())
    module = ShippedModule("cadrumo.entrypoints.tui.modelo.workbench.bulk_confirm", path, False, tree)
    contracts = framework_contracts({module.name: module})
    definitions = {definition.qualname for definition in _definitions(tree, contracts[module.name])}
    assert "TickBox._button" not in definitions
    assert "BulkConfirmScreen.DEFAULT_CSS" not in definitions
    assert "BulkConfirmScreen.SCOPED_CSS" not in definitions

    for node in ast.walk(tree):
        if isinstance(node, ast.Name) and node.id == "DEFAULT_CSS" and isinstance(node.ctx, ast.Store):
            node.id = "UNUSED_CSS"
    definitions = {definition.qualname for definition in _definitions(tree, contracts[module.name])}
    assert "BulkConfirmScreen.UNUSED_CSS" in definitions


def test_wrapping_decorators_do_not_hide_unused_definitions() -> None:
    tree = ast.parse(
        """
from functools import lru_cache
from pydantic import BaseModel, field_validator as validate
import pydantic as pd
@lru_cache()
def unused(): pass
@custom_wrapper
def also_unused(): pass
class Model(BaseModel):
    @validate('value')
    def validate_value(self): pass
    @pd.model_validator(mode='after')
    def validate_model(self): pass
    @custom_wrapper
    def unused_method(self): pass
"""
    )
    module = ShippedModule("pkg.models", Path("models.py"), False, tree)
    contracts = framework_contracts({module.name: module})
    definitions = {definition.qualname for definition in _definitions(tree, contracts[module.name])}

    assert definitions == {"unused", "also_unused", "Model", "Model.unused_method"}


def test_ctypes_layout_is_consumed_only_on_native_structure_subclasses() -> None:
    module = _module(
        "pkg.native",
        """
import ctypes as native
class Record(native.Structure):
    _fields_ = [('value', native.c_int)]
    unused = 1
class Plain:
    _fields_ = []
""",
    )
    contracts = framework_contracts({module.name: module})
    definitions = {definition.qualname for definition in _definitions(module.tree, contracts[module.name])}

    assert definitions == {"Record", "Record.unused", "Plain", "Plain._fields_"}


def test_a_mixin_callback_is_consumed_by_its_framework_subclass() -> None:
    module = _module(
        "pkg.mixins",
        """
from textual.screen import Screen
class Form:
    def on_mount(self): pass
    def unused(self): pass
class Plain:
    def on_mount(self): pass
class Dialog(Form, Screen): pass
""",
    )
    contracts = framework_contracts({module.name: module})
    definitions = {definition.qualname for definition in _definitions(module.tree, contracts[module.name])}

    assert definitions == {"Form", "Form.unused", "Plain", "Plain.on_mount", "Dialog"}


def test_settings_validation_is_registered_through_the_installed_base() -> None:
    module = _module(
        "pkg.settings",
        """
from pydantic_settings import BaseSettings as SettingsBase
from pydantic import field_validator as validate
class Settings(SettingsBase):
    @validate('value')
    def validate_value(self): pass
    @ordinary_wrapper
    def unused(self): pass
""",
    )
    contracts = framework_contracts({module.name: module})
    definitions = {definition.qualname for definition in _definitions(module.tree, contracts[module.name])}

    assert definitions == {"Settings", "Settings.unused"}


def test_assigned_validators_and_computed_fields_are_registered_only_on_models() -> None:
    module = _module(
        "pkg.models",
        """
from pydantic import BaseModel, field_validator as validator, computed_field
class Model(BaseModel):
    _normalize = validator('value')(normalize)
    @computed_field
    @property
    def total(self): return 1
    unused = ordinary_wrapper(normalize)
    class Plain:
        _normalize = validator('value')(normalize)
class Plain:
    _normalize = validator('value')(normalize)
""",
    )
    contracts = framework_contracts({module.name: module})
    definitions = {definition.qualname for definition in _definitions(module.tree, contracts[module.name])}
    assert definitions == {
        "Model",
        "Model.unused",
        "Model.Plain",
        "Model.Plain._normalize",
        "Plain",
        "Plain._normalize",
    }


def test_click_dispatch_overrides_are_reached_but_ordinary_methods_are_auditable() -> None:
    module = _module(
        "pkg.commands",
        """
from typer.core import TyperGroup as Group
class Commands(Group):
    def format_commands(self, ctx, formatter): pass
    def unused(self): pass
class Plain:
    def format_commands(self, ctx, formatter): pass
""",
    )
    contracts = framework_contracts({module.name: module})
    definitions = {definition.qualname for definition in _definitions(module.tree, contracts[module.name])}
    assert definitions == {"Commands", "Commands.unused", "Plain", "Plain.format_commands"}

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

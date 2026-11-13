"""An operation contract module types each registered request as validated and each result as serialised.

The module is rendered from the models a registry binds to a definition's public schemas, so a field the
window may leave out of a request is optional, a result field is always present, a model two definitions
share is written once, and the closing map names every definition's request and result. A string the
window types with a name of its own is written with that name and imported from where the window defines it.
"""

from __future__ import annotations

from dataclasses import dataclass

import pytest
from pydantic import BaseModel

from ..operation_contract_module import WindowType, render_contract_module

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]


class _Row(BaseModel):
    name: str
    note: str | None


class _ListRequest(BaseModel):
    profile_id: str
    year: int
    limit: int = 10


class _ListResult(BaseModel):
    rows: tuple[_Row, ...]
    limit: int = 10


class _AddRequest(BaseModel):
    profile_id: str
    name: str


class _AddResult(BaseModel):
    row: _Row


class _OpenRequest(BaseModel):
    profile_id: str
    source_path: str
    copy_path: str | None = None
    count: int = 0


class _OpenResult(BaseModel):
    opened: bool


@dataclass(frozen=True)
class _Contract:
    request_schema: str
    result_schema: str | None


@dataclass(frozen=True)
class _Binding:
    model_type: type[BaseModel]


class _Registry:
    """A registry binding two definitions that share the ``_Row`` model, and one with no public result."""

    _contracts = {
        "ledger.list": _Contract("list-request", "list-result"),
        "ledger.add": _Contract("add-request", "add-result"),
        "ledger.silent": _Contract("add-request", None),
        "ledger.open": _Contract("open-request", "open-result"),
    }
    _bindings = {
        "list-request": _Binding(_ListRequest),
        "list-result": _Binding(_ListResult),
        "add-request": _Binding(_AddRequest),
        "add-result": _Binding(_AddResult),
        "open-request": _Binding(_OpenRequest),
        "open-result": _Binding(_OpenResult),
    }

    def lookup_public_contract(self, definition_id: str, /) -> _Contract:
        return self._contracts[definition_id]

    def lookup_public_schema_binding(self, schema: str, /) -> _Binding:
        return self._bindings[schema]


_TOKEN = WindowType("FileToken", "./files")


def _module(*definitions: str, field_types: dict[tuple[str, str], WindowType] | None = None) -> str:
    return render_contract_module(
        _Registry(),
        header="// header\n",
        definitions=definitions,
        contracts_name="DemoContracts",
        subject="demo",
        field_types=field_types,
    )


def test_a_request_field_with_a_default_may_be_left_out_and_a_result_field_may_not() -> None:
    module = _module("ledger.list")
    assert "export type ListRequest = {\n  profile_id: string;\n  year: number;\n  limit?: number;\n};" in module
    assert "export type ListResult = {\n  rows: Row[];\n  limit: number;\n};" in module


def test_a_model_two_definitions_share_is_written_once() -> None:
    module = _module("ledger.list", "ledger.add")
    assert module.count("export type Row = {") == 1


def test_the_map_names_each_definitions_request_and_result_in_definition_order() -> None:
    module = _module("ledger.list", "ledger.add")
    assert module.startswith("// header\n")
    assert (
        'export type DemoContracts = {\n  "ledger.add": { request: AddRequest; result: AddResult; };\n'
        '  "ledger.list": { request: ListRequest; result: ListResult; };\n};'
    ) in module


def test_a_definition_with_no_public_result_is_refused() -> None:
    with pytest.raises(SystemExit, match=r"ledger.silent registers no public result"):
        _module("ledger.silent")


def test_a_string_the_window_types_by_name_is_written_with_it_and_imported() -> None:
    module = _module("ledger.open", field_types={("_OpenRequest", "source_path"): _TOKEN})
    assert module.startswith('// header\nimport type { FileToken } from "./files";\n')
    assert "  source_path: FileToken;\n  copy_path?: string | null;\n" in module


def test_a_nullable_string_keeps_its_null_when_the_window_types_it() -> None:
    module = _module("ledger.open", field_types={("_OpenRequest", "copy_path"): _TOKEN})
    assert "  source_path: string;\n  copy_path?: FileToken | null;\n" in module


def test_a_module_with_no_window_type_imports_nothing() -> None:
    assert "import" not in _module("ledger.open")


def test_a_window_type_for_a_property_the_schema_lacks_is_refused() -> None:
    with pytest.raises(
        SystemExit, match=r"FileToken is named for _OpenRequest.target, which the schema does not define"
    ):
        _module("ledger.open", field_types={("_OpenRequest", "target"): _TOKEN})
    with pytest.raises(SystemExit, match=r"FileToken is named for _Gone.source_path"):
        _module("ledger.open", field_types={("_Gone", "source_path"): _TOKEN})


def test_a_window_type_for_a_property_that_is_no_string_is_refused() -> None:
    with pytest.raises(SystemExit, match=r"FileToken stands for a string but the schema writes number"):
        _module("ledger.open", field_types={("_OpenRequest", "count"): _TOKEN})

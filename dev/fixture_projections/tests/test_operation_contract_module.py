"""An operation contract module types each registered request as validated and each result as serialised.

The module is rendered from the models a registry binds to a definition's public schemas, so a field the
window may leave out of a request is optional, a result field is always present, a model two definitions
share is written once, and the closing map names every definition's request and result.
"""

from __future__ import annotations

from dataclasses import dataclass

import pytest
from pydantic import BaseModel

from ..operation_contract_module import render_contract_module

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
    }
    _bindings = {
        "list-request": _Binding(_ListRequest),
        "list-result": _Binding(_ListResult),
        "add-request": _Binding(_AddRequest),
        "add-result": _Binding(_AddResult),
    }

    def lookup_public_contract(self, definition_id: str, /) -> _Contract:
        return self._contracts[definition_id]

    def lookup_public_schema_binding(self, schema: str, /) -> _Binding:
        return self._bindings[schema]


def _module(*definitions: str) -> str:
    return render_contract_module(
        _Registry(), header="// header\n", definitions=definitions, contracts_name="DemoContracts", subject="demo"
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

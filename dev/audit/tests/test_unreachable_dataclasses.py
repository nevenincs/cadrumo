"""Whole-record reads require a live, qualified dataclass consumer."""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

from ..unreachable_dataclasses import dataclass_member_uses
from ..unreachable_models import ShippedModule

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]


def _module(name: str, source: str) -> ShippedModule:
    return ShippedModule(name, Path(name + ".py"), False, ast.parse(source))


@pytest.mark.parametrize("consumer", ["asdict(make())", "serialize(make())"])
def test_serialized_nested_dataclass_fields_are_consumed(consumer: str) -> None:
    records = _module(
        "pkg.records",
        """
from dataclasses import dataclass, InitVar
from typing import ClassVar
@dataclass
class Row:
    value: str
    unused: ClassVar[str]
    input_only: InitVar[str]
    def orphan(self): pass
@dataclass
class Envelope:
    rows: tuple[Row, ...]
def make() -> Envelope:
    return Envelope(())
""",
    )
    consumer_module = _module(
        "pkg.consumer",
        f"""
from dataclasses import fields, asdict
from .records import make
def serialize(value):
    return {{field.name: serialize(getattr(value, field.name)) for field in fields(value)}}
{consumer}
""",
    )

    assert dataclass_member_uses(
        {records.name: records, consumer_module.name: consumer_module}, frozenset({consumer_module.name})
    ) == {("pkg.records", "Envelope.rows"), ("pkg.records", "Row.value")}


@pytest.mark.parametrize("expression", ["Row()", "show(Row())", "filtered(Row())", "shadowed(Row())"])
def test_construction_introspection_filtered_and_shadowed_reads_do_not_clear_fields(expression: str) -> None:
    module = _module(
        "pkg.records",
        f"""
from dataclasses import dataclass, fields
@dataclass
class Row:
    orphan: str
def show(value):
    print(fields(value))
def filtered(value):
    return {{field.name: getattr(value, field.name) for field in fields(value) if field.name == 'something'}}
def shadowed(value, getattr):
    return {{field.name: getattr(value, field.name) for field in fields(value)}}
{expression}
""",
    )

    assert dataclass_member_uses({module.name: module}, frozenset({module.name})) == frozenset()

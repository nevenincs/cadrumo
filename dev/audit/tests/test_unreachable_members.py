"""Member consumers retain their defining module and lexical receiver."""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

from ..unreachable_members import resolved_member_uses
from ..unreachable_models import ShippedModule

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]


def test_imported_class_constructor_and_typed_receivers_are_qualified() -> None:
    module = ShippedModule(
        "pkg.consumer",
        Path("consumer.py"),
        False,
        ast.parse("""
from .records import Record as Row
Row.factory()
record = Row()
record.value
def read(other: Row):
    return other.kind
"""),
    )

    assert resolved_member_uses(module, frozenset({"pkg.records"})) == {
        ("pkg.records", "Record.factory"),
        ("pkg.records", "Record.value"),
        ("pkg.records", "Record.kind"),
    }


def test_untyped_and_shadowed_receivers_cannot_clear_an_imported_member() -> None:
    module = ShippedModule(
        "pkg.consumer",
        Path("consumer.py"),
        False,
        ast.parse("""
from .records import Record
def typed(record: Record):
    return record.used
def untyped(record):
    return record.orphan
def shadowed(Record):
    return Record.orphan
def unknown_result():
    record = build()
    return record.orphan
"""),
    )

    assert resolved_member_uses(module, frozenset({"pkg.records"})) == {("pkg.records", "Record.used")}

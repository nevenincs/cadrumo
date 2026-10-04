"""Member consumers retain their defining module and lexical receiver."""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

from ..unreachable_members import resolved_member_uses
from ..unreachable_models import ShippedModule
from ..unreachable_receiver_types import receiver_types

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


def test_defining_constructor_and_return_annotations_resolve_imported_instances() -> None:
    records = ShippedModule(
        "pkg.records",
        Path("records.py"),
        False,
        ast.parse("""
class Record: pass
INSTANCE = Record()
def build() -> Record:
    return Record()
def unknown():
    return Record()
"""),
    )
    caller = ShippedModule(
        "dev.consumer",
        Path("consumer.py"),
        False,
        ast.parse("""
from pkg.records import INSTANCE, build, unknown
INSTANCE.value
record = build()
record.typed
untyped = unknown()
untyped.orphan
"""),
    )

    assert resolved_member_uses(
        caller, frozenset({records.name}), receivers=receiver_types({records.name: records})
    ) == {
        (records.name, "Record.value"),
        (records.name, "Record.typed"),
        (records.name, "unknown.orphan"),
    }


def test_declared_context_and_nested_field_consumers_keep_their_owner() -> None:
    records = ShippedModule(
        "pkg.records",
        Path("records.py"),
        False,
        ast.parse("""
from contextlib import contextmanager
from collections.abc import Iterator
class Record: pass
class Holder:
    record: Record
@contextmanager
def opened() -> Iterator[Record]:
    yield Record()
def build() -> Holder:
    return Holder()
"""),
    )
    caller = ShippedModule(
        "dev.consumer",
        Path("consumer.py"),
        False,
        ast.parse("""
from pkg.records import opened, build
with opened() as record:
    record.used
build().record.nested
with unknown() as record:
    record.orphan
"""),
    )

    uses = resolved_member_uses(caller, frozenset({records.name}), receivers=receiver_types({records.name: records}))

    assert (records.name, "Record.used") in uses
    assert (records.name, "Holder.record") in uses
    assert (records.name, "Record.nested") in uses
    assert (records.name, "Record.orphan") not in uses

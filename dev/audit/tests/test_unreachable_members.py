"""Member consumers retain their defining module and lexical receiver."""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

from dev._paths import REPO_ROOT

from ..unreachable_members import resolved_member_uses
from ..unreachable_models import ShippedModule
from ..unreachable_receiver_types import receiver_types

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]


def test_isinstance_filtered_collections_resolve_indexed_members_without_guessing() -> None:
    records = ShippedModule("pkg.records", Path("records.py"), False, ast.parse("class Record: pass"))
    caller = ShippedModule(
        "dev.consumer",
        Path("consumer.py"),
        False,
        ast.parse("""
from pkg.records import Record
def read(unknown):
    rows = [row for row in unknown if isinstance(row, Record)]
    rows[0].used()
    item = rows[0]
    item.selected()
    rows.unproven()
    rows[:1].slice_unknown()
    plain = [row for row in unknown]
    plain[0].unproven()
def shadow(unknown, isinstance):
    rows = [row for row in unknown if isinstance(row, Record)]
    rows[0].shadow_unknown()
def sibling(rows):
    rows[0].sibling_unknown()
"""),
    )
    uses = resolved_member_uses(caller, frozenset({records.name}), receivers=receiver_types({records.name: records}))
    assert {pair for pair in uses if pair[1].startswith("Record.")} == {
        (records.name, "Record.used"),
        (records.name, "Record.selected"),
    }


def test_installed_review_acceptance_cleanup_resolves_its_actual_screen() -> None:
    modules = {}
    for name, relative in (
        ("cadrumo.entrypoints.tui.google_saved_review", "src/cadrumo/entrypoints/tui/google_saved_review.py"),
        ("dev.acceptance.review.installed_google_review_tui", "dev/acceptance/review/installed_google_review_tui.py"),
    ):
        path = REPO_ROOT / relative
        modules[name] = ShippedModule(name, path, False, ast.parse(path.read_bytes()))
    screen, consumer = modules.values()
    uses = resolved_member_uses(consumer, frozenset({screen.name}), receivers=receiver_types(modules))
    assert (screen.name, "GoogleSavedReviewScreen.reject_pending_prepublication") in uses


def test_exception_handler_retains_typed_receivers_but_shadows_its_exception_name() -> None:
    records = ShippedModule("pkg.records", Path("records.py"), False, ast.parse("class Record: pass"))
    caller = ShippedModule(
        "dev.consumer",
        Path("consumer.py"),
        False,
        ast.parse("""
from pkg.records import Record
def read(record: Record):
    try:
        raise RuntimeError()
    except Exception as Record:
        record.cleanup()
        Record.unproven()
"""),
    )
    uses = resolved_member_uses(caller, frozenset({records.name}), receivers=receiver_types({records.name: records}))
    assert (records.name, "Record.cleanup") in uses
    assert (records.name, "Record.unproven") not in uses


def test_iterated_return_fields_and_comprehensions_keep_qualified_elements() -> None:
    records = ShippedModule(
        "pkg.records",
        Path("records.py"),
        False,
        ast.parse("""
from collections.abc import Sequence
class Record: pass
class Other: pass
class Holder:
    rows: tuple[Record, ...]
def build() -> tuple[Record, ...]: ...
def mixed() -> tuple[Record, Other]: ...
def unknown(): ...
def holder() -> Holder: ...
"""),
    )
    caller = ShippedModule(
        "pkg.consumer",
        Path("consumer.py"),
        False,
        ast.parse("""
from .records import Record, build, mixed, unknown, holder
for record in build():
    record.direct
rows = build()
values = [record.comp for record in rows]
for record in holder().rows:
    record.nested
def typed(rows: tuple[Record, ...]):
    return tuple(record.argument for record in rows)
for record in mixed():
    record.mixed_unknown
for record in unknown():
    record.unknown
def shadow(build):
    return [record.shadow_unknown for record in build()]
def sibling(rows):
    return [record.sibling_unknown for record in rows]
"""),
    )
    uses = resolved_member_uses(caller, frozenset({records.name}), receivers=receiver_types({records.name: records}))
    assert {pair for pair in uses if pair[1].startswith("Record.")} == {
        (records.name, "Record.direct"),
        (records.name, "Record.comp"),
        (records.name, "Record.nested"),
        (records.name, "Record.argument"),
    }


def test_shadowed_iterable_annotation_does_not_establish_a_class_element() -> None:
    records = ShippedModule(
        "pkg.records",
        Path("records.py"),
        False,
        ast.parse("""
from vendor import Sequence
class Record: pass
def build() -> Sequence[Record]: ...
"""),
    )
    assert receiver_types({records.name: records}).iterables == {}


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


def test_nested_comprehension_shadow_does_not_borrow_outer_element_type() -> None:
    records = ShippedModule("pkg.records", Path("records.py"), False, ast.parse("class Record: pass"))
    caller = ShippedModule(
        "pkg.consumer",
        Path("consumer.py"),
        False,
        ast.parse("""
from .records import Record
def inspect(rows: tuple[Record, ...], unknown):
    return [(record.outer, [record.unproven for record in unknown]) for record in rows]
"""),
    )
    uses = resolved_member_uses(caller, frozenset({records.name}), receivers=receiver_types({records.name: records}))
    assert (records.name, "Record.outer") in uses
    assert (records.name, "Record.unproven") not in uses


def test_qualified_canonical_iterable_annotations_retain_element_type() -> None:
    records = ShippedModule(
        "pkg.records",
        Path("records.py"),
        False,
        ast.parse("""
import collections.abc as abc
import typing
class Record: pass
def sequence() -> abc.Sequence[Record]: ...
def iterable() -> typing.Iterable[Record]: ...
"""),
    )
    facts = receiver_types({records.name: records})
    assert facts.iterables == {
        "pkg.records.sequence": "pkg.records.Record",
        "pkg.records.iterable": "pkg.records.Record",
    }

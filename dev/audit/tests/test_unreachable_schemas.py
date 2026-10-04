"""Live schema use retains wire fields without hiding ordinary dead members."""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

from ..unreachable_frameworks import framework_contracts
from ..unreachable_models import ShippedModule
from ..unreachable_schemas import schema_member_uses

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]


def _module(name: str, source: str) -> ShippedModule:
    return ShippedModule(name, Path(name + ".py"), False, ast.parse(source))


def test_validated_nested_schema_consumes_fields_and_enum_alternatives() -> None:
    records = _module(
        "pkg.records",
        """
from pydantic import BaseModel as Record
from enum import StrEnum
from typing import ClassVar
class Kind(StrEnum):
    FIRST = 'first'
    SECOND = 'second'
class Nested(Record):
    kind: Kind
class Parent(Record):
    version: int = 1
class Envelope(Parent):
    nested: 'Nested'
    unused_constant: ClassVar[int] = 3
    UNANNOTATED = 4
    def unused(self): pass
class ImportedOnly(Record):
    orphan: int = 1
class Plain:
    value: int = 1
""",
    )
    caller = _module(
        "pkg.caller",
        """
from .records import Envelope as Payload, ImportedOnly, Plain
Payload.model_validate_json('{}')
Plain()
""",
    )
    modules = {module.name: module for module in (records, caller)}
    uses = schema_member_uses(modules, frozenset(modules), framework_contracts(modules))

    assert uses == frozenset(
        (records.name, member)
        for member in ("Envelope.nested", "Parent.version", "Nested.kind", "Kind.FIRST", "Kind.SECOND")
    )


def test_construction_is_qualified_and_unreachable_callers_do_not_clear_fields() -> None:
    first = _module("pkg.first", "from pydantic import BaseModel\nclass Payload(BaseModel):\n value: int = 1")
    second = _module("pkg.second", "from pydantic import BaseModel\nclass Payload(BaseModel):\n value: int = 2")
    live = _module("pkg.live", "from .first import Payload as First\nFirst()")
    dead = _module("pkg.dead", "from .second import Payload\nPayload()")
    modules = {module.name: module for module in (first, second, live, dead)}

    uses = schema_member_uses(modules, frozenset({first.name, second.name, live.name}), framework_contracts(modules))

    assert uses == frozenset({(first.name, "Payload.value")})


def test_local_imports_factories_and_typed_schema_registration_are_consumers() -> None:
    records = _module(
        "pkg.records",
        """
from pydantic import BaseModel
from typing import Self
class Payload(BaseModel):
    version: int = 1
    @classmethod
    def from_record(cls) -> Self:
        return cls()
class Response(BaseModel):
    response_version: int = 1
""",
    )
    registration = _module(
        "pkg.registration",
        """
from pydantic import BaseModel
def register(*, model: type[BaseModel]):
    return model.model_json_schema()
""",
    )
    caller = _module(
        "pkg.caller",
        """
from .registration import register
from .records import Response
def read():
    from .records import Payload
    return Payload.from_record()
register(model=Response)
""",
    )
    modules = {module.name: module for module in (records, registration, caller)}

    assert schema_member_uses(modules, frozenset(modules), framework_contracts(modules)) == frozenset(
        {(records.name, "Payload.version"), (records.name, "Response.response_version")}
    )


def test_shadowed_constructor_and_ceremonial_parameter_do_not_consume_a_schema() -> None:
    records = _module("pkg.records", "from pydantic import BaseModel\nclass Payload(BaseModel):\n unused: int = 1")
    caller = _module(
        "pkg.caller",
        """
from pydantic import BaseModel
from .records import Payload
def shadow(Payload):
    return Payload()
def mention(*, model: type[BaseModel]):
    print(model)
mention(model=Payload)
""",
    )
    modules = {module.name: module for module in (records, caller)}

    assert schema_member_uses(modules, frozenset(modules), framework_contracts(modules)) == frozenset()

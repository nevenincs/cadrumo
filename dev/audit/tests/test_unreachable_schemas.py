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


def test_validated_discriminated_aliases_keep_nested_wire_fields_without_import_only_exemptions() -> None:
    records = _module(
        "pkg.records",
        """
from pydantic import BaseModel, Field
from typing import Annotated, Literal
class First(BaseModel):
    kind: Literal['first'] = 'first'
    first_value: int
class Second(BaseModel):
    kind: Literal['second'] = 'second'
    second_value: str
class Unused(BaseModel):
    orphan: int
type Choice = Annotated[First | Second, Field(discriminator='kind')]
type Nested = Choice
type Unconsumed = Unused
class Envelope(BaseModel):
    selected: Nested
""",
    )
    caller = _module("pkg.caller", "from .records import Envelope, Unconsumed\nEnvelope.model_validate_json('{}')")
    modules = {module.name: module for module in (records, caller)}
    uses = schema_member_uses(modules, frozenset(modules), framework_contracts(modules))
    assert uses == frozenset(
        (records.name, member)
        for member in ("Envelope.selected", "First.kind", "First.first_value", "Second.kind", "Second.second_value")
    )


def test_type_adapter_consumes_an_explicit_alias_without_following_unused_recursive_aliases() -> None:
    records = _module(
        "pkg.records",
        """
from pydantic import BaseModel
class Payload(BaseModel):
    value: int
type Choice = Payload
type Recursive = Recursive
""",
    )
    caller = _module(
        "pkg.caller", "from pydantic import TypeAdapter\nfrom .records import Choice, Recursive\nTypeAdapter(Choice)"
    )
    modules = {module.name: module for module in (records, caller)}
    assert schema_member_uses(modules, frozenset(modules), framework_contracts(modules)) == frozenset(
        {(records.name, "Payload.value")}
    )


def test_pep695_generic_schema_arguments_keep_their_exact_position() -> None:
    records = _module(
        "pkg.records",
        """
from pydantic import BaseModel
class Payload(BaseModel):
    value: int
class Ignored(BaseModel):
    orphan: int
""",
    )
    caller = _module(
        "pkg.caller",
        """
from pydantic import BaseModel
from .records import Payload, Ignored
def validate[T: BaseModel](label: str, model: type[T]):
    return model.model_validate_json('{}')
validate(Ignored, Payload)
""",
    )
    modules = {module.name: module for module in (records, caller)}
    assert schema_member_uses(modules, frozenset(modules), framework_contracts(modules)) == frozenset(
        {(records.name, "Payload.value")}
    )


def test_generic_repository_slots_require_actual_schema_building_and_construction() -> None:
    records = _module(
        "pkg.records",
        """
from pydantic import BaseModel
from typing import ClassVar, cast
class Payload(BaseModel):
    value: int
class ImportedOnly(BaseModel):
    orphan: int
class Unconsumed(BaseModel):
    orphan: int
class Envelope[T: BaseModel](BaseModel):
    payload: T
def build[T: BaseModel](payload: type[T], *, envelope: type[Envelope[T]] = Envelope):
    return envelope.__class_getitem__(payload)
class Repository[T: BaseModel]:
    payload_type: ClassVar[type[BaseModel]]
    @classmethod
    def payload_model(cls) -> type[T]:
        payload_type = getattr(cls, 'payload_type', None)
        return cast('type[T]', payload_type)
    def schema(self):
        return build(self.payload_model())
class Live(Repository[Payload]):
    payload_type: ClassVar[type[Payload]] = Payload
class Unconstructed(Repository[ImportedOnly]):
    payload_type: ClassVar[type[ImportedOnly]] = ImportedOnly
class Diagnostic:
    payload_type: ClassVar[type[Unconsumed]] = Unconsumed
    @classmethod
    def payload_model(cls):
        return cls.payload_type
    def report(self):
        return repr(self.payload_model())
Live()
Diagnostic()
""",
    )
    modules = {records.name: records}
    uses = schema_member_uses(modules, frozenset(modules), framework_contracts(modules))
    assert (records.name, "Payload.value") in uses
    assert (records.name, "ImportedOnly.orphan") not in uses
    assert (records.name, "Unconsumed.orphan") not in uses


def test_rebound_schema_parameter_does_not_consume_the_supplied_model() -> None:
    record = _module("pkg.record", "from pydantic import BaseModel\nclass Payload(BaseModel):\n orphan: int")
    caller = _module(
        "pkg.caller",
        """
from pydantic import BaseModel
from .record import Payload
def inspect[T: BaseModel](model: type[T]):
    model = unknown()
    return model.model_validate_json('{}')
inspect(Payload)
""",
    )
    modules = {module.name: module for module in (record, caller)}
    assert schema_member_uses(modules, frozenset(modules), framework_contracts(modules)) == frozenset()


def test_shadowed_getattr_cannot_prove_a_repository_payload_getter() -> None:
    record = _module(
        "pkg.record",
        """
from pydantic import BaseModel
from typing import ClassVar
from vendor import getattr
class Payload(BaseModel):
    orphan: int
def validate(model: type[BaseModel]):
    return model.model_validate_json('{}')
class Repository:
    payload_type: ClassVar[type[Payload]] = Payload
    def payload_model(self):
        return getattr(self, 'payload_type', None)
    def schema(self):
        return validate(self.payload_model())
Repository()
""",
    )
    modules = {record.name: record}
    assert (record.name, "Payload.orphan") not in schema_member_uses(
        modules, frozenset(modules), framework_contracts(modules)
    )


def test_constructed_repository_payload_override_reaches_inherited_schema_factory() -> None:
    record = _module(
        "pkg.record",
        """
from pydantic import BaseModel
from typing import ClassVar
class Payload(BaseModel):
    wire_field: int
class ImportedOnly(BaseModel):
    orphan: int
def validate(model: type[BaseModel]):
    return model.model_validate_json('{}')
class Repository:
    payload_type: ClassVar[type[BaseModel]]
    @classmethod
    def payload_model(cls):
        return cls.payload_type
    def decode(self):
        return validate(self.payload_model())
class Live(Repository):
    @classmethod
    def payload_model(cls) -> type[Payload]:
        return Payload
class Unconstructed(Repository):
    @classmethod
    def payload_model(cls) -> type[ImportedOnly]:
        return ImportedOnly
Live()
""",
    )
    modules = {record.name: record}
    uses = schema_member_uses(modules, frozenset(modules), framework_contracts(modules))
    assert (record.name, "Payload.wire_field") in uses
    assert (record.name, "ImportedOnly.orphan") not in uses

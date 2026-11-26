"""Exact identities for a session's already validated form projection.

Only the declared frozen form graphs qualify. A new mutable or unrecognised
shape takes the ordinary projection path; this module never admits a read.
The identity copies values, preserving their types and decimal representation,
and holds live schema objects by identity so rebuilding a schema invalidates it.
Completing a deferred schema during the first fill may intentionally cause one
additional miss rather than reusing a proof under a different schema identity.
"""

from __future__ import annotations

from collections.abc import Hashable, Iterable
from dataclasses import dataclass, is_dataclass
from datetime import date, datetime, timezone
from decimal import Decimal
from enum import Enum
from types import MappingProxyType
from typing import TypeGuard, get_args, override
from uuid import UUID
from zoneinfo import ZoneInfo

from pydantic import BaseModel
from pydantic_core import TzInfo

from ...core.errors.hierarchy import CadrumoError
from ...core.external_constants import OutputLanguage
from ...domain.modelos.codes import ModeloCode
from ...domain.modelos.verification_report import ModeloVerificationFinding
from ..operations.dataclass_fields import dataclass_instance_fields, dataclass_type_hints
from ..operations.public_mirror import bare_annotation
from .work_form_service import ModeloWorkFormLoadV1

__all__ = [
    "FormIdentities",
    "FormProjectionContext",
    "FormProjectionPair",
    "FormSectionPair",
    "form_identities",
    "form_projection_is_immutable",
]


@dataclass(frozen=True, slots=True)
class FormProjectionContext:
    """Fresh admission and authority coordinates, never a substitute for admission."""

    profile_id: UUID
    work_unit_id: str
    work_unit_record_digest: str
    calculation_head_digest: str
    calculation_revision_id: str | None
    logical_generation: str
    language: OutputLanguage


@dataclass(frozen=True, slots=True)
class FormProjectionPair:
    """A public form and the canonical inverse obtained by strict restoration."""

    public: BaseModel
    canonical: ModeloWorkFormLoadV1


@dataclass(frozen=True, slots=True, eq=False)
class _Identity:
    value: object

    @override
    def __eq__(self, other: object) -> bool:
        return isinstance(other, _Identity) and self.value is other.value

    @override
    def __hash__(self) -> int:
        return id(self.value)


class _NotReusableError(CadrumoError):
    """An unproved shape must use the ordinary validating projection."""


def _class(value: object) -> TypeGuard[type[object]]:
    return isinstance(value, type)


def _tuple(value: object) -> TypeGuard[tuple[object, ...]]:
    return type(value) is tuple


def _fact_map(value: object) -> TypeGuard[MappingProxyType[object, object]]:
    return isinstance(value, MappingProxyType)


def _zone_key(value: object) -> str:
    if not isinstance(value, str):
        raise _NotReusableError
    return value


def _schemas(root: type[BaseModel]) -> tuple[tuple[Hashable, ...], frozenset[type[object]]]:
    pending: list[object] = [root]
    seen: set[type[object]] = set()
    result: list[Hashable] = []
    while pending:
        annotation = bare_annotation(pending.pop())
        pending.extend(get_args(annotation))
        if not _class(annotation) or annotation in seen:
            continue
        seen.add(annotation)
        if issubclass(annotation, BaseModel):
            if annotation.model_config.get("frozen") is not True:
                raise _NotReusableError
            result.append(
                (
                    annotation,
                    _Identity(annotation.__pydantic_core_schema__),
                    _Identity(annotation.__pydantic_validator__),
                    _Identity(annotation.__pydantic_serializer__),
                    tuple(
                        (name, _Identity(field), _Identity(field.annotation))
                        for name, field in annotation.model_fields.items()
                    ),
                )
            )
            pending.extend(field.annotation for field in annotation.model_fields.values())
        elif is_dataclass(annotation):
            if getattr(getattr(annotation, "__dataclass_params__", None), "frozen", False) is not True:
                raise _NotReusableError
            result.append(annotation)
            pending.extend(dataclass_type_hints(annotation).values())
    return tuple(result), frozenset(seen)


class _ValueKind(Enum):
    COMPOUND = "compound"


_NOT_SCALAR = _ValueKind.COMPOUND


class _Snapshot:
    def __init__(self, allowed: frozenset[type[object]], *, capture: bool = True) -> None:
        self.allowed = allowed
        self.capture = capture
        self.memo: dict[int, Hashable] = {}
        self.active: set[int] = set()

    def _atom(self, cls: type[object], value: Hashable) -> Hashable:
        return (cls, value) if self.capture else None

    def _scalar(self, value: object) -> Hashable:
        cls = type(value)
        if value is None:
            return (type(None),) if self.capture else None
        if isinstance(value, (str, int, bytes)) and cls in (str, int, bool, bytes):
            return self._atom(cls, value)
        if isinstance(value, ModeloCode) and cls is ModeloCode and not vars(value):
            return self._atom(cls, str(value))
        if isinstance(value, Enum) and cls in self.allowed:
            return self._atom(cls, self.value(value.value))
        return self._value_object(value)

    def _value_object(self, value: object) -> Hashable:
        cls = type(value)
        if isinstance(value, Decimal) and cls is Decimal:
            return self._atom(cls, value.as_tuple())
        if isinstance(value, (datetime, date)) and cls in (datetime, date):
            return self._date(value)
        if isinstance(value, UUID) and cls is UUID:
            return self._atom(cls, value.hex)
        return _NOT_SCALAR

    def _date(self, value: date) -> Hashable:
        if isinstance(value, datetime):
            return self._atom(type(value), (value.isoformat(), value.fold, self._timezone(value)))
        return self._atom(type(value), (value.isoformat(), 0, None))

    def _timezone(self, value: datetime) -> Hashable:
        zone = value.tzinfo
        if zone is None:
            return None
        if type(zone) not in (timezone, ZoneInfo, TzInfo):
            raise _NotReusableError
        zone_key = None
        if isinstance(zone, ZoneInfo):
            zone_key = _zone_key(zone.key)
        return (type(zone), zone_key, zone.utcoffset(value), zone.tzname(value))

    def value(self, value: object) -> Hashable:
        scalar = self._scalar(value)
        if scalar is not _NOT_SCALAR:
            return scalar
        identity = id(value)
        if identity in self.active:
            raise _NotReusableError
        if identity in self.memo:
            return self.memo[identity]
        self.active.add(identity)
        try:
            result = self._compound(value)
            self.memo[identity] = result
            return result
        finally:
            self.active.remove(identity)

    def _compound(self, value: object) -> Hashable:
        cls = type(value)
        if _tuple(value):
            return self._sequence(value)
        if cls not in self.allowed:
            raise _NotReusableError
        if isinstance(value, BaseModel):
            return self._model(value)
        if is_dataclass(value) and not isinstance(value, type):
            return self._record(value)
        raise _NotReusableError

    def _sequence(self, value: tuple[object, ...]) -> Hashable:
        if not self.capture:
            for child in value:
                self.value(child)
            return None
        return (tuple, tuple(self.value(child) for child in value))

    def _model(self, value: BaseModel) -> Hashable:
        cls = type(value)
        declared = cls.model_fields
        if bool(value.model_extra) or bool(value.__pydantic_private__) or vars(value).keys() != declared.keys():
            raise _NotReusableError
        if cls is ModeloVerificationFinding:
            if not self.capture:
                for name in declared:
                    self._field(value, name)
                return None
            return (cls, tuple((name, self._field(value, name)) for name in declared))
        held = vars(value)
        if not self.capture:
            for name in declared:
                self.value(held[name])
            return None
        return (cls, tuple((name, self.value(held[name])) for name in declared))

    def _record(self, value: object) -> Hashable:
        declared = dataclass_instance_fields(value)
        if not self.capture:
            for field in declared:
                self.value(getattr(value, field.name))
            return None
        return (type(value), tuple((field.name, self.value(getattr(value, field.name))) for field in declared))

    def _field(self, model: BaseModel, name: str) -> Hashable:
        value: object = getattr(model, name)
        if type(model) is ModeloVerificationFinding and name == "message_facts":
            # This owner's validator copies into a new, private backing dictionary.
            # The key copies entries; only the strictly restored owner is retained.
            # A generic mapping proxy may wrap somebody else's mutable dictionary.
            if not _fact_map(value):
                raise _NotReusableError
            entries: list[Hashable] = []
            for key, item in value.items():
                if type(key) is not str:
                    raise _NotReusableError
                copied_key, copied_item = self.value(key), self.value(item)
                if self.capture:
                    entries.append((copied_key, copied_item))
            return (MappingProxyType, tuple(entries)) if self.capture else None
        return self.value(value)


def form_projection_is_immutable(
    value: BaseModel, public_type: type[BaseModel], *, settled: Iterable[object] = ()
) -> bool:
    """Check retained values without allocating a second, unused value-key tree.

    ``settled`` are parts of ``value`` this check already passed, the very
    objects and not copies of them; they are not walked again.
    """
    try:
        _, canonical_types = _schemas(ModeloWorkFormLoadV1)
        _, public_types = _schemas(public_type)
        snapshot = _Snapshot(canonical_types | public_types, capture=False)
        snapshot.memo.update((id(part), None) for part in settled)
        snapshot.value(value)
    except _NotReusableError:
        return False
    return True


@dataclass(frozen=True, slots=True)
class FormSectionPair:
    """One section's public mirror and the canonical section its strict restoration gave."""

    public: BaseModel
    canonical: BaseModel


@dataclass(frozen=True, slots=True)
class FormIdentities:
    """One form's exact identity and, page by page, each section's, under the schemas they were read with."""

    schemas: Hashable
    form: Hashable
    sections: tuple[tuple[Hashable, ...], ...]


def form_identities(load: ModeloWorkFormLoadV1, public_type: type[BaseModel]) -> FormIdentities | None:
    """Copy the form's and each section's exact values in one walk; ``None`` declines reuse.

    ``form`` copies exact immutable values and the current schemas; this is an eligibility check,
    not validation. A section's identity is the same kind of copy, so two sections share one only when
    every value in them, its type and its decimal representation are the same.
    """
    try:
        canonical_schema, canonical_types = _schemas(ModeloWorkFormLoadV1)
        public_schema, public_types = _schemas(public_type)
        snapshot = _Snapshot(canonical_types | public_types)
        sections = tuple(tuple(snapshot.value(section) for section in page.sections) for page in load.form.pages)
        form = (canonical_schema, public_schema, snapshot.value(load))
    except _NotReusableError:
        return None
    return FormIdentities(schemas=(canonical_schema, public_schema), form=form, sections=sections)

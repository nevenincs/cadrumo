"""Private transforms for strict public operation mirrors."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import is_dataclass
from datetime import date
from decimal import Decimal
from types import UnionType
from typing import Union, cast, get_args, get_origin, get_type_hints

from pydantic import BaseModel

from . import public_mirror as _mirror
from ._dataclass_fields import dataclass_instance_fields


def _scalar(value: object) -> _mirror.PublicScalarValueV1:
    if value is None:
        return _mirror.PublicScalarValueV1(kind="null", text="")
    if isinstance(value, bool):
        return _mirror.PublicScalarValueV1(kind="boolean", text="true" if value else "false")
    if isinstance(value, int):
        return _mirror.PublicScalarValueV1(kind="integer", text=str(value))
    if isinstance(value, Decimal):
        return _mirror.PublicScalarValueV1(kind="decimal", text=str(value))
    if isinstance(value, date):
        return _mirror.PublicScalarValueV1(kind="date", text=value.isoformat())
    if isinstance(value, str):
        return _mirror.PublicScalarValueV1(kind="string", text=value)
    raise TypeError("unsupported public-mirror scalar")


def _fact_entry(key: str, value: object) -> _mirror.PublicFactEntryV1:
    scalar = _scalar(value)
    if scalar.kind == "date":
        raise TypeError("fact maps cannot contain dates")
    return _mirror.PublicFactEntryV1(key=key, kind=scalar.kind, text=scalar.text)


def _mapping_key(value: object) -> str:
    if not isinstance(value, str):
        raise TypeError("public-mirror mapping key must be text")
    return value


def _mapping_text(value: object) -> str:
    if not isinstance(value, str):
        raise TypeError("public-mirror mapping value must be text")
    return value


def _public_model_type(annotation: object, value: object) -> type[BaseModel] | None:
    annotation = _mirror.bare_annotation(annotation)
    if isinstance(annotation, type) and issubclass(annotation, BaseModel):
        return annotation
    origin = get_origin(annotation)
    if origin in (Union, UnionType):
        for choice in get_args(annotation):
            candidate = _mirror.bare_annotation(choice)
            if not isinstance(candidate, type) or not issubclass(candidate, BaseModel):
                continue
            if value is None:
                continue
            # Distinct union arms retain their canonical class-name suffix.
            if candidate.__name__.removeprefix("Public") == type(value).__name__:
                return candidate
    return None


def _project_mapping(value: Mapping[object, object], public: object) -> object:
    if not isinstance(public, type) and get_origin(public) is tuple:
        item = get_args(public)[0]
        if item is _mirror.PublicFactEntryV1:
            return tuple(_fact_entry(_mapping_key(key), fact) for key, fact in value.items())
        if item is _mirror.PublicTextEntryV1:
            return tuple(
                _mirror.PublicTextEntryV1(key=_mapping_key(key), value=_mapping_text(fact))
                for key, fact in value.items()
            )
    raise TypeError("unsupported public-mirror mapping")


def _project_tuple(
    value: tuple[object, ...],
    canonical: object,
    public: object,
    omissions: Mapping[type[BaseModel], frozenset[str]],
) -> tuple[object, ...]:
    canonical_args = get_args(canonical)
    public_args = get_args(public)
    if get_origin(public) is not tuple or not public_args:
        raise TypeError("public-mirror tuple changed its public shape")
    if len(public_args) == 2 and public_args[1] is Ellipsis:
        canonical_item = canonical_args[0] if canonical_args else object
        return tuple(project_public_value(item, canonical_item, public_args[0], omissions) for item in value)
    if len(value) != len(public_args):
        raise ValueError("public-mirror fixed tuple changed arity")
    return tuple(
        project_public_value(item, canonical_args[index], public_args[index], omissions)
        for index, item in enumerate(value)
    )


def _project_model(
    value: BaseModel | object,
    public: object,
    omissions: Mapping[type[BaseModel], frozenset[str]],
) -> object:
    target = _public_model_type(public, value)
    if target is None:
        raise TypeError("public-mirror model arm is unavailable")
    if isinstance(value, BaseModel) and target is type(value):
        return target.model_validate_json(value.model_dump_json(), strict=True)
    target.model_rebuild()
    target_fields = target.model_fields
    if isinstance(value, BaseModel):
        source_fields = type(value).model_fields
        source_annotations = {name: field.annotation for name, field in source_fields.items()}
    else:
        source_fields = {field.name: field for field in dataclass_instance_fields(value)}
        source_annotations = get_type_hints(type(value))
    allowed_missing = omissions.get(target, frozenset())
    if frozenset(set(source_fields) - set(target_fields)) != allowed_missing or set(target_fields) - set(source_fields):
        raise ValueError("public-mirror model field inventory drifted")
    return target.model_validate(
        {
            name: project_public_value(
                getattr(value, name),
                source_annotations[name],
                field.annotation,
                omissions,
            )
            for name, field in target_fields.items()
        }
    )


def project_public_value(
    value: object,
    canonical: object,
    public: object,
    omissions: Mapping[type[BaseModel], frozenset[str]],
) -> object:
    if value is None:
        return None
    canonical, public = _mirror.bare_annotation(canonical), _mirror.bare_annotation(public)
    if public is _mirror.PublicScalarValueV1:
        return _scalar(value)
    if isinstance(value, Mapping):
        return _project_mapping(cast(Mapping[object, object], value), public)
    if isinstance(value, tuple):
        return _project_tuple(cast(tuple[object, ...], value), canonical, public, omissions)
    if isinstance(value, BaseModel) or is_dataclass(value):
        return _project_model(value, public, omissions)
    if isinstance(value, Decimal):
        return str(value)
    if public is str and isinstance(value, str):
        return str(value)
    return value

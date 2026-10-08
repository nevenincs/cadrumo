"""Private restoration for strict public operation mirrors."""

from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import is_dataclass
from datetime import date
from decimal import Decimal, InvalidOperation
from types import UnionType
from typing import Union, cast, get_args, get_origin, get_type_hints

from pydantic import BaseModel
from pydantic.fields import FieldInfo

from . import public_mirror as _mirror
from ._dataclass_fields import dataclass_type_fields

type _MirrorCompletion = Callable[[type[object], dict[str, object], BaseModel], None]


def _unscalar(value: _mirror.PublicScalarValueV1) -> str | int | bool | Decimal | date | None:
    if value.kind == "null":
        return None
    if value.kind == "boolean":
        return value.text == "true"
    if value.kind == "integer":
        return int(value.text)
    if value.kind == "decimal":
        return Decimal(value.text)
    if value.kind == "date":
        return date.fromisoformat(value.text)
    return value.text


def _canonical_model_type(value: BaseModel, canonical: object) -> type[object]:
    if get_origin(canonical) not in (Union, UnionType):
        if not isinstance(canonical, type):
            raise TypeError("public-mirror canonical model changed")
        return canonical
    options = [item for item in get_args(canonical) if isinstance(_mirror.bare_annotation(item), type)]
    matches = [
        candidate
        for item in options
        if isinstance(candidate := _mirror.bare_annotation(item), type)
        and value.__class__.__name__.removeprefix("Public") == candidate.__name__
    ]
    if len(matches) != 1:
        raise TypeError("public-mirror union arm changed")
    return matches[0]


def _restore_ordered_mapping(value: tuple[object, ...], public_item: object) -> object | None:
    if public_item is _mirror.PublicFactEntryV1:
        return {
            entry.key: _unscalar(_mirror.PublicScalarValueV1(kind=entry.kind, text=entry.text))
            for entry in cast(tuple[_mirror.PublicFactEntryV1, ...], value)
        }
    if public_item is _mirror.PublicTextEntryV1:
        return {entry.key: entry.value for entry in cast(tuple[_mirror.PublicTextEntryV1, ...], value)}
    return None


def _restore_sequence(
    value: tuple[object, ...],
    canonical: object,
    public: object,
    withheld: frozenset[tuple[type[object], str]],
    complete: _MirrorCompletion | None,
) -> object:
    public_item = get_args(public)[0] if get_origin(public) is tuple else None
    if (mapping := _restore_ordered_mapping(value, public_item)) is not None:
        return mapping
    if get_origin(canonical) not in (tuple, Mapping):
        raise TypeError("public-mirror tuple changed its canonical shape")
    canonical_args = get_args(canonical)
    public_args = get_args(public)
    if len(canonical_args) == 2 and canonical_args[1] is Ellipsis:
        return tuple(
            restore_public_value(item, canonical_args[0], public_args[0], withheld, complete) for item in value
        )
    return tuple(
        restore_public_value(item, canonical_args[index], public_args[index], withheld, complete)
        for index, item in enumerate(value)
    )


def _canonical_field_annotations(
    canonical_type: type[object],
) -> tuple[Mapping[str, object], Mapping[str, object]]:
    if issubclass(canonical_type, BaseModel):
        model_fields = cast(Mapping[str, FieldInfo], canonical_type.model_fields)
        target_fields: dict[str, object] = {name: None for name in model_fields}
        target_annotations = {name: field.annotation for name, field in model_fields.items()}
        return target_fields, target_annotations
    if is_dataclass(canonical_type):
        target_fields = {field.name: field for field in dataclass_type_fields(canonical_type)}
        return target_fields, get_type_hints(canonical_type)
    raise TypeError("public-mirror canonical model changed")


def _restore_model_fields(
    value: BaseModel,
    target_fields: Mapping[str, object],
    target_annotations: Mapping[str, object],
    withheld: frozenset[tuple[type[object], str]],
    complete: _MirrorCompletion | None,
    canonical_type: type[object],
) -> dict[str, object]:
    source_fields = type(value).model_fields
    if set(source_fields) - set(target_fields):
        raise ValueError("public-mirror canonical model field inventory drifted")
    restored = {
        name: restore_public_value(
            getattr(value, name),
            target_annotations[name],
            source_fields[name].annotation,
            withheld,
            complete,
        )
        for name in target_fields
        if name in source_fields and (canonical_type, name) not in withheld
    }
    return restored


def _restore_model(
    value: BaseModel,
    canonical: object,
    withheld: frozenset[tuple[type[object], str]],
    complete: _MirrorCompletion | None,
) -> object:
    model_type = type(value)
    model_type.model_rebuild()
    if isinstance(canonical, type) and canonical is model_type:
        return model_type.model_validate_json(value.model_dump_json(), strict=True)
    canonical_type = _canonical_model_type(value, canonical)
    target_fields, target_annotations = _canonical_field_annotations(canonical_type)
    restored = _restore_model_fields(
        value,
        target_fields,
        target_annotations,
        withheld,
        complete,
        canonical_type,
    )
    if complete is not None:
        complete(canonical_type, restored, value)
    if issubclass(canonical_type, BaseModel):
        return canonical_type.model_validate(restored)
    return cast(Callable[..., object], canonical_type)(**restored)


def restore_public_value(
    value: object,
    canonical: object,
    public: object,
    withheld: frozenset[tuple[type[object], str]],
    complete: _MirrorCompletion | None,
) -> object:
    if value is None:
        return None
    canonical, public = _mirror.bare_annotation(canonical), _mirror.bare_annotation(public)
    if isinstance(value, _mirror.PublicScalarValueV1):
        return _unscalar(value)
    if isinstance(value, tuple):
        return _restore_sequence(cast(tuple[object, ...], value), canonical, public, withheld, complete)
    if isinstance(value, BaseModel):
        return _restore_model(value, canonical, withheld, complete)
    if canonical is Decimal and isinstance(value, str):
        try:
            decimal = Decimal(value)
        except InvalidOperation:
            raise ValueError("invalid public-mirror decimal") from None
        if not decimal.is_finite() or str(decimal) != value:
            raise ValueError("invalid public-mirror decimal")
        return decimal
    return value

"""Canonical strict immutable Pydantic model-graph validation for operations."""

from __future__ import annotations

from collections.abc import Mapping, MutableMapping, MutableSequence, MutableSet, Sequence, Set
from typing import TypeAliasType, cast, get_args, get_origin, is_typeddict

from pydantic import BaseModel

_NONSTRUCTURAL_JSON_SCHEMA_EXTRA_KEYS = frozenset({"deprecated", "description", "examples", "title"})


def require_strict_frozen_operation_model_graph(
    model_type: type[BaseModel],
    *,
    path: str,
    reject_mutable_annotations: bool = True,
    require_validated_defaults: bool = True,
) -> None:
    """Refuse any lax Pydantic model reachable from ``model_type`` fields."""
    _require_model_graph(
        model_type,
        path=path,
        visiting=set(),
        reject_mutable_annotations=reject_mutable_annotations,
        require_validated_defaults=require_validated_defaults,
    )


def _require_model_graph(
    model_type: type[BaseModel],
    *,
    path: str,
    visiting: set[type[BaseModel]],
    reject_mutable_annotations: bool,
    require_validated_defaults: bool,
) -> None:
    if model_type in visiting:
        return
    _require_model_config(
        model_type,
        path=path,
        require_validated_defaults=require_validated_defaults,
    )
    visiting.add(model_type)
    try:
        for field_name, field in model_type.model_fields.items():
            _require_annotation_contract(
                field.annotation,
                path=f"{path}.{field_name}",
                visiting=visiting,
                reject_mutable_annotations=reject_mutable_annotations,
                require_validated_defaults=require_validated_defaults,
            )
    finally:
        visiting.remove(model_type)


def _require_model_config(
    model_type: type[BaseModel],
    *,
    path: str,
    require_validated_defaults: bool,
) -> None:
    config = model_type.model_config
    if config.get("strict") is not True:
        raise ValueError(f"operation {path} model must set strict=True")
    if config.get("frozen") is not True:
        raise ValueError(f"operation {path} model must set frozen=True")
    if config.get("extra") != "forbid":
        raise ValueError(f"operation {path} model must set extra='forbid'")
    if model_type.__private_attributes__:
        raise ValueError(f"operation {path} model must not declare private mutable state")
    if model_type.model_computed_fields:
        raise ValueError(f"operation {path} model must not declare computed fields outside its validation schema")
    _require_no_custom_json_schema_hook(model_type, path=path)
    _require_nonstructural_json_schema_extra(config.get("json_schema_extra"), path=path)
    for field_name, field in model_type.model_fields.items():
        _require_nonstructural_json_schema_extra(
            field.json_schema_extra,
            path=f"{path}.{field_name}",
        )
    decorators = model_type.__pydantic_decorators__
    if decorators.field_serializers or decorators.model_serializers:
        raise ValueError(f"operation {path} model must not declare serializers that drift from validation schema")
    if require_validated_defaults and any(
        not field.is_required() for field in model_type.model_fields.values()
    ) and config.get(
        "validate_default",
    ) is not True:
        raise ValueError(f"operation {path} model with defaults must set validate_default=True")


def _require_no_custom_json_schema_hook(model_type: type[BaseModel], *, path: str) -> None:
    for owner in model_type.__mro__:
        if "__get_pydantic_json_schema__" not in owner.__dict__:
            continue
        if owner is not BaseModel:
            raise ValueError(f"operation {path} model must not customize its JSON schema")
        return


def _require_nonstructural_json_schema_extra(extra: object, *, path: str) -> None:
    if extra is None:
        return
    if not isinstance(extra, dict):
        raise ValueError(f"operation {path} must not use callable JSON schema customization")
    typed_extra = cast(dict[object, object], extra)
    unsupported = {
        key
        for key in typed_extra
        if not isinstance(key, str) or key not in _NONSTRUCTURAL_JSON_SCHEMA_EXTRA_KEYS
    }
    if unsupported:
        raise ValueError(f"operation {path} JSON schema extras must be nonstructural annotations only")


def _require_annotation_contract(
    annotation: object,
    *,
    path: str,
    visiting: set[type[BaseModel]],
    reject_mutable_annotations: bool,
    require_validated_defaults: bool,
) -> None:
    if isinstance(annotation, type):
        if issubclass(annotation, BaseModel):
            _require_model_graph(
                annotation,
                path=path,
                visiting=visiting,
                reject_mutable_annotations=reject_mutable_annotations,
                require_validated_defaults=require_validated_defaults,
            )
            return
        if is_typeddict(cast(type[object], annotation)):
            if reject_mutable_annotations:
                raise ValueError(f"operation {path} must not declare a mutable TypedDict")
            return
    if isinstance(annotation, TypeAliasType):
        _require_annotation_contract(
            annotation.__value__,
            path=path,
            visiting=visiting,
            reject_mutable_annotations=reject_mutable_annotations,
            require_validated_defaults=require_validated_defaults,
        )
        return
    origin = get_origin(annotation)
    mutable_origins = (list, set, dict, Mapping, MutableMapping, Sequence, MutableSequence, Set, MutableSet)
    if reject_mutable_annotations and (annotation in mutable_origins or origin in mutable_origins):
        raise ValueError(f"operation {path} must use tuple or frozenset instead of a mutable container")
    if origin is None:
        return
    for argument in get_args(annotation):
        _require_annotation_contract(
            argument,
            path=path,
            visiting=visiting,
            reject_mutable_annotations=reject_mutable_annotations,
            require_validated_defaults=require_validated_defaults,
        )


__all__ = ["require_strict_frozen_operation_model_graph"]

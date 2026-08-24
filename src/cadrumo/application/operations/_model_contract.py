"""Canonical strict immutable Pydantic model-graph validation for operations."""

from __future__ import annotations

from typing import TypeAliasType, get_args, get_origin

from pydantic import BaseModel


def require_strict_frozen_operation_model_graph(
    model_type: type[BaseModel],
    *,
    path: str,
) -> None:
    """Refuse any lax Pydantic model reachable from ``model_type`` fields."""
    _require_model_graph(model_type, path=path, visiting=set())


def _require_model_graph(
    model_type: type[BaseModel],
    *,
    path: str,
    visiting: set[type[BaseModel]],
) -> None:
    if model_type in visiting:
        return
    _require_model_config(model_type, path=path)
    visiting.add(model_type)
    try:
        for field_name, field in model_type.model_fields.items():
            for nested_type in _iter_model_types(field.annotation):
                _require_model_graph(
                    nested_type,
                    path=f"{path}.{field_name}",
                    visiting=visiting,
                )
    finally:
        visiting.remove(model_type)


def _require_model_config(model_type: type[BaseModel], *, path: str) -> None:
    config = model_type.model_config
    if config.get("strict") is not True:
        raise ValueError(f"operation {path} model must set strict=True")
    if config.get("frozen") is not True:
        raise ValueError(f"operation {path} model must set frozen=True")
    if config.get("extra") != "forbid":
        raise ValueError(f"operation {path} model must set extra='forbid'")
    if model_type.__private_attributes__:
        raise ValueError(f"operation {path} model must not declare private mutable state")


def _iter_model_types(annotation: object) -> tuple[type[BaseModel], ...]:
    if isinstance(annotation, type) and issubclass(annotation, BaseModel):
        return (annotation,)
    if isinstance(annotation, TypeAliasType):
        return _iter_model_types(annotation.__value__)
    if get_origin(annotation) is None:
        return ()
    return tuple(
        model_type
        for argument in get_args(annotation)
        for model_type in _iter_model_types(argument)
    )


__all__ = ["require_strict_frozen_operation_model_graph"]

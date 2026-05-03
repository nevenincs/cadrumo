"""Derived schema export for editor tooling."""

from __future__ import annotations

from typing import Any

from ._schema import ModeloDefinition, RegistryCatalogues


def modelo_json_schema() -> dict[str, Any]:
    """Return derived JSON Schema for modelo TOML payloads."""

    return ModeloDefinition.model_json_schema()


def catalogue_json_schema() -> dict[str, Any]:
    """Return derived JSON Schema for shared catalogue payloads."""

    return RegistryCatalogues.model_json_schema()

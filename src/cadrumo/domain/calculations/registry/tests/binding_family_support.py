"""Synthetic binding construction for the per-family build-time validator tests."""

from __future__ import annotations

from collections.abc import Mapping

from ..schema import BindingDefinition


def family_binding(
    provider: Mapping[str, object],
    *,
    data_type: str = "money",
    channel: str = "decimal",
    aggregation: Mapping[str, object] | None = None,
    applicability: Mapping[str, object] | None = None,
    binding_id: str = "test.family.binding",
) -> BindingDefinition:
    """Hydrate one binding through the real schema from plain declaration data."""
    declaration: dict[str, object] = {
        "id": binding_id,
        "provider": dict(provider),
        "value": {"data_type": data_type, "channel": channel},
        "legal_refs": ("ley-37-1992:art-1",),
        "source_refs": ("aeat-modelo-303-diseno-registro",),
    }
    if aggregation is not None:
        declaration["aggregation"] = dict(aggregation)
    if applicability is not None:
        declaration["applicability"] = dict(applicability)
    return BindingDefinition.model_validate(declaration)

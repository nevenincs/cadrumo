"""Deterministic dot-notation routing for domain- and Modelo-sharded locale catalogues.

Translates dotted translation keys to their relative shard paths within a locale
catalogue directory tree.

Shard taxonomy:
- ``modelo.schema.<id>.*`` -> ``modelo/schema/<id>.yml``
- other ``modelo.*`` -> ``modelo/general.yml``
- ``<domain>.*`` where domain in :data:`SHARD_TOP_DOMAINS` -> ``<domain>.yml``
- everything else -> ``common.yml``
"""

from __future__ import annotations

from pathlib import Path

SHARD_TOP_DOMAINS: frozenset[str] = frozenset(
    {"cli", "errors", "wizard", "application", "flows", "docs", "profile", "adapters"},
)
"""Top-level domains that receive dedicated shard files in each locale directory."""

_MODELO_ROOT = "modelo"
_SCHEMA_SEGMENT = "schema"


def route_key_to_shard(dotted_key: str) -> Path:
    """Return the relative shard path for a dotted translation key.

    Args:
        dotted_key: Dotted translation key (e.g. ``cli.root.app_help``,
            ``modelo.schema.303.casilla.continuidad.dr303-01.label``).

    Returns:
        A relative :class:`~pathlib.Path` pointing to the owning YAML shard within
        a language catalogue directory (e.g. ``cli.yml``, ``modelo/schema/303.yml``).
    """
    parts = dotted_key.split(".")
    root = parts[0]
    if root == _MODELO_ROOT:
        if len(parts) > 2 and parts[1] == _SCHEMA_SEGMENT:
            modelo_id = parts[2]
            return Path(_MODELO_ROOT) / _SCHEMA_SEGMENT / f"{modelo_id}.yml"
        return Path(_MODELO_ROOT) / "general.yml"
    if root in SHARD_TOP_DOMAINS:
        return Path(f"{root}.yml")
    return Path("common.yml")


__all__ = [
    "SHARD_TOP_DOMAINS",
    "route_key_to_shard",
]

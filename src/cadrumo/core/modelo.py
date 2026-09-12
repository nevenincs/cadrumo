"""Generic Modelo identifier mechanics backed by the facts registry.

The identifier universe and product-scope dispositions are authored in the
versioned ``modelo-obligation-scope-mapping`` fact. This module only hydrates
that declaration into the string-compatible type and exposes immutable views
for callers that still need the scope partition.
"""

from __future__ import annotations

from collections.abc import Collection, Mapping
from enum import StrEnum
from pathlib import Path
from types import MappingProxyType
import tomllib

from .errors.hierarchy import CoreValidationError

__all__ = ["NON_REGISTRY_MODELOS", "OUT_OF_SCOPE_OBLIGATIONS", "UNMODELED_OBLIGATIONS", "Modelo"]


_FACT_PATH = (
    Path(__file__).resolve().parents[1]
    / "_data"
    / "registry"
    / "aeat"
    / "facts"
    / "0097-2025-modelo-obligation-scope-mapping.toml"
)


def _fact_declarations() -> dict[str, str]:
    """Read the authored Modelo catalogue without duplicating its values in Python."""
    with _FACT_PATH.open("rb") as stream:
        document = tomllib.load(stream)
    variants = document["fact"]["variants"]
    if not variants:
        raise CoreValidationError("Modelo obligation scope fact has no variants")
    entries = variants[0]["payload"]["entries"]
    return {str(entry["key"]): str(entry["value"]) for entry in entries}


_DECLARATIONS = _fact_declarations()


def _csv(value: str) -> tuple[str, ...]:
    values = tuple(token.strip() for token in value.split(",") if token.strip())
    if not values:
        raise CoreValidationError("Modelo catalogue declaration must not be empty")
    return values


def _build_modelo_type() -> type[StrEnum]:
    codes = _csv(_DECLARATIONS["catalogue.codes"])
    if len(codes) != len(set(codes)):
        raise CoreValidationError("Modelo catalogue codes must be unique")
    if any(len(code) != 3 or not code.isdigit() for code in codes):
        raise CoreValidationError("Modelo catalogue codes must be three-digit strings")
    return StrEnum("Modelo", {f"M{code}": code for code in codes}, module=__name__)


Modelo = _build_modelo_type()
"""String-compatible Modelo identifier type hydrated from the canonical fact."""


def _scope_reasons() -> dict[str, str]:
    reasons: dict[str, str] = {}
    groups: dict[str, dict[str, str]] = {}
    for key, value in _DECLARATIONS.items():
        if key.startswith("scope.code.") and key.endswith(".reason"):
            code = key.removeprefix("scope.code.").removesuffix(".reason")
            reasons[code] = value
        elif key.startswith("scope.group."):
            _, _, group, field = key.split(".", 3)
            groups.setdefault(group, {})[field] = value
    for group, fields in groups.items():
        codes = _csv(fields.get("codes", ""))
        reason = fields.get("reason")
        if reason is None or not reason.strip():
            raise CoreValidationError(f"Modelo scope group {group!r} has no reason")
        for code in codes:
            if code in reasons and reasons[code] != reason:
                raise CoreValidationError(f"Modelo scope code {code!r} has conflicting reasons")
            reasons[code] = reason
    unknown = set(reasons).difference(_csv(_DECLARATIONS["catalogue.codes"]))
    if unknown:
        raise CoreValidationError(f"Modelo scope declares unknown codes: {sorted(unknown)!r}")
    return reasons


_SCOPE_REASONS = _scope_reasons()
_SUPPRESSED_CODES = frozenset(_csv(_DECLARATIONS["scope.suppressed.codes"]))
_REGISTRY_OUT_OF_SCOPE_CODES = frozenset(_csv(_DECLARATIONS["scope.registry_out_of_scope.codes"]))


def _validate_scope_partitions(
    scope_reasons: Mapping[str, str],
    suppressed_codes: Collection[str],
    registry_out_of_scope_codes: Collection[str],
) -> None:
    if not set(suppressed_codes).issubset(scope_reasons):
        raise CoreValidationError("suppressed Modelo codes must carry a scope declaration")
    if not set(registry_out_of_scope_codes).issubset(scope_reasons):
        raise CoreValidationError("registry out-of-scope Modelo codes must carry a scope declaration")


_validate_scope_partitions(_SCOPE_REASONS, _SUPPRESSED_CODES, _REGISTRY_OUT_OF_SCOPE_CODES)

OUT_OF_SCOPE_OBLIGATIONS: Mapping[Modelo, str] = MappingProxyType(
    {Modelo(code): reason for code, reason in _SCOPE_REASONS.items() if code not in _SUPPRESSED_CODES},
)
UNMODELED_OBLIGATIONS: Mapping[Modelo, str] = MappingProxyType({})
NON_REGISTRY_MODELOS = frozenset(
    Modelo(code)
    for code in _SCOPE_REASONS
    if code not in _REGISTRY_OUT_OF_SCOPE_CODES
)

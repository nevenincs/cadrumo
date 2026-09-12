"""Registry-backed product-scope partitions for Modelo obligations.

The ``modelo-obligation-scope-mapping`` governed fact owns the distinction
between recognized obligations that have no registry definition and the
subset deliberately outside the product's filing scope.  This module is the
domain service that resolves that declaration through the published authority.
The core ``Modelo`` type remains a syntax/value primitive and does not load
the registry merely to construct an identifier.
"""

from __future__ import annotations

from collections.abc import Iterator, Mapping, Set
from datetime import date

from ....core.errors.hierarchy import CoreValidationError
from ....core.modelo import Modelo
from .authority import bundled_authority
from .facts.resolution import MappingFactQuery, ResolvedMappingFact
from .schema_base import DateAxis

__all__ = [
    "NON_REGISTRY_MODELOS",
    "OUT_OF_SCOPE_OBLIGATIONS",
    "UNMODELED_OBLIGATIONS",
    "resolve_modelo_obligation_scope",
]


def _csv(value: str) -> tuple[str, ...]:
    values = tuple(token.strip() for token in value.split(",") if token.strip())
    if not values:
        raise CoreValidationError("Modelo catalogue declaration must not be empty")
    return values


def resolve_modelo_obligation_scope(
    *,
    effective_date: date | None = None,
) -> tuple[Mapping[Modelo, str], frozenset[Modelo]]:
    """Resolve the current Modelo obligation-scope partitions.

    The authority owns publication identity and cache invalidation.  Resolving
    on each view access therefore keeps the partitions aligned with the
    current published artifact instead of introducing a second process-lifetime
    cache in a value-type module.
    """
    resolved = bundled_authority().resolve_governed_fact(
        MappingFactQuery(
            fact_id="modelo-obligation-scope-mapping",
            date_axis=DateAxis.FILING_PERIOD,
            effective_date=effective_date or date.today(),
        ),
    )
    if not isinstance(resolved, ResolvedMappingFact):
        raise CoreValidationError("Modelo obligation scope did not resolve as a mapping")
    declarations = {str(entry.key): str(entry.value) for entry in resolved.payload.entries}
    catalogue = frozenset(_csv(declarations["catalogue.codes"]))
    suppressed = frozenset(_csv(declarations["scope.suppressed.codes"]))
    registry_out = frozenset(_csv(declarations["scope.registry_out_of_scope.codes"]))
    reasons: dict[str, str] = {}
    groups: dict[str, dict[str, str]] = {}
    for key, value in declarations.items():
        if key.startswith("scope.code.") and key.endswith(".reason"):
            reasons[key.removeprefix("scope.code.").removesuffix(".reason")] = value
        elif key.startswith("scope.group."):
            _, _, group, field = key.split(".", 3)
            groups.setdefault(group, {})[field] = value
    for group, fields in groups.items():
        reason = fields.get("reason", "").strip()
        if not reason:
            raise CoreValidationError(f"Modelo scope group {group!r} has no reason")
        for code in _csv(fields.get("codes", "")):
            if code in reasons and reasons[code] != reason:
                raise CoreValidationError(f"Modelo scope code {code!r} has conflicting reasons")
            reasons[code] = reason
    if not set(reasons).issubset(catalogue) or not suppressed.issubset(reasons) or not registry_out.issubset(reasons):
        raise CoreValidationError("Modelo scope partitions disagree with the published catalogue")
    out_of_scope = {Modelo(code): reason for code, reason in reasons.items() if code not in suppressed}
    non_registry = frozenset(Modelo(code) for code in reasons if code not in registry_out)
    return out_of_scope, non_registry


class _ScopeMapping(Mapping[Modelo, str]):
    def __iter__(self) -> Iterator[Modelo]:
        return iter(resolve_modelo_obligation_scope()[0])

    def __len__(self) -> int:
        return len(resolve_modelo_obligation_scope()[0])

    def __getitem__(self, key: Modelo) -> str:
        return resolve_modelo_obligation_scope()[0][key]


class _NonRegistryModelos(Set[Modelo]):
    def __contains__(self, value: object) -> bool:
        return value in resolve_modelo_obligation_scope()[1]

    def __iter__(self) -> Iterator[Modelo]:
        return iter(resolve_modelo_obligation_scope()[1])

    def __len__(self) -> int:
        return len(resolve_modelo_obligation_scope()[1])


OUT_OF_SCOPE_OBLIGATIONS: Mapping[Modelo, str] = _ScopeMapping()
UNMODELED_OBLIGATIONS: Mapping[Modelo, str] = {}
NON_REGISTRY_MODELOS: Set[Modelo] = _NonRegistryModelos()

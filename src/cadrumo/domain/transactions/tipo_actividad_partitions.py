"""Resolve activity-selector entity sets through the registry authority.

Selector membership, legal applicability, and semantic labels are authored in
the versioned registry.  This module retains only the generic authority query,
and typed payload narrowing used by callers.
"""

from __future__ import annotations

from datetime import date

from ..calculations.registry.facts.resolution import (
    EntitySetFactQuery,
    MappingFactQuery,
    ResolvedEntitySetFact,
    ResolvedMappingFact,
)
from ..calculations.registry.governed_fact_scope import GovernedFactSource, require_governed_fact_authority
from ..calculations.registry.schema_base import DateAxis
from .errors import TransactionValidationError

__all__ = [
    "resolve_tipo_actividad_selector",
    "tipo_actividad_code_set",
]


def _registry_activity_selector_catalogue(
    *,
    effective_date: date,
    authority: GovernedFactSource,
) -> tuple[str, ...]:
    """Resolve the dated M036 selector catalogue before an entity-set lookup."""
    resolved = authority.resolve_governed_fact(
        MappingFactQuery(
            fact_id="m036-activity-selector-catalogue",
            date_axis=DateAxis.FILING_PERIOD,
            effective_date=effective_date,
        ),
    )
    if not isinstance(resolved, ResolvedMappingFact):
        raise TransactionValidationError("activity selector catalogue must resolve as a mapping fact")
    declarations = {str(entry.key): str(entry.value) for entry in resolved.payload.entries}
    selector_ids = tuple(value.strip() for value in declarations.get("selector_ids", "").split(",") if value.strip())
    if not selector_ids:
        raise TransactionValidationError("activity selector catalogue declares no selector facts")
    return selector_ids


def resolve_tipo_actividad_selector(
    fact_id: str,
    *,
    effective_date: date,
    authority: GovernedFactSource | None = None,
) -> ResolvedEntitySetFact:
    """Resolve one registry-owned activity selector through fact authority."""
    normalized_fact_id = fact_id.strip()
    if not normalized_fact_id:
        raise TransactionValidationError("activity selector fact id must not be blank")
    authority = require_governed_fact_authority(authority, subject="activity selector resolution")
    if normalized_fact_id not in _registry_activity_selector_catalogue(
        effective_date=effective_date,
        authority=authority,
    ):
        raise TransactionValidationError(
            f"activity selector {normalized_fact_id!r} is not declared by the registry catalogue",
        )
    try:
        resolved = authority.resolve_governed_fact(
            EntitySetFactQuery(
                fact_id=normalized_fact_id,
                date_axis=DateAxis.FILING_PERIOD,
                effective_date=effective_date,
            ),
        )
    except Exception as exc:
        from ..calculations.registry.errors import RegistryError

        if isinstance(exc, RegistryError):
            raise TransactionValidationError(
                f"failed to resolve activity selector {normalized_fact_id!r}: {exc}",
            ) from exc
        raise
    if not isinstance(resolved, ResolvedEntitySetFact):
        raise TransactionValidationError(
            f"activity selector {normalized_fact_id!r} did not resolve to an entity-set fact",
        )
    return resolved


def _typed_code_set(selector: ResolvedEntitySetFact) -> frozenset[str]:
    """Narrow a resolved entity-set payload to registry-owned activity tokens."""
    return frozenset(str(token) for token in selector.payload.entities)


def tipo_actividad_code_set(
    fact_id: str,
    *,
    effective_date: date,
    authority: GovernedFactSource | None = None,
) -> frozenset[str]:
    """Return the registry-owned code set declared by one selector fact."""
    return _typed_code_set(
        resolve_tipo_actividad_selector(
            fact_id,
            effective_date=effective_date,
            authority=authority,
        ),
    )

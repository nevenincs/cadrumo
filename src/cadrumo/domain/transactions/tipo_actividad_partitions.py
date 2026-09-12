"""Resolve activity-selector entity sets through the registry authority.

Selector membership, legal applicability, and semantic labels are authored in
the versioned registry.  This module retains only the generic authority query,
payload narrowing, and duplicate-code guard used by callers.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from datetime import date
from typing import TYPE_CHECKING

from ...core.tipos_actividad import TipoActividad
from ..calculations.registry.authority import bundled_authority
from ..calculations.registry.facts.resolution import (
    EntitySetFactQuery,
    MappingFactQuery,
    ResolvedEntitySetFact,
    ResolvedMappingFact,
)
from ..calculations.registry.queries import RegistryQueryService
from ..calculations.registry.schema_base import DateAxis
from .errors import TransactionValidationError

if TYPE_CHECKING:
    from ..calculations.registry.authority import ValidatedRegistryAuthority

__all__ = [
    "load_tipo_actividad_selectors",
    "resolve_tipo_actividad_selector",
    "tipo_actividad_code_set",
]


def _registry_activity_selector_catalogue(
    *,
    effective_date: date,
    authority: ValidatedRegistryAuthority,
) -> tuple[str, ...]:
    """Resolve the dated M036 selector catalogue before an entity-set lookup."""
    RegistryQueryService(authority).describe_modelo("036", as_of=effective_date)
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
    authority: ValidatedRegistryAuthority | None = None,
) -> ResolvedEntitySetFact:
    """Resolve one registry-owned activity selector through fact authority."""
    normalized_fact_id = fact_id.strip()
    if not normalized_fact_id:
        raise TransactionValidationError("activity selector fact id must not be blank")
    if authority is None:
        authority = bundled_authority()
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


def _typed_code_set(selector: ResolvedEntitySetFact) -> frozenset[TipoActividad]:
    """Narrow a resolved entity-set payload to the closed activity-code type."""
    codes: set[TipoActividad] = set()
    for token in selector.payload.entities:
        try:
            codes.add(TipoActividad(token))
        except ValueError as exc:
            raise TransactionValidationError(
                f"registry fact {selector.fact_id!r} names {token!r}, which is not a "
                f"recognized activity code; accepted: {', '.join(sorted(t.value for t in TipoActividad))}",
            ) from exc
    return frozenset(codes)


def tipo_actividad_code_set(
    fact_id: str,
    *,
    effective_date: date,
    authority: ValidatedRegistryAuthority | None = None,
) -> frozenset[TipoActividad]:
    """Return the typed code set declared by one registry selector fact."""
    return _typed_code_set(
        resolve_tipo_actividad_selector(
            fact_id,
            effective_date=effective_date,
            authority=authority,
        ),
    )


def load_tipo_actividad_selectors(
    selector_fact_ids: Iterable[str],
    *,
    effective_date: date,
    authority: ValidatedRegistryAuthority | None = None,
) -> Mapping[str, frozenset[TipoActividad]]:
    """Resolve a caller-supplied selector catalogue without embedding its facts."""
    fact_ids = tuple(dict.fromkeys(fact_id.strip() for fact_id in selector_fact_ids))
    if not fact_ids or any(not fact_id for fact_id in fact_ids):
        raise TransactionValidationError("activity selector catalogue must supply non-blank fact ids")

    selectors = {
        fact_id: _typed_code_set(
            resolve_tipo_actividad_selector(
                fact_id,
                effective_date=effective_date,
                authority=authority,
            ),
        )
        for fact_id in fact_ids
    }

    seen: dict[TipoActividad, str] = {}
    for fact_id, codes in selectors.items():
        for code in codes:
            previous = seen.get(code)
            if previous is not None:
                raise TransactionValidationError(
                    f"activity code {code.value!r} is declared by both {previous!r} and "
                    f"{fact_id!r}; a code must select at most one registry selector",
                )
            seen[code] = fact_id
    return selectors

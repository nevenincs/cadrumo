"""Catalogue-level validation for registry-governed facts."""

from __future__ import annotations

from collections.abc import Collection, Mapping
from datetime import date

from .schema import GovernedFact, GovernedFactCatalogue, GovernedFactVariant

__all__ = ["governed_fact_catalogue_failures"]


def governed_fact_catalogue_failures(
    catalogue: GovernedFactCatalogue,
    *,
    legal_ref_ids: Collection[str],
    source_ref_ids: Collection[str],
) -> tuple[str, ...]:
    """Return every unresolved legal or source reference in the catalogue."""
    failures: list[str] = []
    for fact_id, fact in sorted(catalogue.facts.items()):
        failures.extend(_fact_precedence_failures(fact))
        for variant in fact.variants:
            failures.extend(
                f"governed fact {fact_id!r} variant {variant.variant_id!r} references unknown legal id {ref!r}"
                for ref in variant.legal_refs
                if ref not in legal_ref_ids
            )
            failures.extend(
                f"governed fact {fact_id!r} variant {variant.variant_id!r} references unknown source id {ref!r}"
                for ref in variant.source_refs
                if ref not in source_ref_ids
            )
            cited = {citation.source_ref for citation in variant.source_citations}
            if cited != set(variant.source_refs):
                failures.append(
                    f"governed fact {fact_id!r} variant {variant.variant_id!r} citations must cover every source_ref",
                )
    return tuple(failures)


def _fact_precedence_failures(fact: GovernedFact) -> tuple[str, ...]:
    edges = {variant.variant_id: variant.precedence_over for variant in fact.variants}
    failures: list[str] = []
    for variant in fact.variants:
        if _reaches(variant.variant_id, variant.variant_id, edges):
            failures.append(
                f"governed fact {fact.fact_id!r} variant {variant.variant_id!r} precedence graph contains a cycle",
            )
    for index, left in enumerate(fact.variants):
        for right in fact.variants[index + 1 :]:
            overlaps = _overlap(left, right)
            ordered = _reaches(left.variant_id, right.variant_id, edges) or _reaches(
                right.variant_id,
                left.variant_id,
                edges,
            )
            directly_ordered = right.variant_id in edges[left.variant_id] or left.variant_id in edges[right.variant_id]
            if overlaps and not ordered:
                failures.append(
                    f"governed fact {fact.fact_id!r} variants {left.variant_id!r} and {right.variant_id!r} "
                    "overlap without explicit precedence",
                )
            elif directly_ordered and not overlaps:
                failures.append(
                    f"governed fact {fact.fact_id!r} variants {left.variant_id!r} and {right.variant_id!r} "
                    "declare precedence across non-overlapping coordinates",
                )
    return tuple(failures)


def _selector_key(variant: GovernedFactVariant) -> tuple[tuple[str, str, str], ...]:
    return tuple(sorted((item.name, type(item.value).__name__, repr(item.value)) for item in variant.selectors))


def _overlap(left: GovernedFactVariant, right: GovernedFactVariant) -> bool:
    if left.date_axis != right.date_axis or _selector_key(left) != _selector_key(right):
        return False
    return left.valid_from <= (right.valid_to or date.max) and right.valid_from <= (left.valid_to or date.max)


def _reaches(start: str, target: str, edges: Mapping[str, tuple[str, ...]]) -> bool:
    pending = list(edges.get(start, ()))
    seen: set[str] = set()
    while pending:
        current = pending.pop()
        if current == target:
            return True
        if current not in seen:
            seen.add(current)
            pending.extend(edges.get(current, ()))
    return False

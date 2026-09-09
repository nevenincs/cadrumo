"""Catalogue-level validation for registry-governed facts."""

from __future__ import annotations

from collections.abc import Collection

from .schema import GovernedFactCatalogue

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
    return tuple(failures)

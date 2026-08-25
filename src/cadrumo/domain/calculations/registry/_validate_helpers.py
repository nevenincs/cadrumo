"""Shared validation helpers for the registry validate-* modules."""

from __future__ import annotations

from collections.abc import Iterable, Mapping

from .schema import LegalReference, SourceReference


def _missing_refs(
    scope: str,
    owner: str,
    refs: Iterable[str],
    catalogue: Mapping[str, LegalReference] | Mapping[str, SourceReference],
    ref_kind: str,
) -> list[str]:
    failures: list[str] = []
    for ref in refs:
        entry = catalogue.get(ref)
        if entry is None:
            failures.append(f"{scope}: {owner} references unknown {ref_kind} id {ref!r}")
        elif ref_kind == "legal" and entry.evidence_tier != "legal_authority":
            failures.append(f"{scope}: {owner} legal ref {ref!r} is not legal authority")
    return failures


missing_refs = _missing_refs

"""Shared validation helpers for the registry validate-* modules."""

from __future__ import annotations

from collections.abc import Iterable, Mapping

from ._schema import LegalReference, SourceReference


def _missing_refs(
    scope: str,
    owner: str,
    refs: Iterable[str],
    catalogue: Mapping[str, LegalReference] | Mapping[str, SourceReference],
    ref_kind: str,
) -> list[str]:
    return [f"{scope}: {owner} references unknown {ref_kind} id {ref!r}" for ref in refs if ref not in catalogue]

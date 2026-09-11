"""Development-only corpus checks for authored IVA tables.

These checks run while a candidate registry is being compiled.  Product code
uses the published authority evidence projection instead; it must never open the
authoring corpus as a verification fallback.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping, Sequence
from pathlib import Path
from typing import TYPE_CHECKING

from cadrumo.domain.calculations.registry.errors import RegistryValidationError
from cadrumo.domain.iva.compilation_catalogues import compiling_catalogues_in_scope
from cadrumo.domain.iva.errors import IvaCatalogueError

from .legal_grounding import verify_legal_reference_grounding

if TYPE_CHECKING:
    from cadrumo.domain.calculations.registry.schema_references import LegalReference


def legal_ref_failures(
    row: str,
    reference_ids: Iterable[str],
    legal: Mapping[str, LegalReference],
    source_root: Path,
    verified: set[str],
) -> list[str]:
    """Verify authored legal references against the candidate corpus."""
    failures: list[str] = []
    for ref_id in reference_ids:
        if ref_id in verified:
            continue
        reference = legal.get(ref_id)
        if reference is None:
            failures.append(f"{row}: unknown legal_ref {ref_id!r}")
            continue
        try:
            verify_legal_reference_grounding(reference, source_root=source_root)
        except RegistryValidationError as exc:
            failures.append(f"{row}: invalid legal_ref {ref_id!r}: {exc}")
            continue
        verified.add(ref_id)
    return failures


def verify_table_legal_refs(table: str, citations: Sequence[tuple[str, Sequence[str]]]) -> None:
    """Refuse a compilation candidate whose cited legal provisions are invalid."""
    compiling = compiling_catalogues_in_scope()
    if compiling is None:
        raise RuntimeError("authored IVA table verification requires a registry compilation scope")
    legal, _sources, source_root = compiling
    verified: set[str] = set()
    failures = [
        failure
        for row, reference_ids in citations
        for failure in legal_ref_failures(row, reference_ids, legal, source_root, verified)
    ]
    if failures:
        raise IvaCatalogueError(
            f"{table}: legal grounding verification failed:\n" + "\n".join(f" - {failure}" for failure in failures),
        )

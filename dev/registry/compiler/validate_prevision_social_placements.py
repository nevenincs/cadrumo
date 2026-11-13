"""Registry-build validation of a revision's pension-contribution placements.

Each row is checked against the rest of its revision (the placed casilla is one
of the edition's casillas, one row per key, and it is bound to exactly one binding
of the contribution family) and against the bundled corpus: both
quoted texts must be official layout evidence the catalogue declares, and each
quotation must appear in its source.
"""

from __future__ import annotations

from collections.abc import Mapping

from cadrumo.domain.calculations.registry.prevision_social_contribution_bindings import (
    prevision_social_contribution_revision_failures,
)
from cadrumo.domain.calculations.registry.prevision_social_placement import (
    prevision_social_placement_revision_failures,
)
from cadrumo.domain.calculations.registry.schema import ModeloRevision
from cadrumo.domain.calculations.registry.schema_base import SourceCitation
from cadrumo.domain.calculations.registry.schema_references import SourceReference

from .validate_evidence import EvidenceValidator
from .validate_helpers import missing_refs

_GROUNDING_TIER = "layout_authority"
"""Both quoted texts are official designs or dictionaries, never guidance or commentary."""


def _citation_failures(
    *,
    prefix: str,
    owner: str,
    citation: SourceCitation,
    source_refs: Mapping[str, SourceReference],
    evidence: EvidenceValidator,
) -> list[str]:
    refs = (citation.source_ref,)
    unknown = missing_refs(prefix, owner, refs, source_refs, "source")
    if unknown:
        return unknown
    return evidence.validate_source_citations(prefix, owner, refs, (citation,), _GROUNDING_TIER)


def validate_prevision_social_placement_section(
    *,
    prefix: str,
    revision: ModeloRevision,
    source_refs: Mapping[str, SourceReference],
    evidence: EvidenceValidator,
) -> list[str]:
    """Return every placement refusal for one modelo revision."""
    failures = [
        f"{prefix}: {failure}"
        for failure in (
            *prevision_social_placement_revision_failures(revision),
            *prevision_social_contribution_revision_failures(revision),
        )
    ]
    for row in revision.prevision_social_placements:
        owner = f"prevision social placement {row.id}"
        failures.extend(
            _citation_failures(
                prefix=prefix,
                owner=f"{owner} design_citation",
                citation=row.design_citation,
                source_refs=source_refs,
                evidence=evidence,
            )
        )
        if row.casilla_citation is not None:
            failures.extend(
                _citation_failures(
                    prefix=prefix,
                    owner=f"{owner} casilla_citation",
                    citation=row.casilla_citation,
                    source_refs=source_refs,
                    evidence=evidence,
                )
            )
    return failures


__all__ = ["validate_prevision_social_placement_section"]

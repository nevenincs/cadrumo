"""Registry-build refusals for a casilla's complementaria-only declaration.

The schema already refuses the declaration on a casilla that is not an
operator-entered money casilla, and a citation naming a source the declaration
does not list. The rules here need the source catalogue and the bundled corpus,
so they run at build:

* every listed source must resolve to a catalogue entry of
  ``official_source_guidance`` tier. The declaration lets an absent value read as
  zero, so only official guidance may ground it;
* every citation's quoted text must appear in that source. A quotation the
  source does not contain grounds nothing;
* the casilla must not be ``required``. A box every filing must carry cannot
  be one that only a complementaria fills.
"""

from __future__ import annotations

from collections.abc import Mapping

from cadrumo.domain.calculations.registry.schema import ModeloRevision
from cadrumo.domain.calculations.registry.schema_references import SourceReference

from ._validate_helpers import missing_refs
from .validate_evidence import EvidenceValidator

_GROUNDING_TIER = "official_source_guidance"


def validate_complementaria_only_section(
    *,
    prefix: str,
    revision: ModeloRevision,
    source_refs: Mapping[str, SourceReference],
    evidence: EvidenceValidator,
) -> list[str]:
    """Return every complementaria-only refusal for one modelo revision."""
    failures: list[str] = []
    for casilla in revision.casillas:
        declaration = casilla.complementaria_only
        if declaration is None:
            continue
        owner = f"casilla {casilla.id} complementaria_only"
        failures.extend(missing_refs(prefix, owner, declaration.source_refs, source_refs, "source"))
        failures.extend(evidence.require_source_tier(prefix, owner, declaration.source_refs, _GROUNDING_TIER))
        failures.extend(
            evidence.validate_source_citations(
                prefix,
                owner,
                declaration.source_refs,
                declaration.source_citations,
                _GROUNDING_TIER,
            ),
        )
        if casilla.required:
            failures.append(
                f"{prefix}: {owner} is declared on a required casilla; a casilla every filing carries "
                "cannot be one only a complementaria fills",
            )
    return failures


__all__ = ["validate_complementaria_only_section"]

"""Screen: manifest references that no child of the revision cites.

The mirror of the provenance screen beside it. That one asks whether a child's
citation stays inside its revision manifest; this asks whether the manifest
declares anything its children never use. Neither question answers the other,
and screening one direction only reported half a disagreement for as long as
that screen existed.

The two surfaces relate in both directions across the corpus: 59 of 128
revisions declare a manifest that is a subset of what their children cite, and
69 declare references nothing cites. Which containment is correct is not
decided here or by the sibling screen - no rule states it - and both screens
report rather than gate until it is.

One condition is reported, and every row names it:

- ``manifest_reference_uncited`` - the revision manifest declares a legal or
  source reference that none of its authored children carries.

Read from the authored families only, never from resolved export fields. A
derived field's citations are copied from its template, so counting them would
let a manifest reference look cited by a child that never declares it - which
would hide exactly the disagreement being measured.

It lives in its own module rather than beside the sibling screen because the
runner enrols one screen per module, and a condition that exists without being
enrolled is invisible to everyone who runs the suite. That is the failure this
package has now corrected five times.

The screen exits 0 whatever it finds. It reports; it does not gate.
"""

from __future__ import annotations

import collections
import sys
from dataclasses import dataclass
from typing import Final

from cadrumo.domain.calculations.registry.authority import ValidatedRegistryAuthority, bundled_authority
from cadrumo.domain.calculations.registry.schema import ModeloRevision

from .corpus import bundled_modelo_ids
from .provenance_consistency import ProvenanceRefKind, citing_children

#: Named once per module rather than repeated at each read site.
_UTF_8: Final[str] = "utf-8"

__all__ = [
    "KINDS",
    "UncitedManifestReference",
    "screen_authority",
    "uncited_manifest_references",
]

#: Every condition this screen can report, declared once and used at its
#: emission site so the set cannot be recovered by reading the source wrong.
KINDS: tuple[str, ...] = ("manifest_reference_uncited",)


@dataclass(frozen=True, slots=True)
class UncitedManifestReference:
    """One reference a revision manifest declares that none of its children cites."""

    modelo: str
    revision: str
    ref_kind: ProvenanceRefKind
    reference: str
    kind: str = "manifest_reference_uncited"


def uncited_manifest_references(
    revision: ModeloRevision, *, modelo_id: str
) -> tuple[UncitedManifestReference, ...]:
    """Return manifest references no child of the revision cites.

    The mirror of the condition above, and it was unmeasured. A manifest and its
    children's citations are two descriptions of the same revision's grounding,
    and neither contains the other: 59 revisions declare a manifest that is a
    subset of what their children cite, and 69 declare references nothing cites.
    Screening one direction only reported half a disagreement.

    Read from the authored families and not from resolved export fields, because
    a derived field's citations are copied from its template and would make a
    manifest reference look cited by a child that does not declare it.
    """
    cited_legal: set[str] = set()
    cited_source: set[str] = set()
    # The family list is the sibling screen's declaration, not a second copy.
    families = tuple(items for _, items in citing_children(revision))
    for items in families:
        for item in items:
            # A family may carry one reference kind and not the other.
            cited_legal |= {str(ref) for ref in getattr(item, "legal_refs", ())}
            cited_source |= {str(ref) for ref in getattr(item, "source_refs", ())}
    found: list[UncitedManifestReference] = []
    for kind, declared, cited in (
        ("legal", revision.legal_refs, cited_legal),
        ("source", revision.source_refs, cited_source),
    ):
        for reference in sorted({str(ref) for ref in declared} - cited):
            found.append(
                UncitedManifestReference(
                    modelo=modelo_id,
                    revision=str(revision.id),
                    ref_kind=kind,
                    reference=reference,
                )
            )
    return tuple(found)


def screen_authority(
    authority: ValidatedRegistryAuthority, modelo_ids: tuple[str, ...]
) -> tuple[UncitedManifestReference, ...]:
    """Screen every revision for manifest references nothing cites."""
    found: list[UncitedManifestReference] = []
    for modelo_id in modelo_ids:
        for revision in authority.modelo(modelo_id).revisions.values():
            found.extend(uncited_manifest_references(revision, modelo_id=modelo_id))
    return tuple(found)

def main() -> int:
    """Print one greppable row per finding and a closing census; always exit 0."""
    findings = screen_authority(bundled_authority(), bundled_modelo_ids())
    for item in findings:
        sys.stdout.write(
            f"manifest_uncited modelo={item.modelo} revision={item.revision} "
            f"kind={item.kind} ref_kind={item.ref_kind} reference={item.reference}\n"
        )
    tally = collections.Counter(item.ref_kind for item in findings)
    revisions = len({(item.modelo, item.revision) for item in findings})
    sys.stdout.write(
        f"summary findings={len(findings)} revisions={revisions} "
        f"legal={tally['legal']} source={tally['source']}\n"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

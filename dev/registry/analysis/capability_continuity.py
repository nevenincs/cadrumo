"""Screen: a revision declaring less capability than the revision before it.

Every other screen in this package judges a revision on its own. None compares
one with the revision it succeeds, so a modelo that could do something in one
year and cannot in the next reports as two independent rows, or as no row at all
where the later revision is merely incomplete rather than wrong.

Modelo 322 is the case that motivated this. Its `2024-2025` revision declares a
typed filing envelope carrying a product-identity requirement; its
`2026-y-siguientes` revision, also filing grade, spells the envelope as a
pseudo-record and declares no identity requirement. Two rows on the capability
screen, one for the newer revision alone, and nothing anywhere saying the modelo
used to do it correctly. It was found by hand.

Two conditions are reported, and every row names one of them:

- ``capability_lost_at_same_grade`` - the later revision declares no less
  authority than its predecessor and has stopped declaring a capability the
  predecessor had. Nothing about the claim got smaller, so the capability was
  dropped rather than deliberately renounced.
- ``capability_lost_with_grade`` - the capability went and the declared grade
  went down with it. Reported separately and NOT as a regression: modelo 165's
  `2023-2025` is an applicability-grade revision with two casillas sitting
  between two filing revisions, and losing an export layout there is what a
  deliberate stub looks like. Collapsing the two conditions would have made that
  stub read like modelo 322's regression.

Revisions are ordered by ``valid_from``, which is the only site that states when
a revision begins and is mandatory. The comparison is between consecutive pairs,
not against the newest: a capability dropped and restored two revisions later is
still a gap in the years between.

The screen exits 0 whatever it finds. It reports; it does not gate. A modelo may
legitimately lose a capability when the law removes the thing it served, and
nothing here can tell that from an oversight - what it can do is stop the
difference being invisible.
"""

from __future__ import annotations

import collections
import sys
from dataclasses import dataclass

from cadrumo.domain.calculations.registry.authority import ValidatedRegistryAuthority, bundled_authority
from cadrumo.domain.calculations.registry.schema import ModeloRevision

from .corpus import bundled_modelo_ids

__all__ = [
    "GRADE_LADDER",
    "KINDS",
    "CapabilityContinuityFinding",
    "declared_capabilities",
    "modelo_findings",
    "screen_authority",
]

#: Every condition this screen can report, declared once and used at each
#: emission site so the set cannot be recovered by reading the source wrong.
KINDS: tuple[str, ...] = (
    "capability_lost_at_same_grade",
    "capability_lost_with_grade",
)

#: The authority ladder, weakest first, as the shipped enum declares it. Held
#: here as a tuple because comparing grades needs an order and a string enum
#: does not carry one; a second spelling of the members would be the drift this
#: package exists to find, so the names are taken from the enum at import.
GRADE_LADDER: tuple[str, ...] = ("applicability", "calculation", "filing")


@dataclass(frozen=True, slots=True)
class CapabilityContinuityFinding:
    """One capability a revision stopped declaring after its predecessor had it."""

    modelo: str
    revision: str
    predecessor: str
    kind: str
    capability: str
    detail: str


def declared_capabilities(revision: ModeloRevision) -> frozenset[str]:
    """Return the capabilities this revision declares.

    Deliberately few, and each one directional: a capability either is declared
    or is not, and losing it is meaningful in one direction only. Counts are
    excluded for that reason - a revision with fewer casillas than its
    predecessor is not thereby weaker, and a screen reporting it would bury the
    cases where something genuinely stopped being expressible.
    """
    layout = revision.export_layouts[0] if revision.export_layouts else None
    envelope = getattr(layout, "filing_envelope", None) if layout is not None else None
    declared = set()
    if revision.export_layouts:
        declared.add("export_layout")
    if envelope is not None:
        declared.add("typed_filing_envelope")
        if getattr(envelope, "product_identity_requirement", None) is not None:
            declared.add("product_identity_requirement")
    if revision.deadline_windows:
        declared.add("deadline_window")
    if revision.formulas:
        declared.add("formulas")
    return frozenset(declared)


def _grade_rank(revision: ModeloRevision) -> int:
    """Return the revision's rung on the authority ladder, or -1 if unknown."""
    grade = str(getattr(revision, "authority_grade", ""))
    return GRADE_LADDER.index(grade) if grade in GRADE_LADDER else -1


def modelo_findings(
    authority: ValidatedRegistryAuthority, *, modelo_id: str
) -> tuple[CapabilityContinuityFinding, ...]:
    """Return one modelo's capability losses between consecutive revisions."""
    ordered = sorted(authority.modelo(modelo_id).revisions.items(), key=lambda item: item[1].valid_from)
    findings: list[CapabilityContinuityFinding] = []
    for (previous_id, previous), (current_id, current) in zip(ordered, ordered[1:], strict=False):
        lost = declared_capabilities(previous) - declared_capabilities(current)
        if not lost:
            continue
        downgraded = _grade_rank(current) < _grade_rank(previous)
        kind = "capability_lost_with_grade" if downgraded else "capability_lost_at_same_grade"
        for capability in sorted(lost):
            findings.append(
                CapabilityContinuityFinding(
                    modelo=modelo_id,
                    revision=str(current_id),
                    predecessor=str(previous_id),
                    kind=kind,
                    capability=capability,
                    detail=(
                        f"{previous_id} declares {capability} and {current_id} does not; "
                        f"grade {getattr(previous, 'authority_grade', '?')} to "
                        f"{getattr(current, 'authority_grade', '?')}"
                    ),
                )
            )
    return tuple(findings)


def screen_authority(
    authority: ValidatedRegistryAuthority, modelo_ids: tuple[str, ...]
) -> tuple[CapabilityContinuityFinding, ...]:
    """Screen every modelo's consecutive revisions for a lost capability."""
    findings: list[CapabilityContinuityFinding] = []
    for modelo_id in modelo_ids:
        findings.extend(modelo_findings(authority, modelo_id=modelo_id))
    return tuple(findings)


def main() -> int:
    """Print one greppable row per finding and a closing census; always exit 0."""
    authority = bundled_authority()
    findings = screen_authority(authority, bundled_modelo_ids())
    tally: collections.Counter[str] = collections.Counter(item.kind for item in findings)
    for item in findings:
        sys.stdout.write(
            f"capability_continuity modelo={item.modelo} revision={item.revision} "
            f"predecessor={item.predecessor} kind={item.kind} capability={item.capability} "
            f"detail={item.detail!r}\n"
        )
    kinds = " ".join(f"{kind}={tally[kind]}" for kind in KINDS)
    modelos = len({item.modelo for item in findings})
    sys.stdout.write(f"summary findings={len(findings)} modelos={modelos} {kinds}\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

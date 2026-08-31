"""One-shot: close the revision bounds that evidence settles, and route the rest to the worklist.

A revision declares when it applies twice -- a validity window and a period
selector -- and the two can disagree. Two of those disagreements have a
mechanical answer and one does not, which is the whole design of this program.

**Terminable epoch.** A revision left open-ended while a later sibling competes
for the same periods has a determined terminus: the day before the successor
begins. Nothing is chosen here; the successor's own start date fixes it.

**Boundable selector.** A selector bounded by ``year_to`` while validity stays
open has a determined terminus too: the last day of that declared year. Again
the corpus already states it.

**Start mismatch, NOT repaired.** When a selector's first year disagrees with
the declared validity start, either could be the wrong one, and picking the
machine-convenient side would fabricate a boundary. These go to the worklist for
a reading of the governing orden.

Campaign-owned trees are skipped. Modelos 303 and 390 belong to the
export-fragment campaign while it holds them, and a second writer editing those
manifests would collide with work in flight.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date
from pathlib import Path

REGISTRY_MODELOS_ROOT = (
    Path(__file__).resolve().parents[2] / "src" / "cadrumo" / "_data" / "registry" / "aeat" / "modelos"
)

#: Modelo trees another campaign owns. Editing them here would collide with it.
CAMPAIGN_OWNED_MODELOS: frozenset[str] = frozenset({"303", "390"})

_VALID_FROM = re.compile(r"^valid_from\s*=\s*(\d{4})-(\d{2})-(\d{2})\s*$", re.MULTILINE)
_VALID_TO = re.compile(r"^valid_to\s*=", re.MULTILINE)
_YEAR_TO = re.compile(r"year_to\s*=\s*(\d{4})")


@dataclass(frozen=True, slots=True, order=True)
class BoundRepair:
    """One revision whose terminus the corpus already determines."""

    modelo: str
    revision: str
    reason: str
    terminus: str


@dataclass(frozen=True, slots=True, order=True)
class UnsettledBound:
    """One revision whose temporal disagreement evidence must settle."""

    modelo: str
    revision: str
    detail: str


def _load_corpus(root: Path | None):
    from cadrumo.core.resources._boundary import bundled_path
    from cadrumo.domain.calculations.registry.loader import load_registry_tree

    modelos, _catalogues = load_registry_tree(root if root is not None else bundled_path("registry", "aeat"))
    return modelos


def _periods(revision) -> frozenset[str]:
    return frozenset(str(period) for period in (getattr(revision.period_selector, "periods", None) or ()))


def plan_bounds(root: Path | None = None) -> tuple[tuple[BoundRepair, ...], tuple[UnsettledBound, ...]]:
    """Return the repairs the corpus determines and the remainder it does not.

    Returns:
        ``(repairs, unsettled)``. ``repairs`` carry a terminus the corpus itself
        fixes; ``unsettled`` need a reading of the governing orden.
    """
    repairs: list[BoundRepair] = []
    unsettled: list[UnsettledBound] = []
    for modelo in _load_corpus(root):
        if modelo.id in CAMPAIGN_OWNED_MODELOS:
            continue
        revisions = tuple(modelo.revisions.values())
        for revision in revisions:
            has_terminus = getattr(revision, "valid_to", None) is not None
            selector = revision.period_selector
            year_from = getattr(selector, "year_from", None)
            year_to = getattr(selector, "year_to", None)

            if not has_terminus:
                successors = [
                    other
                    for other in revisions
                    if other is not revision
                    and other.valid_from > revision.valid_from
                    and (_periods(other) & _periods(revision))
                ]
                if successors:
                    first = min(successors, key=lambda item: item.valid_from)
                    terminus = first.valid_from.toordinal() - 1
                    repairs.append(
                        BoundRepair(
                            modelo=str(modelo.id),
                            revision=str(revision.id),
                            reason=f"superseded by {first.id}",
                            terminus=str(date.fromordinal(terminus)),
                        ),
                    )
                elif year_to is not None:
                    repairs.append(
                        BoundRepair(
                            modelo=str(modelo.id),
                            revision=str(revision.id),
                            reason=f"selector bounded at {year_to}",
                            terminus=f"{year_to}-12-31",
                        ),
                    )

            if year_from is not None and year_from != revision.valid_from.year:
                unsettled.append(
                    UnsettledBound(
                        modelo=str(modelo.id),
                        revision=str(revision.id),
                        detail=(
                            f"selector starts {year_from} but validity starts "
                            f"{revision.valid_from.isoformat()}; which is correct is evidence"
                        ),
                    ),
                )
    return tuple(sorted(repairs)), tuple(sorted(unsettled))


def apply_bounds(root: Path | None = None, *, apply: bool = False) -> tuple[str, ...]:
    """Write each determined terminus into its manifest.

    Args:
        root: Registry modelos root override, used by the proofs.
        apply: Write the edits. When ``False`` nothing is touched.

    Returns:
        One line per repair made or planned.
    """
    repairs, _unsettled = plan_bounds(root)
    modelos_root = root / "modelos" if root is not None else REGISTRY_MODELOS_ROOT
    lines: list[str] = []
    for repair in repairs:
        manifest = modelos_root / repair.modelo / "revisions" / repair.revision / "revision.toml"
        lines.append(f"{repair.modelo}/{repair.revision}: valid_to = {repair.terminus} ({repair.reason})")
        if not apply or not manifest.exists():
            continue
        text = manifest.read_text(encoding="utf-8")
        if _VALID_TO.search(text):
            continue
        terminus = repair.terminus
        text = _VALID_FROM.sub(
            lambda match, terminus=terminus: f"{match.group(0)}\nvalid_to = {terminus}",
            text,
            count=1,
        )
        manifest.write_text(text, encoding="utf-8")
    return tuple(lines)


def main() -> int:
    """Apply the determined bounds and print the unsettled remainder."""
    import sys

    apply = "--apply" in sys.argv
    made = apply_bounds(apply=apply)
    for line in made:
        print(("bounded " if apply else "would bound ") + line)
    print(f"{len(made)} revision terminus(es) {'written' if apply else 'pending'}")

    _repairs, unsettled = plan_bounds()
    for item in unsettled:
        print(f"WORKLIST {item.modelo}/{item.revision}: {item.detail}")
    print(f"{len(unsettled)} revision(s) need evidence, not a mechanical bound")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())


__all__ = [
    "CAMPAIGN_OWNED_MODELOS",
    "BoundRepair",
    "UnsettledBound",
    "apply_bounds",
    "plan_bounds",
]

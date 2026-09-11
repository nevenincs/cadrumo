"""How much of the legal catalogue actually has its corpus anchor checked.

``resolve_anchored_extracted_unit`` returns the sole unit of a single-unit
sidecar for ANY requested anchor. For every entry whose corpus file holds one
unit, the anchor in ``corpus_ref`` is therefore decorative: a wrong one
verifies exactly as well as the right one.

Today that is mostly cosmetic, because the ``corpus_ref`` still names the right
file and the file still holds the one provision. The hazard is a corpus
refresh. The moment such a file gains units -- which bundling a sibling
provision does -- the anchor stops being decorative and becomes load-bearing,
and an entry whose anchor was never right starts resolving to the wrong text or
failing. Nothing signals that transition. This module is that signal.

The classification is BEHAVIOURAL, not a reimplementation of the resolver: each
entry is resolved twice, once with its declared anchor and once with an anchor
that cannot exist. If the impossible anchor resolves too, the declared one is
not load-bearing. That measures the property directly and cannot drift from the
resolver, because it *is* the resolver.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Final

import pytest

from .....core.corpus_text import CorpusAnchorResolutionError, resolve_anchored_extracted_unit
from .....core.resources.bundled_data import bundled_path
from .....tests.registry_tree import bundled_registry_tree

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]

_IMPOSSIBLE_ANCHOR: Final[str] = "zzz-no-such-anchor-zzz"

_UNVERIFIED_ANCHOR_CEILING: Final[int] = 87
"""Entries whose anchor a wrong value would pass, re-measured 2026-08-06.

Shrink-only. The 318 this replaces was inflated by the resolver falling back to
a sidecar's sole unit for ANY requested anchor, including files that declared an
id it could have checked against. Narrowing that fallback to files declaring no
id at all -- the prediction this docstring already carried -- lands on 90: the
entries whose corpus file genuinely has no internal anchors, where whole-file
matching is correct rather than a gap.

The 228 entries that left this population were never anchor-less; they were
unfalsifiable. Of them, 42 declared an anchor that did not match their sidecar's
unit id, and every one was the ``art-N`` versus ``aN`` notation split, naming the
right article in the wrong spelling -- folded together in the resolver's anchor
canonicalisation rather than by editing 42 call sites. Zero pointed at a
different provision; that was the number that decided this was a contained fix
and not a campaign.

Raising this number means new entries were added whose anchor nothing checks,
which is the regression the ceiling exists to catch.

Lowered 90 -> 89 on 2026-08-07. The two Orden EHA/1274/2007 entries were not
merely unverified, they were grounded on hand-written paraphrase stubs whose
single unit carried no anchor at all, so every anchor resolved against them.
Replacing both with the BOE consolidated text carrying its real ``[Bloque N:
#ar]`` marker made them verified and exposed a second defect the ceiling was
hiding: their declared anchors were ``#a1``/``#a2``, minted by the extractor's
legacy heading fallback, while boe.es publishes this orden's articles under
``#ar``/``#ar-2``. Both citations deep-linked nowhere. An unverified anchor is
not only unchecked, it can be wrong.

Lowered 89 -> 87 on 2026-08-22, by the same remedy, while enrolling three new
entries that would otherwise have pushed this to 92. A hand-authored excerpt
CANNOT produce an anchored unit: the segmenter splits on ``<h[1-6]
class="articulo">`` and reads the anchor from a preceding ``[Bloque N: #x]``
marker, so an excerpt written with ``<div id="a3"><h2>`` -- the shape several
bundled excerpts use -- extracts as one anchorless unit and every anchor
resolves against it. Re-shaping orden-hac-510-2021 to the real BOE markup made
its two existing entries verified (-2) and its new disposición-transitoria entry
verified on arrival; orden-hac-529-2026 was authored in that shape from the
start. The rule for anyone enrolling a new legal reference: author the excerpt
in BOE's marker-and-classed-heading shape, or the citation joins this population
by construction and the ceiling forbids the enrollment.
"""

_MINIMUM_CLASSIFIED_ENTRIES: Final[int] = 550
"""Anti-vacuity floor.

A probe that stopped reaching the catalogue -- a moved corpus root, a renamed
sidecar suffix -- would classify nothing and satisfy every "no unverified
anchors" assertion perfectly. The floor makes silence fail.
"""

_STRICT_RESOLUTION_BLOCKER_COUNT: Final[int] = 6
"""How many entries strict anchor resolution still cannot place, measured 2026-08-05.

Pins the SIZE of the recorded set, not its contents. The membership assertion
below only catches a blocker leaving the data; without this, deleting a name
from the record would quietly retire the finding it documents.
"""

_ANCHOR_ABSENT_FROM_DECLARED_IDS_CEILING: Final[int] = 79
"""Entries naming an anchor absent from their file's declared unit ids, 2026-08-05.

Shrink-only, and a deliberate OVER-count: the comparison here is literal, while
the resolver canonicalises (folding punctuation and Spanish ordinals, so
``a9-bis`` meets ``#a9bis``). Under canonicalisation the population is 42, and
the resolver's structural title match then places all but the six in
:data:`_STRICT_RESOLUTION_BLOCKERS`.

The literal form is used on purpose. Canonicalising here would mean copying the
resolver's folding rules into the audit of those very rules, and an earlier
draft that did exactly that got the ordinal folding wrong and mis-reported the
population. A superset that cannot drift is worth more than an exact figure
that can.
"""

_KNOWN_ABSENT_AT_MEASUREMENT: Final[frozenset[str]] = frozenset[str]()
"""Reserved for naming individual entries once the population is small enough."""

_STRICT_RESOLUTION_BLOCKERS: Final[frozenset[str]] = frozenset(
    {
        "ley-35-2006:art-68.1",
        "ley-35-2006:art-68.2",
        "ley-35-2006:art-68.3",
        "ley-35-2006:art-68.4",
        "ley-35-2006:art-68.5",
        "ley-58-2003:art-27.2",
    },
)
"""Entries citing an apartado against a unit extracted at article granularity.

Each names an anchor like ``articulo-68-1`` while its sidecar's single unit
declares ``#a68`` -- the whole article. The citation is finer-grained than the
extraction, so these are the only entries strict resolution cannot place.

Measured 2026-08-05 over the whole catalogue. 594 entries carry a corpus_ref;
276 resolve multi-unit files where the anchor is already load-bearing. Of the
318 single-unit entries, 90 declare no anchor (the legitimate fallback), 186
declare one that matches, and 42 declare one that does not. Restricting the
fallback and letting the existing structural title matcher run places 36 of
those 42 -- they are ``art-6`` versus BOE's native ``#a6`` for the same
article, a naming-convention difference the title branch already handles. The
six below are what genuinely remains.

Recorded rather than corrected: whether the required_text of art. 68.1 is
properly evidenced by the whole art. 68 unit is a legal-grounding judgement
about what the corpus must contain, not a matcher bug. Five nominally distinct
citations to five different apartados may all be resolving identical
whole-article text. Correcting it means re-extracting the corpus at apartado
granularity or re-pointing the citations, and both are the operator's call.
"""


def _source_root() -> Path:
    """Return the ``_data`` root that ``corpus_ref`` paths are relative to."""
    return bundled_path("registry", "aeat").parents[1]


def _sidecar_for(source_root: Path, corpus_ref: str) -> Path:
    path_text, _, _anchor = corpus_ref.partition("#")
    return source_root / (path_text + ".extracted.json")


def _resolves(sidecar: Path, anchor: str) -> bool:
    """Whether the real resolver yields a unit for ``anchor``."""
    try:
        resolve_anchored_extracted_unit(sidecar, anchor=anchor, include_title=True)
    except CorpusAnchorResolutionError:
        return False
    return True


def _classify() -> tuple[list[str], list[str], set[str]]:
    """Return ``(verified_ids, unverified_ids, corpus_files_seen)``.

    An entry is *verified* when the impossible anchor is refused, and
    *unverified* when it resolves just as the declared anchor does.
    """
    source_root = _source_root()
    _modelos, catalogues = bundled_registry_tree()
    verified: list[str] = []
    unverified: list[str] = []
    files: set[str] = set()
    for ref_id, reference in catalogues.legal.items():
        corpus_ref = getattr(reference, "corpus_ref", "") or ""
        if not corpus_ref:
            continue
        sidecar = _sidecar_for(source_root, corpus_ref)
        if not sidecar.is_file():
            continue
        anchor = corpus_ref.partition("#")[2]
        if not _resolves(sidecar, anchor):
            continue
        files.add(corpus_ref.partition("#")[0])
        if _resolves(sidecar, _IMPOSSIBLE_ANCHOR):
            unverified.append(ref_id)
        else:
            verified.append(ref_id)
    return verified, unverified, files


def test_unverified_anchor_population_only_shrinks() -> None:
    """The count of entries whose anchor nothing checks must not grow."""
    verified, unverified, files = _classify()

    assert len(verified) + len(unverified) >= _MINIMUM_CLASSIFIED_ENTRIES, (
        f"only {len(verified) + len(unverified)} entries classified; the probe is not reaching the catalogue"
    )
    assert len(files) > 1, "every entry resolved to one corpus file; the probe is not spanning the corpus"
    assert len(unverified) <= _UNVERIFIED_ANCHOR_CEILING, (
        f"{len(unverified)} entries carry an anchor nothing verifies, above the "
        f"{_UNVERIFIED_ANCHOR_CEILING} ceiling. A new entry on a single-unit corpus file "
        f"has an unchecked anchor; it will start mattering the moment that file gains a unit."
    )


def test_the_probe_distinguishes_a_verified_anchor_from_an_unverified_one() -> None:
    """Both outcomes must be reachable, or the classification says nothing.

    If every entry came back unverified the ceiling would be satisfied by a
    resolver that accepted everything; if every entry came back verified the
    ceiling would be satisfied by a probe whose impossible anchor was somehow
    resolvable. Requiring both proves the instrument discriminates.
    """
    verified, unverified, _files = _classify()

    assert verified, "no entry refused the impossible anchor; the probe cannot detect a checked anchor"
    assert unverified, (
        "every entry refused the impossible anchor -- either the fallback is already "
        f"closed (then lower _UNVERIFIED_ANCHOR_CEILING from {_UNVERIFIED_ANCHOR_CEILING} to 0) "
        "or the probe is broken"
    )


def test_entries_whose_anchor_is_absent_from_their_files_ids_only_shrink() -> None:
    """Pin the population blocking strict anchor verification.

    A pure data statement -- is the declared anchor literally among the unit
    ids its sidecar declares? -- with no resolution logic reproduced here. That
    matters: an earlier draft of this test reimplemented the resolver's anchor
    canonicalisation, got the Spanish-ordinal folding wrong, and reported 42
    mismatches where the resolver actually places all but six by matching the
    unit title. Reproducing the matcher to audit the matcher is how an audit
    ends up measuring itself.

    So this counts the raw population and lets the resolver speak for the rest.
    Measured 2026-08-05: 79 entries by literal comparison, 42 once the
    resolver's canonicalisation is applied, of which structural title matching
    places all but the six in :data:`_STRICT_RESOLUTION_BLOCKERS`. Those six
    are the real finding.
    """
    source_root = _source_root()
    _modelos, catalogues = bundled_registry_tree()

    mismatched: set[str] = set()
    for ref_id, reference in catalogues.legal.items():
        corpus_ref = getattr(reference, "corpus_ref", "") or ""
        if not corpus_ref:
            continue
        sidecar = _sidecar_for(source_root, corpus_ref)
        if not sidecar.is_file():
            continue
        raw_units = json.loads(sidecar.read_text(encoding="utf-8")).get("units")
        if not isinstance(raw_units, list):
            continue
        declared = {
            str(unit.get("anchor") or "").lstrip("#")
            for unit in raw_units
            if isinstance(unit, dict) and unit.get("anchor")
        }
        if not declared:
            continue
        if corpus_ref.partition("#")[2].lstrip("#") not in declared:
            mismatched.add(ref_id)

    assert len(mismatched) <= _ANCHOR_ABSENT_FROM_DECLARED_IDS_CEILING, (
        f"{len(mismatched)} entries name an anchor their corpus file does not declare, above the "
        f"{_ANCHOR_ABSENT_FROM_DECLARED_IDS_CEILING} ceiling: {sorted(mismatched - _KNOWN_ABSENT_AT_MEASUREMENT)}"
    )
    assert len(_STRICT_RESOLUTION_BLOCKERS) == _STRICT_RESOLUTION_BLOCKER_COUNT, (
        "the recorded blocker set changed size; it is a measurement, so shrinking it must be "
        "a deliberate edit of _STRICT_RESOLUTION_BLOCKER_COUNT alongside evidence the entry was resolved"
    )
    assert mismatched >= _STRICT_RESOLUTION_BLOCKERS, (
        "a recorded strict-resolution blocker no longer names an undeclared anchor; "
        f"remove it from _STRICT_RESOLUTION_BLOCKERS: {sorted(_STRICT_RESOLUTION_BLOCKERS - mismatched)}"
    )

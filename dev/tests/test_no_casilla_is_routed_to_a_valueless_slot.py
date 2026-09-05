"""No casilla declares an export field that writes no value.

WHAT THIS CATCHES. A casilla points at its wire position through ``export_refs``,
naming an entry in the generator's semantic map. Most such entries are ``casilla``
or ``projection`` -- both carry a value. Two kinds do not: ``filler`` pads a gap
and ``literal`` writes a constant. A casilla pointing at either declares a home
that can never hold its figure, so the value is computed, grounded, and then
dropped on the way to the file.

Nothing else sees it. The reference is not dangling, so referential integrity
passes. The position is covered, so no contiguity or coverage check fires. The
casilla simply never appears among the layout's casilla fields, and a reader of
the fixed-width record cannot tell the difference between "declared zero" and
"never written".

THE INSTANCE THAT PROMPTED THIS. Modelo 322's revision ``2008-2023`` declared
casilla ``171`` -- operaciones intragrupo, base imponible, money -- pointing at
``m322-2023.page-01.f097``, a ``filler``. Box 171 exists in the 2024-2025 and
2026 designs and in NEITHER design that revision is governed by, so it was an
era bleed: a box from a later form left in an earlier revision, routed to padding.
It was the only such casilla in the registry, and removing it is what makes this
module green.

WHY ``projection`` IS ALLOWED. A projection field is a real value derived from a
casilla, and modelo 303 routes ten casillas that way legitimately. Treating any
non-``casilla`` kind as the defect would fire on all of them -- the measurement
was corrected once already for exactly that reason, and the narrower predicate is
the one that discards only false positives.

SCOPE. Only ``export_refs`` that RESOLVE against a bundled semantic map are
judged. A revision whose layout is hand-authored rather than generated has no map
entry to look up, and inventing a verdict for it would be a guess.

This gate reads the dev-authored semantic-map mappings directly, so it lives
here rather than under ``src/cadrumo``: the mappings tree is the generator's
input, and the shipped registry authority is its compiled output.
"""

from __future__ import annotations

import tomllib

import pytest

from cadrumo.domain.calculations.registry.authority import bundled_authority

from .._paths import REPO_ROOT
from ..quality.unread_inputs import report_unread

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain, pytest.mark.timeout(600)]
"""The 600-second budget is contention, not a slow test.

Measured at 217.65s under the repository's default `-n auto`
parallelism - 73% of the 300-second ceiling - for
``test_no_casilla_points_at_a_filler_or_literal_slot``.

The ceiling is wall clock and its expiry does not fail the test: the
thread method kills the worker, and every sibling scheduled on it is
reported as never having run. `--dist=loadfile` puts this whole module on
one worker, so the margin here is shared, not per-case.

The walk itself stays real; resolving the live first-party graph is what
costs the minutes.
"""

_MAPPINGS = REPO_ROOT / "dev" / "registry" / "mappings"
#: Map entry kinds that write no casilla value: padding and constants.
_VALUELESS_KINDS = frozenset({"filler", "literal"})
#: Below these the walk found nothing and every assertion would be vacuous.
_MINIMUM_ENTRIES = 1000
_MINIMUM_RESOLVED = 500


def _entry_kinds() -> dict[str, str]:
    """Return ``export_field_id -> kind`` across every bundled semantic map."""
    kinds: dict[str, str] = {}
    unread: list[str] = []
    for fragment in sorted(_MAPPINGS.rglob("*.toml")):
        try:
            data = tomllib.loads(fragment.read_text(encoding="utf-8"))
        except tomllib.TOMLDecodeError as refusal:
            # Malformedness itself is another gate's subject, but its CONSEQUENCE
            # lands here: a fragment that does not parse contributes no entries,
            # so every export ref into it reads as ``kind is None`` below and is
            # skipped as a hand-authored layout rather than judged. A silent skip
            # therefore converts judged routings into unjudged ones, which is
            # indistinguishable from a clean result.
            # Relative where it can be, absolute otherwise: the announcement must
            # never be more fragile than the walk it reports on.
            named = fragment.as_posix()
            if fragment.is_relative_to(REPO_ROOT):
                named = fragment.relative_to(REPO_ROOT).as_posix()
            unread.append(f"{named} ({refusal})")
            continue
        for entry in data.get("entries", []):
            kinds[entry["export_field_id"]] = entry["kind"]

    report_unread(
        "valueless-slot routing gate",
        "these mapping fragments contributed no entries, so export refs into them read as "
        "hand-authored layouts below and were never judged",
        unread,
    )
    return kinds


def _routed() -> tuple[list[tuple[str, str, str, str, str]], int]:
    """Return valueless routings, and how many refs were resolvable at all."""
    kinds = _entry_kinds()
    assert len(kinds) >= _MINIMUM_ENTRIES, f"only {len(kinds)} map entries indexed; the mappings tree was not read"
    offenders: list[tuple[str, str, str, str, str]] = []
    resolved = 0
    for modelo in bundled_authority().modelos:
        for revision_id, revision in modelo.revisions.items():
            for casilla in revision.casillas:
                for ref in list(getattr(casilla, "export_refs", []) or []):
                    kind = kinds.get(ref)
                    if kind is None:
                        continue  # hand-authored layout: no map entry to judge
                    resolved += 1
                    if kind in _VALUELESS_KINDS:
                        offenders.append((str(modelo.id), revision_id, str(casilla.number), ref, kind))
    return offenders, resolved


def test_no_casilla_points_at_a_filler_or_literal_slot() -> None:
    offenders, resolved = _routed()

    assert resolved >= _MINIMUM_RESOLVED, (
        f"only {resolved} export refs resolved against a map; the walk found nothing "
        "to judge and this assertion would pass without checking anything"
    )
    assert not offenders, (
        "these casillas declare an export field that writes no value, so their figure "
        "is computed and then dropped: "
        + ", ".join(
            f"modelo {m} revision {r} casilla [{n}] -> {ref} ({kind})" for m, r, n, ref, kind in sorted(offenders)
        )
    )


def test_value_bearing_kinds_are_not_swept_up() -> None:
    """The predicate must stay narrow enough to admit legitimate routings.

    ``projection`` entries are real derived values and several modelos route
    casillas through them. If the valueless set ever widened to catch those, this
    fails rather than letting a correct registry look broken.
    """
    kinds = _entry_kinds()
    routed_kinds = set()
    for modelo in bundled_authority().modelos:
        for revision in modelo.revisions.values():
            for casilla in revision.casillas:
                for ref in list(getattr(casilla, "export_refs", []) or []):
                    if ref in kinds:
                        routed_kinds.add(kinds[ref])

    assert routed_kinds, "no casilla resolved to any map entry; nothing was measured"
    assert routed_kinds - _VALUELESS_KINDS, (
        "every routed kind is treated as valueless, so the predicate has swallowed "
        f"the legitimate ones: {sorted(routed_kinds)}"
    )

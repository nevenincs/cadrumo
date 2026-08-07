"""A legal entry's ``required_text`` must reach past the excerpt's heading.

The evidence gate cross-checks a legal entry by asserting its ``required_text``
appears in the bundled corpus excerpt. That only proves the excerpt is the right
DOCUMENT when the quoted phrase comes from the operative provision. When it
quotes the article's own title, the check confirms a heading is present and
nothing more -- and a heading is the first line of the file, so it survives any
truncation of everything beneath it.

That is not hypothetical. ``ley-37-1992:art-94`` was found bundled with its body
truncated mid-article: it carries apartado Uno points 1 through 5 and simply
stops, missing the point that grounds treating exports and intra-community
supplies as originating the right to deduct. Its ``required_text`` is
``"operaciones cuya realización origina el derecho a la deducción"`` -- the
article title. The gate passed. The entry is stamped
``review_status = "reviewed"``, so it read as verified to everyone who looked.

This gate measures the population of entries in that shape and refuses to let it
grow. It deliberately does NOT try to fix them: requoting a ``required_text``
means deciding which phrase is operative, and deciding that on an article nobody
has re-read from BOE would leave the entry looking better-grounded while
checking something equally incidental. That is a corpus-refresh decision with a
legal authority behind it, not a test change.
"""

from __future__ import annotations

import html
import re
import tomllib
from pathlib import Path
from typing import Final

import pytest

from .....core.resources import bundled_path

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]

_HEADING_WINDOW: Final[int] = 220
"""Characters of an excerpt treated as its heading.

Wide enough to span an article title plus its numbering on the bundled HTML
renderings, narrow enough that a phrase from the first operative point falls
outside it. Measured against the corpus rather than chosen: the longest bundled
article heading runs well under this, and every entry this gate counts was
confirmed by reading its excerpt.
"""

_UNCHECKED_BODY_FLOOR: Final[int] = 1200
"""Body size above which a heading-only match leaves a real provision unchecked.

Entries below this are mostly one-line dispositions -- an "Entrada en vigor"
whose heading genuinely IS its content -- where a heading match is the whole
document and no gap exists. Counting those would inflate the population with
entries that are correct, which is the over-claim this floor exists to avoid.
"""

_HEADING_ONLY_CEILING: Final[int] = 31
"""Entries whose required_text is satisfied by the heading alone, measured 2026-08-07.

Lowered 32 -> 31 the same day, when ``ley-37-1992:art-94`` -- the entry this
gate was built from -- was actually corrected: its excerpt was refreshed from
the live BOE consolidated text (it had been cut off mid-apartado Uno in the
pre-RDL-7/2021 redaction, missing apartados Dos and Tres entirely) and its
``required_text`` requoted onto two operative phrases, one from Uno.1.c) and
one from Tres.

Shrink-only. Every one is stamped ``review_status = "reviewed"``, which is what
makes the population worth pinning: the stamp says a human checked it, and the
mechanical check behind that stamp cannot see the body.

The tail decides priority. ``orden-eha-3127-2009:art-1`` matches on a heading
and leaves 176,330 characters unchecked; ``ley-37-1992:art-20`` is the LIVA
exemptions article at 30,207 characters, grounded by a phrase that survives any
truncation of it.

This counts SHAPE, not damage. Only ``ley-37-1992:art-94`` is confirmed
truncated, because its tail was read. The other entries may be complete; the
finding is that a truncation in any of them would pass exactly as art. 94's did.
Establishing more would take a tail-read per entry.
"""


def _legal_entries() -> list[tuple[str, dict[str, object]]]:
    root = bundled_path("registry/aeat/legal")
    entries: list[tuple[str, dict[str, object]]] = []
    for toml_file in sorted(Path(root).glob("*.toml")):
        data = tomllib.loads(toml_file.read_text(encoding="utf-8"))
        for key, entry in (data.get("legal") or {}).items():
            if isinstance(entry, dict):
                entries.append((key, entry))
    return entries


def _excerpt_text(corpus_ref: str) -> str | None:
    path = Path(bundled_path(corpus_ref.split("#")[0].removeprefix("corpus/").removeprefix("/")))
    if not path.exists():
        candidate = Path(bundled_path("")) / corpus_ref.split("#")[0]
        if not candidate.exists():
            return None
        path = candidate
    stripped = re.sub(r"<[^>]*>", " ", path.read_text(encoding="utf-8", errors="replace"))
    return re.sub(r"\s+", " ", html.unescape(stripped)).strip() or None


def _heading_only_entries() -> list[tuple[str, int]]:
    """Return entries whose every required phrase sits inside the heading window."""
    found: list[tuple[str, int]] = []
    for key, entry in _legal_entries():
        required = entry.get("required_text") or []
        corpus_ref = entry.get("corpus_ref")
        if not required or not isinstance(corpus_ref, str):
            continue
        text = _excerpt_text(corpus_ref)
        if text is None:
            continue
        heading = text[:_HEADING_WINDOW].lower()
        if len(text) <= _UNCHECKED_BODY_FLOOR:
            continue
        if all(str(phrase).lower() in heading for phrase in required):
            found.append((key, len(text)))
    return found


def test_the_heading_only_population_only_shrinks() -> None:
    """A new entry grounded on its own title must not be added silently.

    Shrink-only rather than hard-zero because the 32 are a real backlog needing
    a legal decision each, and a hard-zero would either block every unrelated
    change or invite someone to satisfy it by quoting an arbitrary body phrase
    -- which looks like grounding and is not.
    """
    found = _heading_only_entries()

    assert len(found) <= _HEADING_ONLY_CEILING, (
        f"{len(found)} legal entries have a required_text satisfied by the excerpt heading alone, "
        f"above the {_HEADING_ONLY_CEILING} ceiling. Such an entry's evidence check confirms a "
        "heading is present and nothing more, so a truncated body passes it silently. Quote a "
        "phrase from the operative provision instead: "
        f"{sorted(key for key, _ in found)[:5]}"
    )


def test_the_ceiling_is_not_stale_slack() -> None:
    """The ceiling must track the real population, not sit above it unnoticed.

    A shrink-only ratchet decays the moment the count drops and the ceiling does
    not follow: the slack silently re-admits exactly what the gate exists to
    keep out. This fails when the ceiling is loose so the number is re-measured
    with the fix that shrank it, in the same change.
    """
    found = _heading_only_entries()

    assert len(found) == _HEADING_ONLY_CEILING, (
        f"the population is {len(found)} but the ceiling is {_HEADING_ONLY_CEILING}. "
        "If entries were corrected, lower the ceiling in the same commit."
    )


def test_the_measurement_would_notice_a_body_phrase() -> None:
    """Anti-tautology: the sweep must distinguish a heading quote from a body quote.

    Every assertion above counts entries the predicate selects. If the
    predicate matched everything, or nothing, both tests would still pass on a
    stable corpus and prove nothing. This pins that it separates the two cases
    on real bundled text, by driving BOTH sides.

    ``ley-37-1992:art-94`` is the worked example this gate was built from and
    is now the CORRECTED side: its excerpt was refreshed from live BOE and its
    required_text requoted onto the operative provision, so it must no longer
    be selected. ``ley-37-1992:art-20`` is the uncorrected side -- the LIVA
    exemptions article, grounded by a phrase that survives any truncation of
    its 30,000 characters -- so it must still be selected. An entry moving
    across that line without the ceiling moving is exactly the drift the
    ratchet exists to catch.
    """
    entries = dict(_legal_entries())
    selected = {key for key, _ in _heading_only_entries()}

    art_94 = entries.get("ley-37-1992:art-94")
    assert art_94 is not None, "the worked example this gate was built from has gone"
    text = _excerpt_text(str(art_94["corpus_ref"]))
    assert text is not None
    heading = text[:_HEADING_WINDOW].lower()

    # Its phrases now come from the body, so at least one falls outside the heading.
    assert not all(str(phrase).lower() in heading for phrase in art_94["required_text"]), (
        "art. 94 was requoted onto its operative provision; a required_text that fits "
        "entirely in the heading means the correction was reverted"
    )
    assert "ley-37-1992:art-94" not in selected, "the corrected entry must leave the population"

    # And the refreshed excerpt must still carry the apartados the truncation dropped,
    # which is what made the heading-only grounding dangerous rather than merely weak.
    lowered = text.lower()
    assert "en ningún caso procederá la deducción" in lowered, "apartado Tres is missing again"
    assert "20 bis, 21, 22, 23, 24 y 25" in lowered, "the exempt-operations point is missing again"

    # The other side: an entry still grounded on its title must still be selected,
    # or the predicate has stopped selecting anything and the ceiling is vacuous.
    assert "ley-37-1992:art-20" in selected, (
        "the predicate no longer selects a known heading-only entry, so the counts above "
        "would pass on an empty population"
    )

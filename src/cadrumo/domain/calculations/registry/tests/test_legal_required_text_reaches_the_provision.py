"""A legal entry's ``required_text`` must reach past the excerpt's heading.

The evidence gate cross-checks a legal entry by asserting its ``required_text``
appears in the bundled corpus excerpt. That only proves the excerpt is the right
DOCUMENT when the quoted phrase comes from the operative provision. When it
quotes the article's own title, the check confirms a heading is present and
nothing more -- and a heading is the first line of the file, so it survives any
truncation of everything beneath it.

That is not hypothetical. ``ley-37-1992:art-94`` was found bundled with its body
truncated mid-apartado Uno in the pre-RDL-7/2021 redaction, missing apartados
Dos and Tres and the point that grounds treating exports and intra-community
supplies as originating the right to deduct. Its ``required_text`` was
``"operaciones cuya realización origina el derecho a la deducción"`` -- the
article title. The gate passed. The entry was stamped
``review_status = "reviewed"``, so it read as verified to everyone who looked.
It has since been refreshed from live BOE and requoted onto two operative
phrases, and it is the worked example the anti-tautology proof below drives.

This gate measures the population of entries in that shape and refuses to let it
grow. It deliberately does NOT try to fix them: requoting a ``required_text``
means deciding which phrase is operative, and deciding that on an article nobody
has re-read from BOE would leave the entry looking better-grounded while
checking something equally incidental. That is a corpus-refresh decision with a
legal authority behind it, not a test change.
"""

from __future__ import annotations

import tomllib
from collections.abc import Mapping
from pathlib import Path
from typing import Final

import pytest

from .....core.corpus_text import normalise_corpus_text, resolve_anchored_extracted_unit
from .....core.directory_scan import scan_directory
from .....core.resources.bundled_data import bundled_path

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

_HEADING_ONLY_CEILING: Final[int] = 34
"""Entries whose required_text is satisfied by the heading alone, measured 2026-08-10.

Shrink-only. Every one is stamped ``review_status = "reviewed"``, which is what
makes the population worth pinning: the stamp says a human checked it, and the
mechanical check behind that stamp cannot see the body.

**Read the 32 -> 56 change as a correction, not slack.** The first measurement
swept the corpus HTML. Production does not ground on the HTML: it resolves the
``.extracted.json`` sidecar and reads the unit at the anchor, so 24 entries
were heading-only on the artefact that grounds filings while reading as
body-grounded on the artefact nobody consults. The sweep now mirrors
``_legal_corpus_text`` exactly, and every sidecar in the corpus resolves, so
the figure is complete rather than a floor. ``ley-37-1992:art-94`` was
genuinely corrected in the same session and is the one entry that LEFT the
population; the other 24 were always in it and were simply not visible.

Each later decrement is a real correction, worked largest-first:
``ley-37-1992:art-20`` (56 -> 55), the LIVA exenciones interiores article at
30,207 characters, requoted onto apartado Dos and the close of apartado Tres;
``ley-27-2014:art-18`` (55 -> 54), the LIS operaciones vinculadas article at
24,535, requoted onto apartado 6 and apartado 14. Both were confirmed COMPLETE
against live BOE first, so both closed a grounding weakness rather than a
truncation.

54 -> 50 corrects four more, worked largest-first: ``ley-35-2006:art-51``
(previsión social), ``ley-35-2006:art-33`` (ganancias patrimoniales),
``ley-37-1992:art-68`` (lugar de realización) and ``ley-37-1992:art-75``
(devengo). Each was confirmed COMPLETE against live BOE before requoting --
apartado enumerations matched on both sides, in word form for the LIVA pair
and digit form for the LIRPF pair.

50 -> 49 corrects ``ley-35-2006:da-50``, the deducción por obras
disposición at 11,879 characters, requoted onto apartado 6.

49 -> 48 corrects ``rd-1065-2007:art-3``, the censos tributarios article at
9,552 characters, requoted onto apartado 12.

48 -> 47 corrects ``rd-1065-2007:art-42-ter``, the Modelo 720 foreign-asset
obligation at 9,396 characters, whose three required phrases were single words
from its own title.

47 -> 46 corrects ``ley-35-2006:da-58`` (deducción vehículos eléctricos),
requoted onto apartado 6.

46 -> 45 corrects ``ley-35-2006:art-92`` (cesión de derechos de imagen),
requoted onto apartado 8.

45 -> 44 corrects ``ley-35-2006:dt-9``, whose sole phrase was a date fragment
recurring throughout the law.

44 -> 43 corrects ``orden-hac-3625-2003:apartado-1`` (Modelo 309 approval),
requoted onto its art. 80.Cinco.5.a case.

43 -> 42 corrects ``rd-1065-2007:art-42-bis`` (Modelo 720 foreign accounts),
requoted onto apartado 4.

42 -> 41 corrects ``rd-1065-2007:art-54-bis`` (Modelo 720 foreign property),
requoted onto apartado 6.d).

41 -> 40 corrects ``ley-35-2006:art-54`` (patrimonios protegidos), requoted
onto apartado 5.

40 -> 39 corrects ``ley-35-2006:art-93`` (régimen de impatriados), pinned onto
both escala tranche boundaries.

39 -> 38 corrects ``ley-35-2006:art-97`` (autoliquidación), requoted onto
apartado 6.

38 -> 37 corrects ``ley-35-2006:art-96`` (obligación de declarar), requoted
onto apartado 9.

37 -> 36 corrects ``ley-35-2006:da-11`` (mutualidad de deportistas), requoted
onto apartado Dos.

36 -> 35 corrects ``ley-37-1992:art-89`` (rectificación de cuotas
repercutidas), requoted onto apartado Cinco.

35 -> 34 corrects ``orden-hac-819-2024:art-unico``: the prior fabricated
source was replaced with the official BOE-A-2024-16129 article unit, whose
required text now quotes its operative annex substitution rather than a title.

The tail decides priority. The largest remaining is ``ley-37-1992:art-24``
at 4,409 characters, grounded by a phrase that survives any truncation of it.

This counts SHAPE, not damage. Only ``ley-37-1992:art-94`` was confirmed
truncated, because its tail was read against live BOE. ``ley-37-1992:art-20`` and
``ley-27-2014:art-18`` were both confirmed COMPLETE by the same method --
apartado counts matched live against bundled -- so their requotes closed a
grounding weakness, not a truncation. The
remaining entries are unread either way; the finding is that a truncation in
any of them would pass exactly as art. 94's did. Establishing more would take a
tail-read per entry.
"""


def _legal_entries() -> list[tuple[str, dict[str, object]]]:
    root = bundled_path("registry/aeat/legal")
    entries: list[tuple[str, dict[str, object]]] = []
    for toml_file in scan_directory(Path(root), pattern="*.toml"):
        data = tomllib.loads(toml_file.read_text(encoding="utf-8"))
        for key, entry in (data.get("legal") or {}).items():
            if isinstance(entry, dict):
                entries.append((key, entry))
    return entries


def _required_phrases(entry: Mapping[str, object]) -> tuple[str, ...]:
    """Read one entry's required phrases as the strings they are.

    Narrowed here rather than at each call site, so both gates below read the
    field the same way. The list check is not ceremony: a bare string is
    truthy and iterable, so a catalogue that stated one phrase unwrapped
    would have been walked one CHARACTER at a time, and every single-letter
    substring matches a heading -- the entry would have been reported as
    heading-only whatever it actually quoted.
    """
    required = entry.get("required_text")
    if required is None:
        return ()
    assert isinstance(required, list), f"required_text is not a list of phrases: {required!r}"
    return tuple(str(phrase) for phrase in required)


def _grounding_text(corpus_ref: str) -> str | None:
    """Return the text production actually grounds on for this reference.

    Deliberately NOT the corpus HTML. ``_legal_corpus_text`` resolves
    ``<file>.extracted.json`` and takes the unit at the anchor, so the HTML is
    an input to extraction and the sidecar is the artefact every grounding
    check consults. Measuring the HTML answers a question nothing asks, and it
    can disagree with production in both directions -- an HTML file refreshed
    without regenerating its sidecar reads as corrected here while production
    still grounds on the truncated extraction.

    That is not hypothetical either: it is exactly what happened when art. 94's
    HTML was refreshed from live BOE, and it is why this helper mirrors
    ``_legal_corpus_text`` -- same resolver, same ``include_title=True``, same
    normaliser -- rather than approximating it.
    """
    path_text, _, anchor = corpus_ref.partition("#")
    sidecar = Path(bundled_path("")) / (path_text + ".extracted.json")
    if not sidecar.is_file():
        return None
    try:
        return normalise_corpus_text(
            resolve_anchored_extracted_unit(
                sidecar,
                anchor=anchor,
                required_text=(),
                include_title=True,
            ),
        )
    except Exception:
        return None


def _heading_only_entries() -> list[tuple[str, int]]:
    """Return entries whose every required phrase sits inside the heading window.

    Phrases are normalised with the same function production compares them
    with, so casing and diacritics cannot make an entry look body-grounded
    here while matching the heading in the validator.
    """
    found: list[tuple[str, int]] = []
    for key, entry in _legal_entries():
        required = _required_phrases(entry)
        corpus_ref = entry.get("corpus_ref")
        if not required or not isinstance(corpus_ref, str):
            continue
        text = _grounding_text(corpus_ref)
        if text is None or len(text) <= _UNCHECKED_BODY_FLOOR:
            continue
        heading = text[:_HEADING_WINDOW]
        if all(normalise_corpus_text(phrase) in heading for phrase in required):
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
    be selected. ``ley-37-1992:art-24`` is the uncorrected side, at 4,409
    characters, grounded by a phrase that survives any truncation of it -- so it
    must still be selected. An
    entry moving across that line without the ceiling moving is exactly the
    drift the ratchet exists to catch.

    The uncorrected example is deliberately the LARGEST remaining entry, so
    this side of the proof retires only when the backlog's worst case is
    genuinely fixed rather than when some incidental entry is.
    """
    entries = dict(_legal_entries())
    selected = {key for key, _ in _heading_only_entries()}

    art_94 = entries.get("ley-37-1992:art-94")
    assert art_94 is not None, "the worked example this gate was built from has gone"
    text = _grounding_text(str(art_94["corpus_ref"]))
    assert text is not None, "the sidecar production grounds on no longer resolves"
    heading = text[:_HEADING_WINDOW]

    # Its phrases now come from the body, so at least one falls outside the heading.
    assert not all(normalise_corpus_text(phrase) in heading for phrase in _required_phrases(art_94)), (
        "art. 94 was requoted onto its operative provision; a required_text that fits "
        "entirely in the heading means the correction was reverted"
    )
    assert "ley-37-1992:art-94" not in selected, "the corrected entry must leave the population"

    # And the refreshed SIDECAR must still carry the apartados the truncation
    # dropped -- asserted on the sidecar, not the HTML, because refreshing the
    # HTML without regenerating the sidecar is precisely the failure that made
    # the first version of this gate report a correction that had not landed.
    assert normalise_corpus_text("En ningún caso procederá la deducción") in text, (
        "apartado Tres is missing from the extracted sidecar again"
    )
    assert normalise_corpus_text("20 bis, 21, 22, 23, 24 y 25") in text, (
        "the exempt-operations point is missing from the extracted sidecar again"
    )

    # The other side: an entry still grounded on its title must still be selected,
    # or the predicate has stopped selecting anything and the ceiling is vacuous.
    assert "ley-37-1992:art-24" in selected, (
        "the predicate no longer selects a known heading-only entry, so the counts above "
        "would pass on an empty population. If art. 18 was corrected, move this to the "
        "next-largest remaining entry rather than deleting the assertion"
    )

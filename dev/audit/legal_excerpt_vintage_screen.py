"""Screen per-article corpus excerpts against the bundled consolidated text.

A legal-catalogue entry cites either a per-article EXCERPT file or a whole-norm
CONSOLIDATED file. Where a norm ships both, the consolidated file's
same-provision unit is the text in force, so the excerpt can be compared
against it and asked whether it still says what current law says -- and whether
the entry's ``required_text`` gate would notice if it did not.

Nothing bridges the two surfaces on its own. Sidecar anchors concatenate an
article number with its Latin ordinal and carry no separator
(``#a163octiesdecies``), while the catalogue and the excerpt filenames use a
hyphenated form (``art-163-octiesdecies``), dotted sub-article suffixes, year
vintage suffixes, and non-article words such as ``apartado`` and
``disposicion final``. Deriving one from the other is this screen's core rule.

WHY THE OBVIOUS DERIVATION IS WRONG, measured rather than assumed. BOE's
anchors are POSITIONAL, not semantic: in ``ley-31-2022`` the unit anchored
``#a1-3`` is titled "Artículo 11", and in ``ley-37-1992`` the same ``#a1-3``
is "Artículo 163 sexvicies". Canonicalisation strips the hyphen
(:func:`cadrumo.core.corpus_text.resolve_anchored_extracted_unit`, via its
private ``_canonical_anchor`` at ``src/cadrumo/core/corpus_text.py:190``), so
``#a1-3`` and ``#a13`` collide on one key. A numeric anchor derivation
therefore lands on a NEIGHBOURING provision for multi-digit articles and
reports total divergence against text that is perfectly current. Nine entries
failed exactly that way, loudly, and were nearly triaged as a supersession
finding.

So the derivation leads with the excerpt's own full TITLE, which cannot collide
with a positional anchor, and falls back to a structured heading rebuilt from
the catalogue's citation token. Every resolution then goes through the one
canonical primitive, ``resolve_anchored_extracted_unit``; this module derives a
lookup key and never selects a unit itself.

AND EVERY RESOLUTION IS CROSS-CHECKED TWICE, against two independent authoring
surfaces, because one check alone was close to self-confirming. The first
compares the EXCERPT's own heading against the resolved unit's heading. It is
the safeguard against the anchor-precedence hazard above and it caught a
mis-derived candidate of this screen's own making -- but the excerpt's title is
also the FIRST lookup key, and for the resolutions it leads the check proves
only that the resolver returned what that key asked for.

The second check binds the CATALOGUE. The heading of the unit the comparison
was made against must ALSO be a heading the entry's own citation token derives,
through the same :func:`candidate_keys` ladder. The entry id and the excerpt's
title are written independently, so their agreement is evidence rather than
restatement: 274 of 275 agree, and the one disagreement is
``orden-hac-1504-2024:art-9``, whose consolidated unit is titled "Artículo
noveno" against a derived "Articulo 9". That is a spelling variant, not a
mis-resolution, which is why it is REPORTED and never promoted to
``misresolved`` -- a benign variant raised to a resolution defect trains a
reader to ignore the class. On the article-payload path the binding is stronger
still and for a different reason: the token is what SELECTS the payload, so it
is enforced at selection rather than corroborated afterwards.

THE LITERAL FORM OF THAT SECOND CHECK WAS MEASURED AND REJECTED. Resolving the
citation token against the excerpt's OWN sidecar and requiring it to reach the
excerpt's single unit returns true for 275 of 275 -- and for the 53 excerpts
whose sole unit carries no anchor it returns true BY CONSTRUCTION, because the
canonical resolver serves a lone anchorless unit for any key at all. A check
that cannot fail for a fifth of its population is not a check, and would have
added a tautology in the place a safeguard is claimed.

A RESOLUTION FAILURE IS A VERDICT, NEVER A DROP-OUT. An earlier instrument let
entries whose anchor resolved to nothing fall silently out of the comparison,
so its published coverage ratio was measured against a denominator that
excluded a third of its own population. Every verdict class here is exhaustive
over the input population and :func:`summarise` reconciles the totals; a screen
whose counts do not add up says so instead of printing a number.

AND THE POPULATION BOUNDARY IS THE SAME HAZARD ONE STEP EARLIER. An entry whose
cited file has no shorter bundled prefix was once skipped outright, as though
it always meant "this entry cites the whole consolidated norm, which is its own
current text". That is true for most of them and false for the rest: an excerpt
whose norm ships no whole-norm counterpart looks identical at that test, and 97
entries left the population before it was counted. The two are separated on the
cited file's own unit count -- many units is the norm itself, one unit is an
excerpt -- and the excluded set is counted and printed rather than skipped.

MEASURED LIMIT, stated because it bounds every verdict this screen emits. The
opening-operative-sentence check is conclusive for SAME-PROVISION IDENTITY and
is not a full-text comparison, so a later-clause divergence remains possible in
an entry reported as matching on it. The clause-level count is the fuller
signal, and even that compares against the bundled consolidated file rather
than against the law: a matching excerpt and a stale consolidated file agree
with each other. This screen detects disagreement with the bundled current
text. It never establishes that an excerpt is CORRECT.

AND THE CLAUSE COUNT IS TWO COUNTS, because divergence has two directions and
an instrument measuring one of them answers a narrower question than it
appears to. Clauses of the CURRENT text absent from the excerpt say the excerpt
is behind. Clauses the EXCERPT carries that the current provision no longer
contains say it holds text the law has dropped -- a surviving repealed clause,
which is exactly what the governing decision's negative clause exists to
express. Only the first direction was counted at first, so an excerpt holding
all of current law PLUS a repealed clause classified as ``matches`` under a
docstring asserting there was nothing for a gate to catch: blind in the one
direction the remedy addresses. Both directions are counted now, both render,
and ``excerpt_carries_more`` is the class that used to be absorbed.

The excerpt-side count carries its own bound. It is taken against the current
provision's title AND body, because the extractor lifts a heading into the unit
title on the oracle side but leaves it inline on an excerpt it found no heading
delimiter for; counting an article's own caption as text the excerpt "adds"
would be an artefact of this screen rather than of the law. It also drops
curator provenance annotations -- a clause naming the cited document's own BOE
identifier is a note ABOUT the document, the excerpt-side counterpart of the
``nota_pie`` note dropped from the oracle. Both drops are mechanical and
neither is entry-specific. What survives is NOT proven repealed: an abridged
excerpt whose scope is wider than the article, and a curated snippet quoting a
neighbouring provision, both land here honestly as "the excerpt carries text
this provision does not", which is what the count says and all it says.

THE WIDENING THAT WAS REJECTED. One entry (``ley-31-2022:art-39``) resolves to
a unit whose heading disagrees, because the excerpt's own title differs from
the consolidated norm's article of that number and the fallback then meets the
positional-anchor hazard. Scanning the consolidated units directly for a
matching heading would recover it, and was rejected: that forks unit selection
away from the canonical primitive to buy one entry, and the entry is reported
as ``misresolved`` with both headings, which is the honest disposition for what
is plausibly a mislabelled excerpt rather than a resolution defect.

THE SECOND ORACLE, and the trap that makes it dangerous. A norm with no bundled
whole-norm consolidation can still have its individual articles bundled as BOE
open-data ARTICLE payloads (``*-redacciones.html``). Those are NOT
current-text documents: each concatenates EVERY historical redaction of the
article, wrapped in ``<version fecha_vigencia=...>`` elements. Comparing an
excerpt against the whole payload finds a clause that survives only in a
REPEALED redaction and reports the entry MATCHING -- a false clean verdict on
exactly the defect class this screen exists to catch. So the redaction IN FORCE
is selected first, by
:func:`dev.corpus.fetch_boe_normative.assert_serves_the_article_in_force`,
which reads the maximum ``fecha_vigencia`` and REFUSES a tie rather than
picking (art. 91 of LIVA carries two redactions dated 19950120, one reading
3 per cent and one 4 per cent). This module never re-derives that rule.

Their committed sidecars are unusable as an oracle for the same reason -- the
extractor has no heading delimiter for this XML shape, so it folds every
redaction into one unit and leads it with the response envelope's ``200``/``ok``
tokens. The raw payload is read instead, which excludes the envelope by
construction rather than by stripping it afterwards.

BOE's block ID is POSITIONAL and its ``titulo`` is SEMANTIC, so a payload is
matched to an entry on the title. The catalogue's own ``corpus_ref`` anchor is
deliberately NOT used for matching, and is reported rather than trusted: many
of these entries carry an anchor that is not BOE's block id, and a subset name
a genuinely DIFFERENT block -- article 11 of the Spain-Morocco convention lives
at ``ar-10``, article 10 of the Spain-Netherlands convention at ``a1-2``. The
screen prints the current counts; no figure is frozen in this prose.

PRECEDENCE, chosen rather than incidental. Where an entry already has a
whole-norm consolidation, that stays its oracle even if an article payload also
exists. Re-oracling an already-comparable entry would move its verdict for a
reason that has nothing to do with the law, and the split could no longer
separate "newly reachable" from "measured differently".

A SCREEN, not a gate, deliberately. Divergences are known-present right now, so
a gate would land red and tax every peer for a defect they did not create.
Correcting an entry is legal-authority work: it needs the redaction history per
provision, and several entries are deliberately vintaged and must NOT be
"fixed". Promote this to a pytest gate once the worklist is empty.

The corpus is read at RUN TIME with no baked-in file list, so newly acquired
consolidated payloads widen the comparable population automatically.

Run as ``python -m dev.audit.legal_excerpt_vintage_screen``.
"""

from __future__ import annotations

import json
import re
import sys
from collections import Counter
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path
from typing import Final

from cadrumo.core.corpus_text import (
    CorpusAnchorResolutionError,
    normalise_corpus_text,
    resolve_anchored_extracted_unit,
)
from cadrumo.core.directory_scan import (
    scan_directory,
)

from .._paths import REPO_ROOT, UTF_8
from ..corpus.fetch_boe_normative import (
    NormativeAcquisitionError,
    article_block_title,
    article_redaction_markup,
    assert_serves_the_article_in_force,
)
from ..docs.preprocess import render_normative_prose
from .legal_catalogue import load_legal_entries

#: Declared locally rather than imported from ``cadrumo.core``: ``dev/`` is
#: unshipped tooling and must not reach into the shipped package's internals,
#: so every dev module carries its own constant (see the sibling screens in
#: this package).
_UTF_8: Final[str] = UTF_8

_CORPUS_DIR: Final = Path("src/cadrumo/_data/corpus/normatives/html")

#: A clause shorter than this is an enumerator, a cross-reference fragment or a
#: heading remnant; counting those as divergence would drown the real signal.
_MIN_CLAUSE_CHARS: Final = 60

#: A whole-norm consolidated file carries many structural units. A one-unit
#: file bearing a norm's bare stem is a sibling excerpt, not an oracle -- five
#: entries were being compared against one such file before this filter, each
#: caught by the identity cross-check.
_MIN_ORACLE_UNITS: Final = 2

#: Latin ordinals name an article; they are part of its identity and are
#: concatenated into the anchor. Anything else trailing a number is scope (an
#: apartado) or a vintage year, and narrows WITHIN the article.
_LATIN_ORDINALS: Final = frozenset(
    {
        "bis",
        "ter",
        "quater",
        "quinquies",
        "sexies",
        "septies",
        "octies",
        "nonies",
        "decies",
        "undecies",
        "duodecies",
        "terdecies",
        "quaterdecies",
        "quinquiesdecies",
        "sexiesdecies",
        "septiesdecies",
        "octiesdecies",
        "noniesdecies",
        "vicies",
        "unvicies",
        "duovicies",
        "tervicies",
        "quatervicies",
        "quinvicies",
        "sexvicies",
        "septvicies",
        "octovicies",
        "novovicies",
        "tricies",
    }
)

#: A BOE open-data article payload, whose stem carries the document id and the
#: BOE block it was fetched for. The block is read from the FILENAME because it
#: is not derivable from the article number, and it is then re-asserted against
#: the payload's own ``<bloque id=...>`` by the acquirer.
_REDACTION_PAYLOAD: Final = re.compile(r"^(?P<document_id>boe-[a-z]-\d{4}-\d+)-(?P<block>.+)-redacciones$")

#: BOE's per-redaction editorial annotation ("Redactado conforme a la
#: corrección de erratas publicada en BOE núm. 295 ... Ref. BOE-A-2003-22594").
#: Dropped because it is PROVENANCE, not a clause of the article: an excerpt
#: sliced from the whole-document view carries a differently-worded note or
#: none, so counting it as legal text reports a divergence about the annotation
#: rather than about the law. Table paragraphs are deliberately NOT dropped --
#: a rate table is operative text.
_EDITORIAL_NOTE: Final = re.compile(r"<p\b[^>]*\bclass=\"nota_pie[^\"]*\"[^>]*>.*?</p\s*>", re.IGNORECASE | re.DOTALL)

#: The excerpt-side counterpart of the note above: a curator's stamp ABOUT the
#: cited document rather than a clause OF the provision -- a transcription
#: banner, or a "Texto consolidado BOE-A-…, redacción vigente tras …" line.
#: Recognised by the BOE DOCUMENT identifier, which operative legal text does
#: not carry: law cites a norm by name and date ("Real Decreto 1008/2023"),
#: never by the identifier BOE files it under. General by construction, with no
#: entry, norm or stem named. Counting an annotation as legal text would report
#: a divergence about the annotation, which is the same reason the oracle side
#: drops its own.
_PROVENANCE_ANNOTATION: Final = re.compile(r"\bboe-[a-z]-\d{4}-\d+\b", re.IGNORECASE)

#: The tokens that open a structural citation in an excerpt filename. A trailing
#: year is a declared vintage only when one of these precedes it; otherwise the
#: year is part of the norm's own name.
_CITATION_HEADS: Final = frozenset(
    {"art", "arts", "articulo", "articulos", "apartado", "anexo", "da", "dt", "df", "dd"}
)

_VINTAGE_YEAR: Final = re.compile(r"^(?:19|20)\d{2}$")
_HEADING_SPLIT: Final = re.compile(r"[.:]")
_SENTENCE_SPLIT: Final = re.compile(r"(?<=[.;])\s+")
_NON_ALNUM: Final = re.compile(r"[^a-z0-9]")
_ARTICLE_PREFIX: Final = re.compile(r"^(?:articulos?|arts?)(?=\d)")

_UNITS_FEMININE: Final = (
    "",
    "primera",
    "segunda",
    "tercera",
    "cuarta",
    "quinta",
    "sexta",
    "septima",
    "octava",
    "novena",
)
_UNITS_MASCULINE: Final = (
    "",
    "primero",
    "segundo",
    "tercero",
    "cuarto",
    "quinto",
    "sexto",
    "septimo",
    "octavo",
    "noveno",
)
_TENS_FEMININE: Final = (
    "",
    "decima",
    "vigesima",
    "trigesima",
    "cuadragesima",
    "quincuagesima",
    "sexagesima",
    "septuagesima",
    "octogesima",
    "nonagesima",
)
_TENS_MASCULINE: Final = (
    "",
    "decimo",
    "vigesimo",
    "trigesimo",
    "cuadragesimo",
    "quincuagesimo",
    "sexagesimo",
    "septuagesimo",
    "octogesimo",
    "nonagesimo",
)
_IRREGULAR_FEMININE: Final = {11: "undecima", 12: "duodecima"}
_IRREGULAR_MASCULINE: Final = {11: "undecimo", 12: "duodecimo"}

#: Structural families whose units BOE titles with a written ordinal rather
#: than a number, keyed by the token the catalogue uses.
_FAMILIES: Final = {
    "da": ("Disposicion adicional", "da"),
    "dt": ("Disposicion transitoria", "dt"),
    "df": ("Disposicion final", "df"),
    "dd": ("Disposicion derogatoria", "dd"),
}


class Verdict(StrEnum):
    """Exhaustive classification of one excerpt-backed catalogue entry.

    Exhaustive is the load-bearing word. Every entry in the input population
    receives exactly one of these, including the ones no comparison could be
    made for, so the published coverage ratio can never quietly shed a
    subpopulation.
    """

    NO_ORACLE = "no_oracle"
    """Nothing bundled can state this provision's current text: neither a
    whole-norm consolidation nor a BOE article payload. Not comparable, and
    neither clean nor dirty -- simply unmeasured."""

    ORACLE_INDETERMINATE = "oracle_indeterminate"
    """An article payload exists but does not say which redaction is in force.
    Distinct from NO_ORACLE on purpose: a payload that ties on the latest
    ``fecha_vigencia`` looks like an oracle and is not one, and folding it into
    "nothing bundled" would hide the one failure mode that can silently return
    REPEALED text."""

    UNRESOLVED = "unresolved"
    """A consolidated counterpart exists but no candidate key reached a unit."""

    MISRESOLVED = "misresolved"
    """A unit was reached and its heading names a DIFFERENT provision, so any
    divergence figure computed from it would be about the wrong article."""

    MATCHES = "matches"
    """Neither direction diverges: every clause of the current text is present
    in the excerpt, and the excerpt adds no clause the current text lacks.
    Nothing for a gate to catch WITHIN THE TWO COUNTS THIS SCREEN TAKES, so the
    gate is UNTESTED here rather than proven. The earlier form of this verdict
    made the same claim off the absent-clause count alone, which could not see
    a surviving repealed clause at all."""

    EXCERPT_CARRIES_MORE = "excerpt_carries_more"
    """Every clause of the current text is present in the excerpt AND the
    excerpt carries clauses the current provision does not. The excerpt is not
    behind; it is a superset, which is how a surviving repealed clause looks
    from here. Its own class rather than a footnote on ``matches`` because no
    presence-only ``required_text`` gate can express it -- that is the whole
    argument the governing decision rests on, and this is the population it
    rests on."""

    VINTAGED = "vintaged"
    """The excerpt is a declared historical vintage. Divergence from current
    text is CORRECT by design and must never be "fixed"."""

    DIVERGES_GATE_FIRES = "diverges_gate_fires"
    """The excerpt diverges and the entry's ``required_text`` would notice,
    because at least one declared phrase is absent from the current text."""

    DIVERGES_GATE_GREEN = "diverges_gate_green"
    """The excerpt diverges and every declared phrase survives in the current
    text, so the gate passes over a stale document. The defect class."""


class OracleKind(StrEnum):
    """Which bundled document stated the current text an entry was measured on.

    Reported alongside the verdict so a shift in the published split can be
    attributed. Two things moved the ratio at once -- the anchor derivation was
    rebuilt, and a population that had no oracle at all acquired one -- and a
    split that cannot separate them answers neither question.
    """

    NONE = "none"
    """No comparison was made, so no document stated anything."""

    CONSOLIDATED_NORM = "consolidated_norm"
    """The norm's whole-norm consolidated file, reached by anchor derivation."""

    ARTICLE_REDACTION = "article_redaction"
    """A BOE open-data article payload, reduced to the redaction in force."""


@dataclass(frozen=True)
class Finding:
    """One entry's measured relationship to the bundled current text."""

    entry_id: str
    verdict: Verdict
    detail: str
    clauses_total: int = 0
    clauses_absent: int = 0
    clauses_extra: int = 0
    opening_sentence_matches: bool = False
    identity_confirmed: bool = False
    citation_confirmed: bool = False
    resolved_anchor: str = ""
    oracle_kind: OracleKind = OracleKind.NONE
    catalogue_anchor: str = ""
    boe_block: str = ""

    @property
    def anchor_disagrees(self) -> bool:
        """Whether the catalogue's own anchor is not BOE's block id, verbatim.

        Reported, never acted on: repointing an anchor is adjudication.
        """
        return bool(self.catalogue_anchor and self.boe_block and self.catalogue_anchor != self.boe_block)

    @property
    def anchor_names_another_block(self) -> bool:
        """Whether the disagreement is substantive rather than a naming form.

        ``art-10`` against block ``a10`` is the same provision spelled two
        ways and costs nothing. ``art-10`` against block ``a1-2`` is a
        DIFFERENT block, and an instrument keyed on the catalogue anchor would
        have compared the entry against another article and read the difference
        as supersession. Only this subset is a hazard.
        """
        return self.anchor_disagrees and structural_key(self.catalogue_anchor) != structural_key(self.boe_block)

    def render(self) -> str:
        """Return the finding as one operator-readable line."""
        if self.verdict in {
            Verdict.NO_ORACLE,
            Verdict.ORACLE_INDETERMINATE,
            Verdict.UNRESOLVED,
            Verdict.MISRESOLVED,
        }:
            return f"{self.entry_id}: {self.verdict.value} -- {self.detail}"
        opening = "opening sentence verbatim" if self.opening_sentence_matches else "opening sentence differs"
        identity = "identity confirmed" if self.identity_confirmed else "identity UNCONFIRMED"
        citation = "citation bound" if self.citation_confirmed else "citation UNBOUND"
        return (
            f"{self.entry_id}: {self.verdict.value} -- {self.clauses_absent}/{self.clauses_total} "
            f"current clauses absent from the excerpt, {self.clauses_extra} excerpt clauses absent "
            f"from the current text; {opening}; {identity}; {citation}; "
            f"resolved {self.resolved_anchor or '(anchor not recoverable)'}"
        )


def ordinal_spellings(number: int, *, feminine: bool) -> tuple[str, ...]:
    """Return the written Spanish ordinals BOE plausibly uses for ``number``.

    Several spellings are returned rather than one, because BOE is not
    self-consistent: the same corpus carries "vigésima primera" and "vigésimo
    primera" for the twenty-first disposición, and elides the doubled vowel in
    "decimoctava". A candidate ladder absorbs that variation, where committing
    to one spelling would silently drop an entry out of the comparison.

    Args:
        number: The ordinal position, from 1 to 99.
        feminine: Whether the family takes feminine agreement (disposiciones
            do; an orden's numbered apartados take masculine).

    Returns:
        Distinct spellings in preference order, empty when out of range.
    """
    if not 1 <= number <= 99:
        return ()
    units = _UNITS_FEMININE if feminine else _UNITS_MASCULINE
    tens = _TENS_FEMININE if feminine else _TENS_MASCULINE
    other_tens = _TENS_MASCULINE if feminine else _TENS_FEMININE
    irregular = _IRREGULAR_FEMININE if feminine else _IRREGULAR_MASCULINE
    if number < 10:
        return (units[number],)
    ten, unit = divmod(number, 10)
    if unit == 0:
        return (tens[ten],)
    spellings = []
    if number in irregular:
        spellings.append(irregular[number])
    spellings.extend(
        (
            f"{tens[ten]} {units[unit]}",
            tens[ten] + units[unit],
            f"{other_tens[ten]} {units[unit]}",
            other_tens[ten] + units[unit],
        )
    )
    if ten == 1:
        # "decimoctava", not "decimaoctava": BOE elides the doubled vowel.
        spellings.append(tens[1][:-1] + units[unit])
        spellings.append(_TENS_MASCULINE[1] + units[unit])
    return tuple(dict.fromkeys(spellings))


def candidate_keys(citation_token: str) -> tuple[str, ...]:
    """Return lookup keys for the provision a catalogue citation token names.

    The token is the part of an entry id after the colon -- ``art-81``,
    ``art-163-octiesdecies``, ``art-68-1``, ``da-18``, ``df-unica``,
    ``apartado-3``. Keys are returned in preference order and are consumed by
    the canonical anchor resolver, which accepts an anchor OR a structural
    heading; this function never selects a unit itself.

    Args:
        citation_token: The catalogue's own citation token.

    Returns:
        Distinct keys in preference order, empty when the token is not a
        recognised structural citation.
    """
    parts = [part for part in re.split(r"[-_.]", citation_token.strip().lower()) if part]
    if not parts:
        return ()
    head, rest = parts[0], parts[1:]

    if head in {"art", "arts", "articulo", "articulos"}:
        return _article_keys(rest)
    if head == "apartado" and rest and rest[0].isdigit():
        keys = [word.capitalize() for word in ordinal_spellings(int(rest[0]), feminine=False)]
        keys.append(rest[0])
        return tuple(dict.fromkeys(keys))
    if head == "anexo" and rest:
        return (f"Anexo {' '.join(rest)}", "an" + "".join(rest))
    family = _FAMILIES.get(head)
    if family is not None:
        return _family_keys(family, rest)
    return ()


def _article_keys(rest: list[str]) -> tuple[str, ...]:
    if not rest:
        return ()
    if not rest[0].isdigit():
        # "Artículo único" and its kin: no number to concatenate an ordinal to.
        return ("Articulo " + " ".join(rest), "a" + "".join(rest))
    number = rest[0]
    named: list[str] = []
    for part in rest[1:]:
        if part not in _LATIN_ORDINALS:
            break
        named.append(part)
    keys: list[str] = []
    if named:
        keys.append(f"Articulo {number} {' '.join(named)}")
        keys.append("a" + number + "".join(named))
    # A trailing apartado digit or vintage year narrows within the article; the
    # consolidated file carries the whole article, so both are simply dropped.
    # A hyphenated ``a68-1`` key is deliberately NOT emitted: canonicalisation
    # strips the hyphen, so it silently collides with article 681.
    keys.append(f"Articulo {number}")
    keys.append("a" + number)
    return tuple(dict.fromkeys(keys))


def _family_keys(family: tuple[str, str], rest: list[str]) -> tuple[str, ...]:
    heading, prefix = family
    if not rest or rest[0] in {"unica", "unico"}:
        return (f"{heading} unica", prefix)
    if rest[0].isdigit():
        keys = [f"{heading} {word}" for word in ordinal_spellings(int(rest[0]), feminine=True)]
        keys.append(f"{prefix}{rest[0]}")
        return tuple(dict.fromkeys(keys))
    return (f"{heading} {' '.join(rest)}", prefix + "".join(rest))


def structural_key(text: str) -> str:
    """Return a comparison key for a unit heading, ignoring its caption prose."""
    heading = _HEADING_SPLIT.split(text, maxsplit=1)[0]
    folded = _NON_ALNUM.sub("", normalise_corpus_text(heading))
    return _ARTICLE_PREFIX.sub("a", folded, count=1)


def clause_chunks(text: str) -> tuple[str, ...]:
    """Return the normalised clause-level chunks of a provision's text.

    Splitting on line and sentence boundaries mirrors how a BOE article is
    laid out in apartados. Short fragments are dropped so an enumerator or a
    cross-reference cannot inflate a divergence count.
    """
    chunks = []
    for line in text.split("\n"):
        for sentence in _SENTENCE_SPLIT.split(line):
            normalised = normalise_corpus_text(sentence)
            if len(normalised) >= _MIN_CLAUSE_CHARS:
                chunks.append(normalised)
    return tuple(chunks)


def readable_units(sidecar: Path) -> tuple[dict[str, str], ...]:
    """Return a sidecar's units that carry text, as anchor/title/text records."""
    try:
        payload = json.loads(sidecar.read_text(encoding=_UTF_8))
    except (OSError, json.JSONDecodeError) as exc:
        raise SystemExit(
            f"cannot read extracted sidecar, so the result would be meaningless: {sidecar}: {exc}"
        ) from exc
    raw_units = payload.get("units") if isinstance(payload, dict) else None
    units: list[dict[str, str]] = []
    for raw in raw_units if isinstance(raw_units, list) else ():
        if not isinstance(raw, dict):
            continue
        text = raw.get("text")
        if not isinstance(text, str) or not text.strip():
            continue
        anchor = raw.get("anchor")
        title = raw.get("title")
        units.append(
            {
                "anchor": anchor if isinstance(anchor, str) else "",
                "title": title if isinstance(title, str) else "",
                "text": text.strip(),
            }
        )
    return tuple(units)


def norm_root(stem: str, stems: frozenset[str]) -> tuple[str, str] | None:
    """Return the norm stem an excerpt belongs to, and its citation remainder.

    The SHORTEST hyphen-boundary prefix that names a bundled file is the norm
    document; longer prefixes are sibling excerpts of the same norm.

    Args:
        stem: The cited file's stem, without its ``.html`` suffix.
        stems: Every bundled corpus stem.

    Returns:
        The norm stem and the citation remainder, or ``None`` when no shorter
        prefix is bundled. ``None`` covers TWO situations that the caller must
        separate: the stem may itself be a bundled file, in which case the
        entry cites a document that is its own current text, or nothing
        resembling it may be bundled at all, which is a reportable gap and not
        an exclusion. Reading ``None`` as the first alone is the silent-drop
        class -- an entry with no bundled text would leave the population
        looking deliberately out of scope.
    """
    parts = stem.split("-")
    for index in range(1, len(parts)):
        prefix = "-".join(parts[:index])
        if prefix in stems:
            return prefix, "-".join(parts[index:])
    return None


@dataclass(frozen=True)
class ArticlePayload:
    """One bundled BOE open-data article payload, before redaction selection.

    ``block`` is read from the filename because it is not derivable from the
    article number, and the acquirer re-asserts it against the payload's own
    ``<bloque id=...>``. ``title`` is BOE's ``titulo``, which is the only field
    that names the provision.
    """

    path: Path
    document_id: str
    block: str
    title: str


@dataclass(frozen=True)
class ScreenResult:
    """The screened population, plus the one subpopulation deliberately excluded.

    The exclusion is carried rather than dropped. An entry citing its norm's
    whole consolidated file has no excerpt to compare and is out of scope by
    definition -- but "out of scope" and "silently lost" look identical in a
    published ratio unless the count is printed.
    """

    findings: tuple[Finding, ...]
    population: int
    cites_consolidated_norm: int


def summarise(findings: list[Finding], population: int) -> str:
    """Return the reconciled tally, refusing to print a split that does not add up.

    The refusal is the point. An instrument that can lose a subpopulation
    between its input and its output publishes a ratio whose denominator nobody
    can check, which is the specific defect this screen was rebuilt to remove.
    """
    counts = Counter(finding.verdict for finding in findings)
    if len(findings) != population:
        return f"COUNTS DO NOT RECONCILE: {len(findings)} findings over {population} input entries; the split is unsafe"
    lines = [f"excerpt-backed catalogue entries screened: {population}"]
    for verdict in Verdict:
        lines.append(f"  {verdict.value:24} {counts[verdict]:4}")
    comparable = sum(
        counts[verdict]
        for verdict in (
            Verdict.MATCHES,
            Verdict.EXCERPT_CARRIES_MORE,
            Verdict.VINTAGED,
            Verdict.DIVERGES_GATE_FIRES,
            Verdict.DIVERGES_GATE_GREEN,
        )
    )
    diverging = (
        counts[Verdict.DIVERGES_GATE_FIRES]
        + counts[Verdict.DIVERGES_GATE_GREEN]
        + counts[Verdict.VINTAGED]
        + counts[Verdict.EXCERPT_CARRIES_MORE]
    )
    lines.append(f"\ncomparable: {comparable} of {population} screened")
    lines.append(
        f"of {diverging} measured divergences the gate catches {counts[Verdict.DIVERGES_GATE_FIRES]} "
        f"({counts[Verdict.VINTAGED]} of them vintaged by design, "
        f"{counts[Verdict.EXCERPT_CARRIES_MORE]} excerpt-side only)"
    )
    lines.append(
        "excerpt-side only means the excerpt carries text the current provision does not,"
        " which no presence-only gate can express"
    )
    return "\n".join(lines)


def article_payloads(corpus: Path) -> dict[str, tuple[ArticlePayload, ...]]:
    """Return the bundled article payloads, grouped by BOE document id.

    Read at run time with no baked-in list, so a later acquisition widens the
    comparable population without editing this module.
    """
    grouped: dict[str, list[ArticlePayload]] = {}
    for path in scan_directory(corpus, pattern="*-redacciones.html"):
        match = _REDACTION_PAYLOAD.match(path.name.removesuffix(".html"))
        if match is None:
            continue
        document_id = match.group("document_id").upper()
        payload = path.read_text(encoding=_UTF_8)
        grouped.setdefault(document_id, []).append(
            ArticlePayload(
                path=path,
                document_id=document_id,
                block=match.group("block"),
                title=article_block_title(payload),
            ),
        )
    return {document_id: tuple(items) for document_id, items in grouped.items()}


def screen(root: Path) -> ScreenResult:
    """Return one finding per excerpt-backed entry, and the excluded count."""
    entries = load_legal_entries(root)
    corpus = root / _CORPUS_DIR
    stems = frozenset(path.name.removesuffix(".html") for path in scan_directory(corpus, pattern="*.html"))
    if not stems:
        raise SystemExit(f"read zero corpus files, so the result would be meaningless: {corpus}")
    payloads = article_payloads(corpus)

    findings: list[Finding] = []
    cites_consolidated_norm = 0
    for entry_id, body in sorted(entries.items()):
        corpus_ref = body.get("corpus_ref", "")
        if not isinstance(corpus_ref, str):
            continue
        path, _, fragment = corpus_ref.partition("#")
        if not path.endswith(".html"):
            continue
        stem = Path(path).name.removesuffix(".html")
        root_pair = norm_root(stem, stems)
        if root_pair is not None:
            findings.append(_screen_entry(entry_id, body, corpus, stem, root_pair))
            continue
        if stem not in stems:
            # Split by DECLARATION, not by whether a sidecar happens to exist.
            # No shorter prefix AND no file of its own means nothing bundled
            # states this provision at all -- a reportable gap. Left folded
            # into the branch below it would read as an entry deliberately out
            # of scope, which is the silent-drop shape this screen was rebuilt
            # to remove. The population is zero here today, and a routing that
            # is correct by accident stops being correct without warning.
            findings.append(Finding(entry_id, Verdict.NO_ORACLE, f"no bundled corpus file for {stem}"))
            continue
        # The cited file IS bundled. Either the entry cites its norm's whole
        # consolidated file -- its own current text, nothing to compare -- or it
        # cites an excerpt whose norm ships no consolidation at all. The two are
        # indistinguishable by name and were once both skipped; the cited file's
        # own unit count tells them apart.
        cited = corpus / f"{stem}.html.extracted.json"
        if not cited.exists():
            findings.append(Finding(entry_id, Verdict.NO_ORACLE, f"no extracted sidecar for {stem}"))
            continue
        cited_units = readable_units(cited)
        if len(cited_units) >= _MIN_ORACLE_UNITS:
            cites_consolidated_norm += 1
            continue
        findings.append(_screen_via_article_payload(entry_id, body, stem, fragment, cited_units, payloads))
    return ScreenResult(tuple(findings), len(findings), cites_consolidated_norm)


def _screen_entry(
    entry_id: str,
    body: dict[str, object],
    corpus: Path,
    stem: str,
    root_pair: tuple[str, str],
) -> Finding:
    norm, filename_token = root_pair
    oracle = corpus / f"{norm}.html.extracted.json"
    excerpt = corpus / f"{stem}.html.extracted.json"
    if not oracle.exists():
        return Finding(entry_id, Verdict.NO_ORACLE, f"no extracted sidecar for {norm}")
    oracle_units = readable_units(oracle)
    if len(oracle_units) < _MIN_ORACLE_UNITS:
        return Finding(entry_id, Verdict.NO_ORACLE, f"{norm} is a single-unit file, not a whole-norm consolidation")
    if not excerpt.exists():
        return Finding(entry_id, Verdict.NO_ORACLE, f"no extracted sidecar for the excerpt {stem}")
    excerpt_units = readable_units(excerpt)
    if len(excerpt_units) != 1:
        return Finding(entry_id, Verdict.NO_ORACLE, f"excerpt {stem} holds {len(excerpt_units)} units, not one")
    excerpt_unit = excerpt_units[0]

    token = entry_id.partition(":")[2] or filename_token
    keys = [key for key in (excerpt_unit["title"].strip(),) if key]
    keys.extend(candidate_keys(token) or candidate_keys(filename_token))
    resolved, reason = _resolve_first(oracle, keys)
    if resolved is None:
        return Finding(entry_id, Verdict.UNRESOLVED, f"no candidate key reached a unit ({reason}); tried {keys}")

    current_title, current_text = resolved
    identity = _confirm_identity(entry_id, excerpt_unit["title"], current_title, "consolidated unit")
    if isinstance(identity, Finding):
        return identity
    anchor = next((unit["anchor"] for unit in oracle_units if unit["text"] == current_text.strip()), "")
    return _classify(
        entry_id,
        body,
        stem,
        excerpt_unit,
        current_title,
        current_text,
        identity_confirmed=identity,
        citation_confirmed=confirms_citation(token, current_title),
        resolved_anchor=anchor,
        oracle_kind=OracleKind.CONSOLIDATED_NORM,
    )


def _screen_via_article_payload(
    entry_id: str,
    body: dict[str, object],
    stem: str,
    fragment: str,
    cited_units: tuple[dict[str, str], ...],
    payloads: dict[str, tuple[ArticlePayload, ...]],
) -> Finding:
    """Measure one entry against the redaction in force of a BOE article payload."""
    document_id = body.get("document_id")
    if not isinstance(document_id, str) or document_id.upper() not in payloads:
        return Finding(entry_id, Verdict.NO_ORACLE, f"no whole-norm consolidation and no article payload for {stem}")
    if len(cited_units) != 1:
        return Finding(entry_id, Verdict.NO_ORACLE, f"excerpt {stem} holds {len(cited_units)} units, not one")
    excerpt_unit = cited_units[0]

    token = entry_id.partition(":")[2]
    wanted = {structural_key(key) for key in candidate_keys(token)} - {""}
    matched = [item for item in payloads[document_id.upper()] if structural_key(item.title) in wanted]
    if len(matched) != 1:
        return Finding(
            entry_id,
            Verdict.NO_ORACLE,
            f"{len(matched)} of {len(payloads[document_id.upper()])} article payloads for {document_id} "
            f"carry a title matching {sorted(wanted)}; refused rather than picked",
        )
    payload_file = matched[0]

    markup = payload_file.path.read_text(encoding=_UTF_8)
    try:
        redaction = assert_serves_the_article_in_force(
            markup,
            document_id=payload_file.document_id,
            block=payload_file.block,
        )
        in_force = _EDITORIAL_NOTE.sub("", article_redaction_markup(markup, redaction))
        current = render_normative_prose(in_force)
    except NormativeAcquisitionError as exc:
        return Finding(
            entry_id,
            Verdict.ORACLE_INDETERMINATE,
            f"{payload_file.path.name}: {exc}",
            oracle_kind=OracleKind.ARTICLE_REDACTION,
            catalogue_anchor=fragment,
            boe_block=payload_file.block,
        )

    current_title, current_text = _split_redaction_heading(current, block_title=payload_file.title)
    identity = _confirm_identity(entry_id, excerpt_unit["title"], current_title, "article payload reached")
    if isinstance(identity, Finding):
        return identity
    return _classify(
        entry_id,
        body,
        stem,
        excerpt_unit,
        current_title,
        current_text,
        identity_confirmed=identity,
        # Enforced rather than corroborated on this path: the token is what
        # selected the payload above, so agreement here restates that
        # selection. Recorded all the same, so one field means one thing across
        # both strata and a reader is told which stratum a finding sits in.
        citation_confirmed=confirms_citation(token, current_title),
        resolved_anchor=f"#{payload_file.block}",
        oracle_kind=OracleKind.ARTICLE_REDACTION,
        catalogue_anchor=fragment,
        boe_block=payload_file.block,
    )


def _split_redaction_heading(prose: str, *, block_title: str) -> tuple[str, str]:
    """Split a rendered redaction into ``(heading, body)``.

    The consolidated path compares an article's BODY against the excerpt's
    body, because the extractor lifts the heading into the unit title. A
    redaction carries its heading inline, so leaving it in the body would count
    the article's own heading as a clause the excerpt is missing.
    """
    head, separator, rest = prose.partition("\n")
    head_key = structural_key(head)
    if separator and head_key and head_key == structural_key(block_title):
        return head, rest
    return block_title, prose


def confirms_citation(citation_token: str, current_title: str) -> bool:
    """Return whether the CATALOGUE's own citation token names the unit compared.

    The companion to the excerpt-heading check, and the independent half of it.
    That check leads with the excerpt's own title as its first lookup key, so
    where the key resolves it largely restates itself; this one compares the
    reached unit against a heading derived from the entry id, which a different
    author wrote in a different file.

    Reported rather than enforced. The single live disagreement is a written
    ordinal against a digit, and refusing a resolution over a spelling variant
    would put a benign case in the same bucket as a wrong-article resolution.

    Args:
        citation_token: The catalogue's citation token, the part of an entry id
            after the colon.
        current_title: The heading of the unit the comparison was made against.

    Returns:
        Whether the reached heading is one the token derives.
    """
    wanted = {structural_key(key) for key in candidate_keys(citation_token)} - {""}
    reached = structural_key(current_title)
    return bool(reached) and reached in wanted


def _confirm_identity(entry_id: str, excerpt_title: str, current_title: str, reached: str) -> bool | Finding:
    """Return whether identity was corroborated, or the misresolution finding."""
    excerpt_key = structural_key(excerpt_title)
    if not excerpt_key:
        return False
    if excerpt_key != structural_key(current_title):
        return Finding(
            entry_id,
            Verdict.MISRESOLVED,
            f"excerpt heading {excerpt_title.split('.')[0]!r} but the {reached} is {current_title.split('.')[0]!r}",
        )
    return True


def _classify(
    entry_id: str,
    body: dict[str, object],
    stem: str,
    excerpt_unit: dict[str, str],
    current_title: str,
    current_text: str,
    *,
    identity_confirmed: bool,
    citation_confirmed: bool,
    resolved_anchor: str,
    oracle_kind: OracleKind,
    catalogue_anchor: str = "",
    boe_block: str = "",
) -> Finding:
    current_clauses = clause_chunks(current_text)
    excerpt_normalised = normalise_corpus_text(excerpt_unit["text"])
    # Title-inclusive, because the extractor lifts an article's heading into
    # the unit title on the oracle side and leaves it inline on an excerpt it
    # found no heading delimiter for. The registry gate normalises the unit
    # with its title for the same reason, so one form serves both readings
    # below: without it the article's own caption counts as text the excerpt
    # adds, and a phrase quoting the heading fires the gate check spuriously.
    current_normalised = normalise_corpus_text(f"{current_title}\n{current_text}")
    absent = [clause for clause in current_clauses if clause not in excerpt_normalised]
    extra = [
        clause
        for clause in clause_chunks(excerpt_unit["text"])
        if clause not in current_normalised and not _PROVENANCE_ANNOTATION.search(clause)
    ]
    opening_matches = bool(current_clauses) and current_clauses[0] in excerpt_normalised

    if not absent and not extra:
        verdict = Verdict.MATCHES
    elif _is_vintaged(stem):
        # Consulted before either direction is read: a declared vintage
        # legitimately holds text current law dropped, which is the whole
        # shape ``excerpt_carries_more`` names. Ordering it second would
        # reclassify the deliberate case as the defect.
        verdict = Verdict.VINTAGED
    elif not absent:
        verdict = Verdict.EXCERPT_CARRIES_MORE
    else:
        declared = body.get("required_text")
        required = tuple(str(phrase) for phrase in declared) if isinstance(declared, list) else ()
        fires = any(normalise_corpus_text(phrase) not in current_normalised for phrase in required)
        verdict = Verdict.DIVERGES_GATE_FIRES if fires else Verdict.DIVERGES_GATE_GREEN

    return Finding(
        entry_id=entry_id,
        verdict=verdict,
        detail=stem,
        clauses_total=len(current_clauses),
        clauses_absent=len(absent),
        clauses_extra=len(extra),
        opening_sentence_matches=opening_matches,
        identity_confirmed=identity_confirmed,
        citation_confirmed=citation_confirmed,
        resolved_anchor=resolved_anchor,
        oracle_kind=oracle_kind,
        catalogue_anchor=catalogue_anchor,
        boe_block=boe_block,
    )


def _is_vintaged(stem: str) -> bool:
    """Return whether the excerpt declares a historical vintage in its stem.

    A trailing year alone does not say so, and reading it that way is a FALSE
    CLEAN VERDICT: ``vintaged`` means "divergence from current text is correct
    by design", so a misclassification excuses a real staleness. Almost every
    norm carries its own enactment year in its name -- ``orden-hac-590-2021``,
    ``trlirnr-rdleg-5-2004``, ``ley-12-2002`` -- and a bare-norm-stem rule
    called 29 of those vintaged the moment the population widened to entries
    citing a norm-named excerpt.

    A vintage suffix is a year that FOLLOWS a citation token
    (``ley-35-2006-art-52-2015`` is article 52 as it stood in 2015), so the
    stem must carry a citation head as well as the year.
    """
    segments = stem.split("-")
    if not _VINTAGE_YEAR.match(segments[-1]):
        return False
    return any(segment in _CITATION_HEADS for segment in segments[:-1])


def _resolve_first(sidecar: Path, keys: list[str]) -> tuple[tuple[str, str] | None, str]:
    reason = "no candidate keys were derivable"
    for key in keys:
        try:
            rendered = resolve_anchored_extracted_unit(sidecar, anchor=key, include_title=True)
        except CorpusAnchorResolutionError as exc:
            reason = str(exc)
            continue
        title, _, text = rendered.partition("\n")
        return (title, text), ""
    return None, reason


def main() -> int:
    """Print the reconciled split and the worklist.

    Exits 0 whatever the findings say: this reports and never gates, because
    the divergences are known-present and a red exit would tax every peer for a
    defect they did not create.

    It does REFUSE, non-zero, when its own inputs cannot support a result -- a
    missing catalogue, an empty corpus, an unreadable sidecar, an empty
    population. Each of those would otherwise print a clean worklist, and a
    silent all-clear is the one output this screen must never emit. "Always
    exits 0" described the findings and read as a promise about the process.
    """
    root = REPO_ROOT
    result = screen(root)
    findings = list(result.findings)
    if not findings:
        raise SystemExit("screened zero excerpt-backed entries; the result would be meaningless")

    print(summarise(findings, result.population))
    print(f"\nexcluded, cites its norm's whole consolidated file: {result.cites_consolidated_norm}")

    for kind in (OracleKind.CONSOLIDATED_NORM, OracleKind.ARTICLE_REDACTION):
        subset = [finding for finding in findings if finding.oracle_kind is kind]
        if not subset:
            continue
        print(f"\n=== measured against a {kind.value} oracle ({len(subset)}) ===")
        print(summarise(subset, len(subset)))
        # Stratified, because the two strata are not the same measurement. An
        # identity-confirmed excerpt carries the article's own structural
        # heading and is a faithful per-article copy; an unconfirmed one is a
        # curated catalogue snippet, abridged by design, whose divergence from
        # full current text says nothing about staleness. Pooling them makes a
        # catch rate that is mostly a statement about excerpt shape.
        confirmed = [finding for finding in subset if finding.identity_confirmed]
        print(f"\n  -- identity confirmed only ({len(confirmed)}) --")
        print("\n".join(f"  {line}" for line in summarise(confirmed, len(confirmed)).splitlines()))

    for verdict in (
        Verdict.UNRESOLVED,
        Verdict.MISRESOLVED,
        Verdict.ORACLE_INDETERMINATE,
        Verdict.EXCERPT_CARRIES_MORE,
        Verdict.DIVERGES_GATE_GREEN,
        Verdict.DIVERGES_GATE_FIRES,
    ):
        selected = [finding for finding in findings if finding.verdict is verdict]
        if not selected:
            continue
        print(f"\n--- {verdict.value} ({len(selected)}) ---")
        for finding in selected:
            print(f"  {finding.render()}")
    unconfirmed = [finding for finding in findings if finding.clauses_total and not finding.identity_confirmed]
    if unconfirmed:
        print(f"\n--- identity unconfirmed ({len(unconfirmed)}) ---")
        print("  The excerpt carries a curated title rather than a structural heading, so its")
        print("  provision identity could not be cross-checked. The verdict stands on the")
        print("  derived key alone and is weaker than the others.")
        for finding in unconfirmed:
            print(f"  {finding.entry_id}")
    unbound = [finding for finding in findings if finding.clauses_total and not finding.citation_confirmed]
    if unbound:
        print(f"\n--- citation token unbound ({len(unbound)}) ---")
        print("  The entry's own citation token derives no heading matching the unit the")
        print("  comparison was made against. Reported, never promoted to misresolved: a")
        print("  written ordinal against a digit is a spelling variant, not a wrong article.")
        for finding in unbound:
            derived = sorted({structural_key(key) for key in candidate_keys(finding.entry_id.partition(":")[2])} - {""})
            print(f"  {finding.entry_id}: token derives {derived}, resolved {finding.resolved_anchor or '(none)'}")
    disagreeing = [finding for finding in findings if finding.anchor_disagrees]
    if disagreeing:
        substantive = [finding for finding in disagreeing if finding.anchor_names_another_block]
        print(f"\n--- catalogue anchor disagrees with BOE's block id ({len(disagreeing)}) ---")
        print(f"  {len(substantive)} name a DIFFERENT block; the rest are the same provision spelled")
        print("  two ways. Reported, never acted on: repointing an anchor is adjudication.")
        for finding in disagreeing:
            marker = "DIFFERENT BLOCK" if finding.anchor_names_another_block else "naming form"
            print(
                f"  {finding.entry_id}: cites #{finding.catalogue_anchor}, BOE serves #{finding.boe_block} ({marker})"
            )
    return 0


if __name__ == "__main__":
    sys.exit(main())

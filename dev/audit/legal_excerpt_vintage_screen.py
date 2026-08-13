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

AND EVERY RESOLUTION IS CROSS-CHECKED. The resolved unit's own heading must
name the provision the entry cites. This is not decoration: it is the only
safeguard against the anchor-precedence hazard above, and it caught a
mis-derived candidate of this screen's own making during authoring.

A RESOLUTION FAILURE IS A VERDICT, NEVER A DROP-OUT. An earlier instrument let
entries whose anchor resolved to nothing fall silently out of the comparison,
so its published coverage ratio was measured against a denominator that
excluded a third of its own population. Every verdict class here is exhaustive
over the input population and :func:`summarise` reconciles the totals; a screen
whose counts do not add up says so instead of printing a number.

MEASURED LIMIT, stated because it bounds every verdict this screen emits. The
opening-operative-sentence check is conclusive for SAME-PROVISION IDENTITY and
is not a full-text comparison, so a later-clause divergence remains possible in
an entry reported as matching on it. The clause-level count is the fuller
signal, and even that compares against the bundled consolidated file rather
than against the law: a matching excerpt and a stale consolidated file agree
with each other. This screen detects disagreement with the bundled current
text. It never establishes that an excerpt is CORRECT.

THE WIDENING THAT WAS REJECTED. One entry (``ley-31-2022:art-39``) resolves to
a unit whose heading disagrees, because the excerpt's own title differs from
the consolidated norm's article of that number and the fallback then meets the
positional-anchor hazard. Scanning the consolidated units directly for a
matching heading would recover it, and was rejected: that forks unit selection
away from the canonical primitive to buy one entry, and the entry is reported
as ``misresolved`` with both headings, which is the honest disposition for what
is plausibly a mislabelled excerpt rather than a resolution defect.

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
import tomllib
from collections import Counter
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path
from typing import Final

from cadrumo.core import CorpusAnchorResolutionError, normalise_corpus_text, resolve_anchored_extracted_unit

#: Declared locally rather than imported from ``cadrumo.core``: ``dev/`` is
#: unshipped tooling and must not reach into the shipped package's internals,
#: so every dev module carries its own constant (see the sibling screens in
#: this package).
_UTF_8: Final[str] = "utf-8"

_LEGAL_DIR: Final = Path("src/cadrumo/_data/registry/aeat/legal")
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
    """The norm ships no whole-norm consolidated counterpart. Not comparable,
    and neither clean nor dirty -- simply unmeasured."""

    UNRESOLVED = "unresolved"
    """A consolidated counterpart exists but no candidate key reached a unit."""

    MISRESOLVED = "misresolved"
    """A unit was reached and its heading names a DIFFERENT provision, so any
    divergence figure computed from it would be about the wrong article."""

    MATCHES = "matches"
    """Every clause of the current text is present in the excerpt. Nothing for
    a gate to catch, so the gate is UNTESTED here rather than proven."""

    VINTAGED = "vintaged"
    """The excerpt is a declared historical vintage. Divergence from current
    text is CORRECT by design and must never be "fixed"."""

    DIVERGES_GATE_FIRES = "diverges_gate_fires"
    """The excerpt diverges and the entry's ``required_text`` would notice,
    because at least one declared phrase is absent from the current text."""

    DIVERGES_GATE_GREEN = "diverges_gate_green"
    """The excerpt diverges and every declared phrase survives in the current
    text, so the gate passes over a stale document. The defect class."""


@dataclass(frozen=True)
class Finding:
    """One entry's measured relationship to the bundled current text."""

    entry_id: str
    verdict: Verdict
    detail: str
    clauses_total: int = 0
    clauses_absent: int = 0
    opening_sentence_matches: bool = False
    identity_confirmed: bool = False
    resolved_anchor: str = ""

    def render(self) -> str:
        """Return the finding as one operator-readable line."""
        if self.verdict in {Verdict.NO_ORACLE, Verdict.UNRESOLVED, Verdict.MISRESOLVED}:
            return f"{self.entry_id}: {self.verdict.value} -- {self.detail}"
        opening = "opening sentence verbatim" if self.opening_sentence_matches else "opening sentence differs"
        identity = "identity confirmed" if self.identity_confirmed else "identity UNCONFIRMED"
        return (
            f"{self.entry_id}: {self.verdict.value} -- {self.clauses_absent}/{self.clauses_total} "
            f"current clauses absent from the excerpt; {opening}; {identity}; "
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
    """
    parts = stem.split("-")
    for index in range(1, len(parts)):
        prefix = "-".join(parts[:index])
        if prefix in stems:
            return prefix, "-".join(parts[index:])
    return None


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
        for verdict in (Verdict.MATCHES, Verdict.VINTAGED, Verdict.DIVERGES_GATE_FIRES, Verdict.DIVERGES_GATE_GREEN)
    )
    diverging = counts[Verdict.DIVERGES_GATE_FIRES] + counts[Verdict.DIVERGES_GATE_GREEN] + counts[Verdict.VINTAGED]
    lines.append(f"\ncomparable: {comparable} of {population} screened")
    lines.append(
        f"of {diverging} measured divergences the gate catches {counts[Verdict.DIVERGES_GATE_FIRES]} "
        f"({counts[Verdict.VINTAGED]} of them vintaged by design)"
    )
    return "\n".join(lines)


def screen(root: Path) -> tuple[list[Finding], int]:
    """Return one finding per excerpt-backed entry, and the population size."""
    entries = _load_entries(root / _LEGAL_DIR)
    corpus = root / _CORPUS_DIR
    stems = frozenset(path.name.removesuffix(".html") for path in corpus.glob("*.html"))
    if not stems:
        raise SystemExit(f"read zero corpus files, so the result would be meaningless: {corpus}")

    findings: list[Finding] = []
    for entry_id, body in sorted(entries.items()):
        corpus_ref = body.get("corpus_ref", "")
        if not isinstance(corpus_ref, str):
            continue
        path, _, _fragment = corpus_ref.partition("#")
        if not path.endswith(".html"):
            continue
        stem = Path(path).name.removesuffix(".html")
        root_pair = norm_root(stem, stems)
        if root_pair is None:
            continue  # The entry cites the consolidated file itself: its own current text.
        findings.append(_screen_entry(entry_id, body, corpus, stem, root_pair))
    return findings, len(findings)


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
    identity_confirmed = False
    excerpt_key = structural_key(excerpt_unit["title"])
    if excerpt_key:
        if excerpt_key != structural_key(current_title):
            return Finding(
                entry_id,
                Verdict.MISRESOLVED,
                f"excerpt heading {excerpt_unit['title'].split('.')[0]!r} "
                f"but the consolidated unit reached is {current_title.split('.')[0]!r}",
            )
        identity_confirmed = True

    return _classify(entry_id, body, stem, excerpt_unit, current_title, current_text, oracle_units, identity_confirmed)


def _classify(
    entry_id: str,
    body: dict[str, object],
    stem: str,
    excerpt_unit: dict[str, str],
    current_title: str,
    current_text: str,
    oracle_units: tuple[dict[str, str], ...],
    identity_confirmed: bool,
) -> Finding:
    current_clauses = clause_chunks(current_text)
    excerpt_normalised = normalise_corpus_text(excerpt_unit["text"])
    absent = [clause for clause in current_clauses if clause not in excerpt_normalised]
    opening_matches = bool(current_clauses) and current_clauses[0] in excerpt_normalised
    anchor = next((unit["anchor"] for unit in oracle_units if unit["text"] == current_text.strip()), "")

    if not absent:
        verdict = Verdict.MATCHES
    elif _is_vintaged(stem):
        verdict = Verdict.VINTAGED
    else:
        declared = body.get("required_text")
        required = tuple(str(phrase) for phrase in declared) if isinstance(declared, list) else ()
        # Title-inclusive, because the registry gate normalises the unit with
        # its title; testing the body alone would fire on a phrase quoting the
        # article's own heading.
        current_normalised = normalise_corpus_text(f"{current_title}\n{current_text}")
        fires = any(normalise_corpus_text(phrase) not in current_normalised for phrase in required)
        verdict = Verdict.DIVERGES_GATE_FIRES if fires else Verdict.DIVERGES_GATE_GREEN

    return Finding(
        entry_id=entry_id,
        verdict=verdict,
        detail=stem,
        clauses_total=len(current_clauses),
        clauses_absent=len(absent),
        opening_sentence_matches=opening_matches,
        identity_confirmed=identity_confirmed,
        resolved_anchor=anchor,
    )


def _is_vintaged(stem: str) -> bool:
    """Return whether the excerpt declares a historical vintage in its stem."""
    return bool(_VINTAGE_YEAR.match(stem.rsplit("-", maxsplit=1)[-1]))


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


def _load_entries(legal_dir: Path) -> dict[str, dict[str, object]]:
    if not legal_dir.is_dir():
        raise SystemExit(f"legal catalogue is missing, so the result would be meaningless: {legal_dir}")
    entries: dict[str, dict[str, object]] = {}
    for path in sorted(legal_dir.glob("*.toml")):
        data = tomllib.loads(path.read_text(encoding=_UTF_8))
        for entry_id, body in data.get("legal", {}).items():
            entries[entry_id] = body
    return entries


def main() -> int:
    """Print the reconciled split and the worklist. Always exits 0 -- this reports."""
    root = Path(__file__).resolve().parents[2]
    findings, population = screen(root)
    if not findings:
        raise SystemExit("screened zero excerpt-backed entries; the result would be meaningless")

    print(summarise(findings, population))
    for verdict in (Verdict.UNRESOLVED, Verdict.MISRESOLVED, Verdict.DIVERGES_GATE_GREEN, Verdict.DIVERGES_GATE_FIRES):
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
    return 0


if __name__ == "__main__":
    sys.exit(main())

"""Screen: a casilla whose translation changed where its Spanish did not.

The catalogues key a casilla label by revision, so every revision carries its own
copy of every label. Copies that are free to disagree eventually do, and the
question is which disagreements mean something.

Spanish is the source. If a casilla's Spanish text is byte-identical across two
revisions, the official wording did not change between them - so a translation
that differs across those same two revisions is not tracking anything. It is two
renderings of one string, and a filer sees whichever revision they are filing
under.

Four conditions are reported, and every row names one of them:

- ``translation_drifts_where_source_is_constant`` - the Spanish is one string
  across the revisions both share, and the translation is not. Nothing in the
  official text justifies the difference.
- ``translation_tracks_source_change`` - the Spanish differs too, so the
  translation is doing its job. Reported rather than filtered, because the two
  populations are the same size to within a factor and a reader who sees only
  the first would think every varying translation is drift.
- ``translation_missed_source_change`` - the Spanish differs across the shared
  revisions and the translation does not. The inverse defect, and the sharper
  one: a filer reads text that no longer matches the official wording. It is
  also the one a screen looking only at varying translations cannot see, which
  is why this iterates from the source side as well.
- ``source_coverage_insufficient`` - the locale labels the casilla under
  revisions the Spanish catalogue does not, so there is no shared pair to
  compare. Kept as its own condition rather than folded into either answer: a
  question that could not be asked is not an answer, and a first version of this
  measurement counted these as tracking a change.

Each row also carries HOW its renderings differ, because the 3,157 drifting
casillas are not one worklist. Some differ only in case, accent or punctuation
and can be collapsed mechanically; others use different words and need a
translator. Reporting them as one number would put a capitalisation beside a
rewritten sentence and price them the same.

The rows name casillas and count renderings; they do not print the label text.
The renderings are carried on each finding for a consumer that wants them, and
the sibling censuses in this package print identifiers and counts for the same
reason - writing Catalan and Hungarian labels to a redirected stdout fails on
the ambient Windows encoding, which truncated this screen's own first run
mid-stream and exited 1 while the piped version had looked fine.

The screen exits 0 whatever it finds. It reports; it does not gate. Which of two
renderings is right is a translator's judgement, and nothing here can make it.
"""

from __future__ import annotations

import collections
import re
import sys
import unicodedata
from dataclasses import dataclass
from typing import Final

from .casilla_label_derivation import casilla_labels

__all__ = [
    "DIFFERENCE_KINDS",
    "KINDS",
    "SHARED_WORDING_RATIO",
    "SOURCE_LOCALE",
    "TranslationDriftFinding",
    "difference_kind",
    "drift_findings",
    "screen_corpus",
]

#: Every condition this screen can report, declared once and used at each
#: emission site so the set cannot be recovered by reading the source wrong.
KINDS: Final[tuple[str, ...]] = (
    "translation_drifts_where_source_is_constant",
    "translation_missed_source_change",
    "translation_tracks_source_change",
    "source_coverage_insufficient",
)

#: How two renderings of one string differ, coarsest agreement first. Declared
#: beside the conditions because it is a second axis rather than a fifth
#: condition: every drifting row has one, and it says what the repair costs
#: rather than whether there is one.
DIFFERENCE_KINDS: Final[tuple[str, ...]] = (
    "identical_after_folding",
    "whitespace_only",
    "shared_wording",
    "distinct_wording",
    "not_applicable",
)

#: The share of words two renderings must have in common to count as sharing
#: their wording. A threshold is a judgement and this one is written down rather
#: than buried: at 0.6 the corpus splits 1,475 shared against 1,199 distinct, and
#: a reader who disagrees can move it and re-run rather than re-derive it.
SHARED_WORDING_RATIO: Final[float] = 0.6

#: The locale the official wording is written in, and therefore the only one
#: whose variation can justify variation elsewhere.
SOURCE_LOCALE: Final[str] = "es"


@dataclass(frozen=True, slots=True)
class TranslationDriftFinding:
    """One casilla whose translation varies across revisions."""

    locale: str
    modelo: str
    casilla: str
    kind: str
    #: The distinct renderings the locale carries, sorted.
    renderings: tuple[str, ...]
    #: How many revisions the two catalogues label the casilla under in common.
    shared_revisions: int
    #: How the renderings differ, or ``not_applicable`` where there is only one.
    #: Carried rather than left to a caller so the report and any consumer agree
    #: about a judgement that decides who has to do the work.
    difference: str = "not_applicable"


def _fold(text: str) -> str:
    """Return ``text`` with case, accents and punctuation removed.

    Accents are stripped through NFKD decomposition rather than a replacement
    table, so a locale this project does not yet ship is folded correctly
    without anybody extending a list.
    """
    decomposed = unicodedata.normalize("NFKD", text)
    stripped = "".join(character for character in decomposed if not unicodedata.combining(character))
    return re.sub(r"[^a-z0-9]+", " ", stripped.lower()).strip()


def difference_kind(renderings: tuple[str, ...]) -> str:
    """Return how a casilla's renderings differ from each other.

    The order is deliberate: a difference that survives folding is checked
    against whitespace before wording, because two renderings identical apart
    from a doubled space fold to different strings only by that space, and
    calling them a wording difference would send a translator to look at
    nothing.

    ``not_applicable`` when there is one rendering or none. A single rendering
    has no difference to describe, and reporting it under any of the others
    would mean the census counted a row that has no repair.
    """
    if len(renderings) < 2:
        return "not_applicable"
    folded = {_fold(text) for text in renderings}
    if len(folded) == 1:
        return "identical_after_folding"
    if len({text.replace(" ", "") for text in folded}) == 1:
        return "whitespace_only"
    words = [set(text.split()) for text in folded]
    shared = set.intersection(*words)
    union = set.union(*words)
    if union and len(shared) / len(union) >= SHARED_WORDING_RATIO:
        return "shared_wording"
    return "distinct_wording"


def drift_findings(
    labels: dict[str, dict[str, dict[str, str]]],
    source: dict[str, dict[str, dict[str, str]]],
    *,
    locale: str,
) -> tuple[TranslationDriftFinding, ...]:
    """Classify every casilla whose ``locale`` text varies across revisions.

    Separated from the corpus read so constructed input travels the same code
    path the catalogues do, and so each condition is reachable from a test with
    input written in it.

    Only revisions the two catalogues SHARE are compared. Comparing a locale's
    revision against a Spanish revision it does not label would be comparing two
    different questions, and the count of shared revisions is carried on each
    row so a reader can see how much the comparison rested on.
    """
    findings: list[TranslationDriftFinding] = []
    subjects = {(modelo, casilla) for modelo, casillas in labels.items() for casilla in casillas} | {
        (modelo, casilla) for modelo, casillas in source.items() for casilla in casillas
    }
    for modelo, casilla in sorted(subjects):
        texts = labels.get(modelo, {}).get(casilla, {})
        spanish = source.get(modelo, {}).get(casilla, {})
        shared = sorted(set(texts) & set(spanish))
        if len(shared) < 2:
            # Only reported when something varies; a casilla labelled under one
            # revision has nothing to disagree with and is not a finding.
            if len(set(texts.values())) < 2 and len(set(spanish.values())) < 2:
                continue
            kind = "source_coverage_insufficient"
        else:
            translation_varies = len({texts[revision] for revision in shared}) > 1
            source_varies = len({spanish[revision] for revision in shared}) > 1
            if translation_varies and not source_varies:
                kind = "translation_drifts_where_source_is_constant"
            elif source_varies and not translation_varies:
                kind = "translation_missed_source_change"
            elif translation_varies and source_varies:
                kind = "translation_tracks_source_change"
            else:
                continue
        findings.append(
            TranslationDriftFinding(
                locale=locale,
                modelo=modelo,
                casilla=casilla,
                kind=kind,
                renderings=(renderings := tuple(sorted(set(texts.values())))),
                shared_revisions=len(shared),
                difference=difference_kind(renderings),
            )
        )
    return tuple(findings)


def screen_corpus() -> tuple[TranslationDriftFinding, ...]:
    """Screen every non-source locale's catalogues against the Spanish one."""
    source = casilla_labels(SOURCE_LOCALE)
    findings: list[TranslationDriftFinding] = []
    for locale in sorted(_translated_locales()):
        findings.extend(drift_findings(casilla_labels(locale), source, locale=locale))
    return tuple(findings)


def _translated_locales() -> tuple[str, ...]:
    """Return every supported locale that is not the source.

    Read from the locale manager rather than written here, because a fifth
    locale must appear in this screen without anybody remembering to add it.
    """
    from ._paths import LOCALES_DIR
    from .manager import discover_locale_codes

    return tuple(code for code in discover_locale_codes(LOCALES_DIR) if code != SOURCE_LOCALE)


def main() -> int:
    """Print one greppable row per finding and a closing census; always exit 0."""
    findings = screen_corpus()
    for item in findings:
        if item.kind != "translation_drifts_where_source_is_constant":
            continue
        sys.stdout.write(
            f"translation_drift locale={item.locale} modelo={item.modelo} casilla={item.casilla} "
            f"kind={item.kind} shared_revisions={item.shared_revisions} "
            f"renderings={len(item.renderings)}\n"
        )
    per_locale: dict[str, collections.Counter[str]] = collections.defaultdict(collections.Counter)
    for item in findings:
        per_locale[item.locale][item.kind] += 1
    for locale in sorted(per_locale):
        tally = " ".join(f"{kind}={per_locale[locale][kind]}" for kind in KINDS)
        sys.stdout.write(f"summary locale={locale} varying_casillas={sum(per_locale[locale].values())} {tally}\n")
    drifting = [item for item in findings if item.kind == "translation_drifts_where_source_is_constant"]
    by_difference: collections.Counter[str] = collections.Counter(item.difference for item in drifting)
    census = " ".join(f"{kind}={by_difference[kind]}" for kind in DIFFERENCE_KINDS)
    sys.stdout.write(f"summary drifting={len(drifting)} {census}\n")
    mechanical = by_difference["identical_after_folding"] + by_difference["whitespace_only"]
    sys.stdout.write(
        f"summary locales={len(per_locale)} varying={len(findings)} drifting={len(drifting)} "
        f"mechanically_resolvable={mechanical} needs_a_translator={by_difference['distinct_wording']}\n"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

"""Screen: a casilla whose translation changed where its Spanish did not.

The catalogues key a casilla label by revision, so every revision carries its own
copy of every label. Copies that are free to disagree eventually do, and the
question is which disagreements mean something.

Spanish is the source. If a casilla's Spanish text is byte-identical across two
revisions, the official wording did not change between them - so a translation
that differs across those same two revisions is not tracking anything. It is two
renderings of one string, and a filer sees whichever revision they are filing
under.

Three conditions are reported, and every row names one of them:

- ``translation_drifts_where_source_is_constant`` - the Spanish is one string
  across the revisions both share, and the translation is not. Nothing in the
  official text justifies the difference.
- ``translation_tracks_source_change`` - the Spanish differs too, so the
  translation is doing its job. Reported rather than filtered, because the two
  populations are the same size to within a factor and a reader who sees only
  the first would think every varying translation is drift.
- ``source_coverage_insufficient`` - the locale labels the casilla under
  revisions the Spanish catalogue does not, so there is no shared pair to
  compare. Kept as its own condition rather than folded into either answer: a
  question that could not be asked is not an answer, and a first version of this
  measurement counted these as tracking a change.

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
import sys
from dataclasses import dataclass
from typing import Final

from .casilla_label_derivation import casilla_labels

__all__ = [
    "KINDS",
    "SOURCE_LOCALE",
    "TranslationDriftFinding",
    "drift_findings",
    "screen_corpus",
]

#: Every condition this screen can report, declared once and used at each
#: emission site so the set cannot be recovered by reading the source wrong.
KINDS: Final[tuple[str, ...]] = (
    "translation_drifts_where_source_is_constant",
    "translation_tracks_source_change",
    "source_coverage_insufficient",
)

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
    for modelo, casillas in sorted(labels.items()):
        for casilla, texts in sorted(casillas.items()):
            renderings = tuple(sorted(set(texts.values())))
            if len(renderings) < 2:
                continue
            spanish = source.get(modelo, {}).get(casilla, {})
            shared = {revision: spanish[revision] for revision in texts if revision in spanish}
            if len(shared) < 2:
                kind = "source_coverage_insufficient"
            elif len(set(shared.values())) == 1:
                kind = "translation_drifts_where_source_is_constant"
            else:
                kind = "translation_tracks_source_change"
            findings.append(
                TranslationDriftFinding(
                    locale=locale,
                    modelo=modelo,
                    casilla=casilla,
                    kind=kind,
                    renderings=renderings,
                    shared_revisions=len(shared),
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
    drifting = sum(1 for item in findings if item.kind == "translation_drifts_where_source_is_constant")
    sys.stdout.write(f"summary locales={len(per_locale)} varying={len(findings)} drifting={drifting}\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

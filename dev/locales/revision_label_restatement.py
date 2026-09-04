"""How much of the shipped casilla label corpus repeats itself across revisions.

A casilla's label is a property of the casilla. The catalogues key it by
revision, so declaring a revision costs a label for every casilla in it whether
or not the official text changed - and mostly it does not. The consequence is
paid in translation: a new revision of modelo 100 asks for thousands of strings
that already exist verbatim under the previous one, in every shipped locale.

Three counts are reported, and every row names one of them:

- ``restated`` - label strings that exist to say what another revision's string
  already says, counted as the surplus (a casilla labelled identically under
  three revisions contributes two). This is the derivable population: text a
  generator could carry rather than a translator retype.
- ``divergent`` - casillas whose label text genuinely differs between
  revisions. These are what a per-revision key is FOR, and any derivation must
  keep them expressible; a design that cannot express them is worse than the
  duplication it removes.
- ``single`` - casillas labelled under one revision only, which neither restate
  nor diverge.

The split is reported per locale rather than summed, because a derivation that
collapsed one locale and left the others untouched would report progress while
leaving most of the work undone.

Every root, catalogue path and flattening step here is borrowed from the
tooling that already owns it: :data:`~dev.locales._paths.LOCALES_DIR` for the
root, :func:`~dev.locales.manager.discover_locale_codes` and
:func:`~dev.locales.manager.locale_catalogue_source` for which catalogues exist
and where each one lives, and
:func:`~dev.locales.manager._flatten_raw_locale_leaves` for the dotted keys. A
glob for one catalogue shape would have been the tempting shortcut and is the
one :func:`~dev.locales.manager.discover_locale_codes` documents as the more
dangerous mistake: it returns empty against the shape the tree does not carry,
and empty reads exactly like a clean corpus.

This module measures. It exits 0 whatever it finds and gates nothing: a gate on
a condition carrying five figures of findings would need a tolerance, and a
tolerance is the ratchet this project retired.
"""

from __future__ import annotations

import collections
import sys
from dataclasses import dataclass

import yaml

from ._paths import LOCALES_DIR
from .manager import _flatten_raw_locale_leaves, discover_locale_codes, locale_catalogue_source

__all__ = [
    "LabelRestatementCensus",
    "casilla_labels",
    "label_restatement_census",
    "restatement_split",
    "translation_diverges_where_source_agrees",
]

_REVISION_SEGMENT = ".revision."
_CASILLA_SEGMENT = ".casilla."
_LABEL_SUFFIX = ".label"


@dataclass(frozen=True, slots=True)
class LabelRestatementCensus:
    """One locale's casilla label corpus, split by how many revisions state it."""

    locale: str
    labels: int
    restated: int
    divergent: int
    single: int
    worst: tuple[tuple[str, int], ...]


def casilla_labels(locale: str) -> dict[str, dict[str, dict[str, str]]]:
    """Return ``{modelo: {casilla: {revision: label}}}`` for one locale.

    Read from the catalogue files rather than through a translation accessor,
    because the question is what the catalogues STORE. An accessor resolves
    fallbacks, which is the behaviour that makes a restated label and a derived
    one indistinguishable.
    """
    source = locale_catalogue_source(LOCALES_DIR, locale)
    if source is None:
        return {}
    paths = sorted(source.rglob("*.yml")) if source.is_dir() else [source]
    found: dict[str, dict[str, dict[str, str]]] = {}
    for path in paths:
        parsed = yaml.safe_load(path.read_text(encoding="utf-8"))
        for key, text in _flatten_raw_locale_leaves(parsed).items():
            if not isinstance(text, str) or not key.endswith(_LABEL_SUFFIX):
                continue
            if _REVISION_SEGMENT not in key or _CASILLA_SEGMENT not in key:
                continue
            head, tail = key.split(_REVISION_SEGMENT, 1)
            revision, casilla_part = tail.split(_CASILLA_SEGMENT, 1)
            modelo = head.rsplit(".", 1)[-1]
            casilla = casilla_part[: -len(_LABEL_SUFFIX)]
            found.setdefault(modelo, {}).setdefault(casilla, {})[revision] = text
    return found


def restatement_split(labels: dict[str, dict[str, dict[str, str]]], *, locale: str) -> LabelRestatementCensus:
    """Classify an already-read label corpus, separately from reading it.

    Kept apart from :func:`label_restatement_census` because the classification
    is the instrument: it decides what counts as a restatement, and an
    instrument proven only against the live corpus is proven against whatever
    it happens to say. Given a mapping, this can be shown to separate the three
    populations on input constructed to hold one of each.
    """
    total = restated = divergent = single = 0
    per_modelo: collections.Counter[str] = collections.Counter()
    for modelo, casillas in labels.items():
        for texts in casillas.values():
            total += len(texts)
            if len(texts) == 1:
                single += 1
            elif len(set(texts.values())) == 1:
                restated += len(texts) - 1
                per_modelo[modelo] += len(texts) - 1
            else:
                divergent += 1
    return LabelRestatementCensus(
        locale=locale,
        labels=total,
        restated=restated,
        divergent=divergent,
        single=single,
        worst=tuple(per_modelo.most_common(6)),
    )


def label_restatement_census(locale: str) -> LabelRestatementCensus:
    """Return one locale's restatement census, read from the shipped catalogues."""
    return restatement_split(casilla_labels(locale), locale=locale)


def translation_diverges_where_source_agrees(source: str, target: str) -> tuple[tuple[str, str], ...]:
    """Return casillas whose source text is identical across revisions but whose translation is not.

    A defect rather than a cost. Where the official Spanish says the same thing
    under two revisions, two different translations of it are two answers to one
    question, and the reader of one revision cannot tell which is current. A
    per-modelo derivation collapses these; nothing sees them today.
    """
    source_labels = casilla_labels(source)
    target_labels = casilla_labels(target)
    found: list[tuple[str, str]] = []
    for modelo, casillas in sorted(source_labels.items()):
        for casilla, texts in sorted(casillas.items()):
            if len(texts) < 2 or len(set(texts.values())) != 1:
                continue
            translated = target_labels.get(modelo, {}).get(casilla, {})
            if len(translated) > 1 and len(set(translated.values())) > 1:
                found.append((modelo, casilla))
    return tuple(found)


def main() -> int:
    """Print one row per shipped locale and a closing census; always exit 0."""
    total = 0
    for locale in sorted(discover_locale_codes(LOCALES_DIR)):
        census = label_restatement_census(locale)
        if not census.labels:
            continue
        total += census.restated
        worst = " ".join(f"{modelo}={count}" for modelo, count in census.worst)
        sys.stdout.write(
            f"label_restatement locale={census.locale} labels={census.labels} "
            f"restated={census.restated} divergent={census.divergent} "
            f"single={census.single} worst={worst}\n"
        )
    sys.stdout.write(f"summary restated_across_locales={total}\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

"""Derive per-modelo casilla labels with per-revision overrides, losslessly.

The catalogues key a casilla label by revision, so a revision costs a label for
every casilla in it whether the official text changed or not. The derived form
keys the label by casilla and carries an override only for the revisions whose
text genuinely differs.

This module builds that form and proves it reproduces the shipped bytes. It
changes no catalogue: the key shape the runtime reads is generated from the
registry, so the collapse cannot land here. What can land here is the evidence
that the collapse is safe to make - which is the part worth having before
anyone edits a key shape, because a derivation that loses a string loses
taxpayer-facing text and the loss reads as a missing translation rather than as
a bug in a generator.

Two properties are asserted rather than assumed:

- **Lossless.** Expanding the derived form back over the revisions each casilla
  is labelled under must reproduce every current label byte-for-byte. This
  holds by construction, so the assertion is not there to discover a
  counterexample in the arithmetic; it is there because the reconstruction is
  what a future generator will actually run, and a reconstruction nobody
  exercises is a reconstruction nobody knows the revision set of.
- **Bounded.** The derived form must be smaller, and by how much is the
  deliverable. The residual is the override population: the casillas whose text
  really does differ between revisions, which no derivation may collapse.

The canonical text is the most common rendering across a casilla's revisions,
with the earliest-sorting text breaking a tie so the choice does not depend on
dictionary ordering. Where a casilla's revisions disagree two-against-two the
tie-break is arbitrary by nature, which is why the override set carries the
losers explicitly rather than relying on the choice being right.
"""

from __future__ import annotations

import collections
import sys
from dataclasses import dataclass

from .revision_label_restatement import casilla_labels

__all__ = [
    "DerivedLabels",
    "derive_labels",
    "derived_from",
    "expand_labels",
]


@dataclass(frozen=True, slots=True)
class DerivedLabels:
    """One locale's labels keyed by casilla, with per-revision overrides."""

    locale: str
    #: ``{modelo: {casilla: text}}`` - the one rendering that needs no override.
    canonical: dict[str, dict[str, str]]
    #: ``{modelo: {casilla: {revision: text}}}`` - only revisions that differ.
    overrides: dict[str, dict[str, dict[str, str]]]
    #: ``{modelo: {casilla: (revision, ...)}}`` - which revisions label the casilla.
    coverage: dict[str, dict[str, tuple[str, ...]]]

    @property
    def strings(self) -> int:
        """Return how many text strings the derived form stores."""
        canonical = sum(len(item) for item in self.canonical.values())
        overrides = sum(len(texts) for modelo in self.overrides.values() for texts in modelo.values())
        return canonical + overrides


def _canonical_text(texts: dict[str, str]) -> str:
    """Return the rendering that needs no override.

    Most common wins; the earliest-sorting text breaks a tie. The tie-break is
    arbitrary where a casilla's revisions disagree evenly, so it is made
    deterministic rather than left to whatever order the catalogue happened to
    be written in - a derivation whose output depends on file ordering cannot
    be checked by re-running it.
    """
    tally = collections.Counter(texts.values())
    best = max(tally.values())
    return min(text for text, count in tally.items() if count == best)


def derived_from(labels: dict[str, dict[str, dict[str, str]]], *, locale: str = "es") -> DerivedLabels:
    """Derive per-casilla labels from an already-read mapping.

    Separated from the corpus read so constructed input travels the same code
    path the catalogues do. A test that reimplemented the choice to check it
    would be checking its own copy.
    """
    canonical: dict[str, dict[str, str]] = {}
    overrides: dict[str, dict[str, dict[str, str]]] = {}
    coverage: dict[str, dict[str, tuple[str, ...]]] = {}
    for modelo, casillas in labels.items():
        for casilla, texts in casillas.items():
            chosen = _canonical_text(texts)
            canonical.setdefault(modelo, {})[casilla] = chosen
            coverage.setdefault(modelo, {})[casilla] = tuple(sorted(texts))
            differing = {revision: text for revision, text in texts.items() if text != chosen}
            if differing:
                overrides.setdefault(modelo, {})[casilla] = differing
    return DerivedLabels(locale=locale, canonical=canonical, overrides=overrides, coverage=coverage)


def derive_labels(locale: str) -> DerivedLabels:
    """Derive one locale's per-casilla labels from its shipped catalogues."""
    return derived_from(casilla_labels(locale), locale=locale)


def expand_labels(derived: DerivedLabels) -> dict[str, dict[str, dict[str, str]]]:
    """Rebuild the per-revision label mapping the derived form stands for.

    This is the reconstruction a generator would run, kept here so the round
    trip is exercised by the same code the collapse would depend on rather than
    by a reimplementation in a test.
    """
    rebuilt: dict[str, dict[str, dict[str, str]]] = {}
    for modelo, casillas in derived.canonical.items():
        for casilla, text in casillas.items():
            overrides = derived.overrides.get(modelo, {}).get(casilla, {})
            rebuilt.setdefault(modelo, {})[casilla] = {
                revision: overrides.get(revision, text) for revision in derived.coverage[modelo][casilla]
            }
    return rebuilt


def main() -> int:
    """Print the derivation's size and residual per locale; always exit 0."""
    from ._paths import LOCALES_DIR
    from .manager import discover_locale_codes

    stored = derived_total = 0
    for locale in sorted(discover_locale_codes(LOCALES_DIR)):
        current = casilla_labels(locale)
        held = sum(len(texts) for casillas in current.values() for texts in casillas.values())
        if not held:
            continue
        derived = derive_labels(locale)
        lossless = expand_labels(derived) == current
        override_casillas = sum(len(modelo) for modelo in derived.overrides.values())
        stored += held
        derived_total += derived.strings
        sys.stdout.write(
            f"derivation locale={locale} stored={held} derived={derived.strings} "
            f"removed={held - derived.strings} override_casillas={override_casillas} "
            f"lossless={str(lossless).lower()}\n"
        )
    sys.stdout.write(f"summary stored={stored} derived={derived_total} removed={stored - derived_total}\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

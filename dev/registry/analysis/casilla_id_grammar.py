"""Screen: which casilla identifier grammars a modelo uses, and which modelos mix them.

A casilla identifier is the name every other declaration reaches the casilla by:
formulas target it, bindings resolve to it, export fields address it, continuity
records assert identity across revisions with it. Nothing constrains its shape.
Five shapes are in use across the corpus and no declaration says which one a
modelo has chosen, so a modelo can use several at once and the registry
validates.

The grammars are named from what the corpus actually contains, not from a
specification, because none exists:

- ``numeric`` - digits only, the official casilla number as printed
  (``109``, ``0001``);
- ``dotted`` - a dotted domain path (``iva.cuota-deducible-total``);
- ``kebab`` - hyphenated segments with no dot, whose first segment may be
  numeric (``declarante-nif``, ``490-01-tipo-declaracion-13``);
- ``token`` - a bare alphanumeric token, typically an official dictionary key
  (``TIPOTRIBUTACION``, ``A``);
- ``page_qualified`` - a page or block reference joined by a colon to a tail
  that is itself one of the grammars above (``DP200013:00417``,
  ``DP200014:bin-aplicada-maxima``).

Anything matching none of these is reported as ``unclassified`` rather than
forced into the nearest grammar: an unrecognised shape is a finding, and
quietly widening a grammar to swallow it would hide exactly what this screen
exists to surface.

Mixing is reported per modelo rather than per revision. A modelo that changes
grammar between revisions has a continuity problem as well as a naming one,
and collapsing to the revision would hide it.

The screen exits 0 whatever it finds. It reports; it does not gate. A gate
belongs here once a modelo can declare the grammar it has chosen.
"""

from __future__ import annotations

import collections
import re
import sys
from dataclasses import dataclass

from cadrumo.domain.calculations.registry.authority import ValidatedRegistryAuthority, bundled_authority

from .corpus import bundled_modelo_ids

__all__ = [
    "GRAMMARS",
    "ModeloGrammarUse",
    "classify_casilla_id",
    "screen_authority",
]

GRAMMARS: tuple[str, ...] = ("numeric", "dotted", "kebab", "token", "page_qualified")

_NUMERIC = re.compile(r"\d+")
_DOTTED = re.compile(r"[A-Za-z0-9_-]+(?:\.[A-Za-z0-9_-]+)+")
_KEBAB = re.compile(r"[A-Za-z0-9][A-Za-z0-9_]*(?:-[A-Za-z0-9_]+)+")
_TOKEN = re.compile(r"[A-Za-z][A-Za-z0-9_]*")
_PAGE_HEAD = re.compile(r"[A-Za-z0-9]+")


def classify_casilla_id(casilla_id: str) -> str:
    """Return the grammar name for one identifier, or ``unclassified``.

    ``page_qualified`` is decided first on the colon, then its tail is
    classified by the same rules as an unqualified identifier: a colon form
    whose tail is unclassifiable is itself unclassified, so widening the head
    can never quietly absorb an unrecognised tail.
    """
    head, separator, tail = casilla_id.partition(":")
    if separator:
        if _PAGE_HEAD.fullmatch(head) and _classify_unqualified(tail) != "unclassified":
            return "page_qualified"
        return "unclassified"
    return _classify_unqualified(casilla_id)


def _classify_unqualified(casilla_id: str) -> str:
    """Classify an identifier carrying no page qualifier."""
    if _NUMERIC.fullmatch(casilla_id):
        return "numeric"
    if _DOTTED.fullmatch(casilla_id):
        return "dotted"
    if _KEBAB.fullmatch(casilla_id):
        return "kebab"
    if _TOKEN.fullmatch(casilla_id):
        return "token"
    return "unclassified"


@dataclass(frozen=True, slots=True)
class ModeloGrammarUse:
    """One modelo's identifier-grammar usage across every revision it declares."""

    modelo: str
    counts: tuple[tuple[str, int], ...]

    @property
    def grammars_used(self) -> tuple[str, ...]:
        """Every grammar this modelo uses, most-used first."""
        return tuple(name for name, _ in self.counts)

    @property
    def mixes(self) -> bool:
        """Whether this modelo uses more than one grammar."""
        return len(self.counts) > 1


def screen_authority(
    authority: ValidatedRegistryAuthority, modelo_ids: tuple[str, ...]
) -> tuple[ModeloGrammarUse, ...]:
    """Return each modelo's grammar usage, ordered by modelo id."""
    uses: list[ModeloGrammarUse] = []
    for modelo_id in modelo_ids:
        definition = authority.modelo(modelo_id)
        tally: collections.Counter[str] = collections.Counter()
        for revision in definition.revisions.values():
            for casilla in revision.casillas:
                tally[classify_casilla_id(str(casilla.id))] += 1
        ordered = tuple(sorted(tally.items(), key=lambda entry: (-entry[1], entry[0])))
        uses.append(ModeloGrammarUse(modelo=modelo_id, counts=ordered))
    return tuple(uses)


def main() -> int:
    """Print one row per modelo, then a corpus-wide census; always exit 0."""
    authority = bundled_authority()
    uses = screen_authority(authority, bundled_modelo_ids())
    corpus: collections.Counter[str] = collections.Counter()
    mixing = 0
    for use in uses:
        corpus.update(dict(use.counts))
        if use.mixes:
            mixing += 1
            detail = " ".join(f"{name}={count}" for name, count in use.counts)
            sys.stdout.write(f"grammar_mixed modelo={use.modelo} grammars={len(use.counts)} {detail}\n")
    for use in uses:
        if not use.mixes and use.counts:
            sys.stdout.write(
                f"grammar_single modelo={use.modelo} grammar={use.counts[0][0]} casillas={use.counts[0][1]}\n"
            )
    census = " ".join(f"{name}={count}" for name, count in sorted(corpus.items(), key=lambda e: (-e[1], e[0])))
    sys.stdout.write(f"summary modelos={len(uses)} mixing={mixing} casillas={sum(corpus.values())} {census}\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

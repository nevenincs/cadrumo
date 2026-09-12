"""Read the signed dispositions that classify a promised filing coordinate as legitimately unserved.

:mod:`edition_delta_status` projects every modelo's declared reach against the
registry's ``supported_filing_years`` promise and reports three coverage
conditions. Its own docstring says why it carries no suppression: classifying a
gap as legitimate "is a judgement that belongs in a declaration a reviewer
signs, not in a screen's heuristic". This module is that declaration's reader.

A gap can be legitimate. The product may promise a filing year corpus-wide while
AEAT published no design for a particular modelo that year, and no amount of
migration work will close it. What a screen cannot do is decide which gaps those
are. So the classification is authored, one coordinate at a time, with the
authority that settles it, and everything not classified stays outstanding.

The shape is deliberately narrow:

- A disposition names exactly one ``(modelo, filing_year, period)`` coordinate.
  ``period`` may be ``*``, which is the period the screen itself reports for a
  whole unserved year, and never a pattern of any other kind. A prefix, a
  modelo-wide exemption or a count-based allowance would let one entry cover
  gaps nobody read, which is the failure mode ``no-silent-under-declaration``
  names.
- It names the ``kind`` it disposes of, so an entry written for an unserved year
  cannot silently absorb the opposite failure -- a coordinate served twice --
  should the corpus change underneath it.
- It names a ``classification``, and the two are not interchangeable:

  ``inception``
      The modelo did not legally exist in that filing year. The gap is
      permanent, no authoring will ever close it, and the coordinate leaves the
      outstanding count. The authority is the instrument that created the
      modelo.
  ``unauthored``
      The modelo existed and nobody authored its revision for that year. The
      gap is real debt. The coordinate is classified -- somebody has read it and
      said what it is -- but it STAYS outstanding, because saying what a gap is
      does not close it.

  These two refuse identically in the corpus today and mean opposite things.
  Collapsing them into one "not applicable" would destroy the only signal that
  says which cells are debt, which is exactly the silent under-declaration this
  file exists to prevent. A coordinate whose research came back uncertain gets
  NO entry: an unclassified gap is an honest statement that nobody knows yet,
  and is more useful than a confident guess.
- It carries a ``reason`` and an ``authority``. The authority is the official
  source that settles the question; a disposition without one is an opinion.

Reading refuses a malformed entry, an unknown kind, an unknown classification,
or a coordinate named twice, rather than letting any of them quietly widen the
exempt set.
"""

from __future__ import annotations

import tomllib
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Final

__all__ = [
    "CLASSIFICATIONS",
    "DISPOSITIONS_PATH",
    "CoverageCoordinate",
    "CoverageDisposition",
    "load_coverage_dispositions",
]

DISPOSITIONS_PATH: Final = Path(__file__).with_name("coverage_dispositions.toml")

_REQUIRED: Final = ("modelo", "period", "kind", "classification", "reason", "authority")

#: The conditions a disposition may classify. Kept as a literal set rather than
#: imported from the screen, so a condition renamed there fails loudly here
#: instead of silently accepting an entry that now disposes of nothing.
_KINDS: Final = frozenset({"promised_year_unserved", "promised_coordinate_unserved", "coordinate_served_twice"})

#: What a classified coordinate IS. ``inception`` is terminal and closes the
#: coordinate; ``unauthored`` names it as debt and leaves it outstanding. There
#: is deliberately no third value for "unsure": that case is written by not
#: writing an entry.
CLASSIFICATIONS: Final = frozenset({"inception", "unauthored"})

#: The classifications that close a coordinate rather than describing it. Only
#: `inception` qualifies, because only a modelo that never existed in a year has
#: a gap no authoring can close.
_TERMINAL: Final = frozenset({"inception"})

#: One coordinate: modelo, filing year, and period token. ``*`` is the period a
#: whole-year gap carries, matching what the screen reports.
type CoverageCoordinate = tuple[str, int, str]


@dataclass(frozen=True, slots=True)
class CoverageDisposition:
    """One signed classification of a promised coordinate the corpus does not serve."""

    coordinate: CoverageCoordinate
    kind: str
    classification: str
    reason: str
    authority: str

    @property
    def closes(self) -> bool:
        """Whether this classification closes the coordinate or merely names it.

        An ``inception`` gap is closed: the modelo did not exist, and no work
        will ever serve that year. An ``unauthored`` gap is named and still
        owed. A screen that treated the two alike would report the corpus's own
        authoring debt as resolved.
        """
        return self.classification in _TERMINAL


def load_coverage_dispositions(path: Path = DISPOSITIONS_PATH) -> Mapping[CoverageCoordinate, CoverageDisposition]:
    """Load every ``[[disposition]]`` keyed by the coordinate it classifies.

    An absent file is an empty declaration, not an error: a corpus whose
    coverage has never been adjudicated has disposed of nothing, and that is the
    honest reading of it.
    """
    dispositions: dict[CoverageCoordinate, CoverageDisposition] = {}
    if not path.is_file():
        return dispositions
    document = tomllib.loads(path.read_text(encoding="utf-8"))
    for index, entry in enumerate(document.get("disposition", ())):
        blank = [name for name in _REQUIRED if not isinstance(entry.get(name), str) or not entry[name].strip()]
        if blank:
            raise ValueError(f"{path.name}: disposition #{index} has no {', '.join(blank)}")
        year = entry.get("filing_year")
        if not isinstance(year, int):
            raise ValueError(f"{path.name}: disposition #{index} has no integer filing_year")
        modelo, period, kind, classification, reason, authority = (str(entry[name]) for name in _REQUIRED)
        if kind not in _KINDS:
            raise ValueError(f"{path.name}: disposition #{index} names unknown kind {kind!r}")
        if classification not in CLASSIFICATIONS:
            raise ValueError(
                f"{path.name}: disposition #{index} names unknown classification {classification!r}; "
                f"expected one of {', '.join(sorted(CLASSIFICATIONS))}, or no entry at all when unsure"
            )
        coordinate: CoverageCoordinate = (modelo, year, period)
        if coordinate in dispositions:
            raise ValueError(f"{path.name}: disposition #{index} names {coordinate} a second time")
        dispositions[coordinate] = CoverageDisposition(
            coordinate=coordinate,
            kind=kind,
            classification=classification,
            reason=reason,
            authority=authority,
        )
    return dispositions

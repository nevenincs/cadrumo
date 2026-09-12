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
- It carries a ``reason`` and an ``authority``. The authority is the official
  source that settles the question; a disposition without one is an opinion.

Reading refuses a malformed entry, an unknown kind, or a coordinate named twice,
rather than letting any of them quietly widen the exempt set.
"""

from __future__ import annotations

import tomllib
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Final

__all__ = [
    "DISPOSITIONS_PATH",
    "CoverageCoordinate",
    "CoverageDisposition",
    "load_coverage_dispositions",
]

DISPOSITIONS_PATH: Final = Path(__file__).with_name("coverage_dispositions.toml")

_REQUIRED: Final = ("modelo", "period", "kind", "reason", "authority")

#: The conditions a disposition may classify. Kept as a literal set rather than
#: imported from the screen, so a condition renamed there fails loudly here
#: instead of silently accepting an entry that now disposes of nothing.
_KINDS: Final = frozenset({"promised_year_unserved", "promised_coordinate_unserved", "coordinate_served_twice"})

#: One coordinate: modelo, filing year, and period token. ``*`` is the period a
#: whole-year gap carries, matching what the screen reports.
type CoverageCoordinate = tuple[str, int, str]


@dataclass(frozen=True, slots=True)
class CoverageDisposition:
    """One signed classification of a promised coordinate the corpus does not serve."""

    coordinate: CoverageCoordinate
    kind: str
    reason: str
    authority: str


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
        modelo, period, kind, reason, authority = (str(entry[name]) for name in _REQUIRED)
        if kind not in _KINDS:
            raise ValueError(f"{path.name}: disposition #{index} names unknown kind {kind!r}")
        coordinate: CoverageCoordinate = (modelo, year, period)
        if coordinate in dispositions:
            raise ValueError(f"{path.name}: disposition #{index} names {coordinate} a second time")
        dispositions[coordinate] = CoverageDisposition(
            coordinate=coordinate, kind=kind, reason=reason, authority=authority
        )
    return dispositions

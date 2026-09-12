"""Retire coverage dispositions whose coordinate the corpus now serves.

A disposition is a signed statement that a promised filing coordinate is NOT
served and why. Authoring the edition that serves it does not retract the
signature: the entry stays, now asserting something false, sitting beside the
edition that contradicts it. Nothing links the two, so the falsehood survives
exactly as long as nobody re-reads the file.

That is not hypothetical. Modelo 036's 2023 and 2024 entries still read
``promised_year_unserved / unauthored`` an hour after the edition serving both
was written, and they were found only because someone went looking for the 2022
entry and read its neighbours.

A retired entry is DELETED rather than reclassified. There is no "was unserved"
state to record: the coordinate is served, the file's whole subject is
coordinates that are not, and a disposition kept for history would be read as a
live claim by the next reader and by the screen.

Held coordinates are never touched. A coordinate under an open question may be
about to be re-signed differently, and retiring it would delete a judgement
someone is still making.
"""

from __future__ import annotations

import argparse
import hashlib
import sys
import tomllib
from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path

from dev.registry.compiler.loader import load_modelo_directory

_ROOT = Path(__file__).resolve().parents[3]
DISPOSITIONS = _ROOT / "dev/registry/analysis/coverage_dispositions.toml"
MODELOS = _ROOT / "src/cadrumo/_data/registry/aeat/modelos"


@dataclass(frozen=True)
class Coordinate:
    """One promised filing coordinate a disposition speaks about."""

    modelo: str
    filing_year: int
    period: str

    def __str__(self) -> str:
        return f"{self.modelo}/{self.filing_year}" + ("" if self.period == "*" else f" {self.period}")


def served_coordinates(modelo: str) -> set[tuple[int, str]] | None:
    """Every (year, period) the modelo's loaded editions admit, or None if it cannot load."""
    directory = MODELOS / modelo
    if not directory.is_dir():
        return None
    try:
        definition = load_modelo_directory(directory)
    except Exception:
        # A modelo that cannot load proves nothing about what it serves, and a
        # disposition must never be retired on the strength of a failed read.
        return None
    served: set[tuple[int, str]] = set()
    for revision in definition.revisions.values():
        selector = revision.period_selector
        years = set(selector.years)
        if selector.year_from is not None:
            upper = selector.year_to if selector.year_to is not None else selector.year_from
            years |= set(range(selector.year_from, upper + 1))
        for year in years:
            for period in selector.periods:
                served.add((year, str(period)))
    return served


def is_served(coordinate: Coordinate, served: set[tuple[int, str]] | None) -> bool:
    """Whether the corpus serves this coordinate.

    ``period = "*"`` disposes of a whole year, so ANY period served in that year
    retires it. A named period must be served exactly.
    """
    if served is None:
        return False
    if coordinate.period == "*":
        return any(year == coordinate.filing_year for year, _ in served)
    return (coordinate.filing_year, coordinate.period) in served


def main(argv: Iterable[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--apply", action="store_true", help="write; otherwise dry-run")
    parser.add_argument(
        "--hold",
        default="",
        help="comma-separated modelo/year coordinates to leave alone, e.g. 303/2022,303/2026",
    )
    arguments = parser.parse_args(list(argv) if argv is not None else None)
    held = {item.strip() for item in arguments.hold.split(",") if item.strip()}

    raw = DISPOSITIONS.read_bytes()
    entries = tomllib.loads(raw.decode("utf-8"))["disposition"]
    by_modelo: dict[str, set[tuple[int, str]] | None] = {}

    retire: list[Coordinate] = []
    kept_held: list[Coordinate] = []
    for entry in entries:
        coordinate = Coordinate(str(entry["modelo"]), int(entry["filing_year"]), str(entry["period"]))
        if coordinate.modelo not in by_modelo:
            by_modelo[coordinate.modelo] = served_coordinates(coordinate.modelo)
        if not is_served(coordinate, by_modelo[coordinate.modelo]):
            continue
        if f"{coordinate.modelo}/{coordinate.filing_year}" in held:
            kept_held.append(coordinate)
            continue
        retire.append(coordinate)

    print(f"dispositions: {len(entries)} | served: {len(retire) + len(kept_held)} | "
          f"retiring: {len(retire)} | held: {len(kept_held)}")
    for coordinate in retire:
        print(f"  RETIRE {coordinate}")
    for coordinate in kept_held:
        print(f"  HOLD   {coordinate}  (under an open question; may be re-signed)")
    if not arguments.apply or not retire:
        return 0

    text = raw.decode("utf-8")
    newline = (chr(13) + chr(10)) if (chr(13) + chr(10)).encode() in raw else chr(10)
    lines = text.split(newline)

    # Line-wise rather than split-on-marker: a chunk produced by splitting can be
    # a header comment with no keys at all, and re-parsing it raises. An entry
    # runs from its [[disposition]] line to just before the next one, and
    # anything that will not parse or names no modelo is KEPT untouched -- a
    # retirement must never rest on a chunk this code failed to understand.
    doomed = {(c.modelo, c.filing_year, c.period) for c in retire}
    kept: list[str] = []
    index = 0
    while index < len(lines):
        if lines[index].strip() != "[[disposition]]":
            kept.append(lines[index])
            index += 1
            continue
        stop = index + 1
        while stop < len(lines) and lines[stop].strip() != "[[disposition]]":
            stop += 1
        chunk = lines[index:stop]
        try:
            parsed = tomllib.loads(newline.join(chunk))["disposition"][0]
            key = (str(parsed["modelo"]), int(parsed["filing_year"]), str(parsed["period"]))
        except Exception:
            kept.extend(chunk)
            index = stop
            continue
        if key not in doomed:
            kept.extend(chunk)
        index = stop
    body = newline.join(kept)

    pre = hashlib.sha256(raw).hexdigest()
    DISPOSITIONS.write_bytes(body.encode("utf-8"))
    back = DISPOSITIONS.read_bytes()
    if b"\r\r\n" in back:
        raise SystemExit("REFUSE: the write double-translated line endings")
    if (b"\r\n" in back) != (b"\r\n" in raw):
        raise SystemExit("REFUSE: the write changed the file's line-ending style")
    remaining = tomllib.loads(back.decode("utf-8"))["disposition"]
    if len(remaining) != len(entries) - len(retire):
        raise SystemExit(
            f"REFUSE: expected {len(entries) - len(retire)} entries after the write, found {len(remaining)}"
        )
    print(f"\nwrote {DISPOSITIONS.relative_to(_ROOT).as_posix()}: "
          f"{len(entries)} -> {len(remaining)} entries")
    print(f"  sha256 {pre[:16]}... -> {hashlib.sha256(back).hexdigest()[:16]}...")
    return 0


if __name__ == "__main__":
    sys.exit(main())

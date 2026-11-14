"""The returns whose CLI result does not match the table, as the keys file a rerun sweep drives.

    python -m dev.acceptance.persona_table.cli_column.unmatched --rows <rows-<sha>.jsonl> --frontend <dir> \
        --out keys.json [--split 2]

The outcome of each table row on the CLI is the frontend comparison's own (``frontend.compare_frontend``), so this
module compares nothing: a row is listed when its CLI parity is anything but ``matched``, which includes a row with no
CLI line (not run), a persona whose profile did not load, a row whose line states a workaround or an inherited
calculation, and a row that differs. A row with nothing to compare (``not-comparable``) is left out, because driving
it again cannot change that, unless ``--include-not-comparable`` is given. Each key carries the horizon of its table
row. ``--split N`` also writes the keys as N files (``<out stem>.part<i>.json``) with whole personas in each,
balanced by key count.
"""

from __future__ import annotations

import argparse
import sys
from collections import Counter
from collections.abc import Iterable, Mapping, Sequence
from pathlib import Path

from ..frontend import MATCHED, NOT_COMPARABLE, FrontendResultError, compare_frontend, read_results
from ..planner import registry_envelope
from ..rows import TableRow, latest_rows, read_rows
from .keys import RerunKey, write_keys

SURFACE = "cli"


def unmatched_keys(
    rows: Iterable[TableRow], results_directory: Path, *, include_not_comparable: bool = False
) -> list[tuple[RerunKey, str]]:
    """Each table row whose CLI parity is not ``matched``, as a key and its outcome, in the comparison's key order."""
    held = list(rows)
    horizons = {row.key: row.horizon for row in held}
    comparison = compare_frontend(held, read_results(results_directory))
    kept = {MATCHED} | (set() if include_not_comparable else {NOT_COMPARABLE})
    return [
        (RerunKey(*item.key, horizon=horizons[item.key]), item.outcome)
        for item in comparison.parities[SURFACE]
        if item.outcome not in kept
    ]


def counts_by_persona(found: Iterable[tuple[RerunKey, str]]) -> dict[str, Counter[str]]:
    """Per persona, how many keys stand at each outcome."""
    counts: dict[str, Counter[str]] = {}
    for key, outcome in found:
        counts.setdefault(key.persona, Counter())[outcome] += 1
    return counts


def split_personas(keys: Sequence[RerunKey], parts: int) -> list[list[RerunKey]]:
    """``keys`` in ``parts`` lists holding whole personas, each persona in the list with the fewest keys so far."""
    held: dict[str, list[RerunKey]] = {}
    for key in keys:
        held.setdefault(key.persona, []).append(key)
    groups: list[list[RerunKey]] = [[] for _ in range(parts)]
    for persona in sorted(held, key=lambda name: (-len(held[name]), name)):
        min(groups, key=len).extend(held[persona])
    return groups


def count_lines(counts: Mapping[str, Counter[str]]) -> list[str]:
    """One line per persona, most keys first, then the total."""
    ordered = sorted(counts, key=lambda name: (-sum(counts[name].values()), name))
    lines = [
        f"{persona}: {sum(counts[persona].values())} "
        f"({', '.join(f'{word} {number}' for word, number in sorted(counts[persona].items()))})"
        for persona in ordered
    ]
    return [*lines, f"total: {sum(sum(counter.values()) for counter in counts.values())}"]


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python -m dev.acceptance.persona_table.cli_column.unmatched", description=__doc__
    )
    parser.add_argument("--rows", required=True, type=Path, help="a rows-<sha>.jsonl file of the table")
    parser.add_argument("--frontend", required=True, type=Path, help="the directory of frontend result files")
    parser.add_argument("--out", required=True, type=Path, help="the keys file to write")
    parser.add_argument("--split", type=int, default=1, help="also write the keys as this many files of whole personas")
    parser.add_argument("--include-not-comparable", action="store_true", help="also list rows with nothing to compare")
    return parser


def _write_parts(out: Path, keys: Sequence[RerunKey], parts: int) -> list[Path]:
    written: list[Path] = []
    for index, group in enumerate(split_personas(keys, parts), start=1):
        path = out.with_name(f"{out.stem}.part{index}{out.suffix}")
        write_keys(path, group)
        written.append(path)
    return written


def main(argv: Sequence[str] | None = None) -> int:
    """Write the keys file and print the per-persona counts; the exit code is 2 for a refused input."""
    args = _parser().parse_args(argv)
    try:
        rows = latest_rows(read_rows([args.rows], horizon=registry_envelope().horizon))
        found = unmatched_keys(rows.values(), args.frontend, include_not_comparable=args.include_not_comparable)
    except (FrontendResultError, OSError, ValueError) as refusal:
        sys.stderr.write(f"unmatched keys not computed: {refusal}\n")
        return 2
    keys = [key for key, _ in found]
    write_keys(args.out, keys)
    paths = _write_parts(args.out, keys, args.split) if args.split > 1 else []
    for line in [*count_lines(counts_by_persona(found)), *(f"wrote {path}" for path in paths)]:
        sys.stdout.write(line + "\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())

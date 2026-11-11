"""Run, render, compare and ratchet the persona table.

Run the whole table, or a lane's rows only, and render it::

    python -m dev.acceptance.persona_table run --tree <sha> --out .tmp/table/rows.jsonl
    python -m dev.acceptance.persona_table run --tree <sha> --modelo 130 --out .tmp/table/130.jsonl
    python -m dev.acceptance.persona_table render .tmp/table/rows.jsonl --head <sha> --out .tmp/table/TABLE.md

Compare against the committed baseline, and regenerate it after a new head::

    python -m dev.acceptance.persona_table check .tmp/table/rows.jsonl
    python -m dev.acceptance.persona_table diff dev/acceptance/persona_table/baseline .tmp/table/rows.jsonl
    python -m dev.acceptance.persona_table baseline .tmp/table/rows.jsonl

``run`` needs a private ``CADRUMO_AUTHORITY_ROOT``. Before the first row it publishes
the authority of this tree when stale, proves the published generation records this
tree's legal sources, and exits 2 otherwise. ``--tree`` is the commit of the tree under
test (the tool never runs git); with the generation and database digest it is written
to ``<out>.meta.json``, which ``render`` prints in the table header (``--meta`` names
another sidecar). ``run`` appends to ``--out``; a filtered run writes only its rows. ``check``
exits 1 when a row the baseline holds green is not green in the rows given.
"""

from __future__ import annotations

import argparse
import os
import sys
import tomllib
from collections.abc import Sequence
from functools import cache
from pathlib import Path

import pytest

from cadrumo.domain.calculations.registry.authority import bundled_indexed_authority
from cadrumo.entrypoints.tests.persona_materialisation import year_envelope
from cadrumo.tests.personas import YearEnvelope

from .diff import diff_tables, render_diff, row_id
from .provenance import ProvenanceError, meta_path, prepare_authority, read_meta, write_meta
from .render import render_table, summary_line
from .rows import GREEN, TableRow, latest_rows, read_rows, with_unchecked

BASELINE = Path(__file__).with_name("baseline")
_SWEEP = Path(__file__).with_name("sweep.py")


@cache
def _envelope() -> YearEnvelope:
    with bundled_indexed_authority().operation() as operation:
        return year_envelope(operation)


def _horizon() -> int:
    """The registry's horizon, on which the baseline's year tokens resolve."""
    return _envelope().horizon


def _rows_from(paths: Sequence[Path]) -> dict[tuple[str, str, int, str], TableRow]:
    """The latest row per key in the run files, or the baseline directories, at ``paths``."""
    files: list[Path] = []
    for path in paths:
        files += sorted(path.glob("*.jsonl")) if path.is_dir() else [path]
    latest = latest_rows(read_rows(files, horizon=_horizon()))
    return {row.key: row for row in with_unchecked(latest.values(), _envelope())}


def _run(args: argparse.Namespace) -> int:
    out = args.out.resolve()
    try:
        provenance = prepare_authority(os.environ, tree=args.tree)
    except ProvenanceError as refusal:
        sys.stderr.write(f"persona table not run: {refusal}\n")
        return 2
    write_meta(out, provenance)
    environment = dict(os.environ)
    environment |= {
        "PERSONA_TABLE_OUT": str(out),
        "PERSONA_TABLE_PERSONAS": ",".join(args.persona),
        "PERSONA_TABLE_MODELOS": ",".join(args.modelo),
        "PERSONA_TABLE_YEARS": ",".join(str(year) for year in args.year),
    }
    os.environ.update(environment)
    command = [
        str(_SWEEP),
        "-m",
        "integration",
        "-n",
        str(args.workers),
        "--dist=load",
        "-q",
        "-p",
        "no:cacheprovider",
    ]
    return int(pytest.main(command))


def _render(args: argparse.Namespace) -> int:
    rows = _rows_from(args.rows)
    lanes = tomllib.loads(args.lanes.read_text(encoding="utf-8")) if args.lanes else None
    lane_of = {str(modelo): lane for lane, modelos in (lanes or {}).items() for modelo in modelos}
    meta = read_meta(args.meta or meta_path(args.rows[0]))
    text = render_table(rows.values(), head=args.head, lanes=lane_of or None, provenance=meta)
    if args.out is None:
        sys.stdout.write(text)
    else:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(text, encoding="utf-8")
        sys.stderr.write(summary_line(list(rows.values())) + "\n")
    return 0


def _baseline(args: argparse.Namespace) -> int:
    rows = _rows_from(args.rows)
    args.dir.mkdir(parents=True, exist_ok=True)
    by_persona: dict[str, list[TableRow]] = {}
    for key in sorted(rows):
        by_persona.setdefault(key[0], []).append(rows[key])
    for persona, persona_rows in by_persona.items():
        text = "".join(row.to_baseline_json(_horizon()) + "\n" for row in persona_rows)
        (args.dir / f"{persona}.jsonl").write_text(text, encoding="utf-8", newline="\n")
    return 0


def _diff(args: argparse.Namespace) -> int:
    before, after = _rows_from([args.before]), _rows_from([args.after])
    text = render_diff(diff_tables(before, after), before=args.before_label, after=args.after_label)
    sys.stdout.write(text)
    return 0


def _check(args: argparse.Namespace) -> int:
    baseline, current = _rows_from([args.baseline]), _rows_from(args.rows)
    lost = [
        key
        for key, row in baseline.items()
        if row.verdict in GREEN and key in current and current[key].verdict not in GREEN
    ]
    for key in lost:
        sys.stderr.write(f"regressed: {row_id(key)} ({current[key].verdict.value}: {current[key].reason[:200]})\n")
    return 1 if lost else 0


def main(argv: Sequence[str] | None = None) -> int:
    """Parse the command line and run one command."""
    parser = argparse.ArgumentParser(prog="python -m dev.acceptance.persona_table", description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)

    run = commands.add_parser("run", help="replay the personas and append one JSON row per return")
    run.add_argument("--out", type=Path, required=True)
    run.add_argument("--tree", required=True, help="commit SHA of the tree under test")
    run.add_argument("--persona", action="append", default=[])
    run.add_argument("--modelo", action="append", default=[])
    run.add_argument("--year", action="append", type=int, default=[])
    run.add_argument("--workers", default="auto")
    run.set_defaults(handler=_run)

    render = commands.add_parser("render", help="render rows as a Markdown table")
    render.add_argument("rows", type=Path, nargs="+")
    render.add_argument("--head", required=True)
    render.add_argument("--out", type=Path)
    render.add_argument("--meta", type=Path, help="run provenance sidecar; defaults to the first rows file's")
    render.add_argument("--lanes", type=Path, help="TOML mapping each lane to its modelo codes")
    render.set_defaults(handler=_render)

    baseline = commands.add_parser("baseline", help="write the rows as the committed baseline, one file per persona")
    baseline.add_argument("rows", type=Path, nargs="+")
    baseline.add_argument("--dir", type=Path, default=BASELINE)
    baseline.set_defaults(handler=_baseline)

    diff = commands.add_parser("diff", help="compare two row sets (files or directories)")
    diff.add_argument("before", type=Path)
    diff.add_argument("after", type=Path)
    diff.add_argument("--before-label", default="before")
    diff.add_argument("--after-label", default="after")
    diff.set_defaults(handler=_diff)

    check = commands.add_parser("check", help="exit 1 when a baseline-green row is not green")
    check.add_argument("rows", type=Path, nargs="+")
    check.add_argument("--baseline", type=Path, default=BASELINE)
    check.set_defaults(handler=_check)

    args = parser.parse_args(argv)
    return int(args.handler(args))


if __name__ == "__main__":
    raise SystemExit(main())

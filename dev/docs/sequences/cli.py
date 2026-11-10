"""``python -m dev.docs.sequences`` — the golden refresh and check CLI.

Three modes over one engine:

- ``refresh [--page PAGE ... | --sequence ID | --command CMD] [--jobs N]``
  re-executes the addressed sequences in fresh hermetic sandboxes and rewrites
  their committed golden files. Unscoped, or over several pages, it shards the
  pages across ``--jobs`` child interpreters (heaviest first); the goldens do
  not depend on the schedule. ``--command 'app ledger classify'`` addresses
  every page that executes that command. The author reviews the git diff — which IS the behaviour-change
  review — and commits the goldens with the CLI change that legitimately
  moved them. This is the ONLY sanctioned way a golden changes.
- ``check [--page PAGE | --sequence ID]`` re-executes the addressed sequences
  and compares against the committed goldens, failing (exit 1) with every
  divergence: the page, the sequence id, the frame index and argv, the
  post-mask differing paths or unified text diff, and the exact ``refresh``
  invocation that updates the golden.
- ``seeds [--check]`` renders the generated frames of each persona-derived
  seed recipe, and the sandbox persona's statement fixture, from the catalogue
  personas they declare; ``--check`` fails on drift without writing
  (:mod:`dev.docs.sequences.seed_generator`). The unscoped ``check`` mode
  includes the same drift check.

Every mode that executes a sequence first confirms the registry authority the
runner reads is current, and exits 1 naming the republish command when it is
not (:mod:`dev.docs.sequences.authority_currency`).

Both the Sphinx ``builder-inited`` hook and the ``dev/docs/tests`` pytest gate
call the same :func:`check_sequences` engine function this module's
``check`` mode wraps, so neither surface re-implements execution or
comparison (the pull==calculate discipline).

Sequence discovery reads the enrolled docs pages and their private contracts:
a page enrolls by carrying at least one *backtick*-fenced ``cli-sequence`` MyST
directive (the backtick fence form, never the colon form). The public directive
contains only its id and reader-facing ``:verify:`` sentence; this module reads
the frame grammar from
``docs/_sequences/contracts/<page>/<sequence-id>.seq`` and parses it through the
shared grammar parser. A sequence whose author binds
a ``@capture`` no later frame consumes is reported as a named advisory (never
a failure): the capture still records into the transcript and golden, so it is
review-visible, but the advisory keeps dead bindings from accumulating. A
reader-facing frame whose recorded output exceeds
:data:`~dev.docs.sequences.checks.READER_FRAME_OUTPUT_ADVISORY_BYTES` is
reported the same way, by both modes.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from .checks import (
    ADVISORY_PREFIX,
    PROBLEM_PREFIX,
    REFRESHED_PREFIX,
    build_argument_parser,
    check_page_coherence,
    check_page_coherence_in_subprocess,
    check_sequences,
    check_sequences_in_subprocess,
    checks_owning_page,
    discover_sequences,
    pages_running_command,
    refresh_pages,
    refresh_sequences,
)
from .errors import SequenceEngineError
from .golden_store import (
    refresh_invocation,
)
from .seed_generator import check_seeds, write_seeds


def main(argv: list[str] | None = None) -> int:
    """CLI entry: exit 0 on a clean run, 1 on any problem, 2 on usage errors."""
    parser = build_argument_parser()
    args = parser.parse_args(argv)

    if args.mode == "refresh":
        return _refresh_mode(args)

    if args.mode == "seeds":
        return _seeds_mode(args)

    if args.coherence:
        return _coherence_mode(args)

    try:
        if args.timeout is None:
            problems, advisories = check_sequences(
                docs_root=args.docs_root,
                goldens_root=args.goldens_root,
                page=args.page,
                sequence_id=args.sequence,
            )
        else:
            problems = check_sequences_in_subprocess(
                docs_root=args.docs_root,
                goldens_root=args.goldens_root,
                page=args.page,
                sequence_id=args.sequence,
                timeout=args.timeout,
            )
            advisories = ()
    except SequenceEngineError as exc:
        print(f"FAIL: {exc}", file=sys.stderr)
        return 1
    for advisory in advisories:
        print(f"advisory: {advisory}")
    if problems:
        for problem in problems:
            print(f"FAIL: {problem}", file=sys.stderr)
        print(
            f"{len(problems)} divergence(s). If the new behaviour is intended, update the "
            f"golden(s) with: {refresh_invocation(page=args.page, sequence_id=args.sequence)}",
            file=sys.stderr,
        )
        return 1
    print("cli-sequence goldens: clean")
    if args.sequence is not None:
        _single_sequence_advisory(args)
    return 0


def _refresh_mode(args: argparse.Namespace) -> int:
    """Refresh mode."""
    try:
        if args.sequence is not None:
            written, problems, advisories = refresh_sequences(
                docs_root=args.docs_root,
                goldens_root=args.goldens_root,
                sequence_id=args.sequence,
            )
        else:
            pages = _refresh_pages(args.page, args.command, args.docs_root)
            if pages is not None and not pages:
                print(f"no executed frame runs {args.command!r}; nothing to refresh")
                return 0
            written, problems, advisories = refresh_pages(
                docs_root=args.docs_root,
                goldens_root=args.goldens_root,
                pages=pages,
                jobs=args.jobs,
                progress=lambda line: print(line, flush=True),
            )
    except SequenceEngineError as exc:
        print(f"problem: {exc}", file=sys.stderr)
        return 1
    for target in written:
        print(f"{REFRESHED_PREFIX}{target}")
    for advisory in advisories:
        print(f"{ADVISORY_PREFIX}{advisory}")
    for problem in problems:
        print(f"{PROBLEM_PREFIX}{problem}", file=sys.stderr)
    if not written and not problems:
        print("no enrolled cli-sequence directives matched; nothing to refresh")
    if written and not problems:
        print(f"{len(written)} golden(s) rewritten; review the git diff and commit them")
    return 1 if problems else 0


def _refresh_pages(page: list[str] | None, command_path: str | None, docs_root: Path | None) -> list[str] | None:
    """Resolve the refresh scope to pages: ``None`` for every page, else the named or command-selected ones."""
    if command_path is None:
        return page
    command = tuple(command_path.split())
    if not command:
        raise SequenceEngineError("--command needs a command path such as 'app ledger classify'")
    discovered, _problems = discover_sequences(docs_root=docs_root)
    return list(pages_running_command(discovered, command))


def _seeds_mode(args: argparse.Namespace) -> int:
    """Render the persona-derived recipe frames, or with ``--check`` report drift without writing."""
    if args.check:
        problems = check_seeds(seeds_root=args.seeds_root)
        for problem in problems:
            print(f"FAIL: {problem}", file=sys.stderr)
        if problems:
            return 1
        print("seed recipes: clean")
        return 0
    written = write_seeds(seeds_root=args.seeds_root)
    for recipe in written:
        print(f"regenerated: {recipe}")
    print(f"{len(written)} seed recipe(s) rewritten" if written else "seed recipes: already current")
    return 0


def _coherence_mode(args: argparse.Namespace) -> int:
    """Coherence mode."""
    if args.sequence is not None:
        print("--coherence is a page-level tier; scope with --page, not --sequence", file=sys.stderr)
        return 2
    try:
        coherence_problems = (
            check_page_coherence(docs_root=args.docs_root, page=args.page)
            if args.timeout is None
            else check_page_coherence_in_subprocess(
                docs_root=args.docs_root,
                page=args.page,
                timeout=args.timeout,
            )
        )
    except SequenceEngineError as exc:
        print(f"FAIL: {exc}", file=sys.stderr)
        return 1
    if coherence_problems:
        for problem in coherence_problems:
            print(f"FAIL: {problem}", file=sys.stderr)
        print(
            f"{len(coherence_problems)} page-coherence failure(s). This tier runs a page's "
            "sequences cumulatively in one sandbox, in page order — fix the page's prose or "
            "sequences so a reader following it top to bottom gets the described results. "
            "Goldens are the separate per-sequence isolated contract; a refresh does not "
            "apply here.",
            file=sys.stderr,
        )
        return 1
    print("cli-sequence page coherence: clean")
    return 0


def _single_sequence_advisory(args: argparse.Namespace) -> None:
    """Single sequence advisory."""
    owning_page = checks_owning_page(
        args.sequence,
        docs_root=args.docs_root,
    )
    target = owning_page or "<docname>"
    print(
        f"advisory: a single-sequence pass does not verify {args.sequence!r}; sequences on a "
        "page share the in-process CLI tree, so run the page-level gate before trusting this: "
        f"python -m dev.docs.sequences check --page {target}",
    )


if __name__ == "__main__":
    sys.exit(main())

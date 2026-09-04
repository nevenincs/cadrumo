"""``python -m dev.docs.sequences`` — the golden refresh and check CLI.

Two modes over one engine:

- ``refresh [--page PAGE | --sequence ID]`` re-executes the addressed
  sequences in fresh hermetic sandboxes and rewrites their committed golden
  files. The author reviews the git diff — which IS the behaviour-change
  review — and commits the goldens with the CLI change that legitimately
  moved them. This is the ONLY sanctioned way a golden changes.
- ``check [--page PAGE | --sequence ID]`` re-executes the addressed sequences
  and compares against the committed goldens, failing (exit 1) with every
  divergence: the page, the sequence id, the frame index and argv, the
  post-mask differing paths or unified text diff, and the exact ``refresh``
  invocation that updates the golden.

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
review-visible, but the advisory keeps dead bindings from accumulating.
"""

from __future__ import annotations

import sys

from ._golden_store import (
    refresh_invocation,
)
from .checks import (
    _build_argument_parser,
    _owning_page,
    check_page_coherence,
    check_page_coherence_in_subprocess,
    check_sequences,
    check_sequences_in_subprocess,
    refresh_sequences,
)
from .errors import SequenceEngineError


def main(argv: list[str] | None = None) -> int:
    """CLI entry: exit 0 on a clean run, 1 on any problem, 2 on usage errors."""
    parser = _build_argument_parser()
    args = parser.parse_args(argv)

    if args.mode == "refresh":
        written, problems, advisories = refresh_sequences(
            docs_root=args.docs_root,
            goldens_root=args.goldens_root,
            page=args.page,
            sequence_id=args.sequence,
        )
        for target in written:
            print(f"refreshed: {target}")
        for advisory in advisories:
            print(f"advisory: {advisory}")
        for problem in problems:
            print(f"problem: {problem}", file=sys.stderr)
        if not written and not problems:
            print("no enrolled cli-sequence directives matched; nothing to refresh")
        if written and not problems:
            print(f"{len(written)} golden(s) rewritten; review the git diff and commit them")
        return 1 if problems else 0

    if args.coherence:
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
        # A single-sequence pass is NOT a verification. Sequences on one page
        # share the in-process CLI tree, so a clean run in isolation can hide a
        # divergence that only appears once the page's earlier sequences have
        # run ahead of it — observed on `filing-spine-file`, which passed alone
        # and failed under its page. Say so at the point of use rather than
        # letting a green line be mistaken for the gate.
        owning_page = _owning_page(
            args.sequence,
            docs_root=args.docs_root,
        )
        target = owning_page or "<docname>"
        print(
            f"advisory: a single-sequence pass does not verify {args.sequence!r}; sequences on a "
            "page share the in-process CLI tree, so run the page-level gate before trusting this: "
            f"python -m dev.docs.sequences check --page {target}",
        )
    return 0


if __name__ == "__main__":
    sys.exit(main())

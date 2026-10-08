"""Run the committed cli-sequence goldens gate for a merge-gate change set.

The gate re-executes every documented CLI sequence and compares each transcript
with its committed golden. A pull request pays for it only when a changed path
can alter documented output (:func:`dev.ci.change_scope.selects_sequence_goldens`),
and even then a clean verdict already recorded for the identical input set is
reused instead of executing again.

The verdict records live below the development cache root, which defaults to
the checkout's own ``.cache`` and so dies with every fresh CI checkout. A CI step
that points ``CADRUMO_DEV_CACHE_ROOT`` at runner-persistent storage keeps them
between runs. Only a clean verdict is ever recorded, so a stale record can cost
a re-run but can never turn a divergence green.
"""

from __future__ import annotations

import argparse
import sys
from collections.abc import Callable, Iterable, Sequence
from pathlib import Path
from typing import Final

from dev.ci.change_scope import read_changed_files, selects_sequence_goldens
from dev.docs.sequences.checks import check_sequences_in_subprocess, default_docs_root
from dev.docs.sequences.errors import SequenceEngineError
from dev.docs.sequences.golden_store import refresh_invocation
from dev.docs.sequences.verdict_cache import check_reusing_verdict, published_verdict_key

__all__ = [
    "DEFAULT_JOBS",
    "committed_goldens_key",
    "main",
    "run_sequence_goldens_gate",
]

#: Page-sharded check children run at once. Eight is the fleet's explicit lane
#: width for a runner shared with co-resident jobs, never the whole machine.
DEFAULT_JOBS: Final = 8


def committed_goldens_key() -> str:
    """Return the verdict key of the committed docs tree under the published authority.

    The docs root and the absent goldens override match what a full docs build
    passes, so a verdict recorded by either surface is reusable by the other.
    """
    return published_verdict_key(docs_root=default_docs_root(), goldens_root=None)


def _check_committed_goldens(jobs: int) -> tuple[str, ...]:
    return check_sequences_in_subprocess(jobs=jobs)


def run_sequence_goldens_gate(
    changed_files: Iterable[str] | None,
    *,
    jobs: int = DEFAULT_JOBS,
    input_key: Callable[[], str] = committed_goldens_key,
    check: Callable[[int], tuple[str, ...]] = _check_committed_goldens,
) -> int:
    """Run the gate for ``changed_files``; return 0 when clean or not selected, else 1."""
    if changed_files is not None and not selects_sequence_goldens(changed_files):
        print("cli-sequence goldens: not selected; no changed path can alter documented output")
        return 0
    try:
        key = input_key()
        problems, reused = check_reusing_verdict(key, lambda: check(jobs))
    except SequenceEngineError as exc:
        print(f"FAIL: {exc}", file=sys.stderr)
        return 1
    if reused is not None:
        print(f"cli-sequence goldens: clean ({reused})")
        return 0
    if problems:
        for problem in problems:
            print(f"FAIL: {problem}", file=sys.stderr)
        print(
            f"{len(problems)} divergence(s). If the new behaviour is intended, update the "
            f"golden(s) with: {refresh_invocation()}",
            file=sys.stderr,
        )
        return 1
    print(f"cli-sequence goldens: clean (recorded verdict {key[:12]})")
    return 0


def main(
    argv: Sequence[str] | None = None,
) -> int:
    """Run the gate for supplied paths, or the full gate when absent."""
    parser = argparse.ArgumentParser(prog="python -m dev.ci.sequence_goldens_gate", description=__doc__)
    parser.add_argument("--changed-files", type=Path, help="file of repository-relative changed paths")
    parser.add_argument(
        "--jobs",
        type=int,
        default=DEFAULT_JOBS,
        help=f"page-sharded check children run at once (default {DEFAULT_JOBS})",
    )
    arguments = parser.parse_args(argv)
    if arguments.jobs < 1:
        parser.error("--jobs must be at least 1")

    try:
        changed = None if arguments.changed_files is None else read_changed_files(arguments.changed_files)
    except (OSError, ValueError) as error:
        parser.error(str(error))
    return run_sequence_goldens_gate(changed, jobs=arguments.jobs)


if __name__ == "__main__":  # pragma: no cover - entrypoint
    sys.exit(main())

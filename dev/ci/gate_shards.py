"""Partition the merge gate's test files into deterministic shards.

The headless merge gate runs on small hosted runners, so its test population is
spread over a job matrix instead of one long job. Two commands share one
selection, so the matrix a run plans is the matrix its jobs execute:

- ``plan`` reads the change scope (:mod:`dev.ci.change_scope`), counts the test
  files it selects, and prints the shard list a workflow matrix expands;
- ``select`` writes the test files of one shard, one path per line, for pytest
  to run by name.

Files are enumerated from the working tree under the scope's targets, the way a
pytest directory walk finds them, and dealt to shards largest first onto the
lightest shard. File size stands in for run time: it is the only weight the
tree itself carries, and it needs no recorded timings that would have to be
kept current. The same tree and the same shard count always give the same
partition, and every file lands in exactly one shard.
"""

from __future__ import annotations

import argparse
import fnmatch
import json
import sys
from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Final

from dev.paths import REPO_ROOT, UTF_8
from dev.source_tree import repository_files

from .change_scope import ChangeScope, scope_for_manifest

__all__ = [
    "DEFAULT_FILES_PER_SHARD",
    "DEFAULT_MAX_SHARDS",
    "ShardPlan",
    "main",
    "parse_shard",
    "partition",
    "plan_shards",
    "selected_test_files",
    "shard_count",
]

#: A shard is sized by the memory of a hosted runner (16 GB, 3 GB swap), not
#: its time: the four test workers each keep what their tests leave behind, so
#: a runner's memory grows with the tests it runs. At about 900 files every
#: shard of the full tree used all of it, swap included, and the runner was
#: lost before pytest's summary. At 400 the worst shard's projected peak is
#: about 12 GB.
DEFAULT_FILES_PER_SHARD: Final = 400
#: The widest matrix a run may plan. It must hold the full tree at
#: ``DEFAULT_FILES_PER_SHARD``: a cap below that makes every shard larger and
#: brings the memory exhaustion back.
DEFAULT_MAX_SHARDS: Final = 24

_TEST_FILE_PATTERN: Final = "test_*.py"
#: Directory names a pytest directory walk never enters (its default
#: ``norecursedirs``). A file named explicitly would be collected from them
#: anyway, so they are dropped here to keep a shard equal to the walk.
_UNWALKED_DIRECTORIES: Final = (".*", "*.egg", "_darcs", "build", "CVS", "dist", "node_modules", "venv", "{arch}")


@dataclass(frozen=True, slots=True)
class ShardPlan:
    """The matrix one run executes, and the gates beside it."""

    shards: tuple[str, ...]
    files: int
    ci_contracts: bool
    sequence_goldens: bool
    too_broad: bool
    reason: str | None

    def github_outputs(self) -> tuple[str, ...]:
        """Return the plan as ``name=value`` lines for a workflow step's outputs."""
        return (
            f"shards={json.dumps(list(self.shards), separators=(',', ':'))}",
            f"files={self.files}",
            f"ci-contracts={'true' if self.ci_contracts else 'false'}",
            f"sequence-goldens={'true' if self.sequence_goldens else 'false'}",
        )


def _walked(relative: PurePosixPath) -> bool:
    """Return whether a pytest directory walk from a target would reach this file."""
    return not any(
        fnmatch.fnmatchcase(part, pattern) for part in relative.parts[:-1] for pattern in _UNWALKED_DIRECTORIES
    )


def selected_test_files(
    targets: Iterable[str], *, root: Path = REPO_ROOT, excluded: Iterable[str] = ()
) -> tuple[str, ...]:
    """Return every test file under ``targets``, sorted and repository-relative.

    ``excluded`` names files that a lane holds out by path, such as the harness
    proofs that own a worker pool of their own.

    Raises:
        FileNotFoundError: When a target does not exist, so a moved directory
            cannot pass for an empty one.
    """
    held_out = {PurePosixPath(entry.replace("\\", "/")).as_posix() for entry in excluded}
    normalised = [PurePosixPath(target.replace("\\", "/")).as_posix() for target in targets]
    found: set[str] = set()
    for entry in repository_files(root, under=normalised, must_exist=True):
        path = PurePosixPath(entry)
        if not fnmatch.fnmatchcase(path.name, _TEST_FILE_PATTERN) or entry in held_out:
            continue
        # A target is where the walk starts, so only what lies below it is judged.
        base = next((target for target in normalised if entry == target or entry.startswith(f"{target}/")), "")
        below = PurePosixPath(entry[len(base) :].lstrip("/")) if base else path
        if _walked(below):
            found.add(entry)
    return tuple(sorted(found))


def shard_count(files: int, *, files_per_shard: int, max_shards: int) -> int:
    """Return how many shards ``files`` test files are spread over."""
    if files_per_shard < 1 or max_shards < 1:
        raise ValueError("files_per_shard and max_shards must be positive")
    if files < 1:
        raise ValueError("the selection holds no test file, so there is nothing to shard")
    return min(max_shards, -(-files // files_per_shard))


def partition(weights: Sequence[tuple[str, int]], count: int) -> tuple[tuple[str, ...], ...]:
    """Deal weighted files into ``count`` shards, heaviest first onto the lightest shard.

    Ties are broken by path and by shard number, so the result depends on
    nothing but its arguments. Each shard's files come back sorted.
    """
    if count < 1:
        raise ValueError("a partition needs at least one shard")
    names = [name for name, _ in weights]
    if len(set(names)) != len(names):
        raise ValueError("a file may be dealt to one shard only")
    loads = [0] * count
    shards: list[list[str]] = [[] for _ in range(count)]
    for name, weight in sorted(weights, key=lambda item: (-item[1], item[0])):
        lightest = min(range(count), key=lambda index: (loads[index], index))
        shards[lightest].append(name)
        # Every file costs something to collect, so an empty one still weighs.
        loads[lightest] += max(weight, 1)
    return tuple(tuple(sorted(shard)) for shard in shards)


def parse_shard(text: str) -> tuple[int, int]:
    """Read ``INDEX/COUNT`` with a one-based index.

    Raises:
        ValueError: When the text is not two positive integers with the index within the count.
    """
    index_text, separator, count_text = text.partition("/")
    if not separator or not index_text.isascii() or not count_text.isascii():
        raise ValueError(f"a shard is written INDEX/COUNT, not {text!r}")
    if not index_text.isdigit() or not count_text.isdigit():
        raise ValueError(f"a shard is written INDEX/COUNT, not {text!r}")
    index, count = int(index_text), int(count_text)
    if not 1 <= index <= count:
        raise ValueError(f"shard index {index} is outside 1..{count}")
    return index, count


def _weights(files: Sequence[str], root: Path) -> list[tuple[str, int]]:
    return [(name, (root / name).stat().st_size) for name in files]


def plan_shards(
    scope: ChangeScope,
    *,
    root: Path = REPO_ROOT,
    excluded: Iterable[str] = (),
    files_per_shard: int = DEFAULT_FILES_PER_SHARD,
    max_shards: int = DEFAULT_MAX_SHARDS,
) -> ShardPlan:
    """Return the shard matrix for one change scope."""
    files = selected_test_files(scope.targets, root=root, excluded=excluded)
    count = shard_count(len(files), files_per_shard=files_per_shard, max_shards=max_shards)
    return ShardPlan(
        shards=tuple(f"{index}/{count}" for index in range(1, count + 1)),
        files=len(files),
        ci_contracts=scope.ci_contracts,
        sequence_goldens=scope.sequence_goldens,
        too_broad=scope.too_broad,
        reason=scope.reason,
    )


def _plan_lines(scope: ChangeScope, arguments: argparse.Namespace) -> tuple[str, ...]:
    planned = plan_shards(
        scope,
        excluded=arguments.exclude,
        files_per_shard=arguments.files_per_shard,
        max_shards=arguments.max_shards,
    )
    if arguments.github_output:
        return planned.github_outputs()
    return (json.dumps({"shards": list(planned.shards), "files": planned.files}, indent=2),)


def _write_shard(scope: ChangeScope, arguments: argparse.Namespace) -> tuple[str, ...] | None:
    """Write one shard's files and return the line reporting it, or ``None`` for an empty shard."""
    index, count = parse_shard(arguments.shard)
    files = selected_test_files(scope.targets, excluded=arguments.exclude)
    shard = partition(_weights(files, REPO_ROOT), count)[index - 1]
    if not shard:
        return None
    arguments.output.parent.mkdir(parents=True, exist_ok=True)
    arguments.output.write_text("".join(f"{name}\n" for name in shard), encoding=UTF_8, newline="\n")
    return (f"shard {arguments.shard}: {len(shard)} of {len(files)} test files",)


def main(argv: Sequence[str] | None = None) -> int:
    """Plan a run's shard matrix, or write the files of one shard."""
    parser = argparse.ArgumentParser(prog="python -m dev.ci.gate_shards", description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    for name in ("plan", "select"):
        command = commands.add_parser(name)
        command.add_argument("--changed-files", type=Path, help="file of repository-relative changed paths")
        command.add_argument("--exclude", action="append", default=[], help="test file a lane holds out by path")
    plan = commands.choices["plan"]
    plan.add_argument("--files-per-shard", type=int, default=DEFAULT_FILES_PER_SHARD)
    plan.add_argument("--max-shards", type=int, default=DEFAULT_MAX_SHARDS)
    plan.add_argument("--github-output", action="store_true", help="print workflow step outputs instead of JSON")
    select = commands.choices["select"]
    select.add_argument("--shard", required=True, help="INDEX/COUNT, with a one-based index")
    select.add_argument("--output", type=Path, required=True, help="file to receive the shard's test files")
    arguments = parser.parse_args(argv)

    try:
        scope = scope_for_manifest(arguments.changed_files)
        report = _plan_lines if arguments.command == "plan" else _write_shard
        lines = report(scope, arguments)
    except (OSError, ValueError) as error:
        parser.error(str(error))
    if scope.too_broad:
        print(f"change scope too broad; running the contract set only: {scope.reason}", file=sys.stderr)
    if lines is None:
        # A matrix wider than its file list would report green shards that ran nothing.
        print(f"shard {arguments.shard} holds no test file; the plan and the tree disagree", file=sys.stderr)
        return 1
    print("\n".join(lines), file=sys.stdout if arguments.command == "plan" else sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

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

Sequence discovery reads the enrolled docs pages directly: a page enrolls by
carrying at least one *backtick*-fenced ``cli-sequence`` MyST directive (the
backtick fence form, never the colon form); this module extracts each
directive's id, options, and frame body and parses it through the shared
grammar parser. A sequence whose author binds
a ``@capture`` no later frame consumes is reported as a named advisory (never
a failure): the capture still records into the transcript and golden, so it is
review-visible, but the advisory keeps dead bindings from accumulating.
"""

from __future__ import annotations

import argparse
import re
import sys
from dataclasses import dataclass
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Final

from pydantic import BaseModel, Field

from cadrumo.core import STRICT_FROZEN_CONFIG as _STRICT_FROZEN

from ._compare import check_transcript, evaluate_expectations
from ._errors import SequenceEngineError, SequenceParseError
from ._golden_store import (
    read_golden,
    refresh_invocation,
    write_golden,
)
from ._parser import parse_sequence
from ._runner import SequenceTranscript, execute_page_sequences, execute_sequence
from ._schema import ParsedSequence, SequenceId

_UTF_8: Final[str] = "utf-8"

__all__ = [
    "COHERENCE_TIER_PREFIX",
    "DiscoveredSequence",
    "check_page_coherence",
    "check_sequences",
    "default_docs_root",
    "discover_sequences",
    "main",
    "refresh_sequences",
    "unused_capture_advisories",
]

#: Opening line of a backtick-fenced ``cli-sequence`` directive (the
#: backtick fence form, never the colon form).
_FENCE_OPEN_RE = re.compile(r"^(?P<fence>`{3,})\{cli-sequence\}\s+(?P<id>\S+)\s*$")

#: A ``:key: value`` directive option line directly under the opening fence.
_OPTION_RE = re.compile(r"^:(?P<key>[a-z][a-z0-9_-]*):\s*(?P<value>.*)$")

#: Directories under ``docs/`` that never carry enrolled narrative pages.
_SKIPPED_DOC_DIRS = frozenset({"_build", "_sequences", "_static", "_templates"})


class DiscoveredSequence(BaseModel):
    """One ``cli-sequence`` directive found on an enrolled docs page."""

    model_config = _STRICT_FROZEN

    page: str
    sequence_id: SequenceId
    line_number: int = Field(ge=1)
    sequence: ParsedSequence


def default_docs_root() -> Path:
    """Return the committed ``docs/`` narrative tree.

    Resolved relative to this module so the engine finds pages regardless of
    the process working directory (the same anchoring as seeds and goldens).
    """
    repo_root = Path(__file__).resolve().parents[3]
    return repo_root / "docs"


def _page_files(docs_root: Path) -> list[Path]:
    """Return every markdown page under ``docs_root``, skipping non-page trees."""
    pages: list[Path] = []
    for path in sorted(docs_root.rglob("*.md")):
        relative = path.relative_to(docs_root)
        if relative.parts and relative.parts[0] in _SKIPPED_DOC_DIRS:
            continue
        pages.append(path)
    return pages


@dataclass(frozen=True)
class _RawDirective:
    """One extracted-but-unparsed ``cli-sequence`` directive on a page."""

    sequence_id: str
    options: dict[str, str | None]
    body: str
    line_number: int


def _extract_directives(
    text: str,
    *,
    page: str,
    problems: list[str],
) -> list[_RawDirective]:
    """Extract every ``cli-sequence`` directive's raw parts from a page."""
    directives: list[_RawDirective] = []
    lines = text.splitlines()
    index = 0
    while index < len(lines):
        match = _FENCE_OPEN_RE.match(lines[index].strip())
        if match is None:
            index += 1
            continue
        fence = match.group("fence")
        sequence_id = match.group("id")
        opened_at = index + 1
        index += 1
        options: dict[str, str | None] = {}
        while index < len(lines):
            option = _OPTION_RE.match(lines[index].strip())
            if option is None:
                break
            options[option.group("key")] = option.group("value").strip()
            index += 1
        body_lines: list[str] = []
        closed = False
        while index < len(lines):
            stripped = lines[index].strip()
            if stripped.startswith(fence) and set(stripped) == {"`"}:
                closed = True
                index += 1
                break
            body_lines.append(lines[index])
            index += 1
        if not closed:
            problems.append(
                f"page {page!r} line {opened_at}: cli-sequence {sequence_id!r} directive fence is never closed",
            )
            continue
        directives.append(
            _RawDirective(
                sequence_id=sequence_id,
                options=options,
                body="\n".join(body_lines),
                line_number=opened_at,
            ),
        )
    return directives


#: A prose mention of the profile-setup command family qualifies as a
#: valid-profile prerequisite.
_PROFILE_COMMAND_MENTION: str = "aeat config profile"
#: A markdown link whose TARGET names a profile page also qualifies
#: (e.g. ``[Create a profile](profile-setup.md)``).
_PROFILE_LINK_RE = re.compile(r"\[[^\]]*\]\([^)]*profile[^)]*\)", re.IGNORECASE)


def _profile_prerequisite_problem(text: str, docname: str, first_directive_line: int) -> str | None:
    """Enforce the enrolled-page valid-profile prerequisite (rollout gate).

    A reader lands on an enrolled page with their own environment, where no
    sandbox pre-provisions a profile — the page must say, BEFORE its first
    executed sequence, that a valid profile is required and how to get one.
    Qualifying mentions: an ``aeat config profile ...`` command in the prose, or
    a markdown link whose target contains ``profile``.
    """
    prose_above = "\n".join(text.splitlines()[: first_directive_line - 1])
    if _PROFILE_COMMAND_MENTION in prose_above or _PROFILE_LINK_RE.search(prose_above):
        return None
    return (
        f"page {docname!r}: an enrolled page must state its valid-profile prerequisite "
        f"BEFORE the first cli-sequence directive (line {first_directive_line}); qualify by "
        f"mentioning an '{_PROFILE_COMMAND_MENTION} ...' command or linking a profile setup "
        "page (a markdown link whose target contains 'profile', e.g. "
        "[Create a profile](profile-setup.md)) in the prose above it"
    )


def discover_sequences(
    *,
    docs_root: Path | None = None,
    page: str | None = None,
    sequence_id: str | None = None,
) -> tuple[tuple[DiscoveredSequence, ...], tuple[str, ...]]:
    """Discover and parse every enrolled ``cli-sequence`` directive.

    Args:
        docs_root: The narrative pages tree; defaults to the committed ``docs/``.
        page: Restrict to one docname-style page path (e.g.
            ``tutorials/first-filing``).
        sequence_id: Restrict to one sequence id.

    Returns:
        ``(discovered, problems)``. ``problems`` accumulates unclosed fences,
        grammar/structural parse faults (each naming the page), duplicate
        sequence ids, an enrolled page missing its valid-profile prerequisite
        prose, and an addressed page or sequence that does not exist.
    """
    root = docs_root if docs_root is not None else default_docs_root()
    discovered: list[DiscoveredSequence] = []
    problems: list[str] = []
    seen_ids: dict[str, str] = {}

    page_files = _page_files(root)
    if page is not None:
        wanted = root / f"{page}.md"
        page_files = [path for path in page_files if path == wanted]
        if not page_files:
            problems.append(f"page {page!r} does not exist under {root}")

    for path in page_files:
        docname = path.relative_to(root).with_suffix("").as_posix()
        try:
            text = path.read_text(encoding=_UTF_8)
        except OSError as exc:
            problems.append(f"page {docname!r}: cannot read ({exc})")
            continue
        raw_directives = _extract_directives(text, page=docname, problems=problems)
        if raw_directives:
            prerequisite_problem = _profile_prerequisite_problem(text, docname, raw_directives[0].line_number)
            if prerequisite_problem is not None:
                problems.append(prerequisite_problem)
        for raw in raw_directives:
            found_id = raw.sequence_id
            if sequence_id is not None and found_id != sequence_id:
                continue
            if found_id in seen_ids:
                problems.append(
                    f"page {docname!r}: duplicate sequence id {found_id!r} "
                    f"(already declared on page {seen_ids[found_id]!r}); sequence ids are "
                    "globally unique",
                )
                continue
            seen_ids[found_id] = docname
            try:
                sequence = parse_sequence(sequence_id=found_id, options=raw.options, body=raw.body)
            except SequenceParseError as exc:
                problems.extend(f"page {docname!r}: {problem}" for problem in exc.problems)
                continue
            discovered.append(
                DiscoveredSequence(
                    page=docname,
                    sequence_id=found_id,
                    line_number=raw.line_number,
                    sequence=sequence,
                ),
            )

    if sequence_id is not None and not discovered and not problems:
        problems.append(f"no enrolled cli-sequence with id {sequence_id!r} was found under {root}")
    return tuple(discovered), tuple(problems)


def unused_capture_advisories(item: DiscoveredSequence) -> tuple[str, ...]:
    """Report ``@capture`` bindings no later frame's placeholder consumes.

    A named advisory, never a failure: the capture still records into the
    transcript and golden (review-visible data), but a binding nothing consumes
    is usually authoring dead weight worth pruning.
    """
    consumed = {name for frame in item.sequence.frames for name in frame.placeholder_names}
    return tuple(
        f"page {item.page!r} sequence {item.sequence_id!r}: @capture {binding.name!r} "
        "is never consumed by a later frame's {placeholder}; it is recorded in the "
        "golden but interpolates nowhere"
        for frame in item.sequence.frames
        for binding in frame.captures
        if binding.name not in consumed
    )


def refresh_sequences(
    *,
    docs_root: Path | None = None,
    goldens_root: Path | None = None,
    page: str | None = None,
    sequence_id: str | None = None,
) -> tuple[tuple[Path, ...], tuple[str, ...], tuple[str, ...]]:
    """Re-execute the addressed sequences and rewrite their golden files.

    Returns:
        ``(written, problems, advisories)``: the golden paths written, the
        discovery/execution problems (a non-empty tuple means the refresh is
        incomplete), and the non-failing advisories.
    """
    discovered, problems = discover_sequences(docs_root=docs_root, page=page, sequence_id=sequence_id)
    written: list[Path] = []
    advisories: list[str] = []
    all_problems = list(problems)
    for item in discovered:
        advisories.extend(unused_capture_advisories(item))
        try:
            transcript = _execute_in_fresh_sandbox(item.sequence)
        except SequenceEngineError as exc:
            all_problems.append(f"page {item.page!r}: {exc}")
            continue
        written.append(write_golden(transcript, page=item.page, goldens_root=goldens_root))
    return tuple(written), tuple(all_problems), tuple(advisories)


def check_sequences(
    *,
    docs_root: Path | None = None,
    goldens_root: Path | None = None,
    page: str | None = None,
    sequence_id: str | None = None,
) -> tuple[tuple[str, ...], tuple[str, ...]]:
    """Execute the addressed sequences and compare against committed goldens.

    This is THE engine check function: the ``check`` CLI mode, the Sphinx
    ``builder-inited`` hook, and the pytest gate all call it, so a divergence
    reds every surface through one execution path.

    Returns:
        ``(problems, advisories)``. Empty ``problems`` is a clean pass; each
        problem names the page, sequence id, frame index and argv, the
        differing paths or unified diff, and the run closes with the exact
        refresh invocation (appended by :func:`main`'s check mode; callers
        composing their own output can use
        :func:`~dev.docs.sequences._golden_store.refresh_invocation`).
    """
    discovered, problems = discover_sequences(docs_root=docs_root, page=page, sequence_id=sequence_id)
    all_problems = list(problems)
    advisories: list[str] = []
    for item in discovered:
        advisories.extend(unused_capture_advisories(item))
        try:
            golden = read_golden(item.page, item.sequence_id, goldens_root=goldens_root)
        except SequenceEngineError as exc:
            all_problems.append(str(exc))
            continue
        try:
            transcript = _execute_in_fresh_sandbox(item.sequence)
        except SequenceEngineError as exc:
            all_problems.append(f"page {item.page!r}: {exc}")
            continue
        all_problems.extend(check_transcript(item.sequence, transcript, golden, page=item.page))
    return tuple(all_problems), tuple(advisories)


def _execute_in_fresh_sandbox(sequence: ParsedSequence) -> SequenceTranscript:
    """Run one sequence in a disposable sandbox directory."""
    with TemporaryDirectory(prefix="cli-sequence-", ignore_cleanup_errors=True) as tmp:
        return execute_sequence(sequence, sandbox_root=Path(tmp))


#: The tier prefix every page-coherence problem leads with, so a failure is
#: never mistaken for a golden divergence (the remedy differs: fix the page,
#: never refresh a golden).
COHERENCE_TIER_PREFIX: str = "page-coherence (cumulative page run, not the golden tier)"


def check_page_coherence(
    *,
    docs_root: Path | None = None,
    page: str | None = None,
) -> tuple[str, ...]:
    """Check every enrolled page reads true when followed top to bottom.

    The page-coherence tier (rollout gate): for each enrolled page, ONE fresh
    hermetic sandbox, all the page's sequences executed IN PAGE ORDER with
    state accumulating across them — exactly what a reader reproducing the page
    in one clean environment experiences. Per frame the exit-code expectation
    is enforced (a mismatch aborts the page's cumulative run); per sequence
    every ``@expect`` evaluates against the LIVE cumulative output. Golden
    equality is deliberately NOT asserted here: cross-sequence state
    accumulates by design, and goldens remain the separate per-sequence
    isolated contract.

    Returns:
        Accumulated problems: discovery faults (shared with the golden tier)
        plus coherence-tier failures, each prefixed with
        :data:`COHERENCE_TIER_PREFIX` and naming the page, sequence, frame,
        argv, and the failed expectation with actual vs expected.
    """
    discovered, problems = discover_sequences(docs_root=docs_root, page=page)
    all_problems = list(problems)

    by_page: dict[str, list[DiscoveredSequence]] = {}
    for item in discovered:
        by_page.setdefault(item.page, []).append(item)

    for docname, items in by_page.items():
        try:
            with TemporaryDirectory(prefix="cli-sequence-page-", ignore_cleanup_errors=True) as tmp:
                transcripts = execute_page_sequences(
                    [item.sequence for item in items],
                    label=docname,
                    sandbox_root=Path(tmp),
                )
                for item, transcript in zip(items, transcripts, strict=True):
                    all_problems.extend(
                        f"{COHERENCE_TIER_PREFIX}: {problem}"
                        for problem in evaluate_expectations(item.sequence, transcript, page=docname)
                    )
        except SequenceEngineError as exc:
            all_problems.append(
                f"{COHERENCE_TIER_PREFIX}: page {docname!r}: cumulative run aborted — {exc}",
            )
    return tuple(all_problems)


def _build_argument_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python -m dev.docs.sequences",
        description="Refresh or check the committed cli-sequence goldens.",
    )
    subparsers = parser.add_subparsers(dest="mode", required=True)
    for mode, help_text in (
        ("refresh", "re-execute sequences and rewrite their committed goldens"),
        ("check", "re-execute sequences and fail on any divergence from the goldens"),
    ):
        sub = subparsers.add_parser(mode, help=help_text)
        scope = sub.add_mutually_exclusive_group()
        scope.add_argument("--page", help="docname-style page path, e.g. tutorials/first-filing")
        scope.add_argument("--sequence", help="one sequence id")
        sub.add_argument("--docs-root", type=Path, default=None, help=argparse.SUPPRESS)
        sub.add_argument("--goldens-root", type=Path, default=None, help=argparse.SUPPRESS)
        if mode == "check":
            sub.add_argument(
                "--coherence",
                action="store_true",
                help=(
                    "run the page-coherence tier instead of the golden tier: each "
                    "enrolled page's sequences execute cumulatively in ONE sandbox, "
                    "in page order, and every @expect must hold against the live "
                    "cumulative output"
                ),
            )
    return parser


def main(argv: list[str] | None = None) -> int:
    """CLI entry: exit 0 on a clean run, 1 on any problem, 2 on usage errors."""
    args = _build_argument_parser().parse_args(argv)

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
        coherence_problems = check_page_coherence(docs_root=args.docs_root, page=args.page)
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

    problems, advisories = check_sequences(
        docs_root=args.docs_root,
        goldens_root=args.goldens_root,
        page=args.page,
        sequence_id=args.sequence,
    )
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
    return 0


if __name__ == "__main__":
    sys.exit(main())

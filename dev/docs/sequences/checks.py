"""Discovery, refresh, and checking of documentation sequence goldens.

This module owns the reusable sequence-checking API. ``__main__`` owns only
command-line parsing and invokes these definitions directly.
"""

from __future__ import annotations

import argparse
import math
import re
import subprocess
import sys
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Annotated, Final

from pydantic import BaseModel, Field, StringConstraints, ValidationError

from cadrumo.core.directory_scan import scan_directory
from cadrumo.core.models import STRICT_FROZEN_CONFIG as _STRICT_FROZEN
from cadrumo.core.storage_environment import prepare_temporary_directory
from cadrumo.tests.golden_comparison import canonicalise
from dev._paths import REPO_ROOT, UTF_8
from dev.packaging.command_execution import run_command
from dev.product_environment import ambient_product_settings_removed

from .authority_currency import require_current_authority
from .compare import check_transcript, evaluate_expectations, validate_live_export_evidence
from .contracts import read_sequence_contract
from .errors import SequenceEngineError, SequenceParseError
from .golden_store import (
    GoldenFrame,
    SequenceGolden,
    build_golden,
    read_golden,
    write_golden,
)
from .parser import parse_sequence
from .runner import (
    _PROGRESS_JOURNAL_ENV,
    SequenceTranscript,
    _sequence_progress_scope,
    execute_page_sequences,
    execute_sequence,
)
from .schema import FrameKind, ParsedSequence, SequenceId

__all__ = [
    "READER_FRAME_OUTPUT_ADVISORY_BYTES",
    "DiscoveredSequence",
    "check_page_coherence",
    "check_page_coherence_in_subprocess",
    "check_sequences",
    "check_sequences_in_subprocess",
    "default_docs_root",
    "discover_sequences",
    "oversized_frame_advisories",
    "recorded_output_bytes",
    "refresh_sequences",
    "unused_capture_advisories",
]


_UTF_8: Final[str] = UTF_8

_NonEmptyText = Annotated[str, StringConstraints(min_length=1)]

_FENCE_OPEN_RE = re.compile(r"^(?P<fence>`{3,})\{cli-sequence\}\s+(?P<id>\S+)\s*$")

_OPTION_RE = re.compile(r"^:(?P<key>[a-z][a-z0-9_-]*):\s*(?P<value>.*)$")

_SKIPPED_DOC_DIRS = frozenset({"_build", "_sequences", "_static", "_templates"})

_PROFILE_COMMAND_MENTION: str = "aeat config profile"

_PROFILE_LINK_RE = re.compile(r"\[[^\]]*\]\([^)]*profile[^)]*\)", re.IGNORECASE)

COHERENCE_TIER_PREFIX: str = "page-coherence (cumulative page run, not the golden tier)"

#: Recorded output above which a reader-facing frame draws an advisory.
#:
#: A reader-facing frame's recorded output is what the rendered page shows, so
#: a frame this large is a wall of output no reader follows, and it dominates
#: the committed golden tree. It is an advisory rather than a failure: some
#: commands legitimately print a lot, and only the author can judge whether a
#: text view or a narrower command serves the page better.
READER_FRAME_OUTPUT_ADVISORY_BYTES: Final[int] = 64 * 1024


class DiscoveredSequence(BaseModel):
    """One ``cli-sequence`` directive found on an enrolled docs page."""

    model_config = _STRICT_FROZEN

    page: str
    sequence_id: SequenceId
    line_number: int = Field(ge=1)
    sequence: ParsedSequence


class _SequenceProgressRecord(BaseModel):
    """Strict child-to-parent receipt for the last executing sequence frame."""

    model_config = _STRICT_FROZEN

    page: _NonEmptyText
    sequence_id: SequenceId
    frame_index: int = Field(ge=0)
    frame_source: _NonEmptyText
    frame_line: int = Field(ge=1)
    argv: list[_NonEmptyText] = Field(min_length=1)


def default_docs_root() -> Path:
    """Return the committed ``docs/`` narrative tree.

    Resolved relative to this module so the engine finds pages regardless of
    the process working directory (the same anchoring as seeds and goldens).
    """
    repo_root = REPO_ROOT
    return repo_root / "docs"


def _page_files(docs_root: Path) -> list[Path]:
    """Return every markdown page under ``docs_root``, skipping non-page trees."""
    pages: list[Path] = []
    for path in scan_directory(docs_root, pattern="*.md", recursive=True):
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
    contracts_root: Path | None = None,
    page: str | None = None,
    sequence_id: str | None = None,
) -> tuple[tuple[DiscoveredSequence, ...], tuple[str, ...]]:
    """Discover and parse every enrolled directive plus its private contract.

    Args:
        docs_root: The narrative pages tree; defaults to the committed ``docs/``.
        contracts_root: Optional private-contract root override.
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
        _discover_page_sequences(path, root, contracts_root, sequence_id, discovered, problems, seen_ids)

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


def recorded_output_bytes(frame: GoldenFrame) -> int:
    """Measure a golden frame's recorded output in UTF-8 bytes.

    The recorded output is the frame's stored golden content: the canonical
    JSON of its envelope plus its stdout text plus its stderr text. Absent
    streams count as empty.
    """
    envelope = canonicalise(frame.envelope) if frame.envelope is not None else ""
    return sum(len(part.encode(_UTF_8)) for part in (envelope, frame.text or "", frame.stderr_text or ""))


def oversized_frame_advisories(page: str, golden: SequenceGolden) -> tuple[str, ...]:
    """Report reader-facing frames whose recorded output exceeds the advisory limit.

    A named advisory, never a failure. Setup frames are not reader-facing and
    record no output, so only the other executed frames are measured; the frame
    index is the golden's, the same index a check failure names.
    """
    return tuple(
        f"page {page!r} sequence {golden.sequence_id!r} frame {index} (argv: {' '.join(frame.argv)}): "
        f"recorded output is {size} bytes, over the {READER_FRAME_OUTPUT_ADVISORY_BYTES}-byte "
        "reader-facing limit; print the text output instead of JSON, or narrow the command to what "
        "the page needs to show"
        for index, frame in enumerate(golden.frames)
        if frame.kind is not FrameKind.SETUP
        and (size := recorded_output_bytes(frame)) > READER_FRAME_OUTPUT_ADVISORY_BYTES
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

    Raises:
        SequenceEngineError: When a sequence would execute and the registry
            authority the runner reads is not current.
    """
    discovered, problems = discover_sequences(docs_root=docs_root, page=page, sequence_id=sequence_id)
    if any(item.sequence.executed_frames for item in discovered):
        require_current_authority()
    written: list[Path] = []
    advisories: list[str] = []
    all_problems = list(problems)
    for item in discovered:
        advisories.extend(unused_capture_advisories(item))
        if not item.sequence.executed_frames:
            continue  # all-@static: nothing runs, so there is no golden to write
        try:
            with _sequence_progress_scope(item.page), _execute_in_fresh_sandbox(item.sequence) as transcript:
                expectation_problems = evaluate_expectations(item.sequence, transcript, page=item.page)
                if expectation_problems:
                    all_problems.extend(expectation_problems)
                    continue
                evidence_problems = validate_live_export_evidence(transcript, page=item.page)
                if evidence_problems:
                    all_problems.extend(evidence_problems)
                    continue
                written.append(write_golden(transcript, page=item.page, goldens_root=goldens_root))
                advisories.extend(oversized_frame_advisories(item.page, build_golden(transcript)))
        except SequenceEngineError as exc:
            all_problems.append(f"page {item.page!r}: {exc}")
            continue
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
        :func:`~dev.docs.sequences.golden_store.refresh_invocation`).

    Raises:
        SequenceEngineError: When a sequence would execute and the registry
            authority the runner reads is not current.
    """
    discovered, problems = discover_sequences(docs_root=docs_root, page=page, sequence_id=sequence_id)
    if any(item.sequence.executed_frames for item in discovered):
        require_current_authority()
    all_problems = list(problems)
    advisories: list[str] = []
    for item in discovered:
        advisories.extend(unused_capture_advisories(item))
        if not item.sequence.executed_frames:
            continue  # all-@static: nothing runs, so there is no golden to compare
        try:
            golden = read_golden(item.page, item.sequence_id, goldens_root=goldens_root)
        except SequenceEngineError as exc:
            all_problems.append(str(exc))
            continue
        advisories.extend(oversized_frame_advisories(item.page, golden))
        try:
            with _sequence_progress_scope(item.page), _execute_in_fresh_sandbox(item.sequence) as transcript:
                all_problems.extend(check_transcript(item.sequence, transcript, golden, page=item.page))
        except SequenceEngineError as exc:
            all_problems.append(f"page {item.page!r}: {exc}")
            continue
    return tuple(all_problems), tuple(advisories)


def english_pinned_environment() -> dict[str, str]:
    """Return the scrubbed, English-pinned environment for a sequence child.

    CLI help strings are resolved while the command tree is imported, so the
    language premise must hold BEFORE the child's first CLI import; ambient
    ``CADRUMO_*`` / ``AEAT_*`` operator state is dropped for the same
    determinism reason the sandbox scrubs it.

    Public because every child interpreter that executes a sequence needs the
    same premise, not only the check children launched here: a gate that
    composed its own environment would drift from this one and measure a
    differently-configured product.
    """
    environment = ambient_product_settings_removed()
    # This is the check runner's scratch allocation, not product configuration.
    # Preserve its resolved location across children: a build-tree default can
    # exceed the native Unix socket path bound before a sequence starts.
    environment["CADRUMO_TEMP_DIR"] = str(prepare_temporary_directory())
    environment["CADRUMO_OUTPUT_LANGUAGE"] = "en"
    environment["PYTHONIOENCODING"] = _UTF_8
    environment["PYTHONUTF8"] = "1"
    return environment


def _timeout_progress_diagnostic(journal: Path, *, timeout: float) -> str:
    """Render the last frame recorded by a timed-out check child.

    The runner writes only runtime-derived data immediately before each actual
    CLI invocation.  A missing or malformed journal is itself useful evidence:
    the child did not reach a frame before the supplied supervisor deadline.
    """
    try:
        record = _SequenceProgressRecord.model_validate_json(journal.read_text(encoding=_UTF_8))
    except (OSError, ValidationError):
        return f"timeout after {timeout}s before the child recorded an executing frame"
    return (
        f"timeout after {timeout}s while executing page {record.page!r} "
        f"sequence {record.sequence_id!r} frame {record.frame_index} "
        f"({record.frame_source} line {record.frame_line}): {' '.join(record.argv)}"
    )


def _positive_finite_timeout(value: str) -> float:
    """Parse one finite, positive subprocess deadline for argparse."""
    try:
        timeout = float(value)
    except ValueError as exc:
        raise argparse.ArgumentTypeError("must be a finite number greater than zero") from exc
    if not math.isfinite(timeout) or timeout <= 0:
        raise argparse.ArgumentTypeError("must be a finite number greater than zero")
    return timeout


def _run_check_child(command: list[str], *, timeout: float | None) -> tuple[str, ...]:
    """Run one check child; return its report tuple (empty on a clean pass).

    Raises:
        SequenceEngineError: When the child cannot run the check surface
            (any exit other than 0 or 1).
    """
    with TemporaryDirectory(
        prefix="cli-sequence-progress-", ignore_cleanup_errors=True, dir=prepare_temporary_directory()
    ) as tmp:
        journal = Path(tmp) / "last-frame.json"
        environment = english_pinned_environment()
        environment[_PROGRESS_JOURNAL_ENV] = str(journal)
        try:
            result = run_command(
                command,
                cwd=REPO_ROOT,
                environment=environment,
                timeout_seconds=timeout,
            )
        except subprocess.TimeoutExpired as exc:
            if timeout is None:
                raise
            raise SequenceEngineError(_timeout_progress_diagnostic(journal, timeout=timeout)) from exc
    if result.returncode == 0:
        return ()
    report = "\n".join(part.strip() for part in (result.stdout, result.stderr) if part.strip())
    if result.returncode == 1:
        return (report,)
    raise SequenceEngineError(
        f"cli-sequence check subprocess failed (exit {result.returncode}):\n{report or '<no output>'}",
    )


def _scoped_check_command(
    *,
    page: str,
    docs_root: Path | None,
    goldens_root: Path | None,
    coherence: bool,
) -> list[str]:
    """Build one page-scoped ``check`` child command line."""
    command = [sys.executable, "-m", "dev.docs.sequences", "check", "--page", page]
    if coherence:
        command.append("--coherence")
    if docs_root is not None:
        command.extend(("--docs-root", str(docs_root)))
    if goldens_root is not None and not coherence:
        command.extend(("--goldens-root", str(goldens_root)))
    return command


def _check_pages_in_subprocesses(
    *,
    docs_root: Path | None,
    goldens_root: Path | None,
    jobs: int,
    timeout: float | None,
    coherence: bool = False,
) -> tuple[str, ...]:
    """Shard the unscoped check across page-scoped children, ``jobs`` at a time.

    Verdict parity with the serial unscoped run holds because sequences are
    hermetically independent (each executes in its own fresh sandbox) and the
    only CROSS-page discovery fault — a duplicate sequence id declared on two
    pages — is re-detected here by the parent's own unscoped discovery pass
    (parse-only, no execution) and prepended to the merged report. A page-local
    discovery fault is reported by both the parent and its page's child; on an
    already-red gate the repetition is cosmetic.

    Returns:
        The merged report tuple: the parent discovery problems (if any)
        followed by one complete diagnostic report per failing page child.
        Empty on a clean pass.
    """
    from concurrent.futures import ThreadPoolExecutor

    discovered, discovery_problems = discover_sequences(docs_root=docs_root)
    counts: dict[str, int] = {}
    for item in discovered:
        counts[item.page] = counts.get(item.page, 0) + 1
    # Longest page first: with bounded workers, scheduling the heaviest pages
    # early keeps the tail short (the largest page bounds the ideal wall).
    pages = sorted(counts, key=lambda page: counts[page], reverse=True)

    reports: list[str] = []
    if discovery_problems:
        reports.append("\n".join(f"FAIL: {problem}" for problem in discovery_problems))
    if pages:
        commands = [
            _scoped_check_command(page=page, docs_root=docs_root, goldens_root=goldens_root, coherence=coherence)
            for page in pages
        ]
        with ThreadPoolExecutor(max_workers=max(1, jobs)) as pool:
            for child_report in pool.map(lambda command: _run_check_child(command, timeout=timeout), commands):
                reports.extend(child_report)
    return tuple(reports)


def check_sequences_in_subprocess(
    *,
    docs_root: Path | None = None,
    goldens_root: Path | None = None,
    page: str | None = None,
    sequence_id: str | None = None,
    timeout: float | None = None,
    jobs: int = 1,
) -> tuple[str, ...]:
    """Run the golden check in fresh English-pinned interpreter(s).

    CLI help strings are resolved while the command tree is imported. A
    long-lived pytest or Sphinx process may already have materialised that tree
    under another locale, so changing settings in-process cannot make its help
    English again. The children still use :func:`check_sequences`; the process
    boundary only guarantees the language premise before the first CLI import.

    ``jobs`` bounds the page-sharded parallel mode for an UNSCOPED check: with
    ``jobs > 1`` and no ``page``/``sequence_id`` scoping, the enrolled pages
    run as concurrent page-scoped children (each sequence keeps its own fresh
    hermetic sandbox, so execution is unchanged — only the scheduling is).
    A scoped call, or ``jobs=1``, keeps the single-child path.

    Children run to completion unless the caller explicitly supplies an
    elapsed-time deadline; correctness does not depend on host speed.

    Returns:
        An empty tuple on success, or the complete child diagnostic report(s)
        on a golden divergence.

    Raises:
        SequenceEngineError: When the registry authority is not current, or a
            child cannot run the check surface.
    """
    # Refused here, once, so a stale authority is not reported by every child
    # as a golden divergence.
    require_current_authority()
    if jobs > 1 and page is None and sequence_id is None:
        return _check_pages_in_subprocesses(
            docs_root=docs_root,
            goldens_root=goldens_root,
            jobs=jobs,
            timeout=timeout,
        )
    command = [sys.executable, "-m", "dev.docs.sequences", "check"]
    if docs_root is not None:
        command.extend(("--docs-root", str(docs_root)))
    if goldens_root is not None:
        command.extend(("--goldens-root", str(goldens_root)))
    if page is not None:
        command.extend(("--page", page))
    if sequence_id is not None:
        command.extend(("--sequence", sequence_id))
    return _run_check_child(command, timeout=timeout)


def check_page_coherence_in_subprocess(
    *,
    docs_root: Path | None = None,
    page: str | None = None,
    timeout: float | None = None,
    jobs: int = 1,
) -> tuple[str, ...]:
    """Run the page-coherence tier in English-pinned child interpreter(s).

    The subprocess sibling of :func:`check_page_coherence`, with the same
    page-sharded ``jobs`` bound as :func:`check_sequences_in_subprocess`:
    coherence is a strictly page-scoped property (one sandbox per page, state
    accumulating only within the page), so pages are independent and shard
    cleanly.

    Children run to completion unless the caller explicitly supplies an
    elapsed-time deadline.

    Returns:
        An empty tuple on success, or the complete diagnostic report(s).

    Raises:
        SequenceEngineError: When the registry authority is not current, or a
            child cannot run the check surface.
    """
    require_current_authority()
    if page is not None:
        command = _scoped_check_command(
            page=page,
            docs_root=docs_root,
            goldens_root=None,
            coherence=True,
        )
        return _run_check_child(command, timeout=timeout)
    return _check_pages_in_subprocesses(
        docs_root=docs_root,
        goldens_root=None,
        jobs=jobs,
        timeout=timeout,
        coherence=True,
    )


@contextmanager
def _execute_in_fresh_sandbox(sequence: ParsedSequence) -> Iterator[SequenceTranscript]:
    """Keep disposable artifacts alive through their owning refresh/check."""
    with TemporaryDirectory(
        prefix="cli-sequence-", ignore_cleanup_errors=True, dir=prepare_temporary_directory()
    ) as tmp:
        yield execute_sequence(sequence, sandbox_root=Path(tmp))


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

    Raises:
        SequenceEngineError: When a sequence would execute and the registry
            authority the runner reads is not current.
    """
    discovered, problems = discover_sequences(docs_root=docs_root, page=page)
    if any(item.sequence.executed_frames for item in discovered):
        require_current_authority()
    all_problems = list(problems)

    by_page: dict[str, list[DiscoveredSequence]] = {}
    for item in discovered:
        by_page.setdefault(item.page, []).append(item)

    for docname, items in by_page.items():
        # An all-@static sequence runs nothing, so it produces no transcript;
        # only executable sequences take part in the cumulative page run and the
        # transcript alignment below.
        _check_page_coherence_items(docname, items, all_problems)
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
            sub.add_argument(
                "--timeout",
                type=_positive_finite_timeout,
                default=None,
                metavar="SECONDS",
                help=(
                    "run the check in one bounded child interpreter and report the "
                    "last started page, sequence, frame, and resolved command on expiry"
                ),
            )
    return parser


def _owning_page(sequence_id: str, *, docs_root: Path | None = None) -> str | None:
    """Return the docname of the page enrolling ``sequence_id``, or ``None``.

    Used only to make the single-sequence advisory name the exact page-level
    command to run next, so the operator is never told to substitute a docname
    themselves. A discovery failure here degrades the advisory's wording and must
    never affect the check's own verdict.
    """
    try:
        discovered, _problems = discover_sequences(docs_root=docs_root, sequence_id=sequence_id)
    except SequenceEngineError:
        return None
    return next((item.page for item in discovered if item.sequence_id == sequence_id), None)


def _discover_page_sequences(
    path: Path,
    root: Path,
    contracts_root: Path | None,
    sequence_id: str | None,
    discovered: list[DiscoveredSequence],
    problems: list[str],
    seen_ids: dict[str, str],
) -> None:
    """Discover page sequences."""
    docname = path.relative_to(root).with_suffix("").as_posix()
    try:
        text = path.read_text(encoding=_UTF_8)
    except OSError as exc:
        problems.append(f"page {docname!r}: cannot read ({exc})")
        return
    raw_directives = _extract_directives(text, page=docname, problems=problems)
    if raw_directives:
        prerequisite_problem = _profile_prerequisite_problem(text, docname, raw_directives[0].line_number)
        if prerequisite_problem is not None:
            problems.append(prerequisite_problem)
    for raw in raw_directives:
        _discover_raw_sequence(raw, docname, root, contracts_root, sequence_id, discovered, problems, seen_ids)


def _discover_raw_sequence(
    raw: _RawDirective,
    docname: str,
    root: Path,
    contracts_root: Path | None,
    sequence_id: str | None,
    discovered: list[DiscoveredSequence],
    problems: list[str],
    seen_ids: dict[str, str],
) -> None:
    """Discover raw sequence."""
    found_id = raw.sequence_id
    if sequence_id is not None and found_id != sequence_id:
        return
    if found_id in seen_ids:
        problems.append(
            f"page {docname!r}: duplicate sequence id {found_id!r} "
            f"(already declared on page {seen_ids[found_id]!r}); sequence ids are "
            "globally unique",
        )
        return
    seen_ids[found_id] = docname
    if raw.body.strip():
        problems.append(
            f"page {docname!r} sequence {found_id!r}: cli-sequence directive bodies "
            "must be empty; commands and development metadata belong in the keyed "
            "private contract under docs/_sequences/contracts",
        )
        return
    private_public_options = sorted(set(raw.options) - {"verify"})
    if private_public_options:
        rendered = ", ".join(f":{key}:" for key in private_public_options)
        problems.append(
            f"page {docname!r} sequence {found_id!r}: private option(s) {rendered} "
            "must live in the keyed sequence contract, not user-facing Markdown",
        )
        return
    try:
        contract_options, contract_body = read_sequence_contract(
            docname,
            found_id,
            docs_root=root,
            contracts_root=contracts_root,
        )
        options = {**contract_options, **raw.options}
        sequence = parse_sequence(sequence_id=found_id, options=options, body=contract_body)
    except SequenceParseError as exc:
        problems.extend(f"page {docname!r}: {problem}" for problem in exc.problems)
        return
    except SequenceEngineError as exc:
        problems.append(str(exc))
        return
    discovered.append(
        DiscoveredSequence(
            page=docname,
            sequence_id=found_id,
            line_number=raw.line_number,
            sequence=sequence,
        ),
    )


def _check_page_coherence_items(docname: str, items: list[DiscoveredSequence], all_problems: list[str]) -> None:
    """Check page coherence items."""
    executable = [item for item in items if item.sequence.executed_frames]
    try:
        with TemporaryDirectory(
            prefix="cli-sequence-page-", ignore_cleanup_errors=True, dir=prepare_temporary_directory()
        ) as tmp:
            with _sequence_progress_scope(docname):
                transcripts = execute_page_sequences(
                    [item.sequence for item in executable],
                    label=docname,
                    sandbox_root=Path(tmp),
                )
            for item, transcript in zip(executable, transcripts, strict=True):
                all_problems.extend(
                    f"{COHERENCE_TIER_PREFIX}: {problem}"
                    for problem in evaluate_expectations(item.sequence, transcript, page=docname)
                )
    except SequenceEngineError as exc:
        all_problems.append(
            f"{COHERENCE_TIER_PREFIX}: page {docname!r}: cumulative run aborted — {exc}",
        )

"""Golden comparison and semantic expectation evaluation.

An executed :class:`~dev.docs.sequences.runner.SequenceTranscript` is projected
into its run-independent record
(:func:`~dev.docs.sequences.record_store.build_record`) and fingerprinted
(:func:`~dev.docs.sequences.record_store.golden_from_record`); the fingerprint
is compared with the committed
:class:`~dev.docs.sequences.golden_store.SequenceGolden`, field by field:

- **Kind, argv, exit code and captures** are asserted on every frame, setup
  frames included.
- **The envelope stream** must match: a success envelope moving to a stderr
  error document, or JSON output turning into text, is a behavioural change.
- **The output digest and size** cover the compared form
  (:func:`~dev.docs.sequences.record_store.compared_form`): the envelope under
  ``mask_document`` with exactly the central ``GOLDEN_MASK_FIELDS`` plus the
  host-conditional carve-out, and the normalised text streams. This module
  exposes NO mask parameter and never overrides ``mask_document``'s central
  default: the executor never declares its own mask set and a sequence cannot
  carry a per-sequence mask extension (the one dishonesty lever the substrate
  would otherwise allow). Both properties are pinned — a signature gate and an
  AST gate over the ``mask_document`` calls in ``tests/test_compare.py``, plus
  the executor-level double-run proof in ``dev/docs/tests/test_sequence_goldens.py``.

A digest names THAT an output changed, not how. When the last verified record
of the sequence is cached, a changed frame is diffed against it: the post-mask
``differing_paths`` of a JSON envelope, or a unified diff of normalised text.

``@expect`` assertions are evaluated against the LIVE output
(:func:`evaluate_expectations`), never against the golden: golden equality
proves the output is reproducible; the ``@expect`` proves it *means* success,
so a sequence cannot "verify" by merely reproducing a failure.

Every problem string names the page, the sequence id, the frame index, and the
frame's argv; :func:`assert_transcript_matches_golden` closes with the exact
``refresh`` invocation that updates the golden.
"""

from __future__ import annotations

import difflib
import json
from collections.abc import Mapping

from cadrumo.tests.golden_comparison import canonicalise, differing_paths, mask_document

from .errors import SequenceGoldenMismatchError
from .golden_store import SequenceGolden, mask_host_conditional_details, refresh_invocation
from .record_store import RecordFrame, SequenceRecord, build_record, golden_from_record
from .runner import FrameExecution, SequenceTranscript, _resolve_json_path
from .schema import FrameKind, ParsedSequence

__all__ = [
    "assert_transcript_matches_golden",
    "check_transcript",
    "compare_transcript_to_golden",
    "evaluate_expectations",
]

#: The ``@expect`` pseudo-path asserting a frame's process exit code.
_EXIT_CODE_PATH: str = "exit_code"


def _frame_locator(page: str, sequence_id: str, index: int, frame: FrameExecution) -> str:
    """Render the page/sequence/frame/argv locator every problem leads with."""
    return f"page {page!r} sequence {sequence_id!r} frame {index} (argv: {' '.join(frame.argv)})"


def _unified_diff(expected: str, actual: str) -> str:
    """Render a unified diff between the golden and live normalised text."""
    lines = difflib.unified_diff(
        expected.splitlines(),
        actual.splitlines(),
        fromfile="golden",
        tofile="live",
        lineterm="",
    )
    return "\n".join(lines)


def _output_differences(expected: RecordFrame, actual: RecordFrame) -> tuple[str, ...]:
    """Describe how ``actual``'s output differs from the verified ``expected`` frame."""
    differences: list[str] = []
    if expected.envelope is not None and actual.envelope is not None:
        masked_expected = mask_host_conditional_details(mask_document(expected.envelope))
        masked_actual = mask_host_conditional_details(mask_document(actual.envelope))
        if not isinstance(masked_expected, Mapping) or not isinstance(masked_actual, Mapping):
            differences.append("masking returned a non-document, so the envelopes cannot be compared")
        elif canonicalise(masked_expected) != canonicalise(masked_actual):
            diff = ", ".join(sorted(differing_paths(masked_expected, masked_actual)))
            differences.append(f"envelope diverged at post-mask paths: {diff or '<whole-document>'}")
    for label, before, after in (
        ("stdout", expected.text, actual.text),
        ("stderr", expected.stderr_text, actual.stderr_text),
    ):
        if (before or "") != (after or ""):
            differences.append(f"{label} text diverged:\n{_unified_diff(before or '', after or '')}")
    return tuple(differences)


def compare_transcript_to_golden(
    transcript: SequenceTranscript,
    golden: SequenceGolden,
    *,
    page: str,
    baseline: SequenceRecord | None = None,
) -> tuple[str, ...]:
    """Compare an executed transcript against its committed golden fingerprint.

    Accumulating: every frame divergence is collected in one pass so a check
    run reports the whole worklist. An empty tuple is a clean pass.

    ``baseline`` is the last verified record of the sequence, if the caller has
    one; its fingerprint must equal ``golden``. It only enriches the report of a
    changed output with what changed, and never decides the verdict.
    """
    problems: list[str] = []
    if transcript.sequence_id != golden.sequence_id:
        problems.append(
            f"page {page!r}: transcript is for sequence {transcript.sequence_id!r} but the "
            f"golden is for {golden.sequence_id!r}",
        )
        return tuple(problems)

    if len(transcript.frames) != len(golden.frames):
        problems.append(
            f"page {page!r} sequence {golden.sequence_id!r}: frame count changed — golden has "
            f"{len(golden.frames)} frames, the executed sequence has {len(transcript.frames)}; "
            "the sequence body and its golden must move together",
        )
        return tuple(problems)

    record = build_record(transcript)
    live = golden_from_record(record)
    baseline_frames = baseline.frames if baseline is not None and len(baseline.frames) == len(golden.frames) else None

    for index, (expected, actual) in enumerate(zip(golden.frames, live.frames, strict=True)):
        at = _frame_locator(page, golden.sequence_id, index, transcript.frames[index])

        if expected.kind is not actual.kind:
            problems.append(f"{at}: frame kind changed from {expected.kind.value!r} to {actual.kind.value!r}")

        if expected.argv != actual.argv:
            problems.append(
                f"{at}: executed argv diverged from the golden (golden: {' '.join(expected.argv)})",
            )

        if expected.exit_code != actual.exit_code:
            problems.append(f"{at}: exit code {actual.exit_code}, golden expects {expected.exit_code}")

        if expected.captures != actual.captures:
            golden_view = {item.name: item.value for item in expected.captures}
            live_view = {item.name: item.value for item in actual.captures}
            problems.append(f"{at}: captured values diverged — golden {golden_view!r}, live {live_view!r}")

        # A setup frame records no output. When a frame changed to or from
        # setup, the kind problem above already names it; an output comparison
        # against the other side's absent fingerprint would only bury it.
        if FrameKind.SETUP in (expected.kind, actual.kind):
            continue

        if expected.envelope_source != actual.envelope_source:
            problems.append(
                f"{at}: the JSON envelope stream changed from {expected.envelope_source or 'none'} "
                f"to {actual.envelope_source or 'none'}",
            )
            continue

        if expected.output_sha256 != actual.output_sha256:
            detail: tuple[str, ...] = ()
            if baseline_frames is not None:
                detail = _output_differences(baseline_frames[index], record.frames[index])
            if detail:
                problems.extend(f"{at}: {item}" for item in detail)
            else:
                problems.append(
                    f"{at}: output changed (golden sha256 {expected.output_sha256}, live "
                    f"{actual.output_sha256}); no verified earlier record is cached to show the difference",
                )
        elif expected.output_bytes != actual.output_bytes:
            # Equal digests always carry equal sizes, so this is a golden edited by hand.
            problems.append(
                f"{at}: recorded output size {actual.output_bytes}, golden records {expected.output_bytes}",
            )

    return tuple(problems)


def evaluate_expectations(
    sequence: ParsedSequence,
    transcript: SequenceTranscript,
    *,
    page: str,
) -> tuple[str, ...]:
    """Evaluate every ``@expect`` assertion against the LIVE executed output.

    The ``exit_code`` pseudo-path asserts the frame's process exit code; every
    other json-path resolves into the frame's live envelope. A failed
    assertion, a missing path, and a non-JSON frame carrying a json-path
    expectation are all named problems. An empty tuple is a clean pass.
    """
    problems: list[str] = []
    # @static frames never run, so they never enter the transcript; expectations
    # are evaluated over the executed frames, aligned 1:1 with the transcript.
    executed = sequence.executed_frames
    if len(executed) != len(transcript.frames):
        problems.append(
            f"page {page!r} sequence {sequence.sequence_id!r}: transcript has "
            f"{len(transcript.frames)} frames for a {len(executed)}-executed-frame sequence; "
            "expectations cannot be evaluated",
        )
        return tuple(problems)

    for index, (frame, execution) in enumerate(zip(executed, transcript.frames, strict=True)):
        at = _frame_locator(page, sequence.sequence_id, index, execution)
        for assertion in frame.expects:
            expected = assertion.expected
            if isinstance(expected, str) and expected.startswith("{") and expected.endswith("}"):
                capture_name = expected[1:-1]
                if capture_name in transcript.captures:
                    expected = transcript.captures[capture_name]
            rendered = json.dumps(expected)
            if assertion.json_path == _EXIT_CODE_PATH:
                if execution.exit_code != expected:
                    problems.append(
                        f"{at}: @expect {_EXIT_CODE_PATH} == {rendered} failed — live exit "
                        f"code is {execution.exit_code}",
                    )
                continue
            if execution.envelope is None:
                problems.append(
                    f"{at}: @expect {assertion.json_path} == {rendered} cannot be evaluated — "
                    "the live output is not a JSON document (invoke the command with "
                    "'--format json')",
                )
                continue
            found, value = _resolve_json_path(execution.envelope, assertion.json_path)
            if not found:
                problems.append(
                    f"{at}: @expect path {assertion.json_path!r} is missing from the live "
                    f"envelope (top-level keys: {', '.join(sorted(execution.envelope))})",
                )
                continue
            if value != expected:
                problems.append(
                    f"{at}: @expect {assertion.json_path} == {rendered} failed — live value "
                    f"is {json.dumps(value, default=str)}",
                )
    return tuple(problems)


def check_transcript(
    sequence: ParsedSequence,
    transcript: SequenceTranscript,
    golden: SequenceGolden,
    *,
    page: str,
    baseline: SequenceRecord | None = None,
) -> tuple[str, ...]:
    """Run the full check tier over one executed sequence.

    Golden comparison (reproducibility) plus live ``@expect`` evaluation
    (meaning), accumulated into one problem list. This is the single function
    both check surfaces — the Sphinx build hook and the pytest gate — call, so
    neither re-implements comparison.
    """
    return compare_transcript_to_golden(transcript, golden, page=page, baseline=baseline) + evaluate_expectations(
        sequence,
        transcript,
        page=page,
    )


def assert_transcript_matches_golden(
    sequence: ParsedSequence,
    transcript: SequenceTranscript,
    golden: SequenceGolden,
    *,
    page: str,
) -> None:
    """Assert the full check tier passes, else raise with every divergence.

    Raises:
        SequenceGoldenMismatchError: Carrying every accumulated problem and the
            exact refresh invocation that updates the golden.
    """
    problems = check_transcript(sequence, transcript, golden, page=page)
    if problems:
        raise SequenceGoldenMismatchError(
            sequence.sequence_id,
            problems,
            remedy=refresh_invocation(sequence_id=sequence.sequence_id),
        )

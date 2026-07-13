"""Golden comparison and semantic expectation evaluation (ADR D3).

One comparison policy per frame kind, applied to an executed
:class:`~dev.docs.sequences._runner.SequenceTranscript` against its committed
:class:`~dev.docs.sequences._golden_store.SequenceGolden`:

- **JSON frames** compare via the shared observability substrate —
  ``canonicalise`` + ``mask_document`` with exactly the central
  ``GOLDEN_MASK_FIELDS`` — over the FULL envelope (shared spine plus result),
  reporting the post-mask ``differing_paths`` on failure. This module
  deliberately exposes NO mask parameter anywhere: the executor never declares
  its own mask set and a sequence cannot carry a per-sequence mask extension
  (the one dishonesty lever the substrate ADR names); a newly nondeterministic
  field is enrolled in the one central set with its anti-tautology proof.
- **Text frames** compare by exact string equality after the declared narrow
  normalisation (:func:`~dev.docs.sequences._golden_store.normalise_text_output`
  — sandbox paths to stable tokens, centrally-masked ids to the sentinel),
  reporting a unified diff on failure. No wildcards, no fuzzy matching, no
  "contains".
- **Exit codes** are asserted on every frame.

``@expect`` assertions are evaluated against the LIVE output
(:func:`evaluate_expectations`), never against the golden: golden equality
proves the output is reproducible; the ``@expect`` proves it *means* success,
so a sequence cannot "verify" by merely reproducing a failure (ADR D4).

Every problem string names the page, the sequence id, the frame index, and the
frame's argv; :func:`assert_transcript_matches_golden` closes with the exact
``refresh`` invocation that updates the golden.
"""

from __future__ import annotations

import difflib
import json

from cadrumo.core.observability import canonicalise, differing_paths, mask_document

from ._errors import SequenceGoldenMismatchError
from ._golden_store import (
    SequenceGolden,
    masked_envelope_values,
    normalise_text_output,
    refresh_invocation,
)
from ._runner import FrameExecution, SequenceTranscript, _resolve_json_path
from ._schema import ParsedSequence

__all__ = [
    "assert_transcript_matches_golden",
    "check_transcript",
    "compare_transcript_to_golden",
    "evaluate_expectations",
]

#: The ``@expect`` pseudo-path asserting a frame's process exit code (ADR D3).
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


def compare_transcript_to_golden(
    transcript: SequenceTranscript,
    golden: SequenceGolden,
    *,
    page: str,
) -> tuple[str, ...]:
    """Compare an executed transcript against its committed golden (ADR D3).

    Accumulating: every frame divergence is collected in one pass so a check
    run reports the whole worklist. An empty tuple is a clean pass.
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

    live_masked_values = masked_envelope_values(transcript)

    for index, (expected, actual) in enumerate(zip(golden.frames, transcript.frames, strict=True)):
        at = _frame_locator(page, golden.sequence_id, index, actual)

        if expected.kind is not actual.kind:
            problems.append(f"{at}: frame kind changed from {expected.kind.value!r} to {actual.kind.value!r}")

        if expected.argv != actual.argv:
            problems.append(
                f"{at}: executed argv diverged from the golden (golden: {' '.join(expected.argv)})",
            )

        if expected.exit_code != actual.exit_code:
            problems.append(f"{at}: exit code {actual.exit_code}, golden expects {expected.exit_code}")

        if expected.captures != actual.captured:
            golden_view = {item.name: item.value for item in expected.captures}
            live_view = {item.name: item.value for item in actual.captured}
            problems.append(f"{at}: captured values diverged — golden {golden_view!r}, live {live_view!r}")

        if expected.envelope is not None:
            if actual.envelope is None:
                problems.append(
                    f"{at}: the golden expects a JSON envelope but the live output is not a "
                    f"JSON document (output starts: {actual.output[:120]!r})",
                )
                continue
            masked_expected = mask_document(expected.envelope)
            masked_actual = mask_document(actual.envelope)
            if canonicalise(masked_expected) != canonicalise(masked_actual):
                diff = ", ".join(sorted(differing_paths(masked_expected, masked_actual)))
                problems.append(f"{at}: envelope diverged at post-mask paths: {diff or '<whole-document>'}")
            continue

        # Text frame: the golden stores normalised text; normalise the live
        # output with THIS run's sandbox paths and masked ids, then compare
        # exactly.
        if actual.envelope is not None:
            problems.append(
                f"{at}: the golden expects text output but the live output is now a JSON envelope",
            )
            continue
        live_text = normalise_text_output(
            actual.output,
            storage_root=transcript.storage_root,
            workdir=transcript.workdir,
            masked_values=live_masked_values,
        )
        expected_text = expected.text if expected.text is not None else ""
        if live_text != expected_text:
            problems.append(f"{at}: text output diverged:\n{_unified_diff(expected_text, live_text)}")

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
    if len(sequence.frames) != len(transcript.frames):
        problems.append(
            f"page {page!r} sequence {sequence.sequence_id!r}: transcript has "
            f"{len(transcript.frames)} frames for a {len(sequence.frames)}-frame sequence; "
            "expectations cannot be evaluated",
        )
        return tuple(problems)

    for index, (frame, execution) in enumerate(zip(sequence.frames, transcript.frames, strict=True)):
        at = _frame_locator(page, sequence.sequence_id, index, execution)
        for assertion in frame.expects:
            rendered = json.dumps(assertion.expected)
            if assertion.json_path == _EXIT_CODE_PATH:
                if execution.exit_code != assertion.expected:
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
            if value != assertion.expected:
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
) -> tuple[str, ...]:
    """Run the full check tier over one executed sequence.

    Golden comparison (reproducibility) plus live ``@expect`` evaluation
    (meaning), accumulated into one problem list. This is the single function
    both check surfaces — the Sphinx build hook and the pytest gate — call, so
    neither re-implements comparison.
    """
    return compare_transcript_to_golden(transcript, golden, page=page) + evaluate_expectations(
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

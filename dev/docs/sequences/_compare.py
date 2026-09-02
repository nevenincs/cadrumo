"""Golden comparison and semantic expectation evaluation.

One comparison policy per frame kind, applied to an executed
:class:`~dev.docs.sequences._runner.SequenceTranscript` against its committed
:class:`~dev.docs.sequences._golden_store.SequenceGolden`:

- **JSON frames** compare via the shared observability substrate —
  ``canonicalise`` + ``mask_document`` with exactly the central
  ``GOLDEN_MASK_FIELDS`` — over the FULL envelope (shared spine plus result),
  reporting the post-mask ``differing_paths`` on failure. The live envelope is
  first path-normalised (``normalise_document_paths``) with THIS run's sandbox
  and checkout paths, matching the tokens the golden baked at build time, so a
  path leaking into a string value (``config check``'s storage-root / corpus-path
  ``detail``) does not diverge every run; this is a value-anchored replacement of
  the known roots, orthogonal to and preceding the central field mask. This
  module exposes NO mask parameter and never overrides ``mask_document``'s central default:
  the executor never declares its own mask set and a sequence cannot carry a
  per-sequence mask extension (the one dishonesty lever the substrate would
  otherwise allow). Both properties are pinned — a signature gate and an AST gate over
  this module's ``mask_document`` calls in ``tests/test_compare.py``, plus the
  executor-level double-run proof in ``dev/docs/tests/test_sequence_goldens.py``
  — so a newly nondeterministic field is enrolled in the one central set with
  its anti-tautology proof, never masked locally.
- **Text frames** compare by exact string equality after the declared narrow
  normalisation (:func:`~dev.docs.sequences._golden_store.normalise_text_output`
  — sandbox paths to stable tokens, centrally-masked ids to the sentinel),
  reporting a unified diff on failure. No wildcards, no fuzzy matching, no
  "contains".
- **Exit codes** are asserted on every frame.

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

from ._golden_store import (
    SequenceGolden,
    mask_host_conditional_details,
    masked_envelope_values,
    normalise_document_paths,
    normalise_text_output,
    refresh_invocation,
)
from ._runner import FrameExecution, SequenceTranscript, _resolve_json_path
from ._schema import ParsedSequence
from .errors import SequenceGoldenMismatchError

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


def compare_transcript_to_golden(
    transcript: SequenceTranscript,
    golden: SequenceGolden,
    *,
    page: str,
) -> tuple[str, ...]:
    """Compare an executed transcript against its committed golden.

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

        # Envelope tier: golden and live must agree on whether a JSON envelope
        # exists and on which stream carried it (a success envelope moving to
        # a stderr error document — or vice versa — is a behavioural change).
        if expected.envelope is not None:
            if actual.envelope is None:
                problems.append(
                    f"{at}: the golden expects a JSON envelope (on {expected.envelope_source}) "
                    f"but the live output carries none "
                    f"(stdout starts: {actual.output[:120]!r})",
                )
            else:
                if expected.envelope_source != actual.envelope_source:
                    problems.append(
                        f"{at}: the envelope moved streams — golden on "
                        f"{expected.envelope_source}, live on {actual.envelope_source}",
                    )
                # The golden's envelope was path-normalised at build time; the
                # live envelope carries THIS run's raw sandbox/checkout paths, so
                # tokenise it the same value-anchored way before the central field
                # mask — otherwise a path leaking into a string value (config
                # check's storage-root / corpus-path detail) diverges every run.
                live_envelope = normalise_document_paths(
                    actual.envelope,
                    storage_root=transcript.storage_root,
                    workdir=transcript.workdir,
                )
                # Same platform-conditional carve-out the text tier applies, at
                # the structural tier: each side's own detail is masked, so the
                # row's id and verdict stay under exact comparison while the
                # sentence describing the HOST drops out of both.
                masked_expected = mask_host_conditional_details(mask_document(expected.envelope))
                masked_actual = mask_host_conditional_details(mask_document(live_envelope))
                assert isinstance(masked_expected, Mapping)
                assert isinstance(masked_actual, Mapping)
                if canonicalise(masked_expected) != canonicalise(masked_actual):
                    diff = ", ".join(sorted(differing_paths(masked_expected, masked_actual)))
                    problems.append(f"{at}: envelope diverged at post-mask paths: {diff or '<whole-document>'}")
        elif actual.envelope is not None:
            problems.append(
                f"{at}: the golden expects no JSON envelope but the live output now carries "
                f"one on {actual.envelope_source}",
            )

        # Text tier: each stream that did not carry the envelope compares by
        # exact equality after the declared narrow normalisation (the golden
        # stores normalised text; the live side normalises with THIS run's
        # sandbox paths and masked ids). ``None`` reads as the empty stream.
        def _normalised_live(raw: str) -> str:
            return normalise_text_output(
                raw,
                storage_root=transcript.storage_root,
                workdir=transcript.workdir,
                masked_values=live_masked_values,
            )

        if actual.envelope_source != "stdout" and expected.envelope_source != "stdout":
            live_text = _normalised_live(actual.output)
            expected_text = expected.text if expected.text is not None else ""
            if live_text != expected_text:
                problems.append(f"{at}: stdout text diverged:\n{_unified_diff(expected_text, live_text)}")

        if actual.envelope_source != "stderr" and expected.envelope_source != "stderr":
            live_stderr = _normalised_live(actual.stderr)
            expected_stderr = expected.stderr_text if expected.stderr_text is not None else ""
            if live_stderr != expected_stderr:
                problems.append(f"{at}: stderr text diverged:\n{_unified_diff(expected_stderr, live_stderr)}")

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

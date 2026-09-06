"""Errors raised by the ``cli-sequence`` execution engine.

These errors are deliberately NOT part of the
:class:`cadrumo.core.errors.hierarchy.CadrumoError` hierarchy. That hierarchy exists for
operator-facing runtime failures that need a registered
:class:`~cadrumo.core.errors.error_codes.ErrorCode`, a translated message, and
JSON-envelope redaction at the CLI boundary. The sequence engine is build-time
documentation tooling: a malformed ``cli-sequence`` directive is an author / CI
failure surfaced as a stack trace, exactly like the docs build itself. Subclassing
:class:`ValueError` keeps the engine self-contained and avoids enrolling a
build-tooling error into the runtime error-code registry.

:class:`SequenceParseError` is *accumulating*: the parser collects every grammar
and structural violation it can find in a single pass and raises one error that
enumerates them all, each naming the offending line, rather than aborting on
the first fault. An author fixing a directive sees the whole worklist at once.
"""

from __future__ import annotations

from collections.abc import Sequence

__all__ = [
    "SequenceEngineError",
    "SequenceExecutionError",
    "SequenceGoldenError",
    "SequenceGoldenMismatchError",
    "SequenceParseError",
]


class SequenceEngineError(ValueError):
    """Base error for every ``cli-sequence`` engine failure mode."""


class SequenceExecutionError(SequenceEngineError):
    """Raised when a structurally valid sequence cannot execute hermetically.

    Unlike :class:`SequenceParseError` this is fail-fast, not accumulating: the
    runner stops at the first frame whose execution is structurally impossible
    (an unexpected exit code, a ``@capture`` against non-JSON output, a capture
    json-path missing from the envelope, a live-AEAT frame) because every later
    frame would run against a corrupted premise. The message carries the
    sequence id and a locator-prefixed detail naming the offending frame.
    """

    def __init__(self, sequence_id: str, detail: str) -> None:
        self.sequence_id = sequence_id
        self.detail = detail
        super().__init__(f"cli-sequence {sequence_id!r} failed to execute: {detail}")


class SequenceGoldenError(SequenceEngineError):
    """Raised when a committed golden cannot be located, read, or validated.

    Every message names the remedy — the exact ``refresh`` invocation — because
    goldens are CLI-owned artifacts: a missing or hand-corrupted golden is fixed
    by regeneration, never by hand-editing.
    """


class SequenceGoldenMismatchError(SequenceEngineError):
    """Raised when an executed transcript diverges from its committed golden.

    Accumulating, like :class:`SequenceParseError`: ``problems`` carries every
    frame divergence found in one comparison pass (each naming the page, the
    sequence id, the frame index and argv, and the post-mask differing paths or
    unified text diff), and the message closes with the exact refresh
    invocation that updates the golden.
    """

    def __init__(self, sequence_id: str, problems: Sequence[str], *, remedy: str) -> None:
        self.sequence_id = sequence_id
        self.problems: tuple[str, ...] = tuple(problems)
        self.remedy = remedy
        joined = "\n".join(f"  - {problem}" for problem in self.problems)
        super().__init__(
            f"cli-sequence {sequence_id!r} diverged from its committed golden:\n{joined}\n"
            f"If the new behaviour is intended, refresh the golden with: {remedy}",
        )


class SequenceParseError(SequenceEngineError):
    """Raised when a ``cli-sequence`` directive body violates the frame grammar.

    Carries the sequence id and the full, ordered list of accumulated problem
    messages so the rendered error names every fault in one pass. The string
    form enumerates each problem under the sequence id.
    """

    def __init__(self, sequence_id: str, problems: Sequence[str]) -> None:
        self.sequence_id = sequence_id
        self.problems: tuple[str, ...] = tuple(problems)
        joined = "\n".join(f"  - {problem}" for problem in self.problems)
        super().__init__(f"cli-sequence {sequence_id!r} is invalid:\n{joined}")

"""Errors raised by the ``cli-sequence`` execution engine.

These errors are deliberately NOT part of the
:class:`cadrumo.core.errors.AeatError` hierarchy. That hierarchy exists for
operator-facing runtime failures that need a registered
:class:`~cadrumo.core.errors.ErrorCode`, a translated message, and
JSON-envelope redaction at the CLI boundary. The sequence engine is build-time
documentation tooling: a malformed ``cli-sequence`` directive is an author / CI
failure surfaced as a stack trace, exactly like the docs build itself. Subclassing
:class:`ValueError` keeps the engine self-contained and avoids enrolling a
build-tooling error into the runtime error-code registry.

:class:`SequenceParseError` is *accumulating*: the parser collects every grammar
and structural violation it can find in a single pass and raises one error that
enumerates them all, each naming the offending line, rather than aborting on the
first fault. An author fixing a directive sees the whole worklist at once.
"""

from __future__ import annotations

from collections.abc import Sequence

__all__ = ["SequenceEngineError", "SequenceExecutionError", "SequenceParseError"]


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

"""Refuse a record that captured a crash, an undeclared failure, or a frozen version.

A golden fingerprints the output a run produced. Fingerprinting a crash inverts
the gate: ``check`` then passes while the fault is live and fails once it is
fixed. Refresh and check therefore judge every record before it can become a
golden or be rendered:

- **Crash markers** (:func:`crash_findings`) are shapes only a crash or an
  internal fault produces: a Python traceback or source frame, a logging-error
  block, an unraisable-exception report, or an ``INTERNAL`` error category or
  code. An ordinary refusal is not one of them; the CLI's error document is
  legitimate recorded output and many sequences assert one deliberately.
- **Undeclared error outcomes** (:func:`undeclared_error_findings`) are frames
  that recorded an error envelope or a non-zero exit while their ``@expect`` set
  claims neither an ``exit_code`` nor an ``error``-rooted path. A documented
  refusal declares itself; an error nobody asserted is a broken state recorded
  as the expectation.
- **Version literals** (:func:`version_literal_findings`) are a captured
  product banner such as ``CADRUMO 0.2.1``. Pages render from records, so a
  captured version is a hardcoded version in user-facing prose that rots at the
  next release; text normalisation stores the version as a token and rendering
  resolves it, so a literal means that path was bypassed.

Every carrier is read: the JSON envelope, the stdout text and the stderr text.
"""

from __future__ import annotations

import json
import re
from typing import Final

from .record_store import RecordFrame, SequenceRecord
from .schema import FrameKind, ParsedSequence

__all__ = [
    "FAILURE_MARKERS",
    "VERSION_LITERAL",
    "crash_findings",
    "recorded_output_text",
    "undeclared_error_findings",
    "version_literal_findings",
]

#: Patterns that mean recorded output captures a FAILURE rather than behaviour.
FAILURE_MARKERS: Final[dict[str, re.Pattern[str]]] = {
    "traceback": re.compile(r"Traceback \(most recent call last\)"),
    "source_frame": re.compile(r'File "[^"]*(?:<repo-root>|src[/\\]cadrumo)'),
    "logging_error": re.compile(r"--- Logging error ---"),
    "unraisable": re.compile(r"Exception ignored in"),
    "internal_category": re.compile(r'"category"\s*:\s*"INTERNAL"'),
    "internal_code": re.compile(r"\bINTERNAL_[A-Z_]+"),
}

#: A captured package version in the product banner form. Value-shaped, not a
#: bare number, so an unrelated numeric in recorded output is never mistaken for one.
VERSION_LITERAL: Final[re.Pattern[str]] = re.compile(r"CADRUMO \d+\.\d+\.\d+")

#: An error-envelope shape in a frame's recorded output.
_ERROR_OUTCOME: Final[re.Pattern[str]] = re.compile(r'"status"\s*:\s*"error"|"error"\s*:\s*\{')


def recorded_output_text(frame: RecordFrame) -> str:
    """Return every recorded carrier of ``frame`` as one string: envelope, stdout, stderr."""
    parts = [frame.text or "", frame.stderr_text or ""]
    if frame.envelope is not None:
        parts.append(json.dumps(frame.envelope, ensure_ascii=False))
    return "\n".join(part for part in parts if part)


def crash_findings(record: SequenceRecord, *, page: str) -> tuple[str, ...]:
    """Name every frame of ``record`` whose recorded output carries a crash marker."""
    findings: list[str] = []
    for index, frame in enumerate(record.frames):
        text = recorded_output_text(frame)
        for name, pattern in FAILURE_MARKERS.items():
            match = pattern.search(text)
            if match is not None:
                findings.append(
                    f"page {page!r} sequence {record.sequence_id!r} frame {index} (argv: {' '.join(frame.argv)}): "
                    f"the output records a crash or internal fault ({name}: {match.group(0)[:70]!r}); a golden "
                    "of it would pass while the fault is live, so fix the fault instead of recording it",
                )
    return tuple(findings)


def undeclared_error_findings(sequence: ParsedSequence, record: SequenceRecord, *, page: str) -> tuple[str, ...]:
    """Name every frame that recorded an error outcome its ``@expect`` set does not claim."""
    executed = [frame for frame in sequence.frames if frame.kind is not FrameKind.STATIC]
    if len(executed) != len(record.frames):
        return ()
    findings: list[str] = []
    for index, (parsed, frame) in enumerate(zip(executed, record.frames, strict=True)):
        if frame.exit_code == 0 and not _ERROR_OUTCOME.search(recorded_output_text(frame)):
            continue
        if any(
            assertion.json_path == "exit_code" or assertion.json_path.startswith("error")
            for assertion in parsed.expects
        ):
            continue
        findings.append(
            f"page {page!r} sequence {record.sequence_id!r} frame {index} (argv: {' '.join(frame.argv)}): "
            f"the output records a failing outcome (exit {frame.exit_code}) the frame never declares; assert it "
            "with '@expect exit_code == <n>' or an '@expect error...' path when the refusal is the point, or "
            "fix the cause",
        )
    return tuple(findings)


def version_literal_findings(record: SequenceRecord, *, page: str) -> tuple[str, ...]:
    """Name every frame of ``record`` whose recorded output carries a hardcoded package version."""
    return tuple(
        f"page {page!r} sequence {record.sequence_id!r} frame {index} (argv: {' '.join(frame.argv)}): "
        f"the output carries the version literal {match.group(0)!r}, which would render as a frozen version; "
        "print the version through the normalised text output instead"
        for index, frame in enumerate(record.frames)
        for match in VERSION_LITERAL.finditer(recorded_output_text(frame))
    )

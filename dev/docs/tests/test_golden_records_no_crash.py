"""Gate: no committed golden may record a crash as its expected output.

A golden captured while the process was crashing INVERTS the gate it belongs to.
`check` compares a later run against the committed text, so a golden holding a
traceback goes GREEN on the breakage and RED on the repair — the exact opposite
of what a regression gate is for. One instance shipped: `filing-spine-file`
frames 8-9 recorded a storage-fault traceback, captured while the fault was live,
and was re-recorded in commit `7991f30d19`.

This is the executed-frame counterpart to the `@static` blocked-reason gates. A
static frame is now forced to state why it does not run; an executed frame whose
recorded output was a crash had nothing forcing it to say so. Both close the same
hazard from opposite sides: output that documents a failure while presenting as
truth.

SELF-VERIFICATION IS PART OF THE CONTRACT. A scanner that reads nothing reports
zero findings and passes, which is indistinguishable from a clean corpus. During
this gate's own development a first scanner read the wrong frame keys, returned
"0 hits" across 189 goldens, and was only caught by a positive control. So
:func:`test_golden_scan_actually_reads_captured_output` runs first and asserts the
reader sees real bytes and real known tokens; a clean result from
:func:`test_no_golden_records_a_crash_as_expected_output` is only meaningful
because that check passes alongside it.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

from dev.docs.sequences import default_docs_root

pytestmark = [pytest.mark.integration, pytest.mark.hex_core, pytest.mark.docs]

#: Patterns that mean the captured text records a FAILURE rather than behaviour.
#: Each is anchored on a shape only a crash or an internal fault produces — never
#: on an ordinary refusal, which is legitimate golden content (the CLI's error
#: document is a first-class artifact and many sequences assert one deliberately).
_FAILURE_MARKERS: dict[str, re.Pattern[str]] = {
    "traceback": re.compile(r"Traceback \(most recent call last\)"),
    "source_frame": re.compile(r'File "[^"]*(?:<repo-root>|src[/\\]cadrumo)'),
    "logging_error": re.compile(r"--- Logging error ---"),
    "unraisable": re.compile(r"Exception ignored in"),
    "internal_category": re.compile(r'"category"\s*:\s*"INTERNAL"'),
    "internal_code": re.compile(r"\bINTERNAL_[A-Z_]+"),
}

#: Tokens known to occur across the golden corpus. If none appears, the reader is
#: not seeing the data and every negative result above is vacuous.
_CONTROL_TOKENS: tuple[str, ...] = ("docs-sequence-sandbox", "operation")


def _golden_paths() -> list[Path]:
    """Every committed sequence golden, excluding authoring inputs."""
    root = default_docs_root() / "_sequences"
    return [
        path
        for path in sorted(root.rglob("*.json"))
        if "contracts" not in path.parts and "fixtures" not in path.parts
    ]


def _captured_text(document: dict[str, object]) -> str:
    """Return every byte the golden holds as recorded output.

    Text rides ``text`` / ``stderr_text``, and a JSON frame carries its parsed
    ``envelope`` instead, so all three carriers are read. Missing the envelope is
    what made the first version of this scanner blind.
    """
    frames = document.get("frames")
    if not isinstance(frames, list):
        return ""
    parts: list[str] = []
    for frame in frames:
        if not isinstance(frame, dict):
            continue
        for key in ("text", "stderr_text"):
            value = frame.get(key)
            if isinstance(value, str):
                parts.append(value)
        envelope = frame.get("envelope")
        if envelope is not None:
            parts.append(json.dumps(envelope, ensure_ascii=False))
    return "\n".join(parts)


def _read_corpus() -> list[tuple[Path, str]]:
    """Return ``(path, captured_text)`` for every readable golden."""
    corpus: list[tuple[Path, str]] = []
    for path in _golden_paths():
        try:
            document = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:  # pragma: no cover - a corrupt golden is its own failure
            pytest.fail(f"unreadable golden {path}: {exc}")
        if isinstance(document, dict) and "frames" in document:
            corpus.append((path, _captured_text(document)))
    return corpus


def test_golden_scan_actually_reads_captured_output() -> None:
    """The reader sees real bytes and real known tokens.

    This is the anti-vacuity proof for the gate below, and it is not theoretical:
    a scanner reading the wrong frame keys reported a clean corpus of 189 goldens
    while having read zero characters.
    """
    corpus = _read_corpus()
    assert corpus, "no goldens were discovered; the gate below would pass vacuously"
    total = sum(len(text) for _, text in corpus)
    assert total > 0, (
        f"read {len(corpus)} goldens but zero characters of captured output; "
        "the frame carriers ('text', 'stderr_text', 'envelope') are not being read"
    )
    found = {token: sum(1 for _, text in corpus if token in text) for token in _CONTROL_TOKENS}
    assert any(found.values()), (
        "no control token appeared anywhere in the captured output, so the reader "
        f"is not seeing golden content: {found}"
    )


def test_no_golden_records_a_crash_as_expected_output() -> None:
    """No committed golden holds a traceback or internal fault as its expectation.

    Such a golden asserts the breakage, so `check` passes while the defect is
    present and fails once it is fixed. An ordinary refusal is NOT a finding here:
    the CLI's error document is legitimate golden content, and the markers are
    anchored on crash shapes rather than on non-zero exits.
    """
    offenders: list[str] = []
    for path, text in _read_corpus():
        for name, pattern in _FAILURE_MARKERS.items():
            match = pattern.search(text)
            if match is not None:
                relative = path.relative_to(default_docs_root())
                offenders.append(f"{relative.as_posix()}: {name} -> {match.group(0)[:70]!r}")
    assert offenders == [], (
        "these goldens record a crash or internal fault as their expected output, which "
        "inverts their gate (green on the breakage, red on the repair). Fix the underlying "
        "fault, then re-record with "
        "'python -m dev.docs.sequences refresh --page <docname>':\n  " + "\n  ".join(offenders)
    )

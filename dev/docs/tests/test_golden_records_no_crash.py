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

from cadrumo.core.directory_scan import scan_directory

from ...quality.unread_inputs import report_unread
from ..sequences.checks import default_docs_root, discover_sequences
from ..sequences.golden_store import read_golden
from ..sequences.schema import FrameKind

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
        for path in scan_directory(root, pattern="*.json", recursive=True)
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


def _captured_lengths(document: dict[str, object]) -> dict[str, int]:
    """Return characters read PER CARRIER, so a total cannot hide one dying.

    Measured across the live corpus the carriers are wildly unequal: the
    envelope holds 15,752,565 characters (98.2%), text 290,627 (1.8%) and
    stderr_text none at all. A floor on their sum therefore proves only that
    the envelope is being read - losing text entirely still leaves 98% of the
    total standing.
    """
    lengths = {"text": 0, "stderr_text": 0, "envelope": 0}
    frames = document.get("frames")
    if not isinstance(frames, list):
        return lengths
    for frame in frames:
        if not isinstance(frame, dict):
            continue
        for key in ("text", "stderr_text"):
            value = frame.get(key)
            if isinstance(value, str):
                lengths[key] += len(value)
        envelope = frame.get("envelope")
        if envelope is not None:
            lengths["envelope"] += len(json.dumps(envelope, ensure_ascii=False))
    return lengths


def _read_corpus() -> list[tuple[Path, str]]:
    """Return ``(path, captured_text)`` for every readable golden.

    Refuses an empty corpus at the source: the gate over it asserts no golden
    records a crash as expected output, and no crash marker can be found in
    nothing.
    """
    corpus: list[tuple[Path, str]] = []
    for path in _golden_paths():
        try:
            document = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:  # pragma: no cover - a corrupt golden is its own failure
            pytest.fail(f"unreadable golden {path}: {exc}")
        if isinstance(document, dict) and "frames" in document:
            corpus.append((path, _captured_text(document)))
    assert corpus, "the golden-record corpus is empty; no crash marker can be found in nothing"
    return corpus


def test_golden_scan_actually_reads_captured_output() -> None:
    """The reader sees real bytes and real known tokens.

    This is the anti-vacuity proof for the gate below, and it is not theoretical:
    a scanner reading the wrong frame keys reported a clean corpus of 189 goldens
    while having read zero characters.
    """
    corpus = _read_corpus()
    # The historical defect was 189 goldens and ZERO characters, so `> 0`
    # closed exactly that. It does not close the partial case: a reader
    # taking one frame carrier of three, or only the first golden, still
    # returns millions of characters and passes. Floors, not pinned counts:
    # live the corpus holds 206 goldens and 16,043,894 captured characters,
    # a mean of about 78,000 each.
    assert len(corpus) > 150, (
        f"only {len(corpus)} goldens were discovered; the gate below is measured over a fraction of the recorded corpus"
    )
    # Per carrier, because the total is 98% envelope: a floor on the sum
    # proves only that the envelope is read, and losing `text` entirely
    # leaves 15.75M characters standing. Live: envelope 15,752,565, text
    # 290,627, stderr_text 0 - so stderr_text carries nothing in this corpus
    # and no character floor can prove it is being read at all.
    carriers = {
        "text": 0,
        "stderr_text": 0,
        "envelope": 0,
    }
    for path, _text in corpus:
        for key, value in _captured_lengths(json.loads(path.read_text(encoding="utf-8"))).items():
            carriers[key] += value
    assert carriers["envelope"] > 10_000_000, carriers
    assert carriers["text"] > 150_000, carriers

    total = sum(len(text) for _, text in corpus)
    assert total > 5_000_000, (
        f"read {len(corpus)} goldens but only {total} characters of captured output; "
        "the frame carriers ('text', 'stderr_text', 'envelope') are not all being read"
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


#: An error-envelope shape in a frame's recorded output. Unlike the crash markers,
#: these are LEGITIMATE when the frame declares them — a documented refusal is
#: valuable golden content, not a defect.
#: Below this the scan has stopped covering the corpus. Live: 206 of 277
#: discovered sequences reach the per-frame check, the other 71 being static
#: with no executed frame to judge. A floor rather than a pinned count, so
#: authoring or retiring a sequence does not touch this file.
_MINIMUM_EXAMINED_SEQUENCES: int = 150

_ERROR_OUTCOME = re.compile(r'"status"\s*:\s*"error"|"error"\s*:\s*\{')


def test_a_recorded_error_outcome_is_declared_by_the_frame() -> None:
    """A golden holding an error outcome must have DECLARED it, not merely recorded it.

    This is the semantic half of the crash-golden hazard, reduced to something
    mechanical. "Contains an error" is the wrong discriminator: the sole frame in
    the corpus that records one is ``correct-remove-transaction`` frame 3, whose
    ``@step`` reads "Confirm the id no longer resolves." and which declares
    ``@expect error.category == "REFUSED"`` and ``@expect exit_code == 2``. Its
    outcome AGREES with its documented intent, and that agreement is exactly what
    makes it correct.

    The inversion is an error nobody asserted. So the check is whether the frame's
    own ``@expect`` set claims the failure — an ``exit_code`` expectation or an
    ``error``-rooted path. The runner already refuses an undeclared non-zero exit
    at execution time, which is why the corpus is clean rather than merely lucky;
    this asserts the same invariant over committed bytes, so weakening that
    runtime guard cannot silently let an unasserted failure become an expectation.
    """
    discovered, problems = discover_sequences(docs_root=default_docs_root())
    assert not problems, "sequence discovery reported problems:\n  " + "\n  ".join(problems)

    undeclared: list[str] = []
    # Both deferrals below are correct about OWNERSHIP and silent about
    # CONSEQUENCE: a sequence dropped for either reason is never examined for an
    # unasserted failure, which is the one thing this gate exists to find. With
    # no record, a corpus that lost every golden would still report clean.
    unchecked: list[str] = []
    examined = 0
    for item in discovered:
        executed = [frame for frame in item.sequence.frames if frame.kind is not FrameKind.STATIC]
        if not executed:
            continue
        try:
            golden = read_golden(item.page, item.sequence_id)
        except Exception as refusal:
            unchecked.append(f"{item.sequence_id}: golden unreadable ({type(refusal).__name__})")
            continue
        recorded = list(golden.frames)
        if len(recorded) != len(executed):
            # frame-count alignment is the golden store's own contract
            unchecked.append(f"{item.sequence_id}: {len(recorded)} recorded frames against {len(executed)} executed")
            continue
        examined += 1
        for index, (parsed, frame) in enumerate(zip(executed, recorded, strict=True)):
            payload = frame.model_dump() if hasattr(frame, "model_dump") else dict(frame)
            text = _captured_text({"frames": [payload]})
            if not _ERROR_OUTCOME.search(text) and payload.get("exit_code", 0) == 0:
                continue
            declares = any(
                assertion.json_path == "exit_code" or assertion.json_path.startswith("error")
                for assertion in parsed.expects
            )
            if not declares:
                undeclared.append(
                    f"{item.page}/{item.sequence_id} frame {index} "
                    f"(exit {payload.get('exit_code')}): {' '.join(parsed.argv)[:80]}"
                )
    report_unread(
        "unasserted-failure golden scan",
        "these sequences were not examined, so a failing outcome recorded in one and declared "
        "by nothing would not appear below",
        unchecked,
    )
    assert examined >= _MINIMUM_EXAMINED_SEQUENCES, (
        f"only {examined} sequence(s) reached the per-frame check, against {len(discovered)} "
        "discovered. Below this the corpus has effectively stopped being read and a clean "
        "result says nothing about whether a failure went undeclared"
    )
    assert undeclared == [], (
        "these goldens record a failing outcome that their frame never declared, so the "
        "broken state has become the expectation. Either assert it deliberately "
        "('@expect exit_code == <n>' and/or '@expect error.category == \"...\"') when the "
        "refusal is the point, or fix the cause and re-record:\n  " + "\n  ".join(undeclared)
    )

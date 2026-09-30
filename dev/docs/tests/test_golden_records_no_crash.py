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
from dev.quality.unread_inputs import report_unread

from ..sequences.checks import default_docs_root, discover_sequences
from ..sequences.golden_store import read_golden
from ..sequences.json_layout import format_sequence_json
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

    The carriers are unequal in size, so a check on their sum proves only that
    the largest one is being read.
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


#: Keys every recorded frame carries together; an envelope's own objects do not.
_FRAME_KEYS: frozenset[str] = frozenset({"argv", "captures", "exit_code", "kind"})


def _decoded_carrier_lengths(raw: str) -> dict[str, int]:
    """Measure each carrier by a second traversal, independent of the reader.

    The reader walks ``document["frames"]``. Here the JSON decoder reports every
    object carrying a frame's keys as it is parsed, wherever it sits and however
    the file is laid out. Two derivations that agree on every golden prove the
    reader saw every frame of every carrier, which no corpus-size floor can.
    """
    lengths = {"text": 0, "stderr_text": 0, "envelope": 0}

    def _measure_frame(pairs: list[tuple[str, object]]) -> dict[str, object]:
        node = dict(pairs)
        if node.keys() >= _FRAME_KEYS:
            for key in ("text", "stderr_text"):
                value = node.get(key)
                if isinstance(value, str):
                    lengths[key] += len(value)
            envelope = node.get("envelope")
            if envelope is not None:
                lengths["envelope"] += len(json.dumps(envelope, ensure_ascii=False))
        return node

    json.loads(raw, object_pairs_hook=_measure_frame)
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


def test_decoded_measurement_catches_a_reader_that_skips_frames() -> None:
    """The independent measurement disagrees with a reader that drops later frames.

    Written in the golden writer's layout, with an envelope that nests its own
    ``text`` key, so only frame-level carriers are shown to count.
    """
    frame = {
        "argv": ["aeat", "--format", "json", "app", "overview", "status"],
        "captures": [],
        "envelope": {"result": {"text": "nested, not a carrier"}, "status": "ok"},
        "envelope_source": "stdout",
        "exit_code": 0,
        "kind": "command",
        "stderr_text": "warning line\n",
        "text": None,
    }
    text_frame = {**frame, "envelope": None, "envelope_source": None, "text": 'plain "quoted" output\n'}
    document: dict[str, object] = {"frames": [frame, text_frame], "golden_schema_version": 2, "sequence_id": "teeth"}
    raw = format_sequence_json(document) + "\n"

    assert _decoded_carrier_lengths(raw) == _captured_lengths(document)
    first_frame_only: dict[str, object] = {**document, "frames": [frame]}
    assert _captured_lengths(first_frame_only) != _decoded_carrier_lengths(raw)


def test_golden_scan_actually_reads_captured_output() -> None:
    """The reader sees real bytes and real known tokens.

    This is the anti-vacuity proof for the gate below, and it is not theoretical:
    a scanner reading the wrong frame keys reported a clean corpus of 189 goldens
    while having read zero characters.
    """
    corpus = _read_corpus()
    # The historical defect was 189 goldens and ZERO characters. The partial
    # case is subtler: a reader taking one carrier of three, the first frame
    # only, or the first golden only still returns plenty of characters. So
    # every golden's reader measurement must equal an independent measurement
    # of its raw bytes, carrier by carrier.
    assert len(corpus) > 150, (
        f"only {len(corpus)} goldens were discovered; the gate below is measured over a fraction of the recorded corpus"
    )
    carriers = {"text": 0, "stderr_text": 0, "envelope": 0}
    disagreements: list[str] = []
    for path, _text in corpus:
        raw = path.read_text(encoding="utf-8")
        read = _captured_lengths(json.loads(raw))
        measured = _decoded_carrier_lengths(raw)
        if read != measured:
            disagreements.append(f"{path.name}: reader {read}, decoder {measured}")
        for key, value in read.items():
            carriers[key] += value
    assert disagreements == [], "the reader missed recorded output:\n  " + "\n  ".join(disagreements)
    # Positive control: both populated carriers are exercised by the corpus, so
    # the agreement above is not two zeros agreeing.
    assert carriers["envelope"] > 0, carriers
    assert carriers["text"] > 0, carriers
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

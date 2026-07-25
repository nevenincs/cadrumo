"""Honesty gates over the ``@static`` blocked-reason corpus.

A ``@static`` frame is a documented command the engine never runs, so nothing
proves it still works. That is admissible only where hermetic execution is
genuinely impossible — and the corpus can only be trusted if each such frame
SAYS WHY, in terms a reader can check. A bare marker is indistinguishable from a
frame nobody converted, and that ambiguity is how a documented dead end hid: the
quickstart export sequence sat ``@static`` and unexercised until its narrative
was found to have no working path at all.

Three gates, mirroring the fixture-provenance discipline (declare it, then
cross-check the declaration against physical evidence):

- **Stated.** The parser already refuses a reason-less ``@static`` frame, so
  discovery parsing clean is itself the first gate; this module asserts the
  corpus-wide invariant directly so the guarantee is visible where it is relied
  on.
- **Cross-checked.** ``live-aeat`` is declared if and only if the frame's own
  argv carries a live-AEAT token, computed by the runner's own scan. A live
  frame mislabelled as a TTY problem, or a purely local frame excused as
  "live AEAT", both fail here.
- **Ratcheted.** ``unconverted`` asserts NO blocker — it is a visible debt, not
  a justification — so its per-page count may never exceed the committed
  baseline. Converting frames tightens the baseline toward zero.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from dev.docs.sequences import (
    FrameKind,
    StaticBlocker,
    default_docs_root,
    discover_sequences,
    live_aeat_tokens,
)

pytestmark = [pytest.mark.integration, pytest.mark.hex_core, pytest.mark.docs]

_BASELINE_PATH = Path(__file__).resolve().parent / "unconverted_static_baseline.json"


def _static_frames() -> list[tuple[str, str, object]]:
    """Return every ``(page, sequence_id, frame)`` triple of static frames."""
    discovered, problems = discover_sequences(docs_root=default_docs_root())
    assert not problems, "sequence discovery reported problems:\n  " + "\n  ".join(problems)
    return [
        (item.page, item.sequence_id, frame)
        for item in discovered
        for frame in item.sequence.frames
        if frame.kind is FrameKind.STATIC
    ]


def test_every_static_frame_states_a_blocked_reason() -> None:
    """No enrolled ``@static`` frame ships without its reason.

    The parser enforces this at parse time, so a violation cannot reach here
    through the normal path; asserting it directly keeps the corpus-wide
    guarantee visible rather than implicit in a discovery side effect.
    """
    offenders = [
        f"{page}/{sequence_id} line {frame.line_number}: {frame.command_line}"
        for page, sequence_id, frame in _static_frames()
        if frame.blocked is None
    ]
    assert offenders == [], (
        "every @static frame must state why it is not executed with a "
        "'@blocked <code> <detail>' line:\n  " + "\n  ".join(offenders)
    )


def test_live_aeat_reason_matches_the_frames_own_argv() -> None:
    """``live-aeat`` is declared exactly when the argv carries a live-AEAT token.

    Both directions are enforced against the runner's OWN token scan — the same
    function that refuses a live frame at execution — so the declared reason
    cannot drift from the mechanical fact. A local frame excused as "live AEAT"
    would hide a convertible frame behind an unfalsifiable claim; a live frame
    labelled anything else misstates why it is undocumented truth.
    """
    mislabelled: list[str] = []
    unlabelled: list[str] = []
    for page, sequence_id, frame in _static_frames():
        assert frame.blocked is not None
        where = f"{page}/{sequence_id} line {frame.line_number}: {frame.command_line}"
        tokens = live_aeat_tokens(frame)
        declares_live = frame.blocked.code is StaticBlocker.LIVE_AEAT
        if declares_live and not tokens:
            mislabelled.append(where)
        elif tokens and not declares_live:
            unlabelled.append(f"{where} (live tokens: {', '.join(tokens)})")
    assert mislabelled == [], (
        "these @static frames claim 'live-aeat' but carry no live-AEAT argv token; "
        "the sandbox would run them, so state the real blocker or convert them:\n  "
        + "\n  ".join(mislabelled)
    )
    assert unlabelled == [], (
        "these @static frames carry a live-AEAT argv token but declare another blocker; "
        f"the runner refuses them for being live, so declare '{StaticBlocker.LIVE_AEAT.value}':\n  "
        + "\n  ".join(unlabelled)
    )


def test_unconverted_static_frames_do_not_exceed_their_baseline() -> None:
    """No page carries more ``unconverted`` static frames than its committed baseline.

    ``unconverted`` is the honest marker for "nothing blocks this; it simply has
    not been converted yet". It is debt, so it ratchets DOWN: a converter turns
    frames into executed truth and tightens the entry. A page below its baseline
    passes, so a partial sweep never reds the tree. An empty baseline means every
    remaining static frame is blocked for a verified reason.
    """
    baseline: dict[str, int] = json.loads(_BASELINE_PATH.read_text(encoding="utf-8"))
    current: dict[str, int] = {}
    for page, _sequence_id, frame in _static_frames():
        assert frame.blocked is not None
        if frame.blocked.code is StaticBlocker.UNCONVERTED:
            current[page] = current.get(page, 0) + 1
    problems = [
        f"{page}: {count} unconverted @static frame(s), baseline allows {baseline.get(page, 0)}"
        for page, count in sorted(current.items())
        if count > baseline.get(page, 0)
    ]
    assert not problems, (
        "unconverted @static frames must ratchet down, never up. Convert the frame to "
        "executed truth (and regenerate its golden), or — if it is genuinely blocked — "
        f"declare the real blocker instead of '{StaticBlocker.UNCONVERTED.value}'. "
        f"Then tighten {_BASELINE_PATH.name}:\n  " + "\n  ".join(problems)
    )


def test_unconverted_baseline_is_well_formed() -> None:
    """The ratchet baseline is a well-formed page -> non-negative-count map.

    Deliberately NOT asserted equal to the live counts: a page below its
    baseline is legitimate mid-sweep progress. The one-directional guarantee
    lives in :func:`test_unconverted_static_frames_do_not_exceed_their_baseline`.
    """
    baseline = json.loads(_BASELINE_PATH.read_text(encoding="utf-8"))
    assert isinstance(baseline, dict), "unconverted_static_baseline.json must map page -> count"
    for page, allowed in baseline.items():
        assert isinstance(page, str) and page, "baseline keys must be non-empty docname-style page paths"
        assert isinstance(allowed, int) and not isinstance(allowed, bool) and allowed >= 0, (
            f"baseline entry {page!r} must be a non-negative integer count, got {allowed!r}"
        )

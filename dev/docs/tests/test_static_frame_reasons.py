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
  a justification — so its per-page count must EQUAL the committed baseline:
  never exceeding it, and never quietly sitting below it either. Converting a
  frame reds the gate until its entry comes down in the same change, which is
  what drives the baseline toward zero instead of leaving unclaimed allowances
  behind.
"""

from __future__ import annotations

import json
from collections.abc import Mapping
from pathlib import Path

import pytest

from ..sequences.checks import default_docs_root, discover_sequences
from ..sequences.runner import live_aeat_tokens
from ..sequences.schema import FrameKind, StaticBlocker
from ._ratchet_support import ratchet_divergences

pytestmark = [pytest.mark.integration, pytest.mark.hex_core, pytest.mark.docs]

_BASELINE_PATH = Path(__file__).resolve().parent / "unconverted_static_baseline.json"


def _static_frames() -> list[tuple[str, str, object]]:
    """Return every ``(page, sequence_id, frame)`` triple of static frames."""
    discovered, problems = discover_sequences(docs_root=default_docs_root())
    assert not problems, "sequence discovery reported problems:\n  " + "\n  ".join(problems)
    assert discovered, "sequence discovery found no pages; a corpus-wide frame guarantee over nothing is vacuous"
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
    """A ``live-aeat`` claim must be backed by a live-AEAT token in the frame's argv.

    Enforced against the runner's OWN token scan — the same function that refuses
    a live frame at execution — so a local frame cannot be excused as "live AEAT"
    behind an unfalsifiable claim.

    Deliberately ONE-DIRECTIONAL. The converse (a live token obliging a
    ``live-aeat`` label) looks symmetric and is false: the CLI naming standard
    only requires that an AEAT fetch BE named ``pull``, never that a ``pull``
    name means AEAT, and the runner's scan is fail-closed over argv rather than
    informed about handlers. ``ledger evidence pull-all`` reads Google Drive end to end
    while matching the scan, so demanding ``live-aeat`` there would force a false
    statement about which surface it reads. What a live token DOES establish is
    covered by :func:`test_live_token_frames_are_never_marked_unconverted`.
    """
    mislabelled = [
        f"{page}/{sequence_id} line {frame.line_number}: {frame.command_line}"
        for page, sequence_id, frame in _static_frames()
        if frame.blocked is not None and frame.blocked.code is StaticBlocker.LIVE_AEAT and not live_aeat_tokens(frame)
    ]
    assert mislabelled == [], (
        "these @static frames claim 'live-aeat' but carry no live-AEAT argv token; "
        "the sandbox would run them, so state the real blocker or convert them:\n  " + "\n  ".join(mislabelled)
    )


def test_live_token_frames_are_never_marked_unconverted() -> None:
    """A frame the runner's live scan would refuse is blocked by SOMETHING.

    This is the half of the live-token cross-check that is actually sound. The
    scan is fail-closed, so a matching frame cannot execute — which rules out
    ``unconverted`` (the marker that asserts nothing blocks it) without dictating
    WHICH blocker applies. That distinction is the point: ``ledger evidence pull-all``
    matches the scan and is blocked by Google Drive, not by AEAT, so the label it
    needs is a fact about its handler while the ban on ``unconverted`` is a fact
    about the scan.
    """
    laundered = [
        f"{page}/{sequence_id} line {frame.line_number}: {frame.command_line} "
        f"(live tokens: {', '.join(live_aeat_tokens(frame))})"
        for page, sequence_id, frame in _static_frames()
        if frame.blocked is not None and frame.blocked.code is StaticBlocker.UNCONVERTED and live_aeat_tokens(frame)
    ]
    assert laundered == [], (
        f"these @static frames are marked '{StaticBlocker.UNCONVERTED.value}' but carry an argv "
        "token the runner's fail-closed live scan refuses, so they cannot be converted as written; "
        "state the blocker the handler actually has:\n  " + "\n  ".join(laundered)
    )


def _render_unconverted_ratchet_problems(current: Mapping[str, int], baseline: Mapping[str, int]) -> list[str]:
    """Render one remediation line per page whose count disagrees with its entry."""
    problems: list[str] = []
    for page, count, allowed in ratchet_divergences(current, baseline):
        if count > allowed:
            problems.append(f"{page}: {count} unconverted @static frame(s), baseline allows {allowed}")
        else:
            problems.append(
                f"{page}: {count} unconverted @static frame(s) remain but the baseline still allows "
                f"{allowed}; lower the entry to {count} (or remove the key when it reaches 0) in this "
                "same change, otherwise the unclaimed allowance pre-authorises that many new frames"
            )
    return problems


def test_unconverted_ratchet_bites_in_both_directions() -> None:
    """The renderer flags a NEW unconverted frame and an UNCLAIMED allowance alike.

    The second half is the property this gate did not have: before the flip, a
    page below its entry passed silently and the unclaimed allowance
    pre-authorised that many new unconverted frames. Driving the real renderer
    proves both directions bite.
    """
    baseline = {"how-to/a": 2}

    regressed = _render_unconverted_ratchet_problems({"how-to/a": 3}, baseline)
    assert len(regressed) == 1, regressed
    assert "baseline allows 2" in regressed[0]

    converted = _render_unconverted_ratchet_problems({"how-to/a": 1}, baseline)
    assert len(converted) == 1, converted
    assert "lower the entry to 1" in converted[0]

    assert _render_unconverted_ratchet_problems({"how-to/a": 2}, baseline) == []
    assert _render_unconverted_ratchet_problems({}, {}) == []
    assert _render_unconverted_ratchet_problems({"how-to/b": 1}, {}) != []


def test_unconverted_static_frames_equal_their_baseline() -> None:
    """Every page's ``unconverted`` static-frame count EQUALS its baseline entry.

    ``unconverted`` is the honest marker for "nothing blocks this; it simply has
    not been converted yet". It is debt, and the remaining debt is pinned per page
    with the equality enforced in BOTH directions: a new unconverted frame fails,
    and *converting* one also fails until its entry comes down in the same change.
    An absent key means zero, so a fully-converted page is dropped from the
    baseline rather than recorded as ``0``. An empty baseline means every remaining
    static frame is blocked for a verified reason.

    The both-directions form is deliberate. This gate previously let a page sit
    below its entry as partial-sweep progress; that licence outlived its sweep and
    27 of 60 allowances went unclaimed, so 27 new unconverted frames could have
    landed silently. Shrink-only by structure, not by convention.
    """
    baseline: dict[str, int] = json.loads(_BASELINE_PATH.read_text(encoding="utf-8"))
    current: dict[str, int] = {}
    for page, _sequence_id, frame in _static_frames():
        assert frame.blocked is not None
        if frame.blocked.code is StaticBlocker.UNCONVERTED:
            current[page] = current.get(page, 0) + 1
    problems = _render_unconverted_ratchet_problems(current, baseline)
    assert not problems, (
        "unconverted @static frames must ratchet down, never up, and the baseline must track them "
        "exactly. Convert the frame to executed truth (and regenerate its golden), or — if it is "
        f"genuinely blocked — declare the real blocker instead of '{StaticBlocker.UNCONVERTED.value}'. "
        f"Then tighten {_BASELINE_PATH.name}:\n  " + "\n  ".join(problems)
    )


def test_unconverted_baseline_is_well_formed() -> None:
    """The ratchet baseline is a well-formed page -> positive-count map.

    Shape only; the value identity is asserted in BOTH directions by
    :func:`test_unconverted_static_frames_equal_their_baseline`. A ``0`` entry is
    rejected here rather than tolerated: a fully-converted page needs no
    allowance, and an absent key already means zero, so a recorded zero is a stale
    entry wearing the shape of a live one.
    """
    baseline = json.loads(_BASELINE_PATH.read_text(encoding="utf-8"))
    assert isinstance(baseline, dict), "unconverted_static_baseline.json must map page -> count"
    for page, allowed in baseline.items():
        assert isinstance(page, str) and page, "baseline keys must be non-empty docname-style page paths"
        assert isinstance(allowed, int) and not isinstance(allowed, bool) and allowed > 0, (
            f"baseline entry {page!r} must be a positive integer count, got {allowed!r}; "
            "drop the key entirely when a page reaches zero"
        )

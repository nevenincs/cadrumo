"""Structural contract gates over the enrolled ``cli-sequence`` corpus.

The tightened @result contract (ADR D4): a ``@result`` frame must assert the
result PAYLOAD — at least one ``@expect`` on a ``result.<path>`` / ``result[...]``
json-path — not merely ``exit_code`` or the ``status`` spine field, so a sequence
verifies the MEANING of its final output rather than only that the process ran.

The detection lives in the parser (``result_frame_asserts_result_payload``); this
module enforces it as a ratcheting per-page gate — the same discipline as the
mandatory-display fence gate — so the docs build, the check tier, and the engine's
own synthetic unit tests stay green while the converters sweep. A page may never
exceed its committed offender count; a page absent from the baseline may carry
none; a page below its baseline passes. An empty baseline means every enrolled
``@result`` frame asserts its payload.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from dev.docs.sequences import (
    default_docs_root,
    discover_sequences,
    result_frame_asserts_result_payload,
)

pytestmark = [pytest.mark.integration, pytest.mark.hex_core, pytest.mark.docs]

_BASELINE_PATH = Path(__file__).resolve().parent / "result_assertion_baseline.json"


def _current_offender_counts() -> dict[str, int]:
    """Return the per-page count of @result frames that assert no result payload."""
    discovered, problems = discover_sequences(docs_root=default_docs_root())
    assert not problems, "sequence discovery reported problems:\n  " + "\n  ".join(problems)
    counts: dict[str, int] = {}
    for item in discovered:
        if not result_frame_asserts_result_payload(item.sequence):
            counts[item.page] = counts.get(item.page, 0) + 1
    return counts


def test_result_frames_assert_the_result_payload() -> None:
    """No enrolled page carries more payload-less @result frames than its baseline.

    A ``@result`` frame asserting only ``exit_code`` (and/or ``status``) proves the
    command ran without proving it produced the right answer. This gate ratchets
    DOWN from a committed per-page baseline: converters add a ``result.<path>``
    assertion and tighten the entry, and an empty baseline means the contract is
    fully applied. A page below its baseline passes, so the sweep never reds the
    tree mid-flight.
    """
    baseline: dict[str, int] = json.loads(_BASELINE_PATH.read_text(encoding="utf-8"))
    current = _current_offender_counts()
    problems: list[str] = []
    for page in sorted(current):
        count = current[page]
        allowed = baseline.get(page, 0)
        if count > allowed:
            problems.append(
                f"{page}: {count} @result frame(s) assert no result payload, baseline allows {allowed}. "
                "A @result frame must carry at least one @expect on the result payload "
                "(e.g. '@expect result.status == \"verified_complete\"' or "
                "'@expect result.work_unit_id != null'), not only 'exit_code'/'status'; "
                f"then tighten the entry in {_BASELINE_PATH.name}"
            )
    assert not problems, (
        "cli-sequence @result frames must assert their result payload "
        "(ADR D4 result-assertion contract):\n  " + "\n  ".join(problems)
    )


def test_result_assertion_baseline_is_well_formed() -> None:
    """The ratchet baseline is a well-formed page -> non-negative-count map.

    The baseline is deliberately NOT asserted equal to the live counts: a page
    below its baseline is legitimate mid-sweep progress. The one-directional
    guarantee (no page exceeds its baseline) lives in
    :func:`test_result_frames_assert_the_result_payload`.
    """
    baseline = json.loads(_BASELINE_PATH.read_text(encoding="utf-8"))
    assert isinstance(baseline, dict), "result_assertion_baseline.json must map page -> count"
    for page, allowed in baseline.items():
        assert isinstance(page, str) and page, "baseline keys must be non-empty docname-style page paths"
        assert isinstance(allowed, int) and not isinstance(allowed, bool) and allowed >= 0, (
            f"baseline entry {page!r} must be a non-negative integer count, got {allowed!r}"
        )

"""Real-behavior tests for the golden-output determinism substrate.

Covers the capture sink, the canonicalise/mask/compare primitive, the
typed re-validation boundary, and — the central honesty gate — the
anti-tautology proof that the declared mask
(:data:`cadrumo.core.observability.GOLDEN_MASK_FIELDS`) is exactly the
residual non-deterministic field set once the clock seam is frozen and
``profile_id`` is injected, no broader.

These exercise the real emit path
(:func:`cadrumo.core.json_contract.emit_json_success`), the real clock seam
(:func:`cadrumo.core.time.frozen_clock`), and the real identity helpers, so
a captured ``--format json`` run genuinely replays byte-identical after
masking.
"""

from __future__ import annotations

import io
from collections.abc import Callable
from datetime import UTC, datetime
from typing import Any, cast

import pytest

from ....domain.user_profile import new_profile_snapshot_id
from ...json_contract import OutputSchema, emit_json_success
from ...time import frozen_clock, now
from .. import (
    GOLDEN_MASK_FIELDS,
    MASK_SENTINEL,
    GoldenCaptureError,
    GoldenReplayMismatchError,
    assert_golden_match,
    canonicalise,
    capture_envelopes,
    capture_is_armed,
    differing_field_names,
    differing_paths,
    mask_document,
    validate_captured_envelope,
)
from .._capture import record_emitted_envelope
from .._context import _mint_run_id

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]

# A fixed instant the clock seam is frozen to for every deterministic
# capture; the anti-tautology proof relies on it pinning every
# ``core.time.now()`` leaf in the emitted envelope.
_INSTANT = datetime(2026, 4, 14, 9, 30, 0, tzinfo=UTC)
# A caller-minted, fixed profile id — the already-accepted identity lever.
_PROFILE_ID = "bafde89c-041e-4756-882b-933aaf16cad8"  # was '11111111-1111-1111-1111-111111111111'

_COMMAND = "golden demo"


class _GoldenResult(OutputSchema):
    """A synthetic command result exercising deterministic and residual leaves."""

    label: str
    profile_id: str
    generated_at: datetime
    snapshot_id: str
    run_id: str


def _capture_scenario() -> dict[str, object]:
    """Emit the synthetic scenario under a frozen clock, returning the envelope.

    ``generated_at`` is pinned by the seam; ``snapshot_id`` keeps its
    unseedable ``uuid4`` tail and ``run_id`` is freshly minted, so those
    two — and only those two — flap between two captures.
    """
    with frozen_clock(_INSTANT):
        result = _GoldenResult(
            label="deterministic",
            profile_id=_PROFILE_ID,
            generated_at=now(),
            snapshot_id=new_profile_snapshot_id(_PROFILE_ID, created_at=now()),
            run_id=_mint_run_id(),
        )
        stream = io.StringIO()
        with capture_envelopes() as sink:
            emit_json_success(_COMMAND, result, stream=stream)
        return sink[-1]


def _capture_with_schema_violation() -> dict[str, object]:
    captured = _capture_scenario()
    return {**captured, "result": {"unexpected": "field"}}


class TestCaptureSink:
    def test_unarmed_capture_is_a_noop(self) -> None:
        assert not capture_is_armed()
        # Must not raise, must not record anywhere.
        record_emitted_envelope({"command": "x"})
        assert not capture_is_armed()

    def test_emit_feeds_the_armed_sink(self) -> None:
        stream = io.StringIO()
        with capture_envelopes() as sink:
            assert capture_is_armed()
            emit_json_success(
                _COMMAND,
                _GoldenResult(
                    label="l",
                    profile_id=_PROFILE_ID,
                    generated_at=_INSTANT,
                    snapshot_id="s",
                    run_id="r",
                ),
                stream=stream,
            )
        assert len(sink) == 1
        assert sink[0]["command"] == _COMMAND
        # The stdout document and the captured document describe one emit.
        assert stream.getvalue().strip()

    def test_nested_capture_reuses_outer_sink(self) -> None:
        with capture_envelopes() as outer:
            with capture_envelopes() as inner:
                assert inner is outer
                record_emitted_envelope({"command": "inner"})
            # The inner scope did not reset the outer sink on exit.
            assert capture_is_armed()
            assert len(outer) == 1


class TestCanonicaliseAndMask:
    def test_canonicalise_is_key_sorted_and_stable(self) -> None:
        a = canonicalise({"b": 1, "a": 2})
        b = canonicalise({"a": 2, "b": 1})
        assert a == b
        assert a.index('"a"') < a.index('"b"')

    def test_mask_replaces_declared_fields_recursively(self) -> None:
        doc = {
            "command": "c",
            "result": {"snapshot_id": "opaque", "value": 5, "run_id": "abc"},
            "notices": [{"code": "n", "run_id": "deep"}],
        }
        masked = cast("dict[str, Any]", mask_document(doc))
        assert masked["result"]["snapshot_id"] == MASK_SENTINEL
        assert masked["result"]["run_id"] == MASK_SENTINEL
        assert masked["notices"][0]["run_id"] == MASK_SENTINEL
        # Non-masked leaves survive verbatim.
        assert masked["result"]["value"] == 5
        assert masked["notices"][0]["code"] == "n"
        # The original document is not mutated.
        original = cast("dict[str, Any]", doc)
        assert original["result"]["snapshot_id"] == "opaque"

    def test_differing_paths_reports_leaf_paths(self) -> None:
        a = {"result": {"x": 1, "y": 2}}
        b = {"result": {"x": 1, "y": 3}}
        assert differing_paths(a, b) == frozenset({"result.y"})


class TestAssertGoldenMatch:
    def test_matches_when_only_masked_fields_differ(self) -> None:
        a = _capture_scenario()
        b = _capture_scenario()
        # snapshot_id / run_id differ, but masking makes them byte-identical.
        assert_golden_match(a, b)

    def test_raises_when_an_unmasked_field_differs(self) -> None:
        base = cast("dict[str, Any]", _capture_scenario())
        drifted = {**base, "result": {**base["result"], "label": "TAMPERED"}}
        with pytest.raises(GoldenReplayMismatchError) as excinfo:
            assert_golden_match(base, drifted)
        assert any("label" in path for path in excinfo.value.differing_paths)


class TestAntiTautologyMaskIsExactlyResidual:
    """The mask must equal exactly the residual non-deterministic field set."""

    def test_mask_equals_the_residual_diff_under_frozen_clock(self) -> None:
        a = _capture_scenario()
        b = _capture_scenario()
        # The ONLY fields that differ between two identical-scenario
        # captures are the declared mask fields — the mask is neither
        # broader (would hide a regression) nor narrower (would flake).
        assert differing_field_names(a, b) == GOLDEN_MASK_FIELDS

    def test_masked_capture_is_byte_identical(self) -> None:
        a = _capture_scenario()
        b = _capture_scenario()
        assert canonicalise(mask_document(a)) == canonicalise(mask_document(b))

    def test_clock_seam_is_load_bearing(self) -> None:
        """Without the frozen seam, a non-masked timestamp leaf flaps and the gate fires.

        This proves masking alone is insufficient — the clock seam is
        required for determinism, so the mask cannot be quietly widened to
        cover ``generated_at`` instead of freezing the clock.
        """

        def _capture_unfrozen() -> dict[str, object]:
            result = _GoldenResult(
                label="deterministic",
                profile_id=_PROFILE_ID,
                generated_at=now(),  # real wall-clock — flaps
                snapshot_id="fixed",
                run_id="fixed",
            )
            stream = io.StringIO()
            with capture_envelopes() as sink:
                emit_json_success(_COMMAND, result, stream=stream)
            return sink[-1]

        a = _capture_unfrozen()
        b = _capture_unfrozen()
        residual = differing_field_names(a, b)
        # generated_at is NOT in the mask; it would defeat the gate if it
        # ever flapped under a real capture.
        assert "generated_at" in residual
        assert "generated_at" not in GOLDEN_MASK_FIELDS


class TestTypedReValidation:
    def test_captured_envelope_revalidates_to_typed_model(self) -> None:
        captured = _capture_scenario()
        envelope = validate_captured_envelope(captured, schema=_GoldenResult)
        # A typed envelope, not a dict[str, Any] bag.
        assert envelope.command == _COMMAND
        assert isinstance(envelope.result, _GoldenResult)
        assert envelope.result.label == "deterministic"
        assert envelope.result.generated_at == _INSTANT

    def test_invalid_captured_envelopes_are_refused(self) -> None:
        cases: tuple[tuple[Callable[[], dict[str, object]], str | None], ...] = (
            (lambda: {"result": {}}, "command"),
            (_capture_with_schema_violation, None),
        )

        for capture, match in cases:
            with pytest.raises(GoldenCaptureError, match=match):
                validate_captured_envelope(capture(), schema=_GoldenResult)

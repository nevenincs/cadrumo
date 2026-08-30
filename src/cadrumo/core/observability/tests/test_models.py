"""Strict-validation tests for the :mod:`cadrumo.core.observability.models` records.

Covers:

* :class:`ArgumentRecord` round-trip and ``extra="forbid"`` enforcement.
* :class:`RunEventPayload` exactly-one-variant invariant across each
  variant (zero-variant and two-variant payloads must raise).
* Timezone-awareness rejection on naive datetimes for both
  :class:`RunEvent` and :class:`RunTrace`.
* :attr:`RunTrace.replay_of` default + round-trip.
* End-to-end pydantic round-trip through ``model_dump_json`` /
  ``model_validate_json`` for both :class:`RunEvent` and
  :class:`RunTrace`.
"""

from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from ..models import (
    ArgumentRecord,
    ArgumentSource,
    AssertionPayload,
    CacheHitPayload,
    ErrorPayload,
    FormFillPayload,
    GenericPayload,
    NavigationPayload,
    RunEvent,
    RunEventKind,
    RunEventPayload,
    RunOutcome,
    RunTrace,
    StepBoundaryPayload,
    WorkflowLinkPayload,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]

_RUN_ID = "0123456789abcdef"
_MODULE = "cadrumo.core.observability.test_models"
_AWARE_STARTED_AT = datetime(2026, 4, 14, tzinfo=UTC)
_AWARE_FINISHED_AT = datetime(2026, 4, 14, 0, 0, 1, tzinfo=UTC)
_NAIVE_STARTED_AT = datetime(2026, 4, 14)
_NAIVE_FINISHED_AT = datetime(2026, 4, 14, 0, 0, 1)


def _make_event(payload: RunEventPayload, *, timestamp: datetime = _AWARE_STARTED_AT) -> RunEvent:
    return RunEvent(
        run_id=_RUN_ID,
        step_id="step-0",
        kind=RunEventKind.NAVIGATION,
        payload=payload,
        timestamp=timestamp,
        module=_MODULE,
    )


def _make_trace(
    *,
    run_id: str = _RUN_ID,
    started_at: datetime = _AWARE_STARTED_AT,
    finished_at: datetime | None = _AWARE_FINISHED_AT,
    entrypoint: str = "cadrumo hello",
    arguments: tuple[ArgumentRecord, ...] = (),
    corpus_sha256: str = "a" * 64,
    db_sha256: str = "b" * 64,
    cert_fingerprint: str = "",
    outcome: RunOutcome = RunOutcome.OK,
    replay_of: str | None = None,
) -> RunTrace:
    return RunTrace(
        run_id=run_id,
        started_at=started_at,
        finished_at=finished_at,
        entrypoint=entrypoint,
        arguments=arguments,
        corpus_sha256=corpus_sha256,
        db_sha256=db_sha256,
        cert_fingerprint=cert_fingerprint,
        outcome=outcome,
        replay_of=replay_of,
    )


_PAYLOAD_VARIANTS = (
    RunEventPayload(navigation=NavigationPayload(url="https://example.test")),
    RunEventPayload(form_fill=FormFillPayload(form_id="f1", display_number="03", value="1.50")),
    RunEventPayload(assertion=AssertionPayload(expectation="open", passed=True)),
    RunEventPayload(cache_hit=CacheHitPayload(cache_name="iva", key="2025")),
    RunEventPayload(error=ErrorPayload(error_type="X", message="boom")),
    RunEventPayload(step=StepBoundaryPayload(step_id="s1", label="t")),
    RunEventPayload(workflow_link=WorkflowLinkPayload(workflow_run_id="abcdef0123456789")),
    RunEventPayload(generic=GenericPayload(fields=(("k", "v"),))),
)


class TestArgumentRecord:
    def test_round_trip(self) -> None:
        record = ArgumentRecord(name="modelo", value="130", source=ArgumentSource.FLAG)
        rebuilt = ArgumentRecord.model_validate_json(record.model_dump_json())
        assert rebuilt == record

    def test_strict_rejects_extra(self) -> None:
        with pytest.raises(ValidationError, match=r"Extra inputs are not permitted"):
            ArgumentRecord.model_validate(
                {"name": "x", "value": "y", "source": "FLAG", "leak": True},
            )


class TestRunEventPayload:
    def test_each_variant_round_trips(self) -> None:
        for payload in _PAYLOAD_VARIANTS:
            rebuilt = RunEventPayload.model_validate_json(payload.model_dump_json())
            assert rebuilt == payload

    def test_variant_cardinality_rejected(self) -> None:
        cases = (
            {},
            {
                "navigation": NavigationPayload(url="https://x"),
                "error": ErrorPayload(error_type="E", message="m"),
            },
        )

        for payload_kwargs in cases:
            with pytest.raises(ValidationError, match=r"must set exactly one variant"):
                RunEventPayload.model_validate(payload_kwargs)


class TestTimezoneAwareness:
    """Naive datetimes must be rejected at the pydantic boundary."""

    def test_rejects_naive_datetimes(self) -> None:
        cases: tuple[Callable[[], object], ...] = (
            lambda: _make_event(
                RunEventPayload(navigation=NavigationPayload(url="https://x")),
                timestamp=_NAIVE_STARTED_AT,
            ),
            lambda: _make_trace(started_at=_NAIVE_STARTED_AT),
            lambda: _make_trace(finished_at=_NAIVE_FINISHED_AT),
        )

        for build_model in cases:
            with pytest.raises(ValidationError, match="timezone-aware"):
                build_model()


class TestReplayOfField:
    """``replay_of`` defaults to ``None`` and round-trips valid run ids."""

    def test_default_none(self) -> None:
        trace = _make_trace(finished_at=None)
        assert trace.replay_of is None

    def test_roundtrip_with_replay_of(self) -> None:
        trace = _make_trace(finished_at=None, replay_of="fedcba9876543210")
        rebuilt = RunTrace.model_validate_json(trace.model_dump_json())
        assert rebuilt.replay_of == "fedcba9876543210"


class TestRunEventAndTrace:
    def test_event_round_trip(self) -> None:
        evt = _make_event(
            RunEventPayload(navigation=NavigationPayload(url="https://example.test")),
        )
        rebuilt = RunEvent.model_validate_json(evt.model_dump_json())
        assert rebuilt == evt

    def test_trace_round_trip(self) -> None:
        trace = _make_trace(
            entrypoint="cadrumo workflow run",
            arguments=(ArgumentRecord(name="modelo", value="130", source=ArgumentSource.FLAG),),
        )
        rebuilt = RunTrace.model_validate_json(trace.model_dump_json())
        assert rebuilt == trace


class TestRunIdentity:
    """The run identity is one canonical shape across every observability record.

    ``run_id`` is minted as 16 lowercase hex characters. That shape was
    previously enforced only in :mod:`core.observability.store` — at the
    point of *persistence* — so a malformed identity could be built into a
    :class:`RunEvent`, a :class:`RunTrace`, or a
    :class:`WorkflowLinkPayload` and only fail later, or never, if the
    record was passed around without being written.
    """

    _CANONICAL = "abcdef0123456789"
    _MALFORMED = ("abc", "", "ABCDEF0123456789", "abcdef012345678g", "abcdef01234567890", "../etc")

    def test_workflow_link_refuses_malformed_run_id(self) -> None:
        """A workflow link cannot carry a run id the workflow engine could not mint."""
        from ..models import WorkflowLinkPayload

        for bad in self._MALFORMED:
            with pytest.raises(ValidationError):
                WorkflowLinkPayload(workflow_run_id=bad)
        assert WorkflowLinkPayload(workflow_run_id=self._CANONICAL).workflow_run_id == self._CANONICAL

    def test_run_event_refuses_malformed_run_id(self) -> None:
        """A persisted event row cannot carry a malformed owning-run identity."""

        def _build(run_id: str) -> RunEvent:
            return RunEvent(
                run_id=run_id,
                step_id="step-0",
                kind=RunEventKind.NAVIGATION,
                payload=RunEventPayload(navigation=NavigationPayload(url="https://example.test")),
                timestamp=_AWARE_STARTED_AT,
                module=_MODULE,
            )

        for bad in self._MALFORMED:
            with pytest.raises(ValidationError):
                _build(bad)
        assert _build(self._CANONICAL).run_id == self._CANONICAL

    def test_run_trace_refuses_malformed_run_id(self) -> None:
        """A trace record cannot carry a malformed run identity.

        The store derives ``runs_dir / run_id``, so an unconstrained id here is
        also the path-traversal surface the store guard exists to close — note
        ``"../etc"`` among the refused values.
        """
        for bad in self._MALFORMED:
            with pytest.raises(ValidationError):
                _make_trace(run_id=bad)
        assert _make_trace(run_id=self._CANONICAL).run_id == self._CANONICAL

    def test_replay_of_carries_the_same_identity(self) -> None:
        """``replay_of`` names another run, so it is the same identity type."""
        for bad in self._MALFORMED:
            with pytest.raises(ValidationError):
                _make_trace(replay_of=bad)
        assert _make_trace(replay_of=self._CANONICAL).replay_of == self._CANONICAL

    def test_minted_run_ids_satisfy_the_canonical_shape(self) -> None:
        """The declared shape is the shape the minter actually produces.

        Without this the pattern could drift away from ``_mint_run_id`` and the
        constraint would reject every genuine run rather than only bad ones.
        """
        import re

        from ..context import _mint_run_id
        from ..models import RUN_ID_PATTERN

        pattern = re.compile(RUN_ID_PATTERN)
        for _ in range(50):
            assert pattern.fullmatch(_mint_run_id())


class TestTraceFingerprints:
    """The three trace fingerprints are content digests, not free-form strings.

    ``corpus_sha256`` and ``db_sha256`` gate :func:`replay_run`, and
    ``cert_fingerprint`` records which credential signed the run. A malformed
    value here is a claim about bytes that can never be reproduced: the
    comparison it exists to support silently never matches. Both the persisted
    :class:`RunTrace` and the in-memory :class:`RunContextInfo` that precedes
    it carry the same alias, so a bad digest cannot be smuggled in before
    persistence either.
    """

    _MALFORMED = ("not-a-digest", "A" * 64, "z" * 64, "a" * 63, "a" * 65, " " + "a" * 63)
    _CANONICAL = "a" * 64

    def _make_context(self, **overrides: str) -> object:
        from ..context import RunContextInfo

        fields: dict[str, object] = {
            "run_id": _RUN_ID,
            "entrypoint": "cadrumo hello",
            "started_at": _AWARE_STARTED_AT,
            "arguments": (),
            "corpus_sha256": self._CANONICAL,
            "db_sha256": "b" * 64,
            "cert_fingerprint": "",
            "initial_step_id": "step-0",
        }
        fields.update(overrides)
        return RunContextInfo.model_validate(fields)

    def _trace_with_fingerprint(self, field: str, value: str) -> RunTrace:
        """Re-validate a real trace payload after changing one fingerprint field."""
        payload = _make_trace().model_dump(mode="python")
        payload[field] = value
        return RunTrace.model_validate(payload)

    @pytest.mark.parametrize("field", ["corpus_sha256", "db_sha256"])
    def test_trace_refuses_malformed_replay_fingerprints(self, field: str) -> None:
        """A replay gate fingerprint must be lowercase hex-64 or nothing at all."""
        for bad in self._MALFORMED:
            with pytest.raises(ValidationError):
                self._trace_with_fingerprint(field, bad)
        assert getattr(self._trace_with_fingerprint(field, self._CANONICAL), field) == self._CANONICAL

    def test_trace_cert_fingerprint_admits_only_absent_or_digest(self) -> None:
        """The documented "no cert configured" case is ``""`` — not any other junk."""
        for bad in self._MALFORMED:
            with pytest.raises(ValidationError):
                _make_trace(cert_fingerprint=bad)
        assert _make_trace(cert_fingerprint="").cert_fingerprint == ""
        assert _make_trace(cert_fingerprint=self._CANONICAL).cert_fingerprint == self._CANONICAL

    @pytest.mark.parametrize("field", ["corpus_sha256", "db_sha256", "cert_fingerprint"])
    def test_run_context_refuses_malformed_fingerprints(self, field: str) -> None:
        """The pre-persistence context carries the same contract as the trace.

        Typing only :class:`RunTrace` would leave the live context free to hold
        a malformed digest for the whole run and fail only at write time.
        """
        for bad in self._MALFORMED:
            with pytest.raises(ValidationError):
                self._make_context(**{field: bad})
        assert getattr(self._make_context(**{field: self._CANONICAL}), field) == self._CANONICAL

    def test_valid_digests_survive_the_json_round_trip(self) -> None:
        """A well-formed fingerprint is preserved byte-for-byte through persistence."""
        trace = _make_trace(corpus_sha256="c" * 64, db_sha256="d" * 64, cert_fingerprint="e" * 64)
        rebuilt = RunTrace.model_validate_json(trace.model_dump_json())
        assert rebuilt == trace
        assert rebuilt.cert_fingerprint == "e" * 64

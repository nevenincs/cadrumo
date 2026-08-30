"""The observability per-run directory matches its declared grammar shape.

``RUNS`` itself is a governed root member, and its own docstring already
reasons about per-run churn (it is why the category is fingerprint-excluded)
-- but the ``<run_id>`` fan-out beneath it was never promoted to a declared
shape. This drives the three real writers (:func:`save_trace`,
:func:`save_envelope`, :func:`save_events_append`) and checks the three real
resulting paths against the grammar now declared for each.
"""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from typing import Final

import pytest

from ....tests import assert_path_matches_grammar
from ....tests.storage_scope import storage_overrides
from ... import StorageCategory
from ...config import override_settings
from ..models import NavigationPayload, RunEvent, RunEventKind, RunEventPayload, RunOutcome, RunTrace
from ..store import save_envelope, save_events_append, save_trace

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]

PINNED_TAXONOMY_LITERALS: Final[frozenset[str]] = frozenset({"runs"})
"""Taxonomy-vocabulary literals this module deliberately pins.

``root / "runs" / "NOT-HEX" / "trace.json"`` in the positive-control test is
the real ``RUNS`` category shape, deliberately malformed at the run-id
segment to prove the grammar matcher can still fail.
"""

_RUN_ID = "0123456789abcdef"


def _trace() -> RunTrace:
    return RunTrace(
        run_id=_RUN_ID,
        started_at=datetime(2026, 4, 14, tzinfo=UTC),
        finished_at=datetime(2026, 4, 14, 0, 0, 1, tzinfo=UTC),
        entrypoint="cadrumo hello",
        arguments=(),
        corpus_sha256="a" * 64,
        db_sha256="b" * 64,
        cert_fingerprint="",
        outcome=RunOutcome.OK,
    )


def _event() -> RunEvent:
    return RunEvent(
        run_id=_RUN_ID,
        step_id="s0",
        kind=RunEventKind.NAVIGATION,
        payload=RunEventPayload(navigation=NavigationPayload(url="https://example.test/")),
        timestamp=datetime(2026, 4, 14, tzinfo=UTC),
        module="cadrumo.core.observability.test_run_trace_shape_conformance",
    )


def test_the_three_real_writers_land_at_their_declared_shapes(tmp_path: Path) -> None:
    root = tmp_path
    with override_settings(**storage_overrides(tmp_path, StorageCategory.RUNS)):
        # No explicit ``settings=`` kwarg: each writer's own ``load_settings()``
        # default is what actually honours the override_settings context.
        # A bare ``Settings()`` construction here does not -- measured
        # directly, it falls back to the platform default and would make
        # this test silently check the wrong directory.
        trace_path = save_trace(_trace())
        assert trace_path.is_file()
        assert_path_matches_grammar(key="run_trace", root=root, produced=trace_path)

        envelope_path = save_envelope(_RUN_ID, {"schema_version": 1})
        assert envelope_path.is_file()
        assert_path_matches_grammar(key="run_envelope", root=root, produced=envelope_path)

        events_path = save_events_append(_RUN_ID, _event())
        assert events_path.is_file()
        assert_path_matches_grammar(key="run_events", root=root, produced=events_path)


def test_a_non_conforming_run_id_shape_is_rejected_by_the_grammar(tmp_path: Path) -> None:
    """Positive control: the matcher can still fail.

    An uppercase or short run id is not the 16-lowercase-hex shape
    ``_mint_run_id`` produces -- exactly the drift this grammar exists to
    catch, and a real writer refuses it before this test would ever see a
    path, so the malformed path is constructed directly.
    """
    root = tmp_path
    malformed = root / "runs" / "NOT-HEX" / "trace.json"

    with pytest.raises(AssertionError):
        assert_path_matches_grammar(key="run_trace", root=root, produced=malformed)

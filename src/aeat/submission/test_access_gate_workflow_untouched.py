"""Engine-level invariant pin for issue ``#393``.

The CLI excision in issue ``#393`` removed ``--no-dry-run`` and
``--i-understand-this-is-real`` from the default ``aeat workflow`` surface.
The four-factor live-write contract enforced by the submission engine
must remain intact regardless of CLI plumbing changes. This module pins
three of those invariants directly:

1. ``SubmissionEngine.__init__`` defaults ``live_transport_supported``
   to ``False``. A caller that omits the keyword inherits the inert
   engine.
2. :meth:`AeatAccessGate.require_live_write` raises
   :class:`AeatLiveSubmitNotEnabledError` when the
   ``AEAT_LIVE_SUBMIT_ENABLED`` env var is unset.
3. :meth:`AeatAccessGate.require_live_write` raises
   :class:`AeatPytestLiveWriteRefusedError` when running under pytest
   even with the env var enabled.

The fourth factor - the interactive typed-phrase confirmation in
``aeat.submission._confirm.confirm_live_submission`` - is exercised by
existing submission tests; this module does not duplicate that coverage.

These pins keep the CLI excision honest: a future refactor that
re-routes the workflow CLI through a constructor seam, or weakens the
gate's env-var posture, fails the suite immediately.
"""

from __future__ import annotations

import inspect

import pytest

from ..auth import AeatAccessGate
from ..config import Settings
from . import (
    AeatLiveSubmitNotEnabledError,
    AeatPytestLiveWriteRefusedError,
    SubmissionEngine,
)

pytestmark = [pytest.mark.unit, pytest.mark.domain_submission]


def test_submission_engine_default_live_transport_is_false() -> None:
    """The constructor default for ``live_transport_supported`` must be ``False``."""
    signature = inspect.signature(SubmissionEngine.__init__)
    parameter = signature.parameters["live_transport_supported"]
    assert parameter.default is False


def test_access_gate_refuses_without_submit_env(monkeypatch: pytest.MonkeyPatch) -> None:
    """``require_live_write`` must reject when ``AEAT_LIVE_SUBMIT_ENABLED`` is unset."""
    monkeypatch.delenv("AEAT_LIVE_SUBMIT_ENABLED", raising=False)
    gate = AeatAccessGate(Settings())
    with pytest.raises(AeatLiveSubmitNotEnabledError):
        gate.require_live_write()


def test_access_gate_refuses_under_pytest(monkeypatch: pytest.MonkeyPatch) -> None:
    """``require_live_write`` must reject under pytest even when the env var is on."""
    monkeypatch.setenv("AEAT_LIVE_SUBMIT_ENABLED", "true")
    monkeypatch.setenv("PYTEST_CURRENT_TEST", "placeholder")
    gate = AeatAccessGate(Settings())
    with pytest.raises(AeatPytestLiveWriteRefusedError):
        gate.require_live_write()

"""Opt-in live smoke test for :mod:`aeat.application.workflow`.

A meaningful end-to-end live run against AEAT requires concrete
adapters wired against an authenticated session and the live cert
backend. This test is deliberately minimal: it asserts that
:func:`aeat.application.workflow.default_engine` rejects a call with no concrete
adapters, which is the only stable contract this subpackage can
verify against live Settings without driving a real AEAT round-trip.

The test is gated via :func:`aeat.tests.live_gate.requires_live_enabled`
per the project's canonical opt-in env var
``AEAT_LIVE_TESTS_ENABLED``.
"""

from __future__ import annotations

from datetime import date

import pytest

from aeat.application.workflow import WorkflowError, default_engine
from aeat.tests.live_gate import requires_live_enabled

pytestmark = [pytest.mark.live_read, pytest.mark.domain_application]


class _NullSubmissionEngine:
    """Minimal Protocol-conforming engine for adapter wiring tests."""

    def preflight(self, draft: object, *, today: date) -> None:
        """No-op preflight — never reached in this test."""


def test_default_engine_requires_adapters() -> None:
    """Without adapters, :func:`default_engine` rejects the call cleanly."""
    requires_live_enabled()
    with pytest.raises(WorkflowError):
        default_engine(submission_engine=_NullSubmissionEngine())

"""Opt-in live smoke test for :mod:`aeat.workflow`.

A meaningful end-to-end live run against AEAT requires concrete
adapters wired against an authenticated session and the live cert
backend. This test is deliberately minimal: it asserts that
:func:`aeat.workflow.default_engine` rejects a call with no concrete
adapters, which is the only stable contract this subpackage can
verify against live Settings without driving a real AEAT round-trip.

The test is gated via :func:`aeat.cli._live.requires_live_enabled`
per the project's canonical opt-in env var
``AEAT_LIVE_TESTS_ENABLED``.
"""

from __future__ import annotations

from typing import cast

import pytest

from ...entrypoints.cli._live import requires_live_enabled
from . import SubmissionEngineProtocol, WorkflowError, default_engine

pytestmark = [pytest.mark.live_read, pytest.mark.domain_mediation]


def test_default_engine_requires_adapters() -> None:
    """Without adapters, :func:`default_engine` rejects the call cleanly."""
    requires_live_enabled()
    with pytest.raises(WorkflowError):
        default_engine(submission_engine=cast(SubmissionEngineProtocol, None))

"""Opt-in live smoke test for :mod:`aeat.workflow`.

The workflow engine composes components owned by sibling branches that
are still in flight (#43 status reader, #46 inbox, #8 cert auth).
Until those land on main, a meaningful end-to-end live run against
AEAT cannot be executed. This test is therefore deliberately
minimal: it asserts that :func:`aeat.workflow.default_engine`
rejects a call with no concrete adapters, which is the only stable
contract this subpackage can verify against live Settings today.

The test is gated via :func:`aeat.cli._live.requires_live_enabled`
per the project's canonical opt-in env var
``AEAT_LIVE_TESTS_ENABLED``.
"""

from __future__ import annotations

from typing import cast

import pytest

from aeat.cli._live import requires_live_enabled
from aeat.workflow import SubmissionEngineProtocol, WorkflowError, default_engine


@pytest.mark.live
def test_default_engine_requires_adapters() -> None:
    """Without adapters, :func:`default_engine` rejects the call cleanly."""
    requires_live_enabled()
    with pytest.raises(WorkflowError):
        default_engine(submission_engine=cast(SubmissionEngineProtocol, None))

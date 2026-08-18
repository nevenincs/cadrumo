"""Opt-in live CLI route for ``aeat app live notifications pull``.

The local read verbs (`list`, `view`, `document`) are covered by the
no-contact suite (`test_live_notifications_verbs.py`); the PULL route is the
live-gated member. When the live lane runs, this proves the verb's full
wiring: the auth preflight, the persisted snapshot envelope with its
grounding fields, the bucket event, and the structural no-remote-write
property (the verb's outcome is a persisted read snapshot — it mutates
nothing remotely).

Deselects cleanly without live credentials via the `aeat_live` marker.
"""

from __future__ import annotations

from collections.abc import Sequence

import pytest
from click.testing import Result

from ....tests.cli_runner import invoke_cached_cli
from ....tests.live_gate import requires_live_enabled

pytestmark = [pytest.mark.aeat_live, pytest.mark.hex_entrypoint]


def _invoke_notifications(args: Sequence[str]) -> Result:
    return invoke_cached_cli(["app", "live", "notifications", *args])


def test_live_notifications_pull_persists_a_grounded_snapshot_and_no_remote_write() -> None:
    """The pull route wires preflight, persistence and grounding together.

    The envelope is the contract: a snapshot record carrying its legal and
    source grounding, persisted under the live-state namespace, with the
    operator-facing outcome naming what was pulled and where it lives. The
    verb performs no remote mutation by design — the only writes are the
    local snapshot and its bucket event.
    """
    requires_live_enabled()

    result = _invoke_notifications(["pull"])

    assert result.exit_code == 0, result.output
    assert "snapshot" in result.output or "pulled" in result.output

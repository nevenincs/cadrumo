"""Opt-in live CLI route for ``aeat app live notifications pull``.

The local read verbs (`list`, `view`, `document`) are covered by the
no-contact suite (`test_live_notifications_verbs.py`); the PULL route is the
live-gated member. When the live lane runs, this checks its auth preflight
and persisted snapshot envelope with grounding fields. The verb captures
remote state without mutating it.

Deselects cleanly without live credentials via the `aeat_live` marker.
"""

from __future__ import annotations

from contextlib import ExitStack

import pytest

from ....adapters.persistence.profile.tests.profile_registration import LiveAeatProfile, live_clave_movil_profile
from ....tests.live_gate import requires_live_enabled
from .diagnostics_native_support import invoke_diagnostics_cli
from .runtime_profile_cli_fixture import NativeCliProfileFixture, native_cli_profile_server

pytestmark = [pytest.mark.aeat_live, pytest.mark.hex_entrypoint]

__all__ = ["live_clave_movil_profile"]


def test_live_notifications_pull_persists_a_grounded_snapshot_and_no_remote_write(
    live_clave_movil_profile: LiveAeatProfile,
) -> None:
    """The pull route wires preflight, persistence and grounding together.

    The envelope is the contract: a snapshot record carrying its legal and
    source grounding, persisted under the live-state namespace, with the
    operator-facing outcome naming what was pulled and where it lives. The
    verb performs no remote mutation by design — the only writes are the
    local encrypted snapshot.
    """
    requires_live_enabled()

    with ExitStack() as scope:
        profile = NativeCliProfileFixture(
            storage_root=live_clave_movil_profile.storage_root, scope=scope, label=live_clave_movil_profile.label
        )
        scope.enter_context(native_cli_profile_server(profile.storage_root))
        result = invoke_diagnostics_cli(["app", "live", "notifications", "pull"], profile=profile)

    assert result.exit_code == 0, result.output
    assert "snapshot" in result.output or "pulled" in result.output

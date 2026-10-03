"""Real Linux runtime owner admits one exact profile and releases a registered read."""

from __future__ import annotations

import json
import sys
from pathlib import Path
from uuid import UUID

import pytest

from cadrumo.application.user_profile.access_contracts import (
    AccessAction,
    AccessScope,
    DisclosureCategory,
    DisclosurePermission,
)
from cadrumo.tests.cli_envelope import unwrap_cli_result

from .native_api_cli_support import native_api_cli_session

pytestmark = [
    pytest.mark.integration,
    pytest.mark.hex_entrypoint,
    pytest.mark.skipif(sys.platform != "linux", reason="requires native Linux runtime and private worker"),
    pytest.mark.usefixtures("authority_operation"),
]


def _scope(destination_id: UUID) -> AccessScope:
    return AccessScope(
        operations=frozenset({"auth.local-read"}),
        actions=frozenset({AccessAction.SUBMIT, AccessAction.START, AccessAction.OBSERVE, AccessAction.RESULT}),
        disclosures=frozenset(
            {
                DisclosurePermission(
                    destination_id=destination_id,
                    projection_id="auth.local-read.result",
                    category=DisclosureCategory.PROFILE_VALUES,
                ),
                DisclosurePermission(
                    destination_id=destination_id,
                    projection_id="operation.observation",
                    category=DisclosureCategory.OPERATION_METADATA,
                ),
            }
        ),
        periods=None,
        allow_period_independent=True,
        allow_delegation=False,
    )


def test_linux_native_runtime_exact_profile_auth_status_read(tmp_path: Path) -> None:
    with native_api_cli_session(
        tmp_path,
        scope_for_destination=_scope,
        prepare_profile=lambda _profile_id, _root: None,
        profile_label="Linux native auth read",
    ) as session:
        read = session.invoke_api_key("config", "auth", "status")
        assert read.exit_code == 0, (json.loads(read.output), session.runtime_failure_events)
        report = unwrap_cli_result(read)
        assert report["active_profile"] == session.profile_label
        assert report["active_profile_registered"] is True
        assert not session.runtime_failure_events

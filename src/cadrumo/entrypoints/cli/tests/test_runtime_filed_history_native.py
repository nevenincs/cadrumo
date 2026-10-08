"""Native profile-worker admission for a filed-history sweep without AEAT access."""

from __future__ import annotations

import sys
from pathlib import Path
from typing import cast
from uuid import UUID

import pytest

from ....application.live.filed_history_operation import FILED_HISTORY_OPERATION_DEFINITION_ID
from ....application.user_profile.access_contracts import (
    AccessAction,
    AccessScope,
    DisclosureCategory,
    DisclosurePermission,
)
from ....core.period import Period
from ....tests.cli_envelope import require_error_document
from .native_api_cli_support import native_api_cli_session

pytestmark = [
    pytest.mark.integration,
    pytest.mark.hex_entrypoint,
    pytest.mark.windows_only,
    pytest.mark.skipif(sys.platform != "win32", reason="requires native Windows profile workers"),
]


def _scope(client_id: UUID, *, periods: frozenset[Period] | None) -> AccessScope:
    return AccessScope(
        operations=frozenset({FILED_HISTORY_OPERATION_DEFINITION_ID}),
        actions=frozenset(
            {
                AccessAction.SUBMIT,
                AccessAction.START,
                AccessAction.RESUME,
                AccessAction.COMMIT,
                AccessAction.OBSERVE,
                AccessAction.RESULT,
                AccessAction.DETACH,
            }
        ),
        disclosures=frozenset(
            {
                DisclosurePermission(
                    destination_id=client_id,
                    projection_id="operation.observation",
                    category=DisclosureCategory.OPERATION_METADATA,
                ),
                DisclosurePermission(
                    destination_id=client_id,
                    projection_id=f"{FILED_HISTORY_OPERATION_DEFINITION_ID}.result",
                    category=DisclosureCategory.TAX_VALUES,
                ),
            }
        ),
        periods=periods,
        allow_period_independent=True,
        allow_delegation=False,
    )


def test_native_filed_history_refuses_finite_period_before_provider_access(tmp_path: Path) -> None:
    """An API grant limited to a quarter cannot launch profile-wide AEAT discovery."""
    with native_api_cli_session(
        tmp_path,
        scope_for_destination=lambda client_id: _scope(
            client_id, periods=frozenset({Period.from_year_and_code(2025, "1T")})
        ),
        prepare_profile=lambda _profile_id, _root: None,
    ) as session:
        refused = session.invoke_credential_reference("app", "live", "filed", "pull-all", "--limit", "1")

    assert refused.exit_code == 2
    error = require_error_document(refused.output)["error"]
    assert error["code"] == "REFUSED_RUNTIME_FRONTEND"
    assert cast(dict[str, object], error["context"]) == {"reason": "period_denied"}


def test_native_filed_history_requires_configured_provider_before_browser(tmp_path: Path) -> None:
    """Whole-profile local authority does not invent a configured AEAT provider."""
    with native_api_cli_session(
        tmp_path,
        scope_for_destination=lambda client_id: _scope(client_id, periods=None),
        prepare_profile=lambda _profile_id, _root: None,
    ) as session:
        refused = session.invoke_credential_reference("app", "live", "filed", "pull-all", "--limit", "1")

    assert refused.exit_code == 2
    error = require_error_document(refused.output)["error"]
    assert error["code"] == "REFUSED_CLI_BOUNDARY"
    context = cast(dict[str, object], error["context"])
    assert context["reason"] == "REFUSED_PROFILE_ACCESS"
    assert context["terminal_condition"] == "refused"
    assert isinstance(context["operation_id"], str)

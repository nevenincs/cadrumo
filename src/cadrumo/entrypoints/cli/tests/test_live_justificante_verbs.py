"""CLI surface tests for `aeat app live justificante {list, view}`.

The ``capture`` verb is a live read (covered by the application-layer
orchestrator and the opt-in live test); these tests exercise the local
read verbs and the registration wiring without contacting AEAT.
"""

from __future__ import annotations

import hashlib
import sys
from collections.abc import Sequence
from datetime import UTC, datetime
from pathlib import Path
from typing import cast
from uuid import UUID

import pytest
from click.testing import Result

from ....application.live.justificante import JustificanteCaptureSnapshot
from ....application.live.justificante_read_operation import (
    JUSTIFICANTE_LIST_DEFINITION_ID,
    JUSTIFICANTE_SHOW_DEFINITION_ID,
)
from ....application.operations.frontend_requests import OPERATION_OBSERVATION_PROJECTION_ID
from ....application.user_profile.access_contracts import (
    AccessAction,
    AccessScope,
    DisclosureCategory,
    DisclosurePermission,
)
from ....core.period import Period
from ....tests.cli_envelope import unwrap_cli_result
from ...justificante_composition import build_justificante_capture_service
from .cli_runner import invoke_cached_cli
from .native_api_cli_support import NativeApiCliSession, native_api_cli_session

# INTENTIONAL: integration because it exercises the local justificante read verbs and
# registration wiring without contacting AEAT.
pytestmark = [
    pytest.mark.integration,
    pytest.mark.hex_entrypoint,
    pytest.mark.windows_only,
    pytest.mark.skipif(sys.platform != "win32", reason="requires native Windows profile workers"),
]


_READ_OPERATIONS = (JUSTIFICANTE_LIST_DEFINITION_ID, JUSTIFICANTE_SHOW_DEFINITION_ID)


def _justificante_scope(client_id: UUID) -> AccessScope:
    """Grant only the two exact-profile reads and their registered projections."""
    return AccessScope(
        operations=frozenset(_READ_OPERATIONS),
        actions=frozenset(
            {
                AccessAction.SUBMIT,
                AccessAction.START,
                AccessAction.RESUME,
                AccessAction.OBSERVE,
                AccessAction.RESULT,
                AccessAction.CANCEL,
                AccessAction.DETACH,
            }
        ),
        disclosures=frozenset(
            {
                DisclosurePermission(
                    destination_id=client_id,
                    projection_id=OPERATION_OBSERVATION_PROJECTION_ID,
                    category=DisclosureCategory.OPERATION_METADATA,
                ),
                *(
                    DisclosurePermission(
                        destination_id=client_id,
                        projection_id=f"{definition_id}.result",
                        category=DisclosureCategory.TAX_VALUES,
                    )
                    for definition_id in _READ_OPERATIONS
                ),
            }
        ),
        periods=None,
        allow_period_independent=True,
        allow_delegation=False,
    )


def _invoke_justificante[Prepared](fixture: NativeApiCliSession[Prepared], args: Sequence[str]) -> Result:
    """Invoke only through the shared exact-profile credential-reference route."""
    return fixture.invoke_credential_reference("app", "live", "justificante", *args)


def test_justificante_list_is_empty_on_fresh_bucket(tmp_path: Path) -> None:
    with native_api_cli_session(
        tmp_path,
        scope_for_destination=_justificante_scope,
        prepare_profile=lambda _profile_id, _root: None,
    ) as session:
        result = _invoke_justificante(session, ["list"])
    assert result.exit_code == 0, result.output
    result_payload = unwrap_cli_result(result)
    assert result_payload["count"] == 0
    assert result_payload["rows"] == []


def test_justificante_capture_command_is_not_registered() -> None:
    result = invoke_cached_cli(["app", "live", "justificante", "capture", "--help"])

    assert result.exit_code != 0
    assert "No such command" in result.output


def test_justificante_view_refuses_unknown_snapshot(tmp_path: Path) -> None:
    with native_api_cli_session(
        tmp_path,
        scope_for_destination=_justificante_scope,
        prepare_profile=lambda _profile_id, _root: None,
    ) as session:
        result = _invoke_justificante(session, ["view", "no-such-snapshot"])
    assert result.exit_code != 0


def _prepare_snapshot(profile_id: UUID, _storage_root: Path) -> JustificanteCaptureSnapshot:
    """Persist one synthetic receipt through the profile's encrypted object store."""
    pdf_bytes = b"%PDF-1.4\njustificante period cli smoke\n%%EOF"
    return build_justificante_capture_service(str(profile_id)).capture(
        modelo="130",
        filing_year=2026,
        period=Period.from_year_and_code(2026, "1T"),
        expediente_id="202613000010001A",
        csv="ABCD1234EFGH5678",
        pdf_bytes=pdf_bytes,
        pdf_sha256=hashlib.sha256(pdf_bytes).hexdigest(),
        captured_at=datetime(2026, 4, 20, 10, 30, tzinfo=UTC),
    )


def test_justificante_list_and_view_emit_registry_period_tokens(tmp_path: Path) -> None:
    with native_api_cli_session(
        tmp_path,
        scope_for_destination=_justificante_scope,
        prepare_profile=_prepare_snapshot,
    ) as session:
        snapshot = session.prepared
        listed = _invoke_justificante(session, ["list"])
        assert listed.exit_code == 0, listed.output
        listed_payload = unwrap_cli_result(listed)
        listed_rows = cast("list[dict[str, object]]", listed_payload["rows"])
        assert listed_payload["count"] == 1
        assert len(listed_rows) == 1
        assert listed_rows[0]["snapshot_id"] == snapshot.snapshot_id
        assert listed_rows[0]["modelo"] == "130"
        assert listed_rows[0]["filing_year"] == 2026
        assert listed_rows[0]["period"] == "1T"
        assert "2026 1T" not in listed.output

        viewed = _invoke_justificante(session, ["view", snapshot.snapshot_id[:12]])
        assert viewed.exit_code == 0, viewed.output
        viewed_payload = unwrap_cli_result(viewed)
        assert viewed_payload["filing_year"] == 2026
        assert viewed_payload["period"] == "1T"
        assert "period\t2026 1T" not in viewed.output

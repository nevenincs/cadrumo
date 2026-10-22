"""An executed operation's reply carries the link to the page that shows its records."""

from __future__ import annotations

from uuid import UUID

import pytest

from cadrumo.application.auth.auth_read_contracts import AUTH_READ_OPERATION_DEFINITION_ID
from cadrumo.application.modelo.revision_snapshot_operation import (
    MODELO_WORK_REVISION_SNAPSHOT_OPERATION_DEFINITION_ID,
)
from cadrumo.application.workflow.run_read_operation import WORKFLOW_RUN_READ_OPERATION_DEFINITION_ID

from .test_execute_subject_tool import _RUN_ID, _execute, _RecordingClient, _run_payload, _snapshot_payload

pytestmark = [pytest.mark.integration, pytest.mark.hex_core]

_PROFILE = UUID("5aa00000-0000-4000-8000-0000000000aa")


@pytest.mark.anyio
async def test_a_submitted_profile_operation_links_its_page_even_when_its_outcome_is_unknown() -> None:
    client = _RecordingClient(_PROFILE)

    result = await _execute(client, {"definition_id": AUTH_READ_OPERATION_DEFINITION_ID, "payload": {"kind": "status"}})

    # The submission may have committed, so the person is still shown where to look.
    assert result["outcome"] == "unresolved"
    assert result["page"] == {
        "destination": "aeat_auth",
        "url": "cadrumo://profiles/5aa00000-0000-4000-8000-0000000000aa/aeat-auth",
    }


@pytest.mark.anyio
async def test_a_declaration_operation_links_the_declarations_page() -> None:
    client = _RecordingClient(_PROFILE)

    result = await _execute(
        client,
        {
            "definition_id": MODELO_WORK_REVISION_SNAPSHOT_OPERATION_DEFINITION_ID,
            "subject_ref": "c" * 64,
            "payload": _snapshot_payload(_PROFILE),
        },
    )

    assert result["page"]["url"] == "cadrumo://profiles/5aa00000-0000-4000-8000-0000000000aa/declarations"


@pytest.mark.anyio
async def test_an_operation_no_page_shows_carries_no_link() -> None:
    client = _RecordingClient(_PROFILE)

    result = await _execute(
        client, {"definition_id": WORKFLOW_RUN_READ_OPERATION_DEFINITION_ID, "payload": _run_payload(_PROFILE)}
    )

    assert [item.subject_ref for item in client.submitted] == [_RUN_ID]
    assert "page" not in result


@pytest.mark.anyio
async def test_a_refused_call_changed_nothing_and_carries_no_link() -> None:
    client = _RecordingClient(_PROFILE)

    result = await _execute(
        client,
        {
            "definition_id": AUTH_READ_OPERATION_DEFINITION_ID,
            "subject_ref": str(_PROFILE),
            "payload": {"kind": "status"},
        },
    )

    assert result["outcome"] == "refused"
    assert "page" not in result
    assert client.submitted == []

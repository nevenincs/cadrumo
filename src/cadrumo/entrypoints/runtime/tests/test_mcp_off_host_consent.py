"""Consent to send a stored document to a hosted model is the person's act, never an agent's.

An agent connected through MCP may ask for the extraction that stays on this
machine. The read that sends the document off it carries the person's
per-invocation acknowledgement, which only the person gives in Cadrumo; the
runtime refuses it on the MCP frontend before anything is submitted, and goes
on admitting it from the command line. No document is stored here, so an
admitted submission ends at the missing source and no model, hosted or local,
is ever asked.

The adapter, the installed clients, the native transport, the runtime, its
access policy and registered resolver, and the profile worker are real; the
native login, the keychain and the wall clock are ports held by the test.
"""

from __future__ import annotations

import asyncio
import json
import sys
import time
from pathlib import Path
from uuid import uuid4

import pytest

from cadrumo.adapters.local_runtime.frontend_client_contracts import RuntimeFrontendRefusedError
from cadrumo.adapters.local_runtime.runtime_client import open_installed_runtime_client
from cadrumo.adapters.persistence.storage.custody.tests.enrollment_support import PROFILE_INPUT
from cadrumo.application.ledger.invoice_evidence_extract_operation import (
    LEDGER_EVIDENCE_EXTRACT_OPERATION_DEFINITION_ID,
)
from cadrumo.application.operations.registry import OperationFrontendProjection
from cadrumo.application.runtime.operation_access import RuntimeOperationSubmit, RuntimeOperationSubmitted
from cadrumo.core.config import override_settings
from cadrumo.core.config_support import LLMProvider
from cadrumo.core.operations import profile_operation_subject
from cadrumo_harness.mcp.protocol_contract import PERSON_ACT_REMEDY
from cadrumo_harness.mcp.runtime_adapter import RuntimeMcpAdapter

from .stored_sign_in_runtime import stored_sign_in_runtime

pytestmark = [
    pytest.mark.integration,
    pytest.mark.hex_entrypoint,
    pytest.mark.windows_only,
    pytest.mark.skipif(sys.platform != "win32", reason="requires native Windows worker and protected pipes"),
    pytest.mark.usefixtures("authority_operation"),
]

_EVIDENCE = "e" * 16
_ATTACHMENT = "a" * 64


def _off_host(profile_id: str) -> dict[str, object]:
    return {
        "profile_id": profile_id,
        "evidence_id": _EVIDENCE,
        "off_host_provider": LLMProvider.ANTHROPIC.value,
        "acknowledge_off_host": True,
    }


@pytest.mark.anyio
async def test_an_agent_may_extract_on_this_machine_but_never_consents_to_an_off_host_read(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    with (
        stored_sign_in_runtime(tmp_path, monkeypatch) as runtime,
        override_settings(cadrumo_active_profile=str(runtime.profile_id)),
    ):
        profile = str(runtime.profile_id)
        adapter = RuntimeMcpAdapter(profile_id=None, client=None, resumes_sign_in=True)
        try:
            off_host = await adapter.call(
                "execute",
                {"definition_id": LEDGER_EVIDENCE_EXTRACT_OPERATION_DEFINITION_ID, "payload": _off_host(profile)},
            )
            on_machine = await adapter.call(
                "execute",
                {
                    "definition_id": LEDGER_EVIDENCE_EXTRACT_OPERATION_DEFINITION_ID,
                    "payload": {"profile_id": profile, "attachment_id": _ATTACHMENT},
                    "start": False,
                },
            )
        finally:
            await adapter.close()

    assert off_host == {"outcome": "refused", "code": "person_act_required", "remedy": PERSON_ACT_REMEDY}, off_host
    assert on_machine["outcome"] == "submitted", on_machine


@pytest.mark.anyio
async def test_the_person_still_consents_to_an_off_host_read_at_the_command_line(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    with stored_sign_in_runtime(tmp_path, monkeypatch) as runtime:
        profile = str(runtime.profile_id)
        # The person acknowledges the off-host read for themselves.
        person = await open_installed_runtime_client(
            profile_id=runtime.profile_id, frontend=OperationFrontendProjection.CLI
        )
        try:
            await asyncio.to_thread(person.login_password, bytearray(PROFILE_INPUT.encode()), timeout=120)
            submission = RuntimeOperationSubmit(
                request_id=uuid4(),
                profile_id=runtime.profile_id,
                session_id=person.session_id,
                definition_id=LEDGER_EVIDENCE_EXTRACT_OPERATION_DEFINITION_ID,
                subject_ref=profile_operation_subject(profile),
                payload_json=json.dumps(_off_host(profile)),
                idempotency_key=None,
            )
            try:
                persons = await asyncio.to_thread(person.operation, submission, deadline=time.monotonic() + 60)
            except RuntimeFrontendRefusedError as refused:
                persons = refused.reason
        finally:
            await asyncio.to_thread(person.close)

    assert isinstance(persons, RuntimeOperationSubmitted), persons

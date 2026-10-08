"""Real interactive flow commits only through its authenticated runtime client."""

from __future__ import annotations

import asyncio
from datetime import date
from io import StringIO
from pathlib import Path
from uuid import UUID

import pytest
import typer
from prompt_toolkit.input import create_pipe_input
from prompt_toolkit.output.plain_text import PlainTextOutput

from cadrumo.adapters.local_runtime.runtime_client import open_installed_runtime_client
from cadrumo.adapters.persistence.storage.master_key.active_session import close_active_bucket_session
from cadrumo.application.flows.errors import FlowRunAbandonedError
from cadrumo.application.operations.registry import OperationFrontendProjection
from cadrumo.application.user_profile.view_operation import ProfileViewPageKind
from cadrumo.entrypoints.cli.main import app
from cadrumo.entrypoints.cli.runtime_profile_binding import bind_profile_client

from .._profile_support import require_active_profile_pointer
from ..runtime_descendant_door import run_runtime_descendant_door
from .isolated_storage_fixture import CREDENTIAL_INPUT, native_profile_view_server
from .isolated_storage_fixture import live_cli_profile as live_cli_profile

pytestmark = [
    pytest.mark.integration,
    pytest.mark.hex_entrypoint,
    pytest.mark.windows_only,
    pytest.mark.usefixtures("authority_operation"),
]


def test_bound_interactive_flow_publishes_once_and_abandonment_does_not_write(
    live_cli_profile: None, tmp_path: Path
) -> None:
    """Real line widgets retain the original revision without ambient custody."""
    profile_id = UUID(str(require_active_profile_pointer().bucket_id))
    close_active_bucket_session()
    with native_profile_view_server(tmp_path / "cadrumo-storage"):
        client = asyncio.run(
            open_installed_runtime_client(profile_id=profile_id, frontend=OperationFrontendProjection.CLI)
        )
        context = typer.Context(typer.main.get_command(app))
        with context:
            bind_profile_client(context, client, profile_id=profile_id)
            client.login_password(bytearray(CREDENTIAL_INPUT.encode()))
            keys = "1\r2020-01-01\r\r\r\r\r\r\r\r\x1b[B\r\r\r\r\r\r\r"
            output = StringIO()
            with create_pipe_input() as pipe:
                pipe.send_text(keys)
                pipe.close()
                rows = run_runtime_descendant_door(context, input=pipe, output=PlainTextOutput(output))
            assert len(rows) == 1 and rows[0].birth_date == date(2020, 1, 1)
            assert CREDENTIAL_INPUT not in output.getvalue()
            before = client.read_profile_view((ProfileViewPageKind.FACTS,), timeout=60)
            with create_pipe_input() as pipe:
                pipe.send_text("\x03")
                pipe.close()
                with pytest.raises(FlowRunAbandonedError):
                    run_runtime_descendant_door(context, input=pipe, output=PlainTextOutput(StringIO()))
            after = client.read_profile_view((ProfileViewPageKind.FACTS,), timeout=60)
            assert after.record_revision == before.record_revision
            assert after.content_digest == before.content_digest

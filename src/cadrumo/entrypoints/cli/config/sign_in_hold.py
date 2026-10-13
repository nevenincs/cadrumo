"""Hold a person's live sign-in for the life of standard input, and decide which agent connections follow it.

The sign-in is a password login on this process's own runtime connection and
is never persisted. An MCP connection that asks to follow it is shown as one
event line, with the process the kernel names, and is admitted only when this
process approves that exact ask. Closing standard input, signing out, or the
session's own end ends the sign-in and every connection that followed it.

Standard input carries, in order: one JSON object with the profile password,
``{"passphrase": "..."}``, on the first line; then one JSON object per line,
``{"approve": "<attendance id>"}``, ``{"decline": "<attendance id>"}`` or
``{"sign_out": true}``. Standard output carries one JSON object per event line,
each naming its ``event``, and then the command's result.
"""

from __future__ import annotations

import asyncio
import json
import os
import sys
from queue import Empty, Queue
from threading import Thread
from typing import TYPE_CHECKING, Final, Literal
from uuid import UUID

import typer

from ....core.external_constants import OutputLanguage
from ..common import activate_subcommand_output_language as _activate_subcommand_output_language
from ..common import emit_envelope

if TYPE_CHECKING:
    from ....adapters.local_runtime.frontend_client import RuntimeFrontendClient

_SECRET_LINE_MAX_BYTES: Final = 16 * 1024
_COMMAND_LINE_MAX_BYTES: Final = 4 * 1024
_POLL_SECONDS: Final = 0.25
_INPUT_CLOSED: Final = b""

type _Ending = Literal["input_closed", "signed_out", "session_ended"]


def config_sign_in_hold(
    ctx: typer.Context,
    name: str | None = None,
    output_language: OutputLanguage | None = None,
) -> None:
    """Hold one profile's sign-in, unpersisted, until standard input closes."""
    _activate_subcommand_output_language(ctx, output_language)
    from cadrumo.adapters.local_runtime.runtime_client import open_installed_runtime_client

    from ....adapters.local_runtime.frontend_client_contracts import RuntimeFrontendRefusedError
    from ....application.operations.registry import OperationFrontendProjection
    from ....application.user_profile.login_session import resolve_login_target
    from ....application.user_profile.profile_pointer import (
        active_profile_pointer_transaction,
        observe_active_profile_pointer,
    )
    from ....domain.user_profile.errors import ProfileNotFoundError
    from ..common import no_active_profile_refusal
    from ._profile_support import unknown_profile_refusal
    from .custody import _require_current_profile_login
    from .custody_payloads import ConfigSignInHoldResult

    captured = observe_active_profile_pointer()
    target_name = name or captured.bucket_id
    if target_name is None:
        raise no_active_profile_refusal()
    try:
        target = resolve_login_target(target_name)
    except ProfileNotFoundError:
        raise unknown_profile_refusal(target_name) from None
    lines = _InputLines()
    proof = _read_password_line(lines)
    client = asyncio.run(
        open_installed_runtime_client(profile_id=UUID(target.bucket_id), frontend=OperationFrontendProjection.CLI)
    )
    try:
        try:
            client.login_password(proof, persist_receipt=False)
        finally:
            proof[:] = bytes(len(proof))
        _require_current_profile_login(client)
        with active_profile_pointer_transaction() as selection:
            selection.compare_and_select(expected=captured, bucket_id=target.bucket_id)
        ended, approved, declined = _hold(client, lines)
    except RuntimeFrontendRefusedError as error:
        from .._profile_session_gate import raise_runtime_refusal

        raise_runtime_refusal(error)
    finally:
        # Closing the connection ends the held session, and every attended session with it.
        client.close()
    _event("ended", reason=ended)
    emit_envelope(
        ctx,
        command="config.sign-in-hold",
        result=ConfigSignInHoldResult(profile_id=target.bucket_id, ended=ended, approved=approved, declined=declined),
        lines=(f"ended\t{ended}", f"approved\t{approved}", f"declined\t{declined}"),
    )


def _read_password_line(lines: _InputLines) -> bytearray:
    """Read the first standard-input line as the strict password object; never echo it."""
    from .custody import LoginSecrets
    from .secure_input import validate_secrets_payload

    raw = lines.next(_SECRET_LINE_MAX_BYTES + 1)
    try:
        if len(raw) > _SECRET_LINE_MAX_BYTES:
            from ..errors import CliRefusedBoundaryError

            raise CliRefusedBoundaryError(translated_message="cli.config.custody.errors.secrets_stdin_too_large")
        payload = validate_secrets_payload(
            raw,
            LoginSecrets,
            invalid_json_key="cli.config.custody.errors.secrets_stdin_invalid_json",
            missing_fields_key="cli.config.custody.errors.secrets_stdin_missing_fields",
        )
        try:
            return bytearray(payload.passphrase.get_secret_value(), "utf-8")
        finally:
            del payload
    finally:
        raw[:] = bytes(len(raw))


def _hold(client: RuntimeFrontendClient, lines: _InputLines) -> tuple[_Ending, int, int]:
    """Report asks and apply decisions until input closes, the person signs out, or the session ends."""
    from ....adapters.local_runtime.frontend_client_contracts import RuntimeFrontendRefusedError
    from ....application.runtime.contracts import RuntimeRefusalError

    commands: Queue[bytes] = Queue()
    Thread(target=_read_commands, args=(lines, commands), name="sign-in-hold-input", daemon=True).start()
    announced: set[UUID] = set()
    approved = declined = 0
    try:
        inventory = client.attendance_inventory()
    except (RuntimeFrontendRefusedError, RuntimeRefusalError):
        return "session_ended", approved, declined
    _event("held", profile_id=str(client.profile_id), session_expires_at=inventory.session_expires_at.isoformat())
    while True:
        try:
            line = commands.get(timeout=_POLL_SECONDS)
        except Empty:
            line = None
        except KeyboardInterrupt:
            return "input_closed", approved, declined
        if line == _INPUT_CLOSED:
            return "input_closed", approved, declined
        if line is not None:
            outcome = _apply(client, line)
            if outcome == "signed_out":
                return "signed_out", approved, declined
            approved += outcome == "approved"
            declined += outcome == "declined"
        try:
            inventory = client.attendance_inventory()
        except (RuntimeFrontendRefusedError, RuntimeRefusalError) as error:
            # The session ended by deadline, lock or sign-out elsewhere, or the runtime itself stopped.
            _event("session_ended", code=str(error.reason))
            return "session_ended", approved, declined
        for candidate in inventory.candidates:
            if candidate.attendance_id in announced:
                continue
            announced.add(candidate.attendance_id)
            _event(
                "attendance_request",
                attendance_id=str(candidate.attendance_id),
                process_id=candidate.process_id,
                image_path=candidate.image_path,
                frontend=candidate.frontend.value,
                surface=candidate.surface,
                expires_at=candidate.expires_at.isoformat(),
            )


def _apply(client: RuntimeFrontendClient, line: bytes) -> Literal["approved", "declined", "signed_out", "refused"]:
    """Apply one decision line; a malformed line or a refused decision is reported and changes nothing."""
    from ....adapters.local_runtime.frontend_client_contracts import RuntimeFrontendRefusedError

    try:
        command = json.loads(line)
    except ValueError:
        command = None
    if command == {"sign_out": True}:
        try:
            client.human_sign_out()
        except RuntimeFrontendRefusedError as error:
            _event("sign_out_refused", code=error.reason)
            return "refused"
        _event("signed_out")
        return "signed_out"
    decision = _decision(command)
    if decision is None:
        _event("input_refused")
        return "refused"
    attendance_id, approve = decision
    try:
        decided = client.decide_attendance(attendance_id, approve=approve)
    except RuntimeFrontendRefusedError as error:
        _event("attendance_refused", attendance_id=str(attendance_id), code=error.reason)
        return "refused"
    _event("attendance_decided", attendance_id=str(decided.attendance_id), approved=decided.approved)
    return "approved" if decided.approved else "declined"


def _decision(command: object) -> tuple[UUID, bool] | None:
    if not isinstance(command, dict) or len(command) != 1:
        return None
    approve = "approve" in command
    value = command.get("approve" if approve else "decline")
    if not isinstance(value, str):
        return None
    try:
        return UUID(value), approve
    except ValueError:
        return None


class _InputLines:
    """Split standard input into lines from its raw descriptor.

    The buffered ``sys.stdin`` reader holds a lock while it blocks, and a
    daemon thread left blocked on it when the interpreter finalizes can abort
    the process. The raw descriptor has no such lock, and keeps no line the
    password read did not consume out of reach of the command reader.
    """

    def __init__(self) -> None:
        self._pending = bytearray()

    def next(self, limit: int) -> bytearray:
        """Return the next line, at most ``limit`` bytes, or an empty one at end of input."""
        while b"\n" not in self._pending and len(self._pending) < limit:
            try:
                chunk = os.read(0, 4096)
            except OSError:
                chunk = b""
            if not chunk:
                break
            self._pending += chunk
        end = self._pending.find(b"\n")
        size = min(limit, len(self._pending) if end < 0 else end + 1)
        line = self._pending[:size]
        self._pending[:size] = bytes(size)
        del self._pending[:size]
        return line


def _read_commands(lines: _InputLines, commands: Queue[bytes]) -> None:
    while line := lines.next(_COMMAND_LINE_MAX_BYTES):
        if line.strip():
            commands.put(bytes(line))
    commands.put(_INPUT_CLOSED)


def _event(kind: str, **fields: object) -> None:
    sys.stdout.write(json.dumps({"event": kind, **fields}, separators=(",", ":")) + "\n")
    sys.stdout.flush()

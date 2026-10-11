"""Send one sessionless installation act from a command and bring back its reply.

A command that works with no profile open asks the runtime to do the work
instead of doing it in this process, so the terminal interface and MCP reach
the same act. The command builds the act's request, calls
:func:`run_installation_act`, and projects the reply onto its own envelope. A
refusal is raised as the error the in-process command would have raised, so
the shared command boundary renders it in the envelope unchanged.
"""

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING

from ...application.runtime.installation_requests import (
    RuntimeInstallationActRequest,
    RuntimeInstallationCompleted,
    RuntimeInstallationFailed,
    RuntimeInstallationRefused,
)
from .errors import CliRecordedOperationError, CliRefusedBoundaryError, CliUnexpectedBoundaryError

if TYPE_CHECKING:
    from ...adapters.local_runtime.installation_client import InstallationSecretHolder


def run_installation_act[ReplyT: RuntimeInstallationCompleted](
    request: RuntimeInstallationActRequest,
    reply_type: type[ReplyT],
    *,
    secret: bytearray | None = None,
    hold_secret: InstallationSecretHolder | None = None,
    timeout: float | None = None,
) -> ReplyT:
    """Send ``request`` to the running runtime and return the act's completed reply.

    Args:
        request: The act's request, naming this frontend.
        reply_type: The reply the act's contract declares for it.
        secret: The act's one secret frame, built with
            ``installation_passphrase_document``, for an act that takes one.
            It is consumed and wiped.
        hold_secret: Receives the act's delivered secret, for an act that
            delivers one, and returns the copy read back.
        timeout: Seconds for the whole exchange; the act's default when omitted.

    Raises:
        CliRecordedOperationError: The act was refused with a registered error,
            or stopped on a fault with no public facts.
        CliRefusedBoundaryError: The runtime refused admission.
        RuntimeRefusalError: The runtime is not running, or the transport refused.
    """
    from ...adapters.local_runtime.frontend_client_contracts import RuntimeFrontendRefusedError
    from ...adapters.local_runtime.installation_client import open_installed_installation_client

    client = asyncio.run(open_installed_installation_client())
    try:
        try:
            settled = client.perform(request, reply_type, secret=secret, hold_secret=hold_secret, timeout=timeout)
        except RuntimeFrontendRefusedError as error:
            raise CliRefusedBoundaryError(error.reason, context=error.context) from error
    except BaseException as primary:
        try:
            client.close()
        except Exception:
            primary.add_note("Runtime connection cleanup did not complete.")
        raise
    else:
        client.close()
    if isinstance(settled, RuntimeInstallationRefused):
        raise _refused(settled)
    if isinstance(settled, RuntimeInstallationFailed):
        raise _failed(settled)
    return settled


def _refused(reply: RuntimeInstallationRefused) -> CliRecordedOperationError:
    """Rebuild the error the act's handler stopped with from its recorded public detail."""
    from .registered_operation_errors import detailed_registered_operation_error

    return detailed_registered_operation_error(reply.detail, {})


def _failed(reply: RuntimeInstallationFailed) -> CliRecordedOperationError:
    """Report a fault with no public facts as unexpected, never as a refusal.

    An act that changes records may have changed some before it stopped, so the
    effect is reported as unknown.
    """
    from ...core.errors.error_codes import get_registered_error_code

    unexpected = get_registered_error_code(CliUnexpectedBoundaryError)
    return CliRecordedOperationError(
        unexpected.code,
        context={"installation_act": reply.act.value, "effect": "unknown"},
        translated_message=unexpected.message_key,
    )

"""Send one sessionless installation act from a command and bring back its reply.

A command that works with no profile open asks the runtime to do the work
instead of doing it in this process, so the terminal interface and external client reach
the same act. The command builds the act's request, calls
:func:`run_installation_act_if_runtime`, and projects the reply onto its own envelope. A
refusal is raised as the error the in-process command would have raised, so
the shared command boundary renders it in the envelope unchanged.
"""

from __future__ import annotations

import asyncio
from collections.abc import Mapping
from types import MappingProxyType
from typing import TYPE_CHECKING, Final

from cadrumo_client.contracts.contracts import EndpointPresence, RefusalCode, RefusalError
from cadrumo_client.contracts.installation_requests import (
    INSTALLATION_ACT_CONTRACTS,
    InstallationAct,
    InstallationActRequest,
    InstallationCompleted,
    InstallationFailed,
    InstallationRefused,
    installation_act_of,
)

from ...core.errors.hierarchy import CadrumoError
from .errors import (
    CliOperationStillRunningError,
    CliRecordedOperationError,
    CliRefusedBoundaryError,
    CliUnexpectedBoundaryError,
)

if TYPE_CHECKING:
    from cadrumo_client.transport.installation_client import InstallationClient, InstallationSecretHolder

_SENT_ACT_REFUSALS: Final = frozenset({RefusalCode.DEADLINE_EXCEEDED, RefusalCode.CONNECTION_CLOSED})
"""The transport outcomes that arise only after an act was sent, so what it did is not known."""

_UNANSWERED_REFUSALS: Final = frozenset({RefusalCode.UNAVAILABLE, RefusalCode.DEADLINE_EXCEEDED})
"""The outcomes of opening a connection that a later attempt can cure: busy, timed out, or unreadable."""


def run_installation_act_if_runtime[ReplyT: InstallationCompleted](
    request: InstallationActRequest,
    reply_type: type[ReplyT],
    *,
    timeout: float | None = None,
) -> ReplyT | None:
    """Send ``request`` to the runtime when one is running, and say so when none is.

    ``None`` means the storage root has no runtime endpoint, and nothing was
    sent: the caller does the work in this process. Nothing else means that. A
    refusal to connect is not proof of absence: a runtime whose endpoint is
    busy, one that did not answer in time and one whose state could not be read
    all refuse while they host the workers the caller's own work would run
    beside. Those are reported, with the retry, and every other outcome stands:
    a runtime that answered, refused, could not be verified, or stopped
    answering after the send may have done the work.

    Raises:
        CliRefusedBoundaryError: A runtime may own the root but could not be
            reached, or refused admission. Nothing was sent in the first case.
        CliRecordedOperationError: The handler refused the act with a registered
            error, or stopped on a fault with no public facts.
        CliOperationStillRunningError: The connection stopped answering after
            an act that changes records was sent, leaving its outcome unknown.
        RefusalError: The transport refused for another reason.
    """
    from cadrumo_client.transport.installation_client import (
        installed_connection_presence,
        open_installed_installation_client,
    )

    presence = asyncio.run(installed_connection_presence())
    if presence is EndpointPresence.ABSENT:
        return None
    try:
        client = asyncio.run(open_installed_installation_client())
    except RefusalError as refusal:
        if refusal.reason not in _UNANSWERED_REFUSALS:
            raise
        raise _unanswered(presence, refusal) from refusal
    return _settle(client, request, reply_type, secret=None, hold_secret=None, timeout=timeout)


def _unanswered(presence: EndpointPresence, refusal: RefusalError) -> CliRefusedBoundaryError:
    """Report a runtime that was not shown to be absent and gave no connection to send on.

    Nothing was sent, so nothing changed, and the same command may be run
    again. A release the failed opening still owes stays owned by the report.
    """
    from ...core.async_cleanup import async_cleanup_failures, attach_async_cleanup_error

    report = CliRefusedBoundaryError(
        "a runtime may be serving this storage root but could not be reached, so nothing was sent "
        "and nothing was changed; run the command again",
        context={
            "runtime_endpoint": presence.value,
            "runtime_refusal": refusal.reason.value,
            "effect": "none",
            "retry": "same_command",
        },
    )
    for failure in async_cleanup_failures(refusal):
        attach_async_cleanup_error(report, failure)
    return report


def _settle[ReplyT: InstallationCompleted](
    client: InstallationClient,
    request: InstallationActRequest,
    reply_type: type[ReplyT],
    *,
    secret: bytearray | None,
    hold_secret: InstallationSecretHolder | None,
    timeout: float | None,
) -> ReplyT:
    from cadrumo_client.transport.frontend_client_contracts import FrontendRefusedError

    try:
        try:
            settled = client.perform(request, reply_type, secret=secret, hold_secret=hold_secret, timeout=timeout)
        except FrontendRefusedError as error:
            raise CliRefusedBoundaryError(error.reason, context=error.context) from error
        except RefusalError as refusal:
            raise _unknown_outcome(request, refusal) from refusal
    except BaseException as primary:
        try:
            client.close()
        except Exception:
            primary.add_note("Runtime connection cleanup did not complete.")
        raise
    else:
        client.close()
    if isinstance(settled, InstallationRefused):
        raise _refused(settled)
    if isinstance(settled, InstallationFailed):
        raise _failed(settled)
    return settled


_OUTCOME_READERS: Final[Mapping[InstallationAct, str]] = MappingProxyType(
    {InstallationAct.RESET_STATUS: "config reset status"}
)
"""The command that runs each act that reads an outcome."""


def _unknown_outcome(request: InstallationActRequest, refusal: RefusalError) -> CadrumoError:
    """Report an act the client stopped waiting for as unsettled, never as failed.

    The runtime keeps working on an act it admitted, so an act that changes
    records may have committed. The error names the read that shows how it
    settled. Anything else the transport refused is returned unchanged.
    """
    contract = INSTALLATION_ACT_CONTRACTS[installation_act_of(request)]
    reader = contract.outcome_read_by
    if reader is None or refusal.reason not in _SENT_ACT_REFUSALS:
        return refusal
    return CliOperationStillRunningError(
        operation_id=str(request.request_id), effect="unknown", check_command=_OUTCOME_READERS[reader]
    )


def _refused(reply: InstallationRefused) -> CliRecordedOperationError:
    """Rebuild the error the act's handler stopped with from its recorded public detail."""
    from cadrumo_client.commands.registered_operation_errors import detailed_registered_operation_error

    return detailed_registered_operation_error(reply.detail, {})


def _failed(reply: InstallationFailed) -> CliRecordedOperationError:
    """Report a fault with no public facts as unexpected, never as a refusal.

    An act that changes records may have changed some before it stopped, so the
    effect is reported as unknown, with the read that shows how it settled
    where the act has one.
    """
    from ...core.errors.error_codes import get_registered_error_code

    unexpected = get_registered_error_code(CliUnexpectedBoundaryError)
    context: dict[str, object] = {"installation_act": reply.act.value, "effect": "unknown"}
    reader = INSTALLATION_ACT_CONTRACTS[reply.act].outcome_read_by
    if reader is not None:
        context["check_command"] = _OUTCOME_READERS[reader]
    return CliRecordedOperationError(unexpected.code, context=context, translated_message=unexpected.message_key)

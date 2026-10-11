"""Send one installation act to the running runtime and say how it settled.

The interface holds no session and starts no runtime here. Each act opens its
own verified connection, sends one request, and closes the connection again,
which is what the command line does for the same act.
"""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from functools import partial
from logging import WARNING

from pydantic import SecretBytes

from ....adapters.local_runtime.frontend_client_contracts import RuntimeFrontendRefusedError, frontend_failure_code
from ....adapters.local_runtime.installation_client import (
    InstallationSecretHolder,
    RuntimeInstallationClient,
    installation_passphrase_document,
)
from ....application.runtime.installation_requests import (
    InstallationActContract,
    RuntimeInstallationActRequest,
    RuntimeInstallationCompleted,
    RuntimeInstallationFailed,
    RuntimeInstallationRefused,
    installation_request_facts,
)
from ....core.async_cleanup import await_cancellation_complete
from ....core.diagnostic_log import diagnostic_error_fields, diagnostic_event
from ....core.logging import get_logger

type InstallationClientOpener = Callable[[], Awaitable[RuntimeInstallationClient]]
"""Open one verified connection that names no profile session."""

_LOGGER = get_logger(__name__)


@dataclass(frozen=True, slots=True)
class ActCompleted:
    """The act ran to its end and answered with its own reply."""

    reply: RuntimeInstallationCompleted


@dataclass(frozen=True, slots=True)
class ActRefused:
    """The act's handler stopped it with a registered error."""

    reply: RuntimeInstallationRefused


@dataclass(frozen=True, slots=True)
class ActFailed:
    """The act stopped on a fault the runtime gives no public facts about."""

    reply: RuntimeInstallationFailed
    may_have_changed_records: bool


@dataclass(frozen=True, slots=True)
class ActUnreachable:
    """The runtime could not be reached, refused admission, or broke off the exchange.

    ``effect_unknown`` is true when a request that may change records had
    already been handed to the connection: the exchange ending is then no
    proof that nothing changed.
    """

    code: str
    effect_unknown: bool


@dataclass(frozen=True, slots=True)
class ActSecretDeclined:
    """The person did not keep the secret the act delivered, so the runtime committed nothing that needed it."""


type ActOutcome = ActCompleted | ActRefused | ActFailed | ActUnreachable | ActSecretDeclined


async def perform_act(
    open_client: InstallationClientOpener,
    request: RuntimeInstallationActRequest,
    contract: InstallationActContract,
    *,
    passphrase: bytearray | None = None,
    hold_secret: InstallationSecretHolder | None = None,
) -> ActOutcome:
    """Perform one act on its own connection.

    Args:
        open_client: Opens the connection the act is sent on.
        request: The act's request.
        contract: The act's row of the runtime's table.
        passphrase: The passphrase an act that takes one proves. It is
            consumed and wiped on every path, including a failed connection.
        hold_secret: Receives the secret an act that delivers one hands out.
    """
    changes_records = installation_request_facts(request).changes_records
    secret: bytearray | None = None
    declined = False

    def holding(delivered: bytearray) -> SecretBytes | None:
        nonlocal declined
        held = hold_secret(delivered) if hold_secret is not None else None
        declined = held is None
        return held

    try:
        try:
            client = await open_client()
        except Exception as error:
            return ActUnreachable(frontend_failure_code(error), effect_unknown=False)
        try:
            if passphrase is not None:
                secret = installation_passphrase_document(passphrase)
            settled = await await_cancellation_complete(
                asyncio.to_thread(
                    partial(
                        client.perform,
                        request,
                        contract.reply,
                        secret=secret,
                        hold_secret=None if hold_secret is None else holding,
                    )
                ),
                task_name="tui-installation-act",
            )
        except RuntimeFrontendRefusedError as error:
            if declined:
                return ActSecretDeclined()
            # The runtime answered: it refused before the act ran.
            return ActUnreachable(error.reason, effect_unknown=False)
        except Exception as error:
            return ActUnreachable(frontend_failure_code(error), effect_unknown=changes_records)
        finally:
            await _close(client)
    finally:
        for buffer in (passphrase, secret):
            if buffer is not None:
                buffer[:] = bytes(len(buffer))
    if isinstance(settled, RuntimeInstallationRefused):
        return ActRefused(settled)
    if isinstance(settled, RuntimeInstallationFailed):
        return ActFailed(settled, may_have_changed_records=changes_records)
    return ActCompleted(settled)


async def _close(client: RuntimeInstallationClient) -> None:
    """Release the act's connection; a failed release cannot change how the act settled."""
    try:
        await await_cancellation_complete(asyncio.to_thread(client.close), task_name="tui-installation-close")
    except Exception as error:
        diagnostic_event(
            _LOGGER,
            "tui_installation_connection_release_failed",
            fields={**diagnostic_error_fields(error), "outcome": "release_failed"},
            level=WARNING,
            primary_error=error,
        )


__all__ = [
    "ActCompleted",
    "ActFailed",
    "ActOutcome",
    "ActRefused",
    "ActSecretDeclined",
    "ActUnreachable",
    "InstallationClientOpener",
    "perform_act",
]

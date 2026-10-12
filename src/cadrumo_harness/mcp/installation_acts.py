"""Installation acts, as the command line has them: work the runtime does with no profile session.

The storage tree, the reset of all profiles, the profile list, archive inspect
and import, recovery enrolment, repair, and the verification of files the
person holds are each one request to the runtime's installation door. This
module reaches every act in the door's table: it builds the act's request from
the tool's arguments, sends it on a connection that holds no session, and
returns the act's own reply.

A passphrase an act takes arrives as a mutable buffer and leaves on the
runtime's protected secret frame. A secret an act hands to the person never
enters a reply: this server holds one copy in the machine's protected
credential store until the person has read it at a terminal of their own and
confirmed they kept it, and the reply names only the reference it is held under.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any, cast
from uuid import UUID, uuid4

from pydantic import SecretBytes

from cadrumo.adapters.local_runtime.frontend_client_contracts import RuntimeFrontendRefusedError
from cadrumo.adapters.local_runtime.installation_client import (
    RuntimeInstallationClient,
    installation_passphrase_document,
)
from cadrumo.application.operations.mcp_surfaces import McpSurface
from cadrumo.application.operations.registry import OperationFrontendProjection
from cadrumo.application.runtime.contracts import RuntimeRefusalError
from cadrumo.application.runtime.installation_requests import (
    INSTALLATION_ACT_CONTRACTS,
    InstallationAct,
    InstallationActContract,
    InstallationActFacts,
    RuntimeInstallationActRequest,
    RuntimeInstallationFailed,
    RuntimeInstallationRefused,
    installation_request_facts,
)
from cadrumo.application.user_profile.access_contracts import AccessDenialCode

from .held_secrets import HeldSecretCustody, held_secret_retrieval
from .protocol_contract import (
    INSTALLATION_CONFIRM_ARGUMENT,
    INSTALLATION_CONFIRMED_MEMBER,
    parse_model,
    public_value,
    refusal_code,
)
from .session_acts import SessionSecrets

_SERVER_SUPPLIED = frozenset({"request_id", "frontend", "action"})


def _surface_allows(surface: McpSurface, facts: InstallationActFacts) -> bool:
    return (surface.changes_records or not facts.changes_records) and (
        surface.reaches_network or not facts.reaches_network
    )


def installation_acts_on(surface: McpSurface) -> tuple[InstallationAct, ...]:
    """Name the acts a surface allows in at least one form.

    An act that changes records only once it is confirmed is allowed on a
    surface that changes none, as the report it gives unconfirmed.
    """
    # A request built with only its defaults withholds every confirmation, so
    # its facts are the least a request for that act can do.
    return tuple(
        act
        for act, contract in INSTALLATION_ACT_CONTRACTS.items()
        if _surface_allows(
            surface,
            installation_request_facts(cast("RuntimeInstallationActRequest", contract.request.model_construct())),
        )
    )


@dataclass(frozen=True, slots=True)
class PreparedInstallationAct:
    """One act ready to send: its contract, its request and how it reads the passphrase it takes, if any.

    ``passphrase`` reads the passphrase when it is called, which is the moment
    before it is sent, because reading a secret held for one use spends it.
    """

    contract: InstallationActContract
    request: RuntimeInstallationActRequest
    passphrase: Callable[[], bytearray] | None


def prepare_installation_act(
    args: dict[str, Any], secrets: SessionSecrets, surface: McpSurface
) -> PreparedInstallationAct:
    """Build the request one call asks for, refusing it where the connection's surface does not allow it.

    The surface is asked about this exact request, so an act that only
    reports until it is confirmed is served unconfirmed on a surface that
    changes no record and refused there once confirmed.
    """
    contract = INSTALLATION_ACT_CONTRACTS[InstallationAct(args["action"])]
    secrets.require(contract.act.value, *(("secret",) if contract.takes_secret else ()))
    members = {
        (INSTALLATION_CONFIRMED_MEMBER if name == INSTALLATION_CONFIRM_ARGUMENT else name): value
        for name, value in args.items()
        if name != "action"
    }
    document = {**members, "request_id": str(uuid4()), "frontend": OperationFrontendProjection.MCP.value}
    request = cast("RuntimeInstallationActRequest", parse_model(contract.request, document))
    if not _surface_allows(surface, installation_request_facts(request)):
        # The same refusal the surface gives an operation it leaves out.
        raise RuntimeFrontendRefusedError(AccessDenialCode.FRONTEND_DENIED.value)
    passphrase = (lambda: secrets.take("secret")[0]) if contract.takes_secret else None
    return PreparedInstallationAct(contract, request, passphrase)


class _SecretHandover:
    """Hold the secret an act delivers and keep only the reference it is held under."""

    def __init__(self, held_secrets: Callable[[], HeldSecretCustody], request: RuntimeInstallationActRequest) -> None:
        self._held_secrets = held_secrets
        named = request.model_dump(mode="json", exclude=set(_SERVER_SUPPLIED), exclude_none=True)
        subject = ", ".join(f"{name}={value}" for name, value in named.items())
        self._origin = f"{request.action} {subject}".strip()
        self.reference: UUID | None = None

    def __call__(self, delivered: bytearray) -> SecretBytes:
        held = self._held_secrets().hold(origin=self._origin, secret=delivered)
        self.reference = held.reference
        return held.secret


def perform_installation_act(
    client: RuntimeInstallationClient,
    prepared: PreparedInstallationAct,
    *,
    held_secrets: Callable[[], HeldSecretCustody],
) -> dict[str, Any]:
    """Send one prepared act and return how it settled, as a tool reply.

    A completed act answers with its typed reply. A refusal carries the
    runtime's code and the detail it recorded. A fault with no public facts,
    a transport that broke and a wait that ran out are reported as unresolved
    when the request could have changed records, since it may have changed
    some: the reply then names the act that reads the outcome, where the
    table declares one.

    Whenever a delivered secret was held, the reply names its reference and
    how the person reads it, whatever became of the act: the secret itself is
    in no reply.

    The passphrase is read only here, immediately before the request is sent,
    so an act refused or unreachable before this point spends none.

    Raises:
        ValueError: The passphrase's reference no longer names a held secret.
        RuntimeFrontendRefusedError: The runtime refused admission and no secret was held.
        RuntimeRefusalError: The transport refused a request that changes no record, and no secret was held.
    """
    contract, request = prepared.contract, prepared.request
    act = contract.act.value
    changing = installation_request_facts(request).changes_records
    handover = _SecretHandover(held_secrets, request) if contract.delivers_secret else None
    try:
        passphrase = None if prepared.passphrase is None else installation_passphrase_document(prepared.passphrase())
        settled = client.perform(request, contract.reply, secret=passphrase, hold_secret=handover)
    except RuntimeFrontendRefusedError as error:
        if handover is None or handover.reference is None:
            raise
        return _with_held_secret({"outcome": "refused", "code": refusal_code(error), "act": act}, handover.reference)
    except RuntimeRefusalError as error:
        held = None if handover is None else handover.reference
        if held is None and not changing:
            raise
        # A transport that broke, or a wait that ran out, says nothing about what the runtime went on to do.
        unresolved: dict[str, Any] = {"outcome": "unresolved", "code": refusal_code(error), "act": act}
        if contract.outcome_read_by is not None:
            unresolved["outcome_read_by"] = contract.outcome_read_by.value
        return unresolved if held is None else _with_held_secret(unresolved, held)
    reply: dict[str, Any]
    if isinstance(settled, RuntimeInstallationRefused):
        detail = settled.detail
        reply = {
            "outcome": "refused",
            "code": detail.error_code or detail.kind.value,
            "act": act,
            "error_detail": public_value(detail),
        }
    elif isinstance(settled, RuntimeInstallationFailed):
        reply = {"outcome": "unresolved" if changing else "refused", "code": settled.kind, "act": act}
        if changing and contract.outcome_read_by is not None:
            # The act may have changed some records before it stopped, so the reply says which act reads the outcome.
            reply["outcome_read_by"] = contract.outcome_read_by.value
    else:
        reply = {"outcome": "completed", "act": act, "reply": public_value(settled)}
    if handover is not None and handover.reference is not None:
        return _with_held_secret(reply, handover.reference)
    return reply


def _with_held_secret(reply: dict[str, Any], reference: UUID) -> dict[str, Any]:
    in_force = reply["outcome"] == "completed"
    return {
        **reply,
        "secret_reference": str(reference),
        "secret_retrieval": held_secret_retrieval(reference, in_force=in_force),
    }

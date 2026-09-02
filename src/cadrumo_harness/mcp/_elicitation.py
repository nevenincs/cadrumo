"""Elicitation-backed CONFIRM enforcement and its capability-degradation matrix.

The CONFIRM tier is real: a confirm-tier tool call pauses and asks
the HUMAN through MCP elicitation (accept / decline / cancel) before it runs.
Client support for elicitation is negotiated, not assumed, so the decision of
HOW to enforce a tier is a matrix over (policy, handoff-ness, client
capability):

- ``BLOCK`` refuses outright, always — the permanent live-write rail.
- ``CONFIRM`` with elicitation support elicits a yes/no from the user.
- ``CONFIRM`` without elicitation degrades by CONSEQUENCE: a filing-handoff
  verb (an export, a record marker — the irreversible boundary) REFUSES by
  default with an instructive message, while a non-handoff destructive verb
  proceeds under the client's own ``destructiveHint``-driven confirmation UI,
  which every surveyed client renders for annotated tools.
- ``AUTO_APPROVE`` runs without asking.

The elicitation request itself is deliberately minimal and never carries
sensitive data (a hard MCP-spec constraint): the message names the command and
its consequence; the requested schema is one boolean field.

Like the sibling ``_hitl`` module this is SDK-independent pure logic;
``_server`` owns reading the negotiated client capabilities and performing the
actual ``elicit`` round-trip.
"""

from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field

from cadrumo.core.i18n.render import tr

from ._command_policy import CommandPolicyProjection
from ._command_policy import command_policy as descriptor_command_policy
from ._hitl import ConfirmationPolicy, is_handoff_command

_STRICT_FROZEN = ConfigDict(frozen=True, strict=True, validate_assignment=True, extra="forbid")

_CONFIRM_FIELD = "confirm"


class ConfirmRoute(StrEnum):
    """How one tool call's confirmation tier is enforced for this client."""

    AUTO = "auto"
    """Auto-approved; run without asking."""
    ELICIT = "elicit"
    """Ask the user through an elicitation round-trip before running."""
    CLIENT_HINT = "client_hint"
    """Proceed; the client's ``destructiveHint`` confirmation UI carries the ask."""
    REFUSE_NO_CHANNEL = "refuse_no_channel"
    """Refuse a handoff-tier verb that has no elicitation channel to a human."""
    REFUSE_BLOCKED = "refuse_blocked"
    """Refuse the call under the permanent live-write block."""


class ConfirmDecision(StrEnum):
    """The outcome of an elicitation round-trip for a confirm-tier call."""

    PROCEED = "proceed"
    REFUSED_DECLINED = "refused_declined"
    REFUSED_CANCELLED = "refused_cancelled"
    REFUSED_NOT_CONFIRMED = "refused_not_confirmed"
    """Accepted the form but answered no — treated exactly like a decline."""


class ConfirmationRequest(BaseModel):
    """The elicitation payload for one confirm-tier call.

    ``message`` names the command and its consequence in plain language;
    ``requested_schema`` is the spec-restricted flat object with one boolean
    field. No argument values, figures, or taxpayer data ride in either — the
    MCP spec forbids eliciting sensitive information, and a confirmation needs
    none.
    """

    model_config = _STRICT_FROZEN

    message: str = Field(min_length=1)
    requested_schema: dict[str, object]


def resolve_confirm_route(
    *,
    policy: ConfirmationPolicy,
    command_key: str,
    execution_policy: CommandPolicyProjection | None = None,
    client_supports_elicitation: bool,
) -> ConfirmRoute:
    """The degradation matrix: how this call's tier is enforced for this client.

    Returns:
        A :class:`ConfirmRoute`.
    """
    if policy is ConfirmationPolicy.BLOCK:
        return ConfirmRoute.REFUSE_BLOCKED
    if policy is ConfirmationPolicy.AUTO_APPROVE:
        return ConfirmRoute.AUTO
    if client_supports_elicitation:
        return ConfirmRoute.ELICIT
    attached_policy = execution_policy or descriptor_command_policy(command_key)
    if is_handoff_command(attached_policy):
        return ConfirmRoute.REFUSE_NO_CHANNEL
    return ConfirmRoute.CLIENT_HINT


def confirmation_request(
    *, command_key: str, execution_policy: CommandPolicyProjection | None = None
) -> ConfirmationRequest:
    """Build the elicitation request for one confirm-tier command.

    The ``message`` and field ``description`` are rendered by the client TO THE
    HUMAN taxpayer, so both are localized through :func:`tr` (the configured
    output language), unlike the model-facing refusal/advisory strings in this
    layer, which the model re-narrates in the user's language itself.

    Returns:
        A :class:`ConfirmationRequest`.
    """
    attached_policy = execution_policy or descriptor_command_policy(command_key)
    if is_handoff_command(attached_policy):
        consequence = tr(
            "mcp.elicitation.confirm.consequence_handoff",
            default=(
                "This produces the filing-grade artefact the taxpayer will file "
                "with AEAT themselves. Nothing is submitted anywhere by confirming."
            ),
        )
    else:
        consequence = tr(
            "mcp.elicitation.confirm.consequence_local",
            default="This changes local data for the active taxpayer profile.",
        )
    return ConfirmationRequest(
        message=tr(
            "mcp.elicitation.confirm.message",
            command=command_key,
            consequence=consequence,
            default="Confirm running '{command}'. {consequence} Answer yes to proceed or no to stop.",
        ),
        requested_schema={
            "type": "object",
            "properties": {
                _CONFIRM_FIELD: {
                    "type": "boolean",
                    "description": tr(
                        "mcp.elicitation.confirm.field_description",
                        command=command_key,
                        default="Run '{command}' now?",
                    ),
                },
            },
            "required": [_CONFIRM_FIELD],
        },
    )


def decision_from_elicitation(*, action: str, content: dict[str, object] | None) -> ConfirmDecision:
    """Map an elicitation result onto the confirm decision.

    Fail-closed on every path that is not an explicit accepted yes: a decline,
    a cancel, a malformed accept, and an accepted ``confirm: false`` all
    refuse.

    Returns:
        A :class:`ConfirmDecision`.
    """
    if action == "accept":
        value = (content or {}).get(_CONFIRM_FIELD)
        if value is True:
            return ConfirmDecision.PROCEED
        return ConfirmDecision.REFUSED_NOT_CONFIRMED
    if action == "cancel":
        return ConfirmDecision.REFUSED_CANCELLED
    return ConfirmDecision.REFUSED_DECLINED


def refusal_message(route: ConfirmRoute, *, command_key: str) -> str:
    """The instructive refusal text for the two refusing routes (client-relayed, localized)."""
    if route is ConfirmRoute.REFUSE_BLOCKED:
        return tr(
            "mcp.elicitation.refusal.blocked",
            command=command_key,
            default=(
                "'{command}' is permanently blocked: live submission to AEAT is "
                "forbidden by design. Export locally; the taxpayer files themselves."
            ),
        )
    return tr(
        "mcp.elicitation.refusal.no_channel",
        command=command_key,
        default=(
            "'{command}' needs a human confirmation, and this client does not "
            "support elicitation. Run it from a client that can ask you questions, "
            "or run the equivalent Cadrumo CLI command directly in a terminal."
        ),
    )


__all__ = [
    "ConfirmDecision",
    "ConfirmRoute",
    "ConfirmationRequest",
    "confirmation_request",
    "decision_from_elicitation",
    "is_handoff_command",
    "refusal_message",
    "resolve_confirm_route",
]

"""Human-in-the-loop confirmation policy for MCP tool calls.

Projects each tool's mutability annotations onto a confirmation tier the server's
``PreToolUse`` gate enforces: auto-approve safe reads and non-destructive local
mutations, confirm irreversible or filing-handoff actions, and block any AEAT
live-write surface outright. This is the operator-facing gate; the CLI's own
``--yes`` / write-policy / ``LiveSubmitForbiddenError`` rails remain the
deterministic backstop beneath it.
"""

from __future__ import annotations

from enum import StrEnum

from ...application.operator_surface import command_classification


class ConfirmationPolicy(StrEnum):
    """The PreToolUse decision for a tool call.

    ``auto_approve`` runs without asking; ``confirm`` requires explicit human
    approval; ``block`` refuses the call outright (a forbidden AEAT live-write).
    """

    AUTO_APPROVE = "auto_approve"
    CONFIRM = "confirm"
    BLOCK = "block"


# Vendor-namespaced MCP ``_meta`` extension key. Recent Claude clients force a
# permission prompt on every call for a tool whose ``_meta`` carries this key true,
# regardless of the client's session-level tool-approval state. The slash-namespaced
# form is the MCP ``_meta`` prefixed-key convention (the installed SDK carries it on
# ``mcp.types.Tool._meta``, a free-form ``dict[str, Any]`` with ``extra="allow"``);
# it is not a declared ``ToolAnnotations`` hint field, so ``_meta`` is its carrier.
REQUIRES_USER_INTERACTION_META_KEY = "anthropic/requiresUserInteraction"


def requires_user_interaction(policy: ConfirmationPolicy) -> bool:
    """Whether a tool at ``policy`` must advertise ``requiresUserInteraction``.

    True exactly for the CONFIRM tier: the interaction flag is the client-facing
    projection of the server's own confirmation gate, derived from the same
    :func:`confirmation_for_tool` classification, so the client-side prompt and the
    server-side PreToolUse gate cannot drift.
    """
    return policy is ConfirmationPolicy.CONFIRM


def confirmation_for_tool(*, command_key: str) -> ConfirmationPolicy:
    """Return the confirmation tier for one tool.

    Reads the declared classification (:func:`command_classification`) - the same
    authority the annotation projection reads - so the client hint and the server
    gate cannot drift. Order matters: a forbidden live-write blocks before any
    approval; a destructive or filing-handoff verb requires confirmation;
    everything else (reads and non-destructive local mutations) auto-approves.

    Returns:
        :class:`ConfirmationPolicy` selected for the command.
    """
    classification = command_classification(command_key)
    if classification.live_write:
        return ConfirmationPolicy.BLOCK
    if classification.destructive or classification.handoff:
        return ConfirmationPolicy.CONFIRM
    return ConfirmationPolicy.AUTO_APPROVE


def is_handoff_command(command_key: str) -> bool:
    """True when the command produces the irreversible filing-handoff artefact."""
    return command_classification(command_key).handoff

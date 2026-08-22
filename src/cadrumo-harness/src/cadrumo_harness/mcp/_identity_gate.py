"""Per-session block-first-mutation identity gate.

A tax filing MUST be tied to the correct taxpayer: Erika must not file while
Erik is the active profile. This module enforces, in the pre-tool-use layer,
that an identity READ has happened before the first state-changing call of a
session - and re-arms that requirement whenever the active profile could have
changed. It cannot verify the agent CHOSE the right taxpayer (only the human
can, through the I4 elicitation echo); what it enforces is that an identity read
HAPPENED, the same fail-closed ordering discipline the project takes on
under-declaration.

Like ``_hitl`` / ``_elicitation`` this is SDK-independent pure logic: a
per-session state object plus a decision function, unit-tested directly without
the stdio transport. ``_server`` owns the per-session state instance and calls
the decision function byte-identically on the direct call path and the
``execute`` meta path so the two cannot diverge.

Mutability is read from callback-attached live command policy, never a keyed
table or leaf-name heuristic: a call is mutating when its policy is not
``read_only``.
"""

from __future__ import annotations

from typing import Protocol

from cadrumo.core.i18n import tr

from ._command_policy import command_policy
from ._harness_tools import HARNESS_LOAD_TOOL, WHOAMI_TOOL

#: Verbs that change or clear WHICH taxpayer profile is active. Executing one
#: re-arms the gate so the NEXT mutating call must re-confirm identity. This is
#: the closed set of active-identity-changing verbs (login — which also enters a
#: sandbox by its canonical ``sandbox:<name>`` label, create-and-activate, or
#: strong logout), not every ``config profile`` mutation - editing or renaming
#: the current profile does not change who is active, so it does not re-arm.
ACTIVE_IDENTITY_CHANGING_COMMANDS: frozenset[str] = frozenset(
    {
        "config.login",
        "config.profile.create",
        "config.logout",
    },
)

#: The read VERBS that constitute an identity read and clear the gate. These
#: carry registry command keys, so :func:`identity_gate_refusal` matches them on
#: both the direct and ``execute`` paths. The console identity reads (no command
#: key) are :data:`IDENTITY_READ_CONSOLE_TOOLS`.
IDENTITY_READ_COMMANDS: frozenset[str] = frozenset(
    {
        "config.profile.status",
        "overview.status",
    },
)

#: The console identity-read TOOLS (no registry command key) that clear the gate;
#: ``_server`` records the read on dispatch. ``whoami`` is the primary identity
#: assertion. ``harness.load`` counts because P02 made the harness floor carry
#: the active-identity block (:func:`~cadrumo_harness.mcp._harness_tools.build_whoami_identity`),
#: so an agent that loaded the harness has already seen who is active - exactly
#: what the gate guarantees - and it is the near-universal first call, so counting
#: it cuts friction without weakening safety: a profile SWITCH still re-arms the
#: gate, so identity is re-confirmed before any mutation after a switch.
IDENTITY_READ_CONSOLE_TOOLS: frozenset[str] = frozenset({WHOAMI_TOOL, HARNESS_LOAD_TOOL})

#: English default for the first-mutation refusal, carried verbatim so the
#: refusal survives even if the locale catalogue is unavailable. It is
#: model-facing (the agent re-narrates it), instructive, and deterministic, so
#: an agent recovers in exactly one read-only round-trip.
_FIRST_MUTATION_REFUSED_DEFAULT = (
    "Refused: confirm the active taxpayer before the first change of this session. "
    "A filing or edit must never run under the wrong identity. Call whoami (or "
    "'config profile status' / 'overview status') to see which taxpayer is active, "
    "then retry - one identity read clears this for the session until you switch "
    "profiles."
)

#: English default for the elicitation identity echo. Human-facing
#: (rendered by the client to the taxpayer), so it is localized.
_ELICITATION_ECHO_DEFAULT = "Acting as the taxpayer profile: %{label}."


class SessionIdentityState:
    """Per-session identity-read state for the block-first-mutation gate.

    ``identity_confirmed`` starts ``False`` (armed): the first mutating call is
    refused until an identity read flips it ``True``. An active-identity-changing
    verb re-arms it back to ``False`` so the next mutation re-confirms. The
    server holds exactly one instance per built session and shares it across the
    direct and ``execute`` paths.
    """

    def __init__(self) -> None:
        self._identity_confirmed = False

    @property
    def identity_confirmed(self) -> bool:
        """Whether an identity read has occurred since the last identity change."""
        return self._identity_confirmed

    def record_identity_read(self) -> None:
        """Mark that an identity read (whoami / status) has occurred this session."""
        self._identity_confirmed = True

    def rearm(self) -> None:
        """Re-arm the gate after a profile change; the next mutation must re-confirm."""
        self._identity_confirmed = False


class _IdentityGateState(Protocol):
    @property
    def identity_confirmed(self) -> bool: ...

    def record_identity_read(self) -> None: ...

    def rearm(self) -> None: ...


def identity_gate_refusal(command_key: str, *, state: _IdentityGateState) -> str | None:
    """Return a localized refusal for an unconfirmed first mutating call, else ``None``.

    Evaluated for every verb call on both the direct and ``execute`` paths, in
    order:

    * An active-identity-changing verb re-arms ``state`` and is allowed. This
      includes strong logout, which clears the active identity.
    * An identity-read verb records the read on ``state`` and is allowed,
      whatever its declared mutability.
    * Any other LOCAL read-only call is allowed and leaves the state untouched.
    * Any other call - mutating, or a read that reaches AEAT - is refused
      (returns the localized refusal text) unless an identity read has occurred
      since session start or the last active-identity change.

    The open-world exclusion is why the predicate is not simply ``read_only``. A
    live ``pull`` changes nothing locally and is still not safe to run
    unidentified: it fetches taxpayer data from AEAT under a certificate, so
    reading the WRONG taxpayer is a confidentiality breach that then feeds every
    downstream calculation. "Changes nothing" and "may proceed unidentified" are
    different questions, and this gate asks the second.

    Today the exclusion is a no-op - no exposed command is both ``read_only``
    and ``open_world``, pinned by
    ``test_identity_gate_open_world_invariant.py``. It is here so that the
    invariant holds by CONSTRUCTION rather than by accident of ``read_only``
    deriving from family mutability: were reads ever declared per command, all
    32 AEAT-reaching verbs would otherwise drop out of this gate silently.

    The refusal text carries no interpolation, so it is byte-identical on both
    call paths.
    """
    if command_key in ACTIVE_IDENTITY_CHANGING_COMMANDS:
        state.rearm()
        return None
    if command_key in IDENTITY_READ_COMMANDS:
        state.record_identity_read()
        return None
    try:
        classification = command_policy(command_key)
    except (LookupError, ValueError):
        if state.identity_confirmed:
            return None
        return tr("mcp.identity_gate.first_mutation_refused", default=_FIRST_MUTATION_REFUSED_DEFAULT)
    if classification.read_only and not classification.open_world:
        return None
    if state.identity_confirmed:
        return None
    return tr("mcp.identity_gate.first_mutation_refused", default=_FIRST_MUTATION_REFUSED_DEFAULT)


def identity_elicitation_echo(*, active_profile_label: str | None) -> str:
    """Return the localized identity echo prefixed to a CONFIRM elicitation.

    Names the active-profile LABEL (never the redacted UUID) so the human
    approving a destructive or handoff verb sees whose data it touches and can
    catch an Erik/Erika mismatch at the gate. ``None`` (no active profile)
    renders a neutral placeholder rather than an empty name.
    """
    label = active_profile_label if active_profile_label else "(no active profile)"
    return tr("mcp.identity_gate.elicitation_echo", label=label, default=_ELICITATION_ECHO_DEFAULT)


__all__ = [
    "ACTIVE_IDENTITY_CHANGING_COMMANDS",
    "IDENTITY_READ_COMMANDS",
    "IDENTITY_READ_CONSOLE_TOOLS",
    "SessionIdentityState",
    "identity_elicitation_echo",
    "identity_gate_refusal",
]

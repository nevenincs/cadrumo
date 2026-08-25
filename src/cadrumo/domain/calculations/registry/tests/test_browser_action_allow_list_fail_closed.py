"""An empty browser-action allow-list refuses, it does not permit.

`_evaluate_browser_action` used to gate on
``if policy.allowed_browser_action_patterns and not _matches(...)``, so a
policy declaring NO actions imposed no action restriction at all. Dropping a
pattern set did not narrow the allow-list, it removed the gate.

That is fail-open in the configuration most likely to arise by accident: the
field defaults to an empty tuple, and a shipped registry key that is simply
absent lands there silently -- no error, no warning, and every browser action
permitted on an authenticated AEAT surface.

The surrounding code already assumed the opposite. The expedientes walker
documents its deliberately-empty tuple as meaning "any future browser action
added here fails the guard until it is declared, which is the refusal we want
rather than a gap" -- a guarantee the old branch did not provide. This module
pins the guarantee that comment describes.
"""

from __future__ import annotations

import pytest

from .....tests.aeat_literal_fixtures import aeat_host
from ..remote_state_guard import (
    AEAT_WRITE_FORBIDDEN_VERB_TOKENS,
    RemoteOperation,
    RemoteStateGuardPolicy,
    RemoteStateGuardResult,
    evaluate_remote_operation,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]

_HOST = aeat_host("www6")

#: An action carrying NO forbidden verb token and NO write-shaped word, so a
#: refusal can only come from the allow-list gate. A hostile-sounding action
#: would be refused by the token denylist first and would prove nothing about
#: the defect under test -- the same trap as asserting on an outcome that a
#: neighbouring check already produces.
_INNOCUOUS_ACTION = "open-dialog"

#: Distinct refusal grounds, so a test can name WHICH check fired.
_EMPTY_DECLARATION_GROUND = "declares no allowed browser actions"
_UNLISTED_ACTION_GROUND = "not in the explicit read-only allow-list"
_WRITE_VERB_GROUND = "is forbidden"


def _policy(*, patterns: tuple[str, ...]) -> RemoteStateGuardPolicy:
    """Return an authenticated-read policy carrying ``patterns`` as its action gate."""
    return RemoteStateGuardPolicy(
        id="fail-closed-probe",
        evidence_tier="official_source_guidance",
        classification="authenticated_read_surface",
        allowed_hosts=(_HOST,),
        allowed_browser_action_patterns=patterns,
        synthetic_data_allowed=False,
        requires_authentication=True,
        requires_aeat_authorization=False,
    )


def _evaluate(patterns: tuple[str, ...], action: str) -> RemoteStateGuardResult:
    """Evaluate ``action`` against a policy declaring ``patterns``."""
    return evaluate_remote_operation(
        _policy(patterns=patterns),
        RemoteOperation(kind="browser_action", action=action),
    )


# --------------------------------------------------------------------------
# DISCRIMINATING -- these fail if the empty allow-list stops refusing
# --------------------------------------------------------------------------


def test_an_empty_allow_list_refuses_an_otherwise_innocuous_action() -> None:
    """DISCRIMINATING. Restoring the old branch makes this observably ALLOWED.

    This is the whole defect: no declared actions must mean no permitted
    actions, not unrestricted actions.
    """
    result = _evaluate((), _INNOCUOUS_ACTION)

    assert result.decision == "blocked"


def test_the_empty_allow_list_refusal_names_the_empty_declaration() -> None:
    """DISCRIMINATING. The refusal ground must be the empty declaration.

    A blocked decision alone would not distinguish this gate from the token
    denylist or the unlisted-action branch, so the ground is asserted.
    """
    result = _evaluate((), _INNOCUOUS_ACTION)

    assert result.decision == "blocked"
    assert _EMPTY_DECLARATION_GROUND in result.reason
    assert _UNLISTED_ACTION_GROUND not in result.reason
    assert result.policy_id == "fail-closed-probe"


@pytest.mark.parametrize(
    "action",
    [
        pytest.param("open-dialog", id="innocuous"),
        pytest.param("read-summary", id="read-shaped"),
        pytest.param("continue", id="navigation-shaped"),
    ],
)
def test_an_empty_allow_list_refuses_every_action_shape(action: str) -> None:
    """DISCRIMINATING. The refusal is total, not limited to suspicious labels."""
    assert _evaluate((), action).decision == "blocked"


# --------------------------------------------------------------------------
# SUPPORTING -- anti-tautology, and the neighbouring gates that must not move
# --------------------------------------------------------------------------


def test_a_declared_action_is_still_allowed() -> None:
    """SUPPORTING (anti-tautology). Passes under mutation.

    Without this, a guard hard-wired to refuse every browser action would
    satisfy every discriminating case above.
    """
    result = _evaluate((_INNOCUOUS_ACTION,), _INNOCUOUS_ACTION)

    assert result.decision == "allowed"


def test_an_undeclared_action_is_refused_on_the_unlisted_ground() -> None:
    """SUPPORTING. Passes under mutation; the non-empty branch is unchanged."""
    result = _evaluate(("some-other-action",), _INNOCUOUS_ACTION)

    assert result.decision == "blocked"
    assert _UNLISTED_ACTION_GROUND in result.reason
    assert _EMPTY_DECLARATION_GROUND not in result.reason


def test_a_write_token_is_still_refused_on_the_token_ground() -> None:
    """SUPPORTING. Passes under mutation.

    The write-token denylist runs BEFORE the allow-list gate and must keep
    firing first, so a write action is refused for being a write rather than
    for being undeclared.
    """
    result = _evaluate(("presentar-declaracion",), "presentar-declaracion")

    assert result.decision == "blocked"
    assert _WRITE_VERB_GROUND in result.reason
    assert _EMPTY_DECLARATION_GROUND not in result.reason


def test_the_probe_action_carries_no_forbidden_token() -> None:
    """SUPPORTING (layer control). Passes under mutation.

    Pins the precondition that makes the discriminating cases meaningful: the
    probe action must survive the token denylist, or its refusal would come
    from that denylist and say nothing about the allow-list gate.
    """
    normalized = _INNOCUOUS_ACTION.lower()

    for token in AEAT_WRITE_FORBIDDEN_VERB_TOKENS:
        assert token not in normalized, f"probe action contains write token {token!r}; it would be refused anyway"


def test_the_probe_action_is_permitted_once_declared() -> None:
    """SUPPORTING (layer control). Passes under mutation.

    The complement of the control above: proves the probe action is capable of
    reaching an "allowed" outcome at all, so its refusal on an empty policy is
    attributable to the empty declaration and nothing else.
    """
    assert _evaluate((_INNOCUOUS_ACTION,), _INNOCUOUS_ACTION).decision == "allowed"

"""A registration that lost a race is not reported as a name already taken.

``retryable`` is the instruction this CLI's operator acts on, and that operator
is an autonomous agent. Two custody refusals reach the registration boundary as
one exception family, because the permanent case is a SUBCLASS of the transient
one:

- the stale-witness transaction conflict, which a repeat of the identical call
  can win, published as retryable;
- the duplicate label, which no retry can change, published as permanent.

The boundary caught only the parent and translated both into one non-retryable
"profile already exists". A transient loss therefore told the agent that the
name it had just chosen was taken -- so it would not retry, and would instead
pick a different name for a profile that does not exist.

Split as a subclass for the same reason the custody pair was, so every existing
``except ProfileRegistrationError`` handler keeps catching both; only the
published code and its retryability differ. Both halves are asserted here,
because moving one without pinning the other is how the distinction collapses
back.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from ....core.errors import get_registered_error_code
from .. import ProfileRegistrationConflictError, ProfileRegistrationError

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]


def test_a_lost_race_is_published_as_retryable() -> None:
    """DISCRIMINATING: the answer an agent operator acts on.

    The identical registration can succeed once the witness is re-read, so
    reporting it as permanent strands a caller that only needed to try again.
    """
    code = get_registered_error_code(ProfileRegistrationConflictError)

    assert code is not None
    assert code.retryable is True
    assert code.code == "REFUSED_PROFILE_REGISTRATION_CONFLICT"


def test_an_ordinary_registration_refusal_stays_permanent() -> None:
    """ANTI-TAUTOLOGY: the parent's answer must survive the split.

    Without this, marking the whole family retryable would satisfy the
    assertion above while telling an agent to loop on a label that is
    genuinely taken.
    """
    code = get_registered_error_code(ProfileRegistrationError)

    assert code is not None
    assert code.retryable is False


def test_the_conflict_is_still_caught_as_a_registration_refusal() -> None:
    """The subclassing is load-bearing, not cosmetic.

    The TUI front end catches ``ProfileRegistrationError`` by name. A sibling
    class instead of a subclass would escape that handler and surface as an
    unhandled error rather than a refusal the screen can render.
    """
    assert issubclass(ProfileRegistrationConflictError, ProfileRegistrationError)

    with pytest.raises(ProfileRegistrationError):
        raise ProfileRegistrationConflictError(
            translated_message="errors.refused.refused_storage_profile_custody",
        )


def test_the_two_registration_answers_are_distinguishable() -> None:
    """The distinction the flattening destroyed, stated as one assertion.

    If these ever publish the same code again, the boundary has collapsed back
    to one answer for two different operator situations.
    """
    conflict = get_registered_error_code(ProfileRegistrationConflictError)
    refusal = get_registered_error_code(ProfileRegistrationError)

    assert conflict is not None
    assert refusal is not None
    assert conflict.code != refusal.code
    assert conflict.retryable != refusal.retryable


def test_the_permanent_case_is_caught_ahead_of_the_transient_one() -> None:
    """DISCRIMINATING: subclass-before-parent is what routes the two answers.

    ``ProfileCustodyDuplicateLabelError`` is a subclass of the conflict it
    shares a handler chain with, so Python matches whichever ``except`` comes
    first. Ordering the parent ahead of it silently restores the flattening
    this split exists to undo -- and no retryability assertion above would
    notice, because both codes would still be registered correctly while only
    one of them could ever be raised.
    """
    import ast

    source = (Path(__file__).resolve().parents[1] / "_registration.py").read_text(encoding="utf-8")
    orders: list[tuple[int, int]] = []
    for node in ast.walk(ast.parse(source)):
        if not isinstance(node, ast.Try):
            continue
        names = [handler.type.id if isinstance(handler.type, ast.Name) else None for handler in node.handlers]
        if "ProfileCustodyDuplicateLabelError" in names and "ProfileCustodyTransactionConflictError" in names:
            orders.append(
                (
                    names.index("ProfileCustodyDuplicateLabelError"),
                    names.index("ProfileCustodyTransactionConflictError"),
                )
            )

    assert orders, "the registration boundary no longer handles both custody answers"
    for duplicate_at, conflict_at in orders:
        assert duplicate_at < conflict_at, (
            "the duplicate-label handler must precede the conflict handler it subclasses, "
            "or every duplicate is reported as a retryable race"
        )

"""Every retryable storage/custody error says why repeating the call could work.

``retryable`` is the instruction an autonomous operator acts on, and its
meaning is now stated on the field itself: repeating the IDENTICAL call, with
nothing else changed, may succeed. Time passing or another party finishing is
enough; needing an operator to fix something first is NOT.

The field carried no stated meaning for a long time, and that is how a refusal
for a profile label already bound to a committed capsule came to be published
as retryable -- it inherited the answer from a sibling condition that genuinely
was a stale-witness conflict, and the identical restore could never have
succeeded. An agent told to retry that loops until something else stops it.

This gate covers the storage and custody codes this work owns. Each retryable
one names what changes on its own to make a repeat succeed, so a future code
cannot join them by inheriting a neighbour's answer unexamined. It is scoped
rather than tree-wide on purpose: the same question is open for two Google ADC
codes, where a retry cannot succeed until the operator re-runs a gcloud
command, and those belong to whoever owns that surface to answer.
"""

from __future__ import annotations

import pytest

from ....core.errors import declared_error_codes

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

#: Path fragments identifying the codes this campaign is answerable for.
_OWNED_QUALNAME_FRAGMENTS = (
    "adapters.persistence.storage",
    "application.user_profile",
    "core.locks_errors",
)

#: Every owned code published as retryable, mapped to what resolves ON ITS OWN.
#: An entry is a claim that no operator action is required -- only time, or
#: another holder finishing.
_RETRYABLE_BECAUSE: dict[str, str] = {
    "LOCKED_STORAGE_BUCKET_BUSY": "another process holds the bucket lock and releases it when it finishes",
    "LOCKED_STORAGE_LOCK_ACQUISITION": "the lock is held elsewhere and is released without operator action",
    "FAIL_PROFILE_RECORD_CONFLICT": "a compare-and-swap witness went stale; re-reading and re-applying succeeds",
    "REFUSED_PROFILE_CUSTODY_TRANSACTION_CONFLICT": (
        "the captured local witness no longer matches live state, which a re-read resolves"
    ),
    "REFUSED_PROFILE_CUSTODY_DISPLACED_SESSION_RETIREMENT": (
        "a displaced session is still retiring; it completes on its own"
    ),
    "REFUSED_PROFILE_REGISTRATION_CONFLICT": (
        "registration lost a custody witness race; re-reading and repeating the identical call succeeds"
    ),
    "REFUSED_PROFILE_LOGIN_THROTTLED": "the backoff window expires by the clock, with nothing for the operator to do",
}


def _owned_retryable_codes() -> set[str]:
    """Return the retryable codes declared by storage/custody-owned classes."""
    return {
        code.code
        for qualname, code in declared_error_codes()
        if code.retryable and any(fragment in qualname for fragment in _OWNED_QUALNAME_FRAGMENTS)
    }


def test_every_owned_retryable_code_states_what_resolves_itself() -> None:
    """A new retryable code cannot join by inheriting a neighbour's answer."""
    undeclared = sorted(_owned_retryable_codes() - set(_RETRYABLE_BECAUSE))

    assert not undeclared, (
        f"these storage/custody codes are published as retryable and say nothing about why: "
        f"{undeclared}. Name what resolves on its own -- a lock released, a window expiring, a "
        "witness re-read. If the call cannot succeed until the operator changes something, it is "
        "not retryable: an agent cannot tell that case from a transient one and will loop."
    )


def test_no_declaration_outlives_its_code() -> None:
    """The half that rots: an entry for a code that is no longer retryable.

    A stale entry asserts a retry contract nothing publishes any more, which is
    how this list would drift into describing a tree it no longer matches.
    """
    stale = sorted(set(_RETRYABLE_BECAUSE) - _owned_retryable_codes())

    assert not stale, f"these declarations no longer match a retryable owned code: {stale}"


def test_the_duplicate_label_refusal_is_absent_from_the_retryable_set() -> None:
    """DISCRIMINATING: the case that motivated the contract.

    A label bound to a committed capsule is permanent. If it ever reappears
    among the retryable codes, the distinction this gate exists to hold has
    collapsed back, and it must fail rather than acquire an entry.
    """
    assert "REFUSED_PROFILE_CUSTODY_DUPLICATE_LABEL" not in _owned_retryable_codes()

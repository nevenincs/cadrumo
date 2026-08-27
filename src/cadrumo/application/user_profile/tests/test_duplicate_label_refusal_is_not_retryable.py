"""A label already bound to a capsule refuses permanently, not retryably.

``retryable`` is not decoration on this CLI. Its stated operator is an
autonomous agent, and the field is the instruction it acts on: a refusal marked
retryable invites the identical command again.

Two conditions in the same custody function shared one error class and
therefore one answer. "The captured witness no longer matches live state" is a
compare-and-swap conflict that a re-read genuinely fixes, so its code is
published retryable and should stay that way. "This label already names a
committed capsule" is permanent -- the name is taken, and the identical restore
can never succeed -- yet it inherited the retryable answer and told the agent
to loop.

The split is a SUBCLASS, so every existing handler that catches a custody
conflict keeps catching this one; only the published code and its retryability
differ. Both halves are asserted here, because moving one without pinning the
other is how the distinction quietly collapses back.
"""

from __future__ import annotations

import pytest

from ....core.errors import get_registered_error_code
from ..custody_transactions import ProfileCustodyDuplicateLabelError, ProfileCustodyTransactionConflictError

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]


def test_a_taken_label_is_published_as_not_retryable() -> None:
    """DISCRIMINATING: the answer an agent operator acts on.

    Retrying a restore under a label bound to a committed capsule cannot
    succeed at any point in the future, so advertising it as retryable is an
    instruction to loop.
    """
    code = get_registered_error_code(ProfileCustodyDuplicateLabelError)

    assert code is not None
    assert code.retryable is False
    assert code.code == "REFUSED_PROFILE_CUSTODY_DUPLICATE_LABEL"


def test_the_stale_witness_conflict_stays_retryable() -> None:
    """ANTI-TAUTOLOGY: the parent's retryability must survive the split.

    Without this, marking the whole family not-retryable would satisfy the
    assertion above while breaking the case that genuinely resolves on a
    re-read -- and a real conflict reported as permanent strands a caller that
    only needed to try again.
    """
    code = get_registered_error_code(ProfileCustodyTransactionConflictError)

    assert code is not None
    assert code.retryable is True


def test_the_duplicate_label_error_is_still_caught_as_a_conflict() -> None:
    """The subclassing is load-bearing, not cosmetic.

    Existing handlers catch the conflict type. If the split had introduced a
    sibling instead of a subclass, those handlers would stop seeing this case
    and a refusal would escape as an unexpected error.
    """
    assert issubclass(ProfileCustodyDuplicateLabelError, ProfileCustodyTransactionConflictError)

    with pytest.raises(ProfileCustodyTransactionConflictError):
        raise ProfileCustodyDuplicateLabelError("profile label is already bound to a committed capsule")

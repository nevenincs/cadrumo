"""Which classifications carry a business share is decided once.

A ``business_pct`` answers "how much of this is business", which is only a
question for a row that is partly both. The write-path coupling check enforced
that, and the command offering ``--business-pct`` enforced it again by spelling
``is MIXED`` inline -- the same rule declared twice, with nothing joining them.

The duplication was not yet a defect: both said MIXED. It was a defect waiting
for a third share-bearing classification, at which point the write path would
accept a share the command still refused to let anyone supply, and the operator
would meet a refusal the domain does not make.

These hold the rule and its two consequences together: a share is required for
exactly the share-bearing states and refused for exactly the rest, driven over
EVERY member of the enum rather than the three anyone would think to try.
"""

from __future__ import annotations

from decimal import Decimal

import pytest

from ..enums import (
    BUSINESS_BEARING_STATES,
    CLASSIFIED_STATES,
    SHARE_BEARING_STATES,
    BusinessClassification,
    takes_business_share,
)
from ..errors import TransactionValidationError
from ..model_validation import validate_business_pct_coupling

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]

_A_VALID_SHARE = Decimal("0.4")


def test_a_share_bearing_state_is_one_that_is_partly_both() -> None:
    """The rule itself, stated once so the sets below can be checked against it."""
    assert frozenset({BusinessClassification.MIXED}) == SHARE_BEARING_STATES


def test_the_share_bearing_states_are_a_subset_of_the_classified_ones() -> None:
    """A share on an unclassified row would apportion an economic role nobody assigned.

    Stated as containment rather than equality: the interesting property is
    that no pipeline disposition can acquire one, not that these particular
    members are the answer today.
    """
    assert SHARE_BEARING_STATES <= CLASSIFIED_STATES


def test_a_share_bearing_state_carries_a_business_role_to_apportion() -> None:
    """Apportioning something with no business component is apportioning nothing.

    ``PERSONAL`` is classified but bears no business role, so it could never
    take a share; this says the two sets agree on that rather than leaving it
    to coincidence.
    """
    assert SHARE_BEARING_STATES <= BUSINESS_BEARING_STATES


@pytest.mark.parametrize("state", tuple(BusinessClassification), ids=lambda state: state.value)
def test_the_predicate_answers_for_every_member(state: BusinessClassification) -> None:
    """No member is left to a caller's judgement.

    Driven over the whole enum because a member added without a decision here
    would silently answer ``False`` -- a share refused, which is the safe
    direction but still an answer nobody made.
    """
    assert takes_business_share(state) is (state in SHARE_BEARING_STATES)


@pytest.mark.parametrize("state", tuple(BusinessClassification), ids=lambda state: state.value)
def test_the_write_path_requires_a_share_for_exactly_the_bearing_states(
    state: BusinessClassification,
) -> None:
    """The coupling check and the predicate must agree, member by member.

    This is the join the two declarations lacked. A state the predicate calls
    share-bearing must be one the write path refuses to accept without a
    share, and the reverse -- otherwise a command reading the predicate would
    offer a flag the write path rejects, or withhold one it demands.
    """
    if takes_business_share(state):
        with pytest.raises(TransactionValidationError, match="required"):
            validate_business_pct_coupling(state, None)
    else:
        validate_business_pct_coupling(state, None)


@pytest.mark.parametrize("state", tuple(BusinessClassification), ids=lambda state: state.value)
def test_the_write_path_refuses_a_share_on_every_non_bearing_state(
    state: BusinessClassification,
) -> None:
    """The positive control's other half: a share is not merely optional elsewhere.

    Separating this from the test above is what stops the pair being read as
    "MIXED needs one, everyone else may have one": on a wholly-business or
    wholly-personal row a share is a contradiction, and silently dropping it
    would file a proportion the operator believed they had set.
    """
    if takes_business_share(state):
        validate_business_pct_coupling(state, _A_VALID_SHARE)
    else:
        with pytest.raises(TransactionValidationError, match="must be None"):
            validate_business_pct_coupling(state, _A_VALID_SHARE)


def test_a_share_outside_a_unit_proportion_is_refused_where_one_belongs() -> None:
    """The third refusal, which only a share-bearing state can reach.

    Kept beside the other two so the coupling reads as three outcomes rather
    than two, and so a range check moving elsewhere shows up here.
    """
    with pytest.raises(TransactionValidationError, match=r"within 0\.\.1"):
        validate_business_pct_coupling(BusinessClassification.MIXED, Decimal("1.5"))

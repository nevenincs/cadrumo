"""Which classification a business share implies is decided once, in the domain.

This is the inverse of ``validate_business_pct_coupling`` and its other half.
That one answers "may this classification carry a share"; this one answers
"which classification does this share mean". Together they describe one
relationship between a proportion and a classification.

Only one half was ever named. The other lived inline in ``ledger allocate`` as
a three-branch ``if`` on ``Decimal(1)`` and ``Decimal(0)``, so a second
frontend offering the same verb had to invent it — and the CLI's own comment
recorded what inventing it badly costs: an earlier version hard-coded MIXED and
labelled a fully-business expense as mixed-use.

The rule is not a convenience. A whole share is wholly business and a zero
share wholly personal; neither is a mixture, and calling either MIXED is a
false statement about the row rather than a cautious one. It also feeds the
coupling check directly — a share of 1 classified MIXED would be accepted by a
validator that only asks whether MIXED may carry a share.
"""

from __future__ import annotations

from decimal import Decimal

import pytest

from ..enums import BusinessClassification, takes_business_share
from ..errors import TransactionValidationError
from ..model_validation import classification_for_business_share, validate_business_pct_coupling

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]


@pytest.mark.parametrize(
    ("share", "expected"),
    [
        ("1", BusinessClassification.BUSINESS),
        ("1.00", BusinessClassification.BUSINESS),
        ("0", BusinessClassification.PERSONAL),
        ("0.0", BusinessClassification.PERSONAL),
        ("0.5", BusinessClassification.MIXED),
        ("0.0001", BusinessClassification.MIXED),
        ("0.9999", BusinessClassification.MIXED),
    ],
    ids=["whole", "whole_scaled", "none", "none_scaled", "half", "almost_none", "almost_whole"],
)
def test_a_share_implies_exactly_one_classification(share: str, expected: BusinessClassification) -> None:
    """The boundaries are the rule, so both are named at two scales.

    ``Decimal("1.00")`` and ``Decimal("1")`` are equal but not identical in
    text, and a comparison written against the spelling rather than the value
    would send a scaled whole share to MIXED — which is exactly the mislabel
    this rule exists to prevent.
    """
    assert classification_for_business_share(Decimal(share)) is expected


@pytest.mark.parametrize("share", ["-0.01", "1.01", "2", "-1"], ids=lambda share: share)
def test_a_share_outside_a_unit_proportion_names_no_classification(share: str) -> None:
    """Refusing beats answering MIXED, which would carry the bad value onward.

    MIXED is the tempting default here because it is the "in between" answer,
    and it is the wrong one: a proportion outside 0..1 is not between anything,
    and stamping it would put an impossible share on the row.
    """
    with pytest.raises(TransactionValidationError, match=r"0\.\.1"):
        classification_for_business_share(Decimal(share))


@pytest.mark.parametrize(
    "share",
    ["0", "0.25", "0.5", "0.75", "1"],
    ids=lambda share: share,
)
def test_the_implied_classification_satisfies_the_coupling(share: str) -> None:
    """The two halves must agree, and only this test can say that they do.

    The coupling requires a share exactly where the classification bears one.
    If this rule returned MIXED for a whole share, or BUSINESS for a partial
    one, the pair it produced would be refused by the very validator the same
    module owns — so the round trip is the real invariant, not either half.
    """
    value = Decimal(share)
    classification = classification_for_business_share(value)

    validate_business_pct_coupling(classification, value if takes_business_share(classification) else None)


def test_only_a_strictly_partial_share_bears_one() -> None:
    """The join to the other half, stated over the boundaries it turns on.

    A whole or zero share must NOT come back as a share-bearing state,
    because the coupling would then demand a proportion for a row that is
    wholly one thing.
    """
    assert takes_business_share(classification_for_business_share(Decimal("0.5"))) is True
    assert takes_business_share(classification_for_business_share(Decimal(1))) is False
    assert takes_business_share(classification_for_business_share(Decimal(0))) is False


def test_every_classification_it_returns_is_a_classified_outcome() -> None:
    """It never returns a pipeline disposition.

    ``BusinessClassification`` also holds states the pipeline assigns —
    NOT_YET_PROCESSED, SKIPPED_BY_RULE and the rest. A share is an operator's
    statement about a row, so it can only imply one of the three outcomes an
    operator may assign.
    """
    produced = {classification_for_business_share(Decimal(share)) for share in ("0", "0.5", "1")}

    assert produced == {
        BusinessClassification.BUSINESS,
        BusinessClassification.PERSONAL,
        BusinessClassification.MIXED,
    }

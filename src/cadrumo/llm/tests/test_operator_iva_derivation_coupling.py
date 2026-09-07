"""A derivation's flag and its substrate are one answer, not five fields.

``OperatorIvaDerivationResult`` says whether the registry could rate an
operator-chosen IVA category and, when it could, carries the rate, the taxable
base, the IVA amount and the persisted write. Those four are optional because
the non-derivable case exists -- not because either case is partial.

Nothing said so. ``derivable`` was a free bool beside four independently
optional fields, and only ONE direction was checked anywhere: the command that
reads this hand-checked for a derivable result missing its substrate. The other
direction was checked nowhere, and it is the dangerous one -- a result marked
NOT derivable while carrying numbers invites a consumer to trust the numbers
over the flag and persist a rate the derivation explicitly declined to make.

Both directions are refused on the model now, so every reader gets the
guarantee rather than the surface that remembers to ask. The two real
construction sites already satisfied it; that they still do is the control.
"""

from __future__ import annotations

from decimal import Decimal

import pytest
from pydantic import ValidationError

from ...core.identity import TransactionId
from ...domain.iva.schema import IvaCategory
from ..suggestions import OperatorIvaDerivationResult

pytestmark = [pytest.mark.unit, pytest.mark.hex_outbound_adapter]

_TRANSACTION_ID = TransactionId("a" * 64)
_A_CATEGORY = next(iter(IvaCategory))


def _non_derivable() -> OperatorIvaDerivationResult:
    """The shape the application returns when the registry cannot rate a category."""
    return OperatorIvaDerivationResult(
        transaction_id=_TRANSACTION_ID,
        iva_category=_A_CATEGORY,
        derivable=False,
        note="no simple Spanish rate for this category",
    )


def test_a_non_derivable_result_carrying_no_substrate_is_accepted() -> None:
    """The first real construction site, unchanged.

    Without this the refusals below could be satisfied by a model that rejects
    every non-derivable result, which would break the path the operator most
    often reaches.
    """
    derivation = _non_derivable()

    assert derivation.derivable is False
    assert derivation.iva_rate is None
    assert derivation.note


@pytest.mark.parametrize(
    "field",
    ["iva_rate", "taxable_base", "iva_amount"],
)
def test_a_non_derivable_result_may_not_carry_a_substrate_value(field: str) -> None:
    """The direction nothing checked before.

    Any one of these alone is enough: a consumer reading the numbers and
    ignoring the flag would persist a rate the derivation declined to make.
    Parametrised per field so a single field slipping through is visible
    rather than masked by the others being absent.
    """
    payload = {**_non_derivable().model_dump(), field: Decimal("0.21")}

    with pytest.raises(ValidationError, match="must carry no substrate"):
        OperatorIvaDerivationResult.model_validate(payload)


def test_a_derivable_result_missing_its_substrate_is_refused() -> None:
    """The direction the command hand-checked, now guaranteed upstream.

    Built by moving one field of an otherwise sound answer rather than by
    writing a bare ``derivable=True``, so the refusal is about the
    disagreement and not about the other fields being unset.
    """
    payload = {
        **_non_derivable().model_dump(),
        "derivable": True,
        "iva_rate": Decimal("0.21"),
        "taxable_base": Decimal("100.00"),
        "iva_amount": Decimal("21.00"),
    }

    with pytest.raises(ValidationError, match="must carry its whole substrate"):
        OperatorIvaDerivationResult.model_validate(payload)


def test_the_persisted_write_counts_as_part_of_the_substrate() -> None:
    """``result`` is not a bonus field: without it nothing was written.

    Stated separately because it is the one substrate member that is not a
    number, and a coupling that checked only the three decimals would accept a
    derivable result that persisted nothing while reporting success.
    """
    payload = {
        **_non_derivable().model_dump(),
        "derivable": True,
        "iva_rate": Decimal("0.21"),
        "taxable_base": Decimal("100.00"),
        "iva_amount": Decimal("21.00"),
        "result": None,
    }

    with pytest.raises(ValidationError, match="must carry its whole substrate"):
        OperatorIvaDerivationResult.model_validate(payload)

"""A purchase bearing recargo de equivalencia is classified only for a retailer the profile places in that regime.

The supplier repercutes the recargo only on an entrega to a comerciante minorista in the special
regime (LIVA arts. 154 and 156), so the profile's own IVA regime decides whether a purchase may
carry it. Real behaviour throughout: a catalogue persona replayed through production operations,
then classified through the registered classify operation.
"""

from __future__ import annotations

from decimal import Decimal
from pathlib import Path

import pytest

from ...application.ledger.classify_requests import (
    LEDGER_CLASSIFY_OPERATION_DEFINITION_ID,
    LedgerClassifyPatch,
    LedgerClassifyRequest,
)
from ..ledger_action_composition import compose_ledger_action_ports
from .persona_materialisation import (
    PERSONA_ACTOR,
    PersonaMaterialisationError,
    materialised_persona,
    settle_operation,
)

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint]

#: A plumber in the general IVA regime, and a materials purchase it already classified at 21 %.
_GENERAL_REGIME_PERSONA = "autonomo-fontanero"
_PURCHASE = "FON-MAT-1"


def test_a_general_regime_profile_cannot_classify_a_purchase_with_recargo(tmp_path: Path) -> None:
    """The figures reconstitute the cash exactly, so only the profile's regime refuses them."""
    with materialised_persona(_GENERAL_REGIME_PERSONA, tmp_path, reuse=True) as materialised:
        world = materialised.world
        transaction_id = materialised.transactions[_PURCHASE]

        def stored() -> tuple[Decimal | None, Decimal | None, Decimal | None]:
            row = (
                compose_ledger_action_ports(bucket_id=str(world.profile_id), operation=world.operation)
                .transaction_repository.load()
                .transactions[transaction_id]
            )
            return row.taxable_base, row.iva_amount, row.recargo_amount

        before = stored()
        # 2061.41 + 21 % (432.9) + 5.2 % (107.19) = 2601.50, the movement's cash.
        patch = LedgerClassifyPatch(
            business_classification="BUSINESS",
            taxable_base="2061.41",
            iva_amount="432.9",
            recargo_amount="107.19",
        )
        with pytest.raises(PersonaMaterialisationError, match="recargo de equivalencia"):
            settle_operation(
                world,
                LEDGER_CLASSIFY_OPERATION_DEFINITION_ID,
                LedgerClassifyRequest(
                    profile_id=world.profile_id,
                    transaction_id=transaction_id,
                    patch=patch,
                    patch_fields=("business_classification", "iva_amount", "recargo_amount", "taxable_base"),
                    actor=PERSONA_ACTOR,
                ),
            )

        assert stored() == before
        assert before[2] is None

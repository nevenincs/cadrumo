"""The cash-accounting axis keeps all three statutory states, in code and in the registry.

Ley 37/1992 names two different subjects around the régimen especial del
criterio de caja, and they are not the same taxpayer. Art. 163 terdecies
governs the sujeto pasivo ACOGIDO: the devengo of his own supplies moves to the
cobro. Art. 163 quinquiesdecies governs a taxpayer NOT acogido who is merely
the destinatario of an affected operation: nothing moves on his own supplies,
only his deduction waits for the pago. Plus the ordinary state, outside the
regime entirely.

Three legal states, so three members. Deleting the acogido member once looked
harmless because ``supplier_regime`` was still there, but the two are different
subjects: a received-operation state cannot carry an issued supply, and
``_require_supplier_regime_direction`` refuses ``supplier_regime`` on an issued
row for exactly that reason -- so with the acogido state gone, a criterio-de-caja
SALE becomes unrepresentable and Modelo 303 boxes 62 and 63 can never be filled.

The registry declaration and the enum are therefore asserted against each other
in both directions: the published vocabulary may not name a state the code
cannot express, and the code may not carry a state the declaration does not
ground.
"""

from __future__ import annotations

from datetime import date

import pytest

from ...calculations.registry.authority import bundled_authority
from ...calculations.registry.facts.resolution import MappingFactQuery, ResolvedMappingFact
from ...calculations.registry.schema_base import DateAxis
from ..schema import IvaCashAccountingTreatment

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]

_ON = date(2026, 3, 10)
_PREFIX = "cash_accounting."
_VALUE_SUFFIX = ".value"


def _vocabulary_entries() -> dict[str, str]:
    resolved = bundled_authority().resolve_governed_fact(
        MappingFactQuery(
            fact_id="iva-statutory-schema-vocabulary",
            date_axis=DateAxis.FILING_PERIOD,
            effective_date=_ON,
        ),
    )
    assert isinstance(resolved, ResolvedMappingFact)
    return {str(entry.key): str(entry.value) for entry in resolved.payload.entries}


def test_declared_cash_accounting_states_match_the_enum_in_both_directions() -> None:
    entries = _vocabulary_entries()
    declared = {value for key, value in entries.items() if key.startswith(_PREFIX) and key.endswith(_VALUE_SUFFIX)}

    assert declared == {member.value for member in IvaCashAccountingTreatment}


def test_the_acogido_state_is_grounded_on_its_own_article() -> None:
    """The acogido state is the one art. 163 terdecies governs, and it must say so.

    Without this the parity above would survive a migration that kept the token
    while attaching it to the destinatario's article, which would file an
    operation under a rule that does not govern it.
    """
    entries = _vocabulary_entries()
    refs = entries[f"{_PREFIX}{IvaCashAccountingTreatment.TAXPAYER_REGIME.value}.legal_refs"].split(",")

    assert "ley-37-1992:art-163-terdecies" in refs

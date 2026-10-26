"""The cash-accounting predicates refuse a treatment the pinned vocabulary does not declare.

Both predicates compared a treatment with one declared token and answered
``False`` for anything else. A stored treatment that a later authority retired
therefore read as "not ordinary", which is criterio de caja: the row's devengo
moved onto its collections with no authority behind the move.
"""

from __future__ import annotations

from collections.abc import Callable

import pytest

from ...calculations.registry.authority import PinnedAuthorityOperation
from ...calculations.registry.errors import RegistryValidationError
from ...calculations.registry.iva_cash_accounting_vocabulary import resolve_iva_cash_accounting_catalogue
from ..schema import (
    IvaCashAccountingTreatment,
    is_iva_cash_accounting_none,
    is_iva_cash_accounting_supplier_regime,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]

_RETIRED = IvaCashAccountingTreatment("retired_regime")


@pytest.mark.parametrize("predicate", [is_iva_cash_accounting_none, is_iva_cash_accounting_supplier_regime])
def test_an_undeclared_treatment_is_refused_rather_than_read_as_criterio_de_caja(
    predicate: Callable[..., bool],
    operation: PinnedAuthorityOperation,
) -> None:
    with pytest.raises(RegistryValidationError) as refusal:
        predicate(_RETIRED, authority=operation)

    assert "retired_regime" in str(refusal.value)


def test_every_declared_treatment_still_answers_both_predicates(operation: PinnedAuthorityOperation) -> None:
    """Accepted tokens keep their answers: exactly one is ordinary, exactly one is the supplier's."""
    catalogue = resolve_iva_cash_accounting_catalogue(authority=operation)

    ordinary = {token for token in catalogue.all_treatments if is_iva_cash_accounting_none(token, authority=operation)}
    supplier = {
        token
        for token in catalogue.all_treatments
        if is_iva_cash_accounting_supplier_regime(token, authority=operation)
    }

    assert ordinary == {catalogue.none_token}
    assert supplier == {catalogue.supplier_regime_token}
    assert catalogue.none_token != catalogue.supplier_regime_token

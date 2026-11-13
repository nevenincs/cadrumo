"""Supply a test sociedad's net turnover to every Modelo 200 binding the edition reads it through.

An edition reads the turnover through the preceding período impositivo's INCN
(the LIS art. 29.1 rate) and, from the edition that declares it, through the
INCN of the twelve months before the period (the DA 15ª BIN limit). A fixture
states one figure; this keeps to the bindings the edition declares, since the
engine refuses an unknown binding.
"""

from __future__ import annotations

from decimal import Decimal
from typing import Final

from ..schema import RegistrySnapshot

PRECEDING_PERIOD_TURNOVER: Final = "modelo-200-incn-periodo-impositivo-anterior"
PRIOR_TWELVE_MONTHS_TURNOVER: Final = "modelo-200-profile-incn-prior-12-months"


def turnover_binding_values(snapshot: RegistrySnapshot, turnover: Decimal) -> dict[str, Decimal]:
    """The turnover keyed by each turnover binding ``snapshot`` declares."""
    declared = {binding.id for binding in snapshot.revision.bindings}
    return {
        binding_id: turnover
        for binding_id in (PRECEDING_PERIOD_TURNOVER, PRIOR_TWELVE_MONTHS_TURNOVER)
        if binding_id in declared
    }

"""Derive whether Modelo 232 is owed from the operations a taxpayer states for an ejercicio.

The derivation reads the Modelo 232 statements through the application's read
capability and applies the Orden HFP/816/2017 art. 2 grounds with the thresholds
of the revision that governs the ejercicio. It names the grounds met and the
totals against their limits, and it never carries a tax identifier or a name.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from ...domain.calculations.registry.applicability_models import LedgerPayerFactDerivation
from ...domain.modelos.m232_obligation import (
    Modelo232Obligation,
    Modelo232ObligationFinding,
    assess_modelo_232_obligation,
)
from .m232_registry_parameters import modelo_232_thresholds
from .m232_related_party_repository import Modelo232RelatedPartyPersistenceError, Modelo232RelatedPartyReader

if TYPE_CHECKING:
    from ...core.modelo import Modelo
    from ...domain.calculations.registry.authority import PinnedAuthorityOperation

__all__ = [
    "derive_modelo_232_obligation",
    "ledger_payer_fact_derivation",
]


def derive_modelo_232_obligation(
    reader: Modelo232RelatedPartyReader,
    ejercicio: int,
    *,
    operation: PinnedAuthorityOperation,
    modelo: Modelo,
    period: str,
) -> Modelo232ObligationFinding:
    """Assess what the taxpayer stated for ``ejercicio`` against the pinned art. 2 thresholds.

    Raises:
        Modelo232RelatedPartyPersistenceError: The statements could not be read.
    """
    thresholds = modelo_232_thresholds(ejercicio, operation=operation, modelo=modelo, period=period)
    return assess_modelo_232_obligation(
        ejercicio,
        operations=reader.load_operations(ejercicio),
        nones=reader.load_none_statements(ejercicio),
        turnovers=reader.load_turnover_statements(ejercicio),
        thresholds=thresholds,
    )


def ledger_payer_fact_derivation(
    reader: Modelo232RelatedPartyReader,
    ejercicio: int,
    *,
    operation: PinnedAuthorityOperation,
    modelo: Modelo,
    period: str,
) -> LedgerPayerFactDerivation:
    """Return the payer-fact derivation for ``ejercicio``: owed, not owed, or unknown.

    Statements that cannot be read leave the fact unknown rather than failing
    the read that asked.
    """
    try:
        finding = derive_modelo_232_obligation(reader, ejercicio, operation=operation, modelo=modelo, period=period)
    except Modelo232RelatedPartyPersistenceError:
        return LedgerPayerFactDerivation.UNKNOWN
    if finding.obligation is Modelo232Obligation.OWED:
        return LedgerPayerFactDerivation.DERIVED_YES
    if finding.obligation is Modelo232Obligation.NOT_OWED:
        return LedgerPayerFactDerivation.DERIVED_NO
    return LedgerPayerFactDerivation.UNKNOWN

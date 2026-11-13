"""Derive whether Modelo 232 is owed from the operations a taxpayer states for an ejercicio.

The derivation reads the Modelo 232 statements through the application's read
capability and applies the Orden HFP/816/2017 art. 2 grounds with the thresholds
of the revision that governs the ejercicio. It names the grounds met and the
totals against their limits, and it never carries a tax identifier or a name.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Final

from ...core.decimal.formatting import format_decimal
from ...core.i18n.render import tr
from ...domain.calculations.registry.applicability_models import LedgerPayerFactDerivation
from ...domain.modelos.m232_obligation import (
    Modelo232Basis,
    Modelo232Obligation,
    Modelo232ObligationFinding,
    assess_modelo_232_obligation,
)
from ...domain.modelos.m232_related_party import Modelo232TurnoverSource
from .m232_registry_parameters import modelo_232_thresholds
from .m232_related_party_repository import Modelo232RelatedPartyPersistenceError, Modelo232RelatedPartyReader

if TYPE_CHECKING:
    from ...core.modelo import Modelo
    from ...domain.calculations.registry.authority import PinnedAuthorityOperation

__all__ = [
    "M232_TURNOVER_SOURCE_LOCALE_KEYS",
    "StatedRecordsDerivation",
    "derive_modelo_232_obligation",
    "modelo_232_finding_note",
    "stated_records_derivation",
]

M232_TURNOVER_SOURCE_LOCALE_KEYS: Final[dict[Modelo232TurnoverSource, str]] = {
    Modelo232TurnoverSource.ANNUAL_ACCOUNTS: "filing.applicability.records_turnover_source.annual_accounts",
    Modelo232TurnoverSource.CORPORATION_TAX_RETURN: (
        "filing.applicability.records_turnover_source.corporation_tax_return"
    ),
    Modelo232TurnoverSource.VAT_RETURNS: "filing.applicability.records_turnover_source.vat_returns",
    Modelo232TurnoverSource.OPERATOR_ESTIMATE: "filing.applicability.records_turnover_source.operator_estimate",
}
"""Locale keys naming where a stated turnover came from, one per source."""


@dataclass(frozen=True, slots=True)
class StatedRecordsDerivation:
    """What the stated records show about the fact, and the detail an operator needs to weigh it.

    ``note`` is the translated detail behind a derived yes or no: the turnover the
    art. 2.3 ground was tested against and where it came from, and the operations
    art. 2.2 left out. It is absent when the records settle nothing.
    """

    derivation: LedgerPayerFactDerivation
    note: str | None = None


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


def modelo_232_finding_note(finding: Modelo232ObligationFinding) -> str | None:
    """Name the turnover and its source, and the operations art. 2.2 excluded, when the finding has them."""
    sentences: list[str] = []
    if (
        finding.basis is Modelo232Basis.OPERATIONS_STATED
        and finding.turnover_source is not None
        and finding.turnover_eur is not None
    ):
        sentences.append(
            tr(
                "filing.applicability.records_turnover_considered",
                amount=format_decimal(finding.turnover_eur),
                source=tr(M232_TURNOVER_SOURCE_LOCALE_KEYS[finding.turnover_source]),
            )
        )
    if finding.excluded_operations:
        sentences.append(
            tr(
                "filing.applicability.records_excluded_operations",
                count=finding.excluded_operations,
                amount=format_decimal(finding.excluded_total_eur),
            )
        )
    return " ".join(sentences) or None


def stated_records_derivation(
    reader: Modelo232RelatedPartyReader,
    ejercicio: int,
    *,
    operation: PinnedAuthorityOperation,
    modelo: Modelo,
    period: str,
) -> StatedRecordsDerivation:
    """Return the payer-fact derivation for ``ejercicio``: owed, not owed, or unknown, with its detail.

    Statements that cannot be read leave the fact unknown rather than failing
    the read that asked.
    """
    try:
        finding = derive_modelo_232_obligation(reader, ejercicio, operation=operation, modelo=modelo, period=period)
    except Modelo232RelatedPartyPersistenceError:
        return StatedRecordsDerivation(LedgerPayerFactDerivation.UNKNOWN)
    if finding.obligation is Modelo232Obligation.OWED:
        return StatedRecordsDerivation(LedgerPayerFactDerivation.DERIVED_YES, modelo_232_finding_note(finding))
    if finding.obligation is Modelo232Obligation.NOT_OWED:
        return StatedRecordsDerivation(LedgerPayerFactDerivation.DERIVED_NO, modelo_232_finding_note(finding))
    return StatedRecordsDerivation(LedgerPayerFactDerivation.UNKNOWN)

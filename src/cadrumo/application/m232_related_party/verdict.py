"""What the stated records decide about Modelo 232 for one ejercicio, read for the listing.

The registry's payer-fact catalogue names the Modelo 232 revision whose dated
thresholds the derivation applies, so this module restates neither the modelo
nor its period. The listing shows the derivation of the stated records alone.
"""

from __future__ import annotations

from datetime import date
from typing import TYPE_CHECKING

from ...domain.calculations.registry.applicability_payer_facts import (
    PayerFactRecordsSource,
    resolve_payer_fact_catalogue,
)
from ...domain.calculations.registry.governed_fact_scope import validating_governed_facts
from ..aggregation.m232_related_party_obligation import derive_modelo_232_obligation
from .results import Modelo232VerdictProjection

if TYPE_CHECKING:
    from ...domain.calculations.registry.authority import PinnedAuthorityOperation
    from ..aggregation.m232_related_party_repository import Modelo232RelatedPartyReader

__all__ = ["modelo_232_verdict"]


def _records_source(ejercicio: int, operation: PinnedAuthorityOperation) -> PayerFactRecordsSource | None:
    with validating_governed_facts(operation):
        for fact in resolve_payer_fact_catalogue(effective_date=date(ejercicio, 12, 31)):
            # One store kind exists today, the Modelo 232 records; a second kind must be told apart here.
            source = fact.records_source
            if source is not None:
                return source
    return None


def modelo_232_verdict(
    reader: Modelo232RelatedPartyReader, ejercicio: int, *, operation: PinnedAuthorityOperation
) -> Modelo232VerdictProjection | None:
    """Derive the verdict of ``ejercicio`` from its stated records; ``None`` where no derivation is supported.

    No derivation is supported outside the generation's filing years, where the
    payer-fact catalogue names no Modelo 232 records source, or where that
    source's modelo does not support the ejercicio.

    Raises:
        Modelo232RelatedPartyPersistenceError: The statements could not be read.
    """
    if not operation.supported_filing_years().admits_filing_year(ejercicio):
        return None
    source = _records_source(ejercicio, operation)
    if source is None:
        return None
    support = operation.modelo_directory(source.modelo).supported_filing_years
    if support is not None and not support.admits_filing_year(ejercicio):
        return None
    finding = derive_modelo_232_obligation(
        reader, ejercicio, operation=operation, modelo=source.modelo, period=source.period
    )
    return Modelo232VerdictProjection.from_finding(finding)

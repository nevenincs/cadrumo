"""What a Modelo 202 instalment credits to the Modelo 200 casilla of its pago fraccionado.

The Modelo 200 carries the primer, segundo and tercer pago fraccionado of the
periodo impositivo in casillas 00601, 00603 and 00605, each read by a relation
binding from the Modelo 202 instalment of that period. A filed instalment is
read off its filing by the relation fold. When the fold holds nothing, the
instalment's own resolution decides. A filed instalment that does not state the
casilla of the other modalidad credits 0.00 for it: casillas 03 and 34 are the
Modelo 202's alternative results, and an absent alternative reads as zero, as the
filed amount itself is read. An instalment whose verdict says nothing was owed
(Orden HFP/227/2017 art. 1.3) credits a proven 0.00 with that verdict as its
grounds. Any other instalment stays unresolved with its reason.

The resolution is received through a
:data:`~cadrumo.application.calculations.modelo_202_instalment_resolution.Modelo202InstalmentResolver`
port bound at composition, so this module never decides an instalment verdict.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from ...core.casilla_id import CasillaId
from ...core.casilla_value_absence import AbsentCasillaReading
from ...core.period import Period
from ...domain.calculations.registry.authority import PinnedAuthorityOperation
from ...domain.calculations.registry.binding_temporal import SameFilingYearPeriods
from ...domain.calculations.registry.ids import LegalRefId
from ...domain.calculations.registry.relation_dependency import RelationDependencyRole
from ...domain.calculations.registry.relation_prefill_bindings import RelationPrefillProvider
from ...domain.calculations.registry.result_casillas import result_disposition_casilla_ids
from .modelo_202_base_source import is_modelo_202
from .modelo_202_instalment_resolution import (
    Modelo202InstalmentResolution,
    Modelo202InstalmentResolutionKind,
)


@dataclass(frozen=True, slots=True)
class Modelo202InstalmentCredit:
    """The value an unfolded instalment binding takes, with the grounds it rests on.

    Attributes:
        value: ``0.00`` for an instalment not owed, ``None`` while unresolved.
        note: The provenance sentence: the verdict's served reason, or why the
            instalment stays unresolved.
        legal_refs: The legal references of the verdict that proved the zero.
    """

    value: Decimal | None
    note: str
    legal_refs: tuple[LegalRefId, ...] = ()


def settled_instalment(
    provider: RelationPrefillProvider,
    *,
    filing_year: int,
    operation: PinnedAuthorityOperation,
) -> Period | None:
    """Return the one Modelo 202 instalment a final-settlement binding reads, or ``None``.

    Only a binding that reads a single instalment of the target's own ejercicio
    is credited instalment by instalment; any other binding keeps the fold's
    answer alone.
    """
    if provider.dependency_role is not RelationDependencyRole.INSTALMENT_TO_FINAL_SETTLEMENT:
        return None
    if not is_modelo_202(str(provider.source_modelo), operation=operation):
        return None
    temporal = provider.temporal
    if not isinstance(temporal, SameFilingYearPeriods) or len(temporal.source_periods) != 1:
        return None
    return Period.from_year_and_code(filing_year, temporal.source_periods[0])


def _filed_credit(
    resolution: Modelo202InstalmentResolution,
    *,
    source_modelo: str,
    source_casilla_ids: tuple[CasillaId, ...],
) -> Modelo202InstalmentCredit:
    """Credit a filed instalment the fold refused, only for a result alternative its filing does not state.

    A filing that states the casilla was refused by the fold on other grounds,
    so the binding stays unresolved rather than taking a figure the fold did
    not admit.
    """
    period = resolution.instalment.registry_token
    filing = resolution.filing
    alternatives = frozenset(result_disposition_casilla_ids(source_modelo) or ())
    if (
        filing is not None
        and source_casilla_ids
        and all(
            casilla_id in alternatives and casilla_id not in filing.observation.casilla_values
            for casilla_id in source_casilla_ids
        )
    ):
        reading = AbsentCasillaReading.RESULT_CASILLA_ALTERNATIVE
        return Modelo202InstalmentCredit(
            value=sum(
                (reading.read(filing.observation.casilla_values, casilla_id) for casilla_id in source_casilla_ids),
                Decimal("0"),
            ),
            note=(
                f"Modelo 202 {period} is filed without casilla {', '.join(source_casilla_ids)}, "
                f"the result of the modalidad it was not filed under ({reading.value})"
            ),
        )
    return Modelo202InstalmentCredit(
        value=None,
        note=f"Modelo 202 {period} is filed but the relation fold did not admit its filing",
    )


def instalment_credit(
    resolution: Modelo202InstalmentResolution,
    *,
    source_modelo: str,
    source_casilla_ids: tuple[CasillaId, ...],
) -> Modelo202InstalmentCredit:
    """Map an instalment the fold could not read to the value its binding takes."""
    period = resolution.instalment.registry_token
    if resolution.kind is Modelo202InstalmentResolutionKind.NOT_OWED:
        grounds = resolution.grounds
        if grounds is None or resolution.amount is None:
            raise ValueError(f"Modelo 202 instalment {period} resolved not owed without grounds or amount")
        return Modelo202InstalmentCredit(
            value=resolution.amount,
            note=f"Modelo 202 {period} not owed ({grounds.outcome.value}): {grounds.reason}",
            legal_refs=grounds.legal_refs,
        )
    if resolution.kind is Modelo202InstalmentResolutionKind.FILED:
        return _filed_credit(resolution, source_modelo=source_modelo, source_casilla_ids=source_casilla_ids)
    reason = resolution.unresolved_reason
    return Modelo202InstalmentCredit(
        value=None,
        note=f"Modelo 202 {period} unresolved ({reason.value if reason is not None else 'unknown'})",
    )


__all__ = ["Modelo202InstalmentCredit", "instalment_credit", "settled_instalment"]

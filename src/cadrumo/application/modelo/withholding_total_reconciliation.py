"""Compare an annual withholding summary's total with its periodic returns' totals.

The Modelo 190 resumen's "Importe total de las retenciones e ingresos a cuenta"
is the sum of the summary's own type-2 records (Orden EHA/3127/2009, design
positions 161-175), and each Modelo 111 quarter's casilla 28 is "la suma de las
retenciones e ingresos a cuenta que, por todos los conceptos" that quarter
declared (AEAT, Modelo 111 instructions). Neither figure is computed from the
other, and both state the same year's withholding, so a difference is something
for the filer to look at rather than an error the application settles: a
complementaria filed for one quarter, a record kept after its quarter was filed,
or a withholding entered on one side only each produce one. The summary keeps
its records' sum; the check reports a warning naming both figures, the quarters
compared and the gap.

Only withholding is compared. The summary also declares exempt percepciones that
no periodic box carries, so its percepciones can exceed the quarters' bases
without either being wrong.

A year is compared only when every quarter's return is observed. With a quarter
missing, the sum would understate the periodic side, and the perceptor-count
note already names the quarters it could not read. Which summaries this reaches,
and through which boxes, is declared by the ``withholding-modelo-routing`` fact.
"""

from __future__ import annotations

from decimal import Decimal
from typing import TYPE_CHECKING

from ...core.period import Period
from ...domain.calculations.registry.casilla_membership import casillas_by_id
from ...domain.calculations.registry.errors import RegistrySnapshotError, RegistryValidationError
from ...domain.modelos.verification_report import (
    ModeloVerificationFinding,
    ModeloVerificationFindingKind,
    ModeloVerificationFindingSeverity,
)
from ..aggregation.withholding_filing_cadence import QUARTERLY_WITHHOLDING_PERIODS
from ..aggregation.withholding_modelo_routing import withholding_total_route
from ..aggregation.withholding_source import withholding_binding_grounding
from .finding_message_text import PERIOD_LIST_SEPARATOR
from .registry_input_refusals import registry_integrity_verdict

if TYPE_CHECKING:
    from ...domain.calculations.registry.authority import PinnedAuthorityOperation
    from ...domain.calculations.registry.ids import LegalRefId, SourceRefId
    from ...domain.calculations.registry.schema import ModeloRevision
    from ...domain.modelos.calculation_revision import CalculationRevision
    from ...domain.modelos.work_unit import WorkUnit
    from ..calculations.observations_repository import CalculationObservationRepositoryProtocol

WITHHOLDING_TOTAL_MISMATCH_KEY = "application.modelo.findings.withholding_total_differs_from_periodic_returns"
"""The catalogue key of the warning this check raises."""


def _casilla_grounding(
    revision: ModeloRevision, casilla_id: str
) -> tuple[tuple[LegalRefId, ...], tuple[SourceRefId, ...]]:
    definition = casillas_by_id(revision).get(casilla_id)
    if definition is None:
        raise RegistryValidationError(
            f"revision {revision.id!r} declares no casilla {casilla_id!r}",
            precondition_verdict=registry_integrity_verdict("withholding_total_route"),
        )
    return tuple(definition.legal_refs), tuple(definition.source_refs)


def withholding_total_reconciliation_finding(
    *,
    work_unit: WorkUnit,
    target: CalculationRevision,
    observation_repository: CalculationObservationRepositoryProtocol,
    operation: PinnedAuthorityOperation,
) -> ModeloVerificationFinding | None:
    """Return the warning when the summary's total and the periodic returns' totals differ, else ``None``.

    ``None`` too when no route is declared for the modelo, the calculation holds
    no total, or any quarter's return or total box is not observed.
    """
    modelo = str(work_unit.modelo)
    route = withholding_total_route(modelo)
    if route is None:
        return None
    summary_total = target.casilla_values.get(route.summary_casilla_id)
    if summary_total is None:
        return None
    filing_year = work_unit.filing_year
    periodic_total = Decimal("0")
    periodic_revision: ModeloRevision | None = None
    for period_code in QUARTERLY_WITHHOLDING_PERIODS:
        payload = observation_repository.load_observation(
            route.periodic_modelo.value,
            Period.from_year_and_code(filing_year, period_code),
        )
        declared = None if payload is None else payload.observation.casilla_values.get(route.periodic_casilla_id)
        if declared is None:
            return None
        try:
            periodic_revision = operation.snapshot(
                route.periodic_modelo, filing_year=filing_year, period=period_code
            ).revision
        except (RegistrySnapshotError, RegistryValidationError):
            return None
        periodic_total += declared
    if periodic_revision is None or periodic_total == summary_total:
        return None
    summary_revision = operation.snapshot(
        modelo, filing_year=filing_year, period=work_unit.period.registry_token
    ).revision
    summary_legal, summary_sources = _casilla_grounding(summary_revision, route.summary_casilla_id)
    periodic_legal, periodic_sources = _casilla_grounding(periodic_revision, route.periodic_casilla_id)
    binding_legal, binding_sources = withholding_binding_grounding(summary_revision)
    return ModeloVerificationFinding(
        kind=ModeloVerificationFindingKind.RECONCILIATION_MISMATCH,
        severity=ModeloVerificationFindingSeverity.WARNING,
        casilla_id=route.summary_casilla_id,
        message_locale_key=WITHHOLDING_TOTAL_MISMATCH_KEY,
        message_facts={
            "modelo": modelo,
            "filing_year": filing_year,
            "source_modelo": route.periodic_modelo.value,
            "checked_periods": PERIOD_LIST_SEPARATOR.join(QUARTERLY_WITHHOLDING_PERIODS),
            "summary_total": summary_total,
            "periodic_total": periodic_total,
            "gap": abs(summary_total - periodic_total),
        },
        legal_refs=tuple(sorted({*summary_legal, *periodic_legal, *binding_legal})),
        source_refs=tuple(sorted({*summary_sources, *periodic_sources, *binding_sources})),
    )


__all__ = [
    "WITHHOLDING_TOTAL_MISMATCH_KEY",
    "withholding_total_reconciliation_finding",
]

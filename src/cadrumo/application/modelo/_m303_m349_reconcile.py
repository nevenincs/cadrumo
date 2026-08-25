"""Modelo 303 <-> Modelo 349 intra-community reconcile advisory.

An operator who carries out intra-community operations files both the periodic
Modelo 303 self-assessment — whose information boxes ``10`` (adquisiciones
intracomunitarias de bienes y servicios) and ``59`` (entregas intracomunitarias
de bienes y servicios) total the period's intra-community activity — and the
recapitulativa Modelo 349, whose resumen box ``decl.importe-operaciones``
(*Importe de las operaciones intracomunitarias*) totals every intra-community
operation declared per counterparty. The two totals describe the same economic
activity for the same period and must reconcile; a material divergence is an
operator error to resolve before filing (a missing or duplicated operator row on
the 349, a mis-booked intra-community invoice on the 303).

This module surfaces that divergence as a non-blocking WARNING advisory on the
verify path (a :class:`~domain.modelos.ModeloVerificationFinding` of kind
``reconciliation_mismatch``). It is deliberately advisory rather than blocking:
legitimate scope/timing differences (triangular operations, rectifications
carried in a separate 349 resumen field, cadence quirks) can produce small,
explainable gaps, so only a gap beyond a de-minimis euro tolerance is reported,
and it never refuses the verified-complete transition. Both aggregations already
exist — this cross-validator only *reads* the two persisted totals; it does not
re-derive either one.
"""

from __future__ import annotations

from collections.abc import Mapping
from datetime import datetime
from decimal import Decimal

from ...core import CasillaId, Modelo
from ...domain.calculations.registry import LegalRefId, SourceRefId
from ...domain.modelos import (
    CalculationRevision,
    CalculationRevisionCatalogue,
    CalculationRevisionCatalogueRepositoryProtocol,
    CalculationRevisionState,
    ModeloCode,
    ModeloVerificationFinding,
    ModeloVerificationFindingKind,
    ModeloVerificationFindingSeverity,
    WorkUnit,
    WorkUnitCatalogue,
)
from ...domain.modelos.work_unit_repository import WorkUnitCatalogueRepositoryProtocol
from .work_addressing import (
    ModeloWorkSelectionMode,
    ModeloWorkSelectorRequest,
    ModeloWorkSelectorState,
    select_modelo_work_resolution,
)

#: Modelo 303 information box: base of intra-community acquisitions of goods and
#: services (official casilla 10).
_M303_INTRACOM_ADQUISICIONES_CASILLA: CasillaId = "10"

#: Modelo 303 information box: intra-community supplies of goods and services
#: (official casilla 59).
_M303_INTRACOM_ENTREGAS_CASILLA: CasillaId = "59"

#: Modelo 349 resumen total: importe de las operaciones intracomunitarias — the
#: sum of every declared operator row's base across all claves.
_M349_IMPORTE_OPERACIONES_CASILLA: CasillaId = "decl.importe-operaciones"

#: Euro tolerance below which a 303<->349 total gap is treated as rounding /
#: timing noise rather than a reportable discrepancy. Both surfaces total
#: whole-euro information boxes summed across many per-operator rows, so a small
#: residual is expected and must not train the operator to ignore the advisory.
_M303_M349_RECONCILE_DEMINIMIS_EUR: Decimal = Decimal("1.00")

#: Binding provisions the reconcile grounds against: LIVA arts. 25 (exempt
#: intra-community supplies) and 15 (intra-community acquisitions) establish the
#: 303 boxes; the 349 recapitulativa is the Orden EHA/769/2010 art. 1 obligation
#: implementing the LGT art. 93 duty to inform.
_RECONCILE_LEGAL_REFS: tuple[LegalRefId, ...] = (
    "ley-37-1992:art-25",
    "ley-37-1992:art-15",
    "orden-eha-769-2010:art-1",
    "ley-58-2003:art-93",
)
_RECONCILE_SOURCE_REFS: tuple[SourceRefId, ...] = (
    "aeat-dr-303-2025",
    "aeat-dr-349-2020-current",
)

#: Revision-state preference when several revisions exist for the sibling work
#: unit and no explicit filed/current pointer resolves: the filed revision is the
#: strongest reconcile anchor, then the verified-complete draft, then any draft.
_REVISION_RECONCILE_PRIORITY: Mapping[CalculationRevisionState, int] = {
    CalculationRevisionState.PRESENTADO: 4,
    CalculationRevisionState.PRESENTADO_SUPERSEDIDO: 3,
    CalculationRevisionState.VERIFICADO_COMPLETO: 2,
    CalculationRevisionState.BORRADOR: 1,
}


def _casilla_decimal(values: Mapping[CasillaId, Decimal], casilla: CasillaId) -> Decimal:
    """Read one casilla's Decimal from a revision's value map, defaulting to zero."""
    value = values.get(casilla)
    return value if value is not None else Decimal("0")


def _sibling_work_unit(
    *,
    work_unit: WorkUnit,
    sibling_modelo: str,
    catalogue: WorkUnitCatalogue,
) -> WorkUnit | None:
    """Select one active same-period counterpart through the canonical policy."""
    resolution = select_modelo_work_resolution(
        ModeloWorkSelectorRequest(
            bucket_id=work_unit.bucket_id,
            modelo=ModeloCode(sibling_modelo),
            filing_year=work_unit.filing_year,
            period=work_unit.period,
        ),
        catalogue=catalogue,
        bucket_id=work_unit.bucket_id,
        mode=ModeloWorkSelectionMode.ACTIVE_NATURAL,
    )
    if resolution.state is ModeloWorkSelectorState.ABSENT:
        return None
    assert resolution.work_unit is not None
    return resolution.work_unit


def _reconcile_revision_priority(revision: CalculationRevision) -> tuple[int, datetime]:
    return (_REVISION_RECONCILE_PRIORITY.get(revision.state, 0), revision.updated_at)


def _reconcile_revision_for_work_unit(
    unit: WorkUnit,
    revisions: CalculationRevisionCatalogue,
) -> CalculationRevision | None:
    """Resolve the calculation revision to reconcile against for a work unit.

    Prefers the authoritative live pointers (filed, then current); falls back to
    the strongest-state revision attached to the work unit. Returns ``None`` when
    the work unit has no calculation revision yet.
    """
    for pointer in (unit.filed_calculation_revision_id, unit.current_calculation_revision_id):
        if pointer:
            revision = revisions.get(pointer)
            if revision is not None:
                return revision
    candidates = revisions.for_work_unit(unit.work_unit_id)
    if not candidates:
        return None
    return max(candidates, key=_reconcile_revision_priority)


def m303_m349_intracom_reconcile_findings(
    *,
    work_unit: WorkUnit,
    target: CalculationRevision,
    work_unit_repository: WorkUnitCatalogueRepositoryProtocol,
    calculation_repository: CalculationRevisionCatalogueRepositoryProtocol,
) -> list[ModeloVerificationFinding]:
    """Reconcile Modelo 303 intra-community totals against the Modelo 349 resumen.

    When the work unit under verification is a Modelo 303 or Modelo 349 and its
    same-bucket, same-period counterpart carries a persisted calculation
    revision, compares the 303 intra-community total (box 10 + box 59) against the
    349 resumen total (``decl.importe-operaciones``). A gap beyond
    :data:`_M303_M349_RECONCILE_DEMINIMIS_EUR` yields one non-blocking WARNING
    :class:`~domain.modelos.ModeloVerificationFinding`; otherwise the list is
    empty. The reconcile is skipped (empty list) when the modelo is neither 303
    nor 349, the counterpart work unit or its revision is absent, or both totals
    are zero (nothing intra-community declared on either side).

    Args:
        work_unit: The work unit being verified (the reconcile anchor).
        target: The draft :class:`~domain.modelos.CalculationRevision` under
            verification, supplying the anchor modelo's own totals.
        work_unit_repository: Source of the counterpart work unit.
        calculation_repository: Source of the counterpart's persisted revision.

    Returns:
        Zero or one WARNING-severity advisory finding.
    """
    modelo = str(work_unit.modelo)
    if modelo == Modelo.M303.value:
        sibling_modelo = Modelo.M349.value
    elif modelo == Modelo.M349.value:
        sibling_modelo = Modelo.M303.value
    else:
        return []

    sibling_unit = _sibling_work_unit(
        work_unit=work_unit,
        sibling_modelo=sibling_modelo,
        catalogue=work_unit_repository.load(),
    )
    if sibling_unit is None:
        return []

    sibling_revision = _reconcile_revision_for_work_unit(sibling_unit, calculation_repository.load())
    if sibling_revision is None:
        return []

    if modelo == Modelo.M303.value:
        m303_values, m349_values = target.casilla_values, sibling_revision.casilla_values
    else:
        m303_values, m349_values = sibling_revision.casilla_values, target.casilla_values

    m303_total = _casilla_decimal(m303_values, _M303_INTRACOM_ADQUISICIONES_CASILLA) + _casilla_decimal(
        m303_values,
        _M303_INTRACOM_ENTREGAS_CASILLA,
    )
    m349_total = _casilla_decimal(m349_values, _M349_IMPORTE_OPERACIONES_CASILLA)

    if m303_total == 0 and m349_total == 0:
        return []

    gap = abs(m303_total - m349_total)
    if gap <= _M303_M349_RECONCILE_DEMINIMIS_EUR:
        return []

    return [
        ModeloVerificationFinding(
            kind=ModeloVerificationFindingKind.RECONCILIATION_MISMATCH,
            severity=ModeloVerificationFindingSeverity.WARNING,
            message_locale_key="application.modelo.findings.m303_m349_intracom_reconciliation_mismatch",
            message_facts={
                "period_code": work_unit.period.registry_token,
                "filing_year": work_unit.filing_year,
                "m303_total": m303_total,
                "m349_total": m349_total,
                "gap": gap,
            },
            legal_refs=_RECONCILE_LEGAL_REFS,
            source_refs=_RECONCILE_SOURCE_REFS,
        ),
    ]


__all__ = ["m303_m349_intracom_reconcile_findings"]

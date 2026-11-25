"""Year-over-year comparison of the best persisted calculation revisions of one modelo.

The comparison reads stored :class:`CalculationRevision` rows for two filing
years, prefers verified revisions over drafts, and grounds each delta row in the
compared :class:`ModeloRevision` casilla metadata or the revision's recorded
observation provenance. It shares :class:`ModeloProjectionError` with the
projection service but touches none of its engine, profile or withholding
channels;
:class:`CasillaObservation`, an observed casilla value.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from decimal import Decimal
from typing import TYPE_CHECKING

from pydantic import BaseModel, Field

from ...core.casilla_id import CasillaId
from ...core.models import STRICT_FROZEN_CONFIG
from ...domain.calculations.registry.bindings import CasillaObservation
from ...domain.calculations.registry.ids import FormulaId, LegalRefId, RevisionId, SourceRefId
from ...domain.calculations.registry.schema import ModeloRevision
from ...domain.calculations.registry.schema_surfaces import CasillaDefinition
from ...domain.modelos.calculation_revision import CalculationRevision, CalculationRevisionState
from ...domain.modelos.work_unit import WorkUnit
from .calculation_action_ports import CalculationActionPorts
from .calculation_revision_queries import list_calculation_revisions
from .lifecycle_view_refusal_doors import work_create_verdict, work_list_verdict
from .projection import ModeloProjectionError
from .refusal_door_verdicts import operator_choice_verdict, registry_defect_verdict
from .work_lifecycle import list_work_units

if TYPE_CHECKING:
    from ...domain.calculations.registry.authority import PinnedAuthorityOperation


class ModeloCompareNeedTwoYearsError(ModeloProjectionError):
    """Raised when comparison is not addressed to exactly two filing years."""


class ModeloCompareNoWorkUnitsError(ModeloProjectionError):
    """Raised when comparison finds no work units for a filing year."""


class ModeloCompareNoRevisionsError(ModeloProjectionError):
    """Raised when comparison finds work units but no calculation revisions."""


class ModeloCompareNoUsableRevisionsError(ModeloProjectionError):
    """Raised when comparison finds no verified or draft revisions."""


class ModeloCompareDeltaRow(BaseModel):
    """One casilla delta row in a modelo year comparison."""

    model_config = STRICT_FROZEN_CONFIG

    casilla_id: CasillaId
    label: str
    section: str
    year_a_value: Decimal
    year_b_value: Decimal
    delta: Decimal
    pct_change: Decimal | None
    formula_id: FormulaId | None = None
    legal_refs: tuple[LegalRefId, ...] = Field(min_length=1)
    source_refs: tuple[SourceRefId, ...] = Field(min_length=1)


class ModeloCompareSection(BaseModel):
    """One section grouping for a modelo comparison."""

    model_config = STRICT_FROZEN_CONFIG

    section: str
    rows: tuple[ModeloCompareDeltaRow, ...]


class ModeloCompareServiceResult(BaseModel):
    """Year-over-year comparison result for one modelo."""

    model_config = STRICT_FROZEN_CONFIG

    modelo: str = Field(min_length=1)
    year_a: int
    year_b: int
    year_a_revision_id: RevisionId
    year_b_revision_id: RevisionId
    year_a_is_draft: bool
    year_b_is_draft: bool
    sections: tuple[ModeloCompareSection, ...]
    delta_rows: tuple[ModeloCompareDeltaRow, ...]


def _compare_row_provenance(
    *,
    modelo: str,
    year_a: int,
    year_b: int,
    casilla_id: CasillaId,
    casilla_meta: Mapping[CasillaId, CasillaDefinition],
    observation: CasillaObservation | None,
) -> tuple[str | None, tuple[str, ...], tuple[str, ...]]:
    cdef = casilla_meta.get(casilla_id)
    if cdef is None:
        raise ModeloProjectionError(
            translated_message="errors.error.modelo_projection",
            context={
                "modelo": modelo,
                "year_a": year_a,
                "year_b": year_b,
                "casilla_id": casilla_id,
            },
            precondition_verdict=registry_defect_verdict("compare_casilla_declared"),
        )
    formula_id = observation.formula_id if observation is not None else None
    if formula_id is None and cdef.formula is not None:
        formula_id = cdef.formula
    legal_refs = observation.legal_refs if observation is not None else tuple(cdef.legal_refs)
    source_refs = observation.source_refs if observation is not None else tuple(cdef.source_refs)
    if not legal_refs or not source_refs:
        raise ModeloProjectionError(
            translated_message="errors.error.modelo_projection",
            context={
                "modelo": modelo,
                "year_a": year_a,
                "year_b": year_b,
                "casilla_id": casilla_id,
            },
            precondition_verdict=registry_defect_verdict("compare_casilla_references"),
        )
    return formula_id, legal_refs, source_refs


def _best_revision_for_compare(
    *,
    modelo: str,
    filing_year: int,
    ports: CalculationActionPorts,
) -> tuple[CalculationRevision, bool, str]:
    units_for_year = _comparison_work_units(modelo=modelo, filing_year=filing_year, ports=ports)
    if not units_for_year:
        raise ModeloCompareNoWorkUnitsError(
            context={"modelo": modelo, "filing_year": filing_year},
            translated_message="cli.app.modelo.compare.no_work_units",
            precondition_verdict=work_create_verdict("compare_work_units", modelo=str(modelo), filing_year=filing_year),
        )

    period_by_unit = {unit.work_unit_id: unit.period.registry_token for unit in units_for_year}
    all_revisions = _comparison_revisions_for_units(units_for_year, ports=ports)

    if not all_revisions:
        raise ModeloCompareNoRevisionsError(
            context={"modelo": modelo, "filing_year": filing_year},
            translated_message="cli.app.modelo.compare.no_revisions",
            precondition_verdict=work_list_verdict("compare_revisions"),
        )

    best = _latest_comparison_revision(all_revisions, state=CalculationRevisionState.VERIFICADO_COMPLETO)
    if best is not None:
        return best, False, period_by_unit.get(best.work_unit_id, "0A")

    best = _latest_comparison_revision(all_revisions, state=CalculationRevisionState.BORRADOR)
    if best is not None:
        return best, True, period_by_unit.get(best.work_unit_id, "0A")

    raise ModeloCompareNoUsableRevisionsError(
        context={"modelo": modelo, "filing_year": filing_year},
        translated_message="cli.app.modelo.compare.no_usable_revisions",
        precondition_verdict=work_list_verdict("compare_usable_revisions"),
    )


def _comparison_work_units(*, modelo: str, filing_year: int, ports: CalculationActionPorts) -> list[WorkUnit]:
    """Return persisted work units matching one comparison coordinate."""
    return [
        unit
        for unit in list_work_units(ports=ports.work_lifecycle_ports)
        if str(unit.modelo) == modelo and unit.filing_year == filing_year
    ]


def _comparison_revisions_for_units(
    units: Iterable[WorkUnit],
    *,
    ports: CalculationActionPorts,
) -> list[CalculationRevision]:
    """Flatten the revisions belonging to comparison work units in unit order."""
    revisions: list[CalculationRevision] = []
    for unit in units:
        revisions.extend(list_calculation_revisions(work_unit_id=unit.work_unit_id, ports=ports))
    return revisions


def _latest_comparison_revision(
    revisions: Iterable[CalculationRevision],
    *,
    state: CalculationRevisionState,
) -> CalculationRevision | None:
    """Return the newest revision in one state, or ``None`` when absent."""
    candidates = [revision for revision in revisions if revision.state is state]
    if not candidates:
        return None
    return max(candidates, key=lambda revision: revision.created_at)


def _comparison_year_pair(years: Iterable[int]) -> tuple[int, int]:
    """Validate and order the two filing years addressed by a comparison."""
    requested_years = sorted(years)
    try:
        year_a, year_b = requested_years
    except ValueError:
        raise ModeloCompareNeedTwoYearsError(
            translated_message="cli.app.modelo.compare.need_two_years",
            precondition_verdict=operator_choice_verdict("compare_two_years"),
        ) from None
    return year_a, year_b


def _comparison_static_revisions(
    *,
    modelo: str,
    year_a: int,
    year_b: int,
    period_a: str,
    period_b: str,
    operation: PinnedAuthorityOperation,
) -> tuple[ModeloRevision, ModeloRevision]:
    """Resolve both law-version revisions in the historical comparison order."""
    rev_b_static = operation.revision_for_context(
        modelo,
        filing_year=year_b,
        period=period_b,
    )
    rev_a_static = operation.revision_for_context(
        modelo,
        filing_year=year_a,
        period=period_a,
    )
    return rev_a_static, rev_b_static


def _comparison_casilla_metadata(
    rev_a_static: ModeloRevision,
    rev_b_static: ModeloRevision,
) -> dict[CasillaId, CasillaDefinition]:
    """Index casilla metadata in the same A-then-B overwrite order."""
    casilla_meta: dict[CasillaId, CasillaDefinition] = {}
    for static_revision in (rev_a_static, rev_b_static):
        for cdef in static_revision.casillas:
            casilla_meta[cdef.id] = cdef
    return casilla_meta


def _comparison_casilla_label_section(
    casilla_id: CasillaId,
    casilla_meta: Mapping[CasillaId, CasillaDefinition],
) -> tuple[str, str]:
    """Return the static label and first section for one comparison row."""
    cdef = casilla_meta.get(casilla_id)
    if cdef is None:
        return casilla_id, ""
    sections = cdef.section
    return cdef.label, sections[0] if sections else ""


def _comparison_delta_rows(
    rev_a: CalculationRevision,
    rev_b: CalculationRevision,
    *,
    modelo: str,
    year_a: int,
    year_b: int,
    casilla_meta: Mapping[CasillaId, CasillaDefinition],
) -> list[ModeloCompareDeltaRow]:
    """Build exact own-arithmetic deltas and retain registry provenance."""
    obs_by_id = {obs.casilla_id: obs for revision in (rev_a, rev_b) for obs in revision.observations}
    delta_rows: list[ModeloCompareDeltaRow] = []
    for casilla_id in sorted(set(rev_a.casilla_values) | set(rev_b.casilla_values)):
        value_a = rev_a.casilla_values.get(casilla_id, Decimal("0"))
        value_b = rev_b.casilla_values.get(casilla_id, Decimal("0"))
        delta = value_b - value_a
        label, section = _comparison_casilla_label_section(casilla_id, casilla_meta)
        pct_change = (delta / value_a * Decimal("100")).quantize(Decimal("0.01")) if value_a != Decimal("0") else None
        formula_id, legal_refs, source_refs = _compare_row_provenance(
            modelo=modelo,
            year_a=year_a,
            year_b=year_b,
            casilla_id=casilla_id,
            casilla_meta=casilla_meta,
            observation=obs_by_id.get(casilla_id),
        )
        delta_rows.append(
            ModeloCompareDeltaRow(
                casilla_id=casilla_id,
                label=label,
                section=section,
                year_a_value=value_a,
                year_b_value=value_b,
                delta=delta,
                pct_change=pct_change,
                formula_id=formula_id,
                legal_refs=legal_refs,
                source_refs=source_refs,
            ),
        )
    return delta_rows


def _comparison_sections(
    delta_rows: Iterable[ModeloCompareDeltaRow],
) -> tuple[list[str], dict[str, list[ModeloCompareDeltaRow]]]:
    """Group comparison rows while preserving their first-seen section order."""
    sections_seen: list[str] = []
    by_section: dict[str, list[ModeloCompareDeltaRow]] = {}
    for row in delta_rows:
        if row.section not in by_section:
            sections_seen.append(row.section)
            by_section[row.section] = []
        by_section[row.section].append(row)
    return sections_seen, by_section


def compare_modelo_years(
    *,
    modelo: str,
    years: Iterable[int],
    ports: CalculationActionPorts,
    operation: PinnedAuthorityOperation,
) -> ModeloCompareServiceResult:
    """Compare the best persisted revision for two filing years.

    Verified :class:`CalculationRevision` rows win over drafts. Each emitted
    :class:`ModeloCompareDeltaRow` is grounded against the compared
    :class:`ModeloRevision` casilla metadata or the revision's recorded
    observation provenance before the :class:`ModeloCompareServiceResult` is
    returned; comparing two already-persisted revisions is not itself a
    filing act, so the registry side is read structurally.
    """
    year_a, year_b = _comparison_year_pair(years)

    rev_a, draft_a, period_a = _best_revision_for_compare(modelo=modelo, filing_year=year_a, ports=ports)
    rev_b, draft_b, period_b = _best_revision_for_compare(modelo=modelo, filing_year=year_b, ports=ports)

    rev_a_static, rev_b_static = _comparison_static_revisions(
        modelo=modelo,
        year_a=year_a,
        year_b=year_b,
        period_a=period_a,
        period_b=period_b,
        operation=operation,
    )
    casilla_meta = _comparison_casilla_metadata(rev_a_static, rev_b_static)

    # Both sides are the application's OWN arithmetic, which is what separates
    # this from the tree's other per-casilla comparators. A money tolerance
    # would be wrong here rather than merely unnecessary: two of our own
    # revisions differing by a cent differ by a cent, and absorbing that
    # would hide a real change. Absence is zero for the same reason -- a
    # casilla one revision never resolved contributes nothing to it.
    # ``detect_casilla_divergences`` compares against AEAT, where rounding IS
    # an artefact, and
    # ``casillas_a_recapture_would_change`` skips absence entirely.
    delta_rows = _comparison_delta_rows(
        rev_a,
        rev_b,
        modelo=modelo,
        year_a=year_a,
        year_b=year_b,
        casilla_meta=casilla_meta,
    )
    sections_seen, by_section = _comparison_sections(delta_rows)

    return ModeloCompareServiceResult(
        modelo=modelo,
        year_a=year_a,
        year_b=year_b,
        year_a_revision_id=rev_a.calculation_revision_id,
        year_b_revision_id=rev_b.calculation_revision_id,
        year_a_is_draft=draft_a,
        year_b_is_draft=draft_b,
        sections=tuple(
            ModeloCompareSection(section=section, rows=tuple(by_section[section])) for section in sections_seen
        ),
        delta_rows=tuple(delta_rows),
    )


__all__ = [
    "ModeloCompareDeltaRow",
    "ModeloCompareNeedTwoYearsError",
    "ModeloCompareNoRevisionsError",
    "ModeloCompareNoUsableRevisionsError",
    "ModeloCompareNoWorkUnitsError",
    "ModeloCompareSection",
    "ModeloCompareServiceResult",
    "compare_modelo_years",
]

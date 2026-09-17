"""The RDL 7/2024 DANA reduction applies only inside its authored 2024 window."""

from __future__ import annotations

from collections.abc import Iterator
from datetime import date
from decimal import Decimal

import pytest

from ....core.period import Period
from ....domain.calculations.registry.authority import PinnedAuthorityOperation, bundled_indexed_authority
from ....domain.calculations.registry.errors import RegistryValidationError
from ....domain.calculations.registry.facts.resolution import ResolvedScalarFact, ScalarFactQuery
from ....domain.calculations.registry.iva_schema_vocabulary import m303_regime_composition_simplified_scope
from ....domain.calculations.registry.m303_orden_resolution import resolve_m303_regimen_simplificado_snapshot
from ....domain.calculations.registry.schema_base import DateAxis
from ....domain.calculations.registry.schema_references import TemporalProjectionDirection
from ....domain.calculations.registry.tests.published_authority import PublishedGovernedFactSource, published_snapshot
from ....domain.filing_evidence import FilingEvidenceReference
from ....domain.iva.regimen_simplificado_rows import (
    ActividadNoAgricolaSimplificado,
    EntradaModuloSimplificado,
    M303RegimenSimplificadoScopeDecision,
    RegimenSimplificadoFilingRows,
)
from ..m303_regimen_simplificado import (
    M303RegimenSimplificadoCalculationError,
    calculate_m303_regimen_simplificado_result,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_DANA_FACT_ID = "rdl-7-2024-art-11-2:iva-simplificado-reduccion-cuota-devengada"


@pytest.fixture
def authority_operation() -> Iterator[PinnedAuthorityOperation]:
    with bundled_indexed_authority().operation() as operation:
        yield operation


def _dana_query(effective_date: date) -> ScalarFactQuery:
    return ScalarFactQuery(fact_id=_DANA_FACT_ID, date_axis=DateAxis.FILING_PERIOD, effective_date=effective_date)


def _simplified_scope() -> M303RegimenSimplificadoScopeDecision:
    return M303RegimenSimplificadoScopeDecision(
        scope=m303_regime_composition_simplified_scope("simplified", authority=PublishedGovernedFactSource()),
    )


def test_published_reduction_is_authored_for_2024(authority_operation: PinnedAuthorityOperation) -> None:
    resolved = authority_operation.resolve_governed_fact(_dana_query(date(2024, 12, 31)))

    assert isinstance(resolved, ResolvedScalarFact)
    assert resolved.projection_direction is TemporalProjectionDirection.AUTHORED
    assert resolved.payload.value == Decimal("0.25")


@pytest.mark.parametrize("effective_date", (date(2025, 12, 31), date(2026, 12, 31)))
def test_published_reduction_is_refused_after_2024(
    authority_operation: PinnedAuthorityOperation,
    effective_date: date,
) -> None:
    with pytest.raises(RegistryValidationError, match="has no variant for the exact query context"):
        authority_operation.resolve_governed_fact(_dana_query(effective_date))


def test_2024_terminal_simplified_result_requires_dana_eligibility_evidence(
    authority_operation: PinnedAuthorityOperation,
) -> None:
    period = Period.from_year_and_code(2024, "4T")
    scope_decision = _simplified_scope()
    regimen_snapshot = resolve_m303_regimen_simplificado_snapshot(
        registry_snapshot=published_snapshot("303", filing_year=2024, period="4T"),
        scope_decision=scope_decision,
    )

    with pytest.raises(M303RegimenSimplificadoCalculationError, match="DANA eligibility evidence is required"):
        calculate_m303_regimen_simplificado_result(
            period=period,
            scope_decision=scope_decision,
            rows=RegimenSimplificadoFilingRows(ejercicio=2024, activities=()),
            regimen_snapshot=regimen_snapshot,
            dana_eligibility=None,
            operation=authority_operation,
        )


def test_2026_terminal_simplified_result_calculates_without_dana_evidence(
    authority_operation: PinnedAuthorityOperation,
) -> None:
    period = Period.from_year_and_code(2026, "4T")
    scope_decision = _simplified_scope()
    regimen_snapshot = resolve_m303_regimen_simplificado_snapshot(
        registry_snapshot=published_snapshot("303", filing_year=2026, period="4T"),
        scope_decision=scope_decision,
    )
    annual_activity = next(activity for activity in regimen_snapshot.orden.activities if activity.kind == "no_agricola")
    assert annual_activity.iae_epigrafe is not None
    evidence = FilingEvidenceReference(reference="test:dana-window:2026-terminal-quarter")
    activity = ActividadNoAgricolaSimplificado(
        orden_id=annual_activity.orden_id,
        ejercicio=annual_activity.ejercicio,
        activity_id="test-dana-window-actividad",
        iae_epigrafe=annual_activity.iae_epigrafe,
        auxiliary_activity_indicator=annual_activity.auxiliary_activity_indicator,
        modulos=tuple(
            EntradaModuloSimplificado(
                module_identity=module.identity,
                declared_quantity=Decimal("1"),
                evidence_reference=evidence,
            )
            for module in annual_activity.modulos
        ),
        facts=(),
        evidence_reference=evidence,
    )

    result = calculate_m303_regimen_simplificado_result(
        period=period,
        scope_decision=scope_decision,
        rows=RegimenSimplificadoFilingRows(ejercicio=2026, activities=(activity,)),
        regimen_snapshot=regimen_snapshot,
        dana_eligibility=None,
        operation=authority_operation,
    )

    assert result.period == period

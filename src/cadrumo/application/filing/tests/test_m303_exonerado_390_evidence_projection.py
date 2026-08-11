"""Live application value arrival for immutable S56 exonerado-390 evidence."""

from __future__ import annotations

from decimal import Decimal

import pytest

from ....core import Period, validated_casilla_id
from ....core.resources import resources
from ....domain.calculations.registry import resolve_m303_regimen_simplificado_snapshot
from ....domain.filing import FilingExportError
from ....domain.filing_evidence import FilingEvidenceReference
from ....domain.iva import M303RegimenSimplificadoScope, M303RegimenSimplificadoScopeDecision
from ....domain.modelos import (
    M303Exonerado390ActivityRowEvidence,
    M303Exonerado390EndpointEvidence,
    M303Exonerado390FilingEvidence,
)
from .. import build_runtime_schema_provider, project_m303_exonerado_390_value_arrival

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_PERIODS = (
    Period.from_year_and_code(2023, "4T"),
    Period.from_year_and_code(2024, "2T"),
    Period.from_year_and_code(2024, "4T"),
    Period.from_year_and_code(2025, "4T"),
    Period.from_year_and_code(2026, "4T"),
)


def _evidence(*, operaciones_terceros_declarables: bool) -> M303Exonerado390FilingEvidence:
    reference = FilingEvidenceReference(reference="test:dp30304:value-arrival")
    return M303Exonerado390FilingEvidence(
        applicable=True,
        applicability_reference=reference,
        endpoints=(
            M303Exonerado390EndpointEvidence(
                casilla_id=validated_casilla_id("79", surface="S56 value arrival test"),
                value=Decimal("0"),
                evidence_reference=reference,
            ),
        ),
        activity_rows=(
            M303Exonerado390ActivityRowEvidence(
                slot=1, codigo_actividad="A01", epigrafe_iae="4101", evidence_reference=reference
            ),
            M303Exonerado390ActivityRowEvidence(
                slot=2, codigo_actividad="A02", epigrafe_iae="4102", evidence_reference=reference
            ),
            M303Exonerado390ActivityRowEvidence(
                slot=3, codigo_actividad="A03", epigrafe_iae="4103", evidence_reference=reference
            ),
            M303Exonerado390ActivityRowEvidence(
                slot=4, codigo_actividad="A04", epigrafe_iae="4104", evidence_reference=reference
            ),
            M303Exonerado390ActivityRowEvidence(
                slot=5, codigo_actividad="A05", epigrafe_iae="4105", evidence_reference=reference
            ),
            M303Exonerado390ActivityRowEvidence(
                slot=6, codigo_actividad="A06", epigrafe_iae="4106", evidence_reference=reference
            ),
        ),
        operaciones_terceros_declarables=operaciones_terceros_declarables,
        operaciones_terceros_reference=reference,
    )


def _record_design(period: Period):
    snapshot = resources().modelos.authority.snapshot("303", filing_year=period.filing_year, period=period.code)
    scope = M303RegimenSimplificadoScopeDecision(
        scope=M303RegimenSimplificadoScope.REGIMEN_SIMPLIFICADO_NOT_CLAIMED,
    )
    return resolve_m303_regimen_simplificado_snapshot(
        registry_snapshot=snapshot,
        scope_decision=scope,
    ).record_design


@pytest.mark.parametrize("period", _PERIODS)
@pytest.mark.parametrize(("operaciones_terceros_declarables", "marker"), ((False, None), (True, "X")))
def test_value_arrival_projects_each_real_epoch_in_canonical_order(
    period: Period,
    operaciones_terceros_declarables: bool,
    marker: str | None,
) -> None:
    projection = project_m303_exonerado_390_value_arrival(
        period=period,
        schema_provider=build_runtime_schema_provider(filing_year=period.filing_year, period=period, modelos=("303",)),
        evidence=_evidence(operaciones_terceros_declarables=operaciones_terceros_declarables),
        record_design=_record_design(period),
    )

    assert projection is not None
    assert tuple(field.value for field in projection.fields) == (
        "A01",
        "4101",
        "A02",
        "4102",
        "A03",
        "4103",
        "A04",
        "4104",
        "A05",
        "4105",
        "A06",
        "4106",
        marker,
    )


def test_value_arrival_translates_a_real_wrong_year_record_design_refusal() -> None:
    period = Period.from_year_and_code(2025, "4T")
    provider_period = Period.from_year_and_code(2026, "4T")

    with pytest.raises(FilingExportError, match="does not apply to filing year 2025"):
        project_m303_exonerado_390_value_arrival(
            period=period,
            schema_provider=build_runtime_schema_provider(
                filing_year=provider_period.filing_year,
                period=provider_period,
                modelos=("303",),
            ),
            evidence=_evidence(operaciones_terceros_declarables=False),
            record_design=_record_design(provider_period),
        )

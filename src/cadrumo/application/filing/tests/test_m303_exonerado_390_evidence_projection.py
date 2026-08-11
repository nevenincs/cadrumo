"""Persisted S56 evidence projects through every exact M303 DP30304 epoch."""

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


def _evidence(
    *,
    reference: FilingEvidenceReference,
    operaciones_terceros_declarables: bool,
    six_rows: bool,
) -> M303Exonerado390FilingEvidence:
    slots = range(1, 7) if six_rows else range(1, 2)
    return M303Exonerado390FilingEvidence(
        applicable=True,
        applicability_reference=reference,
        endpoints=(
            M303Exonerado390EndpointEvidence(
                casilla_id=validated_casilla_id("79", surface="DP30304 application projection test"),
                value=Decimal("0"),
                evidence_reference=reference,
            ),
        ),
        activity_rows=tuple(
            M303Exonerado390ActivityRowEvidence(
                slot=slot,
                codigo_actividad=f"A{slot:02d}",
                epigrafe_iae=f"41{slot:02d}",
                evidence_reference=reference,
            )
            for slot in slots
        ),
        operaciones_terceros_declarables=operaciones_terceros_declarables,
        operaciones_terceros_reference=reference,
    )


@pytest.mark.parametrize(("operaciones_terceros_declarables", "marker"), ((False, None), (True, "X")))
@pytest.mark.parametrize("period", _PERIODS)
def test_evidence_arrives_at_all_six_pairs_and_the_exact_modelo_347_marker_for_each_epoch(
    period: Period,
    operaciones_terceros_declarables: bool,
    marker: str | None,
) -> None:
    registry_snapshot = resources().modelos.authority.snapshot(
        "303",
        filing_year=period.filing_year,
        period=period.code,
    )
    scope = M303RegimenSimplificadoScopeDecision(
        scope=M303RegimenSimplificadoScope.REGIMEN_SIMPLIFICADO_NOT_CLAIMED,
    )
    record_design = resolve_m303_regimen_simplificado_snapshot(
        registry_snapshot=registry_snapshot,
        scope_decision=scope,
    ).record_design
    reference = FilingEvidenceReference(reference=f"test:dp30304:{period.filing_year}:{period.code}")
    evidence = _evidence(
        reference=reference,
        operaciones_terceros_declarables=operaciones_terceros_declarables,
        six_rows=True,
    )

    projection = project_m303_exonerado_390_value_arrival(
        period=period,
        schema_provider=build_runtime_schema_provider(
            filing_year=period.filing_year,
            period=period,
            modelos=("303",),
        ),
        evidence=evidence,
        record_design=record_design,
    )

    assert projection is not None
    assert tuple(field.offset for field in projection.fields) == (
        13,
        16,
        20,
        23,
        27,
        30,
        34,
        37,
        41,
        44,
        48,
        51,
        55,
    )
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


def test_value_arrival_refuses_a_record_design_identity_mismatch() -> None:
    period = Period.from_year_and_code(2026, "4T")
    registry_snapshot = resources().modelos.authority.snapshot("303", filing_year=2026, period="4T")
    scope = M303RegimenSimplificadoScopeDecision(
        scope=M303RegimenSimplificadoScope.REGIMEN_SIMPLIFICADO_NOT_CLAIMED,
    )
    record_design = resolve_m303_regimen_simplificado_snapshot(
        registry_snapshot=registry_snapshot,
        scope_decision=scope,
    ).record_design
    reference = FilingEvidenceReference(reference="test:dp30304:wrong-source")
    evidence = _evidence(
        reference=reference,
        operaciones_terceros_declarables=False,
        six_rows=False,
    )

    with pytest.raises(FilingExportError, match="no longer matches the registry"):
        project_m303_exonerado_390_value_arrival(
            period=period,
            schema_provider=build_runtime_schema_provider(filing_year=2026, period=period, modelos=("303",)),
            evidence=evidence,
            record_design=record_design.model_copy(update={"id": "aeat-dr-303-2025"}),
        )

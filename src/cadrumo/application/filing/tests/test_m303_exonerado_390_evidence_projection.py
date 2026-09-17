"""Persisted evidence projects through every exact M303 DP30304 epoch."""

from __future__ import annotations

from decimal import Decimal

import pytest

from cadrumo.domain.calculations.registry.authority import bundled_indexed_authority
from cadrumo.domain.calculations.registry.tests.published_authority import (
    PublishedGovernedFactSource,
    published_snapshot,
)

from ....core.casilla_id import validated_casilla_id
from ....core.filing_projection_ref import (
    M303Exonerado390ActivityField,
    M303Exonerado390ActivityProjectionRef,
    M303Exonerado390OperacionesTercerosProjectionRef,
)
from ....core.period import Period
from ....domain.calculations.registry.iva_schema_vocabulary import m303_regime_composition_simplified_scope
from ....domain.calculations.registry.m303_orden_resolution import resolve_m303_regimen_simplificado_snapshot
from ....domain.calculations.registry.schema import RegistrySnapshot
from ....domain.calculations.registry.schema_references import SourceReference
from ....domain.filing.errors import FilingExportError
from ....domain.filing_evidence import FilingEvidenceReference
from ....domain.iva.regimen_simplificado_rows import M303RegimenSimplificadoScopeDecision
from ....domain.modelos.calculation_revision_m303_evidence import (
    M303Exonerado390ActivityRowEvidence,
    M303Exonerado390EndpointEvidence,
    M303Exonerado390FilingEvidence,
)
from .._m303_exonerado_390 import project_m303_exonerado_390_value_arrival

pytestmark = [pytest.mark.unit, pytest.mark.hex_application, pytest.mark.usefixtures("operation")]


def _last_quarter_of_each_revision() -> tuple[Period, ...]:
    """Return the last declared quarter of each Modelo 303 design, first year inside the supported span."""
    periods: list[Period] = []
    with bundled_indexed_authority().operation() as operation:
        support = operation.supported_filing_years()
        for revision in operation.modelo_directory("303").revisions:
            year = max(revision.valid_from.year, support.floor)
            quarters = [
                str(code) for code in revision.period_selector.periods_for_year(year) if str(code).endswith("T")
            ]
            periods.append(Period.from_year_and_code(year, quarters[-1]))
    return tuple(periods)


_PERIODS = _last_quarter_of_each_revision()


def _projection_refs() -> tuple[
    M303Exonerado390ActivityProjectionRef | M303Exonerado390OperacionesTercerosProjectionRef,
    ...,
]:
    return (
        *(
            M303Exonerado390ActivityProjectionRef(
                projection_kind="m303_exonerado_390_activity",
                slot=slot,
                field=field,
            )
            for slot in range(1, 7)
            for field in M303Exonerado390ActivityField
        ),
        M303Exonerado390OperacionesTercerosProjectionRef(
            projection_kind="m303_exonerado_390_operaciones_terceros",
        ),
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


def _snapshot(period: Period) -> RegistrySnapshot:
    return published_snapshot("303", filing_year=period.filing_year, period=period.code)


def _record_design(registry_snapshot: RegistrySnapshot) -> SourceReference:
    return resolve_m303_regimen_simplificado_snapshot(
        registry_snapshot=registry_snapshot,
        scope_decision=M303RegimenSimplificadoScopeDecision(
            scope=m303_regime_composition_simplified_scope("general", authority=PublishedGovernedFactSource()),
        ),
    ).record_design


@pytest.mark.parametrize(("operaciones_terceros_declarables", "marker"), ((False, None), (True, "X")))
@pytest.mark.parametrize("period", _PERIODS)
def test_evidence_arrives_at_all_six_pairs_and_the_exact_modelo_347_marker_for_each_epoch(
    period: Period,
    operaciones_terceros_declarables: bool,
    marker: str | None,
) -> None:
    registry_snapshot = _snapshot(period)
    reference = FilingEvidenceReference(reference=f"test:dp30304:{period.filing_year}:{period.code}")
    evidence = _evidence(
        reference=reference,
        operaciones_terceros_declarables=operaciones_terceros_declarables,
        six_rows=True,
    )

    projection = project_m303_exonerado_390_value_arrival(
        registry_snapshot=registry_snapshot,
        projection_refs=_projection_refs(),
        evidence=evidence,
        record_design=_record_design(registry_snapshot),
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


def test_value_arrival_refuses_a_record_design_identity_mismatch() -> None:
    period = _PERIODS[-1]
    registry_snapshot = _snapshot(period)
    reference = FilingEvidenceReference(reference="test:dp30304:wrong-source")
    evidence = _evidence(
        reference=reference,
        operaciones_terceros_declarables=False,
        six_rows=False,
    )

    with pytest.raises(FilingExportError) as refusal:
        project_m303_exonerado_390_value_arrival(
            registry_snapshot=registry_snapshot,
            projection_refs=_projection_refs(),
            evidence=evidence,
            record_design=_record_design(registry_snapshot).model_copy(
                update={"id": "aeat-dr-303-not-in-this-snapshot"},
            ),
        )
    assert refusal.value.translated_message == (
        "application.filing.m303_exonerado_390.errors.record_design_source_not_snapshot_owned"
    )

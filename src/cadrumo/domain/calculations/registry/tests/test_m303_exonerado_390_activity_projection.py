"""Typed evidence projection for the DP30304 exonerado-390 activity rows."""

from __future__ import annotations

import inspect
from decimal import Decimal

import pytest
from pydantic import ValidationError

from .....core import (
    M303Exonerado390ActivityField,
    M303Exonerado390ActivityProjectionRef,
    M303Exonerado390OperacionesTercerosProjectionRef,
    validated_casilla_id,
)
from ....filing_evidence import FilingEvidenceReference
from ....modelos.calculation_revision import (
    M303Exonerado390ActivityRowEvidence,
    M303Exonerado390EndpointEvidence,
    M303Exonerado390FilingEvidence,
)
from ..m303_exonerado_390_projection import project_m303_exonerado_390_activity_rows

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]


def _reference() -> FilingEvidenceReference:
    return FilingEvidenceReference(reference="test:dp30304:exonerado-activity-rows")


def _endpoints(reference: FilingEvidenceReference) -> tuple[M303Exonerado390EndpointEvidence, ...]:
    return (
        M303Exonerado390EndpointEvidence(
            casilla_id=validated_casilla_id("79", surface="DP30304 projection test"),
            value=Decimal("0"),
            evidence_reference=reference,
        ),
    )


def _evidence(*, operaciones_terceros: bool = True, slots: int = 6) -> M303Exonerado390FilingEvidence:
    reference = _reference()
    return M303Exonerado390FilingEvidence(
        applicable=True,
        applicability_reference=reference,
        endpoints=_endpoints(reference),
        activity_rows=tuple(
            M303Exonerado390ActivityRowEvidence(
                slot=slot,
                codigo_actividad=f"A{slot:02d}",
                epigrafe_iae=f"41{slot:02d}",
                evidence_reference=reference,
            )
            for slot in range(1, slots + 1)
        ),
        operaciones_terceros_declarables=operaciones_terceros,
        operaciones_terceros_reference=reference,
    )


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


@pytest.mark.parametrize(("decision", "marker"), ((True, "X"), (False, None)))
def test_all_six_rows_and_explicit_modelo_347_decision_project_through_typed_refs(
    decision: bool,
    marker: str | None,
) -> None:
    projection = project_m303_exonerado_390_activity_rows(
        projection_refs=_projection_refs(),
        evidence=_evidence(operaciones_terceros=decision),
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
    assert tuple(field.projection_ref for field in projection.fields) == _projection_refs()


def test_unfilled_otras_slots_project_blank_rather_than_refusing() -> None:
    """DP30304 carries one Principal pair plus five optional ``Otras`` pairs."""
    projection = project_m303_exonerado_390_activity_rows(
        projection_refs=_projection_refs(),
        evidence=_evidence(operaciones_terceros=False, slots=1),
    )

    assert projection is not None
    assert tuple(field.value for field in projection.fields) == (
        "A01",
        "4101",
        *(None,) * 10,
        None,
    )


def test_applicable_evidence_refuses_noncontiguous_rows_and_an_unreferenced_modelo_347_decision() -> None:
    reference = _reference()
    with pytest.raises(ValidationError, match="contiguous ordered slots"):
        M303Exonerado390FilingEvidence(
            applicable=True,
            applicability_reference=reference,
            endpoints=_endpoints(reference),
            activity_rows=(
                M303Exonerado390ActivityRowEvidence(
                    slot=2,
                    codigo_actividad="A02",
                    epigrafe_iae="4102",
                    evidence_reference=reference,
                ),
            ),
            operaciones_terceros_declarables=False,
            operaciones_terceros_reference=reference,
        )

    payload = _evidence().model_dump(mode="python")
    payload["operaciones_terceros_reference"] = None
    with pytest.raises(ValidationError, match="Modelo 347 decision"):
        M303Exonerado390FilingEvidence.model_validate(payload)


def test_projection_identity_never_uses_json_serialisation() -> None:
    from .. import m303_exonerado_390_projection as module

    source = inspect.getsource(module)
    assert "model_dump_json" not in source
    assert "json.dumps" not in source

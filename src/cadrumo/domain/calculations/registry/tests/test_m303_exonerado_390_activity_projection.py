"""Typed evidence projection for all six DP30304 exonerado-390 activity rows."""

from __future__ import annotations

from decimal import Decimal

import pytest
from pydantic import ValidationError

from .....core import validated_casilla_id
from .....core.resources import bundled_path
from ....filing_evidence import FilingEvidenceReference
from ....modelos import (
    M303Exonerado390ActivityRowEvidence,
    M303Exonerado390EndpointEvidence,
    M303Exonerado390FilingEvidence,
)
from .. import (
    SourceRefId,
    extract_record_design,
    load_catalogue_file,
    project_m303_exonerado_390_activity_rows,
    resolve_record_design_binary,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]

_DESIGNS = (
    ("aeat-dr-303-2023", 2023, "2023"),
    ("aeat-dr-303-2024-early", 2024, "2024-early"),
    ("aeat-dr-303-2024-late", 2024, "2024-late"),
    ("aeat-dr-303-2025", 2025, "2025"),
    ("aeat-dr-303-2026", 2026, "2026"),
)


def _reference() -> FilingEvidenceReference:
    return FilingEvidenceReference(reference="test:dp30304:exonerado-activity-rows")


def _evidence() -> M303Exonerado390FilingEvidence:
    reference = _reference()
    return M303Exonerado390FilingEvidence(
        applicable=True,
        applicability_reference=reference,
        endpoints=(
            M303Exonerado390EndpointEvidence(
                casilla_id=validated_casilla_id("79", surface="DP30304 projection test"),
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
            for slot in range(1, 7)
        ),
        operaciones_terceros_declarables=True,
        operaciones_terceros_reference=reference,
    )


@pytest.mark.parametrize(("source_ref", "filing_year", "design_epoch"), _DESIGNS)
def test_all_six_evidenced_rows_project_to_the_exact_real_dp30304_anchors(
    source_ref: SourceRefId,
    filing_year: int,
    design_epoch: str,
) -> None:
    source_root = bundled_path()
    sources = load_catalogue_file(bundled_path("registry", "aeat", "legal", "iva.toml")).sources
    resolved = resolve_record_design_binary(
        source_root,
        sources,
        source_ref=source_ref,
        filing_year=filing_year,
        design_epoch=design_epoch,
    )
    sheet = next(item for item in extract_record_design(resolved.path) if item.name == "DP30304")

    projection = project_m303_exonerado_390_activity_rows(sheet, evidence=_evidence())

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
        "X",
    )


def test_applicable_evidence_refuses_noncontiguous_rows_and_an_unreferenced_modelo_347_decision() -> None:
    reference = _reference()
    with pytest.raises(ValidationError, match="contiguous ordered slots"):
        M303Exonerado390FilingEvidence(
            applicable=True,
            applicability_reference=reference,
            endpoints=(
                M303Exonerado390EndpointEvidence(
                    casilla_id=validated_casilla_id("79", surface="DP30304 projection test"),
                    value=Decimal("0"),
                    evidence_reference=reference,
                ),
            ),
            activity_rows=(
                M303Exonerado390ActivityRowEvidence(
                    slot=2,
                    codigo_actividad="A02",
                    epigrafe_iae="4102",
                    evidence_reference=reference,
                ),
            ),
            operaciones_terceros_declarables=False,
        )
    with pytest.raises(ValidationError, match="requires the Modelo 347 decision"):
        M303Exonerado390FilingEvidence(
            applicable=True,
            applicability_reference=reference,
            endpoints=(
                M303Exonerado390EndpointEvidence(
                    casilla_id=validated_casilla_id("79", surface="DP30304 projection test"),
                    value=Decimal("0"),
                    evidence_reference=reference,
                ),
            ),
            activity_rows=(
                M303Exonerado390ActivityRowEvidence(
                    slot=1,
                    codigo_actividad="A01",
                    epigrafe_iae="4101",
                    evidence_reference=reference,
                ),
            ),
            operaciones_terceros_declarables=False,
        )

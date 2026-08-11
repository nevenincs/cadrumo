"""Real DP30304 source projection from immutable S56 activity evidence."""

from __future__ import annotations

from decimal import Decimal

import pytest

from .....core import validated_casilla_id
from .....core.resources import bundled_path
from ....filing_evidence import FilingEvidenceReference
from ....modelos import (
    M303Exonerado390ActivityRowEvidence,
    M303Exonerado390EndpointEvidence,
    M303Exonerado390FilingEvidence,
)
from .. import (
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


def _evidence(*, operaciones_terceros_declarables: bool) -> M303Exonerado390FilingEvidence:
    reference = FilingEvidenceReference(reference="test:dp30304:real-projection")
    return M303Exonerado390FilingEvidence(
        applicable=True,
        applicability_reference=reference,
        endpoints=(
            M303Exonerado390EndpointEvidence(
                casilla_id=validated_casilla_id("79", surface="S56 source projection test"),
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


@pytest.mark.parametrize("source_ref, filing_year, epoch", _DESIGNS)
@pytest.mark.parametrize(("operaciones_terceros_declarables", "marker"), ((False, None), (True, "X")))
def test_real_dp30304_projects_intrinsically_canonical_order_for_each_epoch(
    source_ref: str,
    filing_year: int,
    epoch: str,
    operaciones_terceros_declarables: bool,
    marker: str | None,
) -> None:
    source_root = bundled_path()
    catalogues = load_catalogue_file(bundled_path("registry", "aeat", "legal", "iva.toml"))
    resolved = resolve_record_design_binary(
        source_root,
        catalogues.sources,
        source_ref=source_ref,
        filing_year=filing_year,
        design_epoch=epoch,
    )
    sheet = next(item for item in extract_record_design(resolved.path) if item.name == "DP30304")

    projection = project_m303_exonerado_390_activity_rows(
        sheet,
        design_epoch=epoch,
        expected_design_epoch=epoch,
        evidence=_evidence(operaciones_terceros_declarables=operaciones_terceros_declarables),
    )

    assert projection is not None
    assert tuple((field.ordinal, field.offset, field.length) for field in projection.fields) == (
        (6, 13, 3),
        (7, 16, 4),
        (8, 20, 3),
        (9, 23, 4),
        (10, 27, 3),
        (11, 30, 4),
        (12, 34, 3),
        (13, 37, 4),
        (14, 41, 3),
        (15, 44, 4),
        (16, 48, 3),
        (17, 51, 4),
        (18, 55, 1),
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
